"""The M1-approximation walk-forward is retired (2026-10-22, DEBUG_2026-10-22.md B5/B6): it must refuse."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walkforward import m1_fill, main, simulate_m1_exit


def test_m1_fill_refuses():
    with pytest.raises(RuntimeError, match="Retired"):
        m1_fill(pd.DataFrame(), pd.Timestamp("2024-01-01", tz="UTC"), 1)


def test_m1_exit_refuses():
    with pytest.raises(RuntimeError, match="Retired"):
        simulate_m1_exit(pd.DataFrame(), pd.Series(dtype=float), "SPLIT", [])


def test_main_refuses():
    with pytest.raises(SystemExit, match="Retired"):
        main()
