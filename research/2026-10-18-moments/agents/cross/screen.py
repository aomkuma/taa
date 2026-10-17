"""Agent "cross", step 3: episodes (design data only). A signal fires when |z| crosses thr (first minute, then
silent 60 minutes); side = sign(z) x direction (+1 follow, -1 fade). Gold's next 60 minutes (close t -> t+60, USD)
signed by side, minus the drift (side x the mean 60-minute move of all minutes of that session and half), so a
bull half cannot pass for an edge. Per half: n, excess USD, hit %; longs and shorts apart.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/screen.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from measure import HALVES  # noqa: E402

SESS = {"asia": (0, 7), "london": (7, 12), "ny": (12, 17), "late": (17, 21)}
H = 60


def episodes(z: pd.Series, thr: float, gap: int = 60) -> np.ndarray:
    """Indices where |z| >= thr and no fire in the previous *gap* minutes (one sign at a time)."""
    a = z.to_numpy()
    t = z.index.as_unit("ns").asi8 // 60_000_000_000
    out, last = [], -10**9
    for i in np.flatnonzero(np.abs(np.nan_to_num(a)) >= thr):
        if t[i] - last >= gap:
            out.append(i)
            last = t[i]
    return np.array(out, dtype=int)


def main() -> None:
    gold.below_normal_priority()
    f = pd.read_parquet("research/2026-10-18-moments/agents/cross/feats.parquet")
    f = f[(f.index >= pd.Timestamp("2023-11-01", tz="UTC")) & (f.index < pd.Timestamp("2026-03-01", tz="UTC"))]
    hour = f.index.hour
    half = np.full(len(f), "", dtype=object)
    for n, a, b in HALVES:
        half[(f.index >= pd.Timestamp(a, tz="UTC")) & (f.index < pd.Timestamp(b, tz="UTC"))] = n
    y = f[f"y{H}"].to_numpy()
    sigs = [c for c in f.columns if not c.startswith("y")]
    res = []
    for sname, (h0, h1) in SESS.items():
        sm = (hour >= h0) & (hour < h1)
        drift = {n: np.nanmean(y[sm & (half == n)]) for n, _a, _b in HALVES}
        for sig in sigs:
            z = f[sig].where(sm)
            for thr in (1.5, 2.0, 2.5):
                ix = episodes(z, thr)
                ix = ix[np.isfinite(y[ix])]
                if len(ix) < 50:
                    continue
                s = np.sign(f[sig].to_numpy()[ix])
                for direction in (1, -1):
                    side = s * direction
                    ex = side * y[ix] - side * np.array([drift[h] for h in half[ix]])
                    row = dict(sess=sname, sig=sig, thr=thr, dir=direction, n=len(ix), ex=np.mean(ex),
                               hit=100 * np.mean(side * y[ix] > 0), long=np.mean(side > 0))
                    pos = 0
                    for n, _a, _b in HALVES:
                        m = half[ix] == n
                        row[n] = np.mean(ex[m]) if m.sum() else np.nan
                        pos += row[n] > 0
                    row["pos"] = pos
                    row["L_ex"] = np.mean(ex[side > 0])
                    row["S_ex"] = np.mean(ex[side < 0])
                    res.append(row)
    r = pd.DataFrame(res)
    r = r[r.dir == np.sign(r.ex)]  # keep the measured direction only (the screen chooses it)
    r.to_csv("research/2026-10-18-moments/agents/cross/screen.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    best = r[(r.pos >= 4) & (r.n >= 80)].sort_values("ex", ascending=False)
    print(best.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
