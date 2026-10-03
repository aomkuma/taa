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
from datetime import datetime, time

import pandas as pd
from pydantic import Field, field_validator, model_validator

from app.core.enums import Action, Regime, Timeframe, Trend
from app.evidence.framework import Family
from app.indicators.price_action import SwingKind, find_swings
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.signal_models import Condition, ReasonCode, Signal, StrategyContext


def _hhmm(value: str) -> time:
    hours, _, minutes = value.partition(":")
    return time(int(hours), int(minutes))


class TrendPullbackParams(StrategyParams):
    adx_min: float = Field(default=20.0, ge=0, le=100)
    pullback_bars: int = Field(default=3, ge=1, le=20)
    level_clearance_atr: float = Field(default=1.0, ge=0, le=10)
    sl_atr_multiple: float = Field(default=1.5, gt=0, le=10)
    max_sl_atr: float = Field(default=3.0, gt=0, le=20)
    rr_target: float = Field(default=2.0, gt=0, le=10)
    min_rr: float = Field(default=1.5, gt=0, le=10)
    max_spread_to_sl: float = Field(default=0.15, gt=0, le=1)
    session_start_utc: str = "07:00"
    session_end_utc: str = "20:00"
    friday_cutoff_utc: str | None = "20:00"
    swing_k: int = Field(default=3, ge=1, le=20)

    @field_validator("session_start_utc", "session_end_utc", "friday_cutoff_utc")
    @classmethod
    def _check_hhmm(cls, value: str | None) -> str | None:
        if value is not None:
            _hhmm(value)
        return value

    @model_validator(mode="after")
    def _coherent(self) -> TrendPullbackParams:
        if self.rr_target < self.min_rr:
            raise ValueError("rr_target must be >= min_rr")
        if self.sl_atr_multiple > self.max_sl_atr:
            raise ValueError("sl_atr_multiple must not exceed max_sl_atr")
        if _hhmm(self.session_start_utc) >= _hhmm(self.session_end_utc):
            raise ValueError("session_start_utc must be before session_end_utc")
        return self


