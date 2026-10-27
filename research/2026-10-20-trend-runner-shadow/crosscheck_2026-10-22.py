# ruff: noqa: E501, T201
"""Cross-check (2026-10-22): the shadow's own TR1 detector + fill + RUNNER outcome against the fixed TR1 tick
pipeline journal of the same weeks. Two independent implementations must give the same trades.

    .venv\\Scripts\\python research\\2026-10-20-trend-runner-shadow\\crosscheck_2026-10-22.py JOURNAL.csv START END
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from shadow.adapter import load_m1, load_ticks  # noqa: E402
from shadow.clocks import SESSIONS, anchor  # noqa: E402
from shadow.detector import detect, fill_and_risk  # noqa: E402
from shadow.outcome_adapter import load_outcome_ticks  # noqa: E402
from shadow.outcomes import build_structure_context, run_exit, structure_events  # noqa: E402

EXAM = (pd.Timestamp("2026-04-18", tz="UTC"), pd.Timestamp("2026-10-18", tz="UTC"))


def main() -> None:
    journal = pd.read_csv(sys.argv[1])
    start, end = pd.Timestamp(sys.argv[2]), pd.Timestamp(sys.argv[3])
    lo, hi = (
        (start - pd.Timedelta(days=30)).tz_localize("UTC"),
        (end + pd.Timedelta(days=3)).tz_localize("UTC"),
    )
    assert hi <= EXAM[0] or lo >= EXAM[1], "exam"  # noqa: S101
    m1 = load_m1(REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet", lo, hi)
    context = build_structure_context(m1)
    ticks_root = REPO / "data/ticks/XAUUSD"
    rows = []
    for day in pd.date_range(start, end - pd.Timedelta(days=1), freq="D"):
        if day.dayofweek >= 5:
            continue
        for window in SESSIONS:
            at = anchor(day, window)
            d = detect(m1, at, window)
            if d is None:
                continue
            f = fill_and_risk(
                d, load_ticks(ticks_root, d.decision_time, d.decision_time + pd.Timedelta(minutes=5))
            )
            if f is None:
                continue
            deadline = f["entry_time"] + pd.Timedelta(hours=8)
            ticks = load_outcome_ticks(ticks_root, f["entry_time"], deadline)
            events = structure_events(
                context, side=d.side, entry_time=f["entry_time"], entry_spread=f["spread"], end_time=deadline
            )
            r = run_exit("RUNNER", ticks, d.side, f["entry"], f["stop"], f["entry_time"], events)
            rows.append(
                {
                    "trade_id": f"TR1-{at.tz_convert('Asia/Bangkok').date()}-{window}",
                    "s_entry": f["entry"],
                    "s_stop": f["stop"],
                    "s_exit": r.exit_price,
                    "s_exit_time": r.exit_time,
                    "s_r": r.r,
                }
            )
    shadow = pd.DataFrame(rows)
    tr1 = journal.loc[
        journal.variant.str.startswith("TR1"), ["trade_id", "entry", "stop", "exit", "exit_time_utc", "r"]
    ]
    both = tr1.merge(shadow, on="trade_id", how="outer", indicator=True)
    both["same"] = (
        np.isclose(both.entry, both.s_entry)
        & np.isclose(both.stop, both.s_stop)
        & np.isclose(both.exit, both.s_exit)
        & (pd.to_datetime(both.exit_time_utc, utc=True) == pd.to_datetime(both.s_exit_time, utc=True))
        & np.isclose(both.r, both.s_r)
    )
    pd.set_option("display.width", 250)
    print(
        both[
            ["trade_id", "_merge", "entry", "s_entry", "stop", "s_stop", "exit", "s_exit", "r", "s_r", "same"]
        ].to_string(index=False)
    )
    print(
        f"\n{int(both.same.sum())} of {len(both)} identical; only in one: {int((both._merge != 'both').sum())}"
    )


if __name__ == "__main__":
    main()
