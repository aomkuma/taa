"""Price action: candle anatomy, confirmed swings, market structure, S/R zones and breakouts (PLAN §A6).

Look-ahead discipline: a swing pivot at bar *i* needs *k* bars on each side, so it only becomes known at its
**confirmation** bar ``i + k``. Everything derived from swings (structure, zones, breakouts) is keyed by
confirmation position, and a consumer evaluating bar *t* may use only swings with ``confirm_pos <= t``.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from app.core.errors import ConfigError, InsufficientDataError
from app.indicators.common import FloatArray, as_float, check_aligned, check_period


class SwingKind(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"


class StructureLabel(StrEnum):
    HH = "HH"  # higher high
    LH = "LH"  # lower high
    EQH = "EQH"  # equal high (within tolerance)
    HL = "HL"  # higher low
    LL = "LL"  # lower low
    EQL = "EQL"  # equal low (within tolerance)


class Trend(StrEnum):
    UP = "UP"  # last high HH and last low HL
    DOWN = "DOWN"  # last high LH and last low LL
    RANGE = "RANGE"  # any other combination


class BreakoutStatus(StrEnum):
    PENDING = "PENDING"  # fewer than N bars since the breakout, still outside the zone
    CONFIRMED = "CONFIRMED"  # held outside the zone for N bars
    FALSE = "FALSE"  # closed back inside the zone within N bars


@dataclass(frozen=True, slots=True)
class Swing:
    kind: SwingKind
    price: float
    pivot_pos: int
    confirm_pos: int
    pivot_at: Hashable  # index label of the pivot bar (a UTC timestamp for candle frames)
    confirm_at: Hashable


@dataclass(frozen=True, slots=True)
class LabeledSwing:
    swing: Swing
    label: StructureLabel | None  # None for the first swing of its kind (nothing to compare with)


@dataclass(frozen=True, slots=True)
class Zone:
    low: float
    high: float
    touches: int
    high_touches: int  # members that were swing highs (resistance history)
    low_touches: int  # members that were swing lows (support history)
    first_pivot_pos: int
    last_pivot_pos: int

    @property
    def center(self) -> float:
        return (self.low + self.high) / 2

    def role(self, price: float) -> str:
        """``SUPPORT`` below *price*, ``RESISTANCE`` above it, ``INSIDE`` when *price* is within it."""
        if self.high < price:
            return "SUPPORT"
        if self.low > price:
            return "RESISTANCE"
        return "INSIDE"


@dataclass(frozen=True, slots=True)
class Breakout:
    zone: Zone
    direction: int  # +1 up through the zone top, -1 down through the zone bottom
    pos: int  # bar whose close broke out
    level: float  # zone edge plus the ATR buffer at that bar
    status: BreakoutStatus
    resolved_pos: int | None  # bar that confirmed or falsified it; None while pending


# --- candle anatomy ---------------------------------------------------------------------------------------


def candle_anatomy(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.DataFrame:
    """Columns ``body``, ``range``, ``body_ratio``, ``upper_wick_ratio``, ``lower_wick_ratio``, ``direction``.

    Ratios are fractions of the bar range (they sum to 1); a zero-range bar has NaN ratios. ``direction`` is
    +1 (close > open), -1 (close < open) or 0.
    """
    check_aligned(open_, high, low, close)
    o, h, lo, c = as_float(open_), as_float(high), as_float(low), as_float(close)
    rng = h - lo
    body = np.abs(c - o)
    with np.errstate(divide="ignore", invalid="ignore"):
        safe = np.where(rng > 0, rng, np.nan)
        body_ratio = body / safe
        upper = (h - np.maximum(o, c)) / safe
        lower = (np.minimum(o, c) - lo) / safe
    return pd.DataFrame(
        {
            "body": body,
            "range": rng,
            "body_ratio": body_ratio,
            "upper_wick_ratio": upper,
            "lower_wick_ratio": lower,
            "direction": np.sign(c - o),
        },
        index=close.index,
    )


# --- swings -----------------------------------------------------------------------------------------------


def _pivot_mask(values: FloatArray, k: int, *, high: bool) -> npt.NDArray[np.bool_]:
    """Pivot if strictly beyond the k bars before and at least equal to the k bars after.

    The asymmetric tie rule makes the *first* bar of an equal-price top (or bottom) the pivot, so a flat top
    yields exactly one swing.
    """
    mask = np.zeros(values.shape, dtype=bool)
    if len(values) < 2 * k + 1:
        return mask
    w = sliding_window_view(values if high else -values, 2 * k + 1)
    centre = w[:, k]
    with np.errstate(invalid="ignore"):
        is_pivot = (centre > w[:, :k].max(axis=1)) & (centre >= w[:, k + 1 :].max(axis=1))
    mask[k : len(values) - k] = is_pivot & np.isfinite(w).all(axis=1)
    return mask


def find_swings(high: pd.Series, low: pd.Series, k: int = 3) -> list[Swing]:
    """Confirmed pivot highs/lows, ordered by confirmation position (highs before lows on the same bar).

    The last *k* bars can never hold a confirmed pivot yet.
    """
    check_period("k", k)
    check_aligned(high, low)
    h, lo = as_float(high), as_float(low)
    index = high.index
    swings: list[Swing] = []
    for kind, values, mask in (
        (SwingKind.HIGH, h, _pivot_mask(h, k, high=True)),
        (SwingKind.LOW, lo, _pivot_mask(lo, k, high=False)),
    ):
        for i in np.flatnonzero(mask):
            pos = int(i)
            swings.append(Swing(kind, float(values[pos]), pos, pos + k, index[pos], index[pos + k]))
    swings.sort(key=lambda s: (s.confirm_pos, s.kind != SwingKind.HIGH))
    return swings


def swing_points(high: pd.Series, low: pd.Series, k: int = 3) -> pd.DataFrame:
    """Per-bar view of :func:`find_swings`: ``swing_high``/``swing_low`` hold the pivot price on the
    **confirmation** bar (NaN elsewhere), and ``*_pivot_pos`` the pivot's position."""
    n = len(high)
    cols = {
        name: np.full(n, np.nan) for name in ("swing_high", "swing_low", "high_pivot_pos", "low_pivot_pos")
    }
    for s in find_swings(high, low, k):
        prefix = "high" if s.kind is SwingKind.HIGH else "low"
        cols[f"swing_{prefix}"][s.confirm_pos] = s.price
        cols[f"{prefix}_pivot_pos"][s.confirm_pos] = s.pivot_pos
    return pd.DataFrame(cols, index=high.index)


