"""``example_trend_pullback``: the demonstration strategy of PLAN §A7.

DEMONSTRATION ONLY. It shows how a strategy is written, explained and tested. It is not production-proven
and makes no claim of profitability.

Rules (higher timeframe = ``timeframes.higher``, entry timeframe = ``timeframes.entry``; H1/M15 by default):

- **Bias (higher TF):** BULLISH when close > EMA(slow), EMA(mid) > EMA(slow) and ADX >= ``adx_min``; BEARISH
  mirrored; otherwise HOLD ``NO_BIAS``.
- **Regime (higher TF):** must be TRENDING, else HOLD ``REGIME_NOT_TRENDING``.
- **Entry (entry TF), shown for a BUY (SELL mirrored):**
  - pullback: a low touched EMA(fast) within the last ``pullback_bars`` bars (the signal bar included);
  - resumption: the signal bar closes above EMA(fast), and RSI is >= 50 now after being below 50 earlier in
    the pullback window (RSI crossed 50 in the bias direction);
  - room: the close is not within ``level_clearance_atr`` x ATR of the nearest resistance zone.
- **Stop and target:** SL beyond the last confirmed swing low or ``sl_atr_multiple`` x ATR below the entry,
  whichever is farther, plus the spread as a buffer; HOLD ``SL_TOO_FAR`` when that is more than
  ``max_sl_atr`` x ATR away. TP = ``rr_target`` x the risk.
- **Filters:** entry-bar close inside the ``session_*_utc`` window on weekdays; no new entries from the
  Friday cutoff; spread at most ``max_spread_to_sl`` of the SL distance. Cooldown and position limits are
  applied by the arbiter and the decision engine.

Management (break-even at +1R, trailing after +1.5R, close when the bias flips) belongs to the position
manager; :meth:`TrendPullback.bias` exposes the bias for it.

Score (a ranking heuristic, **not a probability**): ``setup_strength x (0.75 + 0.25 x min(1, (ADX - adx_min)
/ 20))``, so among complete setups a stronger higher-timeframe trend ranks first.
"""

from __future__ import annotations

import math

import pandas as pd
from pydantic import Field, model_validator

from app.core.enums import Action, Regime, Timeframe, Trend
from app.evidence.framework import Family
from app.indicators.price_action import SwingKind, find_swings
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
from app.strategy.signal_models import Condition, ReasonCode, Signal, StrategyContext


class TrendPullbackParams(EntryRuleParams):
    adx_min: float = Field(default=20.0, ge=0, le=100)
    pullback_bars: int = Field(default=3, ge=1, le=20)
    level_clearance_atr: float = Field(default=1.0, ge=0, le=10)
    sl_atr_multiple: float = Field(default=1.5, gt=0, le=10)
    swing_k: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def _coherent(self) -> TrendPullbackParams:
        if self.sl_atr_multiple > self.max_sl_atr:
            raise ValueError("sl_atr_multiple must not exceed max_sl_atr")
        return self


