"""OWN v2 (docs/OWN_SETUP.md, written 2026-10-17): P1 break-and-hold at the Asia and New York moments, taken only
when the entry lies 0.1-0.3 U beyond the moment's open the trade's way; stop 0.38 U, the exits of exits.py, one
position at a time. Month by month for one window of ``moments.py``.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/judge_v2.py PREFIX START END
    (the latest six months: data/research/own_moments 2026-04-14 2026-10-14;
     the untouched earlier six: data/research/own_moments_prev 2025-10-14 2026-04-14)
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
from exits import TARGET_U, TARGET_USD, Path  # noqa: E402
from select_fit import group, one_at_a_time  # noqa: E402

STOP_U, BAND = 0.38, (0.1, 0.3)


def main() -> None:
    prefix, start, end = sys.argv[1], pd.Timestamp(sys.argv[2], tz="UTC"), pd.Timestamp(sys.argv[3], tz="UTC")
    P = Path(start)
    f = pd.read_parquet(f"{prefix}_features.parquet")
    t = pd.read_parquet(f"{prefix}_trades.parquet").merge(
        f[["rid", "tags", "kind", "u", "clear"]], on="rid"
    )
    t = t[(t.kind == "moment") & (t.pb == "P1") & (t.t >= start) & (t.t < end)].copy()
    t["session"] = t.tags.map(group)
    t = t[t.session.isin(["asia", "ny"])]
    t["e"] = P.ot.searchsorted(t.te)
    s0 = P.ot.searchsorted(t.t)
    fills = np.array([P.entry(e, s) for e, s in zip(t.e, t.side, strict=True)])
    t["chase_u"] = (fills - P.o[s0]) * t.side.to_numpy() / t.u.to_numpy()
    print(f"P1 entries at the Asia and New York moments: {len(t)}; in the band: "
          f"{((t.chase_u >= BAND[0]) & (t.chase_u <= BAND[1])).sum()}")
    v2 = t[(t.chase_u >= BAND[0]) & (t.chase_u <= BAND[1])].copy()
    res = []
    for row in v2.itertuples():
        entry = P.entry(row.e, row.side)
        tp = max(TARGET_USD, TARGET_U * row.u)
        res.append(P.run(row.e, row.side, entry - row.side * STOP_U * row.u, tp, row.clear == row.side, row.u))
    v2["r"], v2["usd"], v2["mins"] = [x[0] for x in res], [x[1] for x in res], [x[2] for x in res]
    v2 = one_at_a_time(v2.dropna(subset=["r"]), "mins")
    days = int(pd.bdate_range(start, end - pd.Timedelta(days=1)).size)
    months = [start + pd.DateOffset(months=k) for k in range(7)]
    v2["month"] = pd.cut(v2.t, months, labels=[f"{m:%Y-%m-%d}" for m in months[:-1]], right=False)
    print("  month        trades  R/trade  win%  USD (0.01 lot)  Asia / NY trades")
    for mo, g in v2.groupby("month", observed=True):
        print(f"  {mo}  {len(g):6}  {g.r.mean():+.3f}  {100 * (g.r > 0).mean():4.0f}  {g.usd.sum():+10.1f}"
              f"      {(g.session == 'asia').sum()} / {(g.session == 'ny').sum()}")
    by_m = v2.groupby("month", observed=True).usd.sum()
    print(f"  all: {len(v2)} trades, {v2.r.mean():+.3f} R (se {v2.r.std() / np.sqrt(len(v2)):.3f}), win"
          f" {100 * (v2.r > 0).mean():.0f}%, {v2.usd.sum():+.1f} USD at 0.01 lot, {len(v2) / days:.2f} trades/day,"
          f" months positive {(by_m > 0).sum()}/{len(by_m)}")
    for s, g in v2.groupby("session"):
        print(f"     {s}: {len(g)} trades {g.r.mean():+.3f} R, {g.usd.sum():+.1f} USD")
    los = v2[v2.r < -0.5]
    print(f"  losers {len(los)}: minutes to the stop median {los.mins.median():.0f}; stop USD median"
          f" {(STOP_U * v2.u).median():.2f}, target USD median {np.maximum(TARGET_USD, TARGET_U * v2.u).median():.2f}")
    v2.to_parquet(f"{prefix}_v2.parquet")


if __name__ == "__main__":
    main()
