"""F1 with a FRESH run instead of / beside C4 (owner, 2026-10-18: "do it"; where_base.py: the winners came 1 hour after
the 72-h extreme was made, the mid-range losers 15-18 hours after). Written before computing:
- FRESH(N): the 72-hour extreme in the trade's way (highs for a BUY, over the last 4,320 M1 bars up to the decision
  bar) was made within the last N hours, N = 1, 2, 3, 4, 6, 12.
- A: F1 with FRESH(N) instead of C4.  B: F1 with C4 OR FRESH(N) (the trades it adds to F1 reported apart).
F1 otherwise as frozen (+ the 0.5 M15-ATR floor, C5), one position at a time, real costs. N chosen on design (R >=
+0.10 in >= 4 of 5 halves, the most trades), then the window once.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/fresh_run.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
from portfolio import family_signals  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)
W = 4320


def bars_since_extreme(p: np.ndarray, side: np.ndarray) -> np.ndarray:
    out = np.empty(len(p))
    for i, (q, s) in enumerate(zip(p, side)):
        seg = P.h[q - W + 1 : q + 1] if s > 0 else -P.lo[q - W + 1 : q + 1]
        out[i] = W - 1 - (len(seg) - 1 - np.argmax(seg[::-1]))  # the latest bar at the extreme
    return out


for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C5 not a fast tape"], 2, part).reset_index(drop=True)  # F1 without C4
    S["t"] = pd.to_datetime(S.t, utc=True)
    S["sl"] = np.maximum(S.sl, 0.5 * a15.reindex(S.t, method="ffill").to_numpy())
    S["hrs"] = bars_since_extreme(S.e.to_numpy() - 1, S.side.to_numpy()) / 60
    c4 = plib.MENU["C4 72-h extreme near/behind"](S).to_numpy(bool)
    days = pd.bdate_range(*(("2023-11-01", "2026-02-28") if part == "wdesign" else ("2026-03-01", "2026-10-13"))).size
    f1 = plib.run(S[c4], P)
    f1_t = set(pd.to_datetime(f1.t, utc=True))

    def line(name, z):
        z = z.copy()
        z["t"] = pd.to_datetime(z.t, utc=True)
        if not len(z):
            return f"  {name:26}    0"
        per = plib.by_half(z) if part == "wdesign" else " ".join(
            f"{k[5:]} {v:+.0f}" for k, v in z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum().items())
        return (f"  {name:26} {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}% R {z.R.mean():+.3f}"
                f" USD {z.pnl.sum():+7.1f} | {per}")

    print(f"\n== {'DESIGN' if part == 'wdesign' else 'WINDOW'}  (F1 signals: hours since the extreme, median {S.hrs[c4].median():.1f})")
    print(line("F1 (C4)", f1))
    for n in (1, 2, 3, 4, 6, 12):
        fresh = (S.hrs <= n).to_numpy()
        za = plib.run(S[fresh], P)
        zb = plib.run(S[c4 | fresh], P)
        print(line(f"A FRESH({n}) instead of C4", za))
        print(line(f"B C4 or FRESH({n})", zb))
        added = zb[~pd.to_datetime(zb.t, utc=True).isin(f1_t)]
        print(line("   of which not F1 trades", added))
