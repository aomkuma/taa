"""Rank the scan: edge = R ours - R coin per half-year; consistency over the five development half-years."""

from __future__ import annotations

import sys

import pandas as pd

d = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else "research/2026-10-18-moments/agents/reversion/scan_dev.csv")
d["edge"] = d.R - d.cR
key = ["geom", "feat", "thr", "ses", "trend", "mode"]
w = d.pivot_table(index=key, columns="half", values=["edge", "R", "n", "pd"])
w = w[(w["n"].min(axis=1) >= 60)]
e = w["edge"]
r = w["R"]
s = pd.DataFrame({"pos_edge": (e > 0).sum(1), "min_edge": e.min(1), "mean_edge": e.mean(1), "R_mean": r.mean(1),
                  "R_H4": r["H4"], "R_H5": r["H5"], "min_R": r.min(1), "pd": w["pd"].mean(1), "n": w["n"].sum(1)})
pd.set_option("display.width", 250)
print("rules with >= 60 trades in every half:", len(s))
print("share with edge > 0 in all 5 halves:", (s.pos_edge == 5).mean().round(3), " in >= 4:", (s.pos_edge >= 4).mean().round(3))
print("by mode, share 5/5:", s.groupby(level="mode").pos_edge.apply(lambda x: (x == 5).mean()).round(3).to_dict())
print("by geom, share 5/5:", s.groupby(level="geom").pos_edge.apply(lambda x: (x == 5).mean()).round(3).to_dict())
print("by session, share 5/5:", s.groupby(level="ses").pos_edge.apply(lambda x: (x == 5).mean()).round(3).to_dict())
print("by trend, share 5/5:", s.groupby(level="trend").pos_edge.apply(lambda x: (x == 5).mean()).round(3).to_dict())
print("by feat, share 5/5:", s.groupby(level="feat").pos_edge.apply(lambda x: (x == 5).mean()).round(3).to_dict())
print("\nTop by min edge (5/5):")
print(s[s.pos_edge == 5].sort_values("min_edge", ascending=False).head(40).round(3).to_string())
print("\nTop by mean R with min R > -0.05:")
print(s[s.min_R > -0.05].sort_values("R_mean", ascending=False).head(30).round(3).to_string())
print("\nTop by R in H4+H5 (the current cost regime), pos_edge >= 4:")
s["R45"] = (s.R_H4 + s.R_H5) / 2
print(s[s.pos_edge >= 4].sort_values("R45", ascending=False).head(30).round(3).to_string())
