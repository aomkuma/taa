"""More S1 trades (owner, 2026-10-18: at least one trade a day). S1 = the M1 fade of a counter-trend Donchian break
in an H1 + M15 trend, the 15-spread floor, 240-bar time stop (SETUP_REVIEW §23). Costs: the M1 spread column + 8
points, 15 points of slippage each way (the auditor's level). Levers written before computing: Donchian 20 / 10;
hours 07-20 UTC or also Asia 00-07; the New York 08-12 skip on / off; cooldown 60 / 30 / 15 bars after an entry.
Chosen on design (2024-09 .. 2026-02, three half-years: R >= +0.10 in all, the most trades), then the window
2026-03-01 .. 10-14 once.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/s1_more.py
"""

import itertools
import json
import sys
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
import s1_funnel as f  # noqa: E402

NY = ZoneInfo("America/New_York")
f.below_normal_priority()
f.SLIP = 15.0
point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
m1 = f.load("M1")
m1 = m1[m1.index >= pd.Timestamp("2024-06-01", tz="UTC")]
m1 = m1.assign(spread=m1.spread + 8)
HALVES = [("24-09..25-02", "2024-09-01", "2025-03-01"), ("25-03..25-08", "2025-03-01", "2025-09-01"),
          ("25-09..26-02", "2025-09-01", "2026-03-01")]
WIN = ("2026-03-01", "2026-10-14")
rows = []
for n in (20, 10):
    d = f.outcomes(m1, f.events(m1, n), point, k=15, spreads_only=True, time_stop=240)
    ny = d.t.dt.tz_convert(NY)
    nym = ny.dt.hour * 60 + ny.dt.minute
    utc = d.t.dt.hour + d.t.dt.minute / 60
    wd = d.t.dt.weekday
    for asia, nyskip, cd in itertools.product((False, True), (True, False), (60, 30, 15)):
        keep = (wd < 5) & (utc >= (0 if asia else 7)) & (utc < 20) & ~((wd == 4) & (utc >= 16))
        if nyskip:
            keep &= ~((nym >= 480) & (nym < 720))
        s = f.one_at_a_time(d[keep], cd)
        cells = []
        for _, a, b in HALVES:
            r = s.r[(s.t >= pd.Timestamp(a, tz="UTC")) & (s.t < pd.Timestamp(b, tz="UTC"))]
            cells.append((len(r), r.mean()))
        w = s[(s.t >= pd.Timestamp(WIN[0], tz="UTC")) & (s.t < pd.Timestamp(WIN[1], tz="UTC"))]
        rows.append(dict(n=n, asia=asia, nyskip=nyskip, cd=cd, design_n=sum(c[0] for c in cells),
                         design=" ".join(f"{m:+.2f}({k})" for k, m in cells), all_pos=all(m >= 0.10 for _, m in cells),
                         win_n=len(w), win_r=w.r.mean(), win_months=" ".join(f"{k[5:]}{v:+.1f}" for k, v in w.groupby(w.t.dt.strftime('%Y-%m')).r.sum().items())))
R = pd.DataFrame(rows)
dd = pd.bdate_range("2024-09-01", "2026-02-28").size
wdays = pd.bdate_range(*WIN).size
R["design_per_day"] = R.design_n / dd
R["win_per_day"] = R.win_n / wdays
pd.set_option("display.width", 250)
print(R.sort_values(["all_pos", "design_n"], ascending=False).round(3).to_string(index=False))
