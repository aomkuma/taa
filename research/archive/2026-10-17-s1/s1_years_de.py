"""S1 with and without the spread floor on two more held-out years of gold, D 2022-10 .. 2023-09 and E 2021-10 ..
2022-09 (the TS session's separate store data/history_old; owner, 2026-10-17: the sessions work together).
The same harness as s1_funnel.py; nothing was chosen on these years.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/s1_years_de.py
"""

import json
import sys

import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
sys.path.insert(0, ".")
import s1_funnel as f  # noqa: E402

f.H = "data/history_old/FBS-Demo/XAUUSD"
f.YEARS = {
    "E": (pd.Timestamp("2021-10-01", tz="UTC"), pd.Timestamp("2022-10-01", tz="UTC")),
    "D": (pd.Timestamp("2022-10-01", tz="UTC"), pd.Timestamp("2023-10-01", tz="UTC")),
}


def main() -> None:
    f.below_normal_priority()
    point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
    m1 = f.load("M1")
    ev = f.events(m1, 20)
    for label, kw, gate in (
        ("S1 now (spread rule, time stop 60)", {}, True),
        ("S1 + floor 15 spreads, time stop 240", {"k": 15, "spreads_only": True, "time_stop": 240}, False),
    ):
        d = f.outcomes(m1, ev, point, **kw)
        ny = d["t"].dt.tz_convert(f.NY)
        nym = ny.dt.hour * 60 + ny.dt.minute
        utc = d["t"].dt.hour + d["t"].dt.minute / 60
        wd = d["t"].dt.weekday
        keep = (wd < 5) & ~((wd == 4) & (utc >= 16)) & (utc >= 7) & (utc < 20) & ~((nym >= 480) & (nym < 720))
        if gate:
            keep &= d.spread_a <= 0.3 / 0.85
        print(f.report(label, f.one_at_a_time(d[keep], 60)), flush=True)
    print("median A and spread/A:", {y: round(float(d[(d.t >= a) & (d.t < b)].spread_a.median()), 2) for y, (a, b) in f.YEARS.items()})


if __name__ == "__main__":
    main()


def gated(cap: float = 0.25) -> None:
    """Fixed before looking at D/E (2026-10-17 16:05 Thai): S1 + floor only while the spread is at most *cap* A."""
    f.below_normal_priority()
    for h, years in (("data/history_old/FBS-Demo/XAUUSD", {k: f.YEARS[k] for k in ("E", "D")}),
                     ("data/history/FBS-Demo/XAUUSD", None)):
        f.H = h
        if years is None:
            f.YEARS = {
                "C": (pd.Timestamp("2023-10-01", tz="UTC"), pd.Timestamp("2024-10-01", tz="UTC")),
                "A": (pd.Timestamp("2024-10-01", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC")),
                "B": (pd.Timestamp("2025-10-01", tz="UTC"), pd.Timestamp("2026-10-01", tz="UTC")),
            }
        point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
        m1 = f.load("M1")
        d = f.outcomes(m1, f.events(m1, 20), point, k=15, spreads_only=True, time_stop=240)
        ny = d["t"].dt.tz_convert(f.NY)
        nym = ny.dt.hour * 60 + ny.dt.minute
        utc = d["t"].dt.hour + d["t"].dt.minute / 60
        wd = d["t"].dt.weekday
        keep = (wd < 5) & ~((wd == 4) & (utc >= 16)) & (utc >= 7) & (utc < 20) & ~((nym >= 480) & (nym < 720))
        print(f.report(f"floor + spread <= {cap:g} A", f.one_at_a_time(d[keep & (d.spread_a <= cap)], 60)), flush=True)
        if years is not None:
            f.YEARS = years
