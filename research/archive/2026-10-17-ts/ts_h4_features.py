"""TS-h4 (H4 EMA tide, level <= 0.5 read ATR, 2 R, at most 12 h): which context separates the trades that went
the wrong way from the ones that worked? Per feature value: n, R/trade, the share of wrong-way losers (stopped and
never back to the entry within 12 h), and R in each of the four half-years. Read-only."""

import sys

import numpy as np
import pandas as pd

sys.argv = ["x", "data/backtests/ts/dataset_m15/triggers.csv"]
__file__ = "C:/Users/korap/taa/research/2026-10-17-ts/ts_study.py"
exec(compile(open(__file__, encoding="utf-8").read().split("def hour_bucket")[0], "head", "exec"))  # outcome()
__file__ = "C:/Users/korap/taa/research/2026-10-17-ts/ts_losers.py"
src = open(__file__, encoding="utf-8").read()
exec(compile(src.split("def from_study")[0].split("ROOT = ")[0] + "ROOT = Path(__file__).resolve().parents[2]\n"
             + src.split("ROOT = Path(__file__).resolve().parents[2]\n")[1].split("def from_study")[0], "losers", "exec"))

d = pd.read_csv("data/backtests/ts/outcomes_two_years_d1.csv", parse_dates=["time"])
loc = d[["H1_pivot_dist", "H4_pivot_dist"]].min(axis=1)
buy = d.side == "BUY"
f = pd.read_parquet("data/history/FBS-Demo/XAUUSD/H4.parquet").sort_values("close_time")
f["e"] = f.close.ewm(span=50, adjust=False).mean(); f["s"] = f.e - f.e.shift(5)
x = pd.merge_asof(d[["time"]], f[["close_time", "close", "e", "s"]], left_on="time", right_on="close_time")
tide = (((x.close > x.e) & (x.s > 0) & buy) | ((x.close < x.e) & (x.s < 0) & ~buy)).to_numpy()
r = d[tide & (loc <= 0.5)].copy()
r["R"] = [outcome(row, 0.25, 2.0, 0.5) for row in r.itertuples()]
spread = r.spread_points.fillna(25.0) * POINT
b = r.side == "BUY"
entry = np.where(b, r.close + spread, r.close)
stop = np.where(b, r["pivot"] - 0.25 * r.atr - spread, r["pivot"] + 0.25 * r.atr + spread)
tp = np.where(b, entry + 2 * np.abs(entry - stop), entry - 2 * np.abs(entry - stop))
r["cls"] = [path(t, s == "BUY", e, st, p).get("after", path(t, s == "BUY", e, st, p)["exit"])
            for t, s, e, st, p in zip(r.time, r.side, entry, stop, tp)]
r["wrong"] = r.cls == "wrong direction"
r["loc_bin"] = pd.cut(loc[r.index], [-1, 0.25, 0.5], labels=["<=0.25", "0.25-0.5"]).astype(str)
r["d1"] = r.d1_rel
print(f"TS-h4 study trades {len(r)}: R/trade {r.R.mean():+.3f}, wrong-way losers {r.wrong.mean():.0%}")
print("feature value: n | R/trade | wrong-way % | R per half (24H2 25H1 25H2 26H1)")
for col in ["side", "kind", "d1", "h4_map", "h4_swings", "h1_map", "h1_swings", "session", "stop_bin", "loc_bin", "h4_room"]:
    for v, g in r.groupby(col, observed=True):
        if len(g) < 25:
            continue
        h = [g.loc[g.q == q, "R"].mean() for q in ["24H2", "25H1", "25H2", "26H1"]]
        mark = "  all 4 < 0" if all(v_ < 0 for v_ in h) else ("  all 4 > 0" if all(v_ > 0 for v_ in h) else "")
        print(f"  {col:9} {str(v):14} {len(g):4d} | {g.R.mean():+.3f} | {g.wrong.mean():4.0%} | "
              + " ".join(f"{v_:+.2f}" for v_ in h) + mark)
r.to_csv("data/backtests/ts/ts_h4_study_trades.csv", index=False)
