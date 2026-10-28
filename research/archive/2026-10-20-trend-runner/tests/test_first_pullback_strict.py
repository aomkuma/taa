# ruff: noqa: S101, PT018, E501
"""Bug B1 (DEBUG_2026-10-22.md): the first valid pullback decides; a later pivot is never substituted.

Hand-worked BUY, reference 100.00, anchor 10:00, impulse known 10:02, deadline 30 minutes. M1 bars (high/low/close):

    bar  high    low     close
    0    100.50  99.90   100.40
    1    101.00  100.40  100.90   impulse extreme 101.00
    2    100.90  100.60  100.70
    3    100.80  100.50  100.60   pivot A low 100.50: depth 101.00-100.50 = 0.50 / span 1.00 = 0.50 (valid)
    4    100.85  100.70  100.80   A confirmed at 10:05; A's continuation level = max high bars 2..4 = 100.90
    5    100.75  100.55  100.60
    6    100.70  100.52  100.55   pivot B low 100.52: ratio 0.48 (valid); B's level = max high bars 5..7 = 100.75
    7    100.72  100.60  100.70
    8    100.80  100.65  100.78   closes > 100.75 (B's level) but not > 100.90 (A's level)
    9..  100.80  100.60  100.70   flat to the deadline: A never continues

The original code skipped A after its deadline scan and returned B's entry at 10:09 - a moment when A was still
pending (A's failure is known only at 10:30). The rule: no candidate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from tr1.bars import minute_bars
from tr1.opportunity import Impulse, find_first_pullback

ANCHOR = pd.Timestamp("2025-11-05 10:00", tz="UTC")
ROWS = [
    (100.50, 99.90, 100.40),
    (101.00, 100.40, 100.90),
    (100.90, 100.60, 100.70),
    (100.80, 100.50, 100.60),
    (100.85, 100.70, 100.80),
    (100.75, 100.55, 100.60),
    (100.70, 100.52, 100.55),
    (100.72, 100.60, 100.70),
    (100.80, 100.65, 100.78),
] + [(100.80, 100.60, 100.70)] * 31


def bars(rows):
    frame = pd.DataFrame(rows, columns=["high", "low", "close"])
    frame["open"] = frame["close"]
    frame["tick_volume"] = 1
    frame["spread"] = 3
    frame.index = pd.date_range(ANCHOR, periods=len(frame), freq="min", tz="UTC")
    return minute_bars(frame)


IMPULSE = Impulse(
    ANCHOR, 100.00, 2.0, 0.25, 1, ANCHOR + pd.Timedelta(minutes=2), ANCHOR + pd.Timedelta(minutes=1)
)


def search(rows):
    b = bars(rows)
    return find_first_pullback(
        b, IMPULSE, window="LONDON", timeframe="M1", deadline_minutes=30, entry_atr_values=np.ones(len(b))
    )


def test_failed_first_pullback_means_no_candidate():
    candidate, reasons = search(ROWS)
    assert candidate is None
    assert reasons["no_continuation"] == 1


def test_first_pullback_that_continues_is_taken():
    rows = list(ROWS)
    rows[8] = (101.00, 100.65, 100.95)  # closes 100.95 > A's level 100.90 at 10:09
    candidate, _ = search(rows)
    assert candidate is not None
    assert candidate.pivot_time == ANCHOR + pd.Timedelta(minutes=3)
    assert candidate.pivot_price == 100.50 and candidate.continuation_level == 100.90
    assert candidate.decision_time == ANCHOR + pd.Timedelta(minutes=9)
    assert candidate.pullback_ratio == 0.5
