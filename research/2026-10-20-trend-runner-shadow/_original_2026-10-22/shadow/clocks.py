"""Frozen DST-aware session clocks for the one-way adapter."""

from __future__ import annotations

import pandas as pd

SESSIONS = ("ASIA", "LONDON", "NY0830")
DEADLINE_MINUTES = {"ASIA": 120, "LONDON": 120, "NY0830": 240}


def anchor(local_day: str | pd.Timestamp, window: str) -> pd.Timestamp:
    day = pd.Timestamp(local_day)
    if day.tzinfo is not None:
        raise ValueError("local_day must be timezone-naive")
    day = day.normalize()
    if window == "ASIA":
        local = (day + pd.Timedelta(hours=7)).tz_localize("Asia/Bangkok")
    elif window == "LONDON":
        local = (day + pd.Timedelta(hours=13)).tz_localize("Asia/Bangkok")
    elif window == "NY0830":
        local = (day + pd.Timedelta(hours=8, minutes=30)).tz_localize(
            "America/New_York", ambiguous="raise", nonexistent="raise"
        )
    else:
        raise ValueError(f"unknown session: {window}")
    return local.tz_convert("UTC")
