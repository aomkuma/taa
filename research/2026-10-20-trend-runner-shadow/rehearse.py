"""Synthetic end-to-end rehearsal; no real forward evidence is retained."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from shadow.journal import ShadowJournal  # noqa: E402
from shadow.report import build_report  # noqa: E402
from shadow.schema import FEATURE_COLUMNS, Opportunity, Outcome  # noqa: E402
from shadow.service import score_opportunity  # noqa: E402


def opportunity(key: str, timestamp: pd.Timestamp, side: int) -> Opportunity:
    window = "ASIA" if timestamp.hour < 6 else "LONDON"
    features = {name: 0.1 for name in FEATURE_COLUMNS}
    features.update(
        {
            "side_feature": float(side),
            "session_asia": float(window == "ASIA"),
            "session_london": float(window == "LONDON"),
        }
    )
    return Opportunity.from_dict(
        {
            "trade_key": key,
            "entry_time": timestamp.isoformat(),
            "anchor": (timestamp - pd.Timedelta(minutes=30)).isoformat(),
            "window": window,
            "side": side,
            "entry": 2000.0,
            "spread": 0.2,
            "stop": 2000.0 - side * 5.0,
            "risk": 5.0,
            "features": features,
        }
    )


def outcome(key: str, timestamp: pd.Timestamp, value: float) -> Outcome:
    return Outcome.from_dict(
        {
            "trade_key": key,
            "fast_exit_time": (timestamp - pd.Timedelta(minutes=30)).isoformat(),
            "runner_exit_time": timestamp.isoformat(),
            "fast_r": min(value, 2.0),
            "runner_r": value,
            "fast_usd_fixed_001": min(value, 2.0) * 5.0,
            "runner_usd_fixed_001": value * 5.0,
        }
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="tr_shadow_rehearsal_") as temporary:
        journal = ShadowJournal(Path(temporary) / "journal.sqlite")
        journal.initialize()
        start = pd.Timestamp("2026-11-02T00:30:00Z")
        for index in range(60):
            timestamp = start + pd.Timedelta(days=index)
            key = f"SYN-{index:03d}"
            journal.record_opportunity(opportunity(key, timestamp, 1 if index % 2 == 0 else -1))
            score_opportunity(journal, key)
            value = ((index % 7) - 2) / 3
            journal.record_outcome(outcome(key, timestamp + pd.Timedelta(hours=2), value))
        target_time = pd.Timestamp("2027-01-02T12:00:00Z")
        journal.record_opportunity(opportunity("SYN-TARGET", target_time, 1))
        score_opportunity(journal, "SYN-TARGET")
        decisions = journal.decisions().loc[lambda frame: frame["trade_key"] == "SYN-TARGET"]
        if len(decisions) != 3 or set(decisions["status"]) != {"SCORED"}:
            raise AssertionError("synthetic target was not scored by all policies")
        report = build_report(journal)
        result = {
            "status": "PASS",
            "synthetic_only": True,
            "training_opportunities": 60,
            "target_decisions": decisions[
                ["policy", "status", "action", "reason", "model_month", "model_hash"]
            ].to_dict(orient="records"),
            "journal_status": report,
            "real_forward_rows_written": 0,
        }
    (ROOT / "REHEARSAL.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
