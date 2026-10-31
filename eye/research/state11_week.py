"""Rule 11's M30 state drawn one short stretch at a time, in the look of the owner's MT5 screen: black
background, plain candles, the side the bot allows as a strip under the price, a label only where the side
changes, and the range edges only while M30 is sideways. The owner, 2026-10-30, on the month drawings: "still
hard to read".

Usage: state11_week.py 2026-08-17 2026-08-21   (Thai dates, inclusive)
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

from eye import bot2e, state11  # noqa: E402
from eye.research import state11_check as chk  # noqa: E402

SIDE = {"BUY": "#26a65b", "SELL": "#e0433b", "either": "#e8c547", "none": "#777777"}
WHY = {1: "range", 2: "trend", 3: "range (7 days)", 4: "no side"}


def main(first: str, last: str) -> None:
    m30 = state11.m30_from_m15(bot2e.load_frames()["M15"])
    start = pd.Timestamp(first, tz=chk.TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=chk.TH).tz_convert("UTC") + pd.Timedelta(days=1)
    todo = chk.select_closes(m30.index, start, end)
    bars = m30.iloc[todo[0] : todo[-1] + 1]
    states = [state11.state_at(m30.iloc[: i + 1]) for i in todo]
    sides = [state11.side_of(s) for s in states]

    plt.style.use("dark_background")
    fig, (ax, strip) = plt.subplots(
        2, 1, figsize=(20, 9), sharex=True, gridspec_kw={"height_ratios": [12, 1], "hspace": 0.03}
    )
    for k, (o, h, lo, c) in enumerate(bars[["open", "high", "low", "close"]].to_numpy()):
        col = "#2ecc71" if c >= o else "#ff4d4d"
        ax.plot([k, k], [lo, h], color=col, lw=0.8)
        ax.add_patch(plt.Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.05), color=col))
    for k, st in enumerate(states):
        r = st.walk.range
        if st.kind == "sideways" and r is not None:
            for y in (r.lo, r.hi):
                ax.plot([k - 0.5, k + 0.5], [y, y], color="#c39bff", lw=2)
        strip.axvspan(k - 0.5, k + 0.5, color=SIDE[sides[k]], lw=0)
    # a label only where the side or its reason changes
    span = float(bars.high.max() - bars.low.min())
    for k, st in enumerate(states):
        if k and (sides[k], st.case) == (sides[k - 1], states[k - 1].case):
            continue
        ax.axvline(k - 0.5, color=SIDE[sides[k]], lw=1, ls=":", alpha=0.8)
        ax.text(
            k, float(bars.high.max()) + 0.02 * span, f"{sides[k]}\n{WHY[st.case]}", color=SIDE[sides[k]],
            fontsize=11, fontweight="bold", ha="left", va="bottom",
        )  # fmt: skip
    ticks = [
        k for k, t in enumerate(bars.index) if t.tz_convert(chk.TH).hour in (7, 13, 19) and t.minute == 0
    ]
    strip.set_xticks(ticks)
    strip.set_xticklabels(
        [f"{bars.index[k].tz_convert(chk.TH):%d/%m %H:%M}" for k in ticks], rotation=45, fontsize=9
    )
    strip.set_yticks([])
    strip.set_ylabel("side", fontsize=10)
    ax.set_ylim(float(bars.low.min()) - 0.03 * span, float(bars.high.max()) + 0.12 * span)
    ax.yaxis.tick_right()
    ax.grid(alpha=0.15)
    ax.set_title(
        f"XAUUSD M30  {first} .. {last} (Thai) - the side the bot allows (strip: green BUY, red SELL); "
        "purple lines = the range while sideways",
        fontsize=12,
    )
    out = HERE.parent / "trades" / f"state11_week_{first}_{last}.png"
    fig.savefig(out, dpi=90, bbox_inches="tight")
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
