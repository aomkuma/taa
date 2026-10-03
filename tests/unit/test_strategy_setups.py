from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
        assert len(STRATEGIES) == 1 + len(SETUPS)

    def test_config_yaml_lists_every_setup_disabled(self) -> None:
        settings = load_settings(
            env_file=None, config_file="config.yaml", environ={"TRADING_MODE": "BACKTEST"}
        )
        listed = {item.name: item.enabled for item in settings.config.strategies.items}
        assert listed == {"example_trend_pullback": True, **{cls.name: False for cls in SETUPS}}

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
