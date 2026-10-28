# ruff: noqa: S101
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from tr1.bars import confirmed_fractals, minute_bars
from tr1.structure import structure_events


def test_structure_event_uses_confirmation_atr_and_never_future_pivot() -> None:
    index = pd.date_range("2025-10-20", periods=5, freq="1min", tz="UTC")
    bars = minute_bars(
        pd.DataFrame(
            {
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [100.0, 99.0, 100.0, 98.0, 100.0],
                "close": [100.5] * 5,
            },
            index=index,
        )
    )
    pivots = confirmed_fractals(bars, radius=1)
    values = np.array([1.0, 1.0, 2.0, 2.0, 4.0])
    events = structure_events(
        bars,
        pivots,
        values,
        timeframe="M1",
        side=1,
        entry_time=pd.Timestamp("2025-10-20 00:00:30", tz="UTC"),
        entry_spread=0.1,
        end_time=pd.Timestamp("2025-10-20 00:04:00", tz="UTC"),
    )
    assert len(events) == 1
    assert events[0].pivot_time == pd.Timestamp("2025-10-20 00:01:00", tz="UTC")
    assert events[0].avail == pd.Timestamp("2025-10-20 00:03:00", tz="UTC")
    assert events[0].stop == pytest.approx(98.8)
