"""Advisory read models and the users' preferences in the cloud (PLAN §A25–§A31; TAA-809).

- :class:`PreferenceStore`: one validated :class:`AdvisoryPreferences` document per user
  (``user_advisory_prefs``; defaults when absent). Every save is checked against the detector and strategy
  catalogs (:func:`parse_preferences`), so a stored document is always usable by the engine and the
  personalizer.
- :func:`engine_advisory_config`: the compute requirements an engine serves (the union of its users' needs;
  with per-user engines, its owner's).
- :class:`AdvisoryReads`: ranking, opportunities (with evidence, win probability contributions and shadow
  results), shadow trades, accuracy, threshold explorer, theory scoreboard and calibration, always for one
  engine. Shadow statistics are hypothetical by construction; every report says which source it is.
"""

from __future__ import annotations

import dataclasses
import enum
import math
from collections.abc import Hashable, Mapping, Sequence
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from sqlalchemy import select

from app.advisory.calibration import latest_version, load_version
from app.advisory.confidence import Query, Source
from app.advisory.preferences import AdvisoryPreferences, parse_preferences
from app.advisory.requirements import AdvisoryConfig, advisory_config, content_version, pattern_setups
from app.advisory.shadow import Variant
from app.advisory.stats import (
    accuracy_report,
    load_records,
    scoreboard,
    threshold_explorer,
)
from app.advisory.suitability import Gate
from app.core.clock import ensure_utc
from app.core.errors import TaaError
from app.evidence.catalog import default_registry as evidence_registry
from app.evidence.framework import Family
from app.evidence.registry import DetectorRegistry
from app.storage.database import Database
from app.storage.models import (
    AccountProfileRow,
    CalibrationTableRow,
    DecisionCheckRow,
    DecisionRecordRow,
    OpportunityAlertRow,
    OpportunityRow,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
    UserAdvisoryPrefsRow,
)
from app.strategy.catalog import default_registry as strategy_registry
from app.strategy.registry import StrategyRegistry
from app.sync.events import json_safe
from app.web.account_profiles import HistoryRates
from app.web.readmodels import Page, QueryError, paginate, row_dict

# Minimum-lot affordability and margin share depend on the account, not the market.
ACCOUNT_GATES = frozenset({Gate.G2_MIN_LOT.value, Gate.G3_MARGIN.value})

MAX_HISTORY_HOURS = 24 * 90


@lru_cache(maxsize=1)
def catalogs() -> tuple[DetectorRegistry, StrategyRegistry]:
    return evidence_registry(), strategy_registry()


def plain(value: Any) -> Any:
    """Dataclasses, enums and tuple keys of the advisory reports as JSON-ready values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, Mapping):
        return {_key(k): plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [plain(v) for v in value]
    return json_safe(value)


def _key(key: Hashable) -> str:
    if isinstance(key, tuple):
        return "|".join(str(plain(k)) for k in key)
    return str(plain(key))


# --- preferences --------------------------------------------------------------------------------------------


class PreferenceStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, user_id: str) -> AdvisoryPreferences:
        with self.db.session() as sess:
            row = sess.get(UserAdvisoryPrefsRow, user_id)
            raw = None if row is None else dict(row.prefs)
        if raw is None:
            return AdvisoryPreferences()
        try:
            return AdvisoryPreferences.model_validate(raw)
        except ValueError:  # a document from an older schema: defaults rather than a broken page
            return AdvisoryPreferences()

    @staticmethod
    def validate(raw: Mapping[str, Any]) -> AdvisoryPreferences:
        """A submitted document, checked against the catalogs; raises ``ConfigError``."""
        evidence, strategies = catalogs()
        return parse_preferences(raw, evidence=evidence, strategies=strategies)

    def save(self, user_id: str, prefs: AdvisoryPreferences, now: datetime) -> AdvisoryPreferences:
        checked = self.validate(prefs.model_dump(mode="json"))
        with self.db.session() as sess:
            row = sess.get(UserAdvisoryPrefsRow, user_id)
            doc = checked.model_dump(mode="json")
            if row is None:
                sess.add(UserAdvisoryPrefsRow(user_id=user_id, prefs=doc, updated_at=now))
            else:
                row.prefs, row.updated_at = doc, now
        return checked


def engine_advisory_config(
    db: Database, users: Sequence[tuple[str, frozenset[Family] | None]]
) -> AdvisoryConfig:
    """The engine's compute requirements: the union of its users' needs (TAA-8A4), each user's detectors cut
    to the evidence families their plan allows (``None``: all, TAA-8A2), so an engine never computes a theory
    no user may see. *users*: (user id, allowed families), the engine's owner first."""
    evidence, strategies = catalogs()
    store = PreferenceStore(db)
    prefs = [store.get(user_id) for user_id, _ in users]
    config = advisory_config(prefs, evidence=evidence, strategies=strategies)
    detectors: set[str] = set()
    for p, (_, families) in zip(prefs, users, strict=True):
        wanted = p.theories.enabled_detectors(evidence)
        detectors |= wanted if families is None else wanted & evidence.ids_in_families(families)
    content = config.model_dump(mode="json", exclude={"version"})
    content["detectors"] = sorted(detectors)
    return AdvisoryConfig(version=content_version(content), **content)


