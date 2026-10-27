"""Confirmed-swing trend pullbacks with a closed M5 range break."""

from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import Field

from app.core.enums import Action, ExitReason, Side, Timeframe
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)
from app.strategy.zigzag import Swing, zigzag

BANGKOK = ZoneInfo("Asia/Bangkok")
NEW_YORK = ZoneInfo("America/New_York")


class TrendBoxParams(StrategyParams):
    """Measured constants shared by the two trend directions."""

    buffer: float = Field(default=0.20, ge=0, le=2)
    min_r: float = Field(default=1.2, gt=0, le=10)
    # Owner 2026-10-27: "you can take the 5 USD out". Measured first (research/.../gate_bite.py): the
    # 5.00 USD floor rejected 1 of 496 complete signals, because every target here is a swing or half an
    # H4 box. The gate stays so a lane can set one; 0.0 is off.
    min_take_profit: float = Field(default=0.0, ge=0)
    # The measured default differs per direction, so each subclass sets its own; a lever either way
    # (journal 2026-10-27: a down trade reached +1.40 R and still stopped out at -1.01 R).
    break_even: bool = False


class TrendBoxDownParams(TrendBoxParams):
    box: float = Field(default=0.20, gt=0, le=1)


class TrendBoxUpParams(TrendBoxParams):
    box: float = Field(default=0.33, gt=0, le=1)
    break_even: bool = True


def in_window(at: pd.Timestamp) -> bool:
    """Research windows use a start-exclusive, end-inclusive close timestamp."""
    utc = at.tz_convert("UTC")
    bangkok = utc.tz_convert(BANGKOK)
    new_york = utc.tz_convert(NEW_YORK)
    bt, nt = bangkok.time(), new_york.time()
    return (time(7) < bt <= time(9)) or (time(13) < bt <= time(15)) or (time(8) < nt <= time(11, 30))


def stepped(swings: list[Swing]) -> str:
    highs = [s.price for s in swings if s.kind == 1]
    lows = [s.price for s in swings if s.kind == -1]
    if len(highs) < 2 or len(lows) < 2:
        return "FLAT"
    if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
        return "DOWN"
    if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
        return "UP"
    return "FLAT"


def running_push_exceeded(run: float, risk: float) -> bool:
    """Apply the measured strict 1.2 R cutoff to the preceding M1 run."""
    return run > 1.2 * risk


