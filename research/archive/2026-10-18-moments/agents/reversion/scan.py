"""Scan stretch rules over the cached all-minute simulations (development window only).

For each geometry x feature x threshold x session x H1-trend filter x fade/follow: one position at a time,
by half-year: trades, R ours, R of the coin (mean of both sides at the same minutes), USD.
    python scan.py  ->  scan_dev.csv
"""

from __future__ import annotations

import itertools
import os
from pathlib import Path

import numpy as np
import pandas as pd

from allsim import CACHE_DIR, GEOM
from common import DEV, SLIP, Bars, gold
from feats import build

OUT = Path("research/2026-10-18-moments/agents/reversion/scan_dev.csv")


def greedy(i: np.ndarray, x: np.ndarray, filled: np.ndarray, valid_end: np.ndarray) -> np.ndarray:
    """i sorted decision bars; x exit bar (filled) / expiry (unfilled). Returns the taken positions."""
    taken, p, n = [], 0, len(i)
    while p < n:
        taken.append(p)
        free = x[p] + 1 if filled[p] else valid_end[p]
        p = int(np.searchsorted(i, free, side="left"))
        if p <= taken[-1]:
            p = taken[-1] + 1
    return np.asarray(taken, np.int64)


def score(C: dict, pos: np.ndarray, side: np.ndarray, halves: list) -> list[dict]:
    """pos: positions into the cache arrays (sorted), side +1/-1 per position."""
    i = C["i"][pos]
    buy = side > 0
    x = np.where(buy, C["x_b"][pos], C["x_s"][pos])
    fl = np.where(buy, C["f_b"][pos], C["f_s"][pos])
    t = greedy(i, x, fl, x)
    p, sd = pos[t], side[t]
    b = sd > 0
    usd = np.where(b, C["usd_b"][p], C["usd_s"][p])
    fill = np.where(b, C["f_b"][p], C["f_s"][p])
    kind = np.where(b, C["k_b"][p], C["k_s"][p])
    win = np.where(b, C["e_b"][p], C["e_s"][p]) == 2
    risk = C["sl"][p] + SLIP
    out = []
    for name, ia, ib, days in halves:
        m = (C["i"][p] >= ia) & (C["i"][p] < ib)
        mf = m & fill
        n = int(mf.sum())
        r = usd[mf] / risk[mf]
        # coin: both sides' R at the same minutes, each over its own fills
        rb = C["usd_b"][p][m & C["f_b"][p]] / risk[m & C["f_b"][p]]
        rs = C["usd_s"][p][m & C["f_s"][p]] / risk[m & C["f_s"][p]]
        k = kind[mf & (kind > 0)]
        out.append(dict(half=name[:2], n=n, pd=n / days, R=r.mean() if n else np.nan,
                        cR=0.5 * (rb.mean() + rs.mean()) if len(rb) and len(rs) else np.nan,
                        usd=usd[mf].sum(), win=win[mf].mean() if n else np.nan,
                        k1=(k == 1).mean() if len(k) else np.nan, k3=(k == 3).mean() if len(k) else np.nan))
    return out


def main() -> None:
    gold.below_normal_priority()
    B = Bars()
    F = build(B)
    day = B.t64 // 86_400_000_000_000
    halves = []
    for name, a, b in DEV:
        ia, ib = B.idx(a), B.idx(b)
        halves.append((name, ia, ib, np.unique(day[ia:ib]).size))
    feats = {f"z{k}": (2.0, 2.5, 3.0, 4.0) for k in (1, 2, 3, 5, 10, 15, 30)}
    feats |= {f: (2.0, 3.0, 4.0, 6.0) for f in ("dv15", "dv30", "dv60", "de20", "de50")}
    feats |= {"bb20": (2.0, 2.5, 3.0)}
    rows = []
    for g in GEOM:
        path = CACHE_DIR / f"{g}_dev.npz"
        C = dict(np.load(path))
        ii = C["i"]
        Fi = F.iloc[ii]
        ses_all = Fi.ses.to_numpy()
        tr = Fi.tr.to_numpy()
        for fname, thrs in feats.items():
            v = Fi[fname].to_numpy(float)
            for thr, ses, trend, mode in itertools.product(thrs, (None, 0, 1, 2, 3), (None, "with", "against"),
                                                             ("fade", "follow")):
                ok = np.isfinite(v) & (np.abs(v) >= thr)
                if ses is not None:
                    ok &= ses_all == ses
                side = -np.sign(v)
                if mode == "follow":
                    side = -side
                if trend == "with":
                    ok &= side == tr
                elif trend == "against":
                    ok &= side == -tr
                pos = np.flatnonzero(ok)
                if len(pos) < 50:
                    continue
                for h in score(C, pos, side[pos].astype(int), halves):
                    rows.append(dict(geom=g, feat=fname, thr=thr, ses=-1 if ses is None else ses,
                                     trend=trend or "-", mode=mode) | h)
        print("geom done", g, len(rows), flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)


if __name__ == "__main__":
    main()
