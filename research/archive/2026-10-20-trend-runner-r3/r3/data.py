"""Immutable verified input for TR3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "2026-10-20-trend-runner-r2"
END_EXCLUSIVE = pd.Timestamp("2026-04-18T00:00:00Z")

FEATURE_COLUMNS = [
    "h1_flow_6_atr",
    "h4_flow_3_atr",
    "open_space_atr",
    "h1_atr_percentile_120",
    "risk_h1_feature",
    "pullback_ratio_feature",
    "anchor_entry_minutes",
    "side_feature",
    "session_asia",
    "session_london",
    "prior_session_runner_edge",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_inputs() -> dict[str, str]:
    expected: dict[str, str] = json.loads((ROOT / "provenance.json").read_text(encoding="utf-8"))["sha256"]
    actual = {name: sha256(SOURCE / name) for name in expected}
    mismatches = {name: (expected[name], actual[name]) for name in expected if actual[name] != expected[name]}
    if mismatches:
        raise ValueError(f"TR3 immutable input mismatch: {mismatches}")
    verification = json.loads((SOURCE / "feature_verification.json").read_text(encoding="utf-8"))
    if verification["status"] != "PASS" or verification["exam_read"]:
        raise ValueError("TR2 feature panel is not verified and exam-safe")
    return actual


def load_panel() -> pd.DataFrame:
    verify_inputs()
    panel = pd.read_parquet(SOURCE / "feature_panel.parquet")
    for column in ("entry_time", "runner_exit_time"):
        panel[column] = pd.to_datetime(panel[column], utc=True)
    if len(panel) != 280 or panel["trade_key"].duplicated().any():
        raise ValueError("TR3 requires exactly 280 unique frozen entries")
    if panel["entry_time"].max() >= END_EXCLUSIVE:
        raise ValueError("Panel crosses the locked exam boundary")
    if panel[FEATURE_COLUMNS].isna().any().any():
        raise ValueError("Verified feature vector is incomplete")
    return panel.sort_values(["entry_time", "trade_key"]).reset_index(drop=True)
