"""Owner 2026-10-22: "a reversal on any timeframe = at resistance (support), price action, volume, with high
volatility - that is when it has a chance to turn." Two reads, closed bars only, nothing after END:

1. the NY-B2 trades (a level + a pattern already): the tick volume of the last 30 minutes before the entry against
   the same half hour of the 20 days before (climax), split by the H1 volatility (vol = H1 ATR(14) / its 20-day median)
2. every H1 bar 2023-08 .. END that touches a line of the owner's zone grid (band +-0.15 step) and rejects it (the
   close back on the near side, the wick through >= half the range) - the next 3 / 6 H1 bars in the turn's
   direction (D1 ATR), split by the bar's tick volume (vs the same hour of the 20 days before) and the volatility

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/climax.py 2026-03-21
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import week as W


def b2(end: pd.Timestamp) -> None:
    X = W.load()
    X = X[X.t < end].sort_values("t").copy()
    X["r"] = W.realistic(X)
    X = X.join(W.pressure(X))
    m5 = W.Z.bars("M5")
    m5 = m5[m5.index < end]
    m5["hm"] = m5.index.hour * 60 + m5.index.minute
    m5["d"] = m5.index.normalize()
    cl = []
    for t in X.t:
        last = m5[(m5.index + pd.Timedelta(minutes=5) <= t) & (m5.index + pd.Timedelta(minutes=35) > t)]
        hm = set(last.hm)
        past = m5[(m5.d < t.normalize()) & (m5.d >= t.normalize() - pd.Timedelta(days=28)) & m5.hm.isin(hm)]
        usual = past.groupby("d").tick_volume.sum().tail(20).mean()
        cl.append(last.tick_volume.sum() / usual if usual else np.nan)
    X["climax"] = cl
    X["hv"] = np.where(X.vol > 1.1, "vol>1.1", "vol<=1.1")
    X["cv"] = pd.cut(X.climax, [0, 1.0, 1.5, np.inf], labels=["volume<1", "1-1.5", "volume>1.5"])
    g = X.groupby(["hv", "cv"], observed=True).agg(n=("r", "size"), base=("r_multiple", "sum"), real=("r", "sum"), win=("r", lambda s: (s > 0).mean() * 100))
    print("1. NY-B2 trades: the last 30 min's tick volume vs usual, by volatility (realistic, unfiltered)")
    print(g.round(2).to_string())


def h1_turns(end: pd.Timestamp) -> None:
    h1 = W.Z.bars("H1")
    h1 = h1[h1.index < end].copy()
    g = W.Z.daily_grid(W.Z.bars("D1"))
    k = g.index.searchsorted(h1.index, side="right") - 1
    ok = k >= 0
    h1, k = h1[ok], k[ok]
    anc, stp = g.anchor.values[k], g.step.values[k]
    pc = h1.close.shift(1)
    atr = pd.concat([h1.high - h1.low, (h1.high - pc).abs(), (h1.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    vol = (atr / atr.rolling(480, min_periods=100).median()).values
    hr = h1.index.hour
    tv = h1.tick_volume
    usual = tv.groupby(hr).transform(lambda s: s.shift(1).rolling(20, min_periods=10).mean()).values
    rel = tv.values / usual
    rng = (h1.high - h1.low).values
    rows = []
    hi, lo, op, cl = h1.high.values, h1.low.values, h1.open.values, h1.close.values
    for i in range(len(h1) - 6):
        if not (np.isfinite(stp[i]) and np.isfinite(vol[i]) and np.isfinite(rel[i]) and rng[i] > 0):
            continue
        band = 0.15 * stp[i]
        j = np.round((np.array([hi[i], lo[i]]) - anc[i]) / stp[i])
        for line in {anc[i] + j[0] * stp[i], anc[i] + j[1] * stp[i]}:
            if hi[i] >= line - band and cl[i] < line - 0 and (hi[i] - max(op[i], cl[i])) >= 0.5 * rng[i]:
                side = -1  # rejected from above: a sell turn at resistance
            elif lo[i] <= line + band and cl[i] > line and (min(op[i], cl[i]) - lo[i]) >= 0.5 * rng[i]:
                side = 1
            else:
                continue
            f3 = (cl[i + 3] - cl[i]) * side / stp[i]
            f6 = (cl[i + 6] - cl[i]) * side / stp[i]
            rows.append(dict(side=side, vol=vol[i], rel=rel[i], f3=f3, f6=f6))
            break
    R = pd.DataFrame(rows)
    R["hv"] = pd.cut(R.vol, [0, 0.9, 1.1, 1.4, np.inf])
    R["tv"] = pd.cut(R.rel, [0, 1.0, 1.5, np.inf], labels=["volume<1", "1-1.5", "volume>1.5"])
    out = R.groupby(["hv", "tv"], observed=True).agg(n=("f3", "size"), next3=("f3", "mean"), turn3=("f3", lambda s: (s > 0).mean() * 100),
                                                     next6=("f6", "mean"), turn6=("f6", lambda s: (s > 0).mean() * 100))
    print("\n2. H1 rejections of a zone-grid line (wick >= half the bar, close back), 2023-08 .. END:"
          " the next 3 / 6 H1 closes in the turn's direction (D1 ATR) and how often they turned")
    print(out.round(3).to_string())
    print(f"all {len(R)}: next3 {R.f3.mean():+.3f} ({(R.f3 > 0).mean() * 100:.0f} %), next6 {R.f6.mean():+.3f} ({(R.f6 > 0).mean() * 100:.0f} %)")


if __name__ == "__main__":
    e = pd.Timestamp(sys.argv[1], tz="UTC")
    b2(e)
    h1_turns(e)
