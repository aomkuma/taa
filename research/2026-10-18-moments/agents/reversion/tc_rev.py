"""Tick replay of a step's limit trades from 2025-10-01 (development part) vs the M1 simulation (real costs)."""
import sys, warnings
import numpy as np, pandas as pd
from common import DEV
from diag import RULES, situations
from exp import Lab
from steps import STEPS, run
from tickcheck import replay
warnings.filterwarnings("ignore")
geom, step = sys.argv[1], sys.argv[2]
L = Lab(); S = situations(L)
t = run(L, S, geom, dict(STEPS)[step], DEV)
t = t[t.t >= pd.Timestamp("2025-10-01", tz="UTC")]
cfg = RULES[geom]
atr = L.F.atr.to_numpy(float)
rows = []
for r in t.itertuples():
    off = cfg["off"] * atr[r.i]
    lim = (L.B.c[r.i] + L.B.sp[r.i] + 0.08 - off) if r.side > 0 else (L.B.c[r.i] + off)
    ny = 480 <= L.B.ny_min[r.i] < 720
    z = replay(int(L.B.t64[r.i]), int(r.side), lim, float(r.sl), float(r.tp), cfg["valid"], cfg["hold"],
               stop_slip=0.20 if ny else 0.15)
    if z is None:
        continue
    rows.append(dict(i=r.i, m1_usd=r.usd, m1_exit=r.exit, tk_filled=z["filled"], tk_usd=z.get("usd", np.nan),
                     tk_exit=z.get("exit", ""), sl=r.sl))
x = pd.DataFrame(rows)
print(f"M1 trades {len(x)} (all filled on M1); ticks filled {x.tk_filled.mean():.3f}")
b = x[x.tk_filled]
print(f"same exit {np.mean(b.m1_exit == b.tk_exit):.3f}; R M1 {(x.m1_usd / (x.sl + .07)).mean():+.3f} "
      f"ticks {(b.tk_usd / (b.sl + .07)).mean():+.3f} (over tick fills); USD M1 {x.m1_usd.sum():+.1f} ticks {b.tk_usd.sum():+.1f}")
print(pd.crosstab(b.m1_exit, b.tk_exit))
