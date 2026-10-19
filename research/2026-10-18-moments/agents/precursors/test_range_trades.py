"""range_trades.setups by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_range_trades.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from range_trades import setups  # noqa: E402


def test_fade_the_m30_edges_in_a_range():
    t = pd.DatetimeIndex(["2025-11-03 08:00", "2025-11-03 08:15", "2025-11-03 08:20", "2025-11-03 08:30", "2025-11-03 08:45", "2025-11-03 09:00"], tz="UTC")
    X = pd.DataFrame({"t": t, "M30_pos": [0.10, 0.90, 0.05, 0.50, 0.15, 0.95], "D1_er20": [0.10, 0.30, 0.10, 0.10, 0.30, 0.30],
                      "H4_er30": [0.50, 0.50, 0.50, 0.50, 0.05, 0.50]})
    S, side = setups(X, 0.1)
    assert side.tolist() == [1, -1, 1, 0, 1, -1]
    # 08:20 is not an M15 close; 08:30 is mid-range; 08:15 / 09:00 no range phase; 08:45 H4 sideways
    assert S["D1 back and forth"].tolist() == [True, False, False, False, False, False]
    assert S["H4 sideways"].tolist() == [False, False, False, False, True, False]
    assert S["outside the ranges"].tolist() == [False, True, False, False, False, True]
