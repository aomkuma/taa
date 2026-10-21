"""Setup OWN PLAN-1 as a lane (``plan1``): the London 13:00-Thai opening-range break and the NY 08:30
straddle on every weekday (docs/PLAN1_LANE.md; research/2026-10-18-moments/agents/dev/plan1.py, the rules in
force in journal/PLAN1_JOURNAL.md / rules_week.py). Asia B2 is the third piece; it comes later (checkpoint B).

**London ORB** (:class:`Plan1Orb`, closed M1 bars; research ``d1_orb.decide`` + ``plan1.orb_trade``):

- the open ``t0`` = ``orb_open`` in ``orb_zone`` (13:00 Thai = 06:00 UTC); the day counts only when its first
  M1 bar at / after ``t0`` opens within ``late_open_minutes``;
- the range = the high / low of the M1 bars opening in [first bar, ``t0 + range_minutes``);
- skipped when the range is wider than ``wide_atr`` x the H1 ATR at ``t0`` (MT5 ATR(14): the simple average
  of 14 true ranges of H1 bars built from the M1 bars on the UTC hour, the last one complete by ``t0``);
- the entry = the **first** M1 close beyond the range among the bars opening in the ``entry_minutes``
  after it; decided at that bar's close; a buy at the ask, a sell at the bid;
- the stop = the range's other side, the target ``target_r`` x the risk (journal week 5: 1.5 R), out at the
  close of the M1 bar ``hold_minutes`` after the entry minute (:meth:`Plan1Orb.manage_position`).

**NY straddle** (:class:`Plan1Straddle`, quotes; research ``plan1.straddle``, S2's machinery): at 08:30:00
New York on every weekday a buy stop ``trigger_u`` USD above the last ask and a sell stop the same below the
last bid, live ``window_seconds``; the stop ``stop_u`` USD from the fill; no target (a far ``target_cap_u``
cap for the risk checks); out at 08:30 + ``hold_seconds``. 1 U = 1 USD here (the research's absolute USD).

``atr_floor`` (both pieces): None = no ATR gate (journal week 6 deleted the floor of 12); a number refuses the
trade below it. The H1 ATR is recorded either way.

**The journal record** (every entry's ``conditions``; owner 2026-10-21: "keep a trade journal"): the rule that
passed, the H1 ATR at the decision (last closed H1 bar), the opening range (ORB) or the trigger
(straddle), the pools at the entry (yesterday's server-day high / low, the Asia range 00:00-07:00 Thai,
today's server-day open; ``liq_journal.pools``), the stop distance, and the release on the calendar
(straddle).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd
from pydantic import Field, field_validator

from app.core.clock import ensure_utc
from app.core.enums import Action, ExitReason, Side, Timeframe
from app.news.releases import Release, of_events
from app.strategy.base_strategy import BaseStrategy, StrategyParams
from app.strategy.release_straddle import OwnS2, ReleaseStraddle, StraddleEntry, StraddleParams
from app.strategy.rules import explain, hhmm
from app.strategy.signal_models import (
    Condition,
    OpenPosition,
    PositionAdvice,
    ReasonCode,
    Signal,
    StrategyContext,
)

ATHENS = ZoneInfo("Europe/Athens")  # FBS's server day: yesterday's high / low, today's open
BANGKOK = ZoneInfo("Asia/Bangkok")  # the Asia range 00:00-07:00 Thai
NEW_YORK = ZoneInfo("America/New_York")
ATR_BARS = 14
NS_MIN = 60 * 10**9
FloatArray = np.ndarray


def _zone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown time zone {value!r}") from exc
    return value


def _hhmm(value: str) -> str:
    hhmm(value)
    return value


def local_instant(day: date, at: str, zone: str) -> pd.Timestamp:
    """*at* (HH:MM) on the local *day* in *zone*, in UTC."""
    t = hhmm(at)
    return pd.Timestamp(
        datetime(day.year, day.month, day.day, t.hour, t.minute, tzinfo=ZoneInfo(zone))
    ).tz_convert("UTC")


# --- shared readings --------------------------------------------------------------------------------------


def h1_atr_at(
    opens: pd.DatetimeIndex, h: FloatArray, lo: FloatArray, c: FloatArray, t: pd.Timestamp
) -> float:
    """MT5 ATR(14) of the H1 bars built from M1 on the UTC hour, the last one complete by *t* (its hour + 1 h
    <= *t*); the true range against the previous H1 bar's close; NaN with fewer than 15 H1 bars."""
    hours = opens.floor("h")
    keep = np.asarray(hours + pd.Timedelta(hours=1) <= t)
    if not keep.any():
        return math.nan
    df = pd.DataFrame({"h": h[keep], "lo": lo[keep], "c": c[keep]}, index=hours[keep])
    g = df.groupby(level=0, sort=True)
    hh, ll, cc = g.h.max().to_numpy(float), g.lo.min().to_numpy(float), g.c.last().to_numpy(float)
    if len(cc) < ATR_BARS + 1:
        return math.nan
    pc = cc[-ATR_BARS - 1 : -1]
    tr = np.maximum(hh[-ATR_BARS:], pc) - np.minimum(ll[-ATR_BARS:], pc)
    return float(tr.mean())


