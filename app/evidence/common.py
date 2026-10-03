"""Helpers shared by level-based detectors: touch/rejection tests and trading-day/week grouping."""

from __future__ import annotations

from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt
import pandas as pd

from app.core.errors import ConfigError
from app.evidence.framework import Direction, EvidenceContext
from app.indicators.common import FloatArray

IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class Touch:
    direction: Direction  # BULL: the level held as support; BEAR: it held as resistance
    quality: float  # 0..1: wick rejection strength combined with how close the probe came to the level


def touch_rejection(ctx: EvidenceContext, t: int, level: float, tol: float) -> Touch | None:
    """Did bar *t* probe *level* (within *tol*) and reject it?

    Support: the bar's low reaches ``level + tol`` while open and close stay at or above the level. Resistance
    mirrors it. A bar that closes through the level is not a rejection. Quality rises with the rejecting
    wick's share of the range and with the probe's closeness to the level.
    """
    if not (np.isfinite(level) and np.isfinite(tol) and tol > 0):
        return None
    o, h, lo, c = float(ctx.o[t]), float(ctx.h[t]), float(ctx.l[t]), float(ctx.c[t])
    rng = h - lo
    if rng <= 0:
        return None
    if lo <= level + tol and min(o, c) >= level:
        wick = (min(o, c) - lo) / rng
        miss = max(0.0, lo - level) / tol
        return Touch(Direction.BULL, _quality(wick, miss))
    if h >= level - tol and max(o, c) <= level:
        wick = (h - max(o, c)) / rng
        miss = max(0.0, level - h) / tol
        return Touch(Direction.BEAR, _quality(wick, miss))
    return None


def _quality(wick: float, miss: float) -> float:
    return float(np.clip(0.3 + 0.5 * wick + 0.2 * (1.0 - min(miss, 1.0)), 0.0, 1.0))


def tolerance(ctx: EvidenceContext, t: int, tol_atr: float) -> float:
    """``tol_atr × ATR[t]``; NaN during the ATR warm-up (callers then skip the bar)."""
    return float(tol_atr * ctx.atr_array()[t])


def period_keys(ctx: EvidenceContext, period: str) -> IntArray:
    """Trading day (``"day"``) or ISO week (``"week"``) of each bar, in the session timezone.

    The bar's **open** time decides, so the bar that closes exactly at midnight belongs to the day it traded
    in.
    """

    def compute() -> IntArray:
        opens = (ctx.times - pd.Timedelta(seconds=ctx.timeframe.seconds)).tz_convert(
            ZoneInfo(ctx.config.session_timezone)
        )
        if period == "day":
            days = opens.normalize().tz_localize(None)
            return np.asarray((days - pd.Timestamp("1970-01-01")) // pd.Timedelta(days=1), dtype=np.int64)
        iso = opens.isocalendar()
        return np.asarray(iso["year"].to_numpy() * 100 + iso["week"].to_numpy(), dtype=np.int64)

    if period not in ("day", "week"):
        raise ConfigError(f"period must be 'day' or 'week' (got {period!r})")
    return ctx.memo(("period_keys", period), compute)


def previous_period_hlc(ctx: EvidenceContext, period: str) -> tuple[FloatArray, FloatArray, FloatArray]:
    """For each bar: high, low and close of the previous **complete** period present in the frame.

    The first period of the frame may be cut off by the history window, so it is never used as a source (fail
    closed: those bars get NaN). All bars of a previous period closed before the current bar opened, so this
    never looks ahead.
    """

    def compute() -> tuple[FloatArray, FloatArray, FloatArray]:
        keys = period_keys(ctx, period)
        n = len(keys)
        ph, pl, pc = (np.full(n, np.nan) for _ in range(3))
        if n == 0:
            return ph, pl, pc
        h, lo, c = ctx.h, ctx.l, ctx.c
        starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
        ends = np.r_[starts[1:], n]
        # period j takes its levels from period j - 1; period 0 may be partial, so period 1 gets none
        for j in range(2, len(starts)):
            src = slice(starts[j - 1], ends[j - 1])
            dst = slice(starts[j], ends[j])
            ph[dst], pl[dst], pc[dst] = h[src].max(), lo[src].min(), c[ends[j - 1] - 1]
        return ph, pl, pc

    return ctx.memo(("previous_period_hlc", period), compute)


@dataclass
class Cooldown:
    """Suppresses repeats: an event overlapping a recent one (same direction, overlapping price range, within
    ``bars``) is the same event seen again, typically because levels were rebuilt after a new pivot."""

    bars: int
    _recent: list[tuple[int, float, float, Direction]] = field(default_factory=list)

    def allow(self, t: int, low: float, high: float, direction: Direction) -> bool:
        self._recent = [r for r in self._recent if r[0] >= t - self.bars]
        for _, lo, hi, d in self._recent:
            if d is direction and lo <= high and low <= hi:
                return False
        self._recent.append((t, low, high, direction))
        return True
