"""DST-aware clock anchors for TREND-RUNNER."""

from __future__ import annotations

from enum import StrEnum

import pandas as pd


class Window(StrEnum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    NY0830 = "NY0830"


def anchor(local_day: str | pd.Timestamp, window: Window | str) -> pd.Timestamp:
    """Return the UTC anchor for the window's own local calendar day."""
    day = pd.Timestamp(local_day)
    if day.tzinfo is not None:
        raise ValueError("local_day must be a timezone-naive calendar day")
    day = day.normalize()
    selected = Window(window)
    if selected is Window.ASIA:
        local = (day + pd.Timedelta(hours=7)).tz_localize("Asia/Bangkok")
    elif selected is Window.LONDON:
        local = (day + pd.Timedelta(hours=13)).tz_localize("Asia/Bangkok")
    else:
        local = (day + pd.Timedelta(hours=8, minutes=30)).tz_localize(
            "America/New_York",
            ambiguous="raise",
            nonexistent="raise",
        )
    return local.tz_convert("UTC")
