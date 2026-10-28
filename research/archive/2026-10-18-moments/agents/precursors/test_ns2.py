"""Hand tests of ns2.k_at: the ATR of the last H1 bar closed by t0, whatever the index's time unit."""

import pandas as pd

import ns2


def test_k_reads_the_bar_closed_by_t0_in_any_unit():
    idx = pd.DatetimeIndex(["2023-08-10 11:00", "2023-08-10 12:00", "2023-08-10 13:00"], tz="UTC").as_unit("us")
    atr = pd.Series([16.33, 32.66, 99.0], index=idx)  # values by close time
    t0 = pd.Timestamp("2023-08-10 12:30", tz="UTC").value  # ns
    assert ns2.k_at(atr, t0) == 2.0  # the bar closed at 12:00, not the one closing at 13:00
    t1 = pd.Timestamp("2023-08-10 12:00", tz="UTC").value
    assert ns2.k_at(atr, t1) == 2.0  # closed exactly at t0 counts
    assert ns2.k_at(atr, t1 - 1) == 1.0
