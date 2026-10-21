from __future__ import annotations

import dataclasses
import math
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest

from app.config import AppConfig, StrategiesConfig, StrategyEntry, TimeframesConfig, load_settings
from app.core.clock import ManualClock
from app.core.enums import Action, Timeframe, Trend
from app.evidence.catalog import default_registry as evidence_registry
from app.evidence.framework import (
    ActiveEvidence,
    Direction,
    Evidence,
    EvidenceSnapshot,
    Family,
    KeyLevel,
    Tier,
)
from app.evidence.registry import EvidenceEngine
from app.indicators.market_map import MapState, MapZone, MarketMap, TimeframeMap, ZoneKind, ZoneSource
from app.strategy.catalog import STRATEGIES, default_registry
from app.strategy.context_builder import ContextBuilder
from app.strategy.setups import (
    SETUPS,
    CandleReversal,
    ElliottWave,
    FibPullback,
    HarmonicPrz,
    NecklineBreak,
    RangeBreakout,
    SmcReversal,
    variant,
)
from app.strategy.signal_models import MarketContext, Signal, StrategyContext
from tests.evidence_harness import candles
from tests.evidence_paths import path_frame
from tests.strategy_data import EURUSD_SPEC, StubCandles, resample
from tests.unit.test_strategy_models import state

T = datetime(2026, 9, 30, 10, 15, tzinfo=UTC)
ATR = 0.0010
CLOSE = 1.1012
SPREAD = 0.00008  # 8 points
ENTRY = CLOSE + SPREAD


def ev(
    detector: str,
    direction: Direction = Direction.BULL,
    *,
    family: Family = Family.CHART_PATTERN,
    quality: float = 0.8,
    invalidation: float | None = None,
    targets: tuple[float, ...] = (),
    var: str | None = None,
    details: dict[str, object] | None = None,
    age: int = 0,
) -> ActiveEvidence:
    suffix = f".{var}" if var else ""
    record = Evidence(
        detector_id=detector,
        detector_version=1,
        family=family,
        tier=Tier.T2,
        name=detector,
        i18n_key=f"evidence.{detector}{suffix}",
        symbol="EURUSD",
        timeframe=Timeframe.M15,
        direction=direction,
        detected_at=T - timedelta(minutes=15 * age),
        quality=quality,
        key_levels=(KeyLevel("x", 1.1),),
        invalidation=invalidation,
        targets=targets,
        details=tuple(sorted((details or {}).items())),  # type: ignore[arg-type]
    )
    return ActiveEvidence(record, T, age)


def mirror_item(a: ActiveEvidence) -> ActiveEvidence:
    e = a.evidence
    flipped = Evidence(
        **{
            **{f: getattr(e, f) for f in e.__dataclass_fields__},
            "direction": Direction.BEAR if e.direction is Direction.BULL else Direction.BULL,
            "invalidation": None if e.invalidation is None else 2.2 - e.invalidation,
            "targets": tuple(2.2 - t for t in e.targets),
        }
    )
    return ActiveEvidence(flipped, a.as_of, a.age_bars)


def sctx(
    *items: ActiveEvidence,
    close: float = CLOSE,
    at: datetime = T,
    htf: Trend = Trend.BULLISH,
    resistance: tuple[float, ...] = (1.1060,),
    support: tuple[float, ...] = (1.0940,),
    evidence: bool = True,
) -> StrategyContext:
    idx = pd.date_range(end=at, periods=5, freq="15min")
    frame = pd.DataFrame(
        {"close": np.full(5, close), "atr": np.full(5, ATR), "spread": np.full(5, 8.0)}, index=idx
    )
    market = MarketContext(
        symbol="EURUSD",
        decision_time_utc=at,
        entry_timeframe=Timeframe.M15,
        higher_timeframe=Timeframe.H1,
        states=(
            state(Timeframe.M15, at, close=close),
            state(Timeframe.H1, at - timedelta(minutes=15), trend=htf),
        ),
        spread_points=8.0,
        support_levels=support,
        resistance_levels=resistance,
    )
    snaps = (
        {Timeframe.M15: EvidenceSnapshot("EURUSD", Timeframe.M15, at, tuple(items), (), "d")}
        if evidence
        else {}
    )
    return StrategyContext(market, {Timeframe.M15: frame}, at, EURUSD_SPEC, snaps)


def run(cls: type, ctx: StrategyContext, **params: object) -> Signal:
    return cls(cls.Params(**params)).evaluate(ctx)  # type: ignore[no-any-return]


DOUBLE = ev("chart.double", invalidation=1.0950, targets=(1.1080,), var="bottom")


