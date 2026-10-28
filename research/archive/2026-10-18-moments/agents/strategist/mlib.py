"""A small M1-bar trade simulator for the strategist's quick checks (DEV_PROMPT section 3, "on M1 only"): bars are
bid bars; the ask = bid + (spread column x 0.01 + 0.08); a buy enters at the next bar's open ask + 0.07, a sell at
the next bar's open bid - 0.07; the stop fills at the stop -/+ 0.15 (0.20 inside the NY window) or at the bar's open
when the bar gaps past it; the target fills at the target (a limit); a bar reaching both = the stop; the time exit at
the close of the last bar (bid for a buy, ask for a sell). Quick checks only - the developers re-run on the ticks.
"""

from __future__ import annotations

import numpy as np


def trade(o, h, lo, c, spr, i_in: int, side: int, stop: float, target: float | None, i_last: int, slip_stop: float = 0.15):
    """Enter at bar i_in's open; manage through bar i_last (inclusive). Returns (pnl, risk, exit, i_exit) or None."""
    if i_in >= len(o) or i_last < i_in:
        return None
    entry = o[i_in] + spr[i_in] + 0.07 if side > 0 else o[i_in] - 0.07
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    for k in range(i_in, min(i_last, len(o) - 1) + 1):
        if side > 0:
            lo_k, hi_k, op = lo[k], h[k], o[k]
            if lo_k <= stop:
                px = min(op, stop) - slip_stop if k > i_in else stop - slip_stop
                return (px - entry), risk, "stop", k
            if target is not None and hi_k >= target:
                return (target - entry), risk, "target", k
        else:
            lo_k, hi_k, op = lo[k] + spr[k], h[k] + spr[k], o[k] + spr[k]
            if hi_k >= stop:
                px = max(op, stop) + slip_stop if k > i_in else stop + slip_stop
                return (entry - px), risk, "stop", k
            if target is not None and lo_k <= target:
                return (entry - target), risk, "target", k
    k = min(i_last, len(o) - 1)
    px = c[k] if side > 0 else c[k] + spr[k]
    return (px - entry) * side, risk, "time", k
