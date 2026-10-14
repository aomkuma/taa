"""The chart read wired into the market map (TAA-L813 CR-2): MapBook, persistence, ctx: features."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.config import AppConfig
from app.core.clock import ManualClock
from app.core.enums import Timeframe
from app.indicators.chart_read import (
    ChartRead,
    EventKind,
    Leg,
    Level,
    LevelRole,
    ReadEvent,
    Structure,
    TrendLine,
)
from app.indicators.market_map import MarketMap, read_features, signal_features
from app.indicators.price_action import SwingKind
from app.strategy.context_builder import ContextBuilder
from app.strategy.market_maps import MapBook, candle_frame, chart_read_params
from app.strategy.signal_models import MarketContext
from tests.strategy_data import EURUSD_SPEC, StubCandles, random_m15, resample

ON = AppConfig.model_validate({"timeframes": {"context": ["H1", "H4"], "context_bars": 400}})
OFF = AppConfig.model_validate(
    {
        "timeframes": {"context": ["H1", "H4"], "context_bars": 400},
        "context_map": {"chart_read": {"enabled": False}},
    }
)
POINT = EURUSD_SPEC.point


@pytest.fixture(scope="module")
def frames() -> dict[Timeframe, pd.DataFrame]:
    m15 = random_m15(4000, drift=0.00002)
    return {
        Timeframe.M15: m15,
        Timeframe.H1: resample(m15, Timeframe.H1),
        Timeframe.H4: resample(m15, Timeframe.H4),
    }


def context(frames: dict[Timeframe, pd.DataFrame]) -> dict[Timeframe, pd.DataFrame]:
    return {tf: candle_frame(frames[tf]) for tf in (Timeframe.H1, Timeframe.H4)}


def late(frames: dict[Timeframe, pd.DataFrame]) -> datetime:
    return pd.Timestamp(frames[Timeframe.H4]["close_time"].iloc[-1]).to_pydatetime()


class TestMapBook:
    def test_every_context_timeframe_carries_its_read_with_the_higher_one_s_leg(
        self, frames: dict[Timeframe, pd.DataFrame]
    ) -> None:
        book = MapBook.from_config(ON)
        assert book is not None
        mm = book.at("EURUSD", context(frames), late(frames), POINT)
        assert mm is not None
        h1, h4 = mm.frames["H1"].read, mm.frames["H4"].read
        assert h1 is not None and h4 is not None
        assert (h1.timeframe, h4.timeframe) == ("H1", "H4")
        assert h1.at == mm.frames["H1"].at and h4.at == mm.frames["H4"].at
        assert h1.retrace_major is not None  # against the H4 read's last leg
        assert h4.retrace_major is None  # no higher context timeframe

    def test_no_point_or_the_block_off_leaves_the_map_as_before(
        self, frames: dict[Timeframe, pd.DataFrame]
    ) -> None:
        on = MapBook.from_config(ON)
        off = MapBook.from_config(OFF)
        assert on is not None and off is not None and off.reads == {}
        without_point = on.at("EURUSD", context(frames), late(frames))
        disabled = off.at("EURUSD", context(frames), late(frames), POINT)
        for mm in (without_point, disabled):
            assert mm is not None
            assert all(m.read is None for m in mm.frames.values())
            assert all("read" not in f for f in mm.to_dict()["frames"].values())

    def test_swings_once_per_frame_and_one_read_per_context_bar(
        self, frames: dict[Timeframe, pd.DataFrame]
    ) -> None:
        book = MapBook.from_config(ON)
        assert book is not None
        ctx = context(frames)
        t = pd.Timestamp(frames[Timeframe.H1]["close_time"].iloc[600]).to_pydatetime()
        a = book.at("EURUSD", ctx, t + timedelta(minutes=15), POINT)
        b = book.at("EURUSD", ctx, t + timedelta(minutes=45), POINT)
        assert a is not None and b is not None
        assert a.frames["H4"].read is b.frames["H4"].read
        assert len(book._frames) == 2

    def test_by_timeframe_overrides_only_the_zigzag(self) -> None:
        cfg = AppConfig.model_validate(
            {"context_map": {"chart_read": {"by_timeframe": {"M15": {"depth": 24}}}}}
        )
        m15, h1 = chart_read_params(cfg, Timeframe.M15), chart_read_params(cfg, Timeframe.H1)
        assert m15 is not None and h1 is not None
        assert (m15.depth, h1.depth, m15.backstep) == (24, 12, 3)
        assert chart_read_params(OFF) is None


class TestPersistence:
    def test_the_market_context_round_trips_with_its_reads(
        self, frames: dict[Timeframe, pd.DataFrame]
    ) -> None:
        now = pd.Timestamp(frames[Timeframe.M15]["close_time"].iloc[-1]).to_pydatetime() + timedelta(
            seconds=5
        )
        market = (
            ContextBuilder(StubCandles(frames, now), ON, ManualClock(now)).build("EURUSD", EURUSD_SPEC).market
        )
        assert market.htf is not None and market.htf.frames["H4"].read is not None
        again = MarketContext.from_json(market.to_json())
        assert again == market and again.digest == market.digest

    def test_a_map_recorded_before_the_read_still_loads(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        book = MapBook.from_config(ON)
        assert book is not None
        mm = book.at("EURUSD", context(frames), late(frames))
        assert mm is not None
        old = mm.to_dict()
        assert MarketMap.from_dict(old) == mm


T = datetime(2026, 3, 2, 10, tzinfo=UTC)


def a_read(**kw: object) -> ChartRead:
    base: dict[str, object] = {
        "timeframe": "H1",
        "at": T,
        "close": 100.0,
        "atr": 1.0,
        "digits": 2,
        "structure": Structure.UP,
        "invalidation": 98.0,
        "broken": False,
        "age_legs": 2,
        "leg": Leg(1, 97.0, 100.5, 10, 3.5, 3.0, 0.25),
        "levels": (
            Level(103.0, LevelRole.RESISTANCE, True, 2, T, T, 0, 3.0),
            Level(99.9, LevelRole.FLIPPED, False, 1, T, T, 1, 0.1),
            Level(97.0, LevelRole.SUPPORT, False, 2, T, T, 0, 3.0),
        ),
        "trendlines": (TrendLine(SwingKind.LOW, T, 95.0, T, 97.0, 99.0, 0.02, 1.0, 3, False, None),),
        "events": (
            ReadEvent(EventKind.RETEST, 1, 99.9, False, T, T),
            ReadEvent(
                EventKind.SWEEP_RECLAIM, -1, 103.0, False, T - timedelta(hours=2), T - timedelta(hours=2)
            ),
        ),
        "retrace_major": 0.4,
    }
    base.update(kw)
    return ChartRead(**base)  # type: ignore[arg-type]


class TestFeatures:
    def test_a_buy_at_a_flipped_level_in_an_up_structure(self) -> None:
        f = read_features(a_read(), "ctx:h1_", buy=True, entry=100.0, risk=1.0, room_cap=10.0)
        assert f["ctx:h1_sw_trend"] == 1.0 and f["ctx:h1_sw_phase"] == 0.0
        assert (f["ctx:h1_sw_age"], f["ctx:h1_sw_broken"]) == (2.0, 0.0)
        assert f["ctx:h1_inv_r"] == pytest.approx(2.0)  # the HL 2 R behind the entry
        assert f["ctx:h1_lvl_with_atr"] == pytest.approx(0.1)
        assert f["ctx:h1_lvl_against_r"] == pytest.approx(3.0)
        assert f["ctx:h1_lvl_flipped"] == 1.0
        assert f["ctx:h1_tl_atr"] == pytest.approx(1.0)  # above the rising support line
        assert (f["ctx:h1_retrace"], f["ctx:h1_retrace_major"]) == (0.25, 0.4)
        assert (f["ctx:h1_ev_retest"], f["ctx:h1_ev_sweep_reclaim"], f["ctx:h1_ev_break_hold"]) == (
            1.0,
            -1.0,
            0.0,
        )

    def test_a_sell_mirrors_every_sign(self) -> None:
        f = read_features(a_read(), "ctx:h1_", buy=False, entry=100.0, risk=1.0, room_cap=10.0)
        assert f["ctx:h1_sw_trend"] == -1.0
        assert f["ctx:h1_inv_r"] == pytest.approx(-2.0)  # the invalidation lies ahead of a sell
        assert f["ctx:h1_lvl_with_atr"] == pytest.approx(3.0)  # the resistance above
        assert f["ctx:h1_lvl_against_r"] == pytest.approx(0.1)
        assert f["ctx:h1_lvl_flipped"] == 0.0  # the flipped level supports a buy, not a sell
        assert f["ctx:h1_tl_atr"] == pytest.approx(-1.0)
        assert (f["ctx:h1_ev_retest"], f["ctx:h1_ev_sweep_reclaim"]) == (-1.0, 1.0)

    def test_mixed_phases_and_the_warm_up(self) -> None:
        tri = read_features(
            a_read(structure=Structure.CONTRACTING, invalidation=None),
            "k_",
            buy=True,
            entry=100.0,
            risk=1.0,
            room_cap=10.0,
        )
        assert (tri["k_sw_trend"], tri["k_sw_phase"]) == (0.0, 1.0) and "k_inv_r" not in tri
        none = read_features(
            a_read(structure=Structure.NONE, invalidation=None),
            "k_",
            buy=True,
            entry=100.0,
            risk=None,
            room_cap=10.0,
        )
        assert not any(k.startswith("k_sw_") for k in none) and "k_lvl_against_r" not in none

    def test_no_level_ahead_is_the_cap(self) -> None:
        f = read_features(a_read(), "k_", buy=True, entry=104.0, risk=1.0, room_cap=10.0)
        assert f["k_lvl_against_r"] == 10.0

    def test_signal_features_include_the_read(self, frames: dict[Timeframe, pd.DataFrame]) -> None:
        book = MapBook.from_config(ON)
        assert book is not None
        mm = book.at("EURUSD", context(frames), late(frames), POINT)
        assert mm is not None
        close = mm.frames["H1"].close
        f = signal_features(mm, buy=True, entry=close, stop=close - 0.002, target=close + 0.004)
        assert {"ctx:h1_ev_break_hold", "ctx:h4_ev_retest", "ctx:h1_lvl_flipped"} <= set(f)
        plain = signal_features(
            MapBook.from_config(OFF).at("EURUSD", context(frames), late(frames), POINT),  # type: ignore[union-attr,arg-type]
            buy=True,
            entry=close,
            stop=close - 0.002,
            target=close + 0.004,
        )
        assert not any("_ev_" in k or "_sw_" in k for k in plain)
