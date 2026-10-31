"""The signal study, piece 1 (eye/SIGNAL_STUDY.md rows S3, C2, C3, C4): the events and the counter-move.

Pure functions on frames and on plain numbers; no file I/O and no clock. Positions are bar positions in the
M15 frame; a bar at position ``i`` closes at ``index[i] + 15 min`` and "the close at ``i``" is that close.

* S3  strip B (the structure side per M15 close, as ``eye/research/structure_side.py`` computes it) and its
      changes of side = the events, with ``H`` = the swing the close broke.
* C2  the counter-move: the stretch of B's previous side, and its fixed swing extremes (LOWs for a BUY event,
      HIGHs for a SELL), ``L*`` = the lowest (highest).
* C3  the count: the run of consecutive lower-or-equal LOWs (higher-or-equal HIGHs) ending at ``L*``.
* C4  the owner's M (BUY, coming down into a support) / W (SELL, into a resistance) on the counter-move's
      last two extremes - the owner's words, the textbook reversed.

Choices the spec does not decide (all listed as questions in the piece report):
* ``none`` -> BUY / SELL (the first break) is not an event: S3 says "the side changing from SELL to BUY".
  It does start a stretch, so the first real flip has a counter-move.
* A swing belongs to the stretch when its pivot bar lies in ``[start_pos, event_pos]``.
* ``L*`` among equal extremes = the latest one.
* C4 reads the last two extremes of the whole counter-move (spec C4), not the last two of the C3 run.
* C4 tolerance: ``abs(second - first) <= 0.35 * height``, height must be > 0.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from eye import state11

M15_STEP = pd.Timedelta(minutes=15)
MW_TOLERANCE = 0.35  # C4: the second extreme within 35 % of the pattern's height of the first
BUY = "BUY"
SELL = "SELL"
NONE = "none"


@dataclass(frozen=True)
class Pivot:
    """A fixed swing in absolute frame positions. ``kind`` is "HIGH" or "LOW"."""

    kind: str
    price: float
    pivot_pos: int
    confirm_pos: int


@dataclass(frozen=True)
class Break:
    """A change of strip B's side at the close at ``pos``: S3's event before C2-C4 are read."""

    pos: int
    side: str
    h: float  # the latest fixed swing HIGH (BUY) / LOW (SELL) that close went beyond
    prev_side: str  # B's side before (never "none")
    start_pos: int  # the last close at which B changed to ``prev_side``


@dataclass(frozen=True)
class Event:
    """One S3 event with its C2-C4 fields."""

    pos: int
    time: pd.Timestamp  # the close time
    side: str
    h: float
    start_pos: int
    moves: tuple[Pivot, ...]  # the counter-move's fixed swing LOWs (BUY) / HIGHs (SELL), time order
    extreme: Pivot | None  # L* (BUY: lowest LOW; SELL: highest HIGH)
    count: int  # C3: the run ending at ``extreme`` (0 if no moves)
    shape: bool  # C4: the owner's M (BUY) / W (SELL)


def strip_sides(
    closes: Sequence[float], last_high: Sequence[float | None], last_low: Sequence[float | None]
) -> list[str]:
    """Strip B: per close, above the latest fixed swing HIGH -> BUY, below the latest fixed swing LOW -> SELL,
    else the side stays; "none" before the first break. ``last_high[i]`` / ``last_low[i]`` are the latest
    swing prices fixed by close ``i`` (None if none yet)."""
    side, out = NONE, []
    for c, hi, lo in zip(closes, last_high, last_low, strict=True):
        if hi is not None and c > hi:
            side = BUY
        elif lo is not None and c < lo:
            side = SELL
        out.append(side)
    return out


def find_breaks(
    closes: Sequence[float], last_high: Sequence[float | None], last_low: Sequence[float | None]
) -> list[Break]:
    """S3: every close where B changes between BUY and SELL, with ``H`` and the previous side's start."""
    sides = strip_sides(closes, last_high, last_low)
    out: list[Break] = []
    change_to = 0  # position of the last close at which the side changed (including from "none")
    for i, s in enumerate(sides):
        prev = sides[i - 1] if i else NONE
        if s == prev:
            continue
        if prev != NONE:
            h = last_high[i] if s == BUY else last_low[i]
            if h is None:  # unreachable: the side changed on that very swing
                raise ValueError("a side change needs the swing it broke")
            out.append(Break(i, s, float(h), prev, change_to))
        change_to = i
    return out


