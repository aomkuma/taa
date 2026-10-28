"""m15_trades.part_of and m15_trades.entries by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_m15_trades.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_trades import entries, part_of  # noqa: E402


def test_parts():
    t = pd.DatetimeIndex(["2025-10-17 23:59", "2025-10-18 00:00", "2026-01-15 23:55", "2026-01-16 00:00", "2026-04-18 00:00"], tz="UTC")
    assert part_of(t).tolist() == ["", "P1", "P1", "P2", "exam"]


def test_entries_only_at_m15_closes():
    t = pd.DatetimeIndex(["2025-11-03 08:00", "2025-11-03 08:05", "2025-11-03 08:15", "2025-11-03 08:30", "2025-11-03 08:45"], tz="UTC")
    X = pd.DataFrame({"t": t, "aligned": [True, True, True, False, True], "D1_way20": [1, 1, 1, 1, -1],
                      "M5_ema50": [-2.0, -2.0, 1.0, -2.0, 2.0], "part": ["P1"] * 5})
    E = entries(X)
    # 08:05 is not an M15 close; 08:30 not aligned
    assert E["A aligned"].tolist() == [True, False, True, False, True]
    # the pullback cut: P1 aligned M15 values turned -2, 1, -2 (08:45 down: 2 x -1) -> 40th percentile -2 -> -2, -2 kept
    assert E["B aligned + M5 pullback"].tolist() == [True, False, False, False, True]
