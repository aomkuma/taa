"""API response samples shared with the PWA (TAA-906).

The PWA validates every response with a zod schema, and its component tests fake the API. A fake that does
not match the real response hides bugs (TAA-905 read ``/symbols`` as a list; it is ``{"items": [...]}``). This
test records real responses of the routes the pages read, built from rows written by the engine's own
serializers, into ``frontend/src/test/fixtures/api-samples.json``; ``frontend/src/test/apiSamples.test.ts``
parses each sample with the page's schema. A change on either side fails one of the two tests.

Regenerate after an intended API change: ``TAA_UPDATE_API_SAMPLES=1 pytest tests/web/test_api_samples.py``.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import load_app_config
from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    BacktestRunRow,
    ConfigSnapshot,
    DecisionRecordRow,
    EngineCommandRow,
    EngineHeartbeatRow,
    NotificationRow,
    SymbolCatalogRow,
    UserRow,
)
from tests.backtest.test_cloud_backtests import Rig as BacktestRig
from tests.backtest.test_cloud_backtests import upload
from tests.strategy_data import EURUSD_SPEC
from tests.sync_data import T
from tests.unit.test_strategy_models import make_context, make_signal
from tests.web.test_data_api import rig  # noqa: F401  (fixture)

SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "test" / "fixtures" / "api-samples.json"

RUN_A = "0191a0a0-0000-7000-8000-0000000000b1"  # finished, standard preset
RUN_B = "0191a0a0-0000-7000-8000-0000000000b2"  # finished, high_costs (a copy of A's result)
RUN_F = "0191a0a0-0000-7000-8000-0000000000b3"  # failed

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
]
USER_ROUTES = ["me/feed", "engines", "notifications?limit=5", "backtests/presets"]


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


def realistic_rows(db: Database, engine_id: str) -> None:
    """Replace the sample placeholders with documents the engine's serializers produce."""
    with db.session() as sess:
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
        config = load_app_config("config.yaml").model_dump(mode="json")
        for item in config["strategies"]["items"]:  # one strategy the owner disabled from the PWA
            item["enabled"] = item["enabled"] or item["name"] == "setup_breakout"
        snapshot.payload = {"env": {"MT5_PASSWORD": "***set***"}, "config": config, "config_hash": "c" * 32}
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
        alice = sess.scalars(select(UserRow).where(UserRow.username == "alice")).one()
        sess.add_all(backtest_runs(engine_id, alice.id))
        sess.add(
            NotificationRow(
                notification_id="0191a0a0-0000-7000-8000-0000000000aa",
                user_id=alice.id,
                engine_id=engine_id,
                type="ENGINE_OFFLINE",
                severity="CRITICAL",
                payload={"reason": "SILENT"},
                created_at=T,
            )
        )
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
VOLATILE = {"verified_hash": "0" * 64, "started_at": T.isoformat()}


def normalize(value: Any, engine_id: str) -> Any:
    """Random engine ids become ``ENGINE`` and volatile values fixed ones, so the file is stable."""

    def fix(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: VOLATILE[k] if k in VOLATILE else fix(v) for k, v in node.items()}
        if isinstance(node, list):
            return [fix(v) for v in node]
        return node

    return fix(json.loads(json.dumps(value).replace(engine_id, "ENGINE")))


def test_api_samples_match_the_shared_file(
    rig: tuple[TestClient, str, str],  # noqa: F811
    db: Database,
) -> None:
    client, mine, _ = rig
    realistic_rows(db, mine)
    samples: dict[str, Any] = {}
    for route in ENGINE_ROUTES:
        resp = client.get(f"/api/v1/engines/{mine}/{route}")
        assert resp.status_code == 200, (route, resp.text)
        samples[f"engines/ENGINE/{route}"] = normalize(resp.json(), mine)
    for route in USER_ROUTES:
        resp = client.get(f"/api/v1/{route}")
        assert resp.status_code == 200, (route, resp.text)
        samples[route] = normalize(resp.json(), mine)
    text = json.dumps(samples, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("TAA_UPDATE_API_SAMPLES") == "1":
        SAMPLES.parent.mkdir(parents=True, exist_ok=True)
        SAMPLES.write_text(text, encoding="utf-8", newline="\n")
    assert SAMPLES.exists(), "run with TAA_UPDATE_API_SAMPLES=1 to create the samples file"
    assert SAMPLES.read_text(encoding="utf-8") == text, (
        "API responses changed: check the PWA schemas, then regenerate with TAA_UPDATE_API_SAMPLES=1"
    )