def counter_move(pivots: Sequence[Pivot], side: str, start_pos: int, event_pos: int) -> tuple[Pivot, ...]:
    """C2: the fixed swing LOWs (side BUY) / HIGHs (SELL) of the stretch ``start_pos..event_pos``, time order.
    A swing not yet fixed at the event (``confirm_pos > event_pos``) is excluded."""
    kind = "LOW" if side == BUY else "HIGH"
    got = [
        p
        for p in pivots
        if p.kind == kind and start_pos <= p.pivot_pos <= event_pos and p.confirm_pos <= event_pos
    ]
    return tuple(sorted(got, key=lambda p: p.pivot_pos))


def extreme_of(moves: Sequence[Pivot], side: str) -> Pivot | None:
    """``L*``: the lowest LOW (BUY) / highest HIGH (SELL); the latest among equals."""
    best: Pivot | None = None
    for p in moves:
        if best is None or (p.price <= best.price if side == BUY else p.price >= best.price):
            best = p
    return best


def run_count(moves: Sequence[Pivot], side: str) -> int:
    """C3: consecutive lower-or-equal LOWs (BUY) / higher-or-equal HIGHs (SELL) ending at ``L*``."""
    star = extreme_of(moves, side)
    if star is None:
        return 0
    j = list(moves).index(star)
    n = 1
    while j > 0 and (
        moves[j - 1].price >= moves[j].price if side == BUY else moves[j - 1].price <= moves[j].price
    ):
        n += 1
        j -= 1
    return n


def is_mw(moves: Sequence[Pivot], pivots: Sequence[Pivot], side: str) -> bool:
    """C4: the last two extremes of the counter-move make the owner's M (BUY) / W (SELL).

    BUY: height = the highest swing HIGH between the two LOWs minus the higher of them; the second LOW within
    35 % of that height of the first. SELL mirrors: height = the lower of the two HIGHs minus the lowest
    swing LOW between them. ``pivots`` must be only the swings fixed at the event."""
    if len(moves) < 2:
        return False
    a, b = moves[-2], moves[-1]
    other = "HIGH" if side == BUY else "LOW"
    between = [p.price for p in pivots if p.kind == other and a.pivot_pos < p.pivot_pos < b.pivot_pos]
    if not between:
        return False
    height = max(between) - max(a.price, b.price) if side == BUY else min(a.price, b.price) - min(between)
    return height > 0 and abs(b.price - a.price) <= MW_TOLERANCE * height


def build_event(brk: Break, pivots: Sequence[Pivot], time: pd.Timestamp) -> Event:
    """C2-C4 for one break, from the swings fixed at its close."""
    moves = counter_move(pivots, brk.side, brk.start_pos, brk.pos)
    fixed = [p for p in pivots if p.confirm_pos <= brk.pos]
    return Event(
        brk.pos,
        time,
        brk.side,
        brk.h,
        brk.start_pos,
        moves,
        extreme_of(moves, brk.side),
        run_count(moves, brk.side),
        is_mw(moves, fixed, brk.side),
    )


# --- from a frame (uses state11._zigzag, MT5 ZigZag 12/5/3, on the last FRAME_BARS bars at each close) ----


def pivots_at(df: pd.DataFrame, i: int) -> list[Pivot]:
    """The swings fixed by the close at position ``i``, positions absolute in ``df``."""
    lo = max(0, i + 1 - state11.FRAME_BARS)
    return [
        Pivot(p.kind.value, float(p.price), p.pivot_pos + lo, p.confirm_pos + lo)
        for p in state11._zigzag(df.iloc[lo : i + 1])
    ]


def strip_inputs(df: pd.DataFrame) -> tuple[list[float], list[float | None], list[float | None]]:
    """Per close: the close and the latest fixed swing HIGH / LOW price (None if none yet)."""
    closes: list[float] = []
    highs: list[float | None] = []
    lows: list[float | None] = []
    for i in range(len(df)):
        piv = pivots_at(df, i)
        highs.append(next((p.price for p in reversed(piv) if p.kind == "HIGH"), None))
        lows.append(next((p.price for p in reversed(piv) if p.kind == "LOW"), None))
        closes.append(float(df["close"].iloc[i]))
    return closes, highs, lows


def signal_events(df: pd.DataFrame) -> list[Event]:
    """All S3 events of an M15 frame with their C2-C4 fields (closed bars only)."""
    closes, highs, lows = strip_inputs(df)
    idx = pd.DatetimeIndex(df.index)
    return [
        build_event(b, pivots_at(df, b.pos), pd.Timestamp(idx[b.pos] + M15_STEP))
        for b in find_breaks(closes, highs, lows)
    ]


__all__ = [
    "Break",
    "Event",
    "Pivot",
    "build_event",
    "counter_move",
    "extreme_of",
    "find_breaks",
    "is_mw",
    "pivots_at",
    "run_count",
    "signal_events",
    "strip_inputs",
    "strip_sides",
]
