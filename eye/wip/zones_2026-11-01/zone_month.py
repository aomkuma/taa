"""Run zones v5 - Claude's form (2026-11-01): the cluster seen over one month of H4, as the owner looks.

At each H4 close: over the last N bars (about a month), the band of height 2S holding the most H4 closes is the
price cluster; the anchor is the lowest low among the bars that closed inside it. The grid A + k*S shifts when
the anchor moves more than TOL*S off the current lines. No trading.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
OUT = sys.argv[1]
S = float(sys.argv[2]) if len(sys.argv) > 2 else 76.0
N = int(sys.argv[3]) if len(sys.argv) > 3 else 132  # 22 trading days x 6 H4 bars
TOL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.2
TAG = sys.argv[5] if len(sys.argv) > 5 else "v5"
TH = "Asia/Bangkok"
START, END = pd.Timestamp("2026-05-01", tz=TH), pd.Timestamp("2026-11-01", tz=TH)
OWNER = [4522.13, 4445.15, 4369.19, 4293.24, 4217.25, 4141.83, 4066.41, 3989.57, 3912.64, 3835.84]

h4 = pd.read_parquet(f"{D}/H4.parquet")
h4["th"] = pd.to_datetime(h4.open_time, utc=True).dt.tz_convert(TH)
h4 = h4[(h4.th >= START - pd.Timedelta(days=45)) & (h4.th < END)].reset_index(drop=True)


def off_grid(price, a):
    o = (price - a) % S
    return min(o, S - o)


def cluster(win):
    c = np.sort(win.close.to_numpy())
    j = np.searchsorted(c, c + 2 * S, side="right")  # band [c_i, c_i + 2S]
    i = int(np.argmax(j - np.arange(len(c))))
    lo_c, hi_c = c[i], c[i] + 2 * S
    inside = win[(win.close >= lo_c) & (win.close <= hi_c)]
    return float(inside.low.min()), float(inside.high.max()), (j[i] - i) / len(c)


grids, anchors = [], []
for i in range(N, len(h4)):
    lo, hi, share = cluster(h4.iloc[i - N + 1 : i + 1])
    anchors.append((h4.th[i], lo, hi, share))
    if not grids or off_grid(lo, grids[-1][1]) > TOL * S:
        grids.append((i + 1, lo, hi, share))

for g, (fi, a, hi, share) in enumerate(grids):
    t = h4.th[min(fi, len(h4) - 1)]
    if t >= START:
        print(f"shift {g+1:2d} from {t:%d/%m %H:%M}  cluster {a:.2f}-{hi:.2f} ({share:.0%} of closes)")
print("shifts in May - Oct:", sum(1 for g in grids if h4.th[min(g[0], len(h4) - 1)] >= START))
for d in ("2026-09-27 21:00", "2026-10-22 21:00", "2026-10-29 21:00"):
    t, lo, hi, sh = min(anchors, key=lambda x: abs(x[0] - pd.Timestamp(d, tz=TH)))
    print(f"at {t:%d/%m %H:%M}: cluster {lo:.2f}-{hi:.2f}")
last = grids[-1][1]
print("last grid vs the owner's lines:", [round(min((last + k * S for k in range(-12, 13)), key=lambda y: abs(y - L)) - L, 1) for L in OWNER])

shown = h4[h4.th >= START]
edges = [pd.Timestamp(x, tz=TH) for x in ("2026-05-01", "2026-07-01", "2026-09-01", "2026-11-01")]
for n in range(3):
    seg = shown[(shown.th >= edges[n]) & (shown.th < edges[n + 1])]
    i0, i1 = seg.index[0], seg.index[-1]
    fig, ax = plt.subplots(figsize=(18, 9))
    for k, r in seg.iterrows():
        c = "#26a69a" if r.close >= r.open else "#ef5350"
        ax.vlines(k, r.low, r.high, color=c, lw=0.7)
        ax.add_patch(plt.Rectangle((k - 0.35, min(r.open, r.close)), 0.7, max(abs(r.close - r.open), 0.01), color=c))
    lo, hi = seg.low.min() - 20, seg.high.max() + 20
    for g, (fi, a, ch, share) in enumerate(grids):
        fe = grids[g + 1][0] if g + 1 < len(grids) else len(h4)
        if fe <= i0 or fi > i1:
            continue
        xs, xe = max(fi, i0), min(fe, i1 + 1)
        m = int((lo - a) // S)
        while a + m * S <= hi:
            y = a + m * S
            if y >= lo:
                ax.hlines(y, xs, xe, color="orange", lw=1.0)
                ax.text(xs + 1, y + 2, f"{y:.0f}", fontsize=7, color="#e65100")
            m += 1
        if i0 <= fi <= i1:
            ax.axvline(fi, color="#8e24aa", lw=0.8, ls=":")
    if n == 2:
        for L in OWNER:
            if lo <= L <= hi:
                ax.hlines(L, i1 - 25, i1 + 3, color="#1565c0", lw=2)
        ax.text(i1 - 25, hi - 8, "blue = the owner's lines (01/11)", color="#1565c0", fontsize=8)
    ticks = list(range(i0, i1, 30))
    ax.set_xticks(ticks, [shown.th[i].strftime("%d/%m") for i in ticks], fontsize=8)
    ax.set_xlim(i0 - 2, i1 + 4)
    ax.set_ylim(lo, hi)
    ax.grid(alpha=0.15)
    ax.set_title(f"XAUUSD H4 FBS-Demo {edges[n]:%d/%m}-{edges[n+1]:%d/%m} Thai - zones from the month's cluster (S {S:.0f}, {N} H4 bars, shift off > {TOL}S); dotted = shift")
    fig.tight_layout()
    fig.savefig(f"{OUT}/zone_{TAG}_{n + 1}.png", dpi=100)
    plt.close(fig)
