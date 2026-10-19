"""p3_paths by hand: the MFE / MAE of a trade's window and their minutes.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_p3_paths.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_paths as PP  # noqa: E402

S = 10**9
MN = 60 * S


def test_path_stats_buy():
    # in 100.0 (risk 2): bids 101 (1 min), 99 (2 min), 104 (3 min), 98.5 (4 min), 106 (6 min - after the limit of 5)
    t = np.array([0, 1, 2, 3, 4, 6], np.int64) * MN
    bid = np.array([100.0, 101.0, 99.0, 104.0, 98.5, 106.0])
    x = PP.path_stats(t, bid, bid + 0.2, 0, 100.0, 1, 2.0, 5 * MN)
    # the first tick at / after the limit counts (6 min): MFE 6 at minute 6; MAE 1.5 at minute 4
    assert (x["mfe"], x["mfe_r"], x["mfe_min"], x["mae"], x["mae_r"], x["mae_min"]) == (6.0, 3.0, 6.0, 1.5, 0.75, 4.0)
    x = PP.path_stats(t, bid, bid + 0.2, 0, 100.0, 1, 2.0, 4 * MN)  # up to 4 min
    assert (x["mfe"], x["mfe_min"], x["mae"], x["mae_min"]) == (4.0, 3.0, 1.5, 4.0)


def test_path_stats_sell_and_none():
    # a sell in 100.0, risk 2, read on the ask (bid + 0.2): asks 99.2 (1 min: 0.8 our way), 100.7 (2 min: 0.7 against)
    t = np.array([0, 1, 2], np.int64) * MN
    bid = np.array([100.0, 99.0, 100.5])
    x = PP.path_stats(t, bid, bid + 0.2, 0, 100.0, -1, 2.0, 10 * MN)
    assert x["mfe"] == pytest.approx(0.8) and x["mae"] == pytest.approx(0.7) and (x["mfe_min"], x["mae_min"]) == (1.0, 2.0)
    # never against: MAE 0, its minute NaN
    x = PP.path_stats(t, np.array([100.0, 101.0, 102.0]), np.array([100.2, 101.2, 102.2]), 0, 100.0, 1, 2.0, 10 * MN)
    assert x["mae"] == 0.0 and np.isnan(x["mae_min"]) and x["mfe"] == 2.0
    x = PP.path_stats(t[:1], bid[:1], bid[:1] + 0.2, 0, 100.0, 1, 2.0, 10 * MN)  # no tick after the fill
    assert x["mfe"] == 0.0 and np.isnan(x["mfe_min"])


def test_describe():
    G = pd.DataFrame(dict(R=[1.0, -1.0], mfe_r=[2.0, 0.5], mae_r=[0.2, 1.0], mfe_min=[3.0, 1.0], mae_min=[1.0, np.nan],
                          risk=[2.0, 4.0], height=[4.0, 6.0], atr=[2.0, 2.0]))
    d = PP.describe(G)
    assert (d["n"], d["R"], d["mfe_1r"], d["mfe_2r"], d["mae_1r"]) == (2, 0.0, 0.5, 0.5, 0.5)
    assert d["mfe_first"] == 0.5  # trade 1: MAE at 1 min before the MFE at 3; trade 2: MFE at 1, no MAE -> MFE first
    assert (d["mfe_r"], d["height"], d["risk"]) == (1.25, 5.0, 3.0)
