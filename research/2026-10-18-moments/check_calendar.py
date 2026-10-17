"""Sanity check of the release calendar: gold's range in the first 5 minutes after each release against the
same New York clock time on the previous 20 weekdays without a release then. A release that moved nothing
(ratio near 1) in a series that usually spikes points to a wrong date or time. The ``check`` rows are also
read at the other candidate time (08:30 / 10:00).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/check_calendar.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402


def window_range(m1: pd.DataFrame, t: pd.Timestamp, minutes: int = 5) -> float:
    w = m1.loc[t : t + pd.Timedelta(minutes=minutes - 1)]
    if len(w) < minutes - 1:
        return np.nan
    return float(w["high"].max() - w["low"].min())


def baseline(m1: pd.DataFrame, date: str, time_et: str, busy: set[pd.Timestamp]) -> float:
    day = pd.Timestamp(date)
    vals = []
    for k in range(1, 40):
        d = day - pd.Timedelta(days=k)
        if d.weekday() > 4:
            continue
        t = pd.Timestamp(f"{d.date()} {time_et}").tz_localize(gold.NY).tz_convert("UTC")
        if t in busy:
            continue
        r = window_range(m1, t)
        if not np.isnan(r):
            vals.append(r)
        if len(vals) == 20:
            break
    return float(np.median(vals)) if len(vals) >= 10 else np.nan


def main() -> None:
    gold.below_normal_priority()
    m1 = gold.bars("M1")
    print("M1", m1.index.min(), "..", m1.index.max(), len(m1))
    c = gold.releases()
    busy = set(c["t"])
    c["r5"] = [window_range(m1, t) for t in c["t"]]
    c["base"] = [baseline(m1, d, te, busy) for d, te in zip(c["date"], c["time_et"], strict=True)]
    c["ratio"] = c["r5"] / c["base"]
    have = c.dropna(subset=["ratio"])
    print(f"\n{len(have)} of {len(c)} releases inside the data; ratio = 5-minute range / usual at that clock time")
    print(have.groupby("event")["ratio"].describe(percentiles=[0.1, 0.5]).round(2).to_string())
    print("\nWeakest per event (ratio < 1.3):")
    print(have[have.ratio < 1.3][["date", "time_et", "event", "r5", "base", "ratio"]].round(2).to_string())
    print("\nRows to check, both candidate times:")
    for _, r in c[c.note != ""].iterrows():
        for te in ("08:30", "10:00"):
            t = pd.Timestamp(f"{r.date} {te}").tz_localize(gold.NY).tz_convert("UTC")
            rr, bb = window_range(m1, t), baseline(m1, r.date, te, busy)
            print(f"  {r.date} {r.event} at {te}: range {rr:.2f}, usual {bb:.2f}, ratio {rr / bb:.2f}")
    missing = c[c.ratio.isna()]
    print(f"\nOutside the data or gaps: {len(missing)}", missing[["date", "event"]].values.tolist()[:20])


if __name__ == "__main__":
    main()