class TrendPullback(BaseStrategy):
    name = "example_trend_pullback"
    version = "1.0.0"
    description = "Higher-timeframe trend bias, entry-timeframe pullback to EMA(fast). Demonstration only."
    demo_only = True
    Params = TrendPullbackParams
    core_families = frozenset({Family.TREND})  # the bias conditions are EMA alignment and ADX

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return ()  # the configured higher and entry timeframes, which every context has

    def warmup_bars(self) -> int:
        return 250  # EMA(200) plus the ATR-percentile window behind the regime

    def bias(self, ctx: StrategyContext) -> Trend:
        """Higher-timeframe bias (also what the position manager watches for a flip)."""
        h = ctx.market.higher
        if not known(h.adx) or h.adx is None or h.adx < self.params.adx_min:
            return Trend.NEUTRAL
        return h.trend

    def evaluate(self, ctx: StrategyContext) -> Signal:
        p: TrendPullbackParams = self.params
        market = ctx.market
        h = market.higher
        bias = self.bias(ctx)
        conds: list[Condition] = [
            Condition(
                "htf_bias",
                bias is not Trend.NEUTRAL,
                2.0,
                f"{h.timeframe.value} trend {h.trend.value}, ADX {_f(h.adx)} (min {p.adx_min:g})",
            ),
            Condition("htf_trending", h.regime is Regime.TRENDING, 2.0, f"regime {h.regime.value}"),
        ]
        if bias is Trend.NEUTRAL:
            return self.hold(ctx, ReasonCode.NO_BIAS, conditions=conds, explanation=explain(conds))
        if h.regime is not Regime.TRENDING:
            return self.hold(
                ctx, ReasonCode.REGIME_NOT_TRENDING, conditions=conds, explanation=explain(conds)
            )

        frame = ctx.frame(market.entry_timeframe)
        n = p.pullback_bars
        if len(frame) < max(n + 1, p.swing_k * 2 + 1):
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds)
        window = frame.iloc[-n:]
        before = frame.iloc[-n - 1 : -1]
        last = frame.iloc[-1]
        close, ema_fast, atr_v, rsi_now = (float(last[c]) for c in ("close", "ema_fast", "atr", "rsi"))
        if not known(close, ema_fast, atr_v, rsi_now) or atr_v <= 0 or window["ema_fast"].isna().any():
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds)

        buy = bias is Trend.BULLISH
        sign = 1 if buy else -1
        touched = bool(
            (window["low"] <= window["ema_fast"]).any()
            if buy
            else (window["high"] >= window["ema_fast"]).any()
        )
        beyond = close > ema_fast if buy else close < ema_fast
        rsi_before = before["rsi"].to_numpy(dtype=float)
        crossed = bool(
            (rsi_now >= 50 and (rsi_before < 50).any())
            if buy
            else (rsi_now <= 50 and (rsi_before > 50).any())
        )
        opposing = market.resistance_levels if buy else market.support_levels
        nearest = min((abs(lv - close) for lv in opposing), default=math.inf)
        room = nearest > p.level_clearance_atr * atr_v
        conds += [
            Condition("pullback_to_ema", touched, 1.0, f"touched EMA{_side(buy)} within {n} bars"),
            Condition("close_beyond_ema", beyond, 1.0, f"close {close:.5f} vs EMA {ema_fast:.5f}"),
            Condition("rsi_cross_50", crossed, 1.0, f"RSI {rsi_now:.1f}"),
            Condition(
                "clear_of_opposing_level",
                room,
                1.0,
                "no opposing zone"
                if math.isinf(nearest)
                else f"nearest opposing zone {nearest / atr_v:.2f} ATR",
            ),
        ]

        # stop, target and costs
        costs = spread_price(ctx, last)
        if costs is None:
            return self.hold(
                ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds, explanation="spread or point unknown"
            )
        spread_points, spread = costs
        entry = entry_price(market, close, spread, buy)
        swing = self._last_swing(frame, buy, entry)
        atr_stop = entry - sign * p.sl_atr_multiple * atr_v
        base_stop = atr_stop if swing is None else (min(swing, atr_stop) if buy else max(swing, atr_stop))
        stop = base_stop - sign * spread
        take_profit = entry + sign * p.rr_target * abs(entry - stop)
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

        if not all(c.passed for c in conds):
            reasons = failed_reasons(conds, _REASON)
            return self.hold(ctx, *reasons, conditions=conds, explanation=explain(conds))
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=entry,
            stop_loss=stop,
            take_profit=take_profit,
            conditions=conds,
            score=self._score(conds, h.adx),
            reasons=("TREND_PULLBACK",),
            explanation=explain(conds),
        )

    # helpers -------------------------------------------------------------------------------------------

    def _last_swing(self, frame: pd.DataFrame, buy: bool, entry: float) -> float | None:
        """Price of the latest confirmed swing low below (BUY) / swing high above (SELL) the entry."""
        kind = SwingKind.LOW if buy else SwingKind.HIGH
        for s in reversed(find_swings(frame["high"], frame["low"], self.params.swing_k)):
            if s.kind is kind and ((s.price < entry) if buy else (s.price > entry)):
                return s.price
        return None

    def _score(self, conds: list[Condition], adx_value: float | None) -> float:
        total = sum(c.weight for c in conds)
        strength = 100.0 * sum(c.weight for c in conds if c.passed) / total
        excess = 0.0 if adx_value is None else max(0.0, min(1.0, (adx_value - self.params.adx_min) / 20.0))
        return strength * (0.75 + 0.25 * excess)


_REASON: dict[str, ReasonCode] = {
    "htf_bias": ReasonCode.NO_BIAS,
    "htf_trending": ReasonCode.REGIME_NOT_TRENDING,
    "clear_of_opposing_level": ReasonCode.NEAR_OPPOSING_LEVEL,
}  # the setup conditions map to NO_SETUP; the shared rules carry their own codes


def _f(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _side(buy: bool) -> str:
    return " from above" if buy else " from below"
