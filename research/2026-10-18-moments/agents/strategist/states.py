"""Row 45, step 2 - the readings for every event of the three leads, the checks, and the splits written before
computing (the top of PROPOSALS.md):
- the terciles of each reading, cut at the stream's O1 + P1 terciles: trades and R per part in each;
- one threshold per stream and reading chosen on O1 + P1 only (the 20th .. 80th percentiles, keep >= or <, eligible when
  it keeps >= 30 % of the O1 and of the P1 trades, score = min(kept R O1, kept R P1)), then read on O2 + P2 once;
- a lead = kept P1 > 0 and P2 > 0 and O1 >= 0 and O2 >= 0.
Checks first: MT5's D1 bars against the M1 server days (the availability), and a look-ahead run (40 events recomputed
from data cut at the entry).

    .venv/Scripts/python research/2026-10-18-moments/agents/strategist/states.py > .../strategist/out_states.txt
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import readings
import slib
import tsim

tsim.idle()
PARTS = ("O1", "O2", "P1", "P2")
READ = ["rng60", "season", "eff_d1", "adx_d1", "eff_h4", "adx_h4", "fail20", "sess10", "spr_atr", "since_big", "used",
        "own20"]
QS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)

E0 = pd.read_parquet(slib.HERE / "states_events.parquet")
B = pd.read_parquet(slib.HERE / "states_breaks.parquet")
E0 = E0[E0.R.notna()].copy()
E0["t_exit"] = E0.t_exit.fillna(-1).astype(np.int64)
rc = E0[E0.stream == "RC"]
E = pd.concat([E0[E0.stream != "RC"], rc.assign(stream="RC_all"), rc[rc.win != "other"].assign(stream="RC_win")],
              ignore_index=True)
m = slib.m1("2023-09-01")
assert m.index.max() < slib.EXAM_START

# ---- check 1: MT5 D1 bars against the M1 server days
D1 = readings.load_mt5("D1")
sday = m.index.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
g = pd.DataFrame({"h": m.high.to_numpy(), "l": m.low.to_numpy(), "last": m.index.asi8}, index=sday).groupby(level=0).agg(
    h=("h", "max"), l=("l", "min"), last=("last", "max"))
D1["sday"] = pd.to_datetime(D1.t_open, utc=True).dt.tz_convert("Europe/Athens").dt.tz_localize(None).dt.floor("1D")
j = D1.merge(g, left_on="sday", right_index=True)
j = j[j.sday >= pd.Timestamp("2023-09-04")]
print(f"check 1: {len(j)} D1 bars; |high - M1 high| max {np.abs(j.high - j.h).max():.2f}, |low - M1 low| max "
      f"{np.abs(j.low - j.l).max():.2f}; bars whose last M1 minute ends after the availability: "
      f"{int((j['last'] + 60 * 10**9 > j.avail).sum())}")

# ---- the readings
X = readings.compute(E, m, B)
E = pd.concat([E, X], axis=1)
E.to_parquet(slib.HERE / "states_readings.parquet")

# ---- check 2: look-ahead - 40 events recomputed from data cut at the entry
rng = np.random.default_rng(45)
bad = 0
for i in rng.choice(E.index.to_numpy(), 40, replace=False):
    t = int(E.at[i, "t_in"])
    st = E.at[i, "stream"]
    sub = E[(E.stream == st) & (E.t_exit <= t) & (E.t_exit > 0)].drop(columns=READ)
    one = pd.concat([sub, E.loc[[i]].drop(columns=READ)])
    x = readings.compute(one, m[m.index.asi8 < t], B[B.t_settle <= t]).loc[i]
    for k in READ:
        a, b = x[k], E.at[i, k]
        if not ((np.isnan(a) and np.isnan(b)) or abs(a - b) < 1e-9):
            bad += 1
            print(f"  look-ahead difference: {st} {pd.Timestamp(t, tz='UTC')} {k}: cut {a} full {b}")
print(f"check 2: 40 events x {len(READ)} readings recomputed from data cut at the entry: {bad} differ")


def stat(x: pd.DataFrame) -> str:
    return " | ".join(f"{p} {len(x[x.part == p]):3d} {x[x.part == p].R.mean():+.3f}" if len(x[x.part == p]) else
                      f"{p}   0    -   " for p in PARTS)


print("\n=== the streams, spread only (P1 / P2 ticks, O1 / O2 M1); per part: trades R")
for st in ("ORB", "RC_win", "RC_all", "RT_opp"):
    print(f"{st:7s} {stat(E[E.stream == st])}")

print("\n=== terciles (cut at the stream's O1 + P1 terciles); per part: trades R")
for st in ("ORB", "RC_win", "RC_all", "RT_opp"):
    S = E[E.stream == st]
    for k in READ:
        fit = S[S.part.isin(["O1", "P1"])][k].dropna()
        a, b = fit.quantile(1 / 3), fit.quantile(2 / 3)
        print(f"{st} {k} (cuts {a:.3g} / {b:.3g}; missing {int(S[k].isna().sum())})")
        for name, sel in (("low ", S[k] < a), ("mid ", (S[k] >= a) & (S[k] < b)), ("high", S[k] >= b)):
            print(f"   {name} {stat(S[sel])}")

print("\n=== one threshold per stream and reading, chosen on O1 + P1, read once on O2 + P2")
rows = []
for st in ("ORB", "RC_win", "RC_all", "RT_opp"):
    S = E[E.stream == st]
    n_o1, n_p1 = (S.part == "O1").sum(), (S.part == "P1").sum()
    for k in READ:
        fit = S[S.part.isin(["O1", "P1"])][k].dropna()
        best = None
        for q in QS:
            cut = float(fit.quantile(q))
            for d in (">=", "<"):
                keep = (S[k] >= cut) if d == ">=" else (S[k] < cut)
                o1, p1 = S[keep & (S.part == "O1")], S[keep & (S.part == "P1")]
                if len(o1) < 0.3 * n_o1 or len(p1) < 0.3 * n_p1:
                    continue
                sc = min(o1.R.mean(), p1.R.mean())
                if best is None or sc > best[0]:
                    best = (sc, q, cut, d, keep)
        if best is None:
            print(f"{st:7s} {k:9s} no eligible cut")
            continue
        sc, q, cut, d, keep = best
        kept, drop = S[keep], S[~keep]
        r = {p: kept[kept.part == p].R.mean() for p in PARTS}
        lead = r["P1"] > 0 and r["P2"] > 0 and r["O1"] >= 0 and r["O2"] >= 0
        rows.append(dict(stream=st, reading=k, q=q, cut=cut, dir=d, lead=lead, **{f"R_{p}": r[p] for p in PARTS},
                         **{f"n_{p}": int((kept.part == p).sum()) for p in PARTS}))
        print(f"{st:7s} {k:9s} keep {d} {cut:.4g} (q{int(q * 100)})  kept: {stat(kept)}" + ("   LEAD" if lead else ""))
        print(f"{'':17s} {'':22s}dropped: {stat(drop)}")
pd.DataFrame(rows).to_csv(slib.HERE / "out_states_choice.csv", index=False)