class TestNecklineBreak:
    def test_buy_takes_the_nearer_stop_and_the_measured_target(self) -> None:
        sig = run(NecklineBreak, sctx(DOUBLE))
        assert sig.action is Action.BUY, sig.explanation
        assert sig.entry_price == pytest.approx(ENTRY)
        assert sig.stop_loss == pytest.approx(ENTRY - 1.5 * ATR - SPREAD)  # 1.5 ATR is nearer than 1.0950
        assert sig.take_profit == pytest.approx(1.1080)
        assert sig.reason_codes == ("NECKLINE_BREAK", "DEMO_UNPROVEN")
        assert "nearer than the invalidation" in sig.explanation

    def test_sell_is_the_mirror(self) -> None:
        sig = run(NecklineBreak, sctx(mirror_item(DOUBLE), close=2.2 - CLOSE, htf=Trend.BEARISH))
        assert sig.action is Action.SELL, sig.explanation
        assert sig.entry_price == pytest.approx(2.2 - CLOSE)
        assert sig.stop_loss == pytest.approx(2.2 - CLOSE + 1.5 * ATR + SPREAD)
        assert sig.take_profit == pytest.approx(2.2 - 1.1080)

    def test_invalidation_mode_stops_beyond_the_pattern(self) -> None:
        sig = run(NecklineBreak, sctx(DOUBLE), stop_mode="invalidation", max_sl_atr=10.0, min_rr=0.5)
        assert sig.stop_loss == pytest.approx(1.0950 - 0.1 * ATR - SPREAD)

    def test_far_invalidation_is_sl_too_far(self) -> None:
        sig = run(NecklineBreak, sctx(DOUBLE), stop_mode="invalidation")
        assert sig.action is Action.HOLD
        assert "SL_TOO_FAR" in sig.reason_codes

    def test_measured_target_too_close_is_rr_too_low(self) -> None:
        close_target = ev("chart.double", invalidation=1.0950, targets=(1.1020,), var="bottom")
        sig = run(NecklineBreak, sctx(close_target))
        assert sig.reason_codes == ("RR_TOO_LOW",)

    def test_wrong_side_invalidation_falls_back_to_atr(self) -> None:
        odd = ev("chart.double", invalidation=1.1050, targets=(1.1080,), var="bottom")
        sig = run(NecklineBreak, sctx(odd), stop_mode="invalidation")
        assert sig.stop_loss == pytest.approx(ENTRY - 1.5 * ATR - SPREAD)
        assert "no usable invalidation" in sig.explanation

    @pytest.mark.parametrize(
        ("items", "reason"),
        [
            ((), "NO_SETUP"),
            ((ev("chart.double", invalidation=1.095, targets=(1.108,), age=1),), "NO_SETUP"),  # stale trigger
            ((ev("chart.triangle", invalidation=1.095),), "NO_SETUP"),  # another setup's detector
            ((DOUBLE, ev("chart.triple", Direction.BEAR, invalidation=1.11)), "CONFLICT"),
        ],
    )
    def test_no_trade(self, items: tuple[ActiveEvidence, ...], reason: str) -> None:
        sig = run(NecklineBreak, sctx(*items))
        assert sig.action is Action.HOLD
        assert sig.reason_codes == (reason,)

    def test_missing_evidence_is_insufficient_data(self) -> None:
        assert run(NecklineBreak, sctx(evidence=False)).reason_codes == ("INSUFFICIENT_DATA",)

    def test_outside_session(self) -> None:
        sig = run(NecklineBreak, sctx(DOUBLE, at=datetime(2026, 9, 30, 22, 0, tzinfo=UTC)))
        assert "OUTSIDE_SESSION" in sig.reason_codes

    def test_best_quality_trigger_wins(self) -> None:
        weak = ev("chart.triple", invalidation=1.0950, targets=(1.1070,), quality=0.3)
        assert run(NecklineBreak, sctx(weak, DOUBLE)).take_profit == pytest.approx(1.1080)


class TestOtherSetups:
    def test_fib_pullback_picks_the_first_target_with_enough_rr(self) -> None:
        golden = ev("fib.golden_zone", family=Family.FIBONACCI, invalidation=1.0995, targets=(1.1030, 1.1060))
        sig = run(FibPullback, sctx(golden))
        assert sig.action is Action.BUY, sig.explanation
        assert sig.stop_loss == pytest.approx(1.0995 - 0.1 * ATR - SPREAD)
        assert sig.take_profit == pytest.approx(1.1060)  # 1.1030 gives RR < 1.5
        opposed = run(FibPullback, sctx(golden, htf=Trend.BEARISH))
        assert opposed.action is Action.HOLD
        assert "CONFLICT" in opposed.reason_codes

    def test_harmonic_prz(self) -> None:
        bat = ev(
            "harmonic.bat",
            family=Family.HARMONIC,
            invalidation=1.0990,
            targets=(1.1040, 1.1060),
            var="bullish",
        )
        sig = run(HarmonicPrz, sctx(bat))
        assert sig.action is Action.BUY, sig.explanation
        assert sig.take_profit == pytest.approx(1.1060)
        assert sig.reason_codes[0] == "HARMONIC_PRZ"

    @pytest.mark.parametrize(
        ("var", "count", "fires"),
        [
            ("wave3", "primary", True),
            ("wave5", "primary", True),
            ("wave3", "alternate", False),
            ("c_completion", "primary", False),
        ],
    )
    def test_elliott_takes_primary_wave_3_and_5_only(self, var: str, count: str, fires: bool) -> None:
        wave = ev(
            "elliott.wave",
            family=Family.ELLIOTT,
            invalidation=1.0990,
            targets=(1.1060,),
            var=var,
            details={"count": count},
        )
        assert (run(ElliottWave, sctx(wave)).action is Action.BUY) is fires

    def test_smc_needs_sweep_and_choch_and_stops_beyond_the_sweep(self) -> None:
        fvg = ev("smc.fvg", family=Family.SMART_MONEY, invalidation=1.1004)
        sweep = ev("smc.liquidity_sweep", family=Family.SMART_MONEY, invalidation=1.0990, age=6)
        choch = ev("structure.bos_choch", family=Family.TREND, invalidation=1.0990, var="choch", age=3)
        sig = run(SmcReversal, sctx(fvg, sweep, choch))
        assert sig.action is Action.BUY, sig.explanation
        assert sig.stop_loss == pytest.approx(1.0990 - 0.1 * ATR - SPREAD)
        assert sig.take_profit == pytest.approx(1.1060)  # the opposite liquidity: next resistance
        bos = ev("structure.bos_choch", family=Family.TREND, invalidation=1.0990, var="bos", age=3)
        missing = run(SmcReversal, sctx(fvg, sweep, bos))
        assert missing.reason_codes == ("NO_SETUP",)
        assert [c.name for c in missing.conditions if not c.passed] == ["change_of_character"]
        too_old = run(SmcReversal, sctx(fvg, sweep, choch), confirm_window_bars=5)
        assert too_old.action is Action.HOLD

    def test_breakout_uses_rr_without_a_measured_target(self) -> None:
        donchian = ev("volatility.donchian", family=Family.VOLATILITY_VOLUME, invalidation=1.0950, var="n20")
        sig = run(RangeBreakout, sctx(donchian))
        assert sig.action is Action.BUY, sig.explanation
        risk = 1.5 * ATR + SPREAD
        assert sig.take_profit == pytest.approx(ENTRY + 2 * risk)

    def test_candle_reversal_needs_a_level(self) -> None:
        hammer = ev(
            "candle.hammer",
            family=Family.CANDLESTICK,
            invalidation=1.0998,
            details={"at_level": True, "at_levels": "evidence.fib.retracement"},
        )
        sig = run(CandleReversal, sctx(hammer))
        assert sig.action is Action.BUY, sig.explanation
        assert sig.stop_loss == pytest.approx(1.0998 - 0.1 * ATR - SPREAD)
        assert sig.take_profit == pytest.approx(1.1060)
        floating = ev(
            "candle.hammer", family=Family.CANDLESTICK, invalidation=1.0998, details={"at_level": False}
        )
        assert run(CandleReversal, sctx(floating)).reason_codes == ("NO_SETUP",)

    def test_neutral_candles_never_trigger(self) -> None:
        doji = ev("candle.doji", Direction.NEUTRAL, family=Family.CANDLESTICK, details={"at_level": True})
        assert run(CandleReversal, sctx(doji)).reason_codes == ("NO_SETUP",)


