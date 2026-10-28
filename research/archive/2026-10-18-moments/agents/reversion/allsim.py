"""Simulate every minute of a window on both sides for one geometry, so that any rule (a mask of decision minutes)
is scored instantly: ours = the chosen side, the coin = the mean of both sides at the same minutes.

    python allsim.py GEOM [--test]     caches to the scratchpad (CACHE_DIR)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

from common import REF, Bars, gold
from feats import build
from sim import simulate

CACHE_DIR = Path(os.environ.get("REV_CACHE", "research/2026-10-18-moments/agents/reversion/cache"))

# geometry: sl/tp in ATR(60) units of M1 range; off = limit distance in ATR (None = market); valid / hold minutes
GEOM = {
    "m33": dict(sl=3, tp=3, hold=60),
    "m24": dict(sl=2, tp=4, hold=60),
    "m42": dict(sl=4, tp=2, hold=60),
    "m66": dict(sl=6, tp=6, hold=120),
    "l33a": dict(sl=3, tp=3, hold=60, off=0.5, valid=10),
    "l33b": dict(sl=3, tp=3, hold=60, off=1.0, valid=10),
    "l24b": dict(sl=2, tp=4, hold=60, off=1.0, valid=10),
    "l42b": dict(sl=4, tp=2, hold=60, off=1.0, valid=10),
    "l66b": dict(sl=6, tp=6, hold=120, off=1.0, valid=15),
    "l33c": dict(sl=3, tp=3, hold=60, off=2.0, valid=15),
}


def run(geom: str, a: str, b: str, tag: str) -> Path:
    out = CACHE_DIR / f"{geom}_{tag}.npz"
    if out.exists():
        return out
    gold.below_normal_priority()
    B = Bars()
    F = build(B)
    g = GEOM[geom]
    ia, ib = B.idx(a), B.idx(b)
    atr = F.atr.to_numpy(float)
    i = np.arange(ia, ib)
    i = i[np.isfinite(atr[i]) & F.ok60.to_numpy()[i]]
    res = {}
    for name, s in (("b", 1), ("s", -1)):
        side = np.full(len(i), s)
        sl, tp = g["sl"] * atr[i], g["tp"] * atr[i]
        lim = None if g.get("off") is None else g["off"] * atr[i]
        d = simulate(B, i, side, sl, tp, g["hold"], lim, g.get("valid", 0), g.get("be"), chunk=3000)
        res[f"usd_{name}"] = d.usd.to_numpy(np.float32)
        res[f"x_{name}"] = d.x.to_numpy(np.int32)
        res[f"f_{name}"] = d.filled.to_numpy(bool)
        res[f"k_{name}"] = d.kind.to_numpy(np.int8)
        res[f"e_{name}"] = d.code.to_numpy(np.int8)
    res["i"] = i.astype(np.int32)
    res["sl"] = (g["sl"] * atr[i]).astype(np.float32)
    res["scale"] = (B.c[i] / REF).astype(np.float32)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(out, **res)
    return out


if __name__ == "__main__":
    test = "--test" in sys.argv
    for gname in [a for a in sys.argv[1:] if not a.startswith("--")]:
        if test:
            run(gname, "2026-03-01", "2026-10-15", "test")
        else:
            run(gname, "2023-11-01", "2026-03-01", "dev")
        print("done", gname, flush=True)
