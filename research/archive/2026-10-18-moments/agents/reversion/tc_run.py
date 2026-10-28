"""Compare the M1 simulation with a tick replay for one rule on 2025-10-01 .. 2026-03-01 (development)."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from common import REF
from exp import Lab
from sim import one_at_a_time
from tickcheck import replay


def check(L: Lab, cfg: dict, a: str = "2025-10-01", b: str = "2026-03-01") -> pd.DataFrame:
    i, side = L.candidates(cfg)
    ia, ib = L.B.idx(a), L.B.idx(b)
    m = (i >= ia) & (i < ib)
    d = L.sim(cfg, i[m], side[m])
    t = one_at_a_time(d, cfg.get("cap"), L.B, L.dkey)
    atr = L.F.atr.to_numpy(float)
    rows = []
    for r in t.itertuples():
        lim = None
        if cfg.get("off") is not None:
            off = cfg["off"] * atr[r.i]
            lim = (L.B.c[r.i] + L.B.sp[r.i] - off) if r.side > 0 else (L.B.c[r.i] + off)
        out = {}
        for touch in (False, True):
            z = replay(int(L.B.t64[r.i]), int(r.side), lim, float(r.sl), float(r.tp), cfg.get("valid", 1),
                       cfg["hold"], touch)
            if z is None:
                break
            out[touch] = z
        if len(out) < 2:
            continue
        rows.append(dict(i=r.i, side=r.side, m1_filled=r.filled, m1_usd=r.usd if r.filled else np.nan,
                         m1_exit=r.exit if r.filled else "", tk_filled=out[False]["filled"],
                         tk_usd=out[False].get("usd", np.nan), tk_exit=out[False].get("exit", ""),
                         touch_filled=out[True]["filled"], touch_usd=out[True].get("usd", np.nan), sl=r.sl))
    x = pd.DataFrame(rows)
    print(f"orders {len(x)}: M1 filled {x.m1_filled.mean():.3f}, ticks filled {x.tk_filled.mean():.3f}, "
          f"ticks touch filled {x.touch_filled.mean():.3f}")
    both = x[x.m1_filled & x.tk_filled]
    print(f"both filled {len(both)}: same exit {np.mean(both.m1_exit == both.tk_exit):.3f}; "
          f"USD/trade M1 {both.m1_usd.mean():+.3f} ticks {both.tk_usd.mean():+.3f}")
    print(f"all fills: M1 {x.m1_usd.sum():+.1f} USD ({x.m1_filled.sum()} trades, R {(x.m1_usd / (x.sl + 0.07)).mean():+.3f}); "
          f"ticks {x.tk_usd.sum():+.1f} ({x.tk_filled.sum()}, R {(x.tk_usd / (x.sl + 0.07)).mean():+.3f}); "
          f"touch {x.touch_usd.sum():+.1f} ({x.touch_filled.sum()})")
    print(pd.crosstab(both.m1_exit, both.tk_exit))
    return x


if __name__ == "__main__":
    L = Lab()
    base = dict(feat="z5", thr=3.0, sl=3, tp=3, hold=60)
    check(L, base | dict(off=1.0, valid=10))
    check(L, base)
    _ = REF, sys
