"""Stored ticks for backtests that replay quotes (Setup OWN PLAN-1, S2): one Parquet file per symbol and UTC
day, ``<root>/<SYMBOL>/<YYYY-MM-DD>.parquet`` with ``time_utc`` (UTC), ``bid`` and ``ask`` (the research's
``data/ticks`` layout, filled by the MT5 tick downloads).

A day without a file has no ticks (the backtest falls back to bars there). Reading never goes past ``end``:
a day at / after it is never opened, and ticks at / after it are dropped (a run's period stays closed).
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.clock import ensure_utc
from app.core.errors import DataQualityError

Ticks = tuple[np.ndarray, np.ndarray, np.ndarray]  # UTC epoch ns (int64), bid, ask; in time order
EMPTY: Ticks = (np.empty(0, np.int64), np.empty(0), np.empty(0))


class TickStore:
    def __init__(self, root: Path, *, end: datetime | None = None, keep_days: int = 4) -> None:
        self.root = root
        self.end = None if end is None else ensure_utc(end)
        self.keep_days = keep_days
        self._days: OrderedDict[tuple[str, str], Ticks] = OrderedDict()

    def day(self, symbol: str, day: datetime) -> Ticks:
        """The ticks of one UTC day (cached); empty without a file or at / after ``end``."""
        start = pd.Timestamp(ensure_utc(day)).normalize()
        key = (symbol, f"{start:%Y-%m-%d}")
        if key in self._days:
            self._days.move_to_end(key)
            return self._days[key]
        ticks = EMPTY
        path = self.root / symbol / f"{key[1]}.parquet"
        if (self.end is None or start < pd.Timestamp(self.end)) and path.exists():
            ticks = self._read(path)
            if self.end is not None:
                limit = pd.Timestamp(self.end).as_unit("ns").value
                n = int(np.searchsorted(ticks[0], limit, side="left"))
                ticks = (ticks[0][:n], ticks[1][:n], ticks[2][:n])
        self._days[key] = ticks
        while len(self._days) > self.keep_days:
            self._days.popitem(last=False)
        return ticks

    @staticmethod
    def _read(path: Path) -> Ticks:
        try:
            x = pd.read_parquet(path, columns=["time_utc", "bid", "ask"])
        except (OSError, ValueError, KeyError) as exc:
            raise DataQualityError(f"tick file {path}: {exc}") from exc
        t = pd.to_datetime(x["time_utc"], utc=True).dt.as_unit("ns").astype("int64").to_numpy()
        order = np.argsort(t, kind="stable")
        return t[order], x["bid"].to_numpy(float)[order], x["ask"].to_numpy(float)[order]

    def between(self, symbol: str, start: datetime, end: datetime) -> Ticks:
        """The ticks in [start, end) (UTC), across day files."""
        a, b = pd.Timestamp(ensure_utc(start)), pd.Timestamp(ensure_utc(end))
        parts = []
        day = a.normalize()
        while day < b:
            t, bid, ask = self.day(symbol, day.to_pydatetime())
            lo = int(np.searchsorted(t, a.as_unit("ns").value, side="left"))
            hi = int(np.searchsorted(t, b.as_unit("ns").value, side="left"))
            if hi > lo:
                parts.append((t[lo:hi], bid[lo:hi], ask[lo:hi]))
            day += timedelta(days=1)
        if not parts:
            return EMPTY
        if len(parts) == 1:
            return parts[0]
        return (
            np.concatenate([p[0] for p in parts]),
            np.concatenate([p[1] for p in parts]),
            np.concatenate([p[2] for p in parts]),
        )
