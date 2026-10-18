"""The evidence by the larger timeframes (design snaps, descriptive): the H4 / H1 structure and where the snap sits
against M15 / M30 / H1 / H4 support and resistance -> what M1 did in the next 30-60 minutes; each row also by year
(up share minus down share) to show whether a lean holds.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/bigtf.py
"""

from __future__ import annotations

import pandas as pd

from plib import HERE

pd.set_option("display.width", 250)
STRUCT = {0: "none", 1: "up", 2: "down", 3: "contracting", 4: "broadening"}  # the library's codes
LOC = {0: "between", 1: "at support", 2: "at resistance", 3: "broke up", 4: "broke down"}


def table(S: pd.DataFrame, by: list[str], title: str, min_days: int = 20) -> None:
    S = S.copy()
    S["up"] = S.cls.isin(["ran_up", "slow_up"])
    S["dn"] = S.cls.isin(["ran_dn", "slow_dn"])
    S["ran"] = S.cls.isin(["ran_up", "ran_dn"])
    S["fake"] = S.cls.isin(["fake_up", "fake_dn"])
    S["flat"] = S.cls == "flat"
    S["year"] = S.S.dt.year
    g = S.groupby(by)
    t = pd.DataFrame({"snaps": g.size(), "days": g.day.nunique(), "ran10": g.ran.mean(), "up": g.up.mean(),
                      "down": g.dn.mean(), "fake": g.fake.mean(), "flat": g.flat.mean(),
                      "max_up30": g.mfe_up30.median(), "max_dn30": g.mfe_dn30.median()})
    yr = (S.groupby(by + ["year"]).up.mean() - S.groupby(by + ["year"]).dn.mean()).unstack("year")
    t["up-down by year 23/24/25/26"] = [" ".join(f"{v:+.2f}" for v in yr.loc[i]) for i in t.index]
    t = t[t.days >= min_days]
    print(f"\n-- {title} --")
    print(t.round(2).to_string())


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    S = S[S.half != "W"].copy()
    S["day"] = S.S.dt.tz_convert("Asia/Bangkok").dt.normalize()
    for tf in ("H4", "H1", "M30", "M15"):
        S[f"{tf}_s"] = S[f"{tf}_struct"].map(STRUCT)
        S[f"{tf}_loc"] = S[f"{tf}_sr_loc"].map(LOC)
        S[f"{tf}_imp"] = S[f"{tf}_sr_imp"].map({0: "-", 1: "1 touch", 2: "2 touches", 3: "3+ touches"})
    print("all design snaps:", len(S), "days", S.day.nunique())
    table(S, ["H4_s", "H1_s"], "H4 structure x H1 structure")
    table(S, ["H1_s", "M15_s"], "H1 structure x M15 structure")
    for tf in ("H4", "H1", "M30", "M15"):
        table(S, [f"{tf}_loc", f"{tf}_imp"], f"where against {tf} support / resistance x the level's importance")
    table(S, ["H1_s", "H1_loc"], "H1 trend x where against H1 support / resistance")
    table(S, ["H4_s", "H1_loc"], "H4 trend x where against H1 support / resistance")


if __name__ == "__main__":
    main()
