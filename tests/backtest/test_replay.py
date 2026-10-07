"""Historical replay of the scanner into REPLAY shadow trades (TAA-6C2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select

from app.advisory.replay import HistoricalReplay, load_resolution
from app.advisory.scanner import strategy_set
from app.backtest.runner import load_history
from app.cli.__main__ import main
from app.config import AppConfig
from app.core.enums import Timeframe
from app.core.errors import DataQualityError
from app.market_data.history_store import ParquetHistoryStore
from app.storage.database import Database
from app.storage.models import ShadowTradeRow
from app.strategy.catalog import default_registry
from tests.backtest.test_runner_cli import CONFIG, SERVER, TFS, full_columns, store_symbol, window
from tests.strategy_data import EURUSD_SPEC

KEYS = (
    "shadow_id", "status", "entry_at", "entry_price", "initial_sl", "tp", "lot", "exit_at", "exit_price",
    "exit_reason", "r_multiple", "r_net", "mae", "mfe", "gross_pnl", "swap_days", "flags", "features",
)  # fmt: skip


def split_m5(m15: pd.DataFrame) -> pd.DataFrame:
    """Three M5 bars per M15 bar along open → first extreme → second extreme → close (OHLC-consistent)."""
    rows = []
    for r in m15.itertuples(index=False):
        up = r.close >= r.open
        path = [r.open, r.low if up else r.high, r.high if up else r.low, r.close]
        for k in range(3):
            a, b = path[k], path[k + 1]
            start = r.open_time + pd.Timedelta(minutes=5 * k)
            rows.append(
                {
                    "open_time": start,
                    "close_time": start + pd.Timedelta(minutes=5),
                    "open": a,
                    "high": max(a, b),
                    "low": min(a, b),
                    "close": b,
                    "tick_volume": max(1, int(r.tick_volume) // 3),
                    "spread": int(r.spread),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def store(tmp_path: Path) -> ParquetHistoryStore:
    s = ParquetHistoryStore(tmp_path / "history")
    store_symbol(s, EURUSD_SPEC)
    m15 = s.load(SERVER, "EURUSD", Timeframe.M15)
    s.save(SERVER, "EURUSD", Timeframe.M5, full_columns(split_m5(m15)), EURUSD_SPEC)
    return s


def replay(store: ParquetHistoryStore, **kw: object) -> HistoricalReplay:
    start, end = window(store)
    loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
    res = {"EURUSD": load_resolution(store, SERVER, "EURUSD")}
    strategies = strategy_set(CONFIG, ["example_trend_pullback"], default_registry())
    args: dict[str, object] = {"server": SERVER, "start": start, "end": end} | kw
    return HistoricalReplay(CONFIG, loaded.data, res, loaded.rates, strategies, **args)  # type: ignore[arg-type]


def rows(db: Database) -> list[ShadowTradeRow]:
    with db.session() as sess:
        return list(sess.execute(select(ShadowTradeRow).order_by(ShadowTradeRow.shadow_id)).scalars())


class TestReplay:
    def test_signals_become_resolved_replay_shadow_trades(
        self, store: ParquetHistoryStore, db: Database
    ) -> None:
        report = replay(store).run(db)
        assert report.resolution == {"EURUSD": "M5"} and report.bars > 400
        assert report.accepted >= 1 and report.stored == 2 * report.accepted - report.unresolved
        stored = rows(db)
        assert stored and {r.source for r in stored} == {"REPLAY"}
        assert all(r.opportunity_id.startswith("replay:") for r in stored)
        assert {r.variant for r in stored} == {"PLAN", "MANAGED"}
        for r in stored:
            assert r.status == "CLOSED" and r.exit_at is not None and r.exit_reason is not None
            assert r.entry_at == r.signal_at and r.exit_at > r.entry_at
            assert r.exit_at <= r.deadline + timedelta(minutes=5)
            assert r.win == (r.exit_reason == "TP") and r.r_multiple is not None and r.r_net is not None
            assert (
                r.lot is not None and r.gross_pnl is not None and r.equity == CONFIG.backtest.initial_balance
            )
            assert r.features and r.strategy == "example_trend_pullback" and r.asset_class == "FOREX_MAJOR"
            assert r.ask is not None and r.bid is not None and r.entry_price == pytest.approx(r.ask + 0.00001)
            assert "TICK_RESOLVED" not in r.flags  # history has no ticks

    def test_deterministic(self, store: ParquetHistoryStore, tmp_path: Path) -> None:
        a = Database(f"sqlite:///{(tmp_path / 'a.db').as_posix()}")
        b = Database(f"sqlite:///{(tmp_path / 'b.db').as_posix()}")
        for d in (a, b):
            d.create_all()
        replay(store).run(a)
        replay(store).run(b)
        first = [[getattr(r, k) for k in KEYS] for r in rows(a)]
        assert first and first == [[getattr(r, k) for k in KEYS] for r in rows(b)]
        a.dispose()
        b.dispose()

    def test_reruns_add_nothing_twice(self, store: ParquetHistoryStore, db: Database) -> None:
        first = replay(store).run(db)
        again = replay(store).run(db)
        assert again.stored == 0 and again.existing == first.accepted
        assert len(rows(db)) == first.stored

    def test_equity_sizes_the_lot(self, store: ParquetHistoryStore, db: Database, tmp_path: Path) -> None:
        replay(store).run(db)
        small = Database(f"sqlite:///{(tmp_path / 's.db').as_posix()}")
        small.create_all()
        replay(store, equity=1_000.0).run(small)
        big, little = rows(db)[0], rows(small)[0]
        assert big.lot is not None and little.lot is not None and little.lot < big.lot
        assert little.r_multiple == pytest.approx(big.r_multiple)  # R does not depend on the lot
        small.dispose()


class TestResolution:
    def test_prefers_m1_and_fails_closed(self, store: ParquetHistoryStore) -> None:
        assert load_resolution(store, SERVER, "EURUSD").timeframe is Timeframe.M5
        m5 = store.load(SERVER, "EURUSD", Timeframe.M5)
        store.save(SERVER, "EURUSD", Timeframe.M1, full_columns(m5.head(10)), EURUSD_SPEC)
        assert load_resolution(store, SERVER, "EURUSD").timeframe is Timeframe.M1
        with pytest.raises(DataQualityError, match="M1/M5"):
            load_resolution(store, SERVER, "GBPUSD")

    def test_every_symbol_needs_resolution(self, store: ParquetHistoryStore) -> None:
        loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
        strategies = strategy_set(CONFIG, ["example_trend_pullback"], default_registry())
        with pytest.raises(DataQualityError, match="resolution"):
            HistoricalReplay(CONFIG, loaded.data, {}, loaded.rates, strategies, server=SERVER)


def test_cli(store: ParquetHistoryStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "engine.db"
    env = tmp_path / ".env"
    env.write_text(f"TRADING_MODE=BACKTEST\nENGINE_DB_URL=sqlite:///{db_path.as_posix()}\n", encoding="utf-8")
    start, end = window(store)
    argv = [
        "--env-file", str(env), "advisory", "replay", "--server", SERVER, "--data", str(store.root),
        "--symbols", "EURUSD", "--start", start.isoformat(), "--end", end.isoformat(),
        "--strategies", "example_trend_pullback", "--detectors", "none",
    ]  # fmt: skip
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "source=REPLAY" in out and "resolution {'EURUSD': 'M5'}" in out
    db = Database(f"sqlite:///{db_path.as_posix()}")
    stored = rows(db)
    assert stored and all(r.source == "REPLAY" for r in stored)
    assert main(argv) == 0 and len(rows(db)) == len(stored)  # idempotent
    db.dispose()


def test_months_window(
    store: ParquetHistoryStore, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / ".env"
    env.write_text(
        f"TRADING_MODE=BACKTEST\nENGINE_DB_URL=sqlite:///{(tmp_path / 'e.db').as_posix()}\n", encoding="utf-8"
    )
    argv = [
        "--env-file", str(env), "advisory", "replay", "--server", SERVER, "--data", str(store.root),
        "--symbols", "EURUSD", "--months", "0.1", "--strategies", "example_trend_pullback", "--detectors", "none",
    ]  # fmt: skip
    assert main(argv) == 0
    line = next(x for x in capsys.readouterr().out.splitlines() if x.startswith("replay"))
    first, last = (datetime.fromisoformat(p.strip()) for p in line.split("  ")[1].split("->"))
    assert timedelta(days=2) < last - first <= timedelta(days=3.1)


def test_evidence_features_are_recorded(store: ParquetHistoryStore, db: Database) -> None:
    from app.evidence.catalog import default_registry as evidence_registry
    from app.evidence.registry import EvidenceEngine

    registry = evidence_registry()
    plan = registry.plan_from_config(CONFIG.evidence, only={"trend.ma_alignment"})
    replay(store, evidence=EvidenceEngine(registry, plan)).run(db)
    stored = rows(db)
    assert stored and any(k.startswith("ev:") for r in stored for k in r.features)


class TestEntryModes:
    """TAA-L702: replay support (REPLAY rows of the entry-mode variants)."""

    def test_variants_are_replayed_beside_plan(self, store: ParquetHistoryStore, db: Database) -> None:
        data = CONFIG.model_dump(mode="json")
        data["advisory"]["shadow"]["entry_modes"] = {"variants": ["PULLBACK", "WIDE_STOP", "PULLBACK_WIDE"]}
        cfg = AppConfig.model_validate(data)
        start, end = window(store)
        loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
        res = {"EURUSD": load_resolution(store, SERVER, "EURUSD")}
        strategies = strategy_set(cfg, ["example_trend_pullback"], default_registry())
        HistoricalReplay(
            cfg, loaded.data, res, loaded.rates, strategies, server=SERVER, start=start, end=end
        ).run(db)
        stored = rows(db)
        by_opp: dict[str, dict[str, ShadowTradeRow]] = {}
        for r in stored:
            by_opp.setdefault(r.opportunity_id, {})[r.variant] = r
        assert {r.variant for r in stored} >= {"PLAN", "MANAGED", "WIDE_STOP"}
        assert {r.status for r in stored} <= {"CLOSED", "MISSED", "VOID"}  # never PENDING in a replay
        for variants in by_opp.values():
            plan = variants.get("PLAN")
            if plan is None or plan.status != "CLOSED":
                continue
            for name, row in variants.items():
                assert row.tp == plan.tp, name  # no variant moves the TP
                if name in ("PULLBACK", "PULLBACK_WIDE") and row.status == "CLOSED":
                    assert row.entry_window_end is not None and row.entry_at < row.entry_window_end
                    assert (plan.entry_price - row.entry_price) * (1 if plan.side == "BUY" else -1) > 0
