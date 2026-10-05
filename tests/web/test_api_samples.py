"""API response samples shared with the PWA (TAA-906).

The PWA validates every response with a zod schema, and its component tests fake the API. A fake that does
not match the real response hides bugs (TAA-905 read ``/symbols`` as a list; it is ``{"items": [...]}``). This
test records real responses of the routes the pages read, built from rows written by the engine's own
serializers, into ``frontend/src/test/fixtures/api-samples.json``; ``frontend/src/test/apiSamples.test.ts``
parses each sample with the page's schema. A change on either side fails one of the two tests.

Regenerate after an intended API change: ``TAA_UPDATE_API_SAMPLES=1 pytest tests/web/test_api_samples.py``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from app.advisory.calibration import build, save
from app.advisory.personalize import UserContext, replacement
from app.advisory.requirements import ComputeRequirements
from app.advisory.shadow import ShadowExit, ShadowResult, Variant, new_state
from app.advisory.shadow_tracker import EntryQuote, SignalFacts, apply_close, new_row
from app.config import AppConfig, Settings, load_app_config, load_settings
from app.core.enums import ExitReason, Side
from app.evidence.catalog import default_registry as evidence_registry
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    BacktestRunRow,
    CalibrationTableRow,
    ConfigSnapshot,
    DecisionCheckRow,
    DecisionRecordRow,
    EngineCommandRow,
    EngineHeartbeatRow,
    EvidenceModelVersionRow,
    ManualTradeLinkRow,
    NotificationPrefsRow,
    NotificationRow,
    OpportunityRow,
    PushSubscriptionRow,
    ShadowTradeRow,
    SuitabilitySnapshotRow,
    SymbolCatalogRow,
    UserRow,
)
from tests.backtest.test_cloud_backtests import Rig as BacktestRig
from tests.backtest.test_cloud_backtests import upload
from tests.integration.test_ranking_service import CONFIG as RANKING_CONFIG
from tests.integration.test_ranking_service import service as ranking_service
from tests.integration.test_scanner import REQ, scanner
from tests.integration.test_scanner import config as scanner_config
from tests.strategy_data import EURUSD_SPEC
from tests.sync_data import T
from tests.unit.test_calibration import CFG, INFORMATIVE, outcomes
from tests.unit.test_personalize import opportunity, prefs
from tests.unit.test_strategy_models import make_context, make_signal
from tests.web.test_data_api import rig  # noqa: F401  (fixture)

SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "test" / "fixtures" / "api-samples.json"

RUN_A = "0191a0a0-0000-7000-8000-0000000000b1"  # finished, standard preset
RUN_B = "0191a0a0-0000-7000-8000-0000000000b2"  # finished, high_costs (a copy of A's result)
RUN_F = "0191a0a0-0000-7000-8000-0000000000b3"  # failed
# the scanner's opportunity ids are the signals' idempotency keys (deterministic on the FakeMT5 bar)
OPP_EUR = "ebf613a7581b7648eaca8328cdccb599d0751b14ec0d0d451901e2799917e5de"

ENGINE_ROUTES = [
    "status",
    "quotes",
    "symbols",
    "symbols/EURUSD",
    "candles?symbol=EURUSD&limit=5&overlays=ema:5,rsi:5&zones=true",
    "positions?status=OPEN",
    "decisions?limit=2",
    "decisions/d1",
    "breakers?limit=1",
    "trades?limit=2",
    "trades/1",
    "intents?kind=paper",
    "intents?kind=broker",
    "decisions?limit=50&profile=EXECUTION",
    "strategies",
    "strategies?days=7",
    "backtests",
    f"backtests/{RUN_A}",
    f"backtests/{RUN_A}/trades?limit=3",
    f"backtests/compare?ids={RUN_A},{RUN_B}",
    "backtests/history",
    "config",
    "kill-switch?limit=20",
    "commands?limit=20",
    "breakers?limit=20",
    "audit/verify",
    "ranking",
    "ranking/XAUUSD",
    "opportunities?limit=50",
    f"opportunities/{OPP_EUR}",
    "theory-scoreboard",
    "accuracy",
    "accuracy?mine=true",
    "calibration",
    "shadow-trades?limit=20",
    "manual-trades?status=OPEN&limit=100",
    "manual-trades?status=CLOSED&limit=100",
    "manual-trades/2078278005/candidates",
    "analytics?scope=PAPER&days=366",
    "analytics?scope=SHADOW&days=366",
    f"analytics?scope=BACKTEST&days=366&run={RUN_A}",
    f"recommendations?scope=BACKTEST&days=366&run={RUN_A}",
    "ai-assessments?days=366",
]
USER_ROUTES = [
    "me/feed",
    "engines",
    "notifications?limit=5",
    "notifications?limit=20",
    "notifications/preferences",
    "push/subscriptions",
    "auth/sessions",
    "backtests/presets",
    "advisory/preferences",
    "advisory/detectors",
    "me/entitlements",
    "me/account-profile",
    "admin/users",
    "admin/plans",
    "admin/users/USER/entitlements",
]


# The samples' sizes and money must not move when the owner edits the cage in config.yaml (PLAN §A33).
PINNED_RISK = {
    "max_risk_per_trade_percent": 0.5,
    "max_total_open_risk_percent": 1.5,
    "max_daily_loss_percent": 2.0,
    "max_weekly_loss_percent": 4.0,
}


def pin(cfg: AppConfig) -> AppConfig:
    return cfg.model_copy(update={"risk": cfg.risk.model_copy(update=PINNED_RISK)})


def pinned_config() -> Path:
    """The repository's config.yaml with :data:`PINNED_RISK`, in a temporary file."""
    raw = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    raw["risk"] |= PINNED_RISK
    path = Path(tempfile.mkdtemp(prefix="taa-samples-")) / "config.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8", newline="\n")
    return path


