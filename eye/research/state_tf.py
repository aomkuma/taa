"""The prototype state reader (h1_state.py) on another timeframe - M30 built from the stored M15 bars - drawn
over a month, coloured by the side the bot would allow. The owner, 2026-10-30: "or try M30 instead of H1?".

Usage: state_tf.py 2026-08-01 2026-08-31 M30 v1
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import h1_state as hs  # noqa: E402
from walk import candles  # noqa: E402

from eye import bot2e  # noqa: E402

STEPS = {"M30": pd.Timedelta(minutes=30), "H1": pd.Timedelta(hours=1)}


def frame_of(tf: str) -> pd.DataFrame:
    full = bot2e.load_frames()
    if tf == "H1":
        return full["H1"]
    m15 = full["M15"]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    out = m15.resample("30min", label="left", closed="left").agg(agg).dropna()
    # keep only 30-minute bars made of two stored M15 bars (a missing half would fake a bar)
    n = m15.close.resample("30min", label="left", closed="left").count()
    return out[n.reindex(out.index) == 2]


def main(first: str, last: str, tf: str, mode: str) -> None:
    df = frame_of(tf)
    step = STEPS[tf]
    start = pd.Timestamp(first, tz=bot2e.TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=bot2e.TH).tz_convert("UTC") + pd.Timedelta(days=1)
    bars = df[(df.index >= start) & (df.index < end)]
    ends = df.index + step
    reads = []
    for t in bars.index:
        k = int(ends.searchsorted(t + step, side="right"))
        f = df.iloc[max(0, k - bot2e.FIB_BARS) : k]
        reads.append(hs.read(f, bot2e._zigzag(f), mode))
    fig, ax = plt.subplots(figsize=(20, 9))
    candles(ax, bars, width=0.5, lw=0.6)
    for i, s in enumerate(reads):
        ax.axvspan(i - 0.5, i + 0.5, color=hs.SIDE_COLOURS[hs.side_of(s)], alpha=0.45, zorder=0, lw=0)
        if s.kind == "sideways":
            for y in (s.lo, s.hi):
                ax.plot([i - 0.5, i + 0.5], [y, y], color="#5b2a86", lw=1.3)
    per_day = int(pd.Timedelta(days=1) / step)
    ticks = list(range(0, len(bars), per_day))
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        [f"{bars.index[k].tz_convert(bot2e.TH):%d/%m}" for k in ticks], rotation=45, fontsize=8
    )
    sides = {k: sum(hs.side_of(s) == k for s in reads) / len(reads) for k in hs.SIDE_COLOURS}
    side_share = sum(s.kind == "sideways" for s in reads) / len(reads)
    ax.set_title(
        f"{tf} {first} .. {last} prototype {mode} - side allowed: green BUY {sides['BUY']:.0%}, red SELL "
        f"{sides['SELL']:.0%}, yellow either {sides['either']:.0%}, grey none {sides['none']:.0%}; "
        f"purple = range edges (sideways {side_share:.0%})",
        fontsize=10,
    )
    fig.tight_layout()
    out = HERE.parent / "trades" / f"state_{tf}_{mode}_{first}_{last}.png"
    fig.savefig(out, dpi=100)
    print(out.name, {k: round(v, 2) for k, v in sides.items()}, f"sideways {side_share:.2f}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
