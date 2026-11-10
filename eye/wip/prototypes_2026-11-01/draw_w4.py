"""Draw wave 4 instances of the count (wave_depth.py's form), one image each, MT5-style: TF candles, the ZigZag,
the points 0 (the move's start), 1, 2, 3, 4 labelled, the owner's Fibo on the move 0 -> 3 (0 % at top 3, 100 % at
point 0) and where 4 ended. Usage: draw_w4.py TF FROM TO N  (N = the n-th instance in time order)"""
import sys
sys.path.insert(0, ".")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from eye import bot2e, walk

TF, A0, A1, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
TH = bot2e.TH
df = walk.frame(TF)
df = df[(df.index >= pd.Timestamp(A0, tz="UTC") - pd.Timedelta(days=30)) & (df.index < pd.Timestamp(A1, tz="UTC"))]
pv = bot2e._zigzag(df)
start, end = pd.Timestamp(A0, tz=TH), pd.Timestamp(A1, tz=TH)

def count(ia):
    a = pv[ia]; up = a.kind.value == "HIGH"; k = ia - 1
    while k >= 0 and not (pv[k].kind is a.kind and ((pv[k].price > a.price) if up else (pv[k].price < a.price))):
        k -= 1
    opp = [i for i in range(k + 1, ia) if pv[i].kind is not a.kind]
    if not opp: return 0, None
    st = min(opp, key=lambda i: pv[i].price) if up else max(opp, key=lambda i: pv[i].price)
    return ia - st, st

found = []
for ia in range(len(pv) - 2):
    if not (start <= df.index[pv[ia].pivot_pos].tz_convert(TH) < end): continue
    n, st = count(ia)
    if n == 3: found.append((st, ia))
st, ia = found[N]
pts = {"0": pv[st], "1": pv[st + 1], "2": pv[st + 2], "3": pv[ia], "4": pv[ia + 1]}
p5 = pv[ia + 2] if ia + 2 < len(pv) else None
lo_t = df.index[pv[st].pivot_pos] - pd.Timedelta(hours=6)
hi_t = df.index[(p5 or pv[ia + 1]).pivot_pos] + pd.Timedelta(hours=6)
bars = df[(df.index >= lo_t) & (df.index < hi_t)]
x = lambda q: float(bars.index.searchsorted(df.index[q.pivot_pos]))
plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(18, 9))
for k, (o, h, l, c) in enumerate(bars[["open", "high", "low", "close"]].to_numpy()):
    col = "#2ecc71" if c >= o else "#ff4d4d"
    ax.plot([k, k], [l, h], color=col, lw=0.8)
    ax.add_patch(plt.Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.05), color=col))
seg = [q for q in pv if lo_t <= df.index[q.pivot_pos] < hi_t]
ax.plot([x(q) for q in seg], [q.price for q in seg], color="#ffeb3b", lw=1.1)
for q in seg:
    ax.text(x(q), q.price, f"{q.price:.2f}", color="#ffeb3b", fontsize=7, ha="center", va="bottom" if q.kind.value == "HIGH" else "top")
up = pts["3"].kind.value == "HIGH"
for lab, q in pts.items():
    ax.annotate(lab, (x(q), q.price), xytext=(0, 18 if (q.kind.value == "HIGH") else -24), textcoords="offset points",
                ha="center", color="#ff80ab", fontsize=15, fontweight="bold")
top, s0 = pts["3"].price, pts["0"].price
x0 = x(pts["3"])
for lv in (0, 0.236, 0.382, 0.5, 0.618, 0.786, 0.886, 1.0):
    p = top - lv * (top - s0)
    ax.plot([x0, len(bars)], [p, p], color="#4fc3f7" if lv not in (0, 1.0) else "#bbbbbb", lw=0.8)
    ax.text(len(bars), p, f" {lv*100:.1f} ({p:.2f})", color="#4fc3f7", fontsize=8, va="center")
w4 = (top - pts["4"].price) / (top - s0)
ticks = range(0, len(bars), max(1, len(bars) // 24))
ax.set_xticks(list(ticks)); ax.set_xticklabels([f"{bars.index[i].tz_convert(TH):%d/%m %H:%M}" for i in ticks], rotation=45, fontsize=8)
ax.yaxis.tick_right(); ax.grid(alpha=0.12)
ax.set_title(f"XAUUSD {TF} - wave 4 no. {N} ({'up' if up else 'down'} move): 0 {s0:.2f}, 3 {top:.2f}, 4 {pts['4'].price:.2f} "
             f"= {w4*100:.1f} % on the Fibo 0 % at 3, 100 % at 0")
out = f"C:/Users/korap/taa/eye/trades/w4_{TF}_{df.index[pts['3'].pivot_pos].tz_convert(TH):%Y%m%d_%H%M}.png"
fig.savefig(out, dpi=85, bbox_inches="tight"); print(out, f"of {len(found)}")
