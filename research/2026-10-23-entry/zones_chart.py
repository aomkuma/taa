"""The owner's way of drawing zones (2026-10-23: "your lines are too dense - not one colour packed together; get close
to my example; the sub-lines are the halves"): XAUUSD H4 2026-09-16 .. now with the zone grid's main lines (orange,
the grid in force now) and the half lines (grey dashed); each line labelled with how many H4 / D1 swings of the last
500 / 250 bars turned within 0.15 step of it (its strength) - the swing clusters rank the lines instead of being
drawn as lines of their own.

    .venv/Scripts/python research/2026-10-23-entry/zones_chart.py
"""

import contextlib
import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    import rederive_strong_levels as R  # noqa: E402

h = R.h4[R.h4.index >= "2026-09-15"]
t = R.pd.Timestamp(h.avail.iloc[-1])
st = R.zg.grid_at(R.G, t.value)
sw = R.sl.swings(R.B4, t.value, last=500) + R.sl.swings(R.B1, t.value, last=250)
fig, ax = plt.subplots(figsize=(16, 7), facecolor="#000000")
ax.set_facecolor("#000000")
for i, r in enumerate(h.itertuples()):
    up = r.close >= r.open
    ax.vlines(i, r.low, r.high, color="#ffffff" if up else "#b0b0b0", linewidth=0.7)
    ax.vlines(i, min(r.open, r.close), max(r.open, r.close), color="#ffffff" if up else "#4a4a4a", linewidth=3.2)
lo, hi = h.low.min() - 30, h.high.max() + 30
for k in range(-20, 21):
    for half in (0.0, 0.5):
        y = st.anchor + (k + half) * st.step
        if not lo < y < hi:
            continue
        n = sum(abs(s.price - y) <= 0.15 * st.step for s in sw)
        main = half == 0.0
        ax.axhline(y, color="#ff9900" if main else "#7a7a7a", linewidth=1.2 if main else 0.8, linestyle="-" if main else "--")
        ax.text(len(h) + 1, y, f"{y:.1f}  ({n})", color="#ff9900" if main else "#9a9a9a", fontsize=9, va="center")
ax.set_ylim(lo, hi)
ticks = list(range(0, len(h), 24))
ax.set_xticks(ticks, [h.index[i].tz_convert("Asia/Bangkok").strftime("%d %b") for i in ticks], color="#c9d1d9")
ax.tick_params(colors="#c9d1d9")
ax.grid(color="#1f3b2a", linestyle=":", linewidth=0.5)
ax.set_title(f"XAUUSD H4 - zone grid now: anchor {st.anchor:.2f}, step {st.step:.2f}; orange = zone lines, grey dashed = "
             "half lines; (n) = swings that turned within 0.15 step", color="#c9d1d9", fontsize=10)
out = HERE / "zones_owner_style.png"
fig.savefig(out, dpi=110, bbox_inches="tight", facecolor=fig.get_facecolor())
print(out, st.anchor, st.step)