class TestCatalog:
    def test_every_setup_is_registered_and_labelled(self) -> None:
        names = default_registry().names
        for cls in SETUPS:
            assert cls.name in names
            assert cls.demo_only
            assert "Unproven" in cls.description
            assert cls.triggers <= set(evidence_registry().ids), cls.name
        # the inverted copies were removed (2026-10-14); Setup OWN F1 and S2 live in their own modules (2026-10-18),
        # PLAN-1's London ORB and NY straddle in app/strategy/plan1.py (2026-10-21)
        assert len(STRATEGIES) == 1 + len(SETUPS) + 4

    def test_config_yaml_trades_harmonic_on_its_normal_side_only(self) -> None:
        settings = load_settings(
            env_file=None, config_file="config.yaml", environ={"TRADING_MODE": "BACKTEST"}
        )
        listed = {item.name: item.enabled for item in settings.config.strategies.items}
        in_lanes = {i.name for lane in settings.config.lanes for i in lane.strategies.items}
        # every setup is listed, except a lane-only one (not advised) that no lane runs yet (under test)
        originals = {"example_trend_pullback", *(c.name for c in SETUPS if c.advised or c.name in in_lanes)}
        originals |= {"setup_own_conf72", "setup_own_s2"}  # Setup OWN's lanes own and news (2026-10-18)
        originals |= {"setup_plan1_orb", "setup_plan1_ny"}  # lane plan1 (2026-10-21, docs/PLAN1_LANE.md)
        assert set(listed) | in_lanes == originals
        # owner, 2026-10-12 (SETUP_REVIEW §15): harmonic, normal side, no break-even/trailing;
        # 2026-10-14 (§16): breakout F1, fades with the H4/H1 trend only; 2026-10-16: its own stop cap off;
        # 2026-10-17: every earlier setup stopped, the bot starts over with Setup OWN (docs/OWN_SETUP.md)
        assert not any(listed.values())
        breakout = next(i for i in settings.config.strategies.items if i.name == "setup_breakout")
        assert breakout.params == {
            "screen_h4": "with",
            "screen_h1": "with",
            "fade_counter_trend": True,
            "trend_entries": False,
            "max_sl_atr": 20.0,
            "friday_cutoff_utc": "16:00",
        }
        assert settings.config.timeframes.context == [Timeframe.H1, Timeframe.H4, Timeframe.D1]
        assert settings.config.risk.fade is not None  # fades need their own RR floor and SL cap
        own = settings.config.position_management.for_strategy("setup_harmonic_prz")
        assert own.break_even_trigger_r == math.inf and own.trailing_start_r == math.inf
        harmonic = next(i for i in settings.config.strategies.items if i.name == "setup_harmonic_prz")
        assert harmonic.params == {
            "phase_gate": "h4_against_or_range",
            "max_rr": 3.0,
            "structure_tf": "H4",
            "room_min_r": 2.0,
            "max_sl_atr": 20.0,
        }  # §15.3, no PRZ confirmation; h4_room_2 (owner, 2026-10-15; §18); own stop cap off (2026-10-16)
        # S1, M1 gold scalping (owner, 2026-10-15; §17); Setup OWN F1 and S2 (2026-10-18), all off until the owner
        s1, own, news, plan1 = settings.config.lanes
        assert (s1.timeframes.entry, s1.symbols) == (Timeframe.M1, ["XAUUSD"])
        assert [(i.name, i.enabled) for i in s1.strategies.items] == [("setup_breakout_scalp", False)]
        assert [(i.name, i.enabled) for i in own.strategies.items] == [("setup_own_conf72", True)]
        assert [(i.name, i.enabled) for i in news.strategies.items] == [("setup_own_s2", True)]
        # PLAN-1 (2026-10-21, docs/PLAN1_LANE.md): both pieces off until the measurer turns them on (PAPER)
        assert [(i.name, i.enabled) for i in plan1.strategies.items] == [
            ("setup_plan1_orb", False),
            ("setup_plan1_ny", False),
        ]
        orb = plan1.strategies.items[0].params
        assert (
            orb["target_r"] == 1.5
            and orb["atr_floor"] is None
            and orb["pool_break_when_h4_contracting"] is True
        )

    def test_each_setup_can_be_enabled_alone(self) -> None:
        for cls in SETUPS:
            cfg = StrategiesConfig(items=[StrategyEntry(name=cls.name, params={"min_quality": 0.5})])
            assert default_registry().from_config(cfg, TimeframesConfig()).names == [cls.name]

    def test_variant_helper(self) -> None:
        assert variant(DOUBLE.evidence) == "bottom"
        assert variant(ev("volatility.donchian").evidence) == ""