def engine_settings() -> Settings:
    """The repository's config.yaml (risk pinned) with a typical engine environment (PAPER, flatten allowed,
    control TOTP)."""
    return load_settings(
        env_file=None,
        config_file=pinned_config(),
        environ={
            "TRADING_MODE": "PAPER",
            "MT5_LOGIN": "12345678",
            "MT5_PASSWORD": "x",
            "MT5_SERVER": "FBS-Demo",
            "MT5_TERMINAL_PATH": "C:/MT5/taa-bot/terminal64.exe",
            "CONTROL_TOTP_SECRET": "JBSWY3DPEHPK3PXP",
            "KILL_SWITCH_FLATTEN_ALLOWED": "true",
        },
    )


def backtest_runs(engine_id: str, owner_id: str) -> list[BacktestRunRow]:
    """A real cloud run on the synthetic history (in a throwaway database), plus a copy and a failed run."""
    scratch = Database("sqlite://")
    scratch.create_all()
    runner = BacktestRig(scratch)
    m15 = upload(scratch, engine=engine_id)
    run = runner.service.create(owner_id, engine_id, runner.request(m15), created_by="alice")
    runner.run()
    done = runner.row(run["run_id"])
    assert done.status == "DONE", done.error
    columns = {c.key: getattr(done, c.key) for c in BacktestRunRow.__table__.columns}
    # signal ids are random per run: fixed ones keep the samples file stable
    columns["trades"] = [t | {"signal_id": f"sig-{i}"} for i, t in enumerate(done.trades)]
    later = timedelta(minutes=5)
    return [
        BacktestRunRow(**columns | {"run_id": RUN_A, "job_id": None}),
        BacktestRunRow(
            **columns
            | {
                "run_id": RUN_B,
                "job_id": None,
                "preset": "high_costs",
                "request": columns["request"] | {"preset": "high_costs"},
                "created_at": done.created_at + later,
            }
        ),
        BacktestRunRow(
            **columns
            | {
                "run_id": RUN_F,
                "job_id": None,
                "status": "FAILED",
                "progress": 0.0,
                "error": "no M15 history for GBPUSD on FBS-Demo",
                "summary": {},
                "equity": [],
                "trades": [],
                "trades_total": 0,
                "created_at": done.created_at + 2 * later,
            }
        ),
    ]


