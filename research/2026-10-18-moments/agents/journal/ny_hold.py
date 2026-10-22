"""The NY straddle held longer, and a second straddle at the US equity open (owner 2026-10-22: "Tuesday's H1 ran at
21:00-22:00 Thai"): the 08:30-NY straddle (+-2 USD from the mid at 08:30:00, live 60 s, stop 8 USD from the fill) held
30 / 60 / 90 / 120 / 180 minutes from 08:30, and the same straddle at 09:30 NY held 30 / 60 / 120 minutes. Every weekday
of the learning weeks (2025-10-20 .. 2026-04-17), on ticks, spread only.

    .venv/Scripts/python research/2026-10-18-moments/agents/journal/ny_hold.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "precursors"))
import check_plan1 as C  # noqa: E402

MIN = 60 * 10**9


def straddle(t, bid, ask, t0: int, hold_min: int) -> float | None:
    i0 = int(np.searchsorted(t, t0))
    if i0 >= len(t) or t[i0] - t0 > 5 * 10**9:
        return None
    ref = (bid[i0] + ask[i0]) / 2
    end = int(np.searchsorted(t, t0 + 60 * 10**9))
    for k in range(i0, end):
        side = 1 if ask[k] >= ref + 2 else -1 if bid[k] <= ref - 2 else 0
        if side:
            f = k + 1  # fill on the next tick, as the bot
            if f >= len(t):
                return None
            entry = ask[f] if side > 0 else bid[f]
            px, _, _ = C.manage(t, bid, ask, f, entry, side, entry - side * 8.0, None, t0 + hold_min * MIN)
            return (px - entry) * side / 8.0
    return None


def main() -> None:
    days = pd.bdate_range("2025-10-20", "2026-04-17", tz="UTC")
    rows = []
    for d in days:
        tk = C.day_ticks(d)
        if tk is None:
            continue
        t, bid, ask = tk
        ny = pd.Timestamp(d.date().isoformat() + " 08:30", tz="America/New_York")
        row = {"day": d.date()}
        for h in (30, 60, 90, 120, 180):
            row[f"0830_{h}"] = straddle(t, bid, ask, ny.tz_convert("UTC").value, h)
        for h in (30, 60, 120):
            row[f"0930_{h}"] = straddle(t, bid, ask, (ny + pd.Timedelta(hours=1)).tz_convert("UTC").value, h)
        rows.append(row)
    X = pd.DataFrame(rows)
    X["half"] = np.where(pd.to_datetime(X.day) < pd.Timestamp("2026-01-16"), "P1", "P2")
    cols = [c for c in X.columns if c[:2] == "08" or c[:2] == "09"]
    out = X.groupby("half")[cols].agg(["count", "mean"]).round(3)
    print(out.T.to_string())
    print("all:", X[cols].mean().round(3).to_dict(), "| n", X[cols].count().to_dict())
    X.to_parquet(Path(__file__).resolve().parent / "ny_hold.parquet")


if __name__ == "__main__":
    main()
