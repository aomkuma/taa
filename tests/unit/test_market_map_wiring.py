"""The market map wired to every setup (TAA-L809): live context, persistence, signal features, replay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select

from app.advisory.confidence import signal_features
from app.advisory.replay import HistoricalReplay, load_resolution
from app.advisory.scanner import strategy_set
from app.backtest.runner import load_context, load_history
from app.config import AppConfig
from app.core.clock import ManualClock
from app.core.enums import Timeframe
from app.indicators.market_map import MapState
from app.market_data.history_store import ParquetHistoryStore
from app.storage.database import Database
from app.storage.models import ShadowTradeRow
from app.strategy.catalog import default_registry
from app.strategy.context_builder import ContextBuilder
from app.strategy.market_maps import MapBook, candle_frame, map_params
from app.strategy.signal_models import MarketContext
from tests.backtest.test_replay import split_m5
from tests.backtest.test_runner_cli import CONFIG, SERVER, TFS, full_columns, store_symbol, window
from tests.strategy_data import EURUSD_SPEC, StubCandles, random_m15, resample
from tests.unit.test_strategy_models import make_signal

ON = AppConfig.model_validate({"timeframes": {"context": ["H4"], "context_bars": 400}})


@pytest.fixture(scope="module")
def frames() -> dict[Timeframe, pd.DataFrame]:
    m15 = random_m15(4000, drift=0.00002)
    return {
        Timeframe.M15: m15,
        Timeframe.H1: resample(m15, Timeframe.H1),
        Timeframe.H4: resample(m15, Timeframe.H4),
    }


class TestLiveContext:
    def test_the_builder_attaches_the_map_and_fetches_the_context_bars(
        self, frames: dict[Timeframe, pd.DataFrame]
    ) -> None:
        now = pd.Timestamp(frames[Timeframe.M15]["close_time"].iloc[-1]).to_pydatetime() + timedelta(
            seconds=5
        )
        source = StubCandles(frames, now)
        ctx = ContextBuilder(source, ON, ManualClock(now)).build("EURUSD")
        assert ctx.market.htf is not None and set(ctx.market.htf.frames) == {"H4"}
        h4 = ctx.market.htf.frames["H4"]
        assert h4.at <= ctx.market.decision_time_utc and h4.state is not MapState.UNKNOWN
        assert ("EURUSD", Timeframe.H4, 400) in source.calls
        assert all(tf is not Timeframe.H4 for tf in ctx.frames)  # never a strategy frame
        assert not any(f.startswith("H4:") for f in ctx.market.quality_flags)

    def test_off_by_default(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        now = pd.Timestamp(frames[Timeframe.M15]["close_time"].iloc[-1]).to_pydatetime() + timedelta(
            seconds=5
        )
        source = StubCandles(frames, now)
        ctx = ContextBuilder(source, AppConfig(), ManualClock(now)).build("EURUSD")
        assert ctx.market.htf is None and "htf" not in ctx.market.to_dict()
        assert all(tf is not Timeframe.H4 for _, tf, _ in source.calls)

    def test_the_market_context_round_trips_with_its_map(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        now = pd.Timestamp(frames[Timeframe.M15]["close_time"].iloc[-1]).to_pydatetime() + timedelta(
            seconds=5
        )
        market = ContextBuilder(StubCandles(frames, now), ON, ManualClock(now)).build("EURUSD").market
        again = MarketContext.from_json(market.to_json())
        assert again == market and again.digest == market.digest


class TestMapBook:
    def test_one_map_per_context_bar_and_states_once_per_frame(
        self, frames: dict[Timeframe, pd.DataFrame]
    ) -> None:
        book = MapBook(map_params(ON), [Timeframe.H4])
        h4 = {Timeframe.H4: candle_frame(frames[Timeframe.H4])}
        t = pd.Timestamp(frames[Timeframe.H4]["close_time"].iloc[200]).to_pydatetime()
        a = book.at("EURUSD", h4, t + timedelta(minutes=15))
        b = book.at("EURUSD", h4, t + timedelta(minutes=45))
        assert a is not None and b is not None and a.frames["H4"] is b.frames["H4"]
        assert a.frames["H4"].at == t  # the last closed bar, never a later one
        assert len(book._states) == 1

    def test_too_few_bars_leave_the_timeframe_out(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        book = MapBook(map_params(ON), [Timeframe.H4])
        h4 = {Timeframe.H4: candle_frame(frames[Timeframe.H4])}
        early = pd.Timestamp(frames[Timeframe.H4]["close_time"].iloc[10]).to_pydatetime()
        assert book.at("EURUSD", h4, early) is None


def test_signal_features_carry_the_map(frames: dict[Timeframe, pd.DataFrame]) -> None:
    now = pd.Timestamp(frames[Timeframe.M15]["close_time"].iloc[-1]).to_pydatetime() + timedelta(seconds=5)
    market = ContextBuilder(StubCandles(frames, now), ON, ManualClock(now)).build("EURUSD").market
    features = signal_features(make_signal(), market)
    assert {"ctx:h4_trend", "ctx:h4_range", "ctx:h4_zone_with", "ctx:h4_room_r"} <= set(features)
    plain = signal_features(make_signal(), MarketContext.from_dict({**market.to_dict(), "htf": None}))
    assert not any(k.startswith("ctx:h4_") for k in plain)


def test_the_replay_records_the_map_features(tmp_path: Path) -> None:
    store = ParquetHistoryStore(tmp_path / "history")
    store_symbol(store, EURUSD_SPEC)
    m15 = store.load(SERVER, "EURUSD", Timeframe.M15)
    store.save(SERVER, "EURUSD", Timeframe.M5, full_columns(split_m5(m15)), EURUSD_SPEC)
    store.save(SERVER, "EURUSD", Timeframe.H4, full_columns(resample(m15, Timeframe.H4)), EURUSD_SPEC)
    data = CONFIG.model_dump(mode="json")
    data["timeframes"]["context"] = ["H4"]
    cfg = AppConfig.model_validate(data)
    start, end = window(store)
    loaded = load_history(store, SERVER, ["EURUSD"], TFS, account_currency="USD")
    context = load_context(store, SERVER, ["EURUSD"], [Timeframe.H4], end=end)
    replay = HistoricalReplay(
        cfg,
        loaded.data,
        {"EURUSD": load_resolution(store, SERVER, "EURUSD")},
        loaded.rates,
        strategy_set(cfg, ["example_trend_pullback"], default_registry()),
        server=SERVER,
        start=start,
        end=end,
        context=context,
    )
    db = Database("sqlite://")
    db.create_all()
    replay.run(db)
    with db.session() as sess:
        rows = list(sess.scalars(select(ShadowTradeRow)))
    assert rows
    with_map = [r for r in rows if "ctx:h4_range" in r.features]  # trend is absent while EMA200 warms up
    assert with_map, "signals after the H4 warm-up carry the map"
    assert all(r.signal_at >= datetime(2000, 1, 1, tzinfo=UTC) for r in with_map)


def test_context_map_thresholds_per_timeframe() -> None:
    """Owner, 2026-10-14: an M5 map needs its own trend thresholds; other timeframes keep the global ones."""
    import pytest

    from app.config import AppConfig, ConfigError, ContextMapConfig
    from app.core.enums import Timeframe
    from app.strategy.market_maps import MapBook, map_params

    cfg = AppConfig.model_validate(
        {
            "timeframes": {"entry": "M1", "higher": "M15", "context": ["M5", "H1"]},
            "context_map": {"by_timeframe": {"M5": {"er_trend": 0.2, "er_range": 0.15, "trend_adx": 15}}},
        }
    )
    m5, h1 = map_params(cfg, Timeframe.M5), map_params(cfg, Timeframe.H1)
    assert (m5.er_trend, m5.er_range, m5.trend_adx) == (0.2, 0.15, 15)
    assert (h1.er_trend, h1.trend_adx) == (cfg.context_map.er_trend, cfg.regime.trend_adx)
    book = MapBook.from_config(cfg)
    assert book is not None and book._params(Timeframe.M5).er_trend == 0.2
    with pytest.raises((ValueError, ConfigError)):
        ContextMapConfig.model_validate({"by_timeframe": {"M5": {"er_range": 0.5}}})
