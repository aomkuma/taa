"""The pure parts of the real-time runner (eye/ZONE_LIVE.md): prices as sent, comments, the hour's
candidates and
their readings, the visit records, and the questions of rules 1 - 3 and 5 asked of the bar-by-bar life
(``app.zone.core.step_setup``) before a bar has closed.

Pure like ``core``: no broker, no clock, no files. **No second copy of a rule**: where the runner needs to
know
what the setup's life would do with values known only in part (the expiry or the closed-hour cancel at a bar's
open, a withdrawal on the highs so far, a blocked P1, the break-even on the high so far), it puts the known
values into ``step_setup`` and reads the answer; the "unknown" side of the bar is set to a value that cannot
trigger anything (``+/- inf``)."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Decimal

import numpy as np
import pandas as pd

from app.zone.core import (
    BarValues,
    Fill,
    Grid,
    H1Reader,
    SetupLife,
    SetupPlan,
    Visit,
    skip_abnormal,
    skip_momentum,
    skip_trend,
    start_life,
    step_setup,
    visits_at_bar,
)
from app.zone.params import ZoneParams

INF = math.inf
HOUR_NS = 3_600_000_000_000
NAMES = ("P1", "P2")


# --- comments (L3) ------------------------------------------------------------------------------------------


def make_comment(setup_id: int, name: str, n: int) -> str:
    """``Z<setup id>-<P1|P2>-<n>``: unique, the key that ties an order, a deal or a position to its row."""
    return f"Z{setup_id}-{name}-{n}"


Key = tuple[int, str, int]


def parse_comment(comment: str | None) -> Key | None:
    """L3 - reading a key: ``Z``, the setup id's digits, ``-``, ``P1`` or ``P2``, ``-``, then ``n`` = the
    digits up to the first non-digit; text the broker adds after it is ignored. Anything else is no
    key."""
    if not comment or not comment.startswith("Z"):
        return None
    parts = comment[1:].split("-", 2)
    if len(parts) < 3 or parts[1] not in NAMES or not parts[0].isdigit():
        return None
    tail = parts[2]
    end = 0
    while end < len(tail) and tail[end].isdigit():
        end += 1
    if end == 0:
        return None
    return int(parts[0]), parts[1], int(tail[:end])


# --- the prices as sent (L3) --------------------------------------------------------------------------------


def _ticks(price: float, tick: float, mode: str) -> float:
    d_tick = Decimal(str(tick))
    q = (Decimal(repr(float(price))) / d_tick).quantize(Decimal(1), rounding=mode)
    return float(q * d_tick)


def tick_nearest(price: float, tick: float) -> float:
    return _ticks(price, tick, ROUND_HALF_EVEN)


def tick_down(price: float, tick: float) -> float:
    return _ticks(price, tick, ROUND_FLOOR)


def tick_up(price: float, tick: float) -> float:
    return _ticks(price, tick, ROUND_CEILING)


@dataclass(frozen=True)
class SentPrices:
    p1: float
    p2: float
    sl: float
    tp: float


def sent_prices(plan: SetupPlan, tick: float) -> SentPrices:
    """P1 and P2 to the nearest tick, the SL to the tick farther from the entry, the TP to the tick nearer
    it."""
    buy = plan.sgn > 0
    return SentPrices(
        tick_nearest(plan.p1, tick),
        tick_nearest(plan.p2, tick),
        tick_down(plan.sl, tick) if buy else tick_up(plan.sl, tick),
        tick_down(plan.tp, tick) if buy else tick_up(plan.tp, tick),
    )


def be_stop_sent(be_sl: float, sgn: int, tick: float) -> float:
    """The break-even stop rounded to the tick toward the TP side."""
    return tick_up(be_sl, tick) if sgn > 0 else tick_down(be_sl, tick)


def stop_at_or_beyond(current: float, wanted: float, buy: bool, tick: float) -> bool:
    """Is the position's SL already at the requested level or better for it (L8: a stop move never
    worsens)?"""
    return current >= wanted - tick / 2 if buy else current <= wanted + tick / 2


# --- time (L2, L3, L5) --------------------------------------------------------------------------------------


def bar_open_of(now: pd.Timestamp, period_s: int) -> pd.Timestamp:
    """The open of the bar that contains ``now`` (broker bars start on whole periods; the server offsets are
    whole
    hours, so UTC floors are the same bars)."""
    sec = int(now.timestamp())
    return pd.Timestamp(sec - sec % period_s, unit="s", tz="UTC")


def broker_expiry(now: pd.Timestamp) -> pd.Timestamp:
    """The backstop expiry of an order placed ``now``: the close of the current H1 bar + 1 minute."""
    return bar_open_of(now, 3600) + pd.Timedelta(hours=1, minutes=1)


def needs_extension(expiry: pd.Timestamp, now: pd.Timestamp) -> bool:
    """From 10 minutes before its expiry the runner extends a wanted order by one hour."""
    return now >= expiry - pd.Timedelta(minutes=10)


def extended_expiry(expiry: pd.Timestamp) -> pd.Timestamp:
    return expiry + pd.Timedelta(hours=1)


# --- the grid and the hour's candidates (L4) ----------------------------------------------------------------

ArmedKey = tuple[float, float, float]


def grid_at(grids: list[Grid], gstart: np.ndarray, t_ns: int) -> Grid | None:
    """The grid in force at ``t_ns`` (the last one started at or before it)."""
    k = int(np.searchsorted(gstart, t_ns, side="right")) - 1
    return None if k < 0 else grids[k]


def nearest_armed(g: Grid, armed: dict[ArmedKey, bool], o: float, sgn: int) -> float:
    """BUY: the highest armed line ``L < o``; SELL: the lowest armed line ``L > o`` (a line equal to ``o``
    is no
    candidate; disarmed lines are passed over). Lines are the grid's, rounded to cents as in
    ``visits_at_bar``."""
    a, s = g.anchor, g.step
    ra, rs = round(a, 2), round(s, 2)
    k = math.floor((o - a) / s) + 2 if sgn > 0 else math.ceil((o - a) / s) - 2
    for _ in range(100_000):
        line = round(a + k * s, 2)
        past = line < o if sgn > 0 else line > o
        if past and armed.get((ra, rs, line), True):
            return line
        k -= sgn
    raise RuntimeError("no armed line found: the whole neighbourhood of the grid is disarmed")


def extend_reader(r: H1Reader, o: float, lo: float, hi: float, t_ns: int) -> H1Reader:
    """The reader with one more H1 row: the forming bar of the hour, only its open known. ``lo`` / ``hi`` are
    chosen by the caller so that exactly the wanted lines are visited; the bar's close is not read."""
    return replace(
        r,
        o=np.append(r.o, o),
        hi=np.append(r.hi, hi),
        lo=np.append(r.lo, lo),
        c=np.append(r.c, o),
        rng=np.append(r.rng, hi - lo),
        h1_open_ns=np.append(r.h1_open_ns, t_ns),
        ema=np.append(r.ema, np.nan),
        atr=np.append(r.atr, np.nan),
    )


