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

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import zone_wait as ZW  # noqa: E402

from app.strategy import big_trend as bt  # noqa: E402
from app.strategy.plan1_b2 import mt5_atr  # noqa: E402

N, SIZE_ATR, EQ_ATR, TH = 72, 1.0, 0.35, "Asia/Bangkok"


def frame(minutes: int, as_of: pd.Timestamp) -> pd.DataFrame:
    m1 = ZW.load("M1")
    m1 = m1[(m1.index >= as_of - pd.Timedelta(minutes=minutes * (N + 40))) & (m1.index < as_of)]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "tick_volume": "sum"}
    return m1.resample(f"{minutes}min").agg(agg).dropna()


def clusters(points: list[tuple[int, float]], tol: float) -> list[list[tuple[int, float]]]:
    out: list[list[tuple[int, float]]] = []
    for p in sorted(points, key=lambda x: x[1]):
        if out and abs(p[1] - np.mean([q[1] for q in out[-1]])) <= tol:
            out[-1].append(p)
        else:
            out.append([p])
    return [c for c in out if len(c) >= 2]


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


def pools(h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr: float) -> list[dict]:
    """Equal bottoms / tops near price: bar lows (highs) lower (higher) than both neighbours, clustered within
    ``EQ_ATR`` x ATR; kept when within 2.5 ATR of the last close, touched in the last 36 bars, the touches 3+ bars
    apart. ``level`` = the cluster's extreme (the pool's edge)."""
    # bars' own lows also count as touches of a floor (a swing ZigZag can merge close bottoms)
    bar_lows = [(i, lo[i]) for i in range(1, len(lo) - 1) if lo[i] <= lo[i - 1] and lo[i] <= lo[i + 1]]
    bar_highs = [(i, h[i]) for i in range(1, len(h) - 1) if h[i] >= h[i - 1] and h[i] >= h[i + 1]]
    price = float(c[-1])
    out = []
    for name, pp in (("bottoms", bar_lows), ("tops", bar_highs)):
        for cl in clusters(pp, EQ_ATR * atr):
            cl = sorted(cl)
            mean = float(np.mean([p for _, p in cl]))
            if abs(mean - price) > 2.5 * atr or cl[-1][0] < len(c) - 36 or cl[-1][0] - cl[0][0] < 3:
                continue
            level = min(p for _, p in cl) if name == "bottoms" else max(p for _, p in cl)
            out.append({"name": name, "mean": mean, "touches": cl, "level": float(level)})
    return out


def sweeps(pool: dict, h: np.ndarray, lo: np.ndarray, c: np.ndarray, v: np.ndarray, atr: float) -> list[dict]:
    """The bars after the pool's last touch that came from inside it, went 0.1 ATR beyond its edge and closed back;
    with the bar's volume over the frame's mean and the bar-by-bar structure since."""
    level, bottoms = pool["level"], pool["name"] == "bottoms"
    out = []
    for i in range(pool["touches"][-1][0] + 1, len(c)):
        came = c[i - 1] > level if bottoms else c[i - 1] < level
        swept = lo[i] < level - 0.1 * atr and c[i] > level if bottoms else h[i] > level + 0.1 * atr and c[i] < level
        if came and swept:
            after = range(i + 1, len(c))
            out.append({"i": i, "extreme": float(lo[i] if bottoms else h[i]), "close": float(c[i]),
                        "volume": float(v[i] / v.mean()), "after": len(after),
                        "up": sum(lo[k] > lo[k - 1] and h[k] > h[k - 1] for k in after),
                        "down": sum(lo[k] < lo[k - 1] and h[k] < h[k - 1] for k in after)})
    return out


def squeeze_range(h: np.ndarray, lo: np.ndarray, atr: float, n: int = 12) -> float:
    """The last ``n`` bars' high-low range in ATR (under 3 = a squeeze)."""
    return float((h[-n:].max() - lo[-n:].min()) / atr)


if __name__ == "__main__":
    as_of = pd.Timestamp(sys.argv[1], tz="UTC")
    print(f"# The picture at {as_of.tz_convert(TH):%a %d %b %Y %H:%M} Thai\n")
    for minutes in (5, 15):
        print("\n".join(read(minutes, as_of)))