class TestScenario:
    """Real detectors on a synthetic W bottom, through the context builder and the evidence engine."""

    START = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)  # Monday: the neckline break lands on Wednesday 10:00

    def frames(self) -> dict[Timeframe, pd.DataFrame]:
        df = path_frame([100, 110, 90, 100, 90, 108])  # W: bottoms 89.9, neckline 100.1, break at bar 47
        df.index = pd.date_range(self.START, periods=len(df), freq="h")
        df["spread"] = 20
        h1 = candles(df)
        return {Timeframe.H1: h1, Timeframe.H4: resample(h1, Timeframe.H4, base=Timeframe.H1)}

    def signal_at(self, bar: int) -> Signal:
        cfg = AppConfig.model_validate({"timeframes": {"higher": "H4", "entry": "H1"}})
        frames = self.frames()
        now = frames[Timeframe.H1]["close_time"].iloc[bar].to_pydatetime() + timedelta(seconds=30)
        engine = EvidenceEngine(evidence_registry(), evidence_registry().plan(["chart.double"]))
        builder = ContextBuilder(StubCandles(frames, now), cfg, ManualClock(now), evidence=engine)
        ctx = builder.build("EURUSD", spec=EURUSD_SPEC)
        strategies = default_registry().from_config(
            StrategiesConfig(items=[StrategyEntry(name="setup_neckline_break")]),
            cfg.timeframes,
            cfg.evidence.confluence,
        )
        return strategies.evaluate(ctx)[0]

    def test_w_bottom_neckline_break_buys(self) -> None:
        sig = self.signal_at(47)
        assert sig.action is Action.BUY, sig.explanation
        assert sig.reason_codes[0] == "NECKLINE_BREAK"
        assert sig.take_profit == pytest.approx(100.1 + 10.2)  # neckline + pattern height
        assert sig.stop_loss is not None and sig.entry_price is not None
        assert sig.stop_loss < sig.entry_price < sig.take_profit
        assert any(e.item.evidence.detector_id == "chart.double" for e in sig.supporting)

    def test_no_signal_before_the_break(self) -> None:
        assert self.signal_at(46).action is Action.HOLD


def _bat(age: int = 0, invalidation: float = 1.0990) -> ActiveEvidence:
    return ev(
        "harmonic.bat",
        family=Family.HARMONIC,
        invalidation=invalidation,
        targets=(1.1040, 1.1060),
        var="bullish",
        age=age,
    )


def _with_h4(ctx: StrategyContext, state_: MapState | None) -> StrategyContext:
    frames = {}
    if state_ is not None:
        frames["H4"] = TimeframeMap("H4", T, state_, state_, 25.0, 0.4, 0.004, CLOSE, False, None)
    market = dataclasses.replace(ctx.market, htf=MarketMap(frames))
    return dataclasses.replace(ctx, market=market)


def _bars(
    ctx: StrategyContext, highs: list[float], lows: list[float], closes: list[float]
) -> StrategyContext:
    idx = pd.date_range(end=T, periods=len(closes), freq="15min")
    n = len(closes)
    frame = pd.DataFrame(
        {"high": highs, "low": lows, "close": closes, "atr": np.full(n, ATR), "spread": np.full(n, 8.0)},
        index=idx,
    )
    return dataclasses.replace(ctx, frames={Timeframe.M15: frame})


