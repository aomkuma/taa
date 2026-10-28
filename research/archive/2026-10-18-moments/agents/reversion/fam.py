"""Families from the scan against two baselines: the coin and the H1 trend alone (every minute of the same session
with a trend, side = the trend) - does the stretch add anything beyond trading with the H1 trend?"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from allsim import CACHE_DIR
from common import DEV, Bars
from feats import build
from scan import score

B = Bars()
F = build(B)
day = B.t64 // 86_400_000_000_000
halves = [(n, B.idx(a), B.idx(b), np.unique(day[B.idx(a):B.idx(b)]).size) for n, a, b in DEV]
RULES = [
    # geom, feat, thr, ses, trend, mode, utc-hour window or None
    ("l33b", "dv15", 3.0, 2, "with", "follow", None),
    ("l24b", "dv15", 3.0, 2, "with", "follow", None),
    ("m24", "dv15", 3.0, 2, "with", "follow", None),
    ("l66b", "z10", 2.5, 0, "with", "follow", None),
    ("m66", "dv60", 4.0, 3, "with", "fade", None),
    ("m66", "dv60", 4.0, 3, "with", "fade", (16, 20)),
    ("l66b", "dv60", 4.0, 3, "with", "fade", (16, 20)),
    ("m66", "de50", 4.0, 3, "with", "fade", (16, 20)),
    ("l66b", "bb20", 2.5, 2, "with", "fade", None),
]
caches = {}
pd.set_option("display.width", 250)
for g, feat, thr, ses, trend, mode, hrs in RULES:
    if g not in caches:
        caches[g] = dict(np.load(CACHE_DIR / f"{g}_dev.npz"))
    C = caches[g]
    ii = C["i"]
    Fi = F.iloc[ii]
    v = Fi[feat].to_numpy(float)
    tr = Fi.tr.to_numpy()
    s_ok = Fi.ses.to_numpy() == ses
    if hrs:
        hh = B.hour[ii]
        s_ok &= (hh >= hrs[0]) & (hh < hrs[1])
    side = -np.sign(np.nan_to_num(v))
    if mode == "follow":
        side = -side
    ok = s_ok & np.isfinite(v) & (np.abs(v) >= thr)
    if trend == "with":
        ok &= side == tr
    pos = np.flatnonzero(ok)
    a = pd.DataFrame(score(C, pos, side[pos].astype(int), halves)).set_index("half")
    base = np.flatnonzero(s_ok & (tr != 0))
    bt = pd.DataFrame(score(C, base, tr[base].astype(int), halves)).set_index("half")
    longs = [(side[pos][(ii[pos] >= ia) & (ii[pos] < ib)] > 0).mean() for _, ia, ib, _ in halves]
    out = pd.DataFrame({"n": a.n, "R": a.R, "coinR": a.cR, "trendR": bt.R, "trend_coinR": bt.cR, "long%": longs,
                        "usd": a.usd})
    print(f"\n## {g} {mode} {feat}>={thr} ses {ses} {trend} hours {hrs}")
    print(out.round(3).to_string())
_ = sys
