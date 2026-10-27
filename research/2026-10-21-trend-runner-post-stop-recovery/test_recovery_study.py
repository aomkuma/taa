import pandas as pd

from recovery_study import make_m5, simulate_reentry


def test_m5_drops_incomplete_candles() -> None:
    times = pd.date_range("2024-01-01", periods=9, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {"open": range(9), "high": range(1, 10), "low": range(9),
         "close": range(1, 10), "spread": [1] * 9}, index=times
    )
    m5 = make_m5(bars)
    assert len(m5) == 1
    assert int(m5.iloc[0]["count"]) == 5


def test_reentry_resolves_same_m1_stop_target_collision_against_trade() -> None:
    start = pd.Timestamp("2024-01-01", tz="UTC")
    bars = pd.DataFrame(
        {"open": [100.0], "high": [102.5], "low": [98.5], "close": [100.0], "spread": [0]},
        index=pd.DatetimeIndex([start]),
    )
    result = simulate_reentry(
        None, bars, side=1, entry_time=start, entry_price=100.0, risk=1.0, stop_multiple=1.0
    )
    assert result["complete"] is True
    assert result["exit_reason"] == "STOP_INTRABAR"
    assert result["r"] == -1.0


def test_reentry_fills_fixed_two_r_target() -> None:
    start = pd.Timestamp("2024-01-01", tz="UTC")
    bars = pd.DataFrame(
        {"open": [100.0], "high": [102.1], "low": [99.5], "close": [102.0], "spread": [0]},
        index=pd.DatetimeIndex([start]),
    )
    result = simulate_reentry(
        None, bars, side=1, entry_time=start, entry_price=100.0, risk=1.0, stop_multiple=1.0
    )
    assert result["complete"] is True
    assert result["exit_reason"] == "TARGET_2R"
    assert result["r"] == 2.0