class TestHarmonicRefinements:
    """SETUP_REVIEW §15: the H4 phase gate, the PRZ confirmation and the R:R ceiling (all off by default)."""

    @pytest.mark.parametrize(
        ("h4", "fires"),
        [(MapState.DOWN, True), (MapState.RANGE, True), (MapState.UP, False), (None, False)],
    )
    def test_phase_gate_buys_against_the_h4_trend_or_in_a_range(
        self, h4: MapState | None, fires: bool
    ) -> None:
        sig = run(HarmonicPrz, _with_h4(sctx(_bat()), h4), phase_gate="h4_against_or_range")
        assert (sig.action is Action.BUY) is fires, sig.explanation

    def test_confirmation_waits_for_the_first_close_beyond_the_previous_bar(self) -> None:
        ctx = sctx(_bat(age=2))
        # bars: [.., PRZ-1, PRZ, after-1, decision]; after-1 does not break the PRZ bar's high, the decision does
        fresh = _bars(ctx, [1.1010, 1.1008, 1.1007, 1.1015], [1.0995] * 4, [1.1000, 1.0998, 1.1004, 1.1012])
        sig = run(HarmonicPrz, fresh, confirm="prior_bar_break", trigger_max_age_bars=6)
        assert sig.action is Action.BUY, sig.explanation
        stale = _bars(ctx, [1.1010, 1.1008, 1.1007, 1.1015], [1.0995] * 4, [1.1000, 1.0998, 1.1009, 1.1012])
        assert (
            run(HarmonicPrz, stale, confirm="prior_bar_break", trigger_max_age_bars=6).action is Action.HOLD
        )
        failed = _bars(ctx, [1.1010, 1.1008, 1.1007, 1.1015], [1.0980] * 4, [1.1000, 1.0985, 1.1004, 1.1012])
        sig = run(HarmonicPrz, failed, confirm="prior_bar_break", trigger_max_age_bars=6)
        assert sig.action is Action.HOLD and "invalidation" in sig.explanation

    def test_confirmation_never_enters_on_the_prz_bar_itself(self) -> None:
        ctx = _bars(
            sctx(_bat(age=0)), [1.1010, 1.1008, 1.1007, 1.1015], [1.0995] * 4, [1.1, 1.1, 1.1, 1.1012]
        )
        assert run(HarmonicPrz, ctx, confirm="prior_bar_break").action is Action.HOLD

    def test_max_rr_refuses_far_targets(self) -> None:
        assert run(HarmonicPrz, sctx(_bat()), max_rr=1.0).action is Action.HOLD
        assert run(HarmonicPrz, sctx(_bat()), max_rr=5.0).action is Action.BUY


DONCHIAN = ev("volatility.donchian", family=Family.VOLATILITY_VOLUME, invalidation=1.0950, var="n20")
BO_RISK = 1.5 * ATR + SPREAD  # the breakout's nearer (ATR) stop; its 2R target is ENTRY + 2 * BO_RISK


def _zone(kind: ZoneKind, low: float, high: float) -> MapZone:
    return MapZone(kind, ZoneSource.SWING, low, high, 2, 0, T)


def _with_map(ctx: StrategyContext, **frames: tuple[MapState, tuple[MapZone, ...]]) -> StrategyContext:
    maps = {
        tf: TimeframeMap(tf, T, st, st, 25.0, 0.4, 0.004, CLOSE, False, None, zones)
        for tf, (st, zones) in frames.items()
    }
    market = dataclasses.replace(ctx.market, htf=MarketMap(maps))
    return dataclasses.replace(ctx, market=market)


class TestTripleScreenAndZones:
    """SETUP_REVIEW §16 (owner, 2026-10-13): Elder's screens and demand/supply for every setup, off by default."""

    @pytest.mark.parametrize(
        ("gate", "h4", "fires"),
        [
            ("with", MapState.UP, True),
            ("with", MapState.RANGE, False),
            ("with", MapState.DOWN, False),
            ("with_or_range", MapState.RANGE, True),
            ("not_against", MapState.TRANSITION, True),
            ("not_against", MapState.DOWN, False),
            ("not_against", MapState.UNKNOWN, False),
            ("against_or_range", MapState.DOWN, True),
        ],
    )
    def test_first_screen_reads_h4_relative_to_the_trade(self, gate: str, h4: MapState, fires: bool) -> None:
        sig = run(RangeBreakout, _with_map(sctx(DONCHIAN), H4=(h4, ())), screen_h4=gate)
        assert (sig.action is Action.BUY) is fires, sig.explanation

    def test_a_sell_is_with_a_falling_h4(self) -> None:
        sell = mirror_item(DONCHIAN)
        assert run(RangeBreakout, _with_map(sctx(sell), H4=(MapState.DOWN, ())), screen_h4="with").action is (
            Action.SELL
        )

    def test_second_screen_reads_h1_and_a_missing_map_holds(self) -> None:
        ctx = _with_map(sctx(DONCHIAN), H4=(MapState.UP, ()), H1=(MapState.DOWN, ()))
        assert run(RangeBreakout, ctx, screen_h4="with").action is Action.BUY
        sig = run(RangeBreakout, ctx, screen_h4="with", screen_h1="not_against")
        assert sig.action is Action.HOLD and "H1 against" in sig.explanation
        assert run(RangeBreakout, sctx(DONCHIAN), screen_h1="not_against").action is Action.HOLD  # no map

    def test_default_ignores_the_map(self) -> None:
        ctx = _with_map(sctx(DONCHIAN), H4=(MapState.DOWN, (_zone(ZoneKind.SUPPLY, 1.1020, 1.1025),)))
        assert run(RangeBreakout, ctx).action is Action.BUY

    def test_zone_gate_refuses_an_opposing_zone_before_the_target(self) -> None:
        tp = ENTRY + 2 * BO_RISK
        blocked = _with_map(
            sctx(DONCHIAN), H4=(MapState.UP, (_zone(ZoneKind.SUPPLY, tp - 0.0005, tp + 0.0005),))
        )
        sig = run(RangeBreakout, blocked, zone_gate="clear_to_target")
        assert sig.action is Action.HOLD and "supply zone" in sig.explanation
        beyond = _with_map(
            sctx(DONCHIAN), H4=(MapState.UP, (_zone(ZoneKind.SUPPLY, tp + 0.0005, tp + 0.0010),))
        )
        assert run(RangeBreakout, beyond, zone_gate="clear_to_target").action is Action.BUY
        inside = _with_map(
            sctx(DONCHIAN), H4=(MapState.UP, (_zone(ZoneKind.SUPPLY, ENTRY - 0.0002, ENTRY + 0.0002),))
        )
        assert (
            run(RangeBreakout, inside, zone_gate="clear_to_target").action is Action.BUY
        )  # the zone it breaks
        demand = _with_map(
            sctx(DONCHIAN), H4=(MapState.UP, (_zone(ZoneKind.DEMAND, tp - 0.0005, tp + 0.0005),))
        )
        assert run(RangeBreakout, demand, zone_gate="clear_to_target").action is Action.BUY
        assert run(RangeBreakout, sctx(DONCHIAN), zone_gate="clear_to_target").action is Action.HOLD  # no map

    def test_zone_scope_h4_ignores_the_daily_zones(self) -> None:
        tp = ENTRY + 2 * BO_RISK
        ctx = _with_map(
            sctx(DONCHIAN), H4=(MapState.UP, ()), D1=(MapState.UP, (_zone(ZoneKind.SUPPLY, tp - 0.0005, tp),))
        )
        assert run(RangeBreakout, ctx, zone_gate="clear_to_target").action is Action.HOLD
        assert run(RangeBreakout, ctx, zone_gate="clear_to_target", zone_scope="H4").action is Action.BUY

    def test_zone_stop_sits_beyond_the_nearest_own_zone(self) -> None:
        zones = (_zone(ZoneKind.DEMAND, 1.0990, 1.1000), _zone(ZoneKind.DEMAND, 1.0960, 1.0970))
        sig = run(RangeBreakout, _with_map(sctx(DONCHIAN), H1=(MapState.UP, zones)), stop_mode="zone")
        assert sig.action is Action.BUY, sig.explanation
        assert sig.stop_loss == pytest.approx(1.0990 - 0.1 * ATR - SPREAD)
        none = run(RangeBreakout, _with_map(sctx(DONCHIAN), H1=(MapState.UP, ())), stop_mode="zone")
        assert none.stop_loss == pytest.approx(ENTRY - BO_RISK)  # no zone behind: the ATR stop

    def test_zone_target_is_the_near_edge_of_the_nearest_opposing_zone(self) -> None:
        zones = (_zone(ZoneKind.SUPPLY, 1.1070, 1.1080), _zone(ZoneKind.SUPPLY, 1.1060, 1.1065))
        sig = run(RangeBreakout, _with_map(sctx(DONCHIAN), H4=(MapState.UP, zones)), target_mode="zone")
        assert sig.action is Action.BUY and sig.take_profit == pytest.approx(1.1060)
        near = (_zone(ZoneKind.SUPPLY, ENTRY + 0.0005, ENTRY + 0.0010),)  # under min_rr: no trade
        assert run(
            RangeBreakout, _with_map(sctx(DONCHIAN), H4=(MapState.UP, near)), target_mode="zone"
        ).action is (Action.HOLD)