def detector_catalog() -> dict[str, Any]:
    evidence, strategies = catalogs()
    detectors = []
    for det_id in evidence.ids:
        det = evidence.get(det_id)
        detectors.append(
            {
                "id": det_id,
                "name": det.name,
                "family": det.family.value,
                "tier": det.tier.value,
                "depends_on": list(det.depends_on),
                "params": evidence.default_params(det_id).model_dump(mode="json"),
            }
        )
    return {"detectors": detectors, "pattern_strategies": pattern_setups(strategies)}


# --- read models --------------------------------------------------------------------------------------------


class AdvisoryReads:
    def __init__(self, db: Database) -> None:
        self.db = db

    def default_server(self, engine_id: str) -> str | None:
        """The trade server of the engine's newest ranking or opportunity (a user rarely has two)."""
        with self.db.session() as sess:
            for model, col in (
                (SuitabilitySnapshotRow, SuitabilitySnapshotRow.computed_at),
                (OpportunityRow, OpportunityRow.created_at),
            ):
                server = sess.scalar(
                    select(model.server).where(model.engine_id == engine_id).order_by(col.desc()).limit(1)
                )
                if server is not None:
                    return str(server)
        return None

    # ranking

    def ranking(self, engine_id: str, *, asset_class: str | None, eligible: bool | None) -> dict[str, Any]:
        m = SuitabilitySnapshotRow
        with self.db.session() as sess:
            latest = sess.scalar(
                select(m.computed_at).where(m.engine_id == engine_id).order_by(m.computed_at.desc()).limit(1)
            )
            if latest is None:
                return {"computed_at": None, "items": []}
            where = [m.engine_id == engine_id, m.computed_at == latest]
            if asset_class:
                where.append(m.asset_class == asset_class)
            if eligible is not None:
                where.append(m.eligible.is_(eligible))
            rows = sess.scalars(select(m).where(*where).order_by(m.rank, m.symbol)).all()
            items = [row_dict(r, skip=("engine_id", "id", "payload")) for r in rows]
        return {"computed_at": json_safe(ensure_utc(latest)), "items": items}

    def personal_ranking(
        self,
        engine_id: str,
        profile: AccountProfileRow | None,
        risk_percent: float,
        now: datetime,
        *,
        asset_class: str | None = None,
    ) -> dict[str, Any]:
        """The ranking for another user's account (TAA-8A4): the market gates stay, the account gates are
        recomputed on the user's MANUAL profile (can the minimum lot be risked within their budget?), and
        the engine owner's sizing is never shown. Eligible for the user first, then the market rank."""
        m = SuitabilitySnapshotRow
        with self.db.session() as sess:
            latest = sess.scalar(
                select(m.computed_at).where(m.engine_id == engine_id).order_by(m.computed_at.desc()).limit(1)
            )
            if latest is None:
                return {"computed_at": None, "personal": True, "items": []}
            where = [m.engine_id == engine_id, m.computed_at == latest]
            if asset_class:
                where.append(m.asset_class == asset_class)
            rows = list(sess.scalars(select(m).where(*where).order_by(m.rank, m.symbol)))
        equity = profile.equity if profile is not None and profile.source == "MANUAL" else None
        manual = equity is not None
        budget = float(equity) * risk_percent / 100 if equity is not None else None
        items = []
        for r in rows:
            metrics = dict((r.payload or {}).get("metrics") or {})
            market_failed = [g for g in r.failed_gates if g not in ACCOUNT_GATES]
            personal: dict[str, Any] = {"currency": None if profile is None else profile.currency}
            if not manual or profile is None or budget is None:
                personal |= {"eligible": None, "reason": "no_manual_profile"}
            else:
                rate = HistoryRates(self.db, engine_id, r.server, profile.currency, now)(
                    str(metrics.get("currency", ""))
                )
                min_lot, min_lot_risk = metrics.get("min_lot"), metrics.get("min_lot_risk")
                if rate is None or not min_lot or min_lot_risk is None:
                    personal |= {"eligible": None, "reason": "no_conversion"}
                else:
                    per_lot = float(min_lot_risk) * rate / float(min_lot)
                    lots = (
                        math.floor(budget / per_lot / float(min_lot) + 1e-9) * float(min_lot)
                        if per_lot > 0
                        else 0.0
                    )
                    affordable = lots >= float(min_lot)
                    personal |= {
                        "eligible": affordable and not market_failed,
                        "affordable": affordable,
                        "risk_budget": round(budget, 2),
                        "lot": round(lots, 8) if affordable else None,
                        "min_lot_risk": round(float(min_lot_risk) * rate, 2),
                    }
            item = row_dict(r, skip=("engine_id", "id", "payload"))
            item["failed_gates"] = market_failed
            item["eligible"] = not market_failed
            item["personal"] = personal
            items.append(item)
        items.sort(key=lambda i: (i["personal"].get("eligible") is not True, i["rank"]))
        return {"computed_at": json_safe(ensure_utc(latest)), "personal": True, "items": items}

    def ranking_symbol(self, engine_id: str, symbol: str) -> dict[str, Any] | None:
        m = SuitabilitySnapshotRow
        with self.db.session() as sess:
            row = sess.scalar(
                select(m)
                .where(m.engine_id == engine_id, m.symbol == symbol)
                .order_by(m.computed_at.desc())
                .limit(1)
            )
            return None if row is None else row_dict(row, skip=("engine_id", "id"))

    def ranking_history(self, engine_id: str, symbol: str, hours: int, now: datetime) -> list[dict[str, Any]]:
        if not 1 <= hours <= MAX_HISTORY_HOURS:
            raise QueryError(f"hours: 1-{MAX_HISTORY_HOURS}")
        m = SuitabilitySnapshotRow
        with self.db.session() as sess:
            rows = sess.scalars(
                select(m)
                .where(m.engine_id == engine_id, m.symbol == symbol, m.hour >= now - timedelta(hours=hours))
                .order_by(m.hour)
            ).all()
            return [
                {
                    "hour": json_safe(ensure_utc(r.hour)),
                    "rank": r.rank,
                    "eligible": r.eligible,
                    "overall": json_safe(r.overall),
                    "now_score": json_safe(r.now_score),
                }
                for r in rows
            ]

    # opportunities

    def opportunities(
        self,
        engine_id: str,
        *,
        status: str | None,
        symbol: str | None,
        strategy: str | None,
        limit: int | None,
        cursor: str | None,
    ) -> Page:
        m = OpportunityRow
        where = [m.engine_id == engine_id]
        for col, value in ((m.status, status), (m.symbol, symbol), (m.strategy, strategy)):
            if value:
                where.append(col == value)

        def brief(row: OpportunityRow) -> dict[str, Any]:
            return row_dict(row, skip=("engine_id", "signal", "features"))

        with self.db.session() as sess:
            return paginate(
                sess, m, where, m.created_at, m.opportunity_id, limit=limit, cursor=cursor, serialize=brief
            )

    def opportunity(
        self, engine_id: str, opportunity_id: str, prefs: AdvisoryPreferences
    ) -> dict[str, Any] | None:
        with self.db.session() as sess:
            row = sess.get(OpportunityRow, (engine_id, opportunity_id))
            if row is None:
                return None
            shadows = sess.scalars(
                select(ShadowTradeRow)
                .where(ShadowTradeRow.engine_id == engine_id, ShadowTradeRow.opportunity_id == opportunity_id)
                .order_by(ShadowTradeRow.variant)
            ).all()
            out = row_dict(row, skip=("engine_id", "features"))
            shadow = [row_dict(s, skip=("engine_id", "features", "cursor")) for s in shadows]
            signal = dict(row.signal or {})
            query = Query(
                strategy=row.strategy,
                symbol=row.symbol,
                asset_class=row.asset_class,
                strength=row.setup_strength,
                rr=row.rr or 0.0,
                features=dict(row.features or {}),
            )
            version = row.calibration_version
            decision = sess.get(DecisionRecordRow, (engine_id, row.decision_id))
            heat = sess.scalar(
                select(DecisionCheckRow.value).where(
                    DecisionCheckRow.engine_id == engine_id,
                    DecisionCheckRow.decision_id == row.decision_id,
                    DecisionCheckRow.name == "max_total_open_risk",
                )
            )
            out["plan"] = plain(decision.plan if decision is not None and decision.plan else [])
            out["heat_after"] = heat if isinstance(heat, int | float) else None
        out["evidence"] = plain(signal.get("evidence", []))
        out["confluence"] = plain(signal.get("confluence"))
        out["shadow"] = shadow
        out["probability"] = self._probability(engine_id, version, query, prefs)
        return out

    def _probability(
        self, engine_id: str, version: str | None, query: Query, prefs: AdvisoryPreferences
    ) -> dict[str, Any]:
        """The win probability and its per-theory contributions for this user's theory selection, from the
        calibration version stamped on the opportunity (None: not calibrated when it was found)."""
        if version is None:
            return {"available": False, "reason": "no_calibration"}
        try:
            loaded = load_version(self.db, version, engine_id)
        except TaaError:
            return {"available": False, "reason": "calibration_missing"}
        evidence, _ = catalogs()
        explanation = loaded.model.explain(query, prefs.theories.enabled_detectors(evidence))
        out = plain(explanation)
        if out.get("contributions"):
            out["contributions"] = sorted(out["contributions"], key=lambda c: -abs(c.get("points") or 0))
        return {"available": True, "calibration_version": version, **out}

    # shadow trades and accuracy

    def shadow_trades(
        self,
        engine_id: str,
        *,
        status: str | None,
        variant: str | None,
        source: str | None,
        symbol: str | None,
        limit: int | None,
        cursor: str | None,
    ) -> Page:
        m = ShadowTradeRow
        where = [m.engine_id == engine_id]
        for col, value in ((m.status, status), (m.variant, variant), (m.source, source), (m.symbol, symbol)):
            if value:
                where.append(col == value)
        with self.db.session() as sess:
            return paginate(
                sess,
                m,
                where,
                m.signal_at,
                m.shadow_id,
                limit=limit,
                cursor=cursor,
                serialize=lambda r: row_dict(r, skip=("engine_id", "features", "cursor")),
            )

    def _records(self, engine_id: str, server: str, variant: str, since: datetime | None) -> list[Any]:
        try:
            v = Variant(variant)
        except ValueError as exc:
            raise QueryError("variant: PLAN or MANAGED") from exc
        return load_records(self.db, server=server, variant=v, since=since, engine_id=engine_id)

    def accuracy(
        self,
        engine_id: str,
        server: str,
        *,
        variant: str,
        since: datetime | None,
        prefs: AdvisoryPreferences,
    ) -> dict[str, Any]:
        records = self._records(engine_id, server, variant, since)
        lists = {w.name: w.symbols for w in prefs.watchlists if w.symbols}
        report = accuracy_report(records, watchlists=lists)
        return {"server": server, "variant": variant, "hypothetical": True, **plain(report)}

    def user_accuracy(
        self, engine_id: str, server: str, user_id: str, *, variant: str, since: datetime | None
    ) -> dict[str, Any]:
        """Accuracy over the opportunities *this user* was alerted to, with P/L = R × the user's risk money at
        alert time (TAA-8A4; None where the user had no sizing)."""
        records = self._records(engine_id, server, variant, since)
        with self.db.session() as sess:
            alerts = {
                a.opportunity_id: a
                for a in sess.scalars(
                    select(OpportunityAlertRow).where(
                        OpportunityAlertRow.user_id == user_id, OpportunityAlertRow.engine_id == engine_id
                    )
                )
            }
        mine = []
        for r in records:
            alert = alerts.get(r.shadow_id.rsplit(":", 1)[0])
            if alert is None:
                continue
            money = None if alert.risk_money is None else r.r_net * alert.risk_money
            mine.append(dataclasses.replace(r, net_pnl=money, alerted=True, followed=False))
        report = accuracy_report(mine)
        currency = next((a.currency for a in alerts.values() if a.currency), None)
        return {
            "server": server,
            "variant": variant,
            "hypothetical": True,
            "scope": "my_alerts",
            "currency": currency,
            **plain(report),
        }

    def explorer(
        self,
        engine_id: str,
        server: str,
        *,
        variant: str,
        source: str | None,
        since: datetime | None,
        money: bool = True,
    ) -> dict[str, Any]:
        """``money`` False (the market feed): R only, the owner's money results are dropped."""
        records = self._source(self._records(engine_id, server, variant, since), source)
        if not money:
            records = [dataclasses.replace(r, net_pnl=None) for r in records]
        return {"server": server, "hypothetical": True, **plain(threshold_explorer(records))}

    def scoreboard(
        self, engine_id: str, server: str, *, variant: str, source: str | None, since: datetime | None
    ) -> dict[str, Any]:
        records = self._source(self._records(engine_id, server, variant, since), source)
        return {"server": server, "hypothetical": True, "items": plain(scoreboard(records))}

    @staticmethod
    def _source(records: list[Any], source: str | None) -> list[Any]:
        if source is None:
            return records
        try:
            wanted = Source(source)
        except ValueError as exc:
            raise QueryError("source: LIVE or REPLAY") from exc
        return [r for r in records if r.source is wanted]

    def calibration(self, engine_id: str, server: str) -> dict[str, Any] | None:
        latest = latest_version(self.db, server, engine_id)
        if latest is None:
            return None
        with self.db.session() as sess:
            row = sess.get(CalibrationTableRow, (engine_id, latest[0]))
            if row is None:
                return None
            return row_dict(row, skip=("engine_id", "cells"))
