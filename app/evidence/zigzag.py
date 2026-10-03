"""Online ATR-scaled zigzag: the shared multi-degree pivot engine for swing-based detectors (PLAN §A29).

A leg reverses when price moves against the running extreme by at least ``multiple * ATR[t]``. The extreme is
then confirmed as a pivot **at bar t** (its confirmation bar). The algorithm walks forward bar by bar and
never revisits a decision, so a pivot list computed on a prefix of the data is exactly the prefix of the list
computed on the full data: no look-ahead, no repainting of confirmed pivots. The running (unconfirmed) extreme
of the current leg is never reported as a pivot.

Conventions:
- A bar cannot both extend the leg and reverse it: intrabar order is unknown, so the reversal is checked
  against bars that did not set a new extreme.
- Bars before the ATR warm-up can set extremes but cannot confirm a reversal.
- Pivots strictly alternate HIGH / LOW. Pivots are :class:`~app.indicators.price_action.Swing` records, so the
  structure and S/R helpers of ``app.indicators.price_action`` accept them directly.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.core.errors import ConfigError
from app.indicators.common import FloatArray, as_float, check_aligned
from app.indicators.price_action import Swing, SwingKind


def zigzag(high: pd.Series, low: pd.Series, atr_values: pd.Series, multiple: float) -> list[Swing]:
    """Confirmed alternating pivots, ordered by confirmation position."""
    check_aligned(high, low, atr_values)
    if not (math.isfinite(multiple) and multiple > 0):
        raise ConfigError(f"zigzag multiple must be > 0 (got {multiple!r})")
    h, lo, a = as_float(high), as_float(low), as_float(atr_values)
    index = high.index
    pivots: list[Swing] = []

    def confirm(kind: SwingKind, price: float, pivot_pos: int, confirm_pos: int) -> None:
        pivots.append(Swing(kind, price, pivot_pos, confirm_pos, index[pivot_pos], index[confirm_pos]))

    # Before the first pivot both directions are open: track the highest high and the lowest low.
    hi_pos = lo_pos = -1
    direction = 0  # +1: up leg (extreme is a high), -1: down leg (extreme is a low)
    ext_pos = -1
    for t in range(len(h)):
        ht, lt, thr = h[t], lo[t], multiple * a[t]
        if not (np.isfinite(ht) and np.isfinite(lt)):
            continue
        can_reverse = bool(np.isfinite(thr) and thr > 0)
        if direction == 0:
            new_hi = hi_pos < 0 or ht > h[hi_pos]
            new_lo = lo_pos < 0 or lt < lo[lo_pos]
            rise = can_reverse and not new_lo and ht - lo[lo_pos] >= thr
            fall = can_reverse and not new_hi and h[hi_pos] - lt >= thr
            if rise and (not fall or lo_pos <= hi_pos):
                confirm(SwingKind.LOW, float(lo[lo_pos]), lo_pos, t)
                direction, ext_pos = 1, _argmax_after(h, lo_pos, t)
            elif fall:
                confirm(SwingKind.HIGH, float(h[hi_pos]), hi_pos, t)
                direction, ext_pos = -1, _argmin_after(lo, hi_pos, t)
            else:
                hi_pos = t if new_hi else hi_pos
                lo_pos = t if new_lo else lo_pos
        elif direction > 0:
            if ht > h[ext_pos]:
                ext_pos = t
            elif can_reverse and h[ext_pos] - lt >= thr:
                confirm(SwingKind.HIGH, float(h[ext_pos]), ext_pos, t)
                direction, ext_pos = -1, _argmin_after(lo, ext_pos, t)
        else:
            if lt < lo[ext_pos]:
                ext_pos = t
            elif can_reverse and ht - lo[ext_pos] >= thr:
                confirm(SwingKind.LOW, float(lo[ext_pos]), ext_pos, t)
                direction, ext_pos = 1, _argmax_after(h, ext_pos, t)
    return pivots


def _argmax_after(values: FloatArray, start: int, end: int) -> int:
    """Position of the highest value in ``(start, end]``: the extreme of the leg that just began."""
    return start + 1 + int(np.nanargmax(values[start + 1 : end + 1]))


def _argmin_after(values: FloatArray, start: int, end: int) -> int:
    return start + 1 + int(np.nanargmin(values[start + 1 : end + 1]))
