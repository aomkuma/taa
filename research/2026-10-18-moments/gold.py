"""Gold's five-year M1 history for Setup OWN (docs/OWN_SETUP.md): the TS session's store (2020-09 .. 2023-10)
joined to the main store (2023-08 .. 2026-10), the main store winning where they overlap. Bars are indexed by
their open time in UTC (both stores already hold UTC open/close times)."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

OLD = Path("data/history_old/FBS-Demo/XAUUSD")
NEW = Path("data/history/FBS-Demo/XAUUSD")
NY = ZoneInfo("America/New_York")
CALENDAR = Path(__file__).with_name("us_releases.csv")


def below_normal_priority() -> None:
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def bars(tf: str = "M1") -> pd.DataFrame:
    new = pd.read_parquet(NEW / f"{tf}.parquet")
    parts = [new]
    if (OLD / f"{tf}.parquet").exists():
        old = pd.read_parquet(OLD / f"{tf}.parquet")
        first_new = pd.to_datetime(new["open_time"], utc=True).min()
        parts.insert(0, old[pd.to_datetime(old["open_time"], utc=True) < first_new])
    d = pd.concat(parts, ignore_index=True)
    d.index = pd.DatetimeIndex(pd.to_datetime(d["open_time"], utc=True))
    return d.sort_index()


def releases() -> pd.DataFrame:
    """The calendar with each release's UTC time (New York local time, DST-aware)."""
    c = pd.read_csv(CALENDAR, dtype=str, keep_default_na=False)
    local = pd.to_datetime(c["date"] + " " + c["time_et"]).dt.tz_localize(NY)
    c["t"] = local.dt.tz_convert("UTC")
    return c
