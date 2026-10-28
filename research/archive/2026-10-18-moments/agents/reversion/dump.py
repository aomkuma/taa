"""Dump one step's trades with the bars around them for charts (development only)."""
import sys, warnings
import numpy as np, pandas as pd
from common import DEV
from diag import situations
from exp import Lab
from steps import STEPS, run
warnings.filterwarnings("ignore")
geom, step = sys.argv[1], sys.argv[2]
L = Lab(); S = situations(L)
names = dict(STEPS)[step]
t = run(L, S, geom, names, DEV).reset_index(drop=True)
t["fill_t"] = L.B.ot[t.f.to_numpy()]
t["x_t"] = L.B.ot[t.x.to_numpy()]
t.to_parquet(f"research/2026-10-18-moments/agents/reversion/trades_{geom}.parquet")
# bars: 180 before .. 240 after each trade of H5 for the charts
sel = t[t.half == "H5"]
idx = np.unique(np.concatenate([np.arange(i - 180, i + 300) for i in sel.i]))
B = L.B
pd.DataFrame({"t": B.ot[idx], "o": B.o[idx], "h": B.h[idx], "l": B.lo[idx], "c": B.c[idx], "sp": B.sp[idx]},
             index=idx).to_parquet(f"research/2026-10-18-moments/agents/reversion/bars_{geom}.parquet")
print(len(t), len(sel))
