"""Draw one trade of fib23_m15.pkl, MT5-style: M15 candles, the ZigZag, the owner's Fibo on the leg (0 % at A, 100 %
at B: 23.6, 38.2, 50, 61.8, 78.6, 100, 161.8 %), the order, the fill and the exit. Usage: draw_fib23.py N"""
import sys
sys.path.insert(0, ".")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from eye import bot2e, walk
S = r"C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\600a9d86-b3ac-4124-878e-b57c675a524d\scratchpad"
TH = bot2e.TH
d = pd.read_pickle(S + chr(92) + sys.argv[2]).sort_values("t").reset_index(drop=True)
r = d.loc[int(sys.argv[1])]
m = walk.frame("M15")
a = r.ta - pd.Timedelta(hours=8); b = max(r.exit_t, r.fill_t) + pd.Timedelta(hours=6)
bars = m[(m.index >= a) & (m.index < b)]
x = lambda t: float(bars.index.searchsorted(t))
plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(18, 9))
for k, (o, h, l, c) in enumerate(bars[["open", "high", "low", "close"]].to_numpy()):
    col = "#2ecc71" if c >= o else "#ff4d4d"
    ax.plot([k, k], [l, h], color=col, lw=0.8)
    ax.add_patch(plt.Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.05), color=col))
pv = bot2e._zigzag(bars)
ax.plot([q.pivot_pos for q in pv], [q.price for q in pv], color="#ffeb3b", lw=1.1)
for q in pv:
    ax.text(q.pivot_pos, q.price, f"{q.price:.2f}", color="#ffeb3b", fontsize=7, ha="center", va="bottom" if q.kind.value == "HIGH" else "top")
x0 = x(r.ta)
for lv in (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.618):
    p = r.pa - lv * (r.pa - r.pb)
    col = "#4fc3f7" if lv == 0.236 else ("#bbbbbb" if lv in (0, 1.0) else "#777777")
    ax.plot([x0, len(bars)], [p, p], color=col, lw=1.2 if lv in (0.236, 0, 1.0) else 0.7)
    ax.text(len(bars), p, f" {lv*100:.1f} ({p:.2f})", color=col, fontsize=8, va="center")
ax.plot([x0, len(bars)], [r.stop] * 2, color="#ff4d4d", ls="--", lw=1); ax.text(len(bars), r.stop, f"    stop {r.stop:.2f}", color="#ff4d4d", fontsize=8, va="bottom")
for t, lab, col in ((r.t, "order (100 % fixed)", "#ffffff"), (r.fill_t, "fill", "#4fc3f7"), (r.exit_t, r.why, "#ff4d4d" if r.why == "stop" else "#2ecc71")):
    ax.axvline(x(t), color=col, ls=":", lw=1); ax.text(x(t), ax.get_ylim()[1], lab, color=col, fontsize=8, va="top")
ticks = range(0, len(bars), 8)
ax.set_xticks(list(ticks)); ax.set_xticklabels([f"{bars.index[i].tz_convert(TH):%d/%m %H:%M}" for i in ticks], rotation=45, fontsize=8)
ax.yaxis.tick_right(); ax.grid(alpha=0.12)
ax.set_title(f"XAUUSD M15 - trade {sys.argv[1]}: {r.side} at the 23.6 % line {r.entry:.2f} (0 % {r.pa:.2f}, 100 % {r.pb:.2f}), "
             f"stop {r.stop:.2f}, target 161.8 % {r.tgt:.2f} -> {r.why}, R {r.R:+.2f}")
out = f"C:/Users/korap/taa/eye/trades/fib23side_{r.t.tz_convert(TH):%Y%m%d_%H%M}_{r.side}.png"
fig.savefig(out, dpi=85, bbox_inches="tight"); print(out)
