"""Full P1 detector/fill/feature parity and truncation verification."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from shadow.adapter import load_m1  # noqa: E402
from shadow.clocks import SESSIONS, anchor  # noqa: E402
from shadow.detector import detect, fill_and_risk  # noqa: E402
from shadow.live_features import build_features  # noqa: E402
from shadow.schema import FEATURE_COLUMNS  # noqa: E402


class FrozenHistory:
    def __init__(self, panel: pd.DataFrame):
        self.panel = panel

    def opportunities(self) -> pd.DataFrame:
        return self.panel[["trade_key", "entry_time", "window"]].copy()

    def outcomes(self) -> pd.DataFrame:
        return self.panel[
            ["trade_key", "outcome_available", "fast_r", "runner_r"]
        ].copy()


def tick_slice(day: pd.Timestamp, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    path = REPO / f"data/ticks/XAUUSD/{day.date().isoformat()}.parquet"
    if not path.exists():
        return None
    ticks = pd.read_parquet(path)
    ticks["time_utc"] = pd.to_datetime(ticks["time_utc"], utc=True)
    return ticks.loc[(ticks["time_utc"] >= start) & (ticks["time_utc"] <= end)].reset_index(drop=True)


def scalar(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def main() -> None:
    m1 = load_m1(
        REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet",
        pd.Timestamp("2025-09-01T00:00:00Z"),
        pd.Timestamp("2026-01-16T00:00:00Z"),
    )
    entries = pd.read_parquet(
        REPO / "research/2026-10-20-trend-runner/frozen_entries_p1.parquet"
    ).reset_index(drop=True)
    entries["anchor"] = pd.to_datetime(entries["anchor"], utc=True)
    feature_panel = pd.read_parquet(
        REPO / "research/2026-10-20-trend-runner-r2/feature_panel.parquet"
    )
    history = FrozenHistory(feature_panel)
    maximum_errors = {name: 0.0 for name in FEATURE_COLUMNS}
    mismatches: list[dict[str, object]] = []
    emitted = 0
    truncation_checked = 0
    days = pd.date_range("2025-10-18", "2026-01-15", freq="D")
    for day in days:
        if day.dayofweek >= 5:
            continue
        for window in SESSIONS:
            at = anchor(day, window)
            expected = entries.loc[(entries["anchor"] == at) & (entries["window"] == window)]
            detection = detect(m1, at, window)
            fill = None
            if detection is not None:
                ticks = tick_slice(
                    detection.decision_time.floor("D"),
                    detection.decision_time,
                    detection.decision_time + pd.Timedelta(minutes=5),
                )
                fill = None if ticks is None else fill_and_risk(detection, ticks)
            if expected.empty:
                if fill is not None:
                    mismatches.append({"anchor": at.isoformat(), "window": window, "issue": "extra_entry"})
                continue
            expected_row = expected.iloc[0]
            if detection is None or fill is None:
                mismatches.append({"anchor": at.isoformat(), "window": window, "issue": "missing_entry"})
                continue
            emitted += 1
            actual = {**asdict(detection), **fill}
            compare = [
                "reference",
                "h1_atr",
                "side",
                "pivot_time",
                "pivot_price",
                "pivot_available",
                "pullback_ratio",
                "decision_time",
                "entry_atr",
                "entry_time",
                "entry",
                "spread",
                "stop",
                "risk",
                "risk_h1",
            ]
            for name in compare:
                left, right = actual[name], expected_row[name]
                equal = left == right if isinstance(left, pd.Timestamp) else np.isclose(left, right, atol=1e-12)
                if not equal:
                    mismatches.append(
                        {
                            "anchor": at.isoformat(),
                            "window": window,
                            "field": name,
                            "actual": scalar(left),
                            "expected": scalar(right),
                        }
                    )
            trade_key = f"P1-{int(expected_row.name):03d}"
            expected_features = feature_panel.loc[feature_panel["trade_key"] == trade_key].iloc[0]
            features = build_features(m1, detection, fill, history)  # type: ignore[arg-type]
            for name in FEATURE_COLUMNS:
                error = abs(features[name] - float(expected_features[name]))
                maximum_errors[name] = max(maximum_errors[name], error)
                if error > 1e-10:
                    mismatches.append(
                        {"trade_key": trade_key, "field": name, "absolute_error": error}
                    )
            if truncation_checked < 12:
                cutoff = at + pd.Timedelta(minutes={"ASIA": 120, "LONDON": 120, "NY0830": 240}[window])
                truncated = detect(m1.loc[m1.index < cutoff], at, window)
                if truncated != detection:
                    mismatches.append(
                        {"anchor": at.isoformat(), "window": window, "issue": "truncation_changed_detection"}
                    )
                truncation_checked += 1
    report = {
        "status": "PASS" if not mismatches and emitted == len(entries) else "FAIL",
        "period": "P1_ONLY_NO_EXAM",
        "expected_entries": len(entries),
        "emitted_entries": emitted,
        "anchors_checked": sum(day.dayofweek < 5 for day in days) * len(SESSIONS),
        "truncation_cases": truncation_checked,
        "feature_maximum_absolute_error": maximum_errors,
        "mismatches": mismatches[:50],
    }
    (ROOT / "ADAPTER_PARITY.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["status"] != "PASS":
        raise AssertionError(f"adapter parity failed: {mismatches[:5]}")


if __name__ == "__main__":
    main()
