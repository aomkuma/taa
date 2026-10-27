# ruff: noqa: S101, E501, PT018
"""Hand-worked tests for the shadow bugs of 2026-10-22 (see 2026-10-21-trend-runner-retest-continuation/DEBUG_2026-10-22.md).

S1 - first valid pullback decides. Synthetic BUY: 15 h of warm-up M1 bars (high 101, low 99, close 100 -> every H1
true range 2.00, so H = 2.00 and the impulse distance 0.25 H = 0.50). Anchor 2025-11-05 00:00 (Asia), reference =
open of the anchor bar = 100.00. Bars after the anchor (high, low, close):

    0  100.50 99.90 100.40     1  101.00 100.40 100.90  <- impulse close 100.90 >= 100.50 (known 00:02)
    2  100.90 100.60 100.70    3  100.80 100.50 100.60  <- pivot A low 100.50: depth 0.50 / span 1.00 = 0.50
    4  100.85 100.70 100.80       A's continuation level = max high bars 2..4 = 100.90
    5  100.75 100.55 100.60    6  100.70 100.52 100.55  <- pivot B (ratio 0.48), level max high 5..7 = 100.75
    7  100.72 100.60 100.70    8  100.80 100.65 100.78  <- closes > 100.75 (B) but not > 100.90 (A)
    9.. 100.80 100.60 100.70 to the 120-minute deadline: A never continues -> no entry.

S2 - equal-time quotes keep file order in both tick loaders.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from shadow.adapter import load_ticks
from shadow.detector import detect
from shadow.outcome_adapter import load_outcome_ticks

ANCHOR = pd.Timestamp("2025-11-05 00:00", tz="UTC")
AFTER = [
    (100.50, 99.90, 100.40),
    (101.00, 100.40, 100.90),
    (100.90, 100.60, 100.70),
    (100.80, 100.50, 100.60),
    (100.85, 100.70, 100.80),
    (100.75, 100.55, 100.60),
    (100.70, 100.52, 100.55),
    (100.72, 100.60, 100.70),
    (100.80, 100.65, 100.78),
] + [(100.80, 100.60, 100.70)] * 125


def m1(after):
    warm = [(101.0, 99.0, 100.0)] * (15 * 60)
    rows = warm + list(after)
    frame = pd.DataFrame(rows, columns=["high", "low", "close"])
    frame["open"] = frame["close"]
    frame.loc[len(warm), "open"] = 100.00  # the anchor bar opens at the reference
    frame.index = pd.date_range(ANCHOR - pd.Timedelta(hours=15), periods=len(frame), freq="min", tz="UTC")
    return frame


def test_failed_first_pullback_gives_no_entry():
    assert detect(m1(AFTER), ANCHOR, "ASIA") is None


def test_first_pullback_that_continues_is_taken():
    after = list(AFTER)
    after[8] = (101.00, 100.65, 100.95)  # 100.95 > A's level 100.90
    d = detect(m1(after), ANCHOR, "ASIA")
    assert d is not None
    assert d.reference == 100.00 and d.h1_atr == 2.0 and d.side == 1
    assert d.pivot_time == ANCHOR + pd.Timedelta(minutes=3) and d.pivot_price == 100.50
    assert d.decision_time == ANCHOR + pd.Timedelta(minutes=9) and d.pullback_ratio == 0.5


def _ticks_file(root: Path) -> None:
    day = pd.Timestamp("2025-11-05", tz="UTC")
    pd.DataFrame(
        {
            "time_utc": [day + pd.Timedelta(seconds=s) for s in (5, 1, 1)],
            "bid": [3.0, 1.0, 2.0],
            "ask": [3.1, 1.1, 2.1],
        }
    ).to_parquet(root / "2025-11-05.parquet")


def test_adapter_ticks_keep_file_order(tmp_path):
    _ticks_file(tmp_path)
    day = pd.Timestamp("2025-11-05", tz="UTC")
    got = load_ticks(tmp_path, day, day + pd.Timedelta(seconds=10))
    assert list(got["bid"]) == [1.0, 2.0, 3.0]


def test_outcome_ticks_keep_file_order(tmp_path):
    _ticks_file(tmp_path)
    day = pd.Timestamp("2025-11-05", tz="UTC")
    got = load_outcome_ticks(tmp_path, day, day + pd.Timedelta(seconds=5))
    assert list(got["bid"]) == [1.0, 2.0, 3.0]


def test_impulse_at_exactly_a_quarter_h():
    # bar 0 closes 100.50 = reference + 0.25 x 2.00 -> the impulse is bar 0 (known 00:01), not bar 1
    after = list(AFTER)
    after[0] = (100.50, 99.90, 100.50)
    after[8] = (101.00, 100.65, 100.95)
    d = detect(m1(after), ANCHOR, "ASIA")
    assert d is not None and d.impulse_decision == ANCHOR + pd.Timedelta(minutes=1)
