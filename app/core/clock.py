"""Time sources and broker server-time conversion.

MetaTrader 5's Python API returns bar, tick and deal times as Unix-epoch integers that
encode the **broker server's wall clock**, not UTC. FBS runs its servers on Eastern European
Time (UTC+2, UTC+3 during EU daylight saving). :class:`ServerClock` converts between that
encoding and real UTC using IANA timezone rules, and can verify the configured timezone
against live ticks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from app.core.errors import ConfigError

_EPOCH_NAIVE = datetime(1970, 1, 1)  # noqa: DTZ001 - naive by design: server wall-clock arithmetic


class Clock(Protocol):
    """Injectable time source (real in production, controllable in tests)."""

    def now_utc(self) -> datetime: ...

    def monotonic(self) -> float: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class ManualClock:
    """Test clock that only moves when told to."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("ManualClock requires an aware datetime")
        self._now = start.astimezone(UTC)
        self._mono = 0.0

    def now_utc(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)
        self._mono += seconds

    def set(self, when: datetime) -> None:
        delta = (when.astimezone(UTC) - self._now).total_seconds()
        self.advance(delta)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetimes are not allowed; use timezone-aware UTC")
    return dt.astimezone(UTC)


def to_epoch(dt: datetime) -> float:
    return ensure_utc(dt).timestamp()


class ClockStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED_MARKET_IDLE = "UNVERIFIED_MARKET_IDLE"  # no advancing ticks to compare against
    OFFSET_MISMATCH = "OFFSET_MISMATCH"  # broker offset != configured timezone rules
    LOCAL_CLOCK_DRIFT = "LOCAL_CLOCK_DRIFT"  # residual not explained by a whole offset


@dataclass(frozen=True)
class ClockVerification:
    status: ClockStatus
    expected_offset_s: int
    observed_offset_s: int | None
    residual_s: float | None
    detail: str

    @property
    def ok(self) -> bool:
        return self.status is ClockStatus.VERIFIED


class ServerClock:
    """Converts broker server wall-clock epochs to/from UTC using a timezone rule.

    Offsets are rounded to 15-minute granularity when observed, which tolerates network and
    tick latency of a few seconds to minutes while still catching a wrong timezone.
    """

    OFFSET_GRANULARITY_S = 900
    MAX_RESIDUAL_S = 120.0

    def __init__(self, tz_name: str, clock: Clock | None = None) -> None:
        try:
            self._tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError as exc:
            raise ConfigError(
                f"unknown BROKER_TIMEZONE {tz_name!r}; install the 'tzdata' package on Windows"
            ) from exc
        self.tz_name = tz_name
        self.clock: Clock = clock or SystemClock()

    # ------------------------------------------------------------------ offsets
    def expected_offset_seconds(self, at_utc: datetime | None = None) -> int:
        at = ensure_utc(at_utc) if at_utc else self.clock.now_utc()
        offset = at.astimezone(self._tz).utcoffset()
        return int(offset.total_seconds()) if offset is not None else 0

    # -------------------------------------------------------------- conversions
    def server_epoch_to_utc(self, server_epoch: float) -> datetime:
        """Interpret an MT5 epoch (server wall clock) and return the real UTC instant.

        Ambiguous wall-clock times during the autumn DST fall-back resolve to the first
        occurrence (``fold=0``). FX, metals and index CFDs are closed at the transition
        (Sunday 01:00 UTC), so this does not affect their bars.
        """
        wall = _EPOCH_NAIVE + timedelta(seconds=float(server_epoch))
        local = wall.replace(tzinfo=self._tz, fold=0)
        return local.astimezone(UTC)

    def server_epochs_to_utc(self, server_epochs: np.ndarray | pd.Series | list[int]) -> pd.DatetimeIndex:
        """Vectorized :meth:`server_epoch_to_utc` (ambiguous times: first occurrence)."""
        wall = pd.to_datetime(np.asarray(server_epochs, dtype="int64"), unit="s")
        local = wall.tz_localize(
            self.tz_name, ambiguous=np.ones(len(wall), dtype=bool), nonexistent="shift_forward"
        )
        return local.tz_convert("UTC")

    def utc_to_server_epoch(self, dt_utc: datetime) -> int:
        local = ensure_utc(dt_utc).astimezone(self._tz)
        wall = local.replace(tzinfo=None)
        return int((wall - _EPOCH_NAIVE).total_seconds())

    def server_now_epoch(self) -> float:
        now = self.clock.now_utc()
        return now.timestamp() + self.expected_offset_seconds(now)

    # ------------------------------------------------------------- verification
    def verify(
        self, tick_epoch: float, advancing: bool, now_utc: datetime | None = None
    ) -> ClockVerification:
        """Check the configured timezone against a live tick timestamp.

        ``advancing`` must be True only when ticks were observed to update (market live);
        otherwise an old tick would look like a large offset error.
        """
        now = ensure_utc(now_utc) if now_utc else self.clock.now_utc()
        expected = self.expected_offset_seconds(now)
        if not advancing:
            return ClockVerification(
                ClockStatus.UNVERIFIED_MARKET_IDLE,
                expected,
                None,
                None,
                "ticks are not advancing (market closed or idle); using configured timezone rules",
            )
        raw = float(tick_epoch) - now.timestamp()
        observed = int(round(raw / self.OFFSET_GRANULARITY_S) * self.OFFSET_GRANULARITY_S)
        residual = raw - observed
        if abs(residual) > self.MAX_RESIDUAL_S:
            return ClockVerification(
                ClockStatus.LOCAL_CLOCK_DRIFT,
                expected,
                observed,
                residual,
                f"tick time differs from local UTC by {residual:+.1f}s beyond a whole offset; "
                "check Windows time synchronization",
            )
        if observed != expected:
            return ClockVerification(
                ClockStatus.OFFSET_MISMATCH,
                expected,
                observed,
                residual,
                f"broker offset {observed / 3600:+.2f}h != expected {expected / 3600:+.2f}h for "
                f"{self.tz_name}; check BROKER_TIMEZONE / broker DST policy",
            )
        return ClockVerification(
            ClockStatus.VERIFIED,
            expected,
            observed,
            residual,
            f"broker offset {observed / 3600:+.2f}h matches {self.tz_name}",
        )
