"""H4 confirmed-swing range breaks on M5 closes."""

from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import Field

from app.core.enums import Action, Side, Timeframe
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)
from app.strategy.trend_box import break_even_advice, in_window, running_push_exceeded, stepped
from app.strategy.zigzag import zigzag

BANGKOK = ZoneInfo("Asia/Bangkok")


class RangeBreakParams(StrategyParams):
    """Measured breakout plan constants."""

    buffer: float = Field(default=0.3, ge=0, le=2)
    tp_range: float = Field(default=0.5, gt=0, le=5)
    min_r: float = Field(default=0.8, gt=0, le=10)
    # Owner 2026-10-27: "you can take the 5 USD out". Measured first (research/.../gate_bite.py): the
    # 5.00 USD floor rejected 1 of 496 complete signals, because every target here is a swing or half an
    # H4 box. The gate stays so a lane can set one; 0.0 is off.
    min_take_profit: float = Field(default=0.0, ge=0)


class RangeBreak(BaseStrategy):
    name = "range_break"
    Params = RangeBreakParams

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return Timeframe.M1, Timeframe.M5, Timeframe.H1

    def warmup_bars(self) -> int:
        # H1 bars, not H4: the 300 H4 bars the box is read from are resampled from 1,200 closed H1 bars.
        # Declaring 300 here would let a lane configure 300 H1 bars, give the ZigZag 75 H4 bars instead of
        # 300, and change the box silently (found in review, 2026-10-27).
        return 1200

    @staticmethod
    def _h4_from_h1(h1: pd.DataFrame) -> pd.DataFrame:
        # App frames are indexed by H1 close; the research resamples bars indexed by H1 open.
        opens = h1.copy()
        opens.index = pd.DatetimeIndex(opens.index) - pd.Timedelta(hours=1)
        return (
            opens.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        )

    def evaluate(self, ctx: StrategyContext) -> Signal:
        at = pd.Timestamp(ctx.decision_time_utc)
        m5, m1 = ctx.frame(Timeframe.M5), ctx.frame(Timeframe.M1)
        h1 = ctx.frame(Timeframe.H1).iloc[-1200:]
        h4 = self._h4_from_h1(h1)
        h4 = h4[(h4.index + pd.Timedelta(hours=4)) <= at].iloc[-300:]
        if len(h4) < 300 or len(m5) < 2 or not len(m1):
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA)
        if not in_window(at):
            return self.hold(ctx, ReasonCode.OUTSIDE_SESSION)
        swings, _forming = zigzag(h4.high.to_numpy(float), h4.low.to_numpy(float))
        highs = [s.price for s in swings if s.kind == 1]
        lows = [s.price for s in swings if s.kind == -1]
        if stepped(swings) != "FLAT" or not highs or not lows:
            return self.hold(ctx, "H4_STEPPING")
        hh, ll = highs[-1], lows[-1]
        if hh <= ll:
            return self.hold(ctx, "INVALID_H4_BOX")
        prev, price = float(m5.close.iloc[-2]), float(m5.close.iloc[-1])
        rng = hh - ll
        if price > hh >= prev:
            side, stop, target = (
                Side.BUY,
                hh - self.params.buffer * rng * 0.25,
                price + self.params.tp_range * rng,
            )
        elif price < ll <= prev:
            side, stop, target = (
                Side.SELL,
                ll + self.params.buffer * rng * 0.25,
                price - self.params.tp_range * rng,
            )
        else:
            return self.hold(ctx, "NO_CLOSE_BREAK")
        risk, reward = abs(stop - price), abs(target - price)
        if risk <= 0 or reward < self.params.min_take_profit or reward < self.params.min_r * risk:
            return self.hold(ctx, ReasonCode.RR_TOO_LOW)
        run_frame = m1[(m1.index >= at - pd.Timedelta(minutes=60)) & (m1.index < at)]
        if run_frame.empty:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA)
        run = float(run_frame.high.max()) - price if side is Side.BUY else price - float(run_frame.low.min())
        if running_push_exceeded(run, risk):
            return self.hold(ctx, "RUNNING_PUSH")
        return self.entry(
            ctx,
            Action.BUY if side is Side.BUY else Action.SELL,
            entry_price=price,
            stop_loss=stop,
            take_profit=target,
            conditions=(
                Condition("h4_flat", True),
                Condition("range_break", True),
                Condition("run_gate", True),
            ),
            score=80,
            explanation="confirmed H4 range break",
        )

    def should_close(self, ctx: StrategyContext, side: Side) -> bool:
        return pd.Timestamp(ctx.decision_time_utc).tz_convert(BANGKOK).time() == time(7)

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        return break_even_advice(ctx, pos)
