"""S1's trade-count levers with the spread floor (owner, 2026-10-17: at least 450 trades in three years).

Every variant keeps the floor (``min_atr_spreads`` 15, spread only, as the strategy sees it) and changes one or
more of: the Donchian length, the hours (07-20 UTC, or 00-20 UTC with Asia; never the 21-24 rollover), the
New York skip (none, 08:00-12:00, 09:30-12:00), the cooldown after an entry and the time stop. One position
at a time. Selection on year A only (2024-10 .. 2025-09); years C and B check it. Fills and plan as
``s1_funnel.py``.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/s1_levers.py
"""

from __future__ import annotations

import itertools
import json
import sys

import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
sys.path.insert(0, ".")
import s1_funnel as f  # noqa: E402

FLOOR = 15
SKIPS = {"none": None, "08-12": (8 * 60, 12 * 60), "09:30-12": (9 * 60 + 30, 12 * 60)}


def main() -> None:
    f.below_normal_priority()
    point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
    m1 = f.load("M1")
    rows = []
    for n, ts in itertools.product((10, 20), (60, 120, 240)):
        d = f.outcomes(m1, f.events(m1, n), point, FLOOR, spreads_only=True, time_stop=ts)
        ny = d["t"].dt.tz_convert(f.NY)
        nym = ny.dt.hour * 60 + ny.dt.minute
        utc = d["t"].dt.hour + d["t"].dt.minute / 60
        wd = d["t"].dt.weekday
        base = (wd < 5) & ~((wd == 4) & (utc >= 16)) & (utc < 20)
        for hours, skip, cd in itertools.product(("07-20", "00-20"), SKIPS, (0, 15, 30, 60)):
            keep = base & (utc >= (7 if hours == "07-20" else 0))
            if SKIPS[skip] is not None:
                lo, hi = SKIPS[skip]
                keep &= ~((nym >= lo) & (nym < hi))
            t = f.one_at_a_time(d[keep], cd)
            row = {"n": n, "time_stop": ts, "hours": hours, "ny_skip": skip, "cooldown": cd}
            for y, (a, b) in f.YEARS.items():
                r = t.loc[(t.t >= a) & (t.t < b), "r"]
                row[f"{y}_n"], row[f"{y}_r"] = len(r), r.mean()
            row["total"] = row["C_n"] + row["A_n"] + row["B_n"]
            row["all_r"] = t.loc[(t.t >= f.YEARS["C"][0]) & (t.t < f.YEARS["B"][1]), "r"].mean()
            rows.append(row)
        print(f"n {n}, time stop {ts}: done", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv("data/research/s1_levers.csv", index=False)
    pd.set_option("display.width", 200)
    cols = ["n", "time_stop", "hours", "ny_skip", "cooldown", "C_n", "C_r", "A_n", "A_r", "B_n", "B_r", "total", "all_r"]
    print("\nS1 now with the floor (n 20, time stop 240, 07-20, skip 08-12, cooldown 60):")
    now = out[(out.n == 20) & (out.time_stop == 240) & (out.hours == "07-20") & (out.ny_skip == "08-12") & (out.cooldown == 60)]
    print(now[cols].round(3).to_string(index=False))
    print("\nat least 450 trades in three years, ranked by year A (the choosing year):")
    big = out[out.total >= 450].sort_values("A_r", ascending=False)
    print(big[cols].head(15).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
