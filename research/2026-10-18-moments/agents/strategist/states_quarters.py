"""Row 45, step 3 (descriptive, written after step 2's result): the three leads quarter by quarter, with the median of
the readings in each quarter - do the older years hold quarters where the leads paid, and what was there then?
Reads states_readings.parquet only (nothing new is loaded).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/states_quarters.py > .../out_states_quarters.txt
"""

import pandas as pd

import slib

E = pd.read_parquet(slib.HERE / "states_readings.parquet")
E["q"] = pd.to_datetime(E.t_in, utc=True).dt.tz_localize(None).dt.to_period("Q")
pd.set_option("display.width", 200)
for st in ("ORB", "RC_win", "RC_all", "RT_opp"):
    g = E[E.stream == st].groupby("q")
    T = pd.DataFrame({"n": g.size(), "R": g.R.mean().round(3), "win": g.R.apply(lambda x: (x > 0).mean()).round(2),
                      "season": g.season.median().round(2), "rng60": g.rng60.median().round(2),
                      "eff_d1": g.eff_d1.median().round(2), "fail20": g.fail20.median().round(2),
                      "H1_ATR": g.H.median().round(1)})
    print(f"=== {st}\n{T.to_string()}\n")
# the same quarters: the share of positive quarters and the correlation of quarter R with each median reading
print("correlation across quarters (quarters with >= 10 trades) of the quarter's R with its median reading:")
for st in ("ORB", "RC_all", "RT_opp"):
    g = E[E.stream == st].groupby("q")
    T = pd.DataFrame({"n": g.size(), "R": g.R.mean(), **{k: g[k].median() for k in
                      ("season", "rng60", "eff_d1", "adx_d1", "eff_h4", "fail20", "sess10", "used", "H")}})
    T = T[T.n >= 10]
    print(f"  {st:7s} quarters {len(T)}, positive {int((T.R > 0).sum())}: " +
          ", ".join(f"{k} {T.R.corr(T[k]):+.2f}" for k in T.columns[2:]))