def _known(*values: float | None) -> bool:
    return all(v is not None and math.isfinite(v) for v in values)


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
        if not _known(h.adx) or h.adx is None or h.adx < self.params.adx_min:
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
            return self.hold(ctx, ReasonCode.NO_BIAS, conditions=conds, explanation=_explain(conds))
        if h.regime is not Regime.TRENDING:
            return self.hold(
                ctx, ReasonCode.REGIME_NOT_TRENDING, conditions=conds, explanation=_explain(conds)
            )

        frame = ctx.frame(market.entry_timeframe)
        n = p.pullback_bars
        if len(frame) < max(n + 1, p.swing_k * 2 + 1):
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds)
        window = frame.iloc[-n:]
        before = frame.iloc[-n - 1 : -1]
        last = frame.iloc[-1]
        close, ema_fast, atr_v, rsi_now = (float(last[c]) for c in ("close", "ema_fast", "atr", "rsi"))
        if not _known(close, ema_fast, atr_v, rsi_now) or atr_v <= 0 or window["ema_fast"].isna().any():
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
        spread_points = market.spread_points if market.spread_points is not None else _opt(last.get("spread"))
        point = ctx.spec.point if ctx.spec is not None else None
        if spread_points is None or point is None:
            return self.hold(
                ctx, ReasonCode.INSUFFICIENT_DATA, conditions=conds, explanation="spread or point unknown"
            )
        spread = spread_points * point
        quoted = market.ask if buy else market.bid
        # bars are bid-based: without a live quote a BUY pays the spread on top of the close
        entry = quoted if quoted is not None else (close + spread if buy else close)
        swing = self._last_swing(frame, buy, entry)
        atr_stop = entry - sign * p.sl_atr_multiple * atr_v
        base_stop = atr_stop if swing is None else (min(swing, atr_stop) if buy else max(swing, atr_stop))
        stop = base_stop - sign * spread
        risk = abs(entry - stop)
        take_profit = entry + sign * p.rr_target * risk
        rr = abs(take_profit - entry) / risk if risk > 0 else 0.0
        conds += [
            Condition(
                "sl_within_limit",
                risk <= p.max_sl_atr * atr_v,
                1.0,
                f"SL {risk / atr_v:.2f} ATR (max {p.max_sl_atr:g})",
            ),
            Condition("rr_ok", rr >= p.min_rr, 1.0, f"RR {rr:.2f} (min {p.min_rr:g})"),
            Condition(
                "spread_ok",
                risk > 0 and spread <= p.max_spread_to_sl * risk,
                1.0,
                f"spread {spread_points:g} pts = {spread / risk:.0%} of SL" if risk > 0 else "zero risk",
            ),
        ]
        conds += self._time_conditions(market.decision_time_utc)

        failed = [c for c in conds if not c.passed]
        if failed:
            reasons = dict.fromkeys(_REASON[c.name] for c in failed)  # ordered, without repeats
            return self.hold(ctx, *reasons, conditions=conds, explanation=_explain(conds))
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=entry,
            stop_loss=stop,
            take_profit=take_profit,
            conditions=conds,
            score=self._score(conds, h.adx),
            reasons=("TREND_PULLBACK",),
            explanation=_explain(conds),
        )

    # helpers -------------------------------------------------------------------------------------------

    def _last_swing(self, frame: pd.DataFrame, buy: bool, entry: float) -> float | None:
        """Price of the latest confirmed swing low below (BUY) / swing high above (SELL) the entry."""
        kind = SwingKind.LOW if buy else SwingKind.HIGH
        for s in reversed(find_swings(frame["high"], frame["low"], self.params.swing_k)):
            if s.kind is kind and ((s.price < entry) if buy else (s.price > entry)):
                return s.price
        return None

    def _time_conditions(self, at: datetime) -> list[Condition]:
        p: TrendPullbackParams = self.params
        now = at.time()
        weekday = at.weekday()
        in_session = weekday < 5 and _hhmm(p.session_start_utc) <= now <= _hhmm(p.session_end_utc)
        cutoff = p.friday_cutoff_utc is not None and (
            weekday > 4 or (weekday == 4 and now >= _hhmm(p.friday_cutoff_utc))
        )
        return [
            Condition("session_window", in_session, 1.0, f"{at:%a %H:%M} UTC"),
            Condition("before_friday_cutoff", not cutoff, 1.0, f"cutoff {p.friday_cutoff_utc} UTC Friday"),
        ]

    def _score(self, conds: list[Condition], adx_value: float | None) -> float:
        total = sum(c.weight for c in conds)
        strength = 100.0 * sum(c.weight for c in conds if c.passed) / total
        excess = 0.0 if adx_value is None else max(0.0, min(1.0, (adx_value - self.params.adx_min) / 20.0))
        return strength * (0.75 + 0.25 * excess)


_REASON: dict[str, ReasonCode] = {
    "htf_bias": ReasonCode.NO_BIAS,
    "htf_trending": ReasonCode.REGIME_NOT_TRENDING,
    "pullback_to_ema": ReasonCode.NO_SETUP,
    "close_beyond_ema": ReasonCode.NO_SETUP,
    "rsi_cross_50": ReasonCode.NO_SETUP,
    "clear_of_opposing_level": ReasonCode.NEAR_OPPOSING_LEVEL,
    "sl_within_limit": ReasonCode.SL_TOO_FAR,
    "rr_ok": ReasonCode.RR_TOO_LOW,
    "spread_ok": ReasonCode.SPREAD_TOO_HIGH,
    "session_window": ReasonCode.OUTSIDE_SESSION,
    "before_friday_cutoff": ReasonCode.FRIDAY_CUTOFF,
}


def _explain(conds: list[Condition]) -> str:
    """One line per checklist item: ``[x]`` passed, ``[ ]`` failed, with the measured value."""
    return "; ".join(f"[{'x' if c.passed else ' '}] {c.name}: {c.detail}" for c in conds)


def _f(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _opt(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _side(buy: bool) -> str:
    return " from above" if buy else " from below"
