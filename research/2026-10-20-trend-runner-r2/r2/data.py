"""Verified, design-only input readers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .boundaries import DESIGN_END, DESIGN_START, WARMUP_START, assert_before_exam

R2_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = R2_ROOT.parents[1]
R1_ROOT = R2_ROOT.parent / "2026-10-20-trend-runner"
M1_PATH = REPO_ROOT / "data/history/FBS-Demo/XAUUSD/M1.parquet"
PROVENANCE_PATH = R2_ROOT / "provenance.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_frozen_inputs() -> dict[str, str]:
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    expected: dict[str, str] = provenance["sha256"]
    actual = {name: sha256(R1_ROOT / name) for name in expected}
    mismatches = {name: (expected[name], value) for name, value in actual.items() if value != expected[name]}
    if mismatches:
        raise ValueError(f"Immutable TR1 input hash mismatch: {mismatches}")
    return actual


def _utc(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(result[column], utc=True)
    return result


def load_entries_and_outcomes() -> pd.DataFrame:
    """Return one immutable entry row with FAST/RUNNER outcomes."""
    verify_frozen_inputs()
    pieces: list[pd.DataFrame] = []
    for period in ("p1", "p2"):
        entries = pd.read_parquet(R1_ROOT / f"frozen_entries_{period}.parquet")
        results = pd.read_parquet(R1_ROOT / f"frozen_results_{period}.parquet")
        entries = _utc(entries, ("anchor", "entry_time"))
        results = _utc(results, ("entry_time", "exit_time"))
        assert_before_exam(entries["entry_time"], label=f"{period} entries")
        if not results["complete"].all():
            raise ValueError(f"{period} contains incomplete frozen outcomes")

        entries = entries.reset_index(drop=True).reset_index(names="entry_id")
        entries.insert(0, "source_period", period.upper())
        entries.insert(1, "trade_key", [f"{period.upper()}-{index:03d}" for index in entries["entry_id"]])
        outcomes = results.loc[results["family"].isin(["FAST", "SPLIT"])].copy()
        if len(outcomes) != 2 * len(entries):
            raise ValueError(f"{period}: expected exactly FAST and SPLIT per entry")
        wide = outcomes.pivot(index="entry_id", columns="family", values=["r", "usd_001", "exit_time"])
        wide.columns = [
            f"{metric}_{'runner' if family == 'SPLIT' else 'fast'}" for metric, family in wide.columns
        ]
        wide = wide.rename(
            columns={
                "r_fast": "fast_r",
                "r_runner": "runner_r",
                "usd_001_fast": "fast_usd",
                "usd_001_runner": "runner_usd",
                "exit_time_fast": "fast_exit_time",
                "exit_time_runner": "runner_exit_time",
            }
        )
        joined = entries.merge(wide, left_on="entry_id", right_index=True, validate="one_to_one")
        joined["outcome_available"] = joined[["fast_exit_time", "runner_exit_time"]].max(axis=1)
        pieces.append(joined)

    panel = (
        pd.concat(pieces, ignore_index=True)
        .sort_values(["entry_time", "trade_key"])
        .reset_index(drop=True)
    )
    if len(panel) != 280 or panel["trade_key"].duplicated().any():
        raise ValueError("Frozen entry population must contain exactly 280 unique rows")
    if panel["entry_time"].min() < DESIGN_START or panel["entry_time"].max() >= DESIGN_END:
        raise ValueError("Frozen entries escape declared design span")
    return panel


def load_design_m1(*, end: pd.Timestamp = DESIGN_END) -> pd.DataFrame:
    """Load warm-up/design M1 rows; a caller cannot request the exam."""
    end = pd.Timestamp(end)
    end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
    if end > DESIGN_END:
        raise ValueError("M1 reader cannot cross the locked exam boundary")
    frame = pd.read_parquet(
        M1_PATH,
        filters=[("open_time", ">=", WARMUP_START.to_pydatetime()), ("open_time", "<", end.to_pydatetime())],
    )
    frame = _utc(frame, ("open_time", "close_time"))
    frame = frame.sort_values("open_time").reset_index(drop=True)
    assert_before_exam(frame["open_time"], label="M1 open times")
    if len(frame) and frame["close_time"].max() > end:
        raise ValueError("M1 close time crosses requested design cutoff")
    if frame["open_time"].duplicated().any() or not frame["open_time"].is_monotonic_increasing:
        raise ValueError("M1 timestamps must be unique and increasing")
    return frame
