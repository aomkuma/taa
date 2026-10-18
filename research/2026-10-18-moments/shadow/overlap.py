"""Do F1, S1 and S2 trade at different moments? (owner, 2026-10-18). The window 2026-03-01 .. 10-14: F1 v2's trades
(f1_v2_window_trades.csv, held to its exit), S1's (s1_window.py, harness costs), S2's releases; how many overlap in
time (one gold position at a time in the bot), by session.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/overlap.py
"""

import json
import sys
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
import s1_funnel as f  # noqa: E402

NY = ZoneInfo("America/New_York")
point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
m1 = f.load("M1")
m1 = m1[m1.index >= pd.Timestamp("2025-12-01", tz="UTC")]
d = f.outcomes(m1, f.events(m1, 20), point, k=15, spreads_only=True, time_stop=240)
ny = d.t.dt.tz_convert(NY)
nym = ny.dt.hour * 60 + ny.dt.minute
utc = d.t.dt.hour + d.t.dt.minute / 60
wd = d.t.dt.weekday
s1 = f.one_at_a_time(d[(wd < 5) & (utc >= 7) & (utc < 20) & ~((wd == 4) & (utc >= 16)) & ~((nym >= 480) & (nym < 720))], 60)
s1 = s1[(s1.t >= pd.Timestamp("2026-03-01", tz="UTC")) & (s1.t < pd.Timestamp("2026-10-14", tz="UTC"))].copy()
s1["end"] = m1.index[s1.x.to_numpy()] + pd.Timedelta(minutes=1)
f1 = pd.read_csv("research/2026-10-18-moments/shadow/f1_v2_window_trades.csv", parse_dates=["t"])
f1["t"] = pd.to_datetime(f1.t, utc=True)
f1["end"] = f1.t + pd.Timedelta(minutes=60)  # at most 60 min (runners up to 180: counted as 60 here)
rel = pd.read_csv("app/news/us_releases.csv")
rel = rel[rel.event.isin(["CPI", "NFP"])]
s2 = pd.DatetimeIndex(pd.to_datetime(rel.date + " " + rel.time_et).dt.tz_localize(NY).dt.tz_convert("UTC"))
s2 = s2[(s2 >= pd.Timestamp("2026-03-01", tz="UTC")) & (s2 < pd.Timestamp("2026-10-14", tz="UTC"))]


def sess(t: pd.Series) -> pd.Series:
    h = t.dt.hour
    return pd.Series(pd.cut(h, [-1, 6, 11, 23], labels=["Asia 00-07", "London 07-12", "NY 12-24"]), index=t.index)


def busy(a_t, b):
    return sum(((b.t <= t) & (t < b.end)).any() for t in a_t)


print(f"F1 v2: {len(f1)} trades; by session {sess(f1.t).value_counts().to_dict()}")
print(f"S1   : {len(s1)} trades; by session {sess(s1.t).value_counts().to_dict()}")
print(f"S2   : {len(s2)} releases (12:30 / 13:30 UTC)")
print(f"S1 entries while an F1 trade is open: {busy(s1.t, f1)}; F1 entries while an S1 trade is open: {busy(f1.t, s1)}")
print(f"releases while F1 open: {busy(pd.Series(s2), f1)}; while S1 open: {busy(pd.Series(s2), s1)}")
same_day = set(f1.t.dt.date) & set(s1.t.dt.date)
days = pd.bdate_range("2026-03-02", "2026-10-13")
any_day = set(f1.t.dt.date) | set(s1.t.dt.date) | set(s2.date)
print(f"days with an F1 and an S1 trade: {len(same_day)}; days with any of the three: {len(any_day)} of {len(days)}")
