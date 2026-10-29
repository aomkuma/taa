"""A prototype reader of the H1 state - range / trend up / trend down - that ignores the swings inside
a range.

The owner, 2026-10-30: the way to fix it is clear; the question is how it becomes code that reads the chart
the way the eye does. Rule 11 as built needs every H1 pivot to sit at an edge, so a range's middle swings end
it. This reader walks the fixed H1 pivots in time order and keeps one range:

- the first two pivots after a start or a break give the provisional edges ``lo`` / ``hi``;
- a later pivot at an edge (a HIGH at or above ``lo + 0.88 h``, a LOW at or below ``lo + 0.12 h``) is a touch;
  one beyond the edge but without an H1 close beyond the break level widens that edge to it;
- a pivot in the middle is ignored - the range stands;
- an H1 close beyond ``hi + 0.27 h`` or ``lo - 0.27 h`` is a break: the state becomes a trend that way, and
  the next two pivots after the break start a new range;
- legs = the alternating edge touches; sideways from two legs (each edge reached once after the first).

Closed bars only: at each H1 close the pivots are those fixed by then. Draws the month like h1_read_month.py.
Usage: h1_state.py 2026-09-24 2026-10-28"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))

from walk import candles  # noqa: E402

from eye import bot2e  # noqa: E402

TOUCH_HI, TOUCH_LO, BREAK = 0.88, 0.12, 0.27
COLOURS = {"sideways": "#b48ad6", "forming": "#e8dcf2", "down": "#f2a3a3", "up": "#9fd9a8", "none": "#dddddd"}


@dataclass
class State:
    kind: str  # none / forming / sideways / up / down
    lo: float = np.nan
    hi: float = np.nan
    legs: int = 0
    last_touch: str = ""  # HIGH / LOW


def read(h1: pd.DataFrame, piv: list) -> State:
    """The H1 state at the last closed bar of ``h1`` from its fixed pivots (time order)."""
    close = h1.close.to_numpy(np.float64)
    st, trend = State("none"), "none"
    start = 0  # index into piv where the current range's pivots begin
    i = 0
    while i < len(piv):
        if i - start < 1:  # need two pivots for the provisional edges
            i += 1
            continue
        if i - start == 1:
            a, b = piv[start], piv[i]
            st = State("forming", min(a.price, b.price), max(a.price, b.price), 1, b.kind.value)
        else:
            q, h = piv[i], st.hi - st.lo
            if h <= 0:
                start, i = i, i + 1
                continue
            if q.kind.value == "HIGH" and q.price >= st.lo + TOUCH_HI * h:
                st.hi = max(st.hi, q.price)
                if st.last_touch != "HIGH":
                    st.legs, st.last_touch = st.legs + 1, "HIGH"
            elif q.kind.value == "LOW" and q.price <= st.lo + TOUCH_LO * h:
                st.lo = min(st.lo, q.price)
                if st.last_touch != "LOW":
                    st.legs, st.last_touch = st.legs + 1, "LOW"
        # a break: an H1 close beyond the break level, between this pivot's bar and the next pivot's bar
        h = st.hi - st.lo
        nxt = piv[i + 1].pivot_pos if i + 1 < len(piv) else len(close)
        seg = close[piv[i].pivot_pos + 1 : nxt + 1]
        up = np.nonzero(seg > st.hi + BREAK * h)[0]
        dn = np.nonzero(seg < st.lo - BREAK * h)[0]
        if h > 0 and (up.size or dn.size):
            trend = "up" if (up[0] if up.size else 1e9) < (dn[0] if dn.size else 1e9) else "down"
            start = i + 1  # the next two pivots start a new range
            st = State(trend)
        i += 1
    if st.kind in ("forming", "sideways") or (st.kind == "none" and trend == "none"):
        if st.kind == "forming" and st.legs >= 2:
            st.kind = "sideways"
        elif st.kind == "forming" and trend != "none":
            st.kind = trend  # a range still forming after a break: the trend still holds
    return st


def main(first: str, last: str) -> None:
    full = bot2e.load_frames()
    h1_all = full["H1"]
    start = pd.Timestamp(first, tz=bot2e.TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=bot2e.TH).tz_convert("UTC") + pd.Timedelta(days=1)
    bars = h1_all[(h1_all.index >= start) & (h1_all.index < end)]
    reads = []
    for t in bars.index:
        h1 = bot2e.cut({"H1": h1_all}, t + pd.Timedelta(hours=1))["H1"].tail(bot2e.FIB_BARS)
        reads.append(read(h1, bot2e._zigzag(h1)))
    fig, ax = plt.subplots(figsize=(20, 9))
    candles(ax, bars, width=0.5, lw=0.6)
    for i, s in enumerate(reads):
        ax.axvspan(i - 0.5, i + 0.5, color=COLOURS[s.kind], alpha=0.4, zorder=0, lw=0)
        if s.kind in ("sideways", "forming"):
            for y in (s.lo, s.hi):
                ax.plot([i - 0.5, i + 0.5], [y, y], color="#5b2a86", lw=1.3)
    h1_end = bot2e.cut({"H1": h1_all}, bars.index[-1] + pd.Timedelta(hours=1))["H1"].tail(bot2e.FIB_BARS)
    for p in bot2e._zigzag(h1_end):
        at = pd.Timestamp(p.pivot_at)
        if at in bars.index:
            ax.annotate(
                f"{p.price:.0f}", (bars.index.get_loc(at), p.price), fontsize=7, color="#1f5fbf", ha="center",
                va="bottom" if p.kind.value == "HIGH" else "top",
            )  # fmt: skip
    ticks = list(range(0, len(bars), 24))
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        [f"{bars.index[k].tz_convert(bot2e.TH):%d/%m}" for k in ticks], rotation=45, fontsize=8
    )
    share = {k: sum(s.kind == k for s in reads) / len(reads) for k in COLOURS}
    ax.set_title(
        f"H1 {first} .. {last} prototype: sideways {share['sideways']:.0%}, light purple "
        f"forming {share['forming']:.0%}, red down {share['down']:.0%}, green up {share['up']:.0%}, "
        f"grey none {share['none']:.0%}",
        fontsize=10,
    )
    fig.tight_layout()
    out = HERE.parent / "trades" / f"h1_state_{first}_{last}.png"
    fig.savefig(out, dpi=100)
    print(out, {k: round(v, 3) for k, v in share.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
