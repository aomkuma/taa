# ruff: noqa: S101
from __future__ import annotations

import pandas as pd
import pytest
from tr1.boundaries import EXAM, P1, P2, DataBoundaryError, PeriodName, period_for, require_utc


def test_periods_are_half_open_and_contiguous() -> None:
    assert P1.end == P2.start
    assert P2.end == EXAM.start
    assert P1.contains(pd.Timestamp("2025-10-18", tz="UTC"))
    assert P1.contains(pd.Timestamp("2026-01-15 23:59:59", tz="UTC"))
    assert not P1.contains(P1.end)


def test_locked_periods_are_refused_by_default() -> None:
    assert period_for(PeriodName.P1) is P1
    with pytest.raises(DataBoundaryError, match="P2 is locked"):
        period_for(PeriodName.P2)
    with pytest.raises(DataBoundaryError, match="exam is locked"):
        period_for(PeriodName.EXAM)
    assert period_for(PeriodName.P2, allow_validation=True) is P2
    assert period_for(PeriodName.EXAM, allow_exam=True) is EXAM


def test_utc_is_required() -> None:
    assert require_utc(pd.Timestamp("2025-10-18", tz="UTC")) == P1.start
    with pytest.raises(DataBoundaryError):
        require_utc(pd.Timestamp("2025-10-18"))
    with pytest.raises(DataBoundaryError):
        require_utc(pd.Timestamp("2025-10-18", tz="Asia/Bangkok"))
