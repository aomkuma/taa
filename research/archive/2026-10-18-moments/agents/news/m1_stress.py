"""Round 2, task 1 on M1 history (2021-09 .. 2026-02, worst-case order inside the release minute as straddle_m1.py):
S2 for trigger D, exit after HOLD minutes, a fill gap GAP and a widened spread X at the release second. All USD
amounts at a gold price of 4000, scaled by price. The widened spread is modelled as triggers on the mid at
D - X/2 from the reference (a wide quote reaches the trigger earlier) and an entry X/2 worse; the stop and the
exit (after the first minute) use the bar's own spread.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/m1_stress.py [--test] [--events CPI,NFP]
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import SLIP, Gold, events  # noqa: E402

TEST = "--test" in sys.argv
EVENTS = sys.argv[sys.argv.index("--events") + 1].split(",") if "--events" in sys.argv else ["CPI", "NFP"]


def one(G: Gold, i: int, D: float, S: float, gap: float, X: float, hold: int):
    o, h, lo, c, sp = G.o[i], G.h[i], G.lo[i], G.c[i], G.sp[i]
    half = max(X / 2, sp / 2)
    mid0 = o + sp / 2
    up_mid, dn_mid = mid0 + sp / 2 + D - half, mid0 - sp / 2 - D + half  # the mid level at which a wide quote triggers
    mid_h, mid_lo = h + sp / 2, lo + sp / 2
    hu, hd = mid_h >= up_mid, mid_lo <= dn_mid
    if not (hu or hd):
        return None
    if hu and hd:
        s, how = (1 if c < o else -1), "whip"
    else:
        s, how = (1 if hu else -1), "time"
    trig = up_mid if s > 0 else dn_mid
    entry = trig + s * (half + gap + SLIP)
    adv = (lo - entry) if s > 0 else (entry - h - sp)
    if adv <= -S:
        return s, -S - SLIP - gap, "stop" if how == "time" else "whip"  # the stop fills a gap past its level too
    for j in range(i + 1, i + hold):
        a2 = (G.lo[j] - entry) if s > 0 else (entry - G.h[j] - G.sp[j])
        if a2 <= -S:
            return s, -S - SLIP - gap, "stop"
    x = i + hold - 1
    ex = (G.c[x] - SLIP) if s > 0 else (G.c[x] + G.sp[x] + SLIP)
    return s, (ex - entry) * s, how


def main() -> None:
    G = Gold()
    ev = events(extra=True)
    ev = ev[ev.main.isin(EVENTS)]
    ev = ev[ev.per == "T"] if TEST else ev[ev.per != "T"]
    rows = []
    for r in ev.itertuples():
        i = G.pos.get(r.t)
        if i is None:
            continue
        i = int(i)
        k = G.c[i - 1] / 4000
        for D, hold, gap, X in itertools.product((2, 3, 5), (1, 5), (1, 2, 3, 4), (0, 2, 4)):
            out = one(G, i, D * k, 8 * k, gap * k, X * k, hold)
            if out:
                rows.append(dict(t=r.t, main=r.main, per=r.per, D=D, hold=hold, gap=gap, X=X, side=out[0],
                                 usd=out[1] / k, R=out[1] / (8 * k + SLIP), how=out[2]))
    d = pd.DataFrame(rows)
    tag = ("test" if TEST else "design") + "_" + "-".join(EVENTS)
    d.to_parquet(f"research/2026-10-18-moments/agents/news/m1_stress_{tag}.parquet")
    pd.set_option("display.width", 220)
    for (D, hold), x in d.groupby(["D", "hold"]):
        t = x.groupby(["gap", "X", "per"]).R.mean().unstack(["per", "X"]).round(2)
        print(f"\nD {D}, exit after {hold} min - R/trade by fill gap (rows) x period / spread X (cols)")
        print(t.to_string())


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
