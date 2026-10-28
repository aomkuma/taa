"""Owner, 2026-10-18: "the scratched trades - later, does price turn our way or keep going the way it ran?" For F1 v2's
10-bar scratches (design + window): what price did after the scratch, from the entry: which comes first, the 8 U
target or the original stop (no time limit, up to 8 hours), and the move at +30/60/120/240 minutes.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/f1_scratch_after.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/weapon4"))
import w4lib as w  # noqa: E402

P = w.instr("XAUUSD")
rows = []
for tag, per in (("design", w.DESIGN), ("window", w.WINDOW)):
    D = w.build(P, 1, *per, [(0, 20)], f"XAUUSD_M1_{tag}_fr")
    h = pd.DatetimeIndex(D.t).hour
    S = w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60)
    z = w.run_v2(S, P)
    for r in z[z.exit == "scratch"].itertuples():
        e, s = int(r.e), int(r.side)
        entry = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
        stop, tp = entry - s * r.sl, entry + s * r.tp
        first, at = "neither", None
        for j in range(e, min(e + 480, len(P.o))):
            adv = P.lo[j] if s > 0 else P.h[j] + P.sp[j]
            fav = P.h[j] if s > 0 else P.lo[j] + P.sp[j]
            if (adv - stop) * s <= 0:
                first, at = "stop", j - e + 1
                break
            if (fav - tp) * s >= 0:
                first, at = "target", j - e + 1
                break
        mv = {f"m{k}": (P.c[min(e + 9 + k, len(P.c) - 1)] - entry) * s / r.unit for k in (30, 60, 120, 240)}
        rows.append(dict(set=tag, t=r.t, usd=r.usd, first=first, mins=at, sl_u=r.sl / r.unit, **mv))
x = pd.DataFrame(rows)
print(f"scratched trades: {len(x)} (design {sum(x.set == 'design')}, window {sum(x.set == 'window')}); "
      f"scratch loss avg {x.usd.mean():+.2f} USD; the stop avg {x.sl_u.mean():.1f} U")
print("first after the entry, up to 8 hours:", x["first"].value_counts().to_dict())
for k, g in x.groupby("first"):
    print(f"  {k:8} {len(g):3}  median minutes {g.mins.median() if g.mins.notna().any() else float('nan'):.0f}")
print("price vs the entry after the scratch (U, + = our way): median / share above 0")
for k in (30, 60, 120, 240):
    print(f"  +{k:3} min  {x[f'm{k}'].median():+5.1f} U  {np.mean(x[f'm{k}'] > 0):4.0%}")
