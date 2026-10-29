"""What the bot reads on H1, hour by hour, drawn over the month's H1 chart - to compare with the owner's own
picture of the same month (the owner, 2026-10-29: "just look at the picture against what the bot reads").

For every H1 close of the month: the H1 frame cut at that close (closed bars only, the last 1,500), its fixed
ZigZag pivots, rule 11's H1 range (sideways or not) and rule 1's lean - the bot's own functions. Chart:
H1 candles, the fixed pivots as the bot knew them at the month's end, a background band per hour (sideways /
lean SELL / lean BUY / none) and, where sideways, the range's two edges.

Usage: h1_read_month.py 2026-10-01 2026-10-28
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

from walk import candles  # noqa: E402

from eye import bot2e  # noqa: E402

COLOURS = {"sideways": "#b48ad6", "SELL": "#f2a3a3", "BUY": "#9fd9a8", "none": "#dddddd"}


def main(first: str, last: str) -> None:
    full = bot2e.load_frames()
    h1_all = full["H1"]
    start = pd.Timestamp(first, tz=bot2e.TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=bot2e.TH).tz_convert("UTC") + pd.Timedelta(days=1)
    bars = h1_all[(h1_all.index >= start) & (h1_all.index < end)]
    reads = []
    for t in bars.index:
        now = t + pd.Timedelta(hours=1)
        h1 = bot2e.cut({"H1": h1_all}, now)["H1"].tail(bot2e.FIB_BARS)
        piv = bot2e._zigzag(h1)
        rng = bot2e.h1_range(h1, piv)
        lean, _ = bot2e.h1_lean(h1, piv)
        if rng is not None and rng.sideways:
            reads.append(("sideways", rng.lo, rng.hi, rng.leg))
        else:
            reads.append((lean or "none", None, None, None))
    fig, ax = plt.subplots(figsize=(20, 9))
    candles(ax, bars, width=0.5, lw=0.6)
    for i, (kind, lo, hi, _leg) in enumerate(reads):
        ax.axvspan(i - 0.5, i + 0.5, color=COLOURS[kind], alpha=0.35, zorder=0, lw=0)
        if kind == "sideways":
            ax.plot([i - 0.5, i + 0.5], [lo, lo], color="#5b2a86", lw=1.4)
            ax.plot([i - 0.5, i + 0.5], [hi, hi], color="#5b2a86", lw=1.4)
    last_now = bars.index[-1] + pd.Timedelta(hours=1)
    h1_end = bot2e.cut({"H1": h1_all}, last_now)["H1"].tail(bot2e.FIB_BARS)
    for s in bot2e._zigzag(h1_end):
        at = pd.Timestamp(s.pivot_at)
        if at in bars.index:
            x = bars.index.get_loc(at)
            ax.annotate(f"{s.price:.0f}", (x, s.price), fontsize=7, color="#1f5fbf",
                        ha="center", va="bottom" if s.kind.value == "HIGH" else "top")  # fmt: skip
    ticks = list(range(0, len(bars), 24))
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        [f"{bars.index[k].tz_convert(bot2e.TH):%d/%m %H:%M}" for k in ticks], rotation=45, fontsize=8
    )
    n = len(reads)
    share = {k: sum(r[0] == k for r in reads) / n for k in COLOURS}
    ax.set_title(
        f"H1 {first} .. {last} (Thai) - the bot's reading each hour: purple = H1 sideways (rule 11, edges) "
        f"{share['sideways']:.0%}, red = lean SELL {share['SELL']:.0%}, green = lean BUY {share['BUY']:.0%}, "
        f"grey = none {share['none']:.0%}; numbers = fixed H1 ZigZag pivots",
        fontsize=10,
    )
    fig.tight_layout()
    out = HERE.parent / "trades" / f"h1_read_{first}_{last}.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=100)
    print(out, share)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
