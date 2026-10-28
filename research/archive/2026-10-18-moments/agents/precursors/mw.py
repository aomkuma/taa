"""M and W only (notes.md "M and W only", written before it is computed; owner, 2026-10-19: "scope it down to M and W").
A W on a timeframe: the last three confirmed swings of the 3-ATR ZigZag are a trough A, a peak B (the neckline) and a
trough C with the bottoms alike (|C - A| <= TOL x the height B - min(A, C)); the signal is the first close above B
after C - no close above B since C's bar - while A, B, C are still the latest swings: a buy. An M is the mirror: a
sell on the first close below the trough B between two alike peaks. Only closed bars.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/mw.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TOL = 0.25
TFS = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h"}


def detect(c: np.ndarray, piv: tuple, tol: float = TOL) -> pd.DataFrame:
    """Every M / W signal bar from the closes and the swings (bar, price, +1 peak / -1 trough, the bar confirming it)."""
    pidx, pval, ptyp, pconf = piv
    rows, k, fired = [], 0, set()
    for i in range(1, len(c)):
        while k < len(pconf) and pconf[k] <= i:
            k += 1
        if k < 3:
            continue
        a, b, x = k - 3, k - 2, k - 1  # the latest three swings known at bar i
        if (ptyp[a], ptyp[b], ptyp[x]) == (-1, 1, -1):
            side, height = 1, pval[b] - min(pval[a], pval[x])
        elif (ptyp[a], ptyp[b], ptyp[x]) == (1, -1, 1):
            side, height = -1, max(pval[a], pval[x]) - pval[b]
        else:
            continue
        if x in fired or abs(pval[x] - pval[a]) > tol * height:
            continue
        if (c[i] - pval[b]) * side <= 0:  # not beyond the neckline
            continue
        since = c[pidx[x] + 1:i]  # the closes between C and this bar
        if len(since) and ((since - pval[b]) * side > 0).any():  # the neckline was already broken: not fresh
            fired.add(x)
            continue
        fired.add(x)
        rows.append(dict(i=i, kind="W" if side > 0 else "M", side=side, a=pval[a], b=pval[b], c=pval[x], ia=int(pidx[a]),
                         ib=int(pidx[b]), ic=int(pidx[x]), height=height))
    return pd.DataFrame(rows, columns=["i", "kind", "side", "a", "b", "c", "ia", "ib", "ic", "height"])


def detect_apart(c: np.ndarray, piv: tuple, tol: float = TOL) -> pd.DataFrame:
    """The same signals found the other way round, written apart from detect: for each run of three alternating swings,
    the bars where they are the latest known (from C's confirmation to the next swing's), the first close beyond B
    there - kept only when no close since C's bar was beyond B before it."""
    pidx, pval, ptyp, pconf = (np.asarray(v) for v in piv)
    out = []
    for x in range(2, len(pidx)):
        a, b = x - 2, x - 1
        shape = (ptyp[a], ptyp[b], ptyp[x])
        if shape not in ((-1, 1, -1), (1, -1, 1)):
            continue
        side = 1 if shape[0] == -1 else -1
        height = (pval[b] - min(pval[a], pval[x])) if side > 0 else (max(pval[a], pval[x]) - pval[b])
        if abs(pval[x] - pval[a]) > tol * height:
            continue
        first = max(int(pconf[x]), 1)
        last = int(pconf[x + 1]) - 1 if x + 1 < len(pconf) else len(c) - 1  # the next swing known from its own bar on
        beyond = np.nonzero((c[int(pidx[x]) + 1:last + 1] - pval[b]) * side > 0)[0]
        if len(beyond) == 0:
            continue
        j = int(pidx[x]) + 1 + int(beyond[0])  # the first close beyond B after C
        if j < first:  # broken before the pattern could be seen: not fresh
            continue
        out.append(dict(i=j, kind="W" if side > 0 else "M", side=side, a=pval[a], b=pval[b], c=pval[x], ia=int(pidx[a]),
                        ib=int(pidx[b]), ic=int(pidx[x]), height=height))
    return pd.DataFrame(out, columns=["i", "kind", "side", "a", "b", "c", "ia", "ib", "ic", "height"])


