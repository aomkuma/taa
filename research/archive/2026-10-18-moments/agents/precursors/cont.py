"""Once it starts, does it run? (design only; written in notes.md before it is computed)

From each focus-window decision close (ref), the first touch of ref +- K U within 30 minutes is the start (the side
is given by the move itself, nothing predicted). From the bar after the touch, within 60 minutes: does price reach
ref + 10 U (the run) before it comes back to ref (stop A), or before ref - K U on the other side (stop B)? A random
walk gives (A) K / 10 and (B) 2K / (10 + K). By window, by half-year, and by the larger timeframes' state relative to
the start's side.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/cont.py [K]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plib
from plib import HERE

K = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
T = 10.0
DH = ["H1", "H2", "H3", "H4", "H5"]


def main() -> None:
    m = plib.load()
    tmin = plib.minutes(m.index)
    h, lo, c = (m[k].to_numpy(float) for k in ("high", "low", "close"))
    n = len(m)
    D = pd.read_parquet(HERE / "decisions.parquet", columns=None)
    D = D[D.half.isin(DH)].copy()
    dec = D.i.to_numpy()
    u = D.u.to_numpy()
    ref = c[dec]
    k, tt = K * u, T * u
    side = np.zeros(len(dec))
    trig = np.full(len(dec), -1)
    for s in range(1, 31):
        j = np.minimum(dec + s, n - 1)
        ok = (dec + s < n) & (tmin[j] - tmin[dec] <= 30) & (side == 0)
        up = ok & (h[j] >= ref + k)
        dn = ok & (lo[j] <= ref - k)
        side = np.where(up & ~dn, 1, np.where(dn & ~up, -1, np.where(up & dn, np.nan, side)))
        trig = np.where(ok & (up | dn), j, trig)
    have = np.isfinite(side) & (side != 0)
    resA = np.full(len(dec), np.nan)
    resB = np.full(len(dec), np.nan)
    sgn = np.nan_to_num(side)
    tgt = ref + sgn * tt
    stA = ref
    stB = ref - sgn * k
    # the trigger bar itself: a touch of the target in it counts unless the bar also reaches the stop
    doneA = ~have
    doneB = ~have
    for s in range(0, 61):
        j = np.minimum(np.maximum(trig, 0) + s, n - 1)
        ok = have & (trig + s < n) & (tmin[j] - tmin[np.maximum(trig, 0)] <= 60)
        hit_t = np.where(sgn > 0, h[j] >= tgt, lo[j] <= tgt)
        hit_a = np.where(sgn > 0, lo[j] <= stA, h[j] >= stA) if s > 0 else np.zeros(len(dec), bool)
        hit_b = np.where(sgn > 0, lo[j] <= stB, h[j] >= stB) if s > 0 else np.zeros(len(dec), bool)
        for res, done, hs in ((resA, doneA, hit_a), (resB, doneB, hit_b)):
            new = ok & ~done & (hit_t | hs)
            res[new] = np.where(hit_t[new] & ~hs[new], 1.0, 0.0)
            done |= new
    D["cside"], D["cA"], D["cB"] = side, resA, resB
    D.loc[~have, ["cA", "cB"]] = np.nan
    pa, pb = K / T, 2 * K / (T + K)
    print(f"=== K = {K} U start, T = {T} U run; random walk: A {pa:.3f}, B {pb:.3f} ===")
    g = D[have]
    print(f"starts: {len(g)} of {len(D)} decision minutes; A decided {g.cA.notna().mean():.3f}")

    def table(by, name):
        t = g.groupby(by).agg(n=("cA", "count"), A=("cA", "mean"), B=("cB", "mean"))
        t["A-rw"] = t.A - pa
        t["B-rw"] = t.B - pb
        print(f"\n-- by {name} --")
        print(t.round(3).to_string())

    table("half", "half-year")
    table("win", "window")
    for tf in ("H4", "H1", "M15", "M5"):
        for kind in ("struct", "tide"):
            v = g[f"{tf}_{kind}"].where(g[f"{tf}_{kind}"].isin([1, -1]))
            rel = (v * g.cside).map({1.0: "with", -1.0: "against"})
            table([rel.rename(f"{tf}_{kind}"), g.half], f"{tf} {kind} vs the start's side x half")
    # states measured before the start
    for col in ("box_now", "day_brk", "x72", "sweep"):
        v = g[col]
        rel = np.sign(v * g.cside).map({1.0: "with", -1.0: "against", 0.0: "none"}) if col != "box_now" else v
        table([rel.rename(col), g.half], f"{col} (relative to the start's side) x half")
    q = pd.qcut(g.M15_atr_pct.rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    table(q.rename("M15_atr_pct"), "M15 ATR percentile")
    q = pd.qcut(g.M5_bbw_pct.rank(method="first"), 5, labels=["q1", "q2", "q3", "q4", "q5"])
    table(q.rename("M5_bbw_pct"), "M5 Bollinger width percentile (compression = q1)")
    rel = g.min_since_rel <= 2
    table(rel.rename("release in the last 2 min"), "a US release just out")
    D[["cside", "cA", "cB"]].to_parquet(HERE / f"cont_{int(K)}.parquet")


if __name__ == "__main__":
    main()
