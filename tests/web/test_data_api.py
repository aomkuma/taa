"""Read APIs over the replicated engine data, scoped to the session user's engines (TAA-803)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.clock import ManualClock
from app.core.enums import Timeframe
from app.market_data.history_store import SqlHistoryStore
from app.storage.audit import AuditLog
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    ConfigSnapshot,
    DecisionCheckRow,
    DecisionRecordRow,
    EngineHeartbeatRow,
    PaperPositionRow,
    Run,
)
from app.sync.command_queue import CommandQueue
from app.sync.events import SPECS_BY_TYPE
from app.sync.ingest import IngestService
from app.web.stream import StreamTiming
from tests.sync_data import T, sample_rows
from tests.web.conftest import DEV_ENV, PASSWORD, TOTP_SECRET, login, make_app

ROUTES = [
    "status",
    "quotes",
    "account",
    "positions",
    "trades",
    "trades/1",
    "intents",
    "decisions",
    "decisions/d1",
    "breakers",
    "kill-switch",
    "symbols",
    "symbols/EURUSD",
    "candles?symbol=EURUSD",
    "config",
    "strategies",
    "audit/verify",
    "stream",
    "commands",
    "commands/c1",
    "backtests",
    "backtests/b1",
    "backtests/b1/trades",
    "backtests/compare?ids=b1,b2",
    "ranking",
    "ranking/EURUSD",
    "ranking/EURUSD/history",
    "opportunities",
    "opportunities/k1",
    "shadow-trades",
    "accuracy",
    "threshold-explorer",
    "theory-scoreboard",
    "calibration",
]


def position(engine_id: str, ticket: int, *, exit_minutes: int | None, net: float = 5.0) -> PaperPositionRow:
    entry = T + timedelta(minutes=15 * ticket)
    return PaperPositionRow(
        engine_id=engine_id,
        ticket=ticket,
        account_key="acct",
        intent_id=f"p{ticket}",
        symbol="EURUSD",
        side="BUY",
        volume=0.1,
        entry_time=entry,
        entry_price=1.1,
        sl=1.095,
        tp=1.11,
        stop_kind="SL",  # ExitReason.STOP_LOSS: the initial stop
        status="OPEN" if exit_minutes is None else "CLOSED",
        exit_time=None if exit_minutes is None else entry + timedelta(minutes=exit_minutes),
        exit_price=None if exit_minutes is None else 1.105,
        exit_reason=None if exit_minutes is None else "TP",
        net=None if exit_minutes is None else net,
        r_multiple=None if exit_minutes is None else 1.0,
        updated_at=entry,
    )


def candles(n: int, start: datetime = T) -> pd.DataFrame:
    times = pd.date_range(start, periods=n, freq="15min", tz=UTC)
    closes = [1.1 + 0.001 * (i % 7) for i in range(n)]
    return pd.DataFrame(
        {
            "open_time": times,
            "close_time": times + pd.Timedelta(minutes=15),
            "time_server": [int(t.timestamp()) for t in times],
            "open": closes,
            "high": [c + 0.002 for c in closes],
            "low": [c - 0.002 for c in closes],
            "close": closes,
            "tick_volume": 10,
            "spread": 12,
            "real_volume": 0,
        }
    )


def fill(db: Database, engine_id: str, clock: ManualClock) -> None:
    with db.session() as sess:
        for row in sample_rows():
            if hasattr(row, "engine_id"):
                row.engine_id = engine_id
            if not isinstance(row, PaperPositionRow):
                sess.add(row)
        sess.add_all(position(engine_id, t, exit_minutes=30, net=float(t)) for t in range(1, 6))
        sess.add(position(engine_id, 10, exit_minutes=None))
        for i, name in enumerate(["spread", "risk"]):
            sess.add(
                DecisionCheckRow(
                    engine_id=engine_id,
                    decision_id="d2",
                    seq=i,
                    name=name,
                    reason="OK",
                    passed=True,
                    kind="HARD",
                )
            )
        d1 = sess.get(DecisionRecordRow, (engine_id, "d1"))
        assert d1 is not None
        d1.created_at = T + timedelta(minutes=30)
    SqlHistoryStore(db, engine_id).save("FBS-Demo", "EURUSD", Timeframe.M15, candles(200))
    log = AuditLog(Database("sqlite://"), f"engine:{engine_id}", clock)
    log.db.create_all()
    spec = SPECS_BY_TYPE["audit_event"]
    events = [
        {
            "event_id": f"0191a0a0-0000-7000-8000-00000000000{i}",
            "type": "audit_event",
            "occurred_at_utc": T.isoformat(),
            "payload": spec.payload(log.append("T", "e", {"i": i})),
        }
        for i in range(3)
    ]
    doc = {"schema": 1, "engine_id": engine_id, "sent_at_utc": T.isoformat(), "events": events}
    assert IngestService(db, clock, CommandQueue(db, clock)).ingest(engine_id, doc).accepted == 3


@pytest.fixture
def rig(db: Database, clock: ManualClock, static_dir: Path) -> Iterator[tuple[TestClient, str, str]]:
    app = make_app(db, clock, static_dir, DEV_ENV | {"MULTI_ENGINE_ENABLED": "true"})
    app.state.ctx.streams.timing = StreamTiming(stream_seconds=0.0)  # the stream route answers and closes
    auth, registry = app.state.ctx.auth, app.state.ctx.engine.registry
    ids = []
    for name, role in (("alice", "OWNER"), ("bob", "SUBSCRIBER")):
        user = auth.create_user(name, PASSWORD, TOTP_SECRET, role=role)
        ids.append(registry.register(user, f"{name} pc", actor=name).engine_id)
    for engine_id in ids:
        fill(db, engine_id, clock)
    with db.session() as sess:  # bob's config holds a secret the API must never show
        sess.add(
            ConfigSnapshot(engine_id=ids[1], config_hash="h" * 32, payload={"env": {"MT5_PASSWORD": "real"}})
        )
    with TestClient(app, base_url="https://testserver") as client:
        assert login(client, clock, username="alice").status_code == 200
        yield client, ids[0], ids[1]


def get(client: TestClient, engine_id: str, route: str) -> Any:
    return client.get(f"/api/v1/engines/{engine_id}/{route}")


class TestOwnership:
    def test_another_users_engine_is_not_found_on_every_route(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, theirs = rig
        for route in ROUTES:
            assert get(client, mine, route).status_code in (200, 404), route
            resp = get(client, theirs, route)
            assert resp.status_code == 404 and resp.json()["error"]["code"] == "engine_not_found", route
        for bogus in ("eng_doesnotexist", "../../etc", "x" * 65):
            assert get(client, bogus, "status").status_code == 404

    def test_signed_out_users_get_401(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        client.post(
            "/api/v1/auth/logout",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "X-CSRF-Token": client.get("/api/v1/auth/session").json()["csrf_token"],
            },
        )
        assert get(client, mine, "status").json()["error"]["code"] == "unauthenticated"


class TestReads:
    def test_status(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        body = get(client, mine, "status").json()
        assert body["engine"]["engine_id"] == mine and body["engine"]["label"] == "alice pc"
        assert body["open_positions"] == 1 and body["kill_switch"]["active"] is True
        assert body["run"]["run_id"] == "r1" and "host" not in body["run"] and "engine_id" not in body["run"]
        assert body["audit"]["status"] == "OK"
        assert (
            "last_received_at" in body
        )  # newest row event applied (none in this rig: rows were written directly)
        assert body["heartbeat"] is None  # no heartbeat received yet

    def test_status_carries_the_newest_heartbeat_and_the_watchdog_verdict(
        self, rig: tuple[TestClient, str, str], db: Database
    ) -> None:
        client, mine, theirs = rig
        brief = {"at": T.isoformat(), "mode": "PAPER", "state": "running", "connected": True, "cycles": 3}
        assert get(client, mine, "quotes").json() == {"at": None, "received_at": None, "quotes": []}
        with db.session() as sess:
            sess.add(
                EngineHeartbeatRow(
                    engine_id=mine,
                    received_at=T + timedelta(seconds=1),
                    sent_at=T,
                    run_id="r1",
                    mode="PAPER",
                    state="running",
                    connected=True,
                    payload=brief,
                    watch_status="OFFLINE",
                    offline_since=T + timedelta(minutes=2),
                    offline_reason="SILENT",
                )
            )
        assert get(client, mine, "quotes").json()["quotes"] == []  # a heartbeat from before TAA-906
        quote = {
            "symbol": "EURUSD",
            "bid": 1.1,
            "ask": 1.1001,
            "spread_points": 10.0,
            "max_spread_points": 30.0,
        }
        with db.session() as sess:
            row = sess.get(EngineHeartbeatRow, mine)
            assert row is not None
            row.payload = {**brief, "quotes": [quote]}
        assert get(client, mine, "quotes").json()["quotes"] == [quote]
        beat = get(client, mine, "status").json()["heartbeat"]
        assert beat == {
            **brief,
            "received_at": (T + timedelta(seconds=1)).isoformat(),
            "watch_status": "OFFLINE",
            "offline_since": (T + timedelta(minutes=2)).isoformat(),
            "offline_reason": "SILENT",
        }
        assert get(client, theirs, "status").status_code == 404  # still only the user's own engine

    def test_a_trade_with_its_intent_decision_and_lifecycle(
        self, rig: tuple[TestClient, str, str], db: Database
    ) -> None:
        client, mine, theirs = rig
        entry = T + timedelta(minutes=15)  # ticket 1 of the rig: entered T+15 min, closed 30 min later
        events = [
            (entry, "POSITION_OPENED", {"ticket": 1, "paper": True, "price": 1.1}),
            (
                entry + timedelta(minutes=10),
                "STOP_MOVED",
                {"ticket": 1, "paper": True, "new": 1.1, "kind": "BREAK_EVEN"},
            ),
            (
                entry + timedelta(minutes=12),
                "STOP_MOVED",
                {"ticket": 1, "paper": False, "new": 1.2},
            ),  # a broker one
            (entry + timedelta(minutes=13), "STOP_MOVED", {"ticket": 2, "paper": True, "new": 1.1}),
            (entry + timedelta(minutes=30), "POSITION_CLOSED", {"ticket": 1, "paper": True, "reason": "TP"}),
            (entry + timedelta(hours=3), "POSITION_CLOSED", {"ticket": 1, "paper": True}),  # a later trade's
        ]
        with db.session() as sess:
            for seq, (at, kind, payload) in enumerate(events, start=1):
                sess.add(
                    AuditEvent(
                        engine_id=mine,
                        event_id=f"0191a0a0-0000-7000-8000-0000000001{seq:02d}",
                        chain="engine:test",
                        seq=seq,
                        ts_utc=at,
                        actor="engine",
                        event_type=kind,
                        payload=payload,
                        prev_hash="0" * 64,
                        hash=f"{seq:064d}",
                    )
                )
        body = get(client, mine, "trades/1").json()
        assert body["position"]["ticket"] == 1 and body["intent"]["intent_id"] == "p1"
        assert body["decision"]["decision_id"] == "d1" and [c["name"] for c in body["decision"]["checks"]]
        assert "market" not in body["decision"] and "signal" in body["decision"]
        assert [(e["type"], e["payload"].get("kind")) for e in body["events"]] == [
            ("POSITION_OPENED", None),
            ("STOP_MOVED", "BREAK_EVEN"),
            ("POSITION_CLOSED", None),
        ]
        assert get(client, mine, "trades/999").json()["error"]["code"] == "trade_not_found"
        assert get(client, theirs, "trades/1").status_code == 404

    def test_positions_paginate_newest_first(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        tickets: list[int] = []
        cursor = None
        for _ in range(4):
            q = "trades?limit=2" + (f"&cursor={cursor}" if cursor else "")
            page = get(client, mine, q).json()
            tickets += [p["ticket"] for p in page["items"]]
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert tickets == [5, 4, 3, 2, 1]
        assert [p["ticket"] for p in get(client, mine, "positions?status=OPEN").json()["items"]] == [10]
        assert get(client, mine, "positions?cursor=garbage").json()["error"]["code"] == "invalid_query"
        assert get(client, mine, "positions?limit=500").status_code == 422

    def test_account_has_a_realized_equity_curve(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        body = get(client, mine, "account").json()
        curve = body["realized_equity"]["acct"]
        assert [p["equity"] for p in curve] == [1001.0, 1003.0, 1006.0, 1010.0, 1015.0]
        assert body["paper_accounts"][0]["balance"] == 1000.0

    def test_decisions_filter_by_reason_code(self, rig: tuple[TestClient, str, str], db: Database) -> None:
        client, mine, _ = rig
        rows = {
            "r1": ["SPREAD_TOO_WIDE"],
            "r2": ["BREAKER_OPEN:daily_loss", "SPREAD_TOO_WIDE"],
            "r3": ["SPREADXTOOXWIDE"],  # matches only if "_" were a wildcard
            "r4": ["BREAKER_OPEN_SOON"],  # a longer code: not BREAKER_OPEN
        }
        with db.session() as sess:
            d1 = sess.get(DecisionRecordRow, (mine, "d1"))
            assert d1 is not None
            for i, (decision_id, codes) in enumerate(rows.items(), start=1):
                sess.add(
                    DecisionRecordRow(
                        **{
                            c.key: getattr(d1, c.key)
                            for c in DecisionRecordRow.__table__.columns
                            if c.key not in ("decision_id", "reason_codes", "decision", "created_at")
                        },
                        decision_id=decision_id,
                        reason_codes=codes,
                        decision="REJECT",
                        created_at=T + timedelta(hours=i),
                    )
                )

        def ids(query: str) -> list[str]:
            return [d["decision_id"] for d in get(client, mine, f"decisions?{query}").json()["items"]]

        assert ids("reason=SPREAD_TOO_WIDE") == ["r2", "r1"]
        assert ids("reason=BREAKER_OPEN") == ["r2"]  # the parameterized code, not BREAKER_OPEN_SOON
        assert ids("reason=SPREAD") == []
        assert ids("reason=SPREAD_TOO_WIDE&symbol=XAUUSD") == []
        assert get(client, mine, "decisions?reason=spread").status_code == 422
        assert get(client, mine, "decisions?reason=%25%22").status_code == 422

    def test_decisions_list_and_detail(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        [item] = get(client, mine, "decisions?decision=ACCEPT").json()["items"]
        assert item["decision_id"] == "d1" and "signal" not in item and "market" not in item
        assert get(client, mine, "decisions?decision=REJECT").json()["items"] == []
        detail = get(client, mine, "decisions/d1").json()
        assert detail["signal"] == {"score": 0.7} and [c["seq"] for c in detail["checks"]] == [0]
        assert get(client, mine, "decisions/nope").json()["error"]["code"] == "decision_not_found"
        assert get(client, mine, "decisions?decision=MAYBE").status_code == 422

    def test_intents_breakers_kill_switch_symbols(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        assert [i["intent_id"] for i in get(client, mine, "intents?kind=broker").json()["items"]] == ["i1"]
        assert [i["intent_id"] for i in get(client, mine, "intents").json()["items"]] == ["p1"]
        breakers = get(client, mine, "breakers").json()
        assert breakers["states"][0]["name"] == "DAILY_LOSS" and len(breakers["events"]["items"]) == 1
        assert get(client, mine, "kill-switch").json()["items"][0]["action"] == "ACTIVATE"
        [sym] = get(client, mine, "symbols").json()["items"]
        assert sym["symbol"] == "EURUSD" and "spec" not in sym
        assert get(client, mine, "symbols/EURUSD").json()["spec"] == {"digits": 5}
        assert get(client, mine, "symbols/XXX").json()["error"]["code"] == "symbol_not_found"

    def test_config_is_masked(self, rig: tuple[TestClient, str, str], db: Database) -> None:
        client, mine, _ = rig
        with db.session() as sess:
            snap = sess.get(ConfigSnapshot, (mine, "c" * 32))
            assert snap is not None
            snap.payload = {
                "env": {"MT5_PASSWORD": "***set***", "AI_API_KEY": "leaked", "MT5_LOGIN": "12***78"},
                "x": [{"engine_hmac_secret": "s"}],
            }
            run = sess.get(Run, (mine, "r1"))
            assert run is not None
        body = get(client, mine, "config").json()
        env = body["config"]["env"]
        assert env["AI_API_KEY"] == "***" and env["MT5_PASSWORD"] == "***" and env["MT5_LOGIN"] == "12***78"
        assert body["config"]["x"] == [{"engine_hmac_secret": "***"}] and "leaked" not in str(body)

    def test_audit_verify(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        body = get(client, mine, "audit/verify").json()
        assert body["ok"] is True and body["events_checked"] == 3


class TestCandles:
    def test_bars_overlays_and_markers(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        body = get(
            client,
            mine,
            "candles?symbol=EURUSD&timeframe=M15&limit=50&overlays=ema:20,bb:20,rsi:14,atr:14,adx:14",
        ).json()
        assert body["server"] == "FBS-Demo" and len(body["bars"]) == 50
        assert set(body["overlays"]) == {
            "ema:20",
            "bb:20:upper",
            "bb:20:mid",
            "bb:20:lower",
            "rsi:14",
            "atr:14",
            "adx:14",
        }
        assert all(len(v) == 50 for v in body["overlays"].values())
        assert all(v is not None for v in body["overlays"]["ema:20"])  # warmed up on earlier bars
        first = datetime.fromisoformat(body["bars"][0][0])
        assert first == T + timedelta(minutes=15 * 150)

    def test_a_window_with_markers(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        start = (T).isoformat().replace("+00:00", "Z")
        body = get(client, mine, f"candles?symbol=EURUSD&start={start}&limit=12&overlays=ema:5").json()
        assert datetime.fromisoformat(body["bars"][0][0]) == T and len(body["bars"]) == 12
        assert body["overlays"]["ema:5"][0] is None  # nothing before the first stored bar to warm up on
        kinds = [(m["kind"], m.get("ticket")) for m in body["markers"]]
        assert ("decision", None) in kinds and ("entry", 1) in kinds and ("exit", 1) in kinds

    def test_sr_zones_at_the_last_bar(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        assert "zones" not in get(client, mine, "candles?symbol=EURUSD&limit=50").json()
        zones = get(client, mine, "candles?symbol=EURUSD&limit=50&zones=true").json()["zones"]
        # the sawtooth repeats its highs (1.108) and lows (1.098): one zone each, many touches
        assert {z["role"] for z in zones} == {"SUPPORT", "RESISTANCE"}
        top = max(zones, key=lambda z: z["high"])
        assert top["role"] == "RESISTANCE" and top["high"] == pytest.approx(1.108) and top["touches"] > 5
        assert all(z["low"] <= z["high"] for z in zones) and len(zones) <= 8

    def test_an_empty_window(self, rig: tuple[TestClient, str, str]) -> None:
        client, mine, _ = rig
        late = (T + timedelta(days=30)).isoformat().replace("+00:00", "Z")
        body = get(client, mine, f"candles?symbol=EURUSD&start={late}&overlays=ema:5").json()
        assert body["bars"] == [] and body["overlays"] == {"ema:5": []} and body["markers"] == []

    @pytest.mark.parametrize(
        ("query", "code"),
        [
            ("candles?symbol=EURUSD&timeframe=W1", "invalid_query"),
            ("candles?symbol=EURUSD&overlays=macd:12", "invalid_query"),
            ("candles?symbol=EURUSD&start=2026-09-30T10:00:00", "invalid_query"),
            ("candles?symbol=NOPE", "candles_not_found"),
        ],
    )
    def test_bad_queries(self, rig: tuple[TestClient, str, str], query: str, code: str) -> None:
        client, mine, _ = rig
        assert get(client, mine, query).json()["error"]["code"] == code
