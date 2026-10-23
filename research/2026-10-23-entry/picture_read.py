"""The picture on the entry frames, computed at every step so nothing is left to the eye (owner 2026-10-23: "you
did not even notice three bottoms and then higher lows and higher highs - you must think and process better than a
human brain"). Bars closed by AS_OF only; M5 built from M1.

Per frame (M5 and M15), over the last ``N`` bars:
- swings: a ZigZag of ``SIZE_ATR`` x the frame's ATR(14) (app/strategy/big_trend.py) and the bar-by-bar structure of
  the last bars (each bar's low / high above or below the one before);
- equal lows / highs: swing lows (highs) within ``EQ_ATR`` x ATR of each other -> a double / triple bottom (top);
- a sweep: a bar whose low went under an equal-low cluster (or the last swing low) and closed back above it (the
  mirror on top), and its volume against the frame's mean;
- the range of the last 12 bars against the frame's ATR (a squeeze when small).

    .venv/Scripts/python research/2026-10-23-entry/picture_read.py AS_OF_UTC
"""

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import zone_wait as ZW  # noqa: E402

from app.strategy import big_trend as bt  # noqa: E402
from app.strategy.picture import EQ_ATR, clusters, pools, squeeze_range, sweeps  # noqa: E402,F401  (TAA-1802)
from app.strategy.plan1_b2 import mt5_atr  # noqa: E402

N, SIZE_ATR, TH = 72, 1.0, "Asia/Bangkok"


def frame(minutes: int, as_of: pd.Timestamp) -> pd.DataFrame:
    m1 = ZW.load("M1")
    m1 = m1[(m1.index >= as_of - pd.Timedelta(minutes=minutes * (N + 40))) & (m1.index < as_of)]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}
    return m1.resample(f"{minutes}min").agg(agg).dropna()


def read(minutes: int, as_of: pd.Timestamp) -> list[str]:
    d = frame(minutes, as_of)
    h, lo, c, v = (d[k].to_numpy(float) for k in ("high", "low", "close", "tick_volume"))
    atr = float(mt5_atr(h, lo, c, 14)[-1])
    d, h, lo, c, v = d.iloc[-N:], h[-N:], lo[-N:], c[-N:], v[-N:]
    tt = [x.tz_convert(TH).strftime("%H:%M") for x in d.index]
    pts, leg, ext = bt.zigzag(h, lo, SIZE_ATR * atr)
    out = [f"{minutes}-min frame (ATR {atr:.2f}, swing size {SIZE_ATR * atr:.2f}):"]
    seq = ", ".join(f"{'H' if k == 1 else 'L'} {p:.2f} @{tt[j]}" for j, k, p in pts[-6:])
    out.append(f"  swings: {seq}; running leg {'up' if leg > 0 else 'down' if leg < 0 else '-'} to {ext:.2f}")
    last = 6
    hl = sum(lo[i] > lo[i - 1] for i in range(len(lo) - last + 1, len(lo)))
    hh = sum(h[i] > h[i - 1] for i in range(len(h) - last + 1, len(h)))
    out.append(f"  the last {last} bars: {hl}/{last - 1} higher lows, {hh}/{last - 1} higher highs "
               f"({'UP steps' if hl >= last - 2 and hh >= last - 2 else 'DOWN steps' if hl <= 1 and hh <= 1 else 'mixed'})")
    for pool in pools(h, lo, c, atr):
        name = pool["name"]
        out.append(f"  equal {name} x{len(pool['touches'])} at {pool['mean']:.2f} "
                   f"({', '.join(f'{p:.2f} @{tt[j]}' for j, p in pool['touches'])})")
        for s in sweeps(pool, h, lo, c, v, atr):
            out.append(f"    SWEEP {'under' if name == 'bottoms' else 'over'} it at {tt[s['i']]}: "
                       f"{'low' if name == 'bottoms' else 'high'} {s['extreme']:.2f}, "
                       f"closed back {s['close']:.2f}, volume {s['volume']:.1f} x the mean; since then "
                       f"{s['after']} bars: {s['up']} higher-low-and-higher-high, {s['down']} lower-low-and-lower-high")
    rng = squeeze_range(h, lo, atr)
    out.append(f"  the last 12 bars' range {rng:.1f} ATR{' (a squeeze)' if rng < 3 else ''}; last volume {v[-1] / v.mean():.1f} x the mean")
    return out


if __name__ == "__main__":
    as_of = pd.Timestamp(sys.argv[1], tz="UTC")
    print(f"# The picture at {as_of.tz_convert(TH):%a %d %b %Y %H:%M} Thai\n")
    for minutes in (5, 15):
        print("\n".join(read(minutes, as_of)))
