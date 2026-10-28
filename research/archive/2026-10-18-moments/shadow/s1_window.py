"""S1 (the M1 fade with the 15-spread floor and a 240-bar time stop: SETUP_REVIEW §23, the best S1 form) on the
OWN window 2026-03-01 .. 10-14, month by month and week by week (owner, 2026-10-18: "at least one trade a day from
F1, S1 or a new one"). The S1 harness's own costs (7 points of slippage, the M1 spread column): lighter than the
auditor's (+0.08 spread, 0.15 stop slippage), so the line with the auditor's costs is added (R x stop in USD).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/s1_window.py
"""

import json
import sys
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
import s1_funnel as f  # noqa: E402

NY = ZoneInfo("America/New_York")
f.below_normal_priority()
point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
m1 = f.load("M1")
m1 = m1[m1.index >= pd.Timestamp("2025-12-01", tz="UTC")]
ev = f.events(m1, 20)
for label, slip in (("S1 harness costs (7 pt)", 7.0), ("auditor-like costs (15 pt + 8 pt spread)", 15.0)):
    f.SLIP = slip
    d = f.outcomes(m1.assign(spread=m1.spread + (8 if slip > 7 else 0)), ev, point, k=15, spreads_only=True, time_stop=240)
    ny = d.t.dt.tz_convert(NY)
    nym = ny.dt.hour * 60 + ny.dt.minute
    utc = d.t.dt.hour + d.t.dt.minute / 60
    wd = d.t.dt.weekday
    keep = (wd < 5) & (utc >= 7) & (utc < 20) & ~((wd == 4) & (utc >= 16)) & ~((nym >= 480) & (nym < 720))
    s = f.one_at_a_time(d[keep], 60)
    s = s[(s.t >= pd.Timestamp("2026-03-01", tz="UTC")) & (s.t < pd.Timestamp("2026-10-14", tz="UTC"))]
    days = pd.bdate_range("2026-03-01", "2026-10-13").size
    print(f"\n== {label}: {len(s)} trades ({len(s) / days:.2f}/day), R {s.r.mean():+.3f}")
    for k, v in s.groupby(s.t.dt.strftime("%Y-%m")):
        print(f"  {k}: {len(v):3} trades, R {v.r.mean():+.3f}, sum {v.r.sum():+.1f} R")
    wk = s.t.dt.tz_convert("Asia/Bangkok").dt.to_period("W-SUN")
    g = s.groupby(wk).r.sum()
    print(f"  weeks with trades {len(g)}, positive {(g > 0).sum()}")
