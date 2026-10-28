"""US 10:00 ET releases from official sources only -> cal10.csv (date, time_et, event, source).

Sources (read 2026-10-17):
- Census economic indicator calendars, https://www.census.gov/economic-indicators/calendar-listview-2023.html,
  -2024.html, -2025.html, -2026.html: New Residential Sales (NHS), Construction Spending (CS), Manufacturers'
  Shipments, Inventories and Orders full report (M3), all 10:00 ET. The 2025 page lists no NHS after 2025-09-24 and
  no CS/M3 between 2025-09-03 and 2025-11-17 (the lapse in appropriations; the delayed releases are not listed),
  so 2025-10 .. 2025-12 is incomplete for these.
- BLS JOLTS (10:00 ET): dates from the news agent's `agents/news/extra_releases.csv` (bls.gov jolts.htm archive).
- ISM (login wall), Conference Board and Michigan: no official dated archive reachable -> not included.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/cal10.py
"""

from __future__ import annotations

import pandas as pd

CENSUS = {
    "NHS": """2023-01-26 2023-02-24 2023-03-23 2023-04-25 2023-05-23 2023-06-27 2023-07-26 2023-08-23 2023-09-26
2023-10-25 2023-11-27 2023-12-22 2024-01-25 2024-02-26 2024-03-25 2024-04-23 2024-05-23 2024-06-26 2024-07-24
2024-08-23 2024-09-25 2024-10-24 2024-11-26 2024-12-23 2025-01-27 2025-02-26 2025-03-25 2025-04-23 2025-05-23
2025-06-25 2025-07-24 2025-08-25 2025-09-24 2026-01-13 2026-02-20 2026-03-19 2026-05-05 2026-05-28 2026-06-24
2026-07-24 2026-08-25 2026-09-24 2026-10-27 2026-11-25 2026-12-23""",
    "CS": """2023-01-03 2023-02-01 2023-03-01 2023-04-03 2023-05-01 2023-06-01 2023-07-03 2023-08-01 2023-09-01
2023-10-02 2023-11-01 2023-12-01 2024-01-02 2024-02-01 2024-03-01 2024-04-01 2024-05-01 2024-06-03 2024-07-01
2024-08-01 2024-09-03 2024-10-01 2024-11-01 2024-12-02 2025-01-02 2025-02-03 2025-03-03 2025-04-01 2025-05-01
2025-06-02 2025-07-01 2025-08-01 2025-09-02 2025-11-17 2026-01-21 2026-02-27 2026-03-23 2026-05-07 2026-06-01
2026-07-01 2026-08-03 2026-09-01 2026-10-01 2026-11-02 2026-12-01""",
    "M3": """2023-01-06 2023-02-02 2023-03-06 2023-04-04 2023-05-02 2023-06-05 2023-07-05 2023-08-03 2023-09-05
2023-10-04 2023-11-02 2023-12-04 2024-01-05 2024-02-02 2024-03-05 2024-04-02 2024-05-02 2024-06-04 2024-07-03
2024-08-02 2024-09-04 2024-10-03 2024-11-04 2024-12-04 2025-01-06 2025-02-04 2025-03-05 2025-04-02 2025-05-02
2025-06-03 2025-07-03 2025-08-04 2025-09-03 2025-11-18 2025-12-04 2026-01-07 2026-01-29 2026-02-23 2026-03-18
2026-04-10 2026-05-04 2026-06-03 2026-07-02 2026-08-04 2026-09-02 2026-10-02 2026-11-03 2026-12-03""",
}


def main() -> None:
    rows = []
    for ev, s in CENSUS.items():
        y = s.split()[0][:4]
        rows += [dict(date=d, time_et="10:00", event=ev, source=f"census.gov calendar-listview-{d[:4]}") for d in s.split()]
        del y
    j = pd.read_csv("research/2026-10-18-moments/agents/news/extra_releases.csv", dtype=str)
    j = j[j.event == "JOL"]
    rows += [dict(date=d, time_et="10:00", event="JOL", source="bls.gov jolts.htm archive (news agent)") for d in j.date]
    c = pd.DataFrame(rows).sort_values(["date", "event"])
    c.to_csv("research/2026-10-18-moments/agents/fx/cal10.csv", index=False)
    print(c.groupby("event").size(), c.date.min(), c.date.max())


if __name__ == "__main__":
    main()
