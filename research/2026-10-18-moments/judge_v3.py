"""OWN v3 (docs/OWN_SETUP_ROUNDS.md, written 2026-10-17): at the London open, enter against the H1/M15 swing-structure
flow at the moment bar's open; stop 0.38 U, target max(5 USD, 0.5 U), 60 minutes. Month by month for one window.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/judge_v3.py PREFIX START END
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
from exits import TARGET_U, TARGET_USD, Path  # noqa: E402

STOP_U = 0.38


def main() -> None:
    prefix, start, end = sys.argv[1], pd.Timestamp(sys.argv[2], tz="UTC"), pd.Timestamp(sys.argv[3], tz="UTC")
    P = Path(start)
    f = pd.read_parquet(f"{prefix}_features.parquet")
    f = f[(f.kind == "moment") & f.tags.str.split(",").map(lambda x: "london" in x) & (f.flow != 0)]
    f = f[(f.t >= start) & (f.t < end)].copy()
    f["e"] = P.ot.searchsorted(f.t)
    assert (P.ot[f.e] == f.t).mean() > 0.95
    res = []
    for e, flow, u in zip(f.e, f.flow, f.u, strict=True):
        side = -int(flow)
        entry = P.entry(e, side)
        res.append(P.run(e, side, entry - side * STOP_U * u, max(TARGET_USD, TARGET_U * u), False, u))
    f["r"], f["usd"] = [x[0] for x in res], [x[1] for x in res]
    f = f.dropna(subset=["r"])
    months = [start + pd.DateOffset(months=k) for k in range(7)]
    f["month"] = pd.cut(f.t, months, labels=[f"{m:%Y-%m-%d}" for m in months[:-1]], right=False)
    print("  month        trades  R/trade  win%  USD (0.01 lot)")
    for mo, g in f.groupby("month", observed=True):
        print(f"  {mo}  {len(g):6}  {g.r.mean():+.3f}  {100 * (g.r > 0).mean():4.0f}  {g.usd.sum():+10.1f}")
    by_m = f.groupby("month", observed=True).usd.sum()
    days = int(pd.bdate_range(start, end - pd.Timedelta(days=1)).size)
    print(f"  all: {len(f)} trades, {f.r.mean():+.3f} R (se {f.r.std() / np.sqrt(len(f)):.3f}), win {100 * (f.r > 0).mean():.0f}%,"
          f" {f.usd.sum():+.1f} USD at 0.01 lot, {len(f) / days:.2f} trades/day, months positive {(by_m > 0).sum()}/{len(by_m)}")
    for side, g in f.groupby(np.where(f.flow > 0, "SELL (flow up)", "BUY (flow down)")):
        print(f"     {side}: {len(g)} trades {g.r.mean():+.3f} R, {g.usd.sum():+.1f} USD")


if __name__ == "__main__":
    main()
