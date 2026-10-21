"""Setup OWN S2: the CPI / NFP release-minute straddle (docs/OWN_SETUP.md; research/2026-10-18-moments/
agents/news, notes.md "FROZEN RULE S2", s2_ticks.py).

At the release second (08:30:00 New York) a buy stop ``trigger_u`` U above the last ask and a sell stop the
same below the last bid, one cancels the other, live for ``window_seconds``; the stop ``stop_u`` U from the
fill; out at market ``hold_seconds`` after the release; no target. 1 U = the bid at the release /
``unit_price`` (the research's 4,000).

This module is the quote-driven plan only (pure, no broker): :meth:`ReleaseStraddle.on_quote` takes every
quote and returns the entry once a trigger is crossed. Execution (the order at market when a trigger is
crossed, the close at ``close_at``) belongs to the engine.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd
from pydantic import Field

from app.core.clock import ensure_utc
from app.core.enums import Action, ExitReason, Side, Timeframe
from app.news.releases import Release, of_events
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)


class StraddleParams(StrategyParams):
    events: tuple[str, ...] = ("CPI", "NFP")
    # the research's frozen D; 3 is the variant to prefer if release spreads run wider than the feed's 0.39
    trigger_u: float = Field(default=2.0, gt=0, le=20)
    stop_u: float = Field(default=8.0, gt=0, le=50)
    unit_price: float = Field(default=4000.0, gt=0)
    window_seconds: float = Field(default=60.0, gt=0, le=600)  # 08:30:00 .. 08:30:59.999
    hold_seconds: float = Field(default=60.0, gt=0, le=3600)  # out at the close of the release minute
    arm_seconds: float = Field(default=30.0, gt=0, le=600)  # quotes this long before set the reference
    # no target in the research: the take-profit (required by the risk checks) is only a far cap
    target_cap_u: float = Field(default=30.0, gt=0, le=200)
    calendar_file: str = "app/news/us_releases.csv"  # read by the engine, which hands the releases over


@dataclass(frozen=True, slots=True)
class StraddleEntry:
    release: Release
    side: Side
    trigger: float  # the crossed level (the fill gap is the price minus it)
    stop_distance: float  # price units from the fill
    close_at: datetime


@dataclass(slots=True)
class _Armed:
    release: Release
    bid: float | None = None
    ask: float | None = None
    done: bool = False


@dataclass
class ReleaseStraddle:
    params: StraddleParams
    releases: Sequence[Release]
    _armed: _Armed | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.releases = of_events(self.releases, self.params.events)

    def unit(self, bid: float) -> float:
        """1 U in price units: the bid / ``unit_price``."""
        return bid / self.params.unit_price

    def upcoming(self, at: datetime) -> Release | None:
        """The release whose arm-to-window span contains *at*."""
        p, at = self.params, ensure_utc(at)
        for r in self.releases:
            if r.at - timedelta(seconds=p.arm_seconds) <= at < r.at + timedelta(seconds=p.window_seconds):
                return r
        return None

    def on_quote(self, at: datetime, bid: float, ask: float) -> StraddleEntry | None:
        """Feed every quote in time order. Before the release the last quote is the reference; inside the
        window the first quote beyond a trigger (ask for the buy stop, bid for the sell stop) is the entry;
        once per release."""
        at = ensure_utc(at)
        release = self.upcoming(at)
        if release is None:
            self._armed = None
            return None
        if self._armed is None or self._armed.release != release:
            self._armed = _Armed(release)
        armed = self._armed
        if armed.done:
            return None
        if at < release.at:
            armed.bid, armed.ask = bid, ask
            return None
        if armed.bid is None or armed.ask is None:
            armed.done = True  # no quote before the release: no reference, no trade (fail closed)
            return None
        p = self.params
        unit = self.unit(armed.bid)
        up, down = armed.ask + p.trigger_u * unit, armed.bid - p.trigger_u * unit
        side = Side.BUY if ask >= up else Side.SELL if bid <= down else None
        if side is None:
            return None
        armed.done = True
        return StraddleEntry(
            release,
            side,
            up if side is Side.BUY else down,
            p.stop_u * unit,
            release.at + timedelta(seconds=p.hold_seconds),
        )


class OwnS2(BaseStrategy):
    """The S2 straddle as a lane strategy: its own name, magic number and statistics. It never fires on a bar;
    the engine feeds it quotes (:meth:`on_quote`) around the releases it was given (:meth:`attach_calendar`)
    and polls faster while :meth:`busy`; the position leaves at the close of the release minute
    (:meth:`manage_position`)."""

    name = "setup_own_s2"
    description = (
        "Setup OWN S2: the CPI / NFP release-minute straddle on gold, on quotes. Lane only. Unproven."
    )
    Params = StraddleParams
    advised = False

    def __init__(self, params: StrategyParams | None = None) -> None:
        super().__init__(params)
        self._releases: tuple[Release, ...] = ()
        self._times: list[datetime] = []
        self._planners: dict[str, ReleaseStraddle] = {}

    def attach_calendar(self, releases: Sequence[Release]) -> None:
        p: StraddleParams = self.params
        self._releases = tuple(sorted(of_events(releases, p.events), key=lambda r: r.at))
        self._times = [r.at for r in self._releases]
        self._planners.clear()

    @property
    def releases(self) -> tuple[Release, ...]:
        return self._releases

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        return (Timeframe.M1,)

    def warmup_bars(self) -> int:
        return 50

    def evaluate(self, ctx: StrategyContext) -> Signal:
        return self.hold(
            ctx, ReasonCode.NO_SETUP, explanation="S2 trades on quotes at a release, not on bars"
        )

    def busy(self, at: datetime) -> bool:
        """A release is being armed or traded: the engine polls quotes faster."""
        at = ensure_utc(at)
        return self.busy_between(at, at + timedelta(microseconds=1))

    def busy_between(self, start: datetime, end: datetime) -> bool:
        """A release's arm-to-window span overlaps [start, end) (a backtest replays those quotes)."""
        start, end = ensure_utc(start), ensure_utc(end)
        return any(a < end and b > start for a, b in self.spans(start, end))

    def spans(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        """The [arm - 5 s, window end) spans of the releases near [start, end)."""
        p: StraddleParams = self.params
        arm, window = timedelta(seconds=p.arm_seconds + 5), timedelta(seconds=p.window_seconds)
        lo, hi = bisect_left(self._times, start - window), bisect_right(self._times, end + arm)
        return [(r.at - arm, r.at + window) for r in self._releases[lo:hi]]

    def unit(self, bid: float) -> float:
        """1 U in price units."""
        p: StraddleParams = self.params
        return bid / p.unit_price

    def new_planner(self) -> ReleaseStraddle:
        return ReleaseStraddle(self.params, self._releases)

    def on_quote(self, symbol: str, at: datetime, bid: float, ask: float) -> StraddleEntry | None:
        planner = self._planners.get(symbol)
        if planner is None:
            planner = self._planners[symbol] = self.new_planner()
        return planner.on_quote(at, bid, ask)

    def entry_signal(self, ctx: StrategyContext, entry: StraddleEntry) -> Signal | None:
        """The market entry at the context's quote; None without one (fail closed)."""
        p: StraddleParams = self.params
        market = ctx.market
        if market.bid is None or market.ask is None:
            return None
        buy = entry.side is Side.BUY
        sign = 1 if buy else -1
        price = market.ask if buy else market.bid
        cap = p.target_cap_u * self.unit(market.bid)
        conds = [
            Condition("release", True, 1.0, f"{entry.release.event} {entry.release.at:%Y-%m-%d %H:%M} UTC"),
            Condition(
                "trigger", True, 1.0, f"{'ask' if buy else 'bid'} {price:.2f} beyond {entry.trigger:.2f}"
            ),
        ]
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=price,
            stop_loss=price - sign * entry.stop_distance,
            take_profit=price + sign * cap,
            conditions=conds,
            score=60.0,
            explanation=f"{entry.release.event} straddle: out at {entry.close_at:%H:%M:%S} UTC",
        )

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        """Out at the first bar close after the release minute (the research's exit at +60 s)."""
        p: StraddleParams = self.params
        due = pd.Timestamp(pos.entry_time).floor("min") + pd.Timedelta(seconds=p.hold_seconds)
        if pd.Timestamp(ctx.decision_time_utc) >= due:
            return PositionAdvice(close=ExitReason.TIME_STOP, note="the release minute is over")
        return None