# --- structure --------------------------------------------------------------------------------------------


def label_structure(swings: Sequence[Swing], equal_tolerance: float = 0.0) -> list[LabeledSwing]:
    """Label each swing against the previous swing of the same kind (HH/LH/EQH, HL/LL/EQL).

    *equal_tolerance* is an absolute price distance (e.g. ``0.1 * ATR``) within which two swings count as
    equal.
    """
    if not (math.isfinite(equal_tolerance) and equal_tolerance >= 0):
        raise ConfigError(f"equal_tolerance must be >= 0 (got {equal_tolerance!r})")
    last: dict[SwingKind, float] = {}
    out: list[LabeledSwing] = []
    for s in sorted(swings, key=lambda x: (x.confirm_pos, x.kind != SwingKind.HIGH)):
        prev = last.get(s.kind)
        label: StructureLabel | None = None
        if prev is not None:
            diff = s.price - prev
            if s.kind is SwingKind.HIGH:
                label = (
                    StructureLabel.EQH
                    if abs(diff) <= equal_tolerance
                    else (StructureLabel.HH if diff > 0 else StructureLabel.LH)
                )
            else:
                label = (
                    StructureLabel.EQL
                    if abs(diff) <= equal_tolerance
                    else (StructureLabel.HL if diff > 0 else StructureLabel.LL)
                )
        out.append(LabeledSwing(s, label))
        last[s.kind] = s.price
    return out


def market_structure(
    high: pd.Series, low: pd.Series, k: int = 3, equal_tolerance: float = 0.0
) -> pd.DataFrame:
    """Per bar: ``last_high_label``, ``last_low_label`` and ``trend`` from swings confirmed at or before it.

    ``trend`` is None until both a labeled high and a labeled low exist.
    """
    n = len(high)
    high_label: list[str | None] = [None] * n
    low_label: list[str | None] = [None] * n
    events = label_structure(find_swings(high, low, k), equal_tolerance)
    current: dict[SwingKind, str | None] = {SwingKind.HIGH: None, SwingKind.LOW: None}
    j = 0
    for t in range(n):
        while j < len(events) and events[j].swing.confirm_pos <= t:
            ev = events[j]
            if ev.label is not None:
                current[ev.swing.kind] = ev.label.value
            j += 1
        high_label[t], low_label[t] = current[SwingKind.HIGH], current[SwingKind.LOW]
    trend = [_trend(h, lo) for h, lo in zip(high_label, low_label, strict=True)]
    return pd.DataFrame(
        {"last_high_label": high_label, "last_low_label": low_label, "trend": trend},
        index=high.index,
        dtype=object,
    )