def ranking_rows(engine_id: str) -> list[SuitabilitySnapshotRow]:
    """A real ranking run on the multi-asset FakeMT5 (in a throwaway database) for a small account, so some
    symbols fail the minimum-lot gate ("needs equity ≥ $Z")."""
    scratch = Database("sqlite://")
    scratch.create_all()
    svc, _, fake = ranking_service(scratch, pin(RANKING_CONFIG))
    fake.account.balance = 1_000.0
    assert svc.tick() is not None
    rows = svc.latest()
    columns = [c.key for c in SuitabilitySnapshotRow.__table__.columns if c.key not in ("id", "engine_id")]
    return [SuitabilitySnapshotRow(engine_id=engine_id, **{c: getattr(r, c) for c in columns}) for r in rows]


def copy_rows(rows: list[Any], engine_id: str) -> list[Any]:
    """Detached copies of *rows* (from a throwaway database) for *engine_id*, without autoincrement ids."""
    out = []
    for r in rows:
        model = type(r)
        columns = [
            c.key for c in model.__table__.columns if c.key != "engine_id" and c.autoincrement is not True
        ]
        out.append(model(engine_id=engine_id, **{c: getattr(r, c) for c in columns}))
    return out


def pin_ids(rows: list[Any], ids: list[str]) -> None:
    """Replace random ids (uuid7 decision and signal ids) everywhere in *rows* by fixed ones."""
    fixed = {old: f"0191a0a0-0000-7000-8000-0000000001{i:02d}" for i, old in enumerate(ids)}

    def swap(value: Any) -> Any:
        text = json.dumps(value)
        for old, new in fixed.items():
            text = text.replace(old, new)
        return json.loads(text)

    for row in rows:
        for column in type(row).__table__.columns:
            value = getattr(row, column.key)
            if isinstance(value, str | dict | list):
                setattr(row, column.key, swap(value))


def opportunity_rows(engine_id: str) -> list[Any]:
    """Two opportunities from the engine's scanner on FakeMT5 with every detector (the EURUSD one alerted and
    ACTIVE), with their ADVISORY decision records."""
    scratch = Database("sqlite://")
    scratch.create_all()
    req = ComputeRequirements(("EURUSD", "XAUUSD"), frozenset(evidence_registry().ids), REQ.strategies)
    svc, _, _ = scanner(scratch, req=req, cfg=pin(scanner_config(budget=60.0)))
    assert len(svc.tick().created) == 2
    with scratch.session() as sess:
        opps = list(sess.scalars(select(OpportunityRow).order_by(OpportunityRow.symbol)))
        decisions = list(sess.scalars(select(DecisionRecordRow)))
        checks = list(sess.scalars(select(DecisionCheckRow)))
        rows = copy_rows([*opps, *decisions, *checks], engine_id)
    pin_ids(rows, [o.decision_id for o in opps] + [str(o.signal["signal_id"]) for o in opps])
    eur = rows[0]
    assert isinstance(eur, OpportunityRow) and eur.opportunity_id == OPP_EUR
    eur.status, eur.alerted_at = "ACTIVE", eur.created_at  # as the personalizer leaves an alerted one
    for opp in rows[:2]:  # the window the lifecycle tracker sets (bar close + 2 entry bars)
        assert isinstance(opp, OpportunityRow)
        opp.valid_until, opp.valid_reason = opp.bar_close_at + timedelta(minutes=30), "SIGNAL_LIFETIME"
    eur.features = dict(eur.features) | {INFORMATIVE: 0.8}  # a feature the sample calibration knows
    return rows


