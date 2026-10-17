"""Round 2: add JOLTS (BLS, 10:00 ET) and weekly jobless claims (DOL, 08:30 ET) to extra_releases.csv, then check
each date against gold's M1 tick volume (the release bar against the 10 bars before it).

Sources (read 2026-10-17):
- JOLTS: https://www.bls.gov/bls/news-release/jolts.htm (archive file names carry the release dates; September 2025
  never published).
- Claims: https://oui.doleta.gov/unemploy/claims_arch.asp - "published each week on Thursday morning at 8:30am",
  moved when the Thursday is a federal holiday (the page's listed exception 2026-11-25 is a Wednesday). Thursday
  federal holidays 2021-2026 (OPM federal holidays): 2021-11-11, 2021-11-25, 2022-11-24, 2023-11-23, 2024-07-04,
  2024-11-28, 2025-06-19, 2025-11-27, 2025-12-25, 2026-01-01, and 2025-01-09 (the national day of mourning,
  federal offices closed) -> released the Wednesday before. The 2025 lapse in
  appropriations (2025-10-01 .. 2025-11-12) and the week after are left out (no national release dates sourced).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/calendar2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402

HERE = Path("research/2026-10-18-moments/agents/news")
JOLTS = """2021-09-08 2021-10-12 2021-11-12 2021-12-08 2022-01-04 2022-02-01 2022-03-09 2022-03-29 2022-05-03
2022-06-01 2022-07-06 2022-08-02 2022-08-30 2022-10-04 2022-11-01 2022-11-30 2023-01-04 2023-02-01 2023-03-08
2023-04-04 2023-05-02 2023-05-31 2023-07-06 2023-08-01 2023-08-29 2023-10-03 2023-11-01 2023-12-05 2024-01-03
2024-01-30 2024-03-06 2024-04-02 2024-05-01 2024-06-04 2024-07-02 2024-07-30 2024-09-04 2024-10-01 2024-10-29
2024-12-03 2025-01-07 2025-02-04 2025-03-11 2025-04-01 2025-04-29 2025-06-03 2025-07-01 2025-07-29 2025-09-03
2025-09-30 2025-12-09 2026-01-07 2026-02-05 2026-03-13 2026-03-31 2026-05-05 2026-06-02 2026-06-30 2026-08-04
2026-09-01 2026-09-29""".split()
HOLIDAY_THU = {"2021-11-11", "2021-11-25", "2022-11-24", "2023-11-23", "2024-07-04", "2024-11-28", "2025-06-19",
               "2025-11-27", "2025-12-25", "2026-01-01", "2025-01-09"}


def claims() -> list[str]:
    out = []
    for d in pd.date_range("2021-09-02", "2026-10-15", freq="W-THU"):
        s = d.strftime("%Y-%m-%d")
        if "2025-10-01" <= s <= "2025-11-19":
            continue
        out.append((d - pd.Timedelta(days=1)).strftime("%Y-%m-%d") if s in HOLIDAY_THU else s)
    return out


def main() -> None:
    x = pd.read_csv(HERE / "extra_releases.csv", dtype=str, keep_default_na=False)
    x = x[~x.event.isin(["JOL", "CLM"])]
    add = [dict(date=d, time_et="10:00", event="JOL", source="bls.gov jolts.htm archive") for d in JOLTS]
    add += [dict(date=d, time_et="08:30", event="CLM", source="DOL claims_arch.asp rule + OPM Thursday holidays")
            for d in claims()]
    x = pd.concat([x, pd.DataFrame(add)], ignore_index=True).sort_values(["date", "time_et"])
    x.to_csv(HERE / "extra_releases.csv", index=False)
    m = gold.bars("M1")
    v = m.tick_volume.to_numpy(float)
    pos = pd.Series(np.arange(len(m)), index=m.index)
    for ev in ("JOL", "CLM"):
        y = x[x.event == ev]
        t = pd.to_datetime(y.date + " " + y.time_et).dt.tz_localize(gold.NY).dt.tz_convert("UTC")
        ratio = []
        for tt in t:
            i = pos.get(tt)
            ratio.append(np.nan if i is None else v[i] / v[i - 10 : i].mean())
        r = pd.Series(ratio, index=y.date.to_numpy())
        print(f"{ev}: {len(r)} dates, release-bar volume / prior 10 bars: median {r.median():.2f}, "
              f"share >= 1.5: {(r >= 1.5).mean():.2f}; lowest: {r.nsmallest(6).round(2).to_dict()}")


if __name__ == "__main__":
    main()
