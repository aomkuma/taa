# ruff: noqa: S101
"""Hand-worked tests of the journal fields (2026-10-22)."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest
from journal_fields import LIQ_DIR, Context, _pools_fn, path_excursions, thai, thai_week


def test_thai_time_is_utc_plus_7():
    assert thai(pd.Timestamp("2025-11-03 18:30", tz="UTC")) == "2025-11-04 01:30:00"


def test_thai_week_uses_the_thai_date():
    # Sunday 2025-11-02 18:00 UTC is Monday 01:00 Thai -> ISO week 45, Monday 2025-11-03
    assert thai_week(pd.Timestamp("2025-11-02 18:00", tz="UTC")) == "2025-W45 (Mon 2025-11-03)"
    # Sunday 2025-11-02 16:59 UTC is still Sunday 23:59 Thai -> week 44
    assert thai_week(pd.Timestamp("2025-11-02 16:59", tz="UTC")) == "2025-W44 (Mon 2025-10-27)"


def test_atr_uses_only_bars_closed_by_the_moment():
    ctx = object.__new__(Context)
    opens = pd.date_range("2025-11-03 00:00", periods=3, freq="h", tz="UTC")
    bars = pd.DataFrame({"close_time": opens + pd.Timedelta(hours=1), "atr": [1.0, 2.0, 3.0]}, index=opens)
    ctx.atr = {"H1": bars}
    # at 02:00 the bar 01:00-02:00 has just closed (2.0); the 02:00 bar (3.0) is still forming
    assert ctx.atr_at("H1", pd.Timestamp("2025-11-03 02:00", tz="UTC")) == 2.0
    assert ctx.atr_at("H1", pd.Timestamp("2025-11-03 01:59", tz="UTC")) == 1.0
    assert np.isnan(ctx.atr_at("H1", pd.Timestamp("2025-11-03 00:30", tz="UTC")))


def test_excursions_buy_and_sell():
    t = pd.Timestamp("2025-11-03 10:00", tz="UTC")
    q = pd.DataFrame(
        {
            "time_utc": [
                t,
                t + pd.Timedelta(minutes=1),
                t + pd.Timedelta(minutes=2),
                t + pd.Timedelta(minutes=3),
            ],
            "bid": [99.9, 101.0, 99.5, 103.0],
            "ask": [100.0, 101.1, 99.6, 103.1],
        }
    )
    # BUY 100.0, 1R 1.0, exit at minute 2: bids 99.9 / 101.0 / 99.5 -> MFE +1.0, MAE -0.5 (minute 3 excluded)
    assert path_excursions(q, 1, 100.0, 1.0, t + pd.Timedelta(minutes=2)) == (
        pytest.approx(1.0),
        pytest.approx(-0.5),
    )
    # SELL 100.0, 1R 0.5, exit at minute 2: asks 100.0 / 101.1 / 99.6 -> MFE (100-99.6)/0.5 = 0.8, MAE -2.2
    assert path_excursions(q, -1, 100.0, 0.5, t + pd.Timedelta(minutes=2)) == (
        pytest.approx(0.8),
        pytest.approx(-2.2),
    )


def test_pools_are_the_liq_journal_function_itself():
    fn = _pools_fn()
    assert str(LIQ_DIR) in sys.path
    import liq_journal

    assert fn is liq_journal.pools