def pools(
    opens: pd.DatetimeIndex, o: FloatArray, h: FloatArray, lo: FloatArray, t: pd.Timestamp
) -> dict[str, float]:
    """The pools known at *t* from M1 bars closed by *t* (liq_journal.pools): yesterday's server-day high /
    low (the last server day before today within three days), the Asia range (today's Thai 00:00-07:00, once
    Thai time is past 07:00), today's server-day open, and the last confirmed M15 3-bar fractal swing high /
    low (M15 bins of those M1 bars on the UTC quarter hour, the last 97, read from the second-last back)."""
    keep = np.asarray(opens + pd.Timedelta(minutes=1) <= t)
    idx = opens[keep]
    if not len(idx):
        return {}
    oo, hh, ll = o[keep], h[keep], lo[keep]
    srv = idx.tz_convert(ATHENS)
    srv_day = srv.normalize()
    today = srv_day[-1]
    out: dict[str, float] = {}
    before = np.asarray((srv_day < today) & (srv_day >= today - pd.Timedelta(days=3)))
    if before.any():
        yday = srv_day[before].max()
        y = np.asarray(srv_day == yday)
        out["yday_high"], out["yday_low"] = float(hh[y].max()), float(ll[y].min())
    thai = idx.tz_convert(BANGKOK)
    d0 = thai[-1].normalize()
    a = np.asarray((thai >= d0) & (thai < d0 + pd.Timedelta(hours=7)))
    if a.any() and t.tz_convert(BANGKOK) >= d0 + pd.Timedelta(hours=7):
        out["asia_high"], out["asia_low"] = float(hh[a].max()), float(ll[a].min())
    tod = np.flatnonzero(np.asarray(srv_day == today))
    out["today_open"] = float(oo[tod[0]])
    q = pd.DataFrame({"high": hh, "low": ll}, index=idx).resample("15min").agg({"high": "max", "low": "min"})
    q = q.dropna().iloc[-97:]
    qh, ql = q["high"].to_numpy(float), q["low"].to_numpy(float)
    for k in range(len(q) - 2, 0, -1):
        if "swing_high" not in out and qh[k] > qh[k - 1] and qh[k] > qh[k + 1]:
            out["swing_high"] = float(qh[k])
        if "swing_low" not in out and ql[k] < ql[k - 1] and ql[k] < ql[k + 1]:
            out["swing_low"] = float(ql[k])
        if "swing_high" in out and "swing_low" in out:
            break
    return out


