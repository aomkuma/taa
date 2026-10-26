"""The signal at the level that confirms an armed AI order (owner 2026-10-26: "wait for the chart to confirm
before entering, not at the first moment price gets there"; "a signal at the level, not a 1-minute close";
"candlestick patterns confirm on 15 minutes to 1 hour; a price structure is read on M1, bar after bar, until
it matches the pattern"; then "enter on M5 instead of M1").

From the bar in which the order's price was first reached, whichever comes first:

- the price structure on complete M5 bars, read at every M5 close:
  - ``sweep`` (a limit): price went more than 0.1 ATR past the level, the extreme bar's tick volume over the
    mean, and the last bar closed back on the trade's side (B3 / W07);
  - ``double`` (a limit): an M / W - the highest push since the touch at the level band, a pullback, a later
    push no higher and back at least half way up, then a close through the pullback's extreme (the neckline);
  - ``break`` (a stop order): an M5 bar closing through the level - not the first tick through it. The
    retest it once also needed missed two of the five with-D1 sell stops of 06-08 Jul, which all reached
    their take-profit (research/2026-10-24-replay/out_regime_orders.txt);
- a candlestick pattern on complete M15, M30 or H1 bars (a limit):
  - ``pin``: a bar that reached the level (within 0.1 ATR) closed back on the trade's side, against its own
    open, with the wick toward the level at least half the bar's range;
  - ``engulfing``: at the level, a bar against the previous one whose body covers that bar's body, closing on
    the trade's side.

Bars are indexed by their open; only bars closed by ``as_of`` count (no look-ahead). A buy is read as the
sell's mirror: every price negated.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from app.core.clock import ensure_utc

STRUCTURE_FRAME = 5  # minutes: the price structure is read on these bars (owner 2026-10-26: M5, not M1)
CANDLE_FRAMES = (15, 30, 60)  # minutes: candlestick patterns confirm on these
TOUCH_ATR = 0.1  # the level is a band: within this many ATRs counts as reached
SWEEP_ATR = 0.1  # past the level by more than this: a sweep (behaviors.level_sweep)
VOLUME_BARS = 24  # the mean tick volume of this many bars before the touch bar
ATR_BARS = 14


def complete(m1: pd.DataFrame, as_of: datetime, minutes: int) -> pd.DataFrame:
    """Complete ``minutes`` bars (open-time index) from M1 bars (open-time index) closed by ``as_of``."""
    at = pd.Timestamp(ensure_utc(as_of))
    x = m1[m1.index + pd.Timedelta(minutes=1) <= at]
    if minutes == 1 or not len(x):
        return x
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}
    bars = x.resample(f"{minutes}min").agg(agg).dropna()
    return bars[bars.index + pd.Timedelta(minutes=minutes) <= at]


def mean_range(bars: pd.DataFrame, n: int = ATR_BARS) -> float:
    """The mean true range of the last ``n`` bars."""
    h, lo, c = (bars[k].to_numpy(float) for k in ("high", "low", "close"))
    if not len(h):
        return 0.0
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - lo, np.maximum(abs(h - prev), abs(lo - prev)))
    tr[0] = h[0] - lo[0]
    return float(tr[-n:].mean())


def _split(
    bars: pd.DataFrame, touched: datetime, minutes: int, level: float, sell: bool
) -> tuple[pd.DataFrame, dict[str, np.ndarray], float, float] | None:
    """(the bars before the touch bar, the bars since it as a sell sees them - buy prices negated - the level
    so seen, the ATR), or None when there is nothing to read."""
    start = pd.Timestamp(ensure_utc(touched)).floor(f"{minutes}min")
    before, since = bars[bars.index < start], bars[bars.index >= start]
    if not len(since) or len(before) < 2:
        return None
    a = mean_range(pd.concat([before, since]))
    if a <= 0:
        return None
    sg = 1.0 if sell else -1.0  # a sell's 'past' is above the level; a buy is the mirror
    x = {
        "o": sg * since.open.to_numpy(float),
        "c": sg * since.close.to_numpy(float),
        "hi": since.high.to_numpy(float) if sell else -since.low.to_numpy(float),
        "lo": since.low.to_numpy(float) if sell else -since.high.to_numpy(float),
        "v": since.tick_volume.to_numpy(float),
    }
    return before, x, sg * level, a


def structure_signal(m5: pd.DataFrame, touched: datetime, level: float, sell: bool, kind: str) -> str | None:
    """The price structure at ``level`` on complete M5 bars since the touch (see the module), or None.
    ``kind``: 'limit' (a turn at the level) or 'stop' (a break of it)."""
    got = _split(m5, touched, STRUCTURE_FRAME, level, sell)
    if got is None:
        return None
    before, x, lv, a = got
    hi, lo, c = x["hi"], x["lo"], x["c"]
    if kind == "stop":
        return "break" if bool((c < lv).any()) else None
    vmean = float(before.tick_volume.to_numpy(float)[-VOLUME_BARS:].mean())
    ext = int(np.argmax(hi))
    if hi[ext] > lv + SWEEP_ATR * a and x["v"][ext] > vmean and c[-1] < lv:
        return "sweep"
    return "double" if _double(hi, lo, c, lv, a) else None


def candle_signal(
    bars: pd.DataFrame, touched: datetime, minutes: int, level: float, sell: bool
) -> str | None:
    """A candlestick pattern at ``level`` on complete ``minutes`` bars since the touch (see the module)."""
    got = _split(bars, touched, minutes, level, sell)
    if got is None:
        return None
    _, x, lv, a = got
    o, hi, lo, c = x["o"], x["hi"], x["lo"], x["c"]
    at = hi >= lv - TOUCH_ATR * a  # the bars that reached the level band
    for i in range(len(c)):
        rng = hi[i] - lo[i]
        if at[i] and c[i] < lv and c[i] < o[i] and rng > 0 and hi[i] - max(o[i], c[i]) >= 0.5 * rng:
            return "pin"
    for i in range(1, len(c)):
        covers = o[i] >= c[i - 1] and c[i] <= o[i - 1]
        if (at[i] or at[i - 1]) and c[i - 1] > o[i - 1] and c[i] < o[i] and covers and c[i] < lv:
            return "engulfing"
    return None


def _double(hi: np.ndarray, lo: np.ndarray, c: np.ndarray, lv: float, a: float) -> bool:
    """An M (a buy's W arrives negated): for a second push k, the highest push p before it (at the level
    band), the pullback low between, k no higher than p and back at least half way up, then a close under that
    low."""
    n = len(c)
    after = np.minimum.accumulate(c[::-1])[::-1]  # after[i]: the lowest close from bar i on
    for k in range(2, n - 1):
        p = int(np.argmax(hi[: k - 1]))
        if hi[p] < lv - TOUCH_ATR * a:
            continue
        trough = float(lo[p + 1 : k].min())
        if trough + 0.5 * (hi[p] - trough) <= hi[k] <= hi[p] and after[k + 1] < trough:
            return True
    return False


def signal(
    m1: pd.DataFrame, as_of: datetime, touched: datetime, level: float, sell: bool, kind: str
) -> str | None:
    """The first signal: the M5 structure, then a candle on M15 / M30 / H1 (a limit); 'M5 sweep' / 'M15 pin'
    ... or None."""
    got = structure_signal(complete(m1, as_of, STRUCTURE_FRAME), touched, level, sell, kind)
    if got is not None:
        return f"M{STRUCTURE_FRAME} {got}"
    if kind == "stop":
        return None
    for minutes in CANDLE_FRAMES:
        found = candle_signal(complete(m1, as_of, minutes), touched, minutes, level, sell)
        if found is not None:
            return f"{'H1' if minutes == 60 else f'M{minutes}'} {found}"
    return None