def first_passage(o1: np.ndarray, h1: np.ndarray, l1: np.ndarray, j0: int, side: int, dist: float, horizon: int) -> str:
    """From the M1 open of bar j0, the signal's way: 'win' if price goes dist that way before dist against it (both in
    one bar: 'loss'), 'none' if neither within horizon bars."""
    e = o1[j0]
    up, dn = (e + dist, e - dist) if side > 0 else (e - dist, e + dist)
    for j in range(j0, min(j0 + horizon, len(o1))):
        hit_t = h1[j] >= up if side > 0 else l1[j] <= up
        hit_s = l1[j] <= dn if side > 0 else h1[j] >= dn
        if hit_s:
            return "loss"
        if hit_t:
            return "win"
    return "none"


def main() -> None:
    import plib  # noqa: PLC0415
    from fingerprint import ZZ_K, raw, zigzag  # noqa: PLC0415

    plib.gold.below_normal_priority()
    m = plib.load()
    o1, h1, l1 = (m[k].to_numpy(float) for k in ("open", "high", "low"))
    ot = m.index.as_unit("ns").asi8
    win_mask = plib.window_mask
    res, allev = [], []
    for tf, rule in TFS.items():
        b = plib.tf_bars(m, rule)
        R = raw(b)
        piv = zigzag(R["h"], R["lo"], R["atr"], ZZ_K)
        E = detect(R["c"], piv)
        E2 = detect_apart(R["c"], piv)
        assert E.reset_index(drop=True).equals(E2.sort_values("i").reset_index(drop=True)), tf  # both detectors agree
        avail = pd.DatetimeIndex(b["avail"]).as_unit("ns")
        E["t"] = avail[E.i.to_numpy()]
        E["tf"] = tf
        E["j0"] = np.searchsorted(ot, pd.DatetimeIndex(E.t).as_unit("ns").asi8)
        E = E[(E.j0 < len(o1)) & (E.t >= pd.Timestamp("2023-11-01", tz="UTC"))].reset_index(drop=True)
        E["out"] = [first_passage(o1, h1, l1, int(j), int(s), float(hh), 1440) for j, s, hh in zip(E.j0, E.side, E.height)]
        E["inwin"] = win_mask(pd.DatetimeIndex(E.t)).any(axis=1).to_numpy()
        allev.append(E)
        print(tf, "signals", len(E), "(both detectors equal)", flush=True)
    A = pd.concat(allev, ignore_index=True)
    A.to_parquet(HERE / "mw_signals.parquet")
    half = np.where(pd.DatetimeIndex(A.t) >= plib.EXAM_START, "exam", "learn")
    for tf in TFS:
        for kind in ("W", "M", "both"):
            for scope in ("all", "windows"):
                for h in ("learn", "exam"):
                    k = (A.tf == tf) & (half == h) & ((A.kind == kind) if kind != "both" else True)
                    if scope == "windows":
                        k &= A.inwin
                    d = A[k & (A.out != "none")]
                    n = len(d)
                    w = (d.out == "win").mean() if n else np.nan
                    res.append(dict(tf=tf, kind=kind, scope=scope, half=h, signals=int(k.sum()), decided=n, win=w,
                                    se=np.sqrt(0.25 / n) if n else np.nan))
    D = pd.DataFrame(res)
    D.to_csv(HERE / "mw_premise.csv", index=False)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 200)
    W = D.pivot_table(index=["tf", "kind", "scope"], columns="half", values=["signals", "win", "se"])
    W.columns = [f"{a}_{b}" for a, b in W.columns]
    print("\nthe measured move before the same distance against (a driftless walk: 0.500), from the next M1 open, no costs")
    print(W[["signals_learn", "win_learn", "se_learn", "signals_exam", "win_exam", "se_exam"]].round(3).reset_index().to_string(index=False))


if __name__ == "__main__":
    main()