def break_even_advice(ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
    """Replay closed M1 bars so a stop crossed before a threshold touch keeps precedence."""
    if (pos.side is Side.BUY and pos.sl >= pos.entry) or (pos.side is Side.SELL and pos.sl <= pos.entry):
        return None
    m1 = ctx.frame(Timeframe.M1)
    bars = m1[(m1.index >= pd.Timestamp(pos.entry_time)) & (m1.index <= pd.Timestamp(ctx.decision_time_utc))]
    risk = abs(pos.initial_sl - pos.entry)
    if risk <= 0 or bars.empty:
        return None
    sell = pos.side is Side.SELL
    stop = pos.sl
    moved = False
    highs = bars["high"].to_numpy(dtype=float)
    lows = bars["low"].to_numpy(dtype=float)
    for high, low in zip(highs, lows, strict=True):
        if (high >= stop) if sell else (low <= stop):
            return None
        if pos.tp is not None and ((low <= pos.tp) if sell else (high >= pos.tp)):
            return None
        ahead = pos.entry - low if sell else high - pos.entry
        if ahead >= 0.5 * risk:
            stop = pos.entry
            moved = True
    if not moved:
        return None
    return PositionAdvice(new_sl=pos.entry, stop_kind=ExitReason.BREAK_EVEN, note="+0.5 R touched")


class TrendBox(BaseStrategy):
    """Shared confirmed H1 swing, M5 box and running-push gates."""

    Params = TrendBoxParams
    direction: str

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return Timeframe.M1, Timeframe.M5, Timeframe.H1

    def warmup_bars(self) -> int:
        return 400

    def evaluate(self, ctx: StrategyContext) -> Signal:
        at = pd.Timestamp(ctx.decision_time_utc)
        h1 = ctx.frame(Timeframe.H1).iloc[-400:]
        m5 = ctx.frame(Timeframe.M5)
        m1 = ctx.frame(Timeframe.M1)
        if len(h1) < 400 or len(m5) < 25 or not len(m1):
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA)
        if not in_window(at):
            return self.hold(ctx, ReasonCode.OUTSIDE_SESSION)
        swings, _forming = zigzag(h1.high.to_numpy(float), h1.low.to_numpy(float))
        highs = [s for s in swings if s.kind == 1]
        lows = [s for s in swings if s.kind == -1]
        down = self.direction == "DOWN"
        stepping = (
            len(highs) >= 2
            and len(lows) >= 2
            and (
                (highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price)
                if down
                else (highs[-1].price > highs[-2].price and lows[-1].price > lows[-2].price)
            )
        )
        if not stepping or len(swings) < 2:
            return self.hold(ctx, "TREND_STEPPING")
        a, b = swings[-2:]
        if (a.kind, b.kind) != ((1, -1) if down else (-1, 1)):
            return self.hold(ctx, "LEG_ORDER")
        leg = abs(a.price - b.price)
        if leg <= 0:
            return self.hold(ctx, "ZERO_LEG")
        decision = m5.iloc[-1]
        price = float(decision.close)
        selected: tuple[int, float, float] | None = None
        for n in range(24, 5, -1):
            if len(m5) < n + 1:
                continue
            box = m5.iloc[-n - 1 : -1]
            top, floor = float(box.high.max()), float(box.low.min())
            if top - floor <= self.params.box * leg:
                selected = n, top, floor
                break
        if selected is None:
            return self.hold(ctx, "NO_BOX")
        _n, top, floor = selected
        mid = (top + floor) / 2
        retr = (mid - b.price) / leg if down else (b.price - mid) / leg
        if not 0.382 <= retr <= 0.786:
            return self.hold(ctx, "RETRACE")
        if (down and price >= floor) or (not down and price <= top):
            return self.hold(ctx, "NO_CLOSE_BREAK")
        stop = (
            top + self.params.buffer * (top - floor) if down else floor - self.params.buffer * (top - floor)
        )
        target = b.price
        risk, reward = abs(stop - price), abs(target - price)
        if reward < self.params.min_take_profit or reward < self.params.min_r * risk:
            return self.hold(ctx, ReasonCode.RR_TOO_LOW)
        if (down and target >= price) or (not down and target <= price) or risk <= 0:
            return self.hold(ctx, "INVALID_GEOMETRY")
        run_frame = m1[(m1.index >= at - pd.Timedelta(minutes=60)) & (m1.index < at)]
        if run_frame.empty:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA)
        run = price - float(run_frame.low.min()) if down else float(run_frame.high.max()) - price
        if running_push_exceeded(run, risk):
            return self.hold(ctx, "RUNNING_PUSH")
        action = Action.SELL if down else Action.BUY
        return self.entry(
            ctx,
            action,
            entry_price=price,
            stop_loss=stop,
            take_profit=target,
            conditions=(
                Condition("stepping", True),
                Condition("box", True, detail=f"{_n} bars"),
                Condition("retrace", True, detail=f"{retr:.3f}"),
                Condition("trigger", True),
                Condition("run_gate", True, detail=f"{run:.2f} <= {1.2 * risk:.2f}"),
            ),
            score=80,
            explanation=f"{self.direction.lower()} confirmed-swing box break",
        )

    def should_close(self, ctx: StrategyContext, side: Side) -> bool:
        at = pd.Timestamp(ctx.decision_time_utc).tz_convert(BANGKOK)
        return at.time() == time(7)

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        if not self.params.break_even:
            return None
        return break_even_advice(ctx, pos)


class TrendBoxDown(TrendBox):
    name = "trend_box_down"
    Params = TrendBoxDownParams
    direction = "DOWN"


class TrendBoxUp(TrendBox):
    name = "trend_box_up"
    Params = TrendBoxUpParams
    direction = "UP"
