"""The D1 tide for TS (Elder's first screen one level higher): at each trigger, the last closed D1 bar's close
against its EMA(50) and the EMA's 5-day slope. Trades with the D1 tide (BUY in UP, SELL in DOWN) against the
ones against it, per side and half-year, on both years' outcomes."""

import numpy as np
import pandas as pd

d = pd.concat([pd.read_csv(p, parse_dates=["time"]) for p in ("data/backtests/ts/dataset_m15/outcomes.csv",
                                                               "data/backtests/ts/oos_dataset_m15/outcomes.csv")],
              ignore_index=True).sort_values("time")
d1 = pd.read_parquet("data/history/FBS-Demo/XAUUSD/D1.parquet").sort_values("close_time")
for n in (20, 50):
    d1[f"ema{n}"] = d1.close.ewm(span=n, adjust=False).mean()
d1["slope50"] = d1.ema50 - d1.ema50.shift(5)
d1 = d1[["close_time", "close", "ema20", "ema50", "slope50"]].rename(columns={"close": "d1_close"})
d = pd.merge_asof(d, d1, left_on="time", right_on="close_time", direction="backward")  # closed bars only
up = (d.d1_close > d.ema50) & (d.slope50 > 0)
down = (d.d1_close < d.ema50) & (d.slope50 < 0)
d["d1"] = np.where(up, "UP", np.where(down, "DOWN", "MIXED"))
buy = d.side == "BUY"
d["d1_rel"] = np.where(d.d1 == "MIXED", "MIXED", np.where((buy & up) | (~buy & down), "WITH", "AGAINST"))
edges = [pd.Timestamp(x, tz="UTC") for x in ("2024-10-01", "2025-04-01", "2025-10-01", "2026-04-01", "2026-10-01")]
d["q"] = pd.cut(d.time, edges, labels=["24H2", "25H1", "25H2", "26H1"], right=False)
print("D1 state share per half:", d.groupby("q", observed=True).d1.value_counts(normalize=True).unstack().round(2).to_dict("index"))
loc = d[["H1_pivot_dist", "H4_pivot_dist"]].min(axis=1)
for plan in ("b0.25_k2.0", "b0.25_k3.0"):
    print(f"\n{plan}: group n R | 24H2 25H1 25H2 26H1")
    for label, m in {
        "D1 WITH, all": d.d1_rel == "WITH",
        "D1 WITH, BUY": (d.d1_rel == "WITH") & buy,
        "D1 WITH, SELL": (d.d1_rel == "WITH") & ~buy,
        "D1 AGAINST": d.d1_rel == "AGAINST",
        "D1 MIXED": d.d1_rel == "MIXED",
        "D1 WITH & H4 not against": (d.d1_rel == "WITH") & (d.h4_map != "AGAINST"),
        "D1 WITH & bos": (d.d1_rel == "WITH") & (d.kind == "bos"),
        "D1 WITH & loc<=0.5": (d.d1_rel == "WITH") & (loc <= 0.5),
    }.items():
        s = d[m]
        h = [s.loc[s.q == q, plan].mean() for q in ["24H2", "25H1", "25H2", "26H1"]]
        print(f"  {label:26} {len(s):5d} {s[plan].mean():+.3f} | " + " ".join(f"{x:+.3f}" for x in h)
              + ("  4/4" if all(x > 0 for x in h) else ""))
d.to_csv("data/backtests/ts/outcomes_two_years_d1.csv", index=False)