class TestTradeWithTheTide:
    """SETUP_REVIEW §16: a break with H4 and H1 is taken; a break against both is faded (fade_counter_trend)."""

    PARAMS: ClassVar[dict[str, object]] = {
        "screen_h4": "with",
        "screen_h1": "with",
        "fade_counter_trend": True,
    }

    def test_a_break_against_h4_and_h1_is_faded_at_the_plan_swapped(self) -> None:
        against = _with_map(sctx(DONCHIAN), H4=(MapState.DOWN, ()), H1=(MapState.DOWN, ()))
        sig = run(RangeBreakout, against, **self.PARAMS)
        assert sig.action is Action.SELL, sig.explanation  # the BUY break, faded: with the falling H4/H1
        assert sig.stop_loss == pytest.approx(ENTRY + 2 * BO_RISK)  # the plan's target
        assert sig.take_profit == pytest.approx(ENTRY - BO_RISK)  # the plan's stop
        assert sig.entry_price == pytest.approx(ENTRY)  # no live quote: the plan's price stands
        assert "FADE" in sig.reason_codes and "RANGE_BREAKOUT" in sig.reason_codes

    def test_a_live_quote_sells_the_fade_at_the_bid(self) -> None:
        against = _with_map(sctx(DONCHIAN), H4=(MapState.DOWN, ()), H1=(MapState.DOWN, ()))
        quoted = dataclasses.replace(
            against, market=dataclasses.replace(against.market, bid=CLOSE, ask=ENTRY)
        )
        assert run(RangeBreakout, quoted, **self.PARAMS).entry_price == pytest.approx(CLOSE)

    def test_a_break_with_h4_and_h1_is_taken(self) -> None:
        with_ = _with_map(sctx(DONCHIAN), H4=(MapState.UP, ()), H1=(MapState.UP, ()))
        sig = run(RangeBreakout, with_, **self.PARAMS)
        assert sig.action is Action.BUY and "FADE" not in sig.reason_codes

    @pytest.mark.parametrize(
        ("h4", "h1"),
        [(MapState.DOWN, MapState.UP), (MapState.DOWN, MapState.RANGE), (MapState.RANGE, MapState.DOWN)],
    )
    def test_anything_else_holds(self, h4: MapState, h1: MapState) -> None:
        ctx = _with_map(sctx(DONCHIAN), H4=(h4, ()), H1=(h1, ()))
        assert run(RangeBreakout, ctx, **self.PARAMS).action is Action.HOLD

    def test_off_by_default_a_counter_trend_break_just_holds(self) -> None:
        against = _with_map(sctx(DONCHIAN), H4=(MapState.DOWN, ()), H1=(MapState.DOWN, ()))
        assert run(RangeBreakout, against, screen_h4="with", screen_h1="with").action is Action.HOLD

    def test_a_fade_still_needs_the_other_rules(self) -> None:
        against = _with_map(sctx(DONCHIAN), H4=(MapState.DOWN, ()), H1=(MapState.DOWN, ()))
        assert run(RangeBreakout, against, max_rr=1.0, **self.PARAMS).action is Action.HOLD

    def test_against_needs_a_trend_not_a_range(self) -> None:
        ranging = _with_map(sctx(DONCHIAN), H4=(MapState.RANGE, ()))
        assert run(RangeBreakout, ranging, screen_h4="against").action is Action.HOLD