def candidate_visits(
    r: H1Reader,
    g: Grid,
    armed: dict[ArmedKey, bool],
    o: float,
    t_ns: int,
    params: ZoneParams,
) -> dict[str, Visit]:
    """The visit readings of the hour's two candidates (side -> ``Visit``), read from bars closed before the
    hour.
    The simulation's own ``visits_at_bar`` is run on a copy of the arming with the forming bar extended so
    that
    exactly the two nearest armed lines are visited."""
    buy = nearest_armed(g, armed, o, +1)
    sell = nearest_armed(g, armed, o, -1)
    i = len(r)
    ext = extend_reader(r, o, buy, sell, t_ns)
    out: dict[str, Visit] = {}
    for v in visits_at_bar(ext, i, g, dict(armed), params):
        if (v.side == "BUY" and v.line == buy) or (v.side == "SELL" and v.line == sell):
            out[v.side] = v
    if set(out) != {"BUY", "SELL"}:
        raise RuntimeError(
            f"the candidates at {pd.Timestamp(t_ns, tz='UTC')} were not both read: {sorted(out)}"
        )
    return out


def skip_reason(v: Visit, params: ZoneParams) -> str | None:
    """The first of 5a momentum, 5c abnormal, 5d trend that stops the visit (5b busy is the reservation)."""
    if skip_momentum(v, params):
        return "momentum"
    if skip_abnormal(v, params):
        return "abnormal"
    if skip_trend(v, params):
        return "trend"
    return None


