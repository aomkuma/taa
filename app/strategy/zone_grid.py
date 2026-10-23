"""The owner's gold zone grid (owner 2026-10-22, docs/OWNER_GOALS.md "Gold runs in zones of about 70-90
USD"; ported from research/2026-10-22-zones/zone_grid_v1.py ``daily_grid``; research/2026-10-23-entry/SPEC.md
C5).

- **Impulse:** a closed D1 bar whose body ``|close - open|`` is at least ``IMPULSE`` x the D1 ATR(20) at that
  bar.
- **Anchor (the zone shift):** the base the move left - the highest body edge (max of open / close) of the
  ``BASE_N`` D1 bars before a down impulse, the lowest body edge of them before an up impulse.
- **Step:** the D1 ATR(20) of the last closed D1 bar, every day (the grid breathes); lines = anchor + k x
  step.

A D1 bar's row is known only once the bar has closed (its open + 24 h): :func:`grid_at` never returns the row
of a bar still forming. The ATR is MetaTrader 5's: the simple mean of ``n`` true ranges, the first bar without
a previous close has none (the research version counted that bar's high - low; the two agree from bar ``n``
on, research/2026-10-23-entry/parity_zone_grid.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.strategy.plan1_b2 import mt5_atr

FloatArray = np.ndarray
NS_DAY = 24 * 60 * 60 * 10**9
IMPULSE = 1.5
BASE_N = 2
ATR_N = 20


@dataclass(frozen=True)
class GridRows:
    """One row per D1 bar: when it is known, and the anchor / step / shift in force from then on."""

    known: np.ndarray  # int64 ns: the D1 bar's open + 24 h
    anchor: FloatArray  # NaN until the first impulse
    step: FloatArray  # D1 ATR(20) at the bar (NaN in the warm-up)
    shift: np.ndarray  # +1 an up impulse re-anchored here, -1 a down impulse, 0 none


@dataclass(frozen=True)
class GridState:
    anchor: float
    step: float
    last_shift: int  # the direction of the latest zone shift known (0 before any)
    row: int  # the D1 row in force (-1: none known yet)


def grid_rows(
    t_open: np.ndarray, o: FloatArray, h: FloatArray, lo: FloatArray, c: FloatArray, bar_ns: int = NS_DAY
) -> GridRows:
    """The grid of every bar of the zone timeframe (``t_open`` int64 ns ascending, ``bar_ns`` its length; D1
    by default). Owner 2026-10-23: no timeframe is fixed - the same grid applies to the frame the trade's
    scale calls for."""
    atr = mt5_atr(h, lo, c, ATR_N)
    n = len(c)
    anchor = np.full(n, np.nan)
    shift = np.zeros(n, dtype=np.int64)
    current = math.nan
    for i in range(n):
        body = c[i] - o[i]
        if np.isfinite(atr[i]) and abs(body) >= IMPULSE * atr[i] and i >= BASE_N:
            top = np.maximum(o[i - BASE_N : i], c[i - BASE_N : i])
            bottom = np.minimum(o[i - BASE_N : i], c[i - BASE_N : i])
            current = float(top.max() if body < 0 else bottom.min())
            shift[i] = -1 if body < 0 else 1
        anchor[i] = current
    return GridRows(np.asarray(t_open, dtype=np.int64) + bar_ns, anchor, atr, shift)


def grid_at(rows: GridRows, t: int) -> GridState:
    """The grid in force at ``t`` (int64 ns): the last D1 row known by then."""
    k = int(np.searchsorted(rows.known, t, side="right")) - 1
    if k < 0:
        return GridState(math.nan, math.nan, 0, -1)
    past = np.flatnonzero(rows.shift[: k + 1])
    last = int(rows.shift[past[-1]]) if len(past) else 0
    return GridState(float(rows.anchor[k]), float(rows.step[k]), last, k)


def nearest_line(state: GridState, price: float) -> tuple[float, float, float]:
    """(the nearest grid line, the price's distance to it in USD, that distance as a share of a step: 0 on a
    line, 0.5 mid-zone)."""
    if not (np.isfinite(state.anchor) and np.isfinite(state.step) and state.step > 0):
        return math.nan, math.nan, math.nan
    k = round((price - state.anchor) / state.step)
    line = state.anchor + k * state.step
    dist = abs(price - line)
    return line, dist, dist / state.step


def next_line(state: GridState, price: float, side: int, min_share: float = 0.25) -> float:
    """The first grid line beyond ``price`` in the trade's direction (``side`` +1 up, -1 down), at least
    ``min_share`` of a step away."""
    if not (np.isfinite(state.anchor) and np.isfinite(state.step) and state.step > 0):
        return math.nan
    pos = (price - state.anchor) / state.step
    k = math.floor(pos + min_share) + 1 if side > 0 else math.ceil(pos - min_share) - 1
    return state.anchor + k * state.step
