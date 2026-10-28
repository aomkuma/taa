"""f1_components.spaced by hand: one row per gap.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_f1_components.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f1_components import spaced  # noqa: E402

MIN = 60_000_000_000


def test_spaced_keeps_one_row_per_gap():
    t = np.array([0, 1, 14, 15, 16, 31, 45]) * MIN
    assert spaced(t, 15).tolist() == [True, False, False, True, False, True, False]  # 0, 15, 31 (45 is 14 after 31)
    assert spaced(np.array([], np.int64), 15).tolist() == []