# Shadow trades of the accuracy samples: (id, source, symbol, side, session, strength, exit reason, R gross,
# R net, net money or None for "not tradable", hours to exit, alerted, followed)
SHADOWS = [
    ("s1", "LIVE", "EURUSD", "BUY", "LONDON", 82.0, "TAKE_PROFIT", 2.0, 1.9, 19.0, 1, True, False),
    ("s2", "LIVE", "EURUSD", "SELL", "NEW_YORK", 64.0, "STOP_LOSS", -1.0, -1.1, -11.0, 5, True, False),
    ("s3", "LIVE", "XAUUSD", "BUY", "LONDON", 91.0, "TAKE_PROFIT", 2.5, 2.4, 24.0, 9, True, True),
    ("s4", "LIVE", "GBPUSD", "SELL", "ASIA", 58.0, "TIME_STOP", -0.3, -0.4, None, 30, False, False),
    ("s5", "LIVE", "XAUUSD", "SELL", "NEW_YORK", 77.0, "STOP_LOSS", -1.0, -1.05, -10.5, 40, False, False),
    ("r1", "REPLAY", "EURUSD", "BUY", "LONDON", 71.0, "TAKE_PROFIT", 2.0, 1.92, 19.2, 2, False, False),
    ("r2", "REPLAY", "EURUSD", "SELL", "ASIA", 66.0, "STOP_LOSS", -1.0, -1.08, -10.8, 6, False, False),
    ("r3", "REPLAY", "GBPUSD", "BUY", "LONDON_NY_OVERLAP", 88.0, "TAKE_PROFIT", 2.0, 1.9, 19.0, 12, False, False),
]  # fmt: skip


def shadow_samples(db: Database) -> None:
    """Closed PLAN trades of :data:`SHADOWS`, a MANAGED copy of the first and one still open."""
    rows = []
    for i, (
        oid,
        source,
        symbol,
        side,
        session,
        strength,
        reason,
        r,
        r_net,
        money,
        hours,
        alerted,
        followed,
    ) in enumerate(SHADOWS):
        buy = side == "BUY"
        facts = SignalFacts(
            opportunity_id=oid, source=source, server="FBS-Demo", strategy="example_trend_pullback",
            symbol=symbol, asset_class="METAL" if symbol == "XAUUSD" else "FOREX_MAJOR", timeframe="M15",
            side=side, session=session, setup_strength=strength, rr=2.0,
            features={INFORMATIVE: 0.9} if r > 0 else {}, atr=0.001, signal_at=T - timedelta(days=5) + timedelta(hours=6 * i),
            lot=None if money is None else 0.1, equity=1_000.0, currency="USD", alerted=alerted, followed=followed,
        )  # fmt: skip
        entry, risk = 1.1, 0.005 if buy else -0.005
        for variant in (Variant.PLAN, Variant.MANAGED) if oid == "s1" else (Variant.PLAN,):
            state = new_state(
                side=Side(side), entry=entry, entry_at=facts.signal_at, sl=entry - risk, tp=entry + 2 * risk,
                time_stop=timedelta(hours=72),
            )  # fmt: skip
            row = new_row(
                facts, variant, state, EntryQuote(entry - 0.0001, entry, 1.0, 1.0), (), facts.signal_at
            )
            exit_ = ShadowExit(ExitReason[reason], entry + r * risk, facts.signal_at + timedelta(hours=hours))
            gross = None if money is None else 10.0 * r
            result = ShadowResult(
                r > 0, r, r_net, -0.4, max(r, 0.3), 0, gross, None if money is None else -0.7, 0.0, money,
                None if money is None else 10.0, frozenset(),
            )  # fmt: skip
            apply_close(row, exit_, result)
            rows.append(row)
    open_facts = dataclasses.replace(
        facts, opportunity_id="s6", source="LIVE", signal_at=T - timedelta(hours=2)
    )
    state = new_state(side=Side.SELL, entry=1.1, entry_at=open_facts.signal_at, sl=1.105, tp=1.09,
                      time_stop=timedelta(hours=72))  # fmt: skip
    rows.append(new_row(open_facts, Variant.PLAN, state, EntryQuote(1.0999, 1.1, 1.0, 1.0), (), T))
    with db.session() as sess:
        sess.add_all(rows)


def calibrate(db: Database, engine_id: str) -> None:
    """A calibration version (synthetic outcomes where the Fibonacci theory is informative) stamped on the
    opportunities, and the shadow trades of :data:`SHADOWS` for the accuracy pages."""
    version = save(db, build(outcomes(1500, informative=True, seed=4), CFG, server="FBS-Demo", built_at=T))
    shadow_samples(db)
    with db.session() as sess:
        for model in (CalibrationTableRow, EvidenceModelVersionRow, ShadowTradeRow):
            sess.execute(update(model).where(model.engine_id == "local").values(engine_id=engine_id))
        sess.execute(
            update(OpportunityRow)
            .where(OpportunityRow.engine_id == engine_id)
            .values(calibration_version=version)
        )


