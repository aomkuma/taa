"""Hard data boundaries for TREND-RUNNER research."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd


class DataBoundaryError(RuntimeError):
    """Raised before a command can read a locked research period."""


class PeriodName(StrEnum):
    P1 = "P1"
    P2 = "P2"
    EXAM = "EXAM"


@dataclass(frozen=True)
class Period:
    """A half-open UTC period."""

    name: PeriodName
    start: pd.Timestamp
    end: pd.Timestamp

    def contains(self, value: pd.Timestamp) -> bool:
        value = require_utc(value)
        return self.start <= value < self.end


P1 = Period(
    PeriodName.P1,
    pd.Timestamp("2025-10-18", tz="UTC"),
    pd.Timestamp("2026-01-16", tz="UTC"),
)
P2 = Period(
    PeriodName.P2,
    pd.Timestamp("2026-01-16", tz="UTC"),
    pd.Timestamp("2026-04-18", tz="UTC"),
)
EXAM = Period(
    PeriodName.EXAM,
    pd.Timestamp("2026-04-18", tz="UTC"),
    pd.Timestamp("2026-10-18", tz="UTC"),
)


def require_utc(value: pd.Timestamp) -> pd.Timestamp:
    """Return a UTC timestamp and reject naive or non-UTC inputs."""
    value = pd.Timestamp(value)
    if value.tzinfo is None or str(value.tz) != "UTC":
        raise DataBoundaryError(f"a timezone-aware UTC timestamp is required, got {value!r}")
    return value


def period_for(
    name: PeriodName | str,
    *,
    allow_validation: bool = False,
    allow_exam: bool = False,
) -> Period:
    """Return an enabled period; locked periods fail before a data reader is called."""
    selected = PeriodName(name)
    if selected is PeriodName.P1:
        return P1
    if selected is PeriodName.P2:
        if not allow_validation:
            raise DataBoundaryError("P2 is locked until round 1 is frozen")
        return P2
    if not allow_exam:
        raise DataBoundaryError("the exam is locked until the pre-exam gate passes")
    return EXAM
