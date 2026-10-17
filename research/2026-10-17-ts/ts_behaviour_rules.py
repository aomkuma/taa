"""The behaviour rules for TS, fixed before year C (2023-10 .. 2024-09) judges them (2026-10-17). Reads one or more
behaviour.csv files (ts_behaviour.py) and prints each rule's n, trades per weekday, win %, R/trade, wrong-way
share and R per half-year. The H4 EMA tide is recomputed from the H4 history."""

import os
import sys

import numpy as np
import pandas as pd

d = pd.concat([pd.read_csv(f, parse_dates=["time"]) for f in sys.argv[1:]], ignore_index=True)
buy = d.side == "BUY"
f = pd.read_parquet((os.environ.get("TS_HISTORY", "data/history") + "/FBS-Demo/XAUUSD/H4.parquet")).sort_values("close_time")
f["e"] = f.close.ewm(span=50, adjust=False).mean()
f["s"] = f.e - f.e.shift(5)
x = pd.merge_asof(d[["time"]].sort_values("time"), f[["close_time", "close", "e", "s"]], left_on="time",
                  right_on="close_time").set_index(d.sort_values("time").index).sort_index()
d["h4_tide"] = ((x.close > x.e) & (x.s > 0) & buy) | ((x.close < x.e) & (x.s < 0) & ~buy)
beyond = d.pdx_room <= 0
expand = d.atr_ratio >= 1.25
with_day = d.day_pos > 0.5
evening = d.ny_hour.between(17, 20)
ny = d.ny_hour
RULES_A = {  # fixed 2026-10-17 before years D (2022-10..2023-09) and E (2021-10..2022-09): 5-of-6 half-year habits
    "A0 all triggers": pd.Series(True, index=d.index),
    "A1 with the day (upper half of the day's range for a buy)": with_day,
    "A2 beyond the previous day's extreme": beyond,
    "A3 A1 & A2": with_day & beyond,
    "A4 A1, not 17-20 New York": with_day & ~evening,
    "A5 21-23 New York (08-11 Thai)": ny.between(21, 23),
}
RULES = {
    "all triggers": pd.Series(True, index=d.index),
    "B1 beyond the previous day's extreme": beyond,
    "B2 B1 & ATR expanding (>= 1.25x)": beyond & expand,
    "B3 B1 & H4 EMA tide": beyond & d.h4_tide,
    "B4 with the day (upper half for a buy) & ATR expanding": with_day & expand,
    "B5 B1, not 17-20 New York": beyond & ~evening,
}
if os.environ.get("TS_RULES") == "A":
    RULES = RULES_A
halves = [h for h in ["23H2", "24H1", "24H2", "25H1", "25H2", "26H1"] if (d.half == h).any()] or ["year"]
if halves == ["year"]:
    d["half"] = "year"
days = len(pd.bdate_range(d.time.min().date(), d.time.max().date()))
print(f"{len(d)} triggers, {days} weekdays; plan: stop 0.25 ATR beyond the pullback extreme, 2 R, at most 12 h")
print("rule | n | per day | win % | R/trade | wrong-way % | R per half " + " ".join(halves))
for name, m in RULES.items():
    g = d[m]
    hs = [g.loc[g.half == h, "R"].mean() for h in halves]
    print(f"{name:52} {len(g):5d} {len(g) / days:5.2f} {100 * (g.R > 0).mean():4.0f} {g.R.mean():+.3f} "
          f"{100 * g.wrong.mean():4.0f} | " + " ".join(f"{v:+.2f}" for v in hs)
          + ("  all > 0" if all(v > 0 for v in hs) else ""))
