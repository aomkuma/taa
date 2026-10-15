"""Score the bot's chart read against the blind sub-agent reads of the 20 eye-check charts (2026-10-15).

Trend: the bot's structure equals the agent's (UP/DOWN/CONTRACTING/BROADENING/FLAT). Levels: the bot's nearest
support and nearest resistance each within 0.5 ATR of the agent's (both absent also agrees). The agent read
pixels, so its prices carry some error; the score is a direction check for changes, not ground truth.

    .venv/Scripts/python research/2026-10-14-chart-read/eye_check_score.py
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import replace

import pandas as pd

sys.path.insert(0, ".")
from app.indicators.chart_read import ChartReadFrame, ChartReadParams  # noqa: E402

H = "data/history/FBS-Demo"
DIR = "research/2026-10-14-chart-read/"
READ_BARS = 1500


def rows() -> list[tuple[int, str, str, pd.Timestamp]]:
    out = []
    for line in open(DIR + "EYE_CHECK.md", encoding="utf-8"):
        if line.startswith("| ") and "open](" in line:
            c = [x.strip() for x in line.split("|")]
            out.append((int(c[1]), c[2], c[3], pd.Timestamp(re.search(r"end=([^&]+)", line).group(1))))  # type: ignore[union-attr]
    return out


def read_at(sym: str, tf: str, end: pd.Timestamp, params: ChartReadParams):  # type: ignore[no-untyped-def]
    d = pd.read_parquet(f"{H}/{sym}/{tf}.parquet").sort_values("close_time")
    d.index = pd.DatetimeIndex(pd.to_datetime(d["close_time"], utc=True))
    d = d[d.index <= end].tail(READ_BARS)
    point = float(json.load(open(f"{H}/{sym}/spec.json"))["spec"]["point"])
    return ChartReadFrame(tf, d[["open", "high", "low", "close"]].astype(float), point, params).at(len(d) - 1)


def score(params: ChartReadParams, now: bool) -> tuple[int, int, int]:
    agent = json.load(open(DIR + "eye_check_agent.json", encoding="utf-8"))["reads"]
    trend = levels = both = 0
    for n, sym, tf, end in rows():
        r = read_at(sym, tf, end, params)
        a_trend, a_sup, a_res = agent[str(n)]
        mine = (r.structure_now or r.structure).value if now else r.structure.value
        t_ok = mine == a_trend
        sup, res = r.nearest(above=False), r.nearest(above=True)

        def close(lv, x):  # type: ignore[no-untyped-def]
            return (lv is None and x is None) or (
                lv is not None and x is not None and abs(lv.price - x) <= 0.5 * r.atr
            )

        l_ok = close(sup, a_sup) and close(res, a_res)
        trend, levels, both = trend + t_ok, levels + l_ok, both + (t_ok and l_ok)
    return trend, levels, both


if __name__ == "__main__":
    rules = ChartReadParams()  # what the setups use
    shown = rules.for_display()  # what the PWA chart draws
    for name, p, now in (
        ("rules (spent at 2, no minor, confirmed swings)", rules, False),
        ("spent at 4 only", replace(shown, minor_depth=0), False),
        ("+ minor swings (depth 5)", shown, False),
        ("+ the read now (provisional pivot): the chart", shown, True),
    ):
        t, lv, b = score(p, now)
        print(f"{name:52} trend {t:2}/20  levels {lv:2}/20  both {b:2}/20")
