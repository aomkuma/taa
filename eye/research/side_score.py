"""How well a side strip follows the price structure, as numbers [Claude, research]. The owner, the
2026-10-30:
strips are wrong and "you can see it from the picture" - so the picture is turned into a measure Claude can
check before showing anything.

The structure, in hindsight: MT5's ZigZag 12/5/3 on the whole M30 series of the period (the final pivots).
  Each M30 bar between two pivots belongs to that leg - up from a LOW to a HIGH, down from a HIGH to a LOW. A
  side at a close (decided with closed bars only) is then held over the next bar:
- right / wrong USD - the next bar's close-to-close move, summed where the side agrees / disagrees with the
  leg;
- strip P&L - BUY earns the move, SELL earns minus the move, none earns 0 (USD per 0.01 oz-lot unit, no
  costs);
- lag - for every leg of at least ``BIG`` USD, the hours from the leg's start to the first close with its
  side, and the share of the leg's move made before that. Sides: rule 11 (from the stability check table), A
  (M30 structure), B (M15 structure) - structure_side.py.

Usage: side_score.py 2026-07-01 2026-10-28"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from eye import bot2e, state11  # noqa: E402
from eye.research import state11_check as chk  # noqa: E402
from eye.research import structure_side as ss  # noqa: E402

BIG = 50.0  # USD - a leg the owner would call a move
HALF = pd.Timedelta(minutes=30)


def rule11_sides(first: str, last: str, close_t: pd.DatetimeIndex) -> pd.Series:
    d = pd.read_csv(HERE / "state11_check" / f"{first}_{last}.csv")
    t = pd.to_datetime(d.thai_time).dt.tz_localize(chk.TH).dt.tz_convert("UTC")
    side = []
    for _, r in d.iterrows():
        if r.kind == "up":
            side.append("BUY")
        elif r.kind == "down":
            side.append("SELL")
        elif r.kind == "sideways":
            leg = int(r.legs) + 1
            side.append("either" if leg >= 6 else ("SELL" if r.last_touch == "HIGH" else "BUY"))
        else:
            side.append("none")
    return pd.Series(side, index=t).reindex(close_t)


def hindsight_legs(m30: pd.DataFrame) -> pd.Series:
    """+1 / -1 for each bar by the final ZigZag leg it lies in (NaN outside the pivots)."""
    piv = state11._zigzag(m30)
    leg = pd.Series(np.nan, index=m30.index)
    for a, b in pairwise(piv):
        leg.iloc[a.pivot_pos + 1 : b.pivot_pos + 1] = 1.0 if b.kind.value == "HIGH" else -1.0
    return leg


def main(first: str, last: str) -> None:
    full = bot2e.load_frames()
    m15 = full["M15"]
    m30_all = state11.m30_from_m15(m15)
    start = pd.Timestamp(first, tz=chk.TH).tz_convert("UTC")
    end = pd.Timestamp(last, tz=chk.TH).tz_convert("UTC") + pd.Timedelta(days=1)
    todo = chk.select_closes(m30_all.index, start, end)
    bars = m30_all.iloc[todo[0] : todo[-1] + 1]
    close_t = bars.index + HALF
    move = bars.close.shift(-1) - bars.close  # held over the next bar
    leg = hindsight_legs(m30_all[(m30_all.index >= start - pd.Timedelta(days=5)) & (m30_all.index < end)])
    leg_next = leg.shift(-1).reindex(bars.index)  # the leg the next bar lies in
    sides = {
        "rule 11": rule11_sides(first, last, close_t),
        "A: M30 structure": ss.structure_sides(m30_all, "M30", start, end).reindex(close_t),
        "B: M15 structure": ss.structure_sides(m15, "M15", start, end).reindex(close_t, method="ffill"),
    }
    total = float(move.abs().sum())
    print(f"{first} .. {last}: {len(bars)} M30 closes; total |move| {total:.0f} USD; legs >= {BIG:.0f} USD:")
    piv = state11._zigzag(m30_all[(m30_all.index >= start - pd.Timedelta(days=5)) & (m30_all.index < end)])
    big = [(a, b) for a, b in pairwise(piv) if abs(b.price - a.price) >= BIG]
    big = [(a, b) for a, b in big if start <= pd.Timestamp(a.pivot_at) < end]
    print(f"  {len(big)} legs")
    for name, s in sides.items():
        sgn = s.map({"BUY": 1.0, "SELL": -1.0}).fillna(0.0).to_numpy()
        mv = move.to_numpy()
        lg = leg_next.to_numpy()
        ok = np.nan_to_num(mv)
        right = float(np.abs(ok[(sgn != 0) & (sgn == lg)]).sum())
        wrong = float(np.abs(ok[(sgn != 0) & (sgn == -lg)]).sum())
        pnl = float(np.nansum(sgn * mv))
        lags, before = [], []
        sv = pd.Series(sgn, index=bars.index)
        for a, b in big:
            want = 1.0 if b.kind.value == "HIGH" else -1.0
            seg = sv[(sv.index > pd.Timestamp(a.pivot_at)) & (sv.index <= pd.Timestamp(b.pivot_at))]
            hit = seg[seg == want]
            if hit.empty:
                lags.append(np.inf)
                before.append(1.0)
                continue
            t = hit.index[0]
            lags.append((t + HALF - pd.Timestamp(a.pivot_at)) / pd.Timedelta(hours=1))
            px = float(bars.close.loc[t])
            before.append(abs(px - a.price) / abs(b.price - a.price))
        missed = sum(1 for x in lags if x == np.inf)
        fin = [x for x in lags if x != np.inf]
        print(
            f"  {name:18s} right {right:6.0f}  wrong {wrong:6.0f}  "
            f"({right / max(right + wrong, 1):.0%} right)  "
            f"strip P&L {pnl:+6.0f}  | big legs: median lag "
            f"{np.median(fin) if fin else float('nan'):4.1f} h, "
            f"median share gone before {np.median(before):.0%}, never on its side {missed}/{len(big)}"
        )


if __name__ == "__main__":
    main(*(sys.argv[1:3] if len(sys.argv) > 2 else ("2026-07-01", "2026-10-28")))
