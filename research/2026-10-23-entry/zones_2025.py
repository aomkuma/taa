"""The owner's check (2026-10-23): "go back and draw the zones in 2025 to test that the system draws them right".
Only the bot's code draws (app/strategy/zone_grid.py, app/strategy/strong_levels.py). For each snapshot date: H4
candles of the 8 weeks before it (what the system had seen) and the 2 weeks after it (what price then did); the zone
lines (orange) and half lines (grey dashed) as the system knew them AT the snapshot, each with its strength (the
swings that turned within 0.15 step). After the snapshot nothing is redrawn - the lines stay as drawn, like the owner's.
Also: of the H4 swing turns in the 2 weeks after, the share within 0.15 step of a line or a half line.

    .venv/Scripts/python research/2026-10-23-entry/zones_2025.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from app.strategy import strong_levels as sl  # noqa: E402
from app.strategy import zone_grid as zg  # noqa: E402
from app.strategy.plan1_b2 import Bars  # noqa: E402

SNAPS = ["2025-02-03", "2025-04-01", "2025-06-02", "2025-08-01", "2025-10-01", "2025-12-01"]


def load(tf: str, hours: int) -> pd.DataFrame:
    d = pd.read_parquet(ROOT / f"data/history/FBS-Demo/XAUUSD/{tf}.parquet")
    d["t"] = pd.to_datetime(d.open_time, utc=True)
    d = d.drop_duplicates("t", keep="last").set_index("t").sort_index()
    d["avail"] = d.index + pd.Timedelta(hours=hours)
    return d


def to_bars(d: pd.DataFrame) -> Bars:
    return Bars(d.index.as_unit("ns").asi8, d.avail.dt.as_unit("ns").astype("int64").to_numpy(), d.open.to_numpy(float),
                d.high.to_numpy(float), d.low.to_numpy(float), d.close.to_numpy(float))


h4, d1 = load("H4", 4), load("D1", 24)
B4, B1 = to_bars(h4), to_bars(d1)
G = zg.grid_rows(B1.t_open, B1.o, B1.h, B1.lo, B1.c)
rows = []
for snap in SNAPS:
    t = pd.Timestamp(snap, tz="UTC")
    st = zg.grid_at(G, t.value)
    past = h4[(h4.index >= t - pd.Timedelta(weeks=8)) & (h4.avail <= t)]
    after = h4[(h4.index >= t) & (h4.index < t + pd.Timedelta(weeks=2))]
    x = pd.concat([past, after])
    lo, hi = x.low.min() - 0.3 * st.step, x.high.max() + 0.3 * st.step
    lines = sl.zone_lines(B4, B1, t.value, st.anchor, st.step, lo, hi)
    # the turns after the snapshot, found on the whole H4 series and kept if they sit after it
    later = [s for s in sl.swings(B4, after.avail.iloc[-1].value) if t.value <= B4.t_open[s.bar] < after.index[-1].value]
    near = [min(abs(s.price - lv.price) for lv in lines) <= 0.15 * st.step for s in later]
    rows.append(dict(snap=snap, anchor=st.anchor, step=st.step, turns_after=len(later), near_line=float(np.mean(near)) if near else np.nan))
    fig, ax = plt.subplots(figsize=(15, 6.5), facecolor="#000000")
    ax.set_facecolor("#000000")
    for i, r in enumerate(x.itertuples()):
        up = r.close >= r.open
        ax.vlines(i, r.low, r.high, color="#ffffff" if up else "#b0b0b0", linewidth=0.7)
        ax.vlines(i, min(r.open, r.close), max(r.open, r.close), color="#ffffff" if up else "#4a4a4a", linewidth=3.0)
    for lv in lines:
        main = lv.source == "zone"
        ax.axhline(lv.price, color="#ff9900" if main else "#7a7a7a", linewidth=1.2 if main else 0.8, linestyle="-" if main else "--")
        ax.text(len(x) + 1, lv.price, f"{lv.price:.1f}  ({lv.touches})", color="#ff9900" if main else "#9a9a9a", fontsize=9, va="center")
    ax.axvline(len(past) - 0.5, color="#3fa9ff", linewidth=1.0)
    ax.text(len(past), hi, "  snapshot: the lines were drawn here - after it nothing is redrawn", color="#3fa9ff", fontsize=9, va="top")
    ax.set_ylim(lo, hi)
    ticks = list(range(0, len(x), 30))
    ax.set_xticks(ticks, [x.index[i].tz_convert("Asia/Bangkok").strftime("%d %b %y") for i in ticks], color="#c9d1d9")
    ax.tick_params(colors="#c9d1d9")
    ax.set_title(f"XAUUSD H4, snapshot {snap}: anchor {st.anchor:.2f}, step {st.step:.2f} (the bot's code); after the line: "
                 f"{len(later)} H4 turns, {np.mean(near) * 100 if near else 0:.0f} % within 0.15 step of a line / half line",
                 color="#c9d1d9", fontsize=10)
    fig.savefig(HERE / "zones_2025" / f"zones_{snap}.png", dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
R = pd.DataFrame(rows)
print(R.round(3).to_string(index=False))
print("note: lines every half step with a band of 0.15 step cover 60 % of prices, so 60 % is what any price would show")
