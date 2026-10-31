"""Rule 11's M30 state drawn over the stored months (eye/BOT_RULES.md rule 11; a drawing, no trading).

For every M30 close of the period the state from the closed bars at that ``now`` (the 1,500-bar frame, as
``state11_check`` reads it) is drawn over the M30 candles: the background is the side the state allows
(BUY green, SELL red, either yellow, none grey), a sideways range's edges are purple with the break lines
dashed, every range's E and B and every break are marked, and the final frame's pivots carry their price.

Usage: state11_draw.py 2026-07-01 2026-07-31          Thai dates; writes eye/trades/state11_<first>_<last>.png
"""

from __future__ import annotations

import sys
from collections.abc import Hashable, Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent))

from walk import candles  # noqa: E402

from eye import bot2e, state11  # noqa: E402
from eye.research import state11_check as chk  # noqa: E402

SIDE_COLOURS = {"BUY": "#9fd9a8", "SELL": "#f2a3a3", "either": "#f3e6a0", "none": "#dddddd"}  # as h1_state.py
EDGE = "#5b2a86"


def shares(values: Sequence[Hashable], keys: Sequence[Hashable]) -> dict[Hashable, float]:
    """The share of each key among ``values`` (0 for a key that never occurs)."""
    n = len(values)
    return {k: sum(v == k for v in values) / n for k in keys}


def main(first: str, last: str) -> None:
    m30 = state11.m30_from_m15(bot2e.load_frames()["M15"])
    start = pd.Timestamp(first, tz=chk.TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=chk.TH).tz_convert("UTC") + pd.Timedelta(days=1)
    todo = chk.select_closes(m30.index, start, end)
    bars = m30.iloc[todo[0] : todo[-1] + 1]
    states = [state11.state_at(m30.iloc[: i + 1]) for i in todo]
    pos = {t: k for k, t in enumerate(bars.index)}

    fig, ax = plt.subplots(figsize=(24, 10))
    candles(ax, bars, width=0.5, lw=0.6)
    for k, st in enumerate(states):
        ax.axvspan(k - 0.5, k + 0.5, color=SIDE_COLOURS[state11.side_of(st)], alpha=0.45, zorder=0, lw=0)
        r = st.walk.range
        if st.kind == "sideways" and r is not None:
            h = r.hi - r.lo
            for y in (r.lo, r.hi):
                ax.plot([k - 0.5, k + 0.5], [y, y], color=EDGE, lw=1.3, zorder=4)
            for y in (r.hi + state11.BREAK_BEYOND * h, r.lo - state11.BREAK_BEYOND * h):
                ax.plot([k - 0.5, k + 0.5], [y, y], color=EDGE, lw=0.6, ls="--", zorder=4)

    span = float(bars.high.max() - bars.low.min())
    seen_range: set = set()
    seen_break: set = set()
    for st in states:
        r = st.walk.range
        if r is not None and (st.e_time, st.b_time) not in seen_range:
            seen_range.add((st.e_time, st.b_time))
            for name, t, piv in (("E", st.e_time, r.e), ("B", st.b_time, r.b)):
                if t in pos:
                    up = piv.kind.value == "HIGH"
                    ax.plot(pos[t], piv.price, marker="v" if up else "^", color=EDGE, ms=9, zorder=6)
                    ax.annotate(
                        f"{name} {piv.price:.2f}",
                        (pos[t], piv.price),
                        xytext=(0, 12 if up else -14),
                        textcoords="offset points",
                        ha="center",
                        fontsize=8,
                        color=EDGE,
                        weight="bold",
                    )
        br = st.walk.last_break
        if br is not None and st.break_time not in seen_break:
            seen_break.add(st.break_time)
            if st.break_time in pos:
                k, up = pos[st.break_time], br.way == "up"
                c = float(bars.close.iloc[k])
                ax.annotate(
                    "",
                    xy=(k, c),
                    xytext=(k, c + (-1 if up else 1) * 0.04 * span),
                    arrowprops={"arrowstyle": "-|>", "color": "#1f4fd8", "lw": 1.8},
                    zorder=7,
                )

    final = m30.iloc[: todo[-1] + 1]
    for p in state11._zigzag(final.iloc[-state11.FRAME_BARS :]):
        t = pd.Timestamp(p.pivot_at)
        if t in pos:
            up = p.kind.value == "HIGH"
            ax.annotate(
                f"{p.price:.0f}",
                (pos[t], p.price),
                xytext=(0, 4 if up else -10),
                textcoords="offset points",
                ha="center",
                fontsize=6,
                color="#333333",
            )

    thai = bars.index.tz_convert(chk.TH)
    ticks = [k for k in range(len(bars)) if k == 0 or thai[k].date() != thai[k - 1].date()]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{thai[k]:%d/%m}" for k in ticks], rotation=45, fontsize=8)
    sides = shares([state11.side_of(s) for s in states], list(SIDE_COLOURS))
    cases = shares([s.case for s in states], [1, 2, 3, 4])
    side_txt = ", ".join(f"{k} {v:.0%}" for k, v in sides.items())
    case_txt = ", ".join(f"case {k} {v:.0%}" for k, v in cases.items())
    ax.set_title(
        f"M30 state (rule 11) {first} .. {last} Thai - side allowed: {side_txt}; {case_txt}; "
        "purple = range edges, dashed = break lines, E / B = range start, arrow = breaking close",
        fontsize=10,
    )
    fig.tight_layout()
    out = ROOT / "eye" / "trades" / f"state11_{first}_{last}.png"
    fig.savefig(out, dpi=100)
    print(
        f"{first}..{last}: {len(states)} closes; side {{{side_txt}}}; {case_txt}; "
        f"ranges {len(seen_range)}, breaks {len(seen_break)}"
    )
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
