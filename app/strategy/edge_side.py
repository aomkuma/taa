"""Which side has the edge on a timeframe LARGER than the one the trade is entered on.

The owner's rule, 2026-10-27: *"every trade takes only the side with the edge on a timeframe larger than
the entry timeframe"*, and their correction the same day: *"D1 should not be that rigid - it is a
quantity, not a gate; the more momentum there is, the further that side runs."*

So the frame's lean is read as a **number**, not a label: the close's distance from its own 50-bar mean,
in that frame's own 14-bar ATR, signed (positive = leaning up). A trade is allowed when the lean is on
its side; the threshold is zero, not a fitted number.

**The frame is H4, measured** (`research/2026-10-26-three-bots/RULES_LOCKED.md`, rule set 2; 239 trades,
2023-09 .. 2026-10-24). Correlation of "lean behind the trade" with the trade's R: H4 +0.156, H1 +0.048,
D1 +0.030 - the middle frame carries it, nearer than the day and slower than the hour. Requiring the H4
lean to be on the trade's side moves the three bots from +0.102 to +0.210 R a trade, and the two halves
of the history agree to 0.007 R (+0.214 fitted, +0.207 never seen) - the reason this rule was taken and
an H1 one was not.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import pandas as pd

from app.core.enums import Side, Timeframe
from app.indicators.volatility import atr

MEAN_BARS = 50
ATR_BARS = 14
HOURS = {Timeframe.H1: 1, Timeframe.H4: 4, Timeframe.D1: 24}


def resample_from_h1(h1: pd.DataFrame, hours: int) -> pd.DataFrame:
    """Bars of ``hours`` from the lane's H1 frame, indexed by each bar's OPEN.

    App frames are stamped at the bar's CLOSE, so the index is shifted back one hour first; the research
    harness reads history stamped at the open and shifts nothing. Getting this backwards costs an hour of
    lookahead, which is how a day of conclusions went wrong on 2026-10-27.
    """
    opens = h1.copy()
    opens.index = pd.DatetimeIndex(opens.index) - pd.Timedelta(hours=1)
    rule = f"{hours}h" if hours < 24 else "1D"
    return opens.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def edge_lean(
    frames: Mapping[Timeframe, pd.DataFrame],
    at: pd.Timestamp,
    entry: Timeframe,
    *,
    frame: Timeframe = Timeframe.H4,
) -> float | None:
    """The signed lean of ``frame``, or ``None`` when it cannot be read from a closed bar.

    ``None`` never means "allowed": a caller that cannot read the frame above its entry has no edge side
    and does not trade. ``entry`` must be smaller than ``frame`` - the rule is meaningless otherwise, and
    a ``ValueError`` here stops it being read from the entry frame by accident.
    """
    if entry.seconds >= frame.seconds:
        raise ValueError(f"the entry frame {entry.value} must be smaller than {frame.value}")
    hours = HOURS.get(frame)
    if hours is None:
        raise ValueError(f"{frame.value} is not read from the H1 frame")

    h1 = frames.get(Timeframe.H1)
    if h1 is None or "close" not in h1:
        return None
    bars = resample_from_h1(h1, hours)
    closed = bars[(bars.index + pd.Timedelta(hours=hours)) <= pd.Timestamp(at)]
    if len(closed) < MEAN_BARS + ATR_BARS:
        return None
    mean = float(closed.close.rolling(MEAN_BARS).mean().iloc[-1])
    width = float(atr(closed.high, closed.low, closed.close, ATR_BARS).iloc[-1])
    if not math.isfinite(mean) or not math.isfinite(width) or width <= 0:
        return None
    lean = (float(closed.close.iloc[-1]) - mean) / width
    # A non-finite lean must never reach a caller: `nan < 0` is False, so a NaN would sail through a
    # gate written as "refuse when the lean is negative" and open a trade on no evidence at all
    # (found by the developer session reviewing this gate while it was live, 2026-10-27).
    # It IS reachable, though I first wrote that it was not: a finite, positive but tiny ATR (1e-320)
    # overflows the division to infinity while passing both guards above. The developer session found
    # that and was right (2026-10-27); the case now has its own test.
    return lean if math.isfinite(lean) else None


def behind(lean: float | None, side: Side) -> float | None:
    """``lean`` seen from a trade's own side: positive means the frame leans the trade's way."""
    if lean is None:
        return None
    return lean if side is Side.BUY else -lean


def edge_side(
    frames: Mapping[Timeframe, pd.DataFrame],
    at: pd.Timestamp,
    entry: Timeframe,
    *,
    frame: Timeframe = Timeframe.H4,
) -> Side | None:
    """The side ``frame`` leans towards, for callers that want one answer rather than the number.

    A lean of exactly zero is on neither side and returns ``None``; the measured rule is "at least 0 on
    the trade's own side", so a strategy that cares about that boundary uses :func:`behind` instead.
    """
    lean = edge_lean(frames, at, entry, frame=frame)
    if lean is None or lean == 0:
        return None
    return Side.BUY if lean > 0 else Side.SELL
