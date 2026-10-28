"""Does a market-phase measure, known before the day, tell C4's continuation from its reversal (notes.md "A phase
component for C4", written before computing)? C4 events (the 72-hour extreme the side's way near or behind) every
15th minute of F1's windows, both eras - 2020-09 .. 2023-10 (ranging; C4 turned) and 2023-11 .. 2026-04-17 (trending;
C4 went on) - split by each phase measure's terciles within the era.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/c4_phase.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import foundation as F  # noqa: E402
import plib  # noqa: E402
from c4_old import TP_U, c4_flags  # noqa: E402
from level_power import first_passage  # noqa: E402

ERAS = (("2020-09..2023-10", pd.Timestamp("2020-09-01", tz="UTC"), pd.Timestamp("2023-11-01", tz="UTC")),
        ("2023-11..2026-04-17", pd.Timestamp("2023-11-01", tz="UTC"), plib.EXAM_START))
HZ = 60


def efficiency_ratio(close: np.ndarray, n: int) -> np.ndarray:
    """Kaufman's efficiency ratio: |close - close n bars ago| / the sum of the n absolute bar-to-bar changes (1 = a
    straight line, near 0 = back and forth). NaN for the first n bars."""
    c = np.asarray(close, float)
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    path = pd.Series(np.abs(np.diff(c))).rolling(n).sum().to_numpy()  # path[i-1] = |changes| of bars i-n+1 .. i
    out[n:] = np.abs(c[n:] - c[:-n]) / np.where(path[n - 1:] > 0, path[n - 1:], np.nan)
    return out


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.gold.bars("M1")
    m = m[(m.index >= ERAS[0][1] - pd.Timedelta(days=120)) & (m.index < ERAS[1][2])]
    m = m[~m.index.duplicated(keep="last")]
    t = m.index
    h, lo, c = (m[k].to_numpy(float) for k in ("high", "low", "close"))
    # daily bars on the broker's server day; a day's phase is known from its close on (used from the next day)
    key = t.tz_convert("Europe/Athens").tz_localize(None).normalize()
    d = m.assign(_k=key).groupby("_k").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    dc, dh, dl = d.close.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float)
    phase = pd.DataFrame({"er20": efficiency_ratio(dc, 20), "adx14": F.adx(dh, dl, dc, 14)[2],
                          "dist50": np.abs(dc - F.sma(dc, 50)) / F.atr(dh, dl, dc, 20)}, index=d.index)
    prev = phase.shift(1)  # the last completed day
    hi72 = pd.Series(h).rolling(4305).max().to_numpy()
    lo72 = pd.Series(lo).rolling(4305).min().to_numpy()
    utc = t.hour * 60 + t.minute
    win = np.asarray((utc < 120) | ((utc >= 420) & (utc < 1020))) & np.asarray(t.dayofweek < 5)
    grid = np.asarray(t.minute % 15 == 0)
    rows = []
    kidx = prev.index.get_indexer(key)
    for i in np.nonzero(win & grid & np.asarray(t >= ERAS[0][1]))[0]:
        if i < 4320 or not np.isfinite(hi72[i - 16]) or kidx[i] < 0:
            continue
        unit = c[i] / 4100.0
        dd = TP_U * unit
        fp = first_passage(h, lo, int(i), c[i] + dd, c[i] - dd, HZ)
        if fp == 0:
            continue
        for side in (1, -1):
            near, behind = c4_flags(hi72[i - 16], lo72[i - 16], c[i], unit, side)
            if near or behind:
                ph = prev.iloc[kidx[i]]
                rows.append((t[i], side, fp == side, ph.er20, ph.adx14, ph.dist50))
    R = pd.DataFrame(rows, columns=["t", "side", "went", "er20", "adx14", "dist50"]).dropna()
    pd.set_option("display.width", 200)
    print("C4 events (near or behind), 8 U the side's way first within 60 minutes, by the phase of the day before")
    for name, a, b in ERAS:
        E = R[(R.t >= a) & (R.t < b)]
        print(f"\n{name}: {len(E)} events, its way {E.went.mean():.3f}")
        for col in ("er20", "adx14", "dist50"):
            q = pd.qcut(E[col], 3, labels=["low", "mid", "high"])
            g = E.groupby(q, observed=True).agg(n=("went", "size"), its_way=("went", "mean"), lo=(col, "min"), hi=(col, "max"))
            g["se"] = np.sqrt(g.its_way * (1 - g.its_way) / g.n)
            top, bot = g.loc["high"], g.loc["low"]
            diff_se = (top.its_way - bot.its_way) / np.sqrt(top.se ** 2 + bot.se ** 2)
            print(f"  {col}: high - low = {top.its_way - bot.its_way:+.3f} ({diff_se:+.1f} SE)")
            print(g.round(3).to_string())


if __name__ == "__main__":
    main()
