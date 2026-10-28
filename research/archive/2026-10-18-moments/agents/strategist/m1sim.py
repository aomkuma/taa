"""Row 45 - an M1-bar trade simulator with the spread only (owner, 2026-10-20: the cost is the bid / ask spread;
slippage is a parameter defaulting to 0). Used for the older years O1 / O2, where there are no ticks.

Bars are bid bars; the ask = bid + spr (spr = the M1 spread column x 0.01 + 0.08, the team's M1 spread model). A buy
enters at bar i_in's open ask + slip, a sell at its open bid - slip. The stop fills at the stop -/+ slip_stop, or at
the bar's open when that bar opened past it (a gap; not on the entry bar). The target is a limit filled at its level.
A bar reaching both: the stop. The time exit: the close of bar i_last (the bid for a buy, the ask for a sell).
"""

from __future__ import annotations


def trade(o, h, lo, c, spr, i_in: int, side: int, stop: float, target: float | None, i_last: int,
          slip: float = 0.0, slip_stop: float = 0.0):
    """Returns (pnl, risk, exit, i_exit) or None (no bar, or the fill is at / past the stop)."""
    if i_in >= len(o) or i_last < i_in:
        return None
    entry = o[i_in] + spr[i_in] + slip if side > 0 else o[i_in] - slip
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    last = min(i_last, len(o) - 1)
    for k in range(i_in, last + 1):
        if side > 0:
            if lo[k] <= stop:
                px = (min(o[k], stop) if k > i_in else stop) - slip_stop
                return px - entry, risk, "stop", k
            if target is not None and h[k] >= target:
                return target - entry, risk, "target", k
        else:
            if h[k] + spr[k] >= stop:
                px = (max(o[k] + spr[k], stop) if k > i_in else stop) + slip_stop
                return entry - px, risk, "stop", k
            if target is not None and lo[k] + spr[k] <= target:
                return entry - target, risk, "target", k
    px = c[last] if side > 0 else c[last] + spr[last]
    return (px - entry) * side, risk, "time", last
