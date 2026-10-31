"""The side from price structure, against rule 11's state, drawn as colour strips under one week of M30
candles. The owner, 2026-10-30, on rule 11's drawings: the side came late both ways (07/10 BUY through
the fall, SELL at the bottom); "compare the colour strips with the price structure".

A side from structure [Claude, from the owner's 2e step 3 - "the structure breaks: the last swing low
goes"]: at each close, with the pivots fixed by then, a close above the latest fixed swing HIGH -> BUY, a
close below the latest fixed swing LOW -> SELL, otherwise the side stays as it was (none before the first
break).
  A - pivots of M30 (MT5 ZigZag 12/5/3), M30 closes;
  B - pivots of M15 (MT5 ZigZag 12/5/3), M15 closes - read at each M30 close.
Research only; no trading. Usage: structure_side.py 2026-10-06 2026-10-10   (Thai dates, inclusive)
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e, state11  # noqa: E402
from eye.research import state11_check as chk  # noqa: E402

COL = {"BUY": "#26a65b", "SELL": "#e0433b", "either": "#e8c547", "none": "#555555"}
STEP = {"M30": pd.Timedelta(minutes=30), "M15": pd.Timedelta(minutes=15)}


def structure_sides(df: pd.DataFrame, tf: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """The structure side at each bar close of ``df`` in ``(start, end]`` (indexed by close time)."""
    closes = df.index + STEP[tf]
    todo = np.nonzero((closes > start - pd.Timedelta(days=3)) & (closes <= end))[0]
    side, out = "none", {}
    for i in todo:
        f = df.iloc[max(0, i + 1 - state11.FRAME_BARS) : i + 1]
        piv = state11._zigzag(f)  # fixed by this close (confirm bar inside the frame)
        hi = next((p.price for p in reversed(piv) if p.kind.value == "HIGH"), None)
        lo = next((p.price for p in reversed(piv) if p.kind.value == "LOW"), None)
        c = float(df.close.iloc[i])
        if hi is not None and c > hi:
            side = "BUY"
        elif lo is not None and c < lo:
            side = "SELL"
        out[closes[i]] = side
    return pd.Series(out)


def main(first: str, last: str) -> None:
    full = bot2e.load_frames()
    m15 = full["M15"]
    m30 = state11.m30_from_m15(m15)
    start = pd.Timestamp(first, tz=chk.TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=chk.TH).tz_convert("UTC") + pd.Timedelta(days=1)
    todo = chk.select_closes(m30.index, start, end)
    bars = m30.iloc[todo[0] : todo[-1] + 1]
    close_t = bars.index + STEP["M30"]
    rule11 = [state11.side_of(state11.state_at(m30.iloc[: i + 1])) for i in todo]
    a = structure_sides(m30, "M30", start, end).reindex(close_t).tolist()
    b = structure_sides(m15, "M15", start, end).reindex(close_t, method="ffill").tolist()
    rows = [("rule 11", rule11), ("A: M30 structure", a), ("B: M15 structure", b)]

    plt.style.use("dark_background")
    fig, axes = plt.subplots(
        4, 1, figsize=(20, 10), sharex=True, gridspec_kw={"height_ratios": [12, 1, 1, 1], "hspace": 0.05}
    )
    ax = axes[0]
    for k, (o, h, lo_, c) in enumerate(bars[["open", "high", "low", "close"]].to_numpy()):
        col = "#2ecc71" if c >= o else "#ff4d4d"
        ax.plot([k, k], [lo_, h], color=col, lw=0.8)
        ax.add_patch(plt.Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.05), color=col))
    flips = {}
    for strip, (name, sides) in zip(axes[1:], rows, strict=True):
        for k, s in enumerate(sides):
            strip.axvspan(k - 0.5, k + 0.5, color=COL.get(s, COL["none"]), lw=0)
        strip.set_yticks([])
        strip.set_ylabel(name, rotation=0, ha="right", va="center", fontsize=10)
        flips[name] = sum(1 for k in range(1, len(sides)) if sides[k] != sides[k - 1])
    ticks = [
        k for k, t in enumerate(bars.index) if t.tz_convert(chk.TH).hour in (7, 13, 19) and t.minute == 0
    ]
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels(
        [f"{bars.index[k].tz_convert(chk.TH):%d/%m %H:%M}" for k in ticks], rotation=45, fontsize=9
    )
    ax.yaxis.tick_right()
    ax.grid(alpha=0.15)
    ax.set_xlim(-1, len(bars))
    ax.set_title(
        f"XAUUSD M30 {first} .. {last} (Thai) - the side: green BUY, red SELL, grey none; "
        f"changes in the week: " + ", ".join(f"{n} {v}" for n, v in flips.items()),
        fontsize=12,
    )
    out = HERE.parent / "trades" / f"structure_side_{first}_{last}.png"
    fig.savefig(out, dpi=90, bbox_inches="tight")
    print(out.name, flips)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
