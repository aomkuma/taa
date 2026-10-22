"""climax.py read 2, closer to the owner's picture of a turn: a move runs into a zone-grid line (the last 10 bars moved
>= 0.5 D1 ATR toward it), the bar at the line rejects it (wick >= half the bar, close back) on the highest tick volume
of those 10 bars (a climax), and the next bar confirms (closes beyond the rejection bar's middle). The 6 / 12 bars
after the confirmation in the turn's direction (D1 ATR), by volatility, on M15 / H1 / H4. Closed bars, up to END.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_b2/climax2.py 2026-03-21
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import week as W


def turns(tf: str, end: pd.Timestamp) -> pd.DataFrame:
    b = W.Z.bars(tf)
    b = b[(b.index < end) & (b.index >= "2023-08-01")].copy()
    g = W.Z.daily_grid(W.Z.bars("D1"))
    k = g.index.searchsorted(b.index, side="right") - 1
    b, k = b[k >= 0], k[k >= 0]
    anc, stp = g.anchor.values[k], g.step.values[k]
    pc = b.close.shift(1)
    atr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1).rolling(14).mean()
    vol = (atr / atr.rolling(int(20 * 24 * {"M15": 4, "H1": 1, "H4": 0.25}[tf]), min_periods=50).median()).values
    hi, lo, op, cl, tv = b.high.values, b.low.values, b.open.values, b.close.values, b.tick_volume.values
    rows = []
    for i in range(10, len(b) - 13):
        if not (np.isfinite(stp[i]) and np.isfinite(vol[i])) or hi[i] == lo[i]:
            continue
        rng, band = hi[i] - lo[i], 0.15 * stp[i]
        climax = tv[i] >= tv[i - 10 : i].max()
        if not climax:
            continue
        for side in (-1, 1):
            ext = hi[i] if side < 0 else lo[i]
            line = anc[i] + np.round((ext - anc[i]) / stp[i]) * stp[i]
            run_in = (ext - cl[i - 10]) * -side / stp[i]  # the move into the line (positive = toward it)
            wick = (hi[i] - max(op[i], cl[i])) if side < 0 else (min(op[i], cl[i]) - lo[i])
            at = abs(ext - line) <= band and (cl[i] - line) * side > -band
            if not (at and run_in >= 0.5 and wick >= 0.5 * rng):
                continue
            mid = (hi[i] + lo[i]) / 2
            if (cl[i + 1] - mid) * side <= 0:  # no confirmation
                continue
            rows.append(dict(tf=tf, side=side, vol=vol[i], f6=(cl[i + 7] - cl[i + 1]) * side / stp[i],
                             f12=(cl[i + 13] - cl[i + 1]) * side / stp[i]))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    e = pd.Timestamp(sys.argv[1], tz="UTC")
    R = pd.concat([turns(tf, e) for tf in ("M15", "H1", "H4")])
    R["hv"] = pd.cut(R.vol, [0, 0.9, 1.1, 1.4, np.inf])
    out = R.groupby(["tf", "hv"], observed=True).agg(n=("f6", "size"), next6=("f6", "mean"), turn6=("f6", lambda s: (s > 0).mean() * 100),
                                                    next12=("f12", "mean"), turn12=("f12", lambda s: (s > 0).mean() * 100))
    print(out.round(3).to_string())
    for side, n in ((-1, "sell turns at resistance"), (1, "buy turns at support")):
        s = R[R.side == side]
        print(f"{n}: {len(s)} next6 {s.f6.mean():+.3f} ({(s.f6 > 0).mean() * 100:.0f} %), next12 {s.f12.mean():+.3f} ({(s.f12 > 0).mean() * 100:.0f} %)")
