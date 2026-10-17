"""Rank the design grid (grid_design.parquet): R a trade in A and B per rule; a rule is kept only when both
periods are positive. Also the share of rules positive in both (a null of independent halves gives ~25 %).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/rank.py [EVENT ...]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

d = pd.read_parquet("research/2026-10-18-moments/agents/news/grid_design.parquet")
d["tpm"] = d.tpm.fillna(0)
only = sys.argv[1:]
out = []
for xmin in (0, 2, 3, 5):
    x = d[d.x >= xmin]
    g = x.groupby(["main", "fam", "stype", "m", "tpm", "hz", "per"]).R.agg(["size", "mean"]).unstack("per")
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    g = g.dropna().reset_index()
    g["xmin"] = xmin
    out.append(g)
g = pd.concat(out, ignore_index=True)
g = g[(g.size_A >= 8) & (g.size_B >= 8)]
g["both"] = (g.mean_A > 0) & (g.mean_B > 0)
g["minR"] = g[["mean_A", "mean_B"]].min(axis=1)
pd.set_option("display.width", 250)
print("share of rules positive in both A and B, by event:")
print(g.groupby("main").both.agg(["size", "mean"]).round(2).to_string())
print("by family:")
print(g.assign(f=g.fam.str.split(",").str[0]).groupby(["main", "f"]).both.mean().unstack().round(2).to_string())
if only:
    g = g[g.main.isin(only)]
print(g.sort_values("minR", ascending=False).head(60).round(3).to_string())
