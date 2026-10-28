"""Causal structure-stop events for TREND-RUNNER exits."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tr1.exits import StructureEvent


def structure_events(
    bars: pd.DataFrame,
    pivots: pd.DataFrame,
    atr_values: np.ndarray,
    *,
    timeframe: str,
    side: int,
    entry_time: pd.Timestamp,
    entry_spread: float,
    end_time: pd.Timestamp,
) -> list[StructureEvent]:
    """Convert confirmed post-entry pivots into buffered stop events."""
    if side not in (-1, 1):
        raise ValueError("side must be -1 or 1")
    if entry_spread < 0:
        raise ValueError("entry spread must be non-negative")
    if len(atr_values) != len(bars):
        raise ValueError("ATR values must align with bars")
    entry_time = pd.Timestamp(entry_time)
    end_time = pd.Timestamp(end_time)
    kind = "low" if side > 0 else "high"
    eligible = pivots.loc[
        (pivots["kind"] == kind)
        & (pivots["pivot_time"] >= entry_time)
        & (pivots["avail"] >= entry_time)
        & (pivots["avail"] <= end_time)
    ]
    events: list[StructureEvent] = []
    for pivot in eligible.itertuples(index=False):
        confirm = int(pivot.confirm)
        value = float(atr_values[confirm])
        if not np.isfinite(value) or value <= 0:
            continue
        buffer = max(entry_spread, 0.10 * value)
        price = float(pivot.price)
        stop = price - buffer if side > 0 else price + buffer
        events.append(
            StructureEvent(
                pd.Timestamp(pivot.avail),
                timeframe,
                pd.Timestamp(pivot.pivot_time),
                price,
                float(stop),
            )
        )
    return events
