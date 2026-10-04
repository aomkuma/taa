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

from app.storage.database import Database
from app.storage.models import (
    AuditEvent,
    DecisionRecordRow,
    EngineHeartbeatRow,
    NotificationRow,
    SymbolCatalogRow,
    UserRow,
)
from tests.strategy_data import EURUSD_SPEC
from tests.sync_data import T
from tests.unit.test_strategy_models import make_context, make_signal
from tests.web.test_data_api import rig  # noqa: F401  (fixture)

SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "test" / "fixtures" / "api-samples.json"

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
]
USER_ROUTES = ["me/feed", "engines", "notifications?limit=5"]


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
        alice = sess.scalars(select(UserRow).where(UserRow.username == "alice")).one()
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