def _m15(ctx: StrategyContext, closes: np.ndarray) -> StrategyContext:
    idx = pd.date_range(end=T, periods=len(closes), freq="15min")
    frame = pd.DataFrame(
        {
            "high": closes + 0.0004,
            "low": closes - 0.0004,
            "close": closes,
            "atr": np.full(len(closes), ATR),
            "spread": np.full(len(closes), 8.0),
        },
        index=idx,
    )
    frame.iloc[-1, frame.columns.get_loc("close")] = CLOSE
    return dataclasses.replace(ctx, frames={Timeframe.M15: frame})


def _quiet(ctx: StrategyContext, h4_atr_pct: float | None) -> StrategyContext:
    h4 = TimeframeMap("H4", T, MapState.UP, MapState.UP, 25.0, 0.4, 0.004, CLOSE, False, None, (), h4_atr_pct)
    market = dataclasses.replace(ctx.market, htf=MarketMap({"H4": h4}))
    return dataclasses.replace(ctx, market=market)


RANGING = 1.1000 + 0.0003 * (-1.0) ** np.arange(300)  # a narrow box: low ADX and efficiency
TRENDING = 1.0700 + 0.00001 * np.arange(300)  # a steady rise


class TestRegimeFit:
    """Owner, 2026-10-14: in a phase that does not suit a setup it takes only its surest signals."""

    QUIET: ClassVar[dict[str, object]] = {"quiet_h4_atr_pct": 30.0, "quiet_rule": "m15_not_range"}

    def test_a_quiet_h4_refuses_a_break_out_of_a_ranging_m15(self) -> None:
        sig = run(RangeBreakout, _quiet(_m15(sctx(DONCHIAN), RANGING), 10.0), **self.QUIET)
        assert sig.action is Action.HOLD
        assert [c.name for c in sig.conditions if not c.passed] == ["quiet_phase_rule"]

    def test_a_quiet_h4_still_takes_a_trending_m15(self) -> None:
        sig = run(RangeBreakout, _quiet(_m15(sctx(DONCHIAN), TRENDING), 10.0), **self.QUIET)
        assert sig.action is Action.BUY, sig.explanation

    def test_a_normal_h4_ignores_the_rule(self) -> None:
        assert (
            run(RangeBreakout, _quiet(_m15(sctx(DONCHIAN), RANGING), 60.0), **self.QUIET).action is Action.BUY
        )

    def test_an_unknown_h4_volatility_counts_as_quiet(self) -> None:
        assert (
            run(RangeBreakout, _quiet(_m15(sctx(DONCHIAN), RANGING), None), **self.QUIET).action
            is Action.HOLD
        )

    def test_off_by_default(self) -> None:
        assert run(RangeBreakout, _quiet(_m15(sctx(DONCHIAN), RANGING), 10.0)).action is Action.BUY


class TestTrendEntryWindow:
    """SETUP_REVIEW §16: entries in the trigger's direction only in the New York window; fades unaffected."""

    PARAMS: ClassVar[dict[str, object]] = {
        "screen_h4": "with",
        "screen_h1": "with",
        "fade_counter_trend": True,
        "trend_entry_window_ny": "09:30-17:00",
    }

    def _at(self, when: datetime, h4: MapState) -> StrategyContext:
        return _with_map(sctx(DONCHIAN, at=when), H4=(h4, ()), H1=(h4, ()))

    def test_a_break_with_the_trend_waits_for_new_york(self) -> None:
        london = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)  # 04:00 New York (EDT)
        new_york = datetime(2026, 9, 30, 15, 0, tzinfo=UTC)  # 11:00 New York
        sig = run(RangeBreakout, self._at(london, MapState.UP), **self.PARAMS)
        assert sig.action is Action.HOLD and "trend_entry_window" in [
            c.name for c in sig.conditions if not c.passed
        ]
        assert run(RangeBreakout, self._at(new_york, MapState.UP), **self.PARAMS).action is Action.BUY

    def test_a_fade_is_not_limited_by_the_window(self) -> None:
        london = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
        assert run(RangeBreakout, self._at(london, MapState.DOWN), **self.PARAMS).action is Action.SELL

    def test_the_window_follows_daylight_saving(self) -> None:
        winter = datetime(2026, 1, 14, 14, 45, tzinfo=UTC)  # 09:45 New York (EST): inside
        assert run(RangeBreakout, self._at(winter, MapState.UP), **self.PARAMS).action is Action.BUY

    @pytest.mark.parametrize("window", ["17:00-09:30", "0930-1700", "09:30"])
    def test_a_bad_window_is_rejected(self, window: str) -> None:
        with pytest.raises(ValueError):
            RangeBreakout.Params(trend_entry_window_ny=window)


