"""Run zones v7 - Claude's form (2026-11-01), from the owner's two examples (September 4399.56 / 4244.12 and
October 4066.42 / 4217.08 - each a pair of neighbouring H4 ZigZag turns two steps apart).

A cluster = two neighbouring fixed H4 ZigZag (12/5/3) turns whose distance is 2S within +-TOLH*2S; known at the
close of the bar that fixes the second turn. The grid A + k*S (A = the pair's low) shifts only when the new pair's
low is more than TOL*S off the current lines (less is the fake-break distance). No trading.
"""

import json
import sys

sys.path.insert(0, r"C:\Users\korap\taa")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.indicators.chart_read import zigzag_pivots

D = r"C:\Users\korap\taa\data\history\FBS-Demo\XAUUSD"
OUT = sys.argv[1]
S = float(sys.argv[2]) if len(sys.argv) > 2 else 76.0
TOLH = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
TOL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.2
TAG = sys.argv[5] if len(sys.argv) > 5 else "v7"
TH = "Asia/Bangkok"
START, END = pd.Timestamp("2026-05-01", tz=TH), pd.Timestamp("2026-11-01", tz=TH)
OWNER = [4522.13, 4445.15, 4369.19, 4293.24, 4217.25, 4141.83, 4066.41, 3989.57, 3912.64, 3835.84]
PT = json.load(open(f"{D}/spec.json"))["spec"]["point"]

h4 = pd.read_parquet(f"{D}/H4.parquet")
h4["th"] = pd.to_datetime(h4.open_time, utc=True).dt.tz_convert(TH)
h4 = h4[(h4.th >= START - pd.Timedelta(days=60)) & (h4.th < END)].reset_index(drop=True)
zz = zigzag_pivots(h4.high.to_numpy(float), h4.low.to_numpy(float), PT)


def off_grid(price, a):
    o = (price - a) % S
    return min(o, S - o)


grids = []  # (from index, anchor, pair)
for a, b in zip(zz, zz[1:]):
    d = abs(a.price - b.price)
    if abs(d - 2 * S) > TOLH * 2 * S:
        continue
    lo = min(a.price, b.price)
    fi = b.confirm_pos + 1
    if not grids or off_grid(lo, grids[-1][1]) > TOL * S:
        grids.append((fi, lo, (a, b)))

for g, (fi, lo, (a, b)) in enumerate(grids):
    t = h4.th[min(fi, len(h4) - 1)]
    print(f"shift {g+1:2d} from {t:%d/%m %H:%M}  pair {a.price:.2f} ({h4.th[a.pivot_pos]:%d/%m}) - {b.price:.2f} ({h4.th[b.pivot_pos]:%d/%m}), anchor {lo:.2f}")
print("shifts from May:", sum(1 for g in grids if h4.th[min(g[0], len(h4) - 1)] >= START))
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
    for g, (fi, a, (p, q)) in enumerate(grids):
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
        x0 = max(p.pivot_pos, i0)
        if x0 <= i1:
            ax.add_patch(plt.Rectangle((x0, a), max(q.pivot_pos, x0) - x0 + 1, abs(p.price - q.price), fill=False, ec="#8e24aa", lw=1.2, ls="--"))
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
    ax.set_title(f"XAUUSD H4 FBS-Demo {edges[n]:%d/%m}-{edges[n+1]:%d/%m} Thai - zones from a pair of H4 turns 2S apart (S {S:.0f}); purple box = the pair, dotted = shift")
    fig.tight_layout()
    fig.savefig(f"{OUT}/zone_{TAG}_{n + 1}.png", dpi=100)
    plt.close(fig)
