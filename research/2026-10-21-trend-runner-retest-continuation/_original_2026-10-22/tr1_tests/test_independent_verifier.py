# ruff: noqa: S101
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]


def test_independent_verifier_does_not_import_producer_modules() -> None:
    source = (HERE / "verify_opportunities.py").read_text(encoding="utf-8")
    assert "from tr1.opportunity import" not in source
    assert "from tr1.simulation import" not in source


def test_independent_atr_has_no_current_or_future_close_dependency() -> None:
    from verify_opportunities import atr_independently

    index = pd.date_range("2025-10-20", periods=20, freq="1h", tz="UTC")
    close = np.arange(100.0, 120.0)
    bars = pd.DataFrame({"high": close + 1, "low": close - 1, "close": close}, index=index)
    before = atr_independently(bars)
    changed = bars.copy()
    changed.iloc[-1] = [1000.0, 0.0, 500.0]
    after = atr_independently(changed)
    np.testing.assert_allclose(before[:-1], after[:-1], equal_nan=True)
