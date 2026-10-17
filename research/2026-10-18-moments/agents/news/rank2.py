"""Robust ranking of the design grid: a rule must be positive in A and B even after dropping each period's best
two trades (no lottery rules).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/rank2.py
"""
from __future__ import annotations

import pandas as pd

d = pd.read_parquet("research/2026-10-18-moments/agents/news/grid_design.parquet")
d["tpm"] = d.tpm.fillna(0)


def trim(v: pd.Series) -> float:
    return v.sort_values().iloc[:-2].mean() if len(v) > 4 else float("nan")


out = []
for xmin in (0, 2, 3, 5):
    x = d[d.x >= xmin]
    g = x.groupby(["main", "fam", "stype", "m", "tpm", "hz", "per"]).R.agg(["size", "mean", trim]).unstack("per")
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    g = g.dropna().reset_index()
    g["xmin"] = xmin
    out.append(g)
g = pd.concat(out, ignore_index=True)
g = g[(g.size_A >= 8) & (g.size_B >= 8)]
g["robust"] = g[["trim_A", "trim_B"]].min(axis=1)
pd.set_option("display.width", 250)
print("rules with both trimmed means > 0, by event:", (g.robust > 0).groupby(g.main).agg(["size", "sum"]).to_string())
print(g.sort_values("robust", ascending=False).head(50).round(3).to_string())
