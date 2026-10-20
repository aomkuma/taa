"""Row 45 - counts the tercile cells of out_states.txt (states_readings.parquet): older-year cells > 0, and terciles
> 0 in all four parts."""

import pandas as pd

import slib

E = pd.read_parquet(slib.HERE / "states_readings.parquet")
READ = ["rng60", "season", "eff_d1", "adx_d1", "eff_h4", "adx_h4", "fail20", "sess10", "spr_atr", "since_big", "used",
        "own20"]
old_pos = old_all = 0
both = []
for st in ("ORB", "RC_win", "RC_all", "RT_opp"):
    S = E[E.stream == st]
    for k in READ:
        fit = S[S.part.isin(["O1", "P1"])][k].dropna()
        a, b = fit.quantile(1 / 3), fit.quantile(2 / 3)
        for name, sel in (("low", S[k] < a), ("mid", (S[k] >= a) & (S[k] < b)), ("high", S[k] >= b)):
            r = {p: S[sel & (S.part == p)].R for p in ("O1", "O2", "P1", "P2")}
            for p in ("O1", "O2"):
                if len(r[p]):
                    old_all += 1
                    old_pos += r[p].mean() > 0
            if all(len(r[p]) and r[p].mean() > 0 for p in r):
                both.append((st, k, name))
            elif len(r["O1"]) and len(r["O2"]) and r["O1"].mean() > 0 and r["O2"].mean() > 0:
                both.append((st, k, name, "older only"))
print(f"older-year tercile cells > 0: {old_pos} of {old_all}")
print("terciles > 0 in O1 and O2:", both)
