# ruff: noqa: S101
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit import path_metrics, removal_stress, sha256  # noqa: E402


def test_path_metrics_preserve_order() -> None:
    values = np.array([2.0, -1.0, -2.0, 1.0, 3.0])
    metrics = path_metrics(values)
    assert metrics["max_drawdown_r"] == 3.0
    assert metrics["maximum_losing_streak"] == 2
    assert metrics["longest_underwater_trades"] == 3
    assert metrics["terminal_underwater_trades"] == 0


def test_best_trade_removal_is_without_replacement() -> None:
    result = removal_stress(np.array([-2.0, 1.0, 4.0, 3.0]))
    assert list(result["remaining_total_r"][:4]) == [6.0, 2.0, -1.0, -2.0]


def test_generated_result_reconciles_frozen_input_and_excludes_slippage() -> None:
    result = json.loads((ROOT / "RESULTS.json").read_text(encoding="utf-8"))
    source = ROOT.parent / "2026-10-20-trend-runner-r3/predictions_primary.parquet"
    assert result["input_sha256"] == sha256(source)
    assert all(result["reconciliation"].values())
    assert result["hypothetical_slippage_stress"] == "EXCLUDED_BY_USER"
    assert "cost_stress" not in result
    assert result["verdict"] == "FRAGILE_POSITIVE"
