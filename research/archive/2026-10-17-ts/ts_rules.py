"""A few reasoned TS rules on outcomes.csv (ts_study.py): n, R/trade overall and per half, per plan. Few rules on
purpose (not a search): each one is a hypothesis from the owner's idea or from the one-feature table."""

import sys

import pandas as pd

d = pd.read_csv(sys.argv[1], parse_dates=["time"])
split = pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else "2026-04-01", tz="UTC")
months = max(1.0, (d.time.max() - d.time.min()).days / 30.4)
loc = d[["H1_pivot_dist", "H4_pivot_dist"]].min(axis=1)
not_against = d.h4_map != "AGAINST"
room = d.h4_room.isin([">3R", "2-3R"])
RULES = {
    "all": pd.Series(True, index=d.index),
    "L25 (extreme within 0.25 ATR of a level)": loc <= 0.25,
    "L25 & H4 map not against": (loc <= 0.25) & not_against,
    "L25 & H4 not against & room >= 2R": (loc <= 0.25) & not_against & room,
    "L25 & H1 swings with": (loc <= 0.25) & (d.h1_swings == "WITH"),
    "L50 & H4 not against": (loc <= 0.5) & not_against,
    "L50 & H4 not against & room >= 2R": (loc <= 0.5) & not_against & room,
    "L100 & H4 not against & H1 swings with": (loc <= 1.0) & not_against & (d.h1_swings == "WITH"),
    "L25 & H4 not against & 07-20 UTC": (loc <= 0.25) & not_against & d.time.dt.hour.between(7, 19),
}
plans = [c for c in d.columns if c.startswith("b0.")]
print(f"{len(d)} rows; months {months:.1f}; split {split:%Y-%m-%d}")
for name, mask in RULES.items():
    sub = d[mask]
    print(f"\n{name}: n {len(sub)} ({len(sub) / months:.1f}/month)")
    for p in plans:
        a, b = sub.loc[sub.time < split, p], sub.loc[sub.time >= split, p]
        win = (sub[p] > 0).mean() * 100
        print(f"  {p:10} {sub[p].mean():+.3f}  H1 {a.mean():+.3f} ({len(a)})  H2 {b.mean():+.3f} ({len(b)})  win {win:.0f} %")
