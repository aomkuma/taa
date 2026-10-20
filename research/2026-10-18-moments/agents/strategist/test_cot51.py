"""Hand-worked tests of the row-51 release-lag alignment (cot51.py)."""

import numpy as np
import pandas as pd
import pytest

import cot51 as C

H = C.holidays()


def test_normal_friday_release_1530_new_york():
    # report Tue 2024-03-12 -> Fri 2024-03-15 15:30 New York (EDT, UTC-4) = 19:30 UTC
    assert C.publish_time(pd.Timestamp("2024-03-12"), H) == pd.Timestamp("2024-03-15 19:30", tz="UTC")
    # winter: report Tue 2024-01-16 -> Fri 2024-01-19 15:30 EST (UTC-5) = 20:30 UTC
    assert C.publish_time(pd.Timestamp("2024-01-16"), H) == pd.Timestamp("2024-01-19 20:30", tz="UTC")


def test_holiday_week_moves_to_monday():
    # Thanksgiving Thu 2024-11-28: report Tue 2024-11-26 -> Mon 2024-12-02 15:30 EST = 20:30 UTC
    assert C.publish_time(pd.Timestamp("2024-11-26"), H) == pd.Timestamp("2024-12-02 20:30", tz="UTC")
    # Juneteenth Fri 2026-06-19: report Tue 2026-06-16 -> Mon 2026-06-22 (as the CFTC 2026 schedule shows)
    assert C.publish_time(pd.Timestamp("2026-06-16"), H) == pd.Timestamp("2026-06-22 19:30", tz="UTC")


def test_shutdown_table_overrides():
    # 2025-09-30 report -> 2025-11-19 15:30 EST = 20:30 UTC; 2025-12-16 -> 2026-01-06
    assert C.publish_time(pd.Timestamp("2025-09-30"), H) == pd.Timestamp("2025-11-19 20:30", tz="UTC")
    assert C.publish_time(pd.Timestamp("2025-12-16"), H) == pd.Timestamp("2026-01-06 20:30", tz="UTC")


def test_known_at_uses_only_published_reports():
    pub = np.array([100, 200, 300])
    v = np.array([1.0, 2.0, 3.0])
    assert np.isnan(C.known_at(pub, v, 99))  # nothing published yet
    assert C.known_at(pub, v, 200) == 2.0  # published at exactly t -> known
    assert C.known_at(pub, v, 299) == 2.0  # the next one not yet
    assert C.known_at(pub, v, 10**6) == 3.0


def test_pct_last():
    x = np.array([5.0, 1.0, 3.0, 4.0])
    # i = 3, n = 4: values <= 4 are 1, 3, 4 -> 3 of 4; min_n 2
    assert C.pct_last(x, 3, n=4, min_n=2) == pytest.approx(0.75)
    # n = 2: [3, 4] -> 2 of 2
    assert C.pct_last(x, 3, n=2, min_n=2) == pytest.approx(1.0)
    assert np.isnan(C.pct_last(x, 0, n=4, min_n=2))