def realistic_rows(db: Database, engine_id: str) -> None:
    """Replace the sample placeholders with documents the engine's serializers produce."""
    with db.session() as sess:
        open_link = sess.get(ManualTradeLinkRow, (engine_id, 2078278005))
        assert open_link is not None
        open_link.sl_initial = 1.0952
        closed = ManualTradeLinkRow(  # the owner's earlier manual trade on the same signal, closed at +1.25 R
            **{c.key: getattr(open_link, c.key) for c in ManualTradeLinkRow.__table__.columns}
        )
        closed.position_id = closed.ticket = 2078278001
        closed.status, closed.closed_at, closed.close_price = "CLOSED", T + timedelta(hours=2), 1.1065
        closed.net_profit, closed.r_multiple = 62.5, 1.25
        sess.add(closed)
        catalog = sess.scalars(
            select(SymbolCatalogRow).where(
                SymbolCatalogRow.engine_id == engine_id, SymbolCatalogRow.symbol == "EURUSD"
            )
        ).one()
        catalog.spec = json.loads(json.dumps(asdict(EURUSD_SPEC)))
        decision = sess.get(DecisionRecordRow, (engine_id, "d1"))
        assert decision is not None
        decision.signal = make_signal().to_dict()
        decision.market = make_context().to_dict()
        snapshot = sess.get(ConfigSnapshot, (engine_id, "c" * 32))
        assert snapshot is not None
        summary = engine_settings().summary()  # what the engine snapshots (secrets masked by the engine)
        # setup_breakout runs but the owner disabled it from the PWA (heartbeat below); setup_elliott_wave is
        # off in the file, so the samples cover both states while config.yaml enables every strategy
        for item in summary["config"]["strategies"]["items"]:
            item["enabled"] = item["name"] != "setup_elliott_wave"
        snapshot.payload = summary | {"config_hash": "c" * 32}
        snapshot.created_at = T  # stamped with the wall clock by the sample rows
        quote = {
            "symbol": "EURUSD",
            "bid": 1.1,
            "ask": 1.10008,
            "spread_points": 8.0,
            "max_spread_points": 30.0,
            "time": T.isoformat(),
        }
        account = {
            "as_of": T.isoformat(),
            "backend": "paper",
            "currency": "USD",
            "balance": 10_000.0,
            "equity": 9_990.0,
            "margin": 50.0,
            "margin_free": 9_940.0,
            "day_pnl": -10.0,
            "day_pnl_percent": -0.1,
            "week_pnl": None,
            "week_pnl_percent": None,
            "drawdown_percent": 0.1,
            "open_risk": 20.0,
            "heat_percent": 0.2,
            "unknown_risk_positions": 0,
            "consecutive_losses": 1,
            "limits": {
                "daily_loss_percent": 2.0,
                "weekly_loss_percent": 4.0,
                "drawdown_percent": 10.0,
                "heat_percent": 1.5,
                "consecutive_losses": 4,
            },
            "risk_limits": {  # the owner's profile (style 50) inside a 0.5 % cage (TAA-710)
                "source": "cloud",
                "version": "367a33e42c836f3d",
                "age_seconds": 120,
                "cage": {
                    "risk_per_trade_percent": 0.5,
                    "total_open_risk_percent": 1.5,
                    "max_open_positions": 3,
                    "max_daily_loss_percent": 2.0,
                    "min_risk_reward": 1.5,
                },
                "profile": {
                    "risk_per_trade_percent": 0.75,
                    "total_open_risk_percent": 2.0,
                    "max_open_positions": 3,
                    "max_daily_loss_percent": 2.0,
                    "min_risk_reward": 1.5,
                },
                "effective": {
                    "risk_per_trade_percent": 0.5,
                    "total_open_risk_percent": 1.5,
                    "max_open_positions": 3,
                    "max_daily_loss_percent": 2.0,
                    "min_risk_reward": 1.5,
                },
            },
        }
        brief = {
            "at": T.isoformat(),
            "run_id": "r1",
            "mode": "PAPER",
            "state": "running",
            "connected": True,
            "clock_verified": True,
            "kill_switch": False,
            "open_positions": 1,
            "cycles": 10,
            "market_open": True,
            "market_change_at": (T + timedelta(hours=8)).isoformat(),
            "outbox_pending": 0,
            "account": account,
            "disabled_strategies": ["setup_breakout"],
        }
        # ticket 1's lifecycle as app.engine.trade_audit appends it (entered T+15 min, closed 30 min later)
        entry = T + timedelta(minutes=15)
        lifecycle = [
            (entry, "POSITION_OPENED", {"ticket": 1, "paper": True, "side": "BUY", "price": 1.1}),
            (
                entry + timedelta(minutes=10),
                "STOP_MOVED",
                {"ticket": 1, "paper": True, "old": 1.095, "new": 1.1, "kind": "BE", "note": "break-even"},
            ),
            (entry + timedelta(minutes=30), "POSITION_CLOSED", {"ticket": 1, "paper": True, "reason": "TP"}),
        ]
        for seq, (at, kind, payload) in enumerate(lifecycle, start=1):
            sess.add(
                AuditEvent(
                    engine_id=engine_id,
                    event_id=f"0191a0a0-0000-7000-8000-0000000002{seq:02d}",
                    chain="engine:samples",
                    seq=seq,
                    ts_utc=at,
                    actor="engine",
                    event_type=kind,
                    payload={**payload, "symbol": "EURUSD", "event_id": f"e{seq}"},
                    prev_hash="0" * 64,
                    hash=f"{seq:064x}",
                )
            )
        sess.add(
            EngineCommandRow(
                command_id="0191a0a0-0000-7000-8000-0000000000c1",
                engine_id=engine_id,
                type="STRATEGY_DISABLE",
                params={"strategy": "setup_breakout", "reason": "too many losses"},
                created_by="alice",
                created_at=T,
                expires_at=T + timedelta(minutes=2),
                status="EXECUTED",
                delivered_at=T + timedelta(seconds=1),
                completed_at=T + timedelta(seconds=2),
                result={
                    "outcome": "EXECUTED",
                    "reason": None,
                    "detail": "strategy setup_breakout disabled (re-enable locally: app.cli strategy enable)",
                    "at": (T + timedelta(seconds=2)).isoformat(),
                },
            )
        )
        sess.execute(delete(SuitabilitySnapshotRow).where(SuitabilitySnapshotRow.engine_id == engine_id))
        sess.add_all(ranking_rows(engine_id))
        sess.execute(delete(OpportunityRow).where(OpportunityRow.engine_id == engine_id))
        sess.add_all(opportunity_rows(engine_id))
        alice = sess.scalars(select(UserRow).where(UserRow.username == "alice")).one()
        sess.add_all(backtest_runs(engine_id, alice.id))
        # one notification of each kind, with the payloads their producers write (app/worker/*)
        expired = replacement(
            opportunity(),
            UserContext(prefs(), active_alerts=3),
            status="EXPIRED",
            reason="SESSION_END:LONDON",
        )
        notes = [
            (
                "ENGINE_OFFLINE",
                "CRITICAL",
                {"label": "alice pc", "reason": "SILENT", "last_seen_at": T.isoformat()},
            ),
            (
                "ENGINE_BACK",
                "INFO",
                {"label": "alice pc", "offline_since": T.isoformat(), "downtime_seconds": 300},
            ),
            ("BACKTEST_FINISHED", "INFO", {"run_id": RUN_A, "status": "DONE", "preset": "standard"}),
            (
                "OPPORTUNITY_UPDATE",
                "INFO",
                {
                    "push": expired,
                    "opportunity_id": "o1",
                    "status": "EXPIRED",
                    "reason": "SESSION_END:LONDON",
                },
            ),
            ("TEST", "INFO", {}),
        ]
        for i, (kind, severity, payload) in enumerate(notes):
            sess.add(
                NotificationRow(
                    notification_id=f"0191a0a0-0000-7000-8000-0000000000a{i}",
                    user_id=alice.id,
                    engine_id=None if kind == "TEST" else engine_id,
                    type=kind,
                    severity=severity,
                    payload=payload,
                    created_at=T + timedelta(minutes=i),
                    read_at=T + timedelta(minutes=10) if kind == "ENGINE_BACK" else None,
                    push_status="SENT",
                )
            )
        sess.add(
            PushSubscriptionRow(
                subscription_id="0191a0a0-0000-7000-8000-0000000000d1",
                user_id=alice.id,
                endpoint="https://fcm.googleapis.com/fcm/send/sample",
                p256dh="B" + "A" * 86,
                auth="A" * 22,
                label="Edge · Windows",
                created_at=T,
                last_success_at=T + timedelta(minutes=4),
            )
        )
        sess.add(NotificationPrefsRow(user_id=alice.id, disabled_types=["BACKTEST_FINISHED"], updated_at=T))
        sess.add(
            EngineHeartbeatRow(
                engine_id=engine_id,
                received_at=T + timedelta(seconds=1),
                sent_at=T,
                run_id="r1",
                mode="PAPER",
                state="running",
                connected=True,
                market_open=True,
                payload={**brief, "quotes": [quote]},
            )
        )