class TestFadeOnly:
    """Owner, 2026-10-14: wait for the counter-trend break, then trade with the big trend (no trend entries)."""

    PARAMS: ClassVar[dict[str, object]] = {
        "screen_h4": "with",
        "screen_h1": "with",
        "fade_counter_trend": True,
        "trend_entries": False,
    }

    def test_only_the_fade_trades(self) -> None:
        with_ = _with_map(sctx(DONCHIAN), H4=(MapState.UP, ()), H1=(MapState.UP, ()))
        against = _with_map(sctx(DONCHIAN), H4=(MapState.DOWN, ()), H1=(MapState.DOWN, ()))
        assert run(RangeBreakout, with_, **self.PARAMS).action is Action.HOLD
        assert run(RangeBreakout, against, **self.PARAMS).action is Action.SELL


class TestScreenTimeframes:
    """Owner, 2026-10-14: the screens follow the entry timeframe (e.g. M1 -> M5 -> M30), H4/H1 by default."""

    def test_the_screens_read_the_chosen_timeframes(self) -> None:
        ctx = _with_map(
            sctx(DONCHIAN),
            H4=(MapState.DOWN, ()),
            H1=(MapState.DOWN, ()),
            M30=(MapState.UP, ()),
            M5=(MapState.UP, ()),
        )
        params = {"screen_h4": "with", "screen_h1": "with"}
        assert run(RangeBreakout, ctx, **params).action is Action.HOLD  # H4/H1 against the BUY
        assert (
            run(RangeBreakout, ctx, screen_tide_tf="M30", screen_wave_tf="M5", **params).action is Action.BUY
        )

    def test_the_fade_reads_them_too(self) -> None:
        ctx = _with_map(
            sctx(DONCHIAN),
            H4=(MapState.UP, ()),
            H1=(MapState.UP, ()),
            M30=(MapState.DOWN, ()),
            M5=(MapState.DOWN, ()),
        )
        sig = run(
            RangeBreakout,
            ctx,
            fade_counter_trend=True,
            screen_tide_tf="M30",
            screen_wave_tf="M5",
            trend_entries=False,
        )
        assert sig.action is Action.SELL, sig.explanation


class TestScalpingParams:
    """Owner, 2026-10-14: M1 scalping sizes stops on an hour of bars and skips the US-release window."""

    def test_atr_bars_sizes_the_stop_on_that_many_bars(self) -> None:
        closes = np.full(80, 1.1000)
        ctx = _m15(sctx(DONCHIAN), closes)  # every bar spans 0.0008 (high - low)
        sig = run(RangeBreakout, ctx, atr_bars=60, stop_mode="atr", sl_atr_multiple=2.0)
        assert sig.action is Action.BUY, sig.explanation
        frame = ctx.frame(Timeframe.M15)
        prev = frame["close"].shift(1)
        tr = pd.concat(
            [frame["high"] - frame["low"], (frame["high"] - prev).abs(), (frame["low"] - prev).abs()], axis=1
        )
        expected = float(tr.max(axis=1).iloc[-60:].mean())
        assert sig.entry_price - sig.stop_loss == pytest.approx(2.0 * expected + SPREAD)

    def test_too_few_bars_hold(self) -> None:
        ctx = _m15(sctx(DONCHIAN), np.full(30, 1.1000))
        assert run(RangeBreakout, ctx, atr_bars=60).action is Action.HOLD

    def test_the_skip_window_blocks_entries_and_fades(self) -> None:
        pre_ny = datetime(2026, 9, 30, 13, 0, tzinfo=UTC)  # 09:00 New York (EDT)
        after = datetime(2026, 9, 30, 17, 0, tzinfo=UTC)  # 13:00 New York
        for at in (pre_ny, after):
            fade = _with_map(sctx(DONCHIAN, at=at), H4=(MapState.DOWN, ()), H1=(MapState.DOWN, ()))
            sig = run(
                RangeBreakout,
                fade,
                fade_counter_trend=True,
                trend_entries=False,
                skip_window_ny="08:00-12:00",
            )
            assert (sig.action is Action.SELL) is (at == after), sig.explanation


class TestResumeEntry:
    """``entry_on: resume`` (Elder's third screen; owner, 2026-10-15): enter on the first bar after the trigger
    that closes beyond the previous bar's extreme in the trade's direction."""

    @staticmethod
    def frame(closes: list[float]) -> pd.DataFrame:
        c = np.array(closes, dtype=float)
        return pd.DataFrame({"high": c + 0.5, "low": c - 0.5, "close": c})

    def test_the_first_close_above_the_previous_high_is_the_resumption(self) -> None:
        from app.strategy.setups import _resumed

        # trigger 2 bars back (a dip), then a bar inside, then a close above the previous high
        f = self.frame([100, 99, 98.8, 99.5])
        assert _resumed(f, 2, True).passed

    def test_a_close_inside_the_previous_bar_is_not_yet(self) -> None:
        from app.strategy.setups import _resumed

        assert not _resumed(self.frame([100, 99, 98.8, 98.9]), 2, True).passed

    def test_only_the_first_resumption_counts(self) -> None:
        from app.strategy.setups import _resumed

        f = self.frame([100, 99, 99.8, 100.6])  # 99.8 already closed above 99.5 (the previous high)
        assert not _resumed(f, 2, True).passed

    def test_a_sell_resumes_below_the_previous_low(self) -> None:
        from app.strategy.setups import _resumed

        assert _resumed(self.frame([100, 101, 101.2, 100.5]), 2, False).passed

    def test_the_default_enters_on_the_trigger(self) -> None:
        from app.strategy.setups import SetupParams

        p = SetupParams()
        assert p.entry_on == "trigger" and p.resume_bars == 4
