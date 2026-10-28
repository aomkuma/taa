"""Frozen TR4 MTF ATR gate. No strategy, broker, or order integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Iterable


UPPER_PERCENTILE = 0.80
LOWER_PERCENTILE = 0.70
ATR_COLUMNS = ("atr_m15_pct", "atr_m30_pct", "atr_h1_pct")
AVAILABLE_COLUMNS = ("atr_m15_available_at", "atr_m30_available_at", "atr_h1_available_at")


@dataclass(frozen=True)
class GateDecision:
    trade_key: str
    decision_time: datetime
    parent_action: str
    tr4_action: str
    composite_percentile: float
    paused: bool
    transition: str


def _utc(value: object, name: str) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ValueError(f"{name} must be an ISO timestamp or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"{name} must be timezone-aware UTC")
    return parsed


def apply_gate(rows: Iterable[dict[str, object]]) -> list[GateDecision]:
    """Apply the locked stateful gate to chronological, causal opportunity rows.

    Each row requires trade_key, decision_time, parent_action, the three ATR
    percentiles, and each percentile's `*_available_at` timestamp. The caller
    must supply already-built ATR features; this function rejects lookahead.
    """
    result: list[GateDecision] = []
    paused = False
    previous_time: datetime | None = None
    seen_keys: set[str] = set()

    for row in rows:
        key = str(row["trade_key"])
        if not key or key in seen_keys:
            raise ValueError("trade_key must be non-empty and unique")
        seen_keys.add(key)
        decision_time = _utc(row["decision_time"], "decision_time")
        if previous_time is not None and decision_time < previous_time:
            raise ValueError("rows must be in nondecreasing decision_time order")
        previous_time = decision_time

        parent_action = str(row["parent_action"])
        if parent_action not in {"RUNNER", "SKIP"}:
            raise ValueError("parent_action must be frozen TR3 RUNNER or SKIP")

        percentiles: list[float] = []
        for feature_name, available_name in zip(ATR_COLUMNS, AVAILABLE_COLUMNS, strict=True):
            available_at = _utc(row[available_name], available_name)
            if available_at > decision_time:
                raise ValueError(f"{feature_name} is not available by decision_time")
            value = float(row[feature_name])
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{feature_name} must be a finite percentile in [0, 1]")
            percentiles.append(value)

        composite = sorted(percentiles)[1]
        transition = "NONE"
        if not paused and composite > UPPER_PERCENTILE:
            paused = True
            transition = "PAUSE"
        elif paused and composite <= LOWER_PERCENTILE:
            paused = False
            transition = "RESUME"

        action = "SKIP" if paused and parent_action == "RUNNER" else parent_action
        result.append(
            GateDecision(
                trade_key=key,
                decision_time=decision_time,
                parent_action=parent_action,
                tr4_action=action,
                composite_percentile=composite,
                paused=paused,
                transition=transition,
            )
        )
    return result
