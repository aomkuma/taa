"""Charts of trades (research venv: matplotlib). python charts.py GEOM KIND(stop|win) N OUT.png"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np, pandas as pd
geom, kind, n, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
d = "research/2026-10-18-moments/agents/reversion/"
t = pd.read_parquet(d + f"trades_{geom}.parquet")
b = pd.read_parquet(d + f"bars_{geom}.parquet")
t = t[(t.half == "H5") & (t.exit == kind)].head(n)
cols = 3
rows = int(np.ceil(len(t) / cols))
fig, axs = plt.subplots(rows, cols, figsize=(16, 3.6 * rows))
for ax, r in zip(np.ravel(axs), t.itertuples()):
    seg = b.loc[r.i - 180: r.i + 240]
    x = seg.index - r.i
    ax.vlines(x, seg.l, seg.h, color="0.6", lw=0.6)
    ax.plot(x, seg.c, color="k", lw=0.7)
    ax.plot(x, seg.c.rolling(60).mean(), color="tab:blue", lw=0.8, label="60-bar mean")
    ax.plot(x, seg.c.ewm(span=20 * 15, adjust=False).mean(), color="tab:orange", lw=0.8, label="~M15 EMA20")
    fill = r.fill_px
    ax.axhline(fill, color="tab:green", lw=0.8)
    ax.axhline(fill - r.side * r.sl, color="tab:red", lw=0.8, ls="--")
    ax.axhline(fill + r.side * r.tp, color="tab:green", lw=0.8, ls="--")
    ax.axvline(0, color="tab:purple", lw=0.6)
    ax.axvline(r.f - r.i, color="tab:green", lw=0.6)
    ax.axvline(r.x - r.i, color="tab:red", lw=0.6)
    ax.set_title(f"{str(r.t)[:16]} {'BUY' if r.side > 0 else 'SELL'} {r.exit} {r.usd:+.1f} USD kind {r.kind}", fontsize=9)
    ax.tick_params(labelsize=7)
fig.tight_layout()
fig.savefig(out, dpi=70)
print(out)
