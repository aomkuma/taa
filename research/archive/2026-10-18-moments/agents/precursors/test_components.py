"""components.way by hand: the first passage scored against the component's side.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_components.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from components import way  # noqa: E402


def test_way():
    assert way(1, 1) == 1.0 and way(-1, -1) == 1.0  # went the component's way
    assert way(1, -1) == 0.0 and way(-1, 1) == 0.0  # the other way
    assert np.isnan(way(0, 1)) and np.isnan(way(1, 0))  # unresolved, or no side to score
