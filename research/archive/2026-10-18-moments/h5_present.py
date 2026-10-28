"""H5 (docs/OWN_SETUP_ROUNDS.md): the playbook that paid at a moment group over the previous 20 trading days is traded
the next day. Walk-forward over 2026-04-14 .. 10-14, each day predicted from earlier days only.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/h5_present.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
from moments import END, OUT, START  # noqa: E402
from select_fit import group, one_at_a_time  # noqa: E402

LOOK, WEIGHT, CLEAR = 20, 20.0, 0.05
MONTHS = [START + pd.DateOffset(months=k) for k in range(7)]


def summary(name: str, g: pd.DataFrame, days: int) -> str:
    if len(g) == 0:
        return f"  {name:34} 0 trades"
    months = g.groupby(pd.cut(g.t, MONTHS, right=False), observed=True).usd_S70.sum()
    return (
        f"  {name:34} {len(g):4} trades  {g.r_S70.mean():+.3f} R (se {g.r_S70.std() / np.sqrt(len(g)):.3f})"
        f"  win {100 * (g.r_S70 > 0).mean():3.0f}%  {g.usd_S70.sum():+7.1f} USD  {len(g) / days:.2f}/day"
        f"  months+ {(months > 0).sum()}/{len(months)}"
    )


def main() -> None:
    t = pd.read_parquet(f"{OUT}_exits.parquet")
    t = t[(t.kind == "moment") & t.r_S70.notna() & (t.t < END)].copy()
    t["grp"] = t.tags.map(group)
    t["cell"] = t.grp + "|" + t.pb
    t["exit_t"] = t.te + pd.to_timedelta(t.min_S70, unit="min")
    t["day"] = t.t.dt.normalize()
    days = sorted(t.day.unique())
    rows = []
    for k in range(LOOK, len(days)):
        d = days[k]
        past = t[(t.day >= days[k - LOOK]) & (t.exit_t < d)]
        est = past.groupby("cell").r_S70.agg(["count", "mean"])
        est["shrunk"] = est["count"] * est["mean"] / (est["count"] + WEIGHT)
        today = t[t.day == d].merge(est["shrunk"], left_on="cell", right_index=True, how="left")
        rows.append(today)
    w = pd.concat(rows)
    w["shrunk"] = w["shrunk"].fillna(0.0)
    n_days = len(days) - LOOK
    chosen = w[w.shrunk > CLEAR].sort_values("shrunk", ascending=False).drop_duplicates("rid")
    skipped = w[~w.index.isin(chosen.index)]
    print(f"Walk-forward {pd.Timestamp(days[LOOK]):%Y-%m-%d} .. {pd.Timestamp(days[-1]):%Y-%m-%d} ({n_days} days)")
    print(summary("H5: the present picks the playbook", one_at_a_time(chosen, "min_S70"), n_days))
    print(summary("every moment entry (all playbooks)", one_at_a_time(w, "min_S70"), n_days))
    print(summary("the cells H5 skips", one_at_a_time(skipped, "min_S70"), n_days))
    for pb in ("P1", "P2", "P3"):
        print(summary(f"every {pb} entry", one_at_a_time(w[w.pb == pb], "min_S70"), n_days))
    h5 = one_at_a_time(chosen, "min_S70")
    print("\nH5 month by month:")
    for mo, g in h5.groupby(pd.cut(h5.t, MONTHS, right=False), observed=True):
        print(f"  {mo.left:%m-%d}  {len(g):3} trades  {g.r_S70.mean():+.3f} R  {g.usd_S70.sum():+7.1f} USD  cells {g.cell.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