def classify_hour(visits: list[Visit], params: ZoneParams, reserved: bool) -> list[tuple[Visit, str]]:
    """The simulation's classification of the visits of one hour, in the order they are taken: 5a momentum,
    5b busy, 5c abnormal, 5d trend, else the hour's setup (and every later visit of the hour is then busy).
    ``reserved``: the hour opened inside a reservation (or a setup still living)."""
    out: list[tuple[Visit, str]] = []
    taken = False
    for v in sorted(visits, key=lambda x: (x.time.value, x.touch_j, x.from_open, x.line)):
        if skip_momentum(v, params):
            out.append((v, "momentum"))
        elif reserved or taken:
            out.append((v, "busy"))
        elif skip_abnormal(v, params):
            out.append((v, "abnormal"))
        elif skip_trend(v, params):
            out.append((v, "trend"))
        else:
            out.append((v, "setup"))
            taken = True
    return out


# --- the life's questions asked before the bar has closed (L5) ----------------------------------------------


def _neutral(prev_close: float, open_hour_ago: float) -> BarValues:
    """A bar that touches nothing: no high, no low, no spread."""
    return BarValues(-INF, INF, 0.0, prev_close, open_hour_ago)


def expired_at(plan: SetupPlan, j: int) -> bool:
    """Rule 1, the expiry: ``j >= end`` (nothing filled)."""
    return step_setup(plan, start_life(plan), j, _neutral(0.0, 0.0)).status == "withdrawn"


def moved_away(plan: SetupPlan, j: int, bid_high: float, bid_low: float) -> bool:
    """Rule 1, the withdrawal (``j > j0``): the bar's bid high (BUY) / low (SELL) so far has reached the
    level."""
    return (
        step_setup(plan, start_life(plan), j, BarValues(bid_high, bid_low, 0.0, 0.0, 0.0)).status
        == "withdrawn"
    )


def closed_hour_cancel(plan: SetupPlan, j: int, prev_close: float, open_hour_ago: float) -> bool:
    """Rule 2, the closed-hour cancel at the open of bar ``j`` (``prev_close`` = the close of bar ``j -
    1``)."""
    return step_setup(plan, start_life(plan), j, _neutral(prev_close, open_hour_ago)).status == "cancel"


def entry_blocked(plan: SetupPlan, price: float, open_hour_ago: float) -> bool:
    """Rule 3, the fill-moment block: the fill test of an order at ``price`` would cancel the setup. (Asked
    as a
    P1 at ``price`` filled in the first bar of the setup, where nothing else can trigger.)"""
    probe = replace(plan, p1=price)
    if plan.sgn > 0:
        bar = BarValues(plan.line, -INF, 0.0, open_hour_ago, open_hour_ago)
    else:
        bar = BarValues(INF, plan.line, 0.0, open_hour_ago, open_hour_ago)
    return step_setup(probe, start_life(probe), plan.j0, bar).status == "cancel"


def be_probe(
    plan: SetupPlan, fills: tuple[Fill, ...], j: int, bar_high: float, bar_low: float, spread_px: float
) -> tuple[bool, float]:
    """Rule 7's break-even on the bar ``j`` (values known so far; the unknown side is neutral): whether it
    goes on and the stop it fixes (unrounded). ``(False, plan.sl)`` when the bar would also exit (the broker's
    exit decides)."""
    life = SetupLife("live", fills, plan.sl)
    if plan.sgn > 0:
        bar = BarValues(bar_high, INF, spread_px, 0.0, 0.0)
    else:
        bar = BarValues(-INF, bar_low, spread_px, 0.0, 0.0)
    after = step_setup(plan, life, j, bar)
    if after.status != "live":
        return False, plan.sl
    return after.be_on, after.cur_sl


def life_at_close(plan: SetupPlan, life: SetupLife, j: int, bar: BarValues) -> SetupLife:
    """The life before any fill, advanced by the closed bar ``j`` (the simulation's own step)."""
    return step_setup(plan, life, j, bar)
