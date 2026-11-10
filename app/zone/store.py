"""The run-zone runner's state store (eye/ZONE_LIVE.md L8): the record for the owner and ``zone status``
- candidates (``zone_live_setup``), every request to the broker (``zone_live_request``, written ``intent``
before the send), the visit records of each closed H1 bar (``zone_live_visit``), the stop request
(``zone_live_stop``) and a status snapshot (``zone_live_state``). The runner never rebuilds a setup from
them (L8). Layer 10: it uses the storage layer (the engine database, tables created by migration 0044)."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.storage.database import Database
from app.storage.models import (
    ZoneLiveRequestRow,
    ZoneLiveSetupRow,
    ZoneLiveStateRow,
    ZoneLiveStopRow,
    ZoneLiveVisitRow,
)

OPEN_REQUEST_STATES = ("intent", "sent", "unknown")
RESERVING = ("no fill", "cancel", "traded")  # L6: the outcomes of the hour's setup that reserve


class ZoneStore:
    """All reads and writes of the zone tables. Every write is its own transaction (the write-ahead rule)."""

    def __init__(self, db: Database, login: int, server: str) -> None:
        self.db = db
        self.login = int(login)
        self.server = server

    # --- setups -------------------------------------------------------------------------------------------

    def add_setup(self, now: datetime, **fields: Any) -> int:
        row = ZoneLiveSetupRow(
            account_login=self.login, account_server=self.server, created_at=now, updated_at=now, **fields
        )
        with self.db.session() as sess:
            sess.add(row)
            sess.flush()
            return int(row.id)

    def add_setups(self, now: datetime, rows: list[dict[str, Any]]) -> list[int]:
        """All of an hour's candidate rows in ONE transaction: a crash leaves the hour with all of them or
        none."""
        made = [
            ZoneLiveSetupRow(
                account_login=self.login, account_server=self.server, created_at=now, updated_at=now, **fields
            )
            for fields in rows
        ]
        with self.db.session() as sess:
            sess.add_all(made)
            sess.flush()
            return [int(r.id) for r in made]

    def update_setup(self, setup_id: int, now: datetime, **fields: Any) -> None:
        with self.db.session() as sess:
            row = sess.get(ZoneLiveSetupRow, setup_id)
            if row is None:
                raise KeyError(f"no zone_live_setup {setup_id}")
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = now

    def setup(self, setup_id: int) -> ZoneLiveSetupRow | None:
        with self.db.session() as sess:
            row = sess.get(ZoneLiveSetupRow, setup_id)
            if row is not None:
                sess.expunge(row)
            return row

    def setups(
        self,
        *,
        states: Collection[str] | None = None,
        hour_open: datetime | None = None,
        all_accounts: bool = False,
    ) -> list[ZoneLiveSetupRow]:
        stmt = select(ZoneLiveSetupRow).order_by(ZoneLiveSetupRow.id)
        if not all_accounts:
            stmt = stmt.where(ZoneLiveSetupRow.account_login == self.login)
            stmt = stmt.where(ZoneLiveSetupRow.account_server == self.server)
        if states is not None:
            stmt = stmt.where(ZoneLiveSetupRow.state.in_(list(states)))
        if hour_open is not None:
            stmt = stmt.where(ZoneLiveSetupRow.hour_open == hour_open)
        with self.db.session() as sess:
            rows = list(sess.scalars(stmt))
            sess.expunge_all()
            return rows

    def last_reservation_end(self, before: datetime | None = None) -> datetime | None:
        """The latest reservation end among this account's ended setups that reserve (L6: the hour's setup,
        by ``no fill``, ``cancel`` or its exit); those of hours before ``before`` only, when given."""
        stmt = (
            select(func.max(ZoneLiveSetupRow.end_close_time))
            .where(ZoneLiveSetupRow.account_login == self.login)
            .where(ZoneLiveSetupRow.account_server == self.server)
            .where(ZoneLiveSetupRow.chosen.is_(True))
            .where(ZoneLiveSetupRow.state == "ended")
            .where(ZoneLiveSetupRow.outcome.in_(RESERVING))
        )
        if before is not None:
            stmt = stmt.where(ZoneLiveSetupRow.hour_open < before)
        with self.db.session() as sess:
            value = sess.scalar(stmt)
        return None if value is None else value

    def end_unfinished(self, now: datetime, outcome: str, note: str) -> list[int]:
        """L8 - every unfinished row of this account (live, or dropped and not yet final) ends ``outcome``, in
        one transaction; the ids."""
        stmt = (
            select(ZoneLiveSetupRow)
            .where(ZoneLiveSetupRow.account_login == self.login)
            .where(ZoneLiveSetupRow.account_server == self.server)
            .where(ZoneLiveSetupRow.state.in_(("live", "dropped")))
        )
        out: list[int] = []
        with self.db.session() as sess:
            for row in sess.scalars(stmt):
                if row.state == "dropped" and row.outcome is not None:
                    continue  # a final drop (one for the other's visit has no outcome until its hour closes)
                row.state, row.outcome, row.updated_at = "ended", outcome, now
                row.note = (row.note + "; " if row.note else "") + note
                out.append(int(row.id))
        return out

    def close_requests(self, now: datetime, note: str) -> int:
        """L8 - every request of this account still open is closed (``intent`` and ``unknown`` ones ``moot``;
        a place's order is no longer followed), in one transaction; how many."""
        stmt = (
            select(ZoneLiveRequestRow)
            .where(ZoneLiveRequestRow.account_login == self.login)
            .where(ZoneLiveRequestRow.account_server == self.server)
            .where(ZoneLiveRequestRow.closed_at.is_(None))
        )
        n = 0
        with self.db.session() as sess:
            for row in sess.scalars(stmt):
                if row.state in ("intent", "unknown"):
                    row.state = "moot"
                if row.kind == "place" and row.order_state == "open":
                    row.order_state = "unfollowed"
                row.closed_at = now
                row.detail = (row.detail + "; " if row.detail else "") + note
                n += 1
        return n

    # --- requests -----------------------------------------------------------------------------------------

    def add_request(
        self,
        now: datetime,
        *,
        setup_id: int,
        kind: str,
        name: str = "",
        comment: str | None = None,
        payload_json: str = "{}",
        market: bool = False,
        order_ticket: int | None = None,
        position_ticket: int | None = None,
    ) -> int:
        """The intent: written, committed, before the request is sent."""
        row = ZoneLiveRequestRow(
            setup_id=setup_id,
            account_login=self.login,
            account_server=self.server,
            kind=kind,
            name=name,
            comment=comment,
            state="intent",
            order_state="open" if kind == "place" else "",
            payload_json=payload_json,
            market=market,
            order_ticket=order_ticket,
            position_ticket=position_ticket,
            intent_at=now,
        )
        with self.db.session() as sess:
            sess.add(row)
            sess.flush()
            return int(row.id)

    def update_request(self, request_id: int, **fields: Any) -> None:
        with self.db.session() as sess:
            row = sess.get(ZoneLiveRequestRow, request_id)
            if row is None:
                raise KeyError(f"no zone_live_request {request_id}")
            for key, value in fields.items():
                setattr(row, key, value)

    def requests(
        self,
        *,
        setup_id: int | None = None,
        kinds: Collection[str] | None = None,
        states: Collection[str] | None = None,
        order_states: Collection[str] | None = None,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[ZoneLiveRequestRow]:
        stmt = select(ZoneLiveRequestRow).where(ZoneLiveRequestRow.account_login == self.login)
        stmt = stmt.where(ZoneLiveRequestRow.account_server == self.server)
        if setup_id is not None:
            stmt = stmt.where(ZoneLiveRequestRow.setup_id == setup_id)
        if kinds is not None:
            stmt = stmt.where(ZoneLiveRequestRow.kind.in_(list(kinds)))
        if states is not None:
            stmt = stmt.where(ZoneLiveRequestRow.state.in_(list(states)))
        if order_states is not None:
            stmt = stmt.where(ZoneLiveRequestRow.order_state.in_(list(order_states)))
        stmt = stmt.order_by(ZoneLiveRequestRow.id.desc() if newest_first else ZoneLiveRequestRow.id)
        if limit is not None:
            stmt = stmt.limit(limit)
        with self.db.session() as sess:
            rows = list(sess.scalars(stmt))
            sess.expunge_all()
            return rows

    def request_by_comment(self, comment: str) -> ZoneLiveRequestRow | None:
        stmt = select(ZoneLiveRequestRow).where(ZoneLiveRequestRow.comment == comment)
        with self.db.session() as sess:
            row = sess.scalar(stmt)
            if row is not None:
                sess.expunge(row)
            return row

    def count_places(self, setup_id: int, name: str) -> int:
        """How many place requests the setup's order ``name`` has had (the ``n`` of the next comment)."""
        stmt = (
            select(func.count())
            .select_from(ZoneLiveRequestRow)
            .where(ZoneLiveRequestRow.setup_id == setup_id)
            .where(ZoneLiveRequestRow.kind == "place")
            .where(ZoneLiveRequestRow.name == name)
        )
        with self.db.session() as sess:
            return int(sess.scalar(stmt) or 0)

    # --- visits -------------------------------------------------------------------------------------------

    def add_visits(self, now: datetime, records: list[dict[str, Any]]) -> None:
        """All the visit records of one H1 bar in ONE transaction: a crash leaves the hour recorded whole or
        not
        at all."""
        rows = [
            ZoneLiveVisitRow(
                account_login=self.login,
                account_server=self.server,
                hour_open=r["hour_open"],
                side=r["side"],
                line=r["line"],
                classification=r["classification"],
                setup_id=r["setup_id"],
                agreed=r["agreed"],
                note=r["note"],
                outcome=r.get("outcome"),
                recorded_at=now,
            )
            for r in records
        ]
        with self.db.session() as sess:
            sess.add_all(rows)

    def set_visit_outcome(self, setup_id: int, outcome: str) -> None:
        """L4 - every visit row linked to the setup (``setup``, ``busy``) is given its
        outcome when the setup ends."""
        stmt = select(ZoneLiveVisitRow).where(ZoneLiveVisitRow.setup_id == setup_id)
        with self.db.session() as sess:
            for row in sess.scalars(stmt):
                row.outcome = outcome

    def visits(self, hour_open: datetime | None = None) -> list[ZoneLiveVisitRow]:
        stmt = select(ZoneLiveVisitRow).where(ZoneLiveVisitRow.account_login == self.login)
        stmt = stmt.where(ZoneLiveVisitRow.account_server == self.server)
        if hour_open is not None:
            stmt = stmt.where(ZoneLiveVisitRow.hour_open == hour_open)
        with self.db.session() as sess:
            rows = list(sess.scalars(stmt.order_by(ZoneLiveVisitRow.id)))
            sess.expunge_all()
            return rows

    # --- the stop request ---------------------------------------------------------------------------------

    def request_stop(self, now: datetime, by: str, *, now_flag: bool = False) -> int:
        row = ZoneLiveStopRow(requested_at=now, requested_by=by, now=now_flag)
        with self.db.session() as sess:
            sess.add(row)
            sess.flush()
            return int(row.id)

    def pending_stop(self) -> ZoneLiveStopRow | None:
        stmt = select(ZoneLiveStopRow).where(ZoneLiveStopRow.acknowledged_at.is_(None))
        with self.db.session() as sess:
            row = sess.scalars(stmt.order_by(ZoneLiveStopRow.id)).first()
            if row is not None:
                sess.expunge(row)
            return row

    def pending_stops(self) -> list[ZoneLiveStopRow]:
        """Every request not yet acknowledged, oldest first."""
        stmt = select(ZoneLiveStopRow).where(ZoneLiveStopRow.acknowledged_at.is_(None))
        with self.db.session() as sess:
            rows = list(sess.scalars(stmt.order_by(ZoneLiveStopRow.id)))
            sess.expunge_all()
            return rows

    def stop(self, stop_id: int) -> ZoneLiveStopRow | None:
        with self.db.session() as sess:
            row = sess.get(ZoneLiveStopRow, stop_id)
            if row is not None:
                sess.expunge(row)
            return row

    def acknowledge_stop(self, stop_id: int, now: datetime, note: str = "") -> None:
        with self.db.session() as sess:
            row = sess.get(ZoneLiveStopRow, stop_id)
            if row is not None:
                row.acknowledged_at = now
                row.note = note

    # --- the status snapshot ------------------------------------------------------------------------------

    def set_state(self, key: str, value: str, now: datetime) -> None:
        with self.db.session() as sess:
            row = sess.get(ZoneLiveStateRow, key)
            if row is None:
                sess.add(ZoneLiveStateRow(key=key, value=value, updated_at=now))
            else:
                row.value, row.updated_at = value, now

    def get_state(self, key: str) -> str | None:
        with self.db.session() as sess:
            row = sess.get(ZoneLiveStateRow, key)
            return None if row is None else row.value

    def all_state(self) -> dict[str, tuple[str, datetime]]:
        with self.db.session() as sess:
            return {r.key: (r.value, r.updated_at) for r in sess.scalars(select(ZoneLiveStateRow))}
