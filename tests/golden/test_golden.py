"""Golden harness (PLAN_LEARNING §L0.2; TAA-L002): today's behaviour, recorded in detail.

The learning track builds beside the existing process and may only change it at default-off hook points. These
tests pin what the existing process does on fixed, deterministic scenarios, so any change in decisions, sizes,
fills, exits or shadow outcomes shows up here, even when the change was not meant to touch it:

- **backtest:** every trade of the synthetic uptrend backtest (strategy, decision, sizing and fill code);
- **replay:** every REPLAY shadow trade of the advisory replay (scanner decisions, shadow resolution);
- **paper engine:** every decision and paper position of the PAPER engine on FakeMT5 with a test strategy
  (orchestrator, decision engine, sizing, paper broker).

A deliberate behaviour change regenerates the files with ``TAA_UPDATE_GOLDEN=1`` and the diff of
``tests/golden/*.json`` is reviewed in the same change. Floats are rounded to 6 decimals; identifiers that are
random per run (uuids) are left out.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.backtest.runner import load_history, run_backtest
from app.core.enums import Timeframe
from app.market_data.history_store import ParquetHistoryStore
from app.storage.database import Database
from app.storage.models import DecisionRecordRow, PaperPositionRow, ShadowTradeRow
from app.strategy.registry import StrategySet
from tests.backtest.test_replay import KEYS, replay, split_m5
from tests.backtest.test_runner_cli import CONFIG, SERVER, TFS, full_columns, store_symbol, window
from tests.integration.test_engine_paper import BuyEveryBar, harness
from tests.strategy_data import EURUSD_SPEC

GOLDEN_DIR = Path(__file__).parent
UPDATE = os.environ.get("TAA_UPDATE_GOLDEN") == "1"


def _plain(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in sorted(value.items())}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


@pytest.fixture
def backtest_store(tmp_path: Path) -> ParquetHistoryStore:
    s = ParquetHistoryStore(tmp_path / "history")
    store_symbol(s, EURUSD_SPEC)
    return s


@pytest.fixture
def replay_store(backtest_store: ParquetHistoryStore) -> ParquetHistoryStore:
    m15 = backtest_store.load(SERVER, "EURUSD", Timeframe.M15)
    backtest_store.save(SERVER, "EURUSD", Timeframe.M5, full_columns(split_m5(m15)), EURUSD_SPEC)
    return backtest_store


def check(name: str, rows: Iterable[dict[str, Any]]) -> None:
    got = [_plain(r) for r in rows]
    path = GOLDEN_DIR / f"{name}.json"
    if UPDATE or not path.exists():
        path.write_text(json.dumps(got, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        if not UPDATE:
            pytest.fail(f"golden file {path.name} was missing and has been written; review and commit it")
        return
    want = json.loads(path.read_text(encoding="utf-8"))
    assert got == want, f"behaviour changed against {path.name}; if intended, rerun with TAA_UPDATE_GOLDEN=1"


def test_backtest_trades(backtest_store: ParquetHistoryStore) -> None:
    start, end = window(backtest_store)
    loaded = load_history(backtest_store, SERVER, ["EURUSD"], TFS, account_currency="USD")
    result, _ = run_backtest(CONFIG, loaded, config_hash="golden", start=start, end=end)
    fields = (
        "symbol", "side", "volume", "entry_time", "entry_price", "exit_time", "exit_price", "exit_reason",
        "sl_initial", "tp_initial", "profit", "commission", "swap", "mae", "mfe", "risk_money", "strategy",
        "magic",
    )  # fmt: skip
    check("backtest", ({f: getattr(t, f) for f in fields} for t in result.trades))
    assert result.trades  # the scenario must exercise the trade path


def test_replay_shadow_trades(replay_store: ParquetHistoryStore) -> None:
    db = Database("sqlite://")
    db.create_all()
    replay(replay_store).run(db)
    with db.session() as sess:
        rows = list(sess.scalars(select(ShadowTradeRow).order_by(ShadowTradeRow.shadow_id)))
        out = [{k: getattr(r, k) for k in (*KEYS, "variant", "source")} for r in rows]
    check("replay", out)
    assert out


def test_paper_engine(tmp_path: Path) -> None:
    h = harness(tmp_path)
    h.engine.start()
    strategy = BuyEveryBar()
    h.engine.strategies = StrategySet((strategy,))
    h.engine.magic = {strategy.name: 7_310_000}
    h.engine.positions.strategies_by_magic = {7_310_000: strategy}
    h.engine.run(max_cycles=120)  # one simulated hour: several M15 bars
    with h.db.session() as sess:
        decisions = [
            {
                "created_at": r.created_at,
                "strategy": r.strategy,
                "symbol": r.symbol,
                "action": r.action,
                "profile": r.profile,
                "decision": r.decision,
                "reason_codes": r.reason_codes,
                "warnings": r.warnings,
                "volume": r.volume,
                "risk_money": r.risk_money,
                "entry_price": r.entry_price,
                "stop_loss": r.stop_loss,
                "take_profit": r.take_profit,
                "plan": r.plan,
                "risk_percent": r.risk_percent,
            }
            for r in sess.scalars(
                select(DecisionRecordRow).order_by(DecisionRecordRow.created_at, DecisionRecordRow.symbol)
            )
        ]
        positions = [
            {
                "symbol": p.symbol,
                "side": p.side,
                "volume": p.volume,
                "entry_price": p.entry_price,
                "sl": p.sl,
                "tp": p.tp,
                "entry_time": p.entry_time,
                "stop_kind": p.stop_kind,
                "status": p.status,
                "exit_time": p.exit_time,
                "exit_price": p.exit_price,
                "exit_reason": p.exit_reason,
                "profit": p.profit,
                "r_multiple": p.r_multiple,
                "mae": p.mae,
                "mfe": p.mfe,
                "bars_held": p.bars_held,
            }
            for p in sess.scalars(select(PaperPositionRow).order_by(PaperPositionRow.ticket))
        ]
    check("paper_engine", [{"decisions": decisions, "positions": positions}])
    assert decisions and positions
