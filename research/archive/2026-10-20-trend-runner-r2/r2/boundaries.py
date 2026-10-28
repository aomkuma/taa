"""Hard research boundaries; callers cannot override the locked end."""

from __future__ import annotations

import pandas as pd

WARMUP_START = pd.Timestamp("2025-09-01T00:00:00Z")
DESIGN_START = pd.Timestamp("2025-10-18T00:00:00Z")
DESIGN_END = pd.Timestamp("2026-04-18T00:00:00Z")


def assert_before_exam(values: pd.Series | pd.DatetimeIndex, *, label: str) -> None:
    """Reject any timestamp at or beyond the locked exam boundary."""
    timestamps = pd.to_datetime(values, utc=True)
    if len(timestamps) and timestamps.max() >= DESIGN_END:
        raise ValueError(f"{label} reaches locked exam boundary: {timestamps.max()}")
