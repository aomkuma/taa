"""Q6d - the 13:00 Thai opening-range break (opens.py's setting, L 15, k 2, X 60) re-run on the real ticks, P1 / P2,
to check that the M1 simulation does not flatter it. Also the reclaim (Q7b) trades in the owner's windows.

Written before computing: the decisions (side, stop, the M1 bar that closed beyond) are recomputed from the M1 bars
exactly as in opens.py / reclaim.py; the fill is the first tick at / after the decision bar's close (a buy at the ask
+ 0.07, a sell at the bid - 0.07); the stop on the bid (buy) / ask (sell) at the first tick at / beyond it, gap
included; the target 2 R as a limit; out at the first tick at / after X minutes. R = pnl / the tick fill's risk.

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/orb_ticks.py > .../strategist/out_orb_ticks.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import slib
from news_follow import run_trade

MIN = 60 * 10**9
m = slib.m1("2025-10-15")
ti = m.index.asi8
c = m.close.to_numpy()
h, lo = m.high.to_numpy(), m.low.to_numpy()
O = pd.read_parquet(slib.HERE / "opens_trades.parquet")
O = O[(O.rule == "ORB15") & (O.open == "London")]


def tick_trade(t_dec_ns: int, side: int, stop: float, X: int, k_r: float = 2.0):
    day = pd.Timestamp(t_dec_ns, tz="UTC").normalize()
    x = slib.ticks(day)
    if x is None:
        return None
    t = x.t.dt.as_unit("ns").astype("int64").to_numpy()
    bid, ask = x.bid.to_numpy(float), x.ask.to_numpy(float)
    f = np.searchsorted(t, t_dec_ns, side="left")
    if f >= len(t) or t[f] - t_dec_ns > 5 * MIN:
        return None
    e = ask[f] + 0.07 if side > 0 else bid[f] - 0.07
    risk = (e - stop) * side
    if risk <= 0:
        return None
    r = run_trade(t, bid, ask, f, e, side, stop, e + side * k_r * risk, t[f] + X * MIN)
    if r is None:
        return None
    return dict(pnl=r[0], risk=risk, R=r[0] / risk, exit=r[1])


# ORB 13:00 Thai: recompute the decision bar and the range
rows = []
for day in pd.bdate_range("2025-10-20", "2026-04-17"):
    t0 = (day.tz_localize(None) + pd.Timedelta(hours=13)).tz_localize(slib.TH).tz_convert("UTC")
    i0 = np.searchsorted(ti, t0.value)
    if i0 >= len(ti) or ti[i0] - t0.value > 5 * MIN:
        continue
    i15 = np.searchsorted(ti, t0.value + 15 * MIN)
    rh, rl = h[i0:i15].max(), lo[i0:i15].min()
    rec = O[O.day.dt.tz_localize(None) == day.tz_localize(None)] if O.day.dt.tz is not None else O[O.day == day]
    if not len(rec):
        continue  # opens.py skipped it (range > 1.5 H or no break): keep the same days
    for k in range(i15, i15 + 60):
        side = 1 if c[k] > rh else (-1 if c[k] < rl else 0)
        if side:
            res = tick_trade(int(ti[k] + MIN), side, rl if side > 0 else rh, 60)
            if res:
                res.update(part=slib.part_of(pd.DatetimeIndex([t0]))[0], m1_R=float(rec.R.iloc[0]))
                rows.append(res)
            break
T = pd.DataFrame(rows)
print("ORB 13:00 Thai (L15 k2 X60) on the ticks:")
for p in ("P1", "P2"):
    x = T[T.part == p]
    print(f"  {p}: {slib.row(x)}  exits {x.exit.value_counts().to_dict()};  the same trades on M1: R {x.m1_R.mean():+.3f}")

R = pd.read_parquet(slib.HERE / "reclaim_trades.parquet")
R = R[R.win != "other"]
rows = []
for _, r in R.iterrows():
    stop = r.t  # placeholder to keep the shape clear
    # rebuild the stop from the M1 fill and the risk: stop = entry - side x risk, entry from the M1 open + costs
    i = np.searchsorted(ti, r.t.value)
    e_m1 = m.open.iloc[i] + (m.spread.iloc[i] * 0.01 + 0.08) + 0.07 if r.side > 0 else m.open.iloc[i] - 0.07
    stop = e_m1 - r.side * r.risk
    res = tick_trade(int(r.t.value), int(r.side), float(stop), 120)
    if res:
        res.update(part=r.part, m1_R=r.R)
        rows.append(res)
T = pd.DataFrame(rows)
print("\nreclaim in the owner's windows (Q7b) on the ticks:")
for p in ("P1", "P2"):
    x = T[T.part == p]
    print(f"  {p}: {slib.row(x)}  exits {x.exit.value_counts().to_dict()};  the same trades on M1: R {x.m1_R.mean():+.3f}")