def broken_pools(
    opens: pd.DatetimeIndex,
    o: FloatArray,
    h: FloatArray,
    lo: FloatArray,
    t: pd.Timestamp,
    side: int,
    found: dict[str, float],
    minutes: int = 15,
) -> list[str]:
    """The pools the M1 bars of the *minutes* before *t* (opening at / after t - minutes, closed by t) broke
    in the trade's direction (liq_journal's ``broke``): a buy - the window opened below the pool and traded
    above it; a sell mirrored."""
    keep = np.asarray((opens >= t - pd.Timedelta(minutes=minutes)) & (opens + pd.Timedelta(minutes=1) <= t))
    if not keep.any():
        return []
    first, top, bottom = float(o[keep][0]), float(h[keep].max()), float(lo[keep].min())
    if side > 0:
        return [k for k, v in found.items() if first < v < top]
    return [k for k, v in found.items() if first > v > bottom]


def is_contracting(change: float, max_pct: float) -> bool:
    """The H4 ATR's change (a fraction) at or below *max_pct* percent; unknown counts as contracting (fail
    closed)."""
    return not math.isfinite(change) or 100.0 * change <= max_pct


def h4_atr_change(h4: pd.DataFrame, t: pd.Timestamp, bars: int = 6) -> float:
    """The H4 ATR's change over the last ``bars`` H4 bars (6 = 24 h): MT5 ATR(14) of the H4 bars closed by
    *t* (the frame's index is the close time), the latest / the one ``bars`` earlier - 1; NaN when unknown."""
    done = h4[h4.index <= t]
    if len(done) < ATR_BARS + bars:
        return math.nan
    hh, ll, cc = (done[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    pc = np.r_[np.nan, cc[:-1]]
    tr = np.fmax(hh, pc) - np.fmin(ll, pc)  # the first bar: high - low (liq_journal's rolling max skips NaN)
    atr = pd.Series(tr).rolling(ATR_BARS).mean().to_numpy()
    now, then = float(atr[-1]), float(atr[-1 - bars])
    if not (math.isfinite(now) and math.isfinite(then)) or then <= 0:
        return math.nan
    return now / then - 1.0


def pools_detail(p: dict[str, float]) -> str:
    keys = ("yday_high", "yday_low", "asia_high", "asia_low", "today_open", "swing_high", "swing_low")
    return " ".join(f"{k}={p[k]:.2f}" if k in p else f"{k}=none" for k in keys)


def _m1_arrays(m1: pd.DataFrame) -> tuple[pd.DatetimeIndex, FloatArray, FloatArray, FloatArray, FloatArray]:
    opens = pd.DatetimeIndex(pd.to_datetime(m1["open_time"], utc=True))
    o, h, lo, c = (m1[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    return opens, o, h, lo, c


# --- the London ORB ---------------------------------------------------------------------------------------


class Plan1OrbParams(StrategyParams):
    orb_open: str = "13:00"  # London 13:00 Thai = 06:00 UTC (Thailand keeps no summer time)
    orb_zone: str = "Asia/Bangkok"
    range_minutes: int = Field(default=15, ge=1, le=120)
    entry_minutes: int = Field(default=60, ge=1, le=240, description="the window after the range")
    late_open_minutes: int = Field(default=5, ge=0, le=60)
    wide_atr: float = Field(default=1.5, gt=0, le=20, description="skip a range wider than this x H1 ATR")
    target_r: float = Field(default=1.5, gt=0, le=20)  # journal week 5 (was 2 R)
    hold_minutes: int = Field(default=60, ge=1, le=1440)
    atr_floor: float | None = Field(default=None, gt=0, le=1000)  # journal week 6: no floor
    # journal week 10: when the H4 ATR(14) did not grow over the last ``h4_change_bars`` H4 bars (latest <=
    # that many bars earlier), enter only after the ``pool_break_minutes`` before the decision broke a pool in
    # the trade's direction
    pool_break_when_h4_contracting: bool = True
    h4_change_bars: int = Field(default=6, ge=1, le=60)
    pool_break_minutes: int = Field(default=15, ge=1, le=120)
    # "contracting" = the change in percent <= this; 0.5 is the journal's reading (liq_journal rounds the
    # change to a whole percent and rules_week takes <= 0: +0.4 % counts as contracting, +0.6 % does not)
    h4_contracting_max_pct: float = Field(default=0.5, ge=-50, le=50)

    @field_validator("orb_zone")
    @classmethod
    def _check_zone(cls, value: str) -> str:
        return _zone(value)

    @field_validator("orb_open")
    @classmethod
    def _check_open(cls, value: str) -> str:
        return _hhmm(value)


@dataclass(frozen=True, slots=True)
class OrbDecision:
    status: str  # late_open / no_range / wide / no_break / trade
    side: int = 0
    k: int = -1  # the decision bar (its close is the decision)
    rh: float = math.nan
    rl: float = math.nan
    h1_atr: float = math.nan  # the wide check's H1 ATR at the open


def orb_decide(
    opens: pd.DatetimeIndex,
    h: FloatArray,
    lo: FloatArray,
    c: FloatArray,
    t0: pd.Timestamp,
    atr: float,
    p: Plan1OrbParams,
) -> OrbDecision:
    """research d1_orb.decide on the bars given (all of them closed)."""
    ns = opens.as_unit("ns").to_numpy(dtype="datetime64[ns]").astype(np.int64)
    t0n = t0.as_unit("ns").value
    i0 = int(np.searchsorted(ns, t0n))
    if i0 >= len(ns) or ns[i0] - t0n > p.late_open_minutes * NS_MIN:
        return OrbDecision("late_open", h1_atr=atr)
    i_l = int(np.searchsorted(ns, t0n + p.range_minutes * NS_MIN))
    if i_l <= i0:
        return OrbDecision("no_range", h1_atr=atr)
    rh, rl = float(h[i0:i_l].max()), float(lo[i0:i_l].min())
    if not math.isfinite(atr) or rh - rl > p.wide_atr * atr:
        return OrbDecision("wide", rh=rh, rl=rl, h1_atr=atr)
    i_e = int(np.searchsorted(ns, t0n + (p.range_minutes + p.entry_minutes) * NS_MIN))
    for k in range(i_l, i_e):
        side = 1 if c[k] > rh else -1 if c[k] < rl else 0
        if side:
            return OrbDecision("trade", side, k, rh, rl, atr)
    return OrbDecision("no_break", rh=rh, rl=rl, h1_atr=atr)


class Plan1Orb(BaseStrategy):
    name = "setup_plan1_orb"
    version = "1.0.0"
    description = (
        "Setup OWN PLAN-1, London ORB: the first M1 close beyond the 13:00-Thai 15-minute range, the stop "
        "at its other side, 1.5 R, out after 60 minutes; M1 gold. Lane only. Unproven."
    )
    Params = Plan1OrbParams
    advised = False

    def required_timeframes(self) -> tuple[Timeframe, ...]:
        p: Plan1OrbParams = self.params
        return (Timeframe.M1, Timeframe.H4) if p.pool_break_when_h4_contracting else (Timeframe.M1,)

    def warmup_bars(self) -> int:
        return 3000  # 15 complete H1 bars and yesterday's server day across a weekend

    def evaluate(self, ctx: StrategyContext) -> Signal:
        p: Plan1OrbParams = self.params
        market = ctx.market
        at = pd.Timestamp(market.decision_time_utc)
        if market.entry_timeframe is not Timeframe.M1:
            return self.hold(ctx, ReasonCode.DATA_QUALITY, explanation="the ORB runs on an M1 lane")
        t0 = local_instant(at.tz_convert(p.orb_zone).date(), p.orb_open, p.orb_zone)
        first = t0 + pd.Timedelta(minutes=p.range_minutes + 1)  # the first bar after the range closes here
        last = t0 + pd.Timedelta(minutes=p.range_minutes + p.entry_minutes)
        if not first <= at <= last or at.weekday() > 4:
            return self.hold(ctx, ReasonCode.OUTSIDE_SESSION, explanation=f"{at:%a %H:%M} UTC")
        m1 = ctx.frame(Timeframe.M1)
        if len(m1) < 2:
            return self.hold(ctx, ReasonCode.INSUFFICIENT_DATA, explanation=f"{len(m1)} M1 bars")
        opens, o, h, lo, c = _m1_arrays(m1)
        atr0 = h1_atr_at(opens, h, lo, c, t0)
        d = orb_decide(opens, h, lo, c, t0, atr0, p)
        if d.status != "trade":
            return self.hold(ctx, ReasonCode.NO_SETUP, explanation=f"ORB {d.status}")
        if d.k != len(m1) - 1:
            return self.hold(
                ctx, ReasonCode.NO_SETUP, explanation=f"ORB broke at {opens[d.k]:%H:%M} UTC already"
            )
        buy = d.side > 0
        price = market.ask if buy else market.bid
        if price is None:
            return self.hold(ctx, ReasonCode.DATA_QUALITY, explanation="no quote")
        stop = d.rl if buy else d.rh
        risk = (price - stop) * d.side
        if not risk > 0:
            return self.hold(ctx, ReasonCode.NO_SETUP, explanation=f"the price {price:.2f} is past the stop")
        atr = h1_atr_at(opens, h, lo, c, at)
        floor_ok = p.atr_floor is None or (math.isfinite(atr) and atr >= p.atr_floor)
        found = pools(opens, o, h, lo, at)
        broke = broken_pools(opens, o, h, lo, at, d.side, found, p.pool_break_minutes)
        h4 = ctx.frames.get(Timeframe.H4)
        change = math.nan if h4 is None else h4_atr_change(h4, at, p.h4_change_bars)
        contracting = is_contracting(change, p.h4_contracting_max_pct)
        pool_ok = not p.pool_break_when_h4_contracting or not contracting or bool(broke)
        h4_text = "unknown" if not math.isfinite(change) else f"{100 * change:+.1f} %"
        conds = [
            Condition(
                "rule",
                True,
                1.0,
                f"London ORB: the first M1 close {c[-1]:.2f} {'above' if buy else 'below'} the range "
                f"(bar {opens[d.k]:%H:%M} UTC)",
            ),
            Condition("h1_atr", floor_ok, 1.0, atr_detail(atr, p.atr_floor)),
            Condition(
                "opening_range",
                True,
                1.0,
                f"{d.rl:.2f}-{d.rh:.2f} width {d.rh - d.rl:.2f} <= {p.wide_atr:g} x H1 ATR {atr0:.2f} at "
                f"{t0:%H:%M} UTC",
            ),
            Condition("pools", True, 1.0, pools_detail(found)),
            Condition(
                "h4_atr_change",
                True,
                1.0,
                f"H4 ATR(14) over {p.h4_change_bars} H4 bars {h4_text} "
                f"({'contracting' if contracting else 'expanding'})",
            ),
            Condition(
                "pool_break",
                pool_ok,
                1.0,
                f"the {p.pool_break_minutes} minutes broke: {','.join(broke) or 'none'}"
                + ("" if p.pool_break_when_h4_contracting else "; rule off"),
            ),
            Condition(
                "stop_distance",
                True,
                1.0,
                f"{risk:.2f} to the range {'low' if buy else 'high'} {stop:.2f}; target {p.target_r:g} R",
            ),
            Condition("spread", True, 1.0, spread_detail(market.bid, market.ask, ctx)),
        ]
        if not (floor_ok and pool_ok):
            return self.hold(ctx, ReasonCode.NO_SETUP, conditions=conds, explanation=explain(conds))
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=price,
            stop_loss=stop,
            take_profit=price + d.side * p.target_r * risk,
            conditions=conds,
            score=60.0,
            explanation=explain(conds),
        )

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        """Out at the close of the M1 bar ``hold_minutes`` after the entry minute (research: the first tick at
        / after the fill + 60 minutes)."""
        p: Plan1OrbParams = self.params
        due = pd.Timestamp(pos.entry_time).floor("min") + pd.Timedelta(minutes=p.hold_minutes)
        if pd.Timestamp(ctx.decision_time_utc) >= due:
            return PositionAdvice(close=ExitReason.TIME_STOP, note=f"{p.hold_minutes} minutes")
        return None


def spread_detail(bid: float | None, ask: float | None, ctx: StrategyContext) -> str:
    """The decision quote's spread in USD and points (the journal's spread record)."""
    if bid is None or ask is None:
        return "no quote"
    point = None if ctx.spec is None else ctx.spec.point
    pts = "" if not point else f" ({(ask - bid) / point:.0f} points)"
    return f"{ask - bid:.2f}{pts} at the decision quote"


def atr_detail(atr: float, floor: float | None) -> str:
    base = f"H1 ATR {atr:.2f} (MT5 ATR(14), last closed H1 bar)"
    return base + ("; no floor" if floor is None else f"; floor {floor:g}")


# --- the NY straddle --------------------------------------------------------------------------------------


class Plan1StraddleParams(StraddleParams):
    """S2's numbers in USD (1 U = 1 USD; ``unit_price`` is not used), on every weekday at ``ny_open``."""

    events: tuple[str, ...] = ("CPI", "NFP", "PPI", "PCE", "GDP")  # only named in the journal record
    ny_open: str = "08:30"
    ny_zone: str = "America/New_York"
    hold_seconds: float = Field(default=1800.0, gt=0, le=14_400)  # 30 minutes after 08:30
    target_cap_u: float = Field(default=100.0, gt=0, le=200)  # no target in the research: a far cap only
    atr_floor: float | None = Field(default=None, gt=0, le=1000)

    @field_validator("ny_zone")
    @classmethod
    def _check_zone(cls, value: str) -> str:
        return _zone(value)

    @field_validator("ny_open")
    @classmethod
    def _check_open(cls, value: str) -> str:
        return _hhmm(value)


def daily_release(day: date, p: Plan1StraddleParams) -> Release | None:
    """08:30 New York on a weekday *day*, as a release; None on a weekend."""
    if day.weekday() > 4:
        return None
    return Release(local_instant(day, p.ny_open, p.ny_zone).to_pydatetime(), "NY0830")


@dataclass
class DailyStraddle(ReleaseStraddle):
    """S2's planner with an instant on every weekday and the triggers / stop in USD."""

    def unit(self, bid: float) -> float:
        return 1.0

    def upcoming(self, at: datetime) -> Release | None:
        p = self.params
        if not isinstance(p, Plan1StraddleParams):
            raise TypeError("DailyStraddle needs Plan1StraddleParams")
        at = ensure_utc(at)
        r = daily_release(at.astimezone(ZoneInfo(p.ny_zone)).date(), p)
        if r is not None and r.at - timedelta(seconds=p.arm_seconds) <= at < r.at + timedelta(
            seconds=p.window_seconds
        ):
            return r
        return None


class Plan1Straddle(OwnS2):
    """The NY 08:30 straddle of PLAN-1 on every weekday: S2's quote path (the engine feeds quotes while
    :meth:`busy`), the triggers in USD, out at 08:30 + ``hold_seconds``."""

    name = "setup_plan1_ny"
    description = (
        "Setup OWN PLAN-1, NY straddle: at 08:30 New York every weekday a buy stop 2 USD above the ask and "
        "a sell stop 2 USD below the bid, the stop 8 USD, out after 30 minutes; gold, on quotes. Lane only. "
        "Unproven."
    )
    Params = Plan1StraddleParams
    advised = False

    def __init__(self, params: StrategyParams | None = None) -> None:
        super().__init__(params)
        self._calendar: tuple[Release, ...] = ()

    def attach_calendar(self, releases: Sequence[Release]) -> None:
        """The calendar only names the day's release in the journal; the straddle trades every weekday."""
        p: Plan1StraddleParams = self.params
        self._calendar = of_events(releases, p.events)
        self._planners.clear()

    def warmup_bars(self) -> int:
        return 3000

    def spans(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        p: Plan1StraddleParams = self.params
        arm, window = timedelta(seconds=p.arm_seconds + 5), timedelta(seconds=p.window_seconds)
        zone = ZoneInfo(p.ny_zone)
        day, last = (start - window).astimezone(zone).date(), (end + arm).astimezone(zone).date()
        out = []
        while day <= last:
            r = daily_release(day, p)
            if r is not None:
                out.append((r.at - arm, r.at + window))
            day += timedelta(days=1)
        return out

    def unit(self, bid: float) -> float:
        return 1.0

    def new_planner(self) -> ReleaseStraddle:
        return DailyStraddle(self.params, ())

    def release_on(self, at: datetime) -> str:
        names = sorted({r.event for r in self._calendar if r.at == at})
        return ",".join(names) if names else "none on the calendar"

    def entry_signal(self, ctx: StrategyContext, entry: StraddleEntry) -> Signal | None:
        """The market entry at the context's quote with the journal record; None without a quote or below an
        ``atr_floor`` (fail closed)."""
        p: Plan1StraddleParams = self.params
        market = ctx.market
        if market.bid is None or market.ask is None:
            return None
        at = pd.Timestamp(market.quote_time_utc or market.decision_time_utc)
        record = self.journal(ctx, entry, at)
        if record is None:
            return None
        conds, floor_ok = record
        if not floor_ok:
            return None
        buy = entry.side is Side.BUY
        sign = 1 if buy else -1
        price = market.ask if buy else market.bid
        return self.entry(
            ctx,
            Action.BUY if buy else Action.SELL,
            entry_price=price,
            stop_loss=price - sign * entry.stop_distance,
            take_profit=price + sign * p.target_cap_u,
            conditions=conds,
            score=60.0,
            explanation=f"NY 08:30 straddle: out at {entry.close_at:%H:%M:%S} UTC; " + explain(conds),
        )

    def journal(
        self, ctx: StrategyContext, entry: StraddleEntry, at: pd.Timestamp
    ) -> tuple[list[Condition], bool] | None:
        p: Plan1StraddleParams = self.params
        m1 = ctx.frames.get(Timeframe.M1)
        if m1 is None or not len(m1):
            return None
        opens, o, h, lo, c = _m1_arrays(m1)
        atr = h1_atr_at(opens, h, lo, c, at)
        floor_ok = p.atr_floor is None or (math.isfinite(atr) and atr >= p.atr_floor)
        buy = entry.side is Side.BUY
        conds = [
            Condition(
                "rule",
                True,
                1.0,
                f"NY straddle: the {'ask' if buy else 'bid'} crossed {entry.trigger:.2f} "
                f"({p.trigger_u:g} USD past the reference) at {at:%H:%M:%S} UTC",
            ),
            Condition("h1_atr", floor_ok, 1.0, atr_detail(atr, p.atr_floor)),
            Condition(
                "release",
                True,
                1.0,
                f"{entry.release.at:%Y-%m-%d %H:%M} UTC: {self.release_on(entry.release.at)}",
            ),
            Condition("pools", True, 1.0, pools_detail(pools(opens, o, h, lo, at))),
            Condition("stop_distance", True, 1.0, f"{entry.stop_distance:.2f} from the fill; no target"),
            Condition("spread", True, 1.0, spread_detail(ctx.market.bid, ctx.market.ask, ctx)),
        ]
        return conds, floor_ok

    def manage_position(self, ctx: StrategyContext, pos: OpenPosition) -> PositionAdvice | None:
        """Out at the first bar close at / after 08:30 New York of the entry's day + ``hold_seconds``."""
        p: Plan1StraddleParams = self.params
        entry = pd.Timestamp(pos.entry_time)
        r = daily_release(entry.tz_convert(p.ny_zone).date(), p)
        start = pd.Timestamp(r.at) if r is not None else entry.floor("min")
        due = start + pd.Timedelta(seconds=p.hold_seconds)
        if pd.Timestamp(ctx.decision_time_utc) >= due:
            return PositionAdvice(close=ExitReason.TIME_STOP, note="the straddle's 30 minutes are over")
        return None


def journal_fields(signal: Signal) -> dict[str, Any]:
    """A signal's journal record as a flat dict (condition name -> detail), for reports."""
    return {c.name: c.detail for c in signal.conditions}