def _trend(high_label: str | None, low_label: str | None) -> str | None:
    if high_label is None or low_label is None:
        return None
    if high_label == StructureLabel.HH and low_label == StructureLabel.HL:
        return Trend.UP.value
    if high_label == StructureLabel.LH and low_label == StructureLabel.LL:
        return Trend.DOWN.value
    return Trend.RANGE.value


# --- support / resistance ---------------------------------------------------------------------------------


def sr_zones(
    swings: Sequence[Swing],
    *,
    as_of_pos: int,
    atr_value: float,
    tolerance_atr: float,
    min_touches: int = 1,
) -> list[Zone]:
    """Cluster swing prices confirmed at or before *as_of_pos* into zones, strongest first.

    Sorted by price, a swing joins the current cluster while it is within ``atr_value * tolerance_atr`` of the
    cluster's lowest price (so a zone is never wider than the tolerance). Strength = number of touches.
    Raises :class:`InsufficientDataError` without a usable ATR: zones sized by a NaN would be meaningless.
    """
    if not (math.isfinite(atr_value) and atr_value > 0):
        raise InsufficientDataError(f"S/R zones need a positive ATR (got {atr_value!r})")
    if not (math.isfinite(tolerance_atr) and tolerance_atr > 0):
        raise ConfigError(f"tolerance_atr must be > 0 (got {tolerance_atr!r})")
    check_period("min_touches", min_touches)
    tol = atr_value * tolerance_atr
    known = sorted((s for s in swings if s.confirm_pos <= as_of_pos), key=lambda s: s.price)
    clusters: list[list[Swing]] = []
    for s in known:
        if clusters and s.price - clusters[-1][0].price <= tol:
            clusters[-1].append(s)
        else:
            clusters.append([s])
    zones = [
        Zone(
            low=members[0].price,
            high=members[-1].price,
            touches=len(members),
            high_touches=sum(m.kind is SwingKind.HIGH for m in members),
            low_touches=sum(m.kind is SwingKind.LOW for m in members),
            first_pivot_pos=min(m.pivot_pos for m in members),
            last_pivot_pos=max(m.pivot_pos for m in members),
        )
        for members in clusters
        if len(members) >= min_touches
    ]
    zones.sort(key=lambda z: (-z.touches, -z.last_pivot_pos))
    return zones


# --- breakouts --------------------------------------------------------------------------------------------


def detect_breakouts(
    close: pd.Series,
    atr_values: pd.Series,
    zones: Sequence[Zone],
    *,
    buffer_atr: float,
    false_breakout_bars: int,
    start_pos: int = 1,
) -> list[Breakout]:
    """Closes that cross beyond a zone edge plus ``buffer_atr * ATR``, ordered by position.

    A breakout is FALSE if a close returns inside the zone within *false_breakout_bars* bars, CONFIRMED after
    that many bars outside, and PENDING while the data ends earlier. Statuses use only bars up to
    ``resolved_pos``. The zones must come from swings confirmed before *start_pos*; zones built later would
    leak future pivots into earlier breakouts.
    """
    check_aligned(close, atr_values)
    check_period("false_breakout_bars", false_breakout_bars)
    if not (math.isfinite(buffer_atr) and buffer_atr >= 0):
        raise ConfigError(f"buffer_atr must be >= 0 (got {buffer_atr!r})")
    c, a = as_float(close), as_float(atr_values)
    n = len(c)
    prev_c = _shift(c)
    out: list[Breakout] = []
    for zone in zones:
        up_level = zone.high + buffer_atr * a
        down_level = zone.low - buffer_atr * a
        with np.errstate(invalid="ignore"):
            up = (c > up_level) & (prev_c <= _shift(up_level))
            down = (c < down_level) & (prev_c >= _shift(down_level))
        for direction, hits, levels in ((1, up, up_level), (-1, down, down_level)):
            for i in np.flatnonzero(hits):
                t = int(i)
                if t < max(start_pos, 1):
                    continue
                status, resolved = _resolve(c, t, direction, zone, false_breakout_bars, n)
                out.append(Breakout(zone, direction, t, float(levels[t]), status, resolved))
    out.sort(key=lambda b: (b.pos, -b.direction))
    return out


def _shift(values: FloatArray) -> FloatArray:
    return np.concatenate(([np.nan], values[:-1])).astype(np.float64)


def _resolve(
    c: FloatArray, t: int, direction: int, zone: Zone, bars: int, n: int
) -> tuple[BreakoutStatus, int | None]:
    for j in range(t + 1, min(t + bars, n - 1) + 1):
        back_inside = c[j] <= zone.high if direction > 0 else c[j] >= zone.low
        if back_inside:
            return BreakoutStatus.FALSE, j
    if t + bars <= n - 1:
        return BreakoutStatus.CONFIRMED, t + bars
    return BreakoutStatus.PENDING, None
