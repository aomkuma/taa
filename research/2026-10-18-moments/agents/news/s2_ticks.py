"""Rule S2 on ticks: the CPI / NFP release-minute straddle (notes.md, FROZEN RULES). At the release second a buy
stop D above the last ask and a sell stop D below the last bid (OCO), live for the whole release minute; stop S
from the fill; exit at market HOLD seconds after the release (60 = the release minute's close). D, S scaled by
price / 4000. Fills on ticks at the first tick beyond the level, gaps included, +/- 0.07 slippage. The opposite
side at the same tick is simulated too (the coin's other half).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/s2_ticks.py [--test] [--hold 60]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
from lab import SLIP, events  # noqa: E402
from straddle import windows  # noqa: E402

TEST = "--test" in sys.argv
HOLD = float(sys.argv[sys.argv.index("--hold") + 1]) if "--hold" in sys.argv else 60.0
D0 = float(sys.argv[sys.argv.index("--d") + 1]) if "--d" in sys.argv else 1.0
S0 = 8.0
T0, T1 = pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-10-14 08:18", tz="UTC")


def sim(w: dict, flip: bool) -> dict | None:
    sec, bid, ask, k0 = w["sec"], w["bid"], w["ask"], w["ref"]
    k = bid[k0] / 4000
    D, S = D0 * k, S0 * k
    up, dn = ask[k0] + D, bid[k0] - D
    live = (sec >= 0) & (sec < 60)
    iu, idn = np.flatnonzero(live & (ask >= up)), np.flatnonzero(live & (bid <= dn))
    ju, jd = (iu[0] if len(iu) else 10**9), (idn[0] if len(idn) else 10**9)
    if ju == jd == 10**9:
        return None
    side, j = (1, ju) if ju < jd else (-1, jd)
    trig = side
    if flip:
        side = -side
    entry = ask[j] + SLIP if side > 0 else bid[j] - SLIP
    gap = (ask[j] - up) if trig > 0 else (dn - bid[j])
    after = np.arange(j + 1, len(sec))
    inn = after[sec[after] < HOLD]
    adv = (bid[inn] - entry) if side > 0 else (entry - ask[inn])
    hs = np.flatnonzero(adv <= -S)
    if len(hs):
        q = inn[hs[0]]
        px = bid[q] - SLIP if side > 0 else ask[q] + SLIP
        ex = "stop"
    else:
        q = inn[-1] if len(inn) else j
        px = bid[q] - SLIP if side > 0 else ask[q] + SLIP
        ex = "time"
    usd = (px - entry) * side
    fav = (bid[j:] - entry) if side > 0 else (entry - ask[j:])
    mfe = fav[sec[j:] < HOLD].max()
    kind = ""
    if ex == "stop":  # kinds against a target of 5 USD (the owner's minimum) within the 15 minutes of ticks
        kind = "3" if fav[sec[j:] > sec[q]].max() >= 5 else ("2" if mfe >= 2.5 else "1")
    return dict(t=w["t"], main=w["main"], side=side, fill_s=sec[j], gap=gap, exit=ex, usd=usd, R=usd / (S + SLIP),
                mfe=mfe, kind=kind, sl=S)


def main() -> None:
    ev = events(extra=True)
    ev = ev[ev.main.isin(["CPI", "NFP"])]
    ev = ev[(ev.t >= T0) & (ev.t < T1)] if TEST else ev[(ev.t >= pd.Timestamp("2025-10-01", tz="UTC")) & (ev.t < T0)]
    rows = []
    for w in windows(ev):
        for flip in (False, True):
            r = sim(w, flip)
            if r:
                rows.append(dict(who="opp" if flip else "rule", **r))
    d = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(d.round(2).to_string())
    d.to_parquet(f"research/2026-10-18-moments/agents/news/s2_ticks_{'test' if TEST else 'design'}_h{HOLD:g}_d{D0:g}.parquet")


if __name__ == "__main__":
    main()
