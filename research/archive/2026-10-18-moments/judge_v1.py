"""OWN v1 (docs/OWN_SETUP_ROUNDS.md, frozen 2026-10-17): R-a (P2 at the New York cash open) and R-b (P1 through the
previous New York session's high/low at any half hour), q70 stop, one position at a time. Prints the fit months
and, once, the judged months (2026-07-14 .. 10-14), month by month.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/judge_v1.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
from moments import END, FIT_END, OUT, START  # noqa: E402
from select_fit import one_at_a_time  # noqa: E402

MONTHS = [START + pd.DateOffset(months=k) for k in range(7)]


def main() -> None:
    t = pd.read_parquet(f"{OUT}_exits.parquet")
    f = pd.read_parquet(f"{OUT}_features.parquet")
    t = t.merge(f[["rid", "pool_up", "pool_dn"]], on="rid")
    broken = np.where(t.side > 0, t.pool_up, t.pool_dn)
    ra = (t.pb == "P2") & t.tags.str.split(",").map(lambda x: "ny_cash" in x)
    rb = (t.pb == "P1") & pd.Series(broken, index=t.index).isin(["ny_h", "ny_l"])
    v1 = t[ra | rb].assign(rule=np.where(ra[ra | rb], "R-a", "R-b"))
    v1 = one_at_a_time(v1, "min_S70")
    v1 = v1[v1.r_S70.notna() & (v1.t < END)]
    v1["month"] = pd.cut(v1.t, MONTHS, labels=[f"{m:%m-%d}" for m in MONTHS[:-1]], right=False)
    v1["part"] = np.where(v1.t < FIT_END, "fit", "judged")
    days = {"fit": 65, "judged": int(pd.bdate_range(FIT_END, END - pd.Timedelta(days=1)).size)}
    print("OWN v1, R per trade (q70 stop), USD at 0.01 lot")
    print("  month   rule   trades  R/trade  win%  USD/trade  USD total  hold share  minutes (median)")
    for (mo, rule), g in v1.groupby(["month", "rule"], observed=True):
        print(
            f"  {mo}  {rule}  {len(g):6}  {g.r_S70.mean():+.3f}  {100 * (g.r_S70 > 0).mean():4.0f}"
            f"  {g.usd_S70.mean():+8.2f}  {g.usd_S70.sum():+9.1f}  {g.hold.mean():10.2f}  {g.min_S70.median():6.0f}"
        )
    for part, g in v1.groupby("part"):
        months = g.groupby("month", observed=True).usd_S70.sum()
        print(
            f"\n  {part}: {len(g)} trades, {g.r_S70.mean():+.3f} R/trade (se {g.r_S70.std() / np.sqrt(len(g)):.3f}),"
            f" win {100 * (g.r_S70 > 0).mean():.0f}%, {g.usd_S70.sum():+.1f} USD at 0.01 lot,"
            f" {len(g) / days[part]:.2f} trades/day, months positive {(months > 0).sum()}/{len(months)}"
        )
        for rule, x in g.groupby("rule"):
            print(f"     {rule}: {len(x)} trades {x.r_S70.mean():+.3f} R, {x.usd_S70.sum():+.1f} USD")
    v1.to_parquet(f"{OUT}_v1.parquet")


if __name__ == "__main__":
    main()
