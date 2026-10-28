"""The TS session's gold habits as overlays on S1 (owner, 2026-10-17: the two sessions work together; their
findings: research/2026-10-17-ts/ts_behaviour.py, docs/OWNER_TRADING.md "TS: why the losers lost").

S1's three-year trade set from the funnel with the spread floor (15 spreads, time stop 240, cooldown 60, one at
a time; ``s1_funnel.py``), and at each entry, as the TS study defines them:

- ``day_pos``: the entry within the broker day's range so far, the trade's way (1 = a buy at the day's high);
  "against the day" = below 0.5 (a buy in the lower half, a sell in the upper half);
- ``pdx_room``: the room to the previous broker day's high (a buy) / low (a sell) in ATR (the trade's 60-bar A);
  negative = already beyond it.

S1 trades 07-20 UTC (03-16 New York), so the TS hour bands (21-23 and 17-20 New York) do not apply.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-17-s1/s1_overlays.py
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-17-s1")
sys.path.insert(0, ".")
import s1_funnel as f  # noqa: E402


def main() -> None:
    f.below_normal_priority()
    point = json.load(open(f"{f.H}/spec.json"))["spec"]["point"]
    m1 = f.load("M1")
    d = f.outcomes(m1, f.events(m1, 20), point, 15, spreads_only=True, time_stop=240)
    ny = d["t"].dt.tz_convert(f.NY)
    nym = ny.dt.hour * 60 + ny.dt.minute
    utc = d["t"].dt.hour + d["t"].dt.minute / 60
    wd = d["t"].dt.weekday
    keep = (wd < 5) & ~((wd == 4) & (utc >= 16)) & (utc >= 7) & (utc < 20) & ~((nym >= 480) & (nym < 720))
    t = f.one_at_a_time(d[keep], 60).copy()

    d1 = pd.read_parquet(f"{f.H}/D1.parquet").sort_values("open_time")
    d1_open = pd.to_datetime(d1["open_time"], utc=True).to_numpy(dtype="datetime64[ns]")
    d1_high, d1_low = d1["high"].to_numpy(float), d1["low"].to_numpy(float)
    times = m1.index.to_numpy(dtype="datetime64[ns]")  # M1 close times
    hi, lo, c = (m1[k].to_numpy(float) for k in ("high", "low", "close"))
    pc = np.r_[np.nan, c[:-1]]
    a = pd.Series(np.nanmax(np.c_[hi - lo, np.abs(hi - pc), np.abs(lo - pc)], axis=1)).rolling(60).mean().to_numpy()
    pos, room = [], []
    for i, side in zip(t["i"].to_numpy(), t["side"].to_numpy(), strict=True):
        k = int(np.searchsorted(d1_open, times[i], side="right")) - 1
        if k < 1:
            pos.append(np.nan)
            room.append(np.nan)
            continue
        j0 = int(np.searchsorted(times, d1_open[k], side="right"))
        dh, dl = hi[j0 : i + 1].max(), lo[j0 : i + 1].min()
        x = c[i]
        p = (x - dl) / (dh - dl) if dh > dl else 0.5
        pos.append(p if side > 0 else 1 - p)
        level = d1_high[k - 1] if side > 0 else d1_low[k - 1]
        room.append((level - x) * side / a[i])
    t["day_pos"], t["pdx_room"] = pos, room
    t["year"] = np.select([t.t < f.YEARS["A"][0], t.t < f.YEARS["B"][0]], ["C", "A"], "B")
    t["against_day"] = np.where(t.day_pos < 0.5, "against the day (<0.5)", "with the day (>=0.5)")
    t["beyond_pdx"] = np.where(t.pdx_room < 0, "beyond the previous day's extreme", "inside")
    t["side_name"] = np.where(t.side > 0, "BUY", "SELL")
    for col in ("side_name", "against_day", "beyond_pdx"):
        g = t.groupby([col, "year"]).r.agg(["count", "mean"]).unstack("year").round(3)
        print(f"\n{col}\n{g.to_string()}")
    t.to_parquet("data/research/s1_overlays.parquet")


if __name__ == "__main__":
    main()
