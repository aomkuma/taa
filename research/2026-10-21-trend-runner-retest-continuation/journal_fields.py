# ruff: noqa: E501
"""Per-trade journal context for the Trend Runner journal (added 2026-10-22).

Every value is known at the entry moment: ATR(14) of the last M15 / M30 / H1 broker bar closed at or before the
entry, ATR(20) of the last closed broker D1 bar (the broker's day, Europe/Athens midnight), and the liquidity pools
of ``research/2026-10-18-moments/agents/journal/liq_journal.py`` ``pools()`` (imported, not copied). Times are given
in UTC and Thai time (UTC+7); the week is the Thai calendar week, Monday first.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BARS = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD"
LIQ_DIR = REPO / "research" / "2026-10-18-moments" / "agents" / "journal"
THAI = "Asia/Bangkok"
PRECURSORS = REPO / "research" / "2026-10-18-moments" / "agents" / "precursors"
if str(PRECURSORS) not in sys.path:
    sys.path.insert(0, str(PRECURSORS))

from foundation import atr as mt5_atr  # noqa: E402  (MT5 ATR.mq5)
from ticks import refuse_exam, utc  # noqa: E402


@cache
def _pools_fn():
    if str(LIQ_DIR) not in sys.path:
        sys.path.append(str(LIQ_DIR))
    import liq_journal

    return liq_journal.pools


def thai(ts: pd.Timestamp) -> str:
    return utc(ts).tz_convert(THAI).strftime("%Y-%m-%d %H:%M:%S")


def thai_week(ts: pd.Timestamp) -> str:
    """The Thai week of a moment: ISO year-week of its Thai date plus the Monday, e.g. '2025-W45 (Mon 2025-11-03)'."""
    local = utc(ts).tz_convert(THAI)
    monday = (local - pd.Timedelta(days=local.dayofweek)).date()
    iso = local.isocalendar()
    return f"{iso.year}-W{iso.week:02d} (Mon {monday.isoformat()})"


def load_bars(timeframe: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Stored broker bars with open_time in [start, end); refuses the exam."""
    refuse_exam(start, end)
    frame = pd.read_parquet(
        BARS / f"{timeframe}.parquet",
        columns=["open_time", "close_time", "open", "high", "low", "close"],
        filters=[("open_time", ">=", start.to_pydatetime()), ("open_time", "<", end.to_pydatetime())],
    )
    frame = frame.drop_duplicates("open_time", keep="last").sort_values("open_time").set_index("open_time")
    return frame


class Context:
    """ATR and pool context for entries inside one slice; bars are read once per slice."""

    def __init__(self, start: pd.Timestamp, end: pd.Timestamp, m1: pd.DataFrame):
        self.m1 = m1
        self.atr: dict[str, pd.DataFrame] = {}
        for tf, n, warm in (("M15", 14, 5), ("M30", 14, 5), ("H1", 14, 10), ("D1", 20, 60)):
            bars = load_bars(tf, start - pd.Timedelta(days=warm), end)
            bars["atr"] = mt5_atr(
                bars["high"].to_numpy(float), bars["low"].to_numpy(float), bars["close"].to_numpy(float), n
            )
            self.atr[tf] = bars

    def atr_at(self, tf: str, moment: pd.Timestamp) -> float:
        bars = self.atr[tf]
        done = bars.loc[pd.DatetimeIndex(bars["close_time"]) <= moment]
        return float(done["atr"].iloc[-1]) if len(done) else np.nan

    def at(self, moment: pd.Timestamp, prefix: str = "") -> dict[str, object]:
        moment = utc(moment)
        out: dict[str, object] = {
            f"{prefix}atr_m15": self.atr_at("M15", moment),
            f"{prefix}atr_m30": self.atr_at("M30", moment),
            f"{prefix}atr_h1": self.atr_at("H1", moment),
            f"{prefix}atr_d1_20": self.atr_at("D1", moment),
        }
        history = self.m1.loc[self.m1.index < moment]
        pools = _pools_fn()(history, out[f"{prefix}atr_h1"], moment) if len(history) else {}
        for name in (
            "yday_high",
            "yday_low",
            "asia_high",
            "asia_low",
            "today_open",
            "swing_high",
            "swing_low",
        ):
            out[f"{prefix}pool_{name}"] = float(pools[name]) if name in pools else np.nan
        return out


def path_excursions(quotes: pd.DataFrame, side: int, entry: float, risk: float, exit_time: pd.Timestamp):
    """MFE / MAE in R on the executable mark from the entry quote through the exit quote (inclusive)."""
    times = pd.DatetimeIndex(quotes["time_utc"])
    mark = quotes["bid"].to_numpy(float) if side > 0 else quotes["ask"].to_numpy(float)
    upto = mark[: int(times.searchsorted(exit_time, side="right"))]
    if not len(upto):
        return np.nan, np.nan
    r = (upto - entry) * side / risk
    return max(0.0, float(r.max())), min(0.0, float(r.min()))
