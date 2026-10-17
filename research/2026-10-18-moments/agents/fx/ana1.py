"""Read trades1.parquet: per family x pair x mode x exit x filter, net R by half, the coin (mean of the two sides on
the same events), and consistency. Prints the family summary and the consistent cells."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import fxlib as fx  # noqa: E402

H = [h for h, _, _ in fx.HALVES]
t = pd.read_parquet("research/2026-10-18-moments/agents/fx/trades1.parquet")
key = ["fam", "pair", "slk", "tpk", "ev"]
both = t.pivot_table(index=key, columns="mode", values="R").dropna()
coin = both.mean(axis=1).rename("coinR").reset_index()
t = t.merge(coin, on=key, how="left")

rows = []
for q in (0.0, 0.5, 1.0, 1.5):
    for trf in ("any", "with", "against"):
        x = t[t.q >= q]
        if trf == "with":
            x = x[x.with_trend > 0]
        elif trf == "against":
            x = x[x.with_trend < 0]
        g = x.groupby(["fam", "pair", "mode", "slk", "tpk", "half"]).agg(R=("R", "mean"), Rg=("Rg", "mean"),
                                                                       c=("coinR", "mean"), n=("R", "size"))
        g = g.unstack("half")
        for idx, r in g.iterrows():
            Rh = [r[("R", h)] if ("R", h) in r.index else np.nan for h in H]
            n = sum(r[("n", h)] for h in H if ("n", h) in r.index and np.isfinite(r[("n", h)]))
            cR = np.nansum([r[("c", h)] * r[("n", h)] for h in H if np.isfinite(r[("n", h)])]) / n
            allR = np.nansum([r[("R", h)] * r[("n", h)] for h in H if np.isfinite(r[("n", h)])]) / n
            allRg = np.nansum([r[("Rg", h)] * r[("n", h)] for h in H if np.isfinite(r[("n", h)])]) / n
            rows.append(dict(zip(["fam", "pair", "mode", "slk", "tpk"], idx), q=q, trend=trf, n=n, R=allR, Rg=allRg,
                             coin=cR, pos=int(np.sum(np.array(Rh) > 0)), **{h: v for h, v in zip(H, Rh)}))
g = pd.DataFrame(rows)
g.to_parquet("research/2026-10-18-moments/agents/fx/grid1.parquet")
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 400)
print("cells:", len(g))
print("\n=== family x mode: mean net R over pairs (q=0, any trend), by exit ===")
b = g[(g.q == 0) & (g.trend == "any")]
print(b.pivot_table(index=["fam", "mode"], columns=["slk", "tpk"], values="R").round(3))
print("\n=== gross R, same ===")
print(b.pivot_table(index=["fam", "mode"], columns=["slk", "tpk"], values="Rg").round(3))
print("\n=== consistent cells: 5/5 positive halves, n >= 100, R >= 0.10 ===")
c = g[(g.pos == 5) & (g.n >= 100) & (g.R >= 0.10)].sort_values("R", ascending=False)
print(c.round(3).to_string())
print("\n=== count of 5/5 cells by family/pair/mode (any exit/filter, n>=100, R>0) ===")
c2 = g[(g.pos == 5) & (g.n >= 100) & (g.R > 0)]
print(c2.groupby(["fam", "pair", "mode"]).size().sort_values(ascending=False).head(40))
print("\nshare of cells with 5/5 among n>=100:", round((g[g.n >= 100].pos == 5).mean(), 3),
      " 0/5:", round((g[g.n >= 100].pos == 0).mean(), 3))
