"""Row 50, step 2 (descriptive): the share of the leads' trades each switch had on, month by month 2025-03 .. 2026-04,
from regime50_trades.parquet and the thresholds in out_regime50_switch.csv (nothing new is loaded or chosen)."""

import numpy as np
import pandas as pd

from pathlib import Path

HERE = Path(__file__).resolve().parent
T = pd.read_parquet(HERE / "regime50_trades.parquet")
C = pd.read_csv(HERE / "out_regime50_switch.csv")
T = T[T.t >= pd.Timestamp("2025-03-01", tz="UTC")]
cols = {}
for r in C.itertuples():
    x = T[f"{r.reading}_{r.form}"].to_numpy(float)
    on = np.isfinite(x) & ((x < r.thr) if r.reading == "spr_atr" else (x > r.thr))
    cols[f"{r.reading}_{r.form}"] = pd.Series(on, index=T.index).groupby(T.month).mean().round(2)
M = pd.DataFrame(cols)
M.insert(0, "leads R", T.groupby("month").R.mean().round(3))
pd.set_option("display.width", 250)
print("share of the month's lead trades switched on (thresholds from out_regime50_switch.csv)")
print(M.to_string())
