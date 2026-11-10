"""Draw one retest trade of retest_all12.pkl, MT5-style: M5 candles, the ZigZag (12/5/3 on the drawn stretch),
the leg's 0 % (L0, the start) and 100 % (H100, the end = the entry), the bounce extreme, the stop, the target, the
break close and the fill. Usage: draw_retest.py ROW_INDEX"""
import sys
sys.path.insert(0, ".")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from eye import bot2e, walk

S = r"C:\Users\korap\AppData\Local\Temp\claude\c--Users-korap-taa\600a9d86-b3ac-4124-878e-b57c675a524d\scratchpad"
TH = bot2e.TH
d = pd.read_pickle(S + r"\retest_all12.pkl")
r = d.loc[int(sys.argv[1])]
m5 = walk.frame("M5")
a = min(r.t0, r.t100) - pd.Timedelta(hours=3); b = max(r.exit_t, r.t) + pd.Timedelta(hours=3)
bars = m5[(m5.index >= a) & (m5.index < b)]
x = lambda t: float(bars.index.searchsorted(t))
plt.style.use("dark_background"); fig, ax = plt.subplots(figsize=(18, 9))
for k, (o, h, l, c) in enumerate(bars[["open", "high", "low", "close"]].to_numpy()):
    col = "#2ecc71" if c >= o else "#ff4d4d"
    ax.plot([k, k], [l, h], color=col, lw=0.8)
    ax.add_patch(plt.Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.05), color=col))
pv = bot2e._zigzag(bars)
ax.plot([q.pivot_pos for q in pv], [q.price for q in pv], color="#ffeb3b", lw=1.1)
for q in pv:
    ax.text(q.pivot_pos, q.price, f"{q.price:.2f}", color="#ffeb3b", fontsize=7, ha="center",
            va="bottom" if q.kind.value == "HIGH" else "top")
x0 = x(r.t0)
for price, lab, col, ls in ((r.l0, f"0 % start {r.l0:.2f}", "#bbbbbb", "-"), (r.h100, f"100 % end = entry {r.h100:.2f}", "#4fc3f7", "-"),
                            (r.stop, f"stop {r.stop:.2f}", "#ff4d4d", "--"), (r.tgt, f"target {r.tgt:.2f}", "#2ecc71", "--"),
                            (r.lb, f"bounce extreme {r.lb:.2f}", "#ffa726", ":")):
    ax.plot([x0, len(bars)], [price, price], color=col, ls=ls, lw=1)
    ax.text(len(bars), price, " " + lab, color=col, fontsize=8, va="center")
for t, lab, col in ((r.t, "break close", "#ffffff"), (r.fill_t, "fill", "#4fc3f7"), (r.exit_t, r.why, "#ff4d4d" if r.why == "stop" else "#2ecc71")):
    ax.axvline(x(t), color=col, ls=":", lw=1); ax.text(x(t), ax.get_ylim()[1], lab, color=col, fontsize=8, va="top")
ticks = range(0, len(bars), 12)
ax.set_xticks(list(ticks)); ax.set_xticklabels([f"{bars.index[i].tz_convert(TH):%d/%m %H:%M}" for i in ticks], rotation=45, fontsize=8)
ax.yaxis.tick_right(); ax.grid(alpha=0.12)
ax.set_title(f"XAUUSD M5 - {r.side} retest, break {r.t.tz_convert(TH):%d/%m/%Y %H:%M} Thai: entry {r.entry:.2f}, stop {r.stop:.2f}, "
             f"target {r.tgt:.2f} -> {r.why}, R {r.R:+.2f}")
out = f"C:/Users/korap/taa/eye/trades/retest_{r.side}_{r.t.tz_convert(TH):%Y%m%d_%H%M}.png"
fig.savefig(out, dpi=85, bbox_inches="tight"); print(out)
