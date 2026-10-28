import pandas as pd
import numpy as np

from build_trade_journal import _first_touch, _path_metrics


def test_first_touch_marks_same_m1_bar_order_ambiguous() -> None:
    times = pd.date_range("2024-01-01", periods=2, freq="min", tz="UTC")
    label, minutes = _first_touch(
        favorable_r=np.array([0.2, 1.2]), adverse_r=np.array([-0.1, -1.1]), times=times, start=times[0]
    )
    assert label == "SAME_M1_BAR_AMBIGUOUS"
    assert minutes == 1.0


def test_first_touch_uses_first_completed_m1_threshold() -> None:
    times = pd.date_range("2024-01-01", periods=3, freq="min", tz="UTC")
    label, minutes = _first_touch(
        favorable_r=np.array([0.2, 1.1, 1.4]), adverse_r=np.array([-0.1, -0.2, -1.1]),
        times=times, start=times[0]
    )
    assert label == "+1R_FIRST"
    assert minutes == 1.0


def test_sell_path_marks_spread_adjusted_ask_for_excursions() -> None:
    bars = pd.DataFrame({"high": [101.0], "low": [99.0], "spread": [10]})
    favorable, adverse, _, _ = _path_metrics(bars, side=-1, entry=100.0, risk=1.0)
    assert round(float(favorable[0]), 6) == 0.9
    assert round(float(adverse[0]), 6) == -1.1
