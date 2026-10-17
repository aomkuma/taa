"""Setup OWN on the fit months only (2026-04-14 .. 07-14): hypotheses H1-H4 and the playbook selector, each fit
month predicted from the other two (docs/OWN_SETUP.md "The selector"). The judged months are not read.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/select_fit.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
from moments import FIT_END, OUT, START  # noqa: E402

STOPS = ("S0", "S70", "S80", "S90")
WEIGHT, CLEAR = 20.0, 0.05
MONTHS = [START + pd.DateOffset(months=k) for k in range(4)]  # 04-14, 05-14, 06-14, 07-14


def group(tags: str) -> str:
    t = set(tags.split(","))
    if t & {"tokyo", "asia"}:
        return "asia"
    if "london" in t:
        return "london"
    if t == {"control"}:
        return "control"
    return "ny"


def one_at_a_time(d: pd.DataFrame, col: str) -> pd.DataFrame:
    d = d.sort_values("te")
    keep, free = [], pd.Timestamp(0, tz="UTC")
    for te, mins in zip(d["te"], d[col], strict=True):
        ok = te >= free
        keep.append(ok)
        if ok:
            free = te + pd.Timedelta(minutes=int(mins))
    return d[np.array(keep, dtype=bool)]


def line(name: str, r: pd.Series, usd: pd.Series | None = None) -> str:
    if len(r) == 0:
        return f"  {name:58}    0"
    se = r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
    extra = f"  {usd.mean():+6.2f} USD" if usd is not None else ""
    return f"  {name:58} {len(r):4}  {r.mean():+.3f} (se {se:.3f})  win {100 * (r > 0).mean():3.0f}%{extra}"


def main() -> None:
    t = pd.read_parquet(f"{OUT}_exits.parquet")
    f = pd.read_parquet(f"{OUT}_features.parquet")
    t = t[t.t < FIT_END].copy()
    f = f[f.t < FIT_END].copy()
    t["grp"] = t.tags.map(group)
    t = t.merge(f[["rid", "adr_spreads"]], on="rid")
    t["cell"] = t.grp + "|" + np.where(t["squeeze"], "sq", "nosq") + "|" + t.pool_side
    t["month"] = pd.cut(t.t, MONTHS, labels=False, right=False)
    best = {pb: max(STOPS, key=lambda s: t.loc[(t.pb == pb) & (t.kind == "moment"), f"r_{s}"].mean()) for pb in ("P1", "P2", "P3")}
    print("Fit-best stop per playbook (moments):", best)
    t["r"] = [row[f"r_{best[row.pb]}"] for _, row in t.iterrows()]
    t["usd"] = [row[f"usd_{best[row.pb]}"] for _, row in t.iterrows()]
    t["mins"] = [row[f"min_{best[row.pb]}"] for _, row in t.iterrows()]

    print("\nHypotheses (fit months; R per trade at the fit-best stop; moments | controls):")
    for kind in ("moment", "control"):
        k = t[t.kind == kind]
        sq, nosq = k[k["squeeze"]], k[~k["squeeze"]]
        print(f" {kind}s")
        print(line("H1 squeeze, pool ahead: P1 with the flow", sq[(sq.pool_side == "ahead") & (sq.pb == "P1") & (sq.with_flow > 0)].r))
        print(line("   no squeeze, pool ahead: P1 with the flow", nosq[(nosq.pool_side == "ahead") & (nosq.pb == "P1") & (nosq.with_flow > 0)].r))
        print(line("H2 squeeze, pool behind: P2 with the flow", sq[(sq.pool_side == "behind") & (sq.pb == "P2") & (sq.with_flow > 0)].r))
        print(line("   no squeeze, pool behind: P2 with the flow", nosq[(nosq.pool_side == "behind") & (nosq.pb == "P2") & (nosq.with_flow > 0)].r))
        for pb in ("P1", "P2", "P3"):
            print(line(f"H3 no squeeze, no pool near: {pb}", nosq[(nosq.pool_side == "none") & (nosq.pb == pb)].r))
        lo_, hi_ = k.adr_spreads.quantile([1 / 3, 2 / 3])
        for pb in ("P1", "P2", "P3"):
            g = k[k.pb == pb]
            cells = [g[g.adr_spreads < lo_].r, g[(g.adr_spreads >= lo_) & (g.adr_spreads < hi_)].r, g[g.adr_spreads >= hi_].r]
            print(f"  H4 {pb} by range/spread tertile: " + "  ".join(f"{x.mean():+.3f} ({len(x)})" for x in cells))

    print("\nPer playbook by cell (moments, fit months, n >= 8):")
    m = t[t.kind == "moment"]
    g = m.groupby(["cell", "pb"]).r.agg(["count", "mean"]).unstack("pb")
    g = g[(g["count"] >= 8).any(axis=1)].round(3)
    print(g.to_string())

    print("\nSelector, leave one fit month out (moments; trade the best playbook whose shrunk mean - 1 se > +0.05):")
    picked = []
    for mo in range(3):
        train, test = m[m.month != mo], m[m.month == mo]
        prior = train.groupby("pb").r.agg(["mean", "std"])
        choice = {}
        for (cell, pb), x in train.groupby(["cell", "pb"]):
            n = len(x)
            shrunk = (n * x.r.mean() + WEIGHT * prior.loc[pb, "mean"]) / (n + WEIGHT)
            se = prior.loc[pb, "std"] / np.sqrt(n + WEIGHT)
            if shrunk - se > CLEAR and shrunk > choice.get(cell, (None, -np.inf))[1]:
                choice[cell] = (pb, shrunk)
        sel = test[[choice.get(c, (None,))[0] == pb for c, pb in zip(test.cell, test.pb, strict=True)]]
        sel = one_at_a_time(sel, "mins")
        picked.append(sel)
        print(f"  month {mo + 1}: cells traded {len(choice)} {sorted(choice.items())}")
        print(line(f"  month {mo + 1} predicted", sel.r, sel.usd))
    allp = pd.concat(picked)
    days = m.t.dt.normalize().nunique()
    print(line("all three predicted months", allp.r, allp.usd), f" trades/day {len(allp) / days:.2f}")

    print("\nWithout context: every moment entry of one playbook, one at a time (fit months):")
    for pb in ("P1", "P2", "P3"):
        x = one_at_a_time(m[m.pb == pb], "mins")
        print(line(f"{pb} ({best[pb]})", x.r, x.usd), f" trades/day {len(x) / days:.2f}")


if __name__ == "__main__":
    main()
