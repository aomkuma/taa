"""Sit at a sampled moment and wait, one step at a time, until the picture is worth trading.

The owner, 2026-10-28, after looking at the first sheets: *"90 % of them are not spots worth watching.
The structure is not clear, the wave legs are not complete; and price is not near the support or
resistance of the side you are watching - or if it is near, it looks likely to go straight through,
because the structure at that level gives no picture."* And then: *"sampling is not wrong. But if price
is not in a tradeable shape, wait for the moment - advance the chart one bar at a time until the picture
is clear. If it is not pretty, keep going until you find a spot that is."*

So a sampled moment is not a decision. It is **where I sit down**. From there the chart advances a few
bars at a time and I look again, seeing only what had printed by then - never a bar from the future. The
waiting is part of the record: how long I sat before a setup appeared, or that none did.

    python eye/walk.py <moment id> <step>     # draw that moment advanced by <step> M5 bars
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TH = "Asia/Bangkok"
BARS = 400  # the entry frame: about 33 hours of M5, the width of the owner's own screen
CONTEXT_BARS = 500  # the frame above, H1: about three weeks, so the LEFT of the chart goes back far

# The owner, 2026-10-28, on the first walk: *"the left of the chart shows nothing at all - there are no
# levels there"* and *"the structure is not pretty, there is no picture telling you what it is."* Nine
# hours of M5 cannot show a level: everything on it was built minutes or hours ago. Asked whether the
# chart has to go back days, the owner: *"I mean the LEFT of the chart - it has to go back far."* So
# both frames are wide now: the entry frame as wide as the owner's own screen, and the frame above three
# weeks deep. A moment is only worth watching when price is working against something the left built.


def frame(tf: str) -> pd.DataFrame:
    df = pd.read_parquet(ROOT / f"data/history/FBS-Demo/XAUUSD/{tf}.parquet")
    col = next(c for c in df.columns if "time" in c.lower())
    df[col] = pd.to_datetime(df[col], utc=True)
    return df.set_index(col).sort_index()


def moment(mid: str) -> pd.Timestamp:
    """A sampled moment by id, or a Thai wall-clock time written out - the owner, 2026-10-28: run real
    days, one at a time, instead of sampled moments, so nothing is selected and every wait is walked."""
    if "-" in mid:  # "2026-04-01 07:00" Thai
        return pd.Timestamp(mid, tz=TH).tz_convert("UTC")
    for r in csv.DictReader((HERE / "moments.csv").open(encoding="utf-8")):
        if r["id"] == mid:
            return pd.Timestamp(r["cutoff_utc"])
    raise SystemExit(f"no moment {mid}")


def candles(ax: plt.Axes, bars: pd.DataFrame, width: float = 0.34, lw: float = 1.0) -> None:
    for i, (_, b) in enumerate(bars.iterrows()):
        up = b.close >= b.open
        colour = "#10795f" if up else "#a83242"
        ax.plot([i, i], [b.low, b.high], color=colour, linewidth=lw, zorder=2)
        lo, hi = (b.open, b.close) if up else (b.close, b.open)
        ax.add_patch(
            plt.Rectangle(
                (i - width, lo), width * 2, max(hi - lo, 0.01), facecolor=colour, edgecolor=colour, zorder=3
            )
        )
    loc = bars.index.tz_convert(TH)
    ticks = list(range(0, len(bars), max(1, len(bars) // 20)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{loc[i]:%d/%m %H:%M}" for i in ticks], rotation=45, ha="right", fontsize=8)
    ax.grid(True, alpha=0.18, linewidth=0.6)
    ax.margins(x=0.01)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def draw(mid: str, step: int) -> None:
    start = moment(mid)
    now = start + pd.Timedelta(minutes=5 * step)
    entry = frame("M5")
    entry = entry[entry.index + pd.Timedelta(minutes=5) <= now].iloc[-BARS:]
    above = frame("H1")
    above = above[above.index + pd.Timedelta(hours=1) <= now].iloc[-CONTEXT_BARS:]

    fig, (ax_h1, ax) = plt.subplots(2, 1, figsize=(21, 13), dpi=100, height_ratios=[1, 1])
    candles(ax_h1, above, width=0.34, lw=0.9)
    ax_h1.set_title(
        f"H1 - three weeks back, where the levels are   (to {above.index[-1].tz_convert(TH):%d/%m %H:%M} Thai)",
        fontsize=11,
    )
    candles(ax, entry, width=0.3, lw=0.7)
    loc = entry.index.tz_convert(TH)
    ax.set_title(
        f"M5 - {mid}, +{step} bars ({step * 5} min). "
        f"Now {loc[-1]:%d/%m %H:%M} Thai, last close {entry.close.iloc[-1]:.2f}",
        fontsize=12,
    )
    frame_, loc_ = entry, loc
    fig.tight_layout()
    stem = mid.replace(" ", "_").replace(":", "") if "-" in mid else f"{int(mid):03d}"
    out = HERE / "walk" / f"{stem}_{step:03d}.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out)
    print(f"{out}")
    print(f"  now {loc_[-1]:%d/%m %H:%M} Thai   last close {frame_.close.iloc[-1]:.2f}")
    print(f"  M5 window {loc_[0]:%d/%m %H:%M} ..   H1 window {above.index[0].tz_convert(TH):%d/%m %H:%M} ..")


if __name__ == "__main__":
    draw(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
