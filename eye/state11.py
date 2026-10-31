"""Rule 11's building blocks (eye/BOT_RULES.md): M30 from the stored M15, and the looks.

Pure functions on frames; no file I/O and no clock. Piece 1 only: ``m30_from_m15`` and ``look``.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
import pandas as pd

from app.indicators.chart_read import zigzag_pivots
from app.indicators.price_action import Swing

OHLC = ["open", "high", "low", "close"]

# BOT_RULES "The looks": a trading day in closed bars present in the data [Claude].
BARS_PER_DAY = {"M30": 46, "M5": 274, "M15": 92, "H1": 23}


def m30_from_m15(m15: pd.DataFrame) -> pd.DataFrame:
    """BOT_RULES "Data": each M30 bar = the M15 bars opening at :00 and :15 (or :30 and :45).

    Open of the first, high and low of both, close of the second, labelled by the first's open time;
    a 30-minute slot without both stored M15 bars has no M30 bar.
    """
    m = m15[OHLC].sort_index(kind="stable")
    m = m[~m.index.duplicated(keep="first")]
    slot = m.index.floor("30min")
    first = (m.index - slot) == pd.Timedelta(0)
    second = (m.index - slot) == pd.Timedelta(minutes=15)
    m = m[first | second]
    slot = slot[first | second]
    g = m.groupby(slot)
    full = g["open"].count() == 2
    out = pd.DataFrame(
        {
            "open": g["open"].first(),
            "high": g["high"].max(),
            "low": g["low"].min(),
            "close": g["close"].last(),
        }
    )
    out = out[full]
    out.index.name = m15.index.name
    return out.sort_index()


def look_bars(tf: str, days: float) -> int:
    """The bar count of a look of ``days`` trading days (floored; the spec does not decide fractions)."""
    if tf not in BARS_PER_DAY:
        raise ValueError(f"unknown timeframe {tf!r}")
    return math.floor(days * BARS_PER_DAY[tf] + 1e-9)


def look(df: pd.DataFrame, tf: str, days: float) -> pd.DataFrame:
    """BOT_RULES "The looks": the last ``days`` x bars-per-day rows of ``df`` (already cut at ``now``).

    The count is of bars present, so a weekend gap is skipped. A non-integer product is floored
    (see the report: the spec does not decide it). A frame shorter than the look is returned whole.
    """
    if tf not in BARS_PER_DAY:
        raise ValueError(f"unknown timeframe {tf!r}")
    n = look_bars(tf, days)
    if n <= 0:
        return df.iloc[0:0]
    return df.iloc[-n:]


# BOT_RULES rule 11 constants.
TOUCH_HIGH = 0.88  # a HIGH at or above lo + 0.88 h touches the high edge
TOUCH_LOW = 0.12  # a LOW at or below lo + 0.12 h touches the low edge
BREAK_BEYOND = 0.27  # the break line: hi + 0.27 h above, lo - 0.27 h below (127 % / -27 %)


@dataclass(frozen=True)
class Range:
    """A range in force (rule 11 "A range")."""

    e: Swing
    b: Swing
    lo: float
    hi: float
    legs: int
    last_touch: str  # "HIGH" or "LOW"


@dataclass(frozen=True)
class Break:
    """A break (rule 11 "A break"): its way and the bar position of the breaking close."""

    way: str  # "up" or "down"
    bar: int


@dataclass(frozen=True)
class Walk:
    """The walk at ``now`` (rule 11 "The walk at `now` gives")."""

    range: Range | None
    last_break: Break | None


def _first_break(close: np.ndarray, start: int, stop: int, lo: float, hi: float) -> Break | None:
    """The first close on bars ``start..stop`` (inclusive) strictly beyond the break line, in time order."""
    if stop < start:
        return None
    h = hi - lo
    seg = close[start : stop + 1]
    hit = (seg > hi + BREAK_BEYOND * h) | (seg < lo - BREAK_BEYOND * h)
    if not hit.any():
        return None
    k = int(np.argmax(hit))
    return Break("up" if seg[k] > hi + BREAK_BEYOND * h else "down", start + k)


def _start_range(pivots: Sequence[Swing], i: int) -> int | None:
    """The first index ``>= i`` whose pair (i, i+1) has h > 0; a pair with h <= 0 is dropped (two pivots)."""
    while i + 1 < len(pivots):
        if pivots[i].price != pivots[i + 1].price:
            return i
        i += 2
    return None


def walk(pivots: Sequence[Swing], close: np.ndarray) -> Walk:
    """Rule 11 "One walk": the range in force and the last break, from the frame's fixed pivots and closes.

    ``pivots`` are fixed by ``now``, oldest first; ``close`` is indexed by bar position, its last element
    the last closed bar at ``now``.
    """
    n = len(pivots)
    for a, b2 in pairwise(pivots):
        if a.kind is b2.kind:
            raise ValueError("pivots must alternate HIGH / LOW")
    last_bar = len(close) - 1
    last_break: Break | None = None
    i = _start_range(
        pivots, 0
    )  # the first range = the first two pivots; no close before the second is tested
    if i is None:
        return Walk(None, None)
    while True:
        e, b = pivots[i], pivots[i + 1]
        lo, hi = min(e.price, b.price), max(e.price, b.price)
        h = hi - lo
        legs, last_touch = 1, b.kind.value
        prev_bar = b.pivot_pos
        j = i + 2
        broke = False
        while j < n:
            p = pivots[j]
            br = _first_break(close, prev_bar + 1, p.pivot_pos, lo, hi)  # closes first (rule 11)
            if br is not None:
                last_break = br
                # E = the HIGH (up) / LOW (down) of the two pivots bounding the breaking segment
                want = "HIGH" if br.way == "up" else "LOW"
                pair = (pivots[j - 1], p)  # alternating kinds: exactly one has the break's kind
                k = j - 1 if pair[0].kind.value == want else j
                # (E, B) with h <= 0 is dropped like the frame's first pair; none left: no range
                nxt = _start_range(pivots, k)
                if nxt is None:
                    return Walk(None, last_break)  # B not yet fixed: no range, the trend stands
                i = nxt
                broke = True
                break
            if p.kind.value == "HIGH" and p.price >= lo + TOUCH_HIGH * h:
                edge = "HIGH"
            elif p.kind.value == "LOW" and p.price <= lo + TOUCH_LOW * h:
                edge = "LOW"
            else:
                edge = ""  # in the middle: ignored
            if edge and edge != last_touch:
                legs += 1
                last_touch = edge
            prev_bar = p.pivot_pos
            j += 1
        if broke:
            continue
        # after the last pivot: the closes up to the last closed bar are tested the same way
        br = _first_break(close, prev_bar + 1, last_bar, lo, hi)
        if br is not None:
            return Walk(None, br)  # trend in force, no range at now
        return Walk(Range(e, b, lo, hi, legs, last_touch), last_break)


# --- the M30 state at now (rule 11 "The M30 state at `now`") ---------------------------------------------

FRAME_BARS = 1500  # "Words used": the frame is the last 1,500 closed bars
THAI = "Asia/Bangkok"


@dataclass(frozen=True)
class M30State:
    """The M30 state at ``now``: kind (sideways, up, down, none), case 1-4, the walk, UTC times."""

    kind: str
    case: int
    walk: Walk
    e_time: pd.Timestamp | None
    b_time: pd.Timestamp | None
    break_time: pd.Timestamp | None


def classify(w: Walk, n_bars: int, range_bars: int, trend_bars: int) -> tuple[str, int]:
    """The four ordered cases. A bar position ``p`` of an ``n_bars`` frame lies in a look of ``k`` bars
    when ``p >= n_bars - k``."""
    r, br = w.range, w.last_break
    sideways = r is not None and r.legs >= 2
    if sideways and r is not None and r.e.pivot_pos >= n_bars - range_bars:
        return "sideways", 1  # 1. legs >= 2 and E in the range look
    if br is not None and br.bar >= n_bars - trend_bars:
        return br.way, 2  # 2. the last break's close in the trend look
    if sideways:
        return "sideways", 3  # 3. legs >= 2, E older than the range look
    return "none", 4  # 4. no M30 side


def _zigzag(df: pd.DataFrame) -> list[Swing]:
    """MT5's ZigZag on the frame as ``eye/bot2e.py`` reads it. ``zigzag_pivots`` already returns only pivots
    whose confirm bar is inside the frame (fixed by ``now``), so no further filter is needed."""
    walker = importlib.import_module("eye.walk")  # lazy: it reads data/.../spec.json at import
    return zigzag_pivots(
        df["high"].to_numpy(dtype=np.float64),
        df["low"].to_numpy(dtype=np.float64),
        walker.POINT,
        index=list(df.index),
        **walker.ZIGZAG,
    )


def state_at(
    m30: pd.DataFrame, range_days: float = 4, trend_days: float = 7, frame_bars: int = FRAME_BARS
) -> M30State:
    """The M30 state from the closed M30 bars at ``now`` (the last ``frame_bars`` are the frame)."""
    frame = m30.iloc[-frame_bars:]
    n = len(frame)
    w = walk(_zigzag(frame), frame["close"].to_numpy(dtype=np.float64))
    kind, case = classify(w, n, look_bars("M30", range_days), look_bars("M30", trend_days))

    def at(pos: int | None) -> pd.Timestamp | None:
        return None if pos is None else pd.Timestamp(frame.index[pos])

    r = w.range
    return M30State(
        kind,
        case,
        w,
        at(r.e.pivot_pos if r else None),
        at(r.b.pivot_pos if r else None),
        at(w.last_break.bar if w.last_break else None),
    )


def _th(t: pd.Timestamp) -> str:
    return t.tz_convert(THAI).strftime("%d/%m %H:%M")


def describe(state: M30State) -> str:
    """The structure text, one line, stable wording."""
    r = state.walk.range
    if state.kind == "sideways" and r is not None and state.e_time is not None and state.b_time is not None:
        return (
            f"M30 sideways (case {state.case}): lo {r.lo:.2f}, hi {r.hi:.2f}, "
            f"E {r.e.kind.value} {r.e.price:.2f} {_th(state.e_time)}, "
            f"B {r.b.kind.value} {r.b.price:.2f} {_th(state.b_time)}, "
            f"legs {r.legs}, leg {r.legs + 1}, last touch {r.last_touch}"
        )
    if state.kind in ("up", "down") and state.break_time is not None:
        return f"M30 trending {state.kind} (case {state.case}): breaking close {_th(state.break_time)}"
    return f"M30 none (case {state.case}): no side"


def side_of(state: M30State) -> str:
    """The side the state allows (rule 11): a trend its own way (up BUY, down SELL).

    Sideways: the leg traded is legs + 1; legs 3-5 go away from the last touch (HIGH SELL, LOW BUY), leg 6 on
    either; otherwise none.
    """
    if state.kind == "up":
        return "BUY"
    if state.kind == "down":
        return "SELL"
    r = state.walk.range
    if state.kind == "sideways" and r is not None:
        leg = r.legs + 1
        if leg >= 6:
            return "either"
        if leg >= 3:
            return "SELL" if r.last_touch == "HIGH" else "BUY"
    return "none"
