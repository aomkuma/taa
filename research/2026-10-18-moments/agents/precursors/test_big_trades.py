"""big_trades.candidates by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_big_trades.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from big_trades import candidates  # noqa: E402


def test_the_pullback_inside_the_aligned_phase():
    # L1 aligned moments with M5_ema50 turned: -2, -1, 0, 1, 2 -> the 40th percentile is -0.4
    X = pd.DataFrame({"half": ["L1"] * 5 + ["L2", "L2", "L2"], "aligned": [True] * 5 + [True, True, False],
                      "D1_way20": [1, 1, 1, 1, 1, -1, -1, 1], "M5_ema50": [-2.0, -1.0, 0.0, 1.0, 2.0, 1.0, -1.0, -3.0],
                      "t": pd.date_range("2026-01-05 08:00", periods=8, freq="h", tz="UTC")})
    C = candidates(X)
    # L1: -2 and -1 are at / below -0.4; L2 down-way: 1.0 turned = -1.0 (a pullback up in a falling D1) yes, -1.0 turned = 1.0 no;
    # the last is not aligned
    assert C.M5_ema50.tolist() == [-2.0, -1.0, 1.0] and C.side.tolist() == [1, 1, -1]
