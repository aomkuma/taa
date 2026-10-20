"""Audit 7: the parts, the owner's windows (Thai clock) and the event times through the DST changes, by hand.

dev/p4_trades.py::window_of is imported read only. Thai time = UTC+7 all year. New York: EDT (UTC-4) 2025-03-09 ..
2025-11-02 and from 2026-03-08; EST (UTC-5) between. London: BST (UTC+1) until 2025-10-26 and from 2026-03-29.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

AG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AG / "precursors"))
sys.path.insert(0, str(AG / "dev"))
import footprints  # noqa: E402
import m15_trades  # noqa: E402
import plib  # noqa: E402
import pullback15  # noqa: E402
from p4_trades import window_of  # noqa: E402


def ns(s: str) -> int:
    return pd.Timestamp(s, tz="UTC").value


@pytest.mark.parametrize(
    ("utc", "want", "why"),
    [
        ("2026-01-14 00:00", "Asia", "07:00 Thai"),
        ("2026-01-14 01:59:59", "Asia", "08:59:59 Thai"),
        ("2026-01-14 02:00", None, "09:00 Thai: the end is excluded"),
        ("2025-12-31 23:59", None, "06:59 Thai"),
        ("2026-01-14 06:00", "London", "13:00 Thai (London's own clock is 06:00 GMT)"),
        ("2026-01-14 06:59", "London", "13:59 Thai"),
        ("2026-01-14 07:00", None, "14:00 Thai"),
        ("2025-10-20 06:00", "London", "13:00 Thai in London summer time too (07:00 BST)"),
        ("2026-01-14 14:30", "NY", "09:30 EST"),
        ("2026-01-14 14:29", None, "09:29 EST"),
        ("2026-01-14 16:29", "NY", "11:29 EST"),
        ("2026-01-14 16:30", None, "11:30 EST: the end is excluded"),
        ("2025-10-20 13:30", "NY", "09:30 EDT"),
        ("2025-10-31 13:30", "NY", "09:30 EDT in the week Europe is already on winter time"),
        ("2025-11-03 13:30", None, "08:30 EST after the US change"),
        ("2025-11-03 14:30", "NY", "09:30 EST"),
        ("2026-03-10 13:30", "NY", "09:30 EDT in the week Europe is still on winter time"),
        ("2026-03-06 13:30", None, "08:30 EST before the US change"),
    ],
)
def test_the_owners_windows(utc: str, want: str | None, why: str) -> None:
    assert window_of(ns(utc)) == want, why


def test_the_london_pad() -> None:
    assert window_of(ns("2026-01-14 05:30"), 30) == "London" and window_of(ns("2026-01-14 05:29"), 30) is None
    assert window_of(ns("2026-01-14 07:29"), 30) == "London" and window_of(ns("2026-01-14 07:30"), 30) is None


def test_the_event_minutes_follow_each_zone() -> None:
    t = pd.DatetimeIndex(
        ["2026-03-06 14:30", "2026-03-10 13:30", "2026-03-10 15:00", "2026-03-30 14:00", "2025-10-31 12:30",
         "2025-11-03 13:20"], tz="UTC"
    )
    ny_open = footprints.event_minutes(t, "America/New_York", 570)
    fix = footprints.event_minutes(t, "Europe/London", 900)
    data = footprints.event_minutes(t, "America/New_York", 510)
    comex = footprints.event_minutes(t, "America/New_York", 500)
    assert ny_open[0] == 0 and ny_open[1] == 0  # 09:30 EST, then 09:30 EDT in the mismatch week
    assert fix[2] == 0 and fix[3] == 0  # 15:00 GMT (London winter time until 2026-03-29), 15:00 BST after it
    assert data[4] == 0 and comex[5] == 0  # 08:30 EDT on 2025-10-31; 08:20 EST on 2025-11-03


def test_pullback15_active_hours_follow_each_zone() -> None:
    t = pd.DatetimeIndex(["2026-03-10 14:30", "2026-03-10 16:00", "2026-03-10 16:01", "2026-03-06 15:30",
                          "2026-03-06 16:01", "2026-03-30 15:00", "2026-03-30 15:01", "2026-03-10 09:00"], tz="UTC")
    # 2026-03-10 (New York EDT, London still GMT): the NY open 13:30 UTC, the fix 15:00 UTC -> 14:30 in; 16:00 is 60
    # after the fix (in), 16:01 is 61 (out). 2026-03-06 (EST, GMT): the NY open 14:30 UTC -> 15:30 in; 16:01 is 91
    # after it and 61 after the 15:00 fix (out). 2026-03-30 (EDT, BST): the fix 14:00 UTC, the NY open 13:30 UTC ->
    # 15:00 is 60 after the fix (in), 15:01 out. 09:00 UTC is near no event (out).
    assert pullback15.active(t, 60).tolist() == [True, True, False, True, False, True, False, False]


def test_ny_mask_is_dst_aware() -> None:
    # the owner's NY windows in plib.WINDOWS start 07:55 New York (NY19): 11:55 UTC in summer, 12:55 UTC in winter
    t = pd.DatetimeIndex(["2026-03-10 11:55", "2026-03-10 11:54", "2026-01-14 12:55", "2026-01-14 12:54"], tz="UTC")
    assert plib.ny_mask(t).tolist() == [True, False, True, False]


def test_the_parts() -> None:
    t = pd.DatetimeIndex(["2025-10-17 23:59", "2025-10-18 00:00", "2026-01-15 23:59", "2026-01-16 00:00",
                          "2026-04-17 23:59", "2026-04-18 00:00", "2026-10-16 23:59", "2026-10-17 00:00"], tz="UTC")
    assert m15_trades.part_of(t).tolist() == ["", "P1", "P1", "P2", "P2", "exam", "exam", ""]
    assert np.array_equal(
        [plib.LEARN_START, plib.EXAM_START, plib.EXAM_END],
        [pd.Timestamp(m15_trades.PARTS["P1"][0], tz="UTC"), pd.Timestamp(m15_trades.PARTS["exam"][0], tz="UTC"),
         pd.Timestamp(m15_trades.PARTS["exam"][1], tz="UTC")],
    )
