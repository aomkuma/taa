import sys; sys.path.insert(0, "research/2026-10-18-moments")
import numpy as np, pandas as pd, gold
d = gold.bars("D1", before=pd.Timestamp("2026-04-18", tz="UTC"))
pc = d.close.shift(1)
tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
feat = pd.DataFrame({"atr20": tr.rolling(20).mean(), "pct": 100 * tr.rolling(20).mean() / d.close})
feat.index = feat.index + pd.Timedelta(days=1)  # known from the next day on (closed D1 bar)
def attach(T, tcol):
    t = pd.to_datetime(T[tcol], utc=True)
    i = feat.index.searchsorted(t, side="right") - 1
    T = T.copy(); T["atr20"] = feat.atr20.values[i]; T["pct"] = feat.pct.values[i]; T["yr"] = t.dt.year; T["t"] = t
    return T
O = pd.read_parquet("research/2026-10-18-moments/agents/strategist/wf_trades.parquet")
O["piece"] = O.piece.map({"ORB": "London ORB", "STR": "NY straddle"})
O = attach(O, "t_in")
B = pd.read_parquet("research/2026-10-18-moments/agents/dev/b2tf_all.parquet"); B = B[B.tf == "M1"]
B = attach(B, "t_in")
X = pd.concat([O[["piece", "t", "R", "atr20", "pct", "yr"]], B[["piece", "t", "R", "atr20", "pct", "yr"]]])
X = X[X.t < "2026-04-18"]
print(len(X), X.groupby("piece").R.agg(["count", "mean"]).round(3).to_dict("index"))
for f, cuts in (("atr20", [0, 20, 30, 40, 50, 60, 80, 1000]), ("pct", [0, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 9])):
    g = X.groupby(pd.cut(X[f], cuts)).R.agg(["count", "sum", "mean"]).round(3)
    print("\n", f); print(g)
    print(X.groupby([pd.cut(X[f], cuts), "piece"]).R.mean().unstack().round(3))
print(X.groupby("yr").agg(n=("R", "size"), R=("R", "mean"), atr20=("atr20", "median"), pct=("pct", "median")).round(3))
print("\n--- atr20 >= 60 / 50 before the present (2025-10-18):")
for th in (50, 60):
    old = X[(X.t < "2025-10-18") & (X.atr20 >= th)]; new = X[(X.t >= "2025-10-18") & (X.atr20 >= th)]
    print(th, "old", len(old), round(old.R.mean(), 3), sorted(old.t.dt.strftime("%Y-%m").unique()), "| present", len(new), round(new.R.mean(), 3))
    print("   present below", th, len(X[(X.t >= "2025-10-18") & (X.atr20 < th)]))
