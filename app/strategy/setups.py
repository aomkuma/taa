"""Pattern-based setup generators (PLAN §A29 use 2, TAA-306). DEMONSTRATION ONLY: unproven, no profit claim.

Each setup turns one *trigger* detector's evidence on the entry timeframe into an explicit trade plan:

- **Trigger:** an active, directional evidence item of the setup's detectors, fired on the decision
  bar (``trigger_max_age_bars`` 0 by default), at or above ``min_quality``. Triggers in both directions on
  the same bar mean HOLD ``CONFLICT``. Among same-direction triggers the best quality wins.
- **Entry:** market, at the live ask/bid (or the bid-based close plus the spread for a BUY).
- **Stop** (``stop_mode``):
  - ``invalidation``: beyond the trigger's invalidation level (or the setup's own reference, e.g. the
    sweep extreme for SMC) by ``stop_buffer_atr`` × ATR;
  - ``atr``: ``sl_atr_multiple`` × ATR from the entry;
  - ``nearer``: whichever of the two is closer to the entry.

  An invalidation on the wrong side of the entry falls back to the ATR stop. The spread is added as a
  buffer in every mode.
- **Target** (``target_mode``):
  - ``measured``: the nearest of the trigger's targets beyond the entry that gives at least ``min_rr``
    (else the farthest, which then fails the RR check);
  - ``level``: the nearest opposing S/R zone of the context, under the same rule;
  - ``rr``: ``rr_target`` × the risk. Measured or level modes without a usable price fall back to it.
- **Rules:** the shared checks of :mod:`app.strategy.rules` (SL ≤ ``max_sl_atr`` ATR, RR ≥ ``min_rr``,
  spread ≤ ``max_spread_to_sl`` of the SL, session window, Friday cutoff), plus each setup's confirmations.

Score (ranking only, **not a probability**): ``setup_strength × (0.5 + 0.5 × trigger quality)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Literal

from pydantic import Field

from app.core.enums import Action, Timeframe, Trend
from app.evidence.framework import ActiveEvidence, Direction, Evidence, Family
from app.strategy.base_strategy import BaseStrategy
from app.strategy.rules import (
    EntryRuleParams,
    entry_price,
    explain,
    failed_reasons,
    known,
    risk_conditions,
    spread_price,
    time_conditions,
)
from app.strategy.signal_models import Condition, MarketContext, ReasonCode, Signal, StrategyContext

StopMode = Literal["invalidation", "atr", "nearer"]
TargetMode = Literal["measured", "level", "rr"]


class SetupParams(EntryRuleParams):
    trigger_max_age_bars: int = Field(default=0, ge=0, le=20, description="0: fired on the decision bar")
    min_quality: float = Field(default=0.0, ge=0, le=1)
    stop_mode: StopMode = "invalidation"
    target_mode: TargetMode = "measured"
    stop_buffer_atr: float = Field(default=0.1, ge=0, le=2)
    sl_atr_multiple: float = Field(default=1.5, gt=0, le=10)
    require_htf_alignment: bool = False
    confirm_window_bars: int = Field(default=30, ge=1, le=200)


def variant(ev: Evidence) -> str:
    """The variant suffix of an evidence record (``evidence.<detector>.<variant>``), or ``""``."""
    prefix = f"evidence.{ev.detector_id}"
    return ev.i18n_key[len(prefix) + 1 :] if ev.i18n_key.startswith(prefix + ".") else ""


def _sign(direction: Direction) -> int:
    return direction.sign


class EvidenceSetup(BaseStrategy):
    """A strategy driven by one family of trigger detectors. Subclasses set the class attributes."""

    triggers: ClassVar[frozenset[str]]
    confirming: ClassVar[frozenset[str]] = frozenset()  # other detectors the confirmations read
    setup_code: ClassVar[str]  # the entry's reason code, e.g. NECKLINE_BREAK
    Params = SetupParams
    demo_only = True

    def required_detectors(self) -> frozenset[str]:
        return self.triggers | self.confirming

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return ()

    def warmup_bars(self) -> int:
        return 120  # zigzag pivots and the evidence detectors' own windows

    # hooks ---------------------------------------------------------------------------------------------

    def accepts(self, ev: Evidence) -> bool:
        """Extra trigger filter (variants, primary counts, ...)."""
        return True

    def confirmations(
        self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence], ctx: StrategyContext
    ) -> list[Condition]:
        return []

    def stop_reference(self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence]) -> float | None:
        return trigger.evidence.invalidation

    # evaluation ----------------------------------------------------------------------------------------

    def evaluate(self, ctx: StrategyContext) -> Signal:
        p: SetupParams = self.params
        market = ctx.market
        snapshot = ctx.evidence.get(market.entry_timeframe)
        if snapshot is None:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, explanation="evidence was not computed")
        items = snapshot.items
        found = [
            a
            for a in items
            if a.evidence.detector_id in self.triggers
            and a.age_bars <= p.trigger_max_age_bars
            and a.evidence.direction is not Direction.NEUTRAL
            and a.evidence.quality >= p.min_quality
            and self.accepts(a.evidence)
        ]
        if not found:
            cond = Condition("trigger", False, 2.0, f"no {self.setup_code} trigger")
            return self.hold(ctx, ReasonCode.NO_SETUP, conditions=[cond], explanation=explain([cond]))
        if len({a.evidence.direction for a in found}) > 1:
            cond = Condition("trigger", False, 2.0, "triggers in both directions")
            return self.hold(ctx, ReasonCode.CONFLICT, conditions=[cond], explanation=explain([cond]))
        trigger = min(found, key=lambda a: (-a.evidence.quality, a.age_bars, a.evidence.detector_id))
        ev = trigger.evidence
        buy = ev.direction is Direction.BULL
        sign = _sign(ev.direction)
        conds = [Condition("trigger", True, 2.0, f"{ev.name} (quality {ev.quality:.2f})")]
        if p.require_htf_alignment:
            opposed = Trend.BEARISH if buy else Trend.BULLISH
            h = market.higher
            conds.append(
                Condition(
                    "htf_not_opposed", h.trend is not opposed, 1.0, f"{h.timeframe.value} {h.trend.value}"
                )
            )
        conds += self.confirmations(trigger, items, ctx)

        frame = ctx.frame(market.entry_timeframe)
        if frame.empty:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds)
        last = frame.iloc[-1]
        close, atr_v = float(last["close"]), float(last["atr"])
        costs = spread_price(ctx, last)
        if not known(close, atr_v) or atr_v <= 0 or costs is None:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds, explanation=explain(conds))
        spread_points, spread = costs
        entry = entry_price(market, close, spread, buy)
        stop, stop_note = self._stop(trigger, items, entry, atr_v, sign)
        stop -= sign * spread
        risk = abs(entry - stop)
        take_profit, target_note = self._target(ev, market, entry, risk, sign)
        conds += risk_conditions(
            entry=entry,
            stop=stop,
            take_profit=take_profit,
            atr=atr_v,
            spread=spread,
            spread_points=spread_points,
            p=p,
        )
        conds += time_conditions(market.decision_time_utc, p)
        conds.append(Condition("plan", True, 1.0, f"stop {stop_note}; target {target_note}"))

        if not all(c.passed for c in conds):
            reasons = failed_reasons(conds, {"htf_not_opposed": ReasonCode.CONFLICT})
            return self.hold(ctx, *reasons, conditions=conds, explanation=explain(conds))
        total = sum(c.weight for c in conds)
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=entry,
            stop_loss=stop,
            take_profit=take_profit,
            conditions=conds,
            score=100.0 * sum(c.weight for c in conds if c.passed) / total * (0.5 + 0.5 * ev.quality),
            reasons=(self.setup_code,),
            explanation=explain(conds),
        )

    def _stop(
        self,
        trigger: ActiveEvidence,
        items: Sequence[ActiveEvidence],
        entry: float,
        atr_v: float,
        sign: int,
    ) -> tuple[float, str]:
        p: SetupParams = self.params
        atr_stop = entry - sign * p.sl_atr_multiple * atr_v
        ref = self.stop_reference(trigger, items)
        usable = ref is not None and (entry - ref) * sign > 0
        if p.stop_mode == "atr" or not usable or ref is None:
            note = f"{p.sl_atr_multiple:g} ATR" + (
                "" if p.stop_mode == "atr" else " (no usable invalidation)"
            )
            return atr_stop, note
        inv_stop = ref - sign * p.stop_buffer_atr * atr_v
        if p.stop_mode == "nearer" and (atr_stop - inv_stop) * sign > 0:
            return atr_stop, f"{p.sl_atr_multiple:g} ATR (nearer than the invalidation {ref:.5g})"
        return inv_stop, f"beyond the invalidation {ref:.5g}"

    def _target(
        self, ev: Evidence, market: MarketContext, entry: float, risk: float, sign: int
    ) -> tuple[float, str]:
        p: SetupParams = self.params
        rr_tp = entry + sign * p.rr_target * risk
        if p.target_mode == "rr" or risk <= 0:
            return rr_tp, f"{p.rr_target:g}R"
        if p.target_mode == "measured":
            prices, label = list(ev.targets), "measured target"
        else:
            prices = list(market.resistance_levels if sign > 0 else market.support_levels)
            label = "next opposing level"
        ahead = sorted((t for t in prices if (t - entry) * sign > 0), key=lambda t: abs(t - entry))
        if not ahead:
            return rr_tp, f"{p.rr_target:g}R (no {label} ahead)"
        for t in ahead:
            if abs(t - entry) / risk >= p.min_rr:
                return t, f"{label} {t:.5g}"
        return ahead[-1], f"{label} {ahead[-1]:.5g}"


def _confirmed_by(
    items: Sequence[ActiveEvidence],
    detector: str,
    direction: Direction,
    window: int,
    variant_name: str | None = None,
) -> ActiveEvidence | None:
    """The most recent same-direction item of *detector* within *window* bars, if any."""
    matches = [
        a
        for a in items
        if a.evidence.detector_id == detector
        and a.evidence.direction is direction
        and a.age_bars <= window
        and (variant_name is None or variant(a.evidence) == variant_name)
    ]
    return min(matches, key=lambda a: a.age_bars) if matches else None


# --- the setups (PLAN §A29 table) -------------------------------------------------------------------------


class NecklineParams(SetupParams):
    # beyond the pattern extreme a measured move gives RR < 1, so the default takes the nearer stop
    stop_mode: StopMode = "nearer"


class NecklineBreak(EvidenceSetup):
    name = "setup_neckline_break"
    description = "M/W, triple tops/bottoms and head & shoulders: neckline-break close. Unproven."
    setup_code = "NECKLINE_BREAK"
    triggers = frozenset({"chart.double", "chart.triple", "chart.head_shoulders"})
    core_families = frozenset({Family.CHART_PATTERN})
    Params = NecklineParams


class PatternBreakout(EvidenceSetup):
    name = "setup_pattern_breakout"
    description = "Triangle, wedge, rectangle, flag/pennant and cup & handle boundary breaks. Unproven."
    setup_code = "PATTERN_BREAKOUT"
    triggers = frozenset(
        {"chart.triangle", "chart.wedge", "chart.rectangle", "chart.flag", "chart.cup_handle"}
    )
    core_families = frozenset({Family.CHART_PATTERN})
    Params = NecklineParams


class FibPullbackParams(SetupParams):
    require_htf_alignment: bool = True  # a continuation trade needs a trend that is at least not against it


class FibPullback(EvidenceSetup):
    name = "setup_fib_pullback"
    description = "Fibonacci golden-zone (50–61.8 %) rejection in the impulse direction. Unproven."
    setup_code = "FIB_PULLBACK"
    triggers = frozenset({"fib.golden_zone"})
    core_families = frozenset({Family.FIBONACCI})
    Params = FibPullbackParams


class HarmonicPrz(EvidenceSetup):
    name = "setup_harmonic_prz"
    description = "Harmonic XABCD completion: reversal at the PRZ, targets 38.2/61.8 % of AD. Unproven."
    setup_code = "HARMONIC_PRZ"
    triggers = frozenset(
        {
            "harmonic.gartley",
            "harmonic.bat",
            "harmonic.butterfly",
            "harmonic.crab",
            "harmonic.cypher",
            "harmonic.shark",
            "harmonic.abcd",
        }
    )
    core_families = frozenset({Family.HARMONIC})


class ElliottWave(EvidenceSetup):
    name = "setup_elliott_wave"
    description = "Possible wave 3 / wave 5 start of the primary (heuristic) count. Unproven."
    setup_code = "ELLIOTT_WAVE"
    triggers = frozenset({"elliott.wave"})
    core_families = frozenset({Family.ELLIOTT})

    def accepts(self, ev: Evidence) -> bool:
        return variant(ev) in {"wave3", "wave5"} and ev.detail("count") == "primary"


class SmcParams(SetupParams):
    target_mode: TargetMode = "level"  # the opposite liquidity: the nearest opposing zone


class SmcReversal(EvidenceSetup):
    """Liquidity sweep, then a change of character, then a fair-value-gap retest, all the same way."""

    name = "setup_smc_reversal"
    description = "Smart money: sweep + CHoCH + FVG retest; stop beyond the sweep extreme. Unproven."
    setup_code = "SMC_REVERSAL"
    triggers = frozenset({"smc.fvg"})
    confirming = frozenset({"smc.liquidity_sweep", "structure.bos_choch"})
    core_families = frozenset({Family.SMART_MONEY, Family.TREND})
    Params = SmcParams

    def confirmations(
        self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence], ctx: StrategyContext
    ) -> list[Condition]:
        window = self.params.confirm_window_bars
        direction = trigger.evidence.direction
        sweep = _confirmed_by(items, "smc.liquidity_sweep", direction, window)
        choch = _confirmed_by(items, "structure.bos_choch", direction, window, "choch")
        return [
            Condition(
                "liquidity_sweep",
                sweep is not None,
                1.0,
                "no sweep" if sweep is None else f"swept {sweep.age_bars} bars ago",
            ),
            Condition(
                "change_of_character",
                choch is not None,
                1.0,
                "no CHoCH" if choch is None else f"CHoCH {choch.age_bars} bars ago",
            ),
        ]

    def stop_reference(self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence]) -> float | None:
        sweep = _confirmed_by(
            items, "smc.liquidity_sweep", trigger.evidence.direction, self.params.confirm_window_bars
        )
        return None if sweep is None else sweep.evidence.invalidation


class BreakoutParams(SetupParams):
    stop_mode: StopMode = "nearer"  # Donchian's invalidation is the channel middle, often far away


class RangeBreakout(EvidenceSetup):
    name = "setup_breakout"
    description = "Donchian channel and Asian / London / New York opening-range breakouts. Unproven."
    setup_code = "RANGE_BREAKOUT"
    triggers = frozenset({"volatility.donchian", "sessions.asian_breakout", "sessions.open_breakout"})
    core_families = frozenset({Family.VOLATILITY_VOLUME, Family.SESSIONS})
    Params = BreakoutParams


class CandleParams(SetupParams):
    target_mode: TargetMode = "level"  # the next level


class CandleReversal(EvidenceSetup):
    """A directional reversal candle that sits on a level (``at_level``), stop beyond the candle extreme."""

    name = "setup_candle_reversal"
    description = "Reversal candlestick at a level (S/R, Fibonacci, pivots, trendline). Unproven."
    setup_code = "CANDLE_REVERSAL"
    triggers = frozenset(
        {
            "candle.engulfing",
            "candle.hammer",
            "candle.shooting_star",
            "candle.doji",
            "candle.inside_outside",
            "candle.star",
            "candle.harami",
            "candle.tweezer",
        }
    )
    core_families = frozenset({Family.CANDLESTICK})
    Params = CandleParams

    def confirmations(
        self, trigger: ActiveEvidence, items: Sequence[ActiveEvidence], ctx: StrategyContext
    ) -> list[Condition]:
        levels = str(trigger.evidence.detail("at_levels", "") or "")
        at_level = bool(trigger.evidence.detail("at_level", False))
        return [
            Condition("at_level", at_level, 1.0, levels.replace(",", ", ") if at_level else "not at a level")
        ]


SETUPS: tuple[type[EvidenceSetup], ...] = (
    NecklineBreak,
    PatternBreakout,
    FibPullback,
    HarmonicPrz,
    ElliottWave,
    SmcReversal,
    RangeBreakout,
    CandleReversal,
)
