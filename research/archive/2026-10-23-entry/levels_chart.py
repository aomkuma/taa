"""A picture for the owner (2026-10-23): XAUUSD H4, the last 500 bars before 2026-10-21 11:00 UTC, with the zone grid
(orange), every level the code calls strong (thin grey) and the stricter pick (blue: strength = touches x turn /
step, the strongest kept within 0.5 step) - to ask which levels the owner reads as strong.

    .venv/Scripts/python research/2026-10-23-entry/levels_chart.py
"""

import contextlib
import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    import rederive_strong_levels as R  # noqa: E402

t = R.pd.Timestamp("2026-10-21 11:00", tz="UTC")
st = R.zg.grid_at(R.G, t.value)
lv = [x for x in R.sl.strong_levels(R.B4, R.B1, t.value, st.step) if x.source == "swings"]
keep = []
for x in sorted(lv, key=lambda x: -(x.touches * x.turn / st.step)):
    if all(abs(x.price - k.price) > 0.5 * st.step for k in keep):
        keep.append(x)
h = R.h4[R.h4.avail <= t].iloc[-500:]
fig, ax = plt.subplots(figsize=(16, 8), facecolor="#0d1117")
ax.set_facecolor("#0d1117")
for i, r in enumerate(h.itertuples()):
    c = "#2ecc71" if r.close >= r.open else "#e74c3c"
    ax.vlines(i, r.low, r.high, color=c, linewidth=0.6)
    ax.vlines(i, min(r.open, r.close), max(r.open, r.close), color=c, linewidth=2.2)
lo, hi = h.low.min() - 40, h.high.max() + 40
for x in lv:
    if lo < x.price < hi:
        ax.axhline(x.price, color="#8b949e", linewidth=0.4, alpha=0.6)
for x in keep:
    if lo < x.price < hi:
        ax.axhline(x.price, color="#3fa9ff", linewidth=1.4)
        ax.text(len(h) + 2, x.price, f"{x.price:.0f} ({x.touches})", color="#3fa9ff", fontsize=8, va="center")
k = -40
while True:
    y = st.anchor + k * st.step
    if y > hi:
        break
    if y > lo:
        ax.axhline(y, color="#e08a00", linewidth=1.0, linestyle="--")
        ax.text(-2, y, f"{y:.0f}", color="#e08a00", fontsize=8, va="center", ha="right")
    k += 1
ax.set_ylim(lo, hi)
ticks = list(range(0, len(h), 60))
ax.set_xticks(ticks, [h.index[i].tz_convert("Asia/Bangkok").strftime("%d %b") for i in ticks], color="#c9d1d9")
ax.tick_params(colors="#c9d1d9")
ax.set_title("XAUUSD H4, 500 bars to 21 Oct 2026 18:00 Thai - orange dashed: zone grid; grey: every 'strong' level (code v1); "
             "blue: the stricter pick (touches)", color="#c9d1d9", fontsize=10)
out = HERE / "levels_2026-10-21.png"
fig.savefig(out, dpi=110, bbox_inches="tight", facecolor=fig.get_facecolor())
print(out)