# Values that differ between runs (the audit hash covers the random engine id; the sample run row is stamped
# with the wall clock), replaced by fixed values of the same shape.
VOLATILE = {
    "verified_hash": "0" * 64,
    "started_at": T.isoformat(),
    "session_id": "0191a0a0-0000-7000-8000-0000000000e1",  # a login's random id
}


def normalize(value: Any, engine_id: str, users: dict[str, str] | None = None) -> Any:
    """Random engine and user ids become ``ENGINE`` and *users*' placeholders (id → name) and volatile values
    fixed ones, so the file is stable."""

    def fix(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: VOLATILE[k] if k in VOLATILE else fix(v) for k, v in node.items()}
        if isinstance(node, list):
            return [fix(v) for v in node]
        return node

    text = json.dumps(value).replace(engine_id, "ENGINE")
    for user_id, name in (users or {}).items():
        text = text.replace(user_id, name)
    return fix(json.loads(text))


def test_api_samples_match_the_shared_file(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, mine, _ = rig
    pinned = load_app_config(pinned_config())  # the cloud reads config.yaml too: same pinned risk
    for module in ("app.web.routers.advisory", "app.worker.opportunities", "app.worker.backtests"):
        monkeypatch.setattr(f"{module}.load_app_config", lambda *_a, **_k: pinned)
    realistic_rows(db, mine)
    calibrate(db, mine)
    samples: dict[str, Any] = {}
    for route in ENGINE_ROUTES:
        resp = client.get(f"/api/v1/engines/{mine}/{route}")
        assert resp.status_code == 200, (route, resp.text)
        samples[f"engines/ENGINE/{route}"] = normalize(resp.json(), mine)
    user_id = client.get("/api/v1/auth/session").json()["user"]["id"]
    listed = client.get("/api/v1/admin/users").json()["items"]
    users = {u["id"]: "USER" if u["id"] == user_id else f"USER_{u['username'].upper()}" for u in listed}
    for route in USER_ROUTES:
        resp = client.get(f"/api/v1/{route.replace('USER', user_id)}")
        assert resp.status_code == 200, (route, resp.text)
        samples[route] = normalize(resp.json(), mine, users)
    text = json.dumps(samples, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("TAA_UPDATE_API_SAMPLES") == "1":
        SAMPLES.parent.mkdir(parents=True, exist_ok=True)
        SAMPLES.write_text(text, encoding="utf-8", newline="\n")
    assert SAMPLES.exists(), "run with TAA_UPDATE_API_SAMPLES=1 to create the samples file"
    assert SAMPLES.read_text(encoding="utf-8") == text, (
        "API responses changed: check the PWA schemas, then regenerate with TAA_UPDATE_API_SAMPLES=1"
    )
