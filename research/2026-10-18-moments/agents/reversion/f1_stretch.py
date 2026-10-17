"""F1: after a stretched move, does gold revert? Development half-years only (before 2026-03-01).

z_k = (close_i - close_{i-k}) / (sigma1 * sqrt(k)), sigma1 = std of 1-minute close changes over the 60 bars to i.
Fade return over h minutes = -sign(z) * (close_{i+h} - close_i), price-scaled to 4100 USD gold. Gross of costs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from common import DEV, REF, Bars, gold, h1_trend, rstd

gold.below_normal_priority()
B = Bars()
d1 = np.r_[0.0, np.diff(B.c)]
sig = rstd(d1, 60)
ses = B.session()
tr = h1_trend(B)
scale = REF / B.c
rows = []
for k in (1, 3, 5, 10, 15):
    ok = B.contiguous(k)
    mv = np.full(B.n, np.nan)
    mv[k:] = B.c[k:] - B.c[:-k]
    z = mv / (sig * np.sqrt(k))
    for h in (5, 15, 30, 60):
        fw = np.full(B.n, np.nan)
        fw[:-h] = B.c[h:] - B.c[:-h]
        okh = np.zeros(B.n, bool)
        okh[:-h] = B.contiguous(h)[h:]
        for thr in (2.0, 3.0):
            sel = ok & okh & (np.abs(z) >= thr) & np.isfinite(fw)
            fade = -np.sign(z) * fw * scale
            for name, a, b in DEV:
                ia, ib = B.idx(a), B.idx(b)
                m = np.zeros(B.n, bool)
                m[ia:ib] = True
                for s in (0, 1, 2, 9):
                    mm = sel & m & ((ses == s) if s != 9 else True)
                    x = fade[mm]
                    # with the H1 trend: the fade is a buy dip in an uptrend (z<0, tr>0) or sell rally in a downtrend
                    w = mm & (-np.sign(z) == tr)
                    rows.append(dict(k=k, h=h, thr=thr, half=name[:2], ses=s, n=len(x), mean=x.mean() if len(x) else np.nan,
                                     t=x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 2 else np.nan,
                                     n_tr=w.sum(), mean_tr=fade[w].mean() if w.sum() else np.nan))
r = pd.DataFrame(rows)
pd.set_option("display.width", 250)
for thr in (2.0, 3.0):
    for s in (9, 0, 1, 2):
        p = r[(r.thr == thr) & (r.ses == s)].pivot_table(index=["k", "h"], columns="half", values="mean").round(3)
        q = r[(r.thr == thr) & (r.ses == s)].pivot_table(index=["k", "h"], columns="half", values="mean_tr").round(3)
        n = r[(r.thr == thr) & (r.ses == s) & (r.h == 5)].pivot_table(index="k", columns="half", values="n")
        print(f"\n=== |z|>={thr} session {s}: fade mean USD (scaled), all | with H1 trend")
        print(pd.concat([p, q.add_suffix("_tr")], axis=1).to_string())
        print("n:", n.to_dict("index"))
