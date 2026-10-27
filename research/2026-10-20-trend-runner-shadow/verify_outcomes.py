# ruff: noqa: T201
"""Verify the independent outcome simulator against frozen safe-design P1/P2 results."""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FROZEN = REPO / "research/2026-10-20-trend-runner"
M1_PATH = REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet"
TICK_ROOT = REPO / "data/ticks/XAUUSD"
sys.path.insert(0, str(ROOT))

from shadow.adapter import load_m1  # noqa: E402
from shadow.outcomes import build_structure_context, run_exit, structure_events  # noqa: E402

FIELDS = (
    "complete",
    "exit_time",
    "exit_price",
    "reason",
    "r",
    "holding_minutes",
    "runner_activated",
    "partial_taken",
    "graduated",
    "final_stop",
)


@lru_cache(maxsize=4)
def tick_day(day: str) -> pd.DataFrame:
    path = TICK_ROOT / f"{day}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["time_utc", "bid", "ask"])
    frame = pd.read_parquet(path)
    frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)
    return frame


def tick_path(start: pd.Timestamp) -> pd.DataFrame:
    deadline = start + pd.Timedelta(hours=8)
    frames = []
    for day in pd.date_range(
        start.floor("D"), deadline.floor("D") + pd.Timedelta(days=14), freq="D"
    ):
        frame = tick_day(day.date().isoformat())
        if frame.empty:
            continue
        frames.append(frame)
        if (frame["time_utc"] >= deadline).any():
            break
    frame = pd.concat(frames, ignore_index=True)
    frame = frame.loc[frame["time_utc"] >= start].reset_index(drop=True)
    end = int(pd.DatetimeIndex(frame["time_utc"]).searchsorted(deadline, side="left"))
    if end >= len(frame):
        raise AssertionError(f"tick file does not cover deadline for {start}")
    return frame.iloc[: end + 1].reset_index(drop=True)


def equal(actual: object, expected: object) -> bool:
    if isinstance(actual, pd.Timestamp) or isinstance(expected, pd.Timestamp):
        return pd.Timestamp(actual) == pd.Timestamp(expected)
    if isinstance(actual, (float, np.floating)) or isinstance(expected, (float, np.floating)):
        return bool(np.isclose(float(actual), float(expected), rtol=1e-12, atol=1e-12, equal_nan=True))
    actual_value = actual.value if hasattr(actual, "value") else actual
    return actual_value == expected


def main() -> None:
    entries_by_period = {
        period: pd.read_parquet(FROZEN / f"frozen_entries_{period.lower()}.parquet")
        for period in ("P1", "P2")
    }
    results_by_period = {
        period: pd.read_parquet(FROZEN / f"frozen_results_{period.lower()}.parquet")
        for period in ("P1", "P2")
    }
    all_entries = pd.concat(entries_by_period.values(), ignore_index=True)
    m1 = load_m1(
        M1_PATH,
        all_entries["entry_time"].min() - pd.Timedelta(days=50),
        all_entries["entry_time"].max() + pd.Timedelta(hours=8, minutes=1),
    )
    context = build_structure_context(m1)
    mismatches: list[dict[str, object]] = []
    checked = 0
    for period in ("P1", "P2"):
        references = results_by_period[period]
        for entry_id, entry in entries_by_period[period].iterrows():
            entry_time = pd.Timestamp(entry["entry_time"])
            ticks = tick_path(entry_time)
            events = structure_events(
                context,
                side=int(entry["side"]),
                entry_time=entry_time,
                entry_spread=float(entry["spread"]),
                end_time=entry_time + pd.Timedelta(hours=8),
            )
            for family, reference_family in (("FAST", "FAST"), ("RUNNER", "SPLIT")):
                actual = run_exit(
                    family,
                    ticks,
                    int(entry["side"]),
                    float(entry["entry"]),
                    float(entry["stop"]),
                    entry_time,
                    events,
                )
                reference = references.loc[
                    (references["entry_id"] == entry_id)
                    & (references["family"] == reference_family)
                ].iloc[0]
                checked += 1
                for field in FIELDS:
                    actual_value = getattr(actual, field)
                    expected_value = reference[field]
                    if not equal(actual_value, expected_value):
                        mismatches.append(
                            {
                                "period": period,
                                "entry_id": int(entry_id),
                                "family": family,
                                "field": field,
                                "actual": str(actual_value),
                                "expected": str(expected_value),
                            }
                        )
    artifact = {
        "status": "PASS" if not mismatches else "FAIL",
        "scope": "safe-design P1/P2 only; exam unopened",
        "entries": len(all_entries),
        "outcomes_checked": checked,
        "fields_per_outcome": len(FIELDS),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
    }
    (ROOT / "OUTCOME_PARITY.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
