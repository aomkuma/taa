"""Higher-timeframe market map: trend vs consolidation and demand/supply zones (TAA-L809; §L20.9).

Pure functions over closed candles of one context timeframe (H4, D1), indexed by close time. Every value at
bar *t* uses bars <= *t* only: swings are used from their confirmation bar, zones from the bar that completed
them, and the state's hysteresis looks back only.

**State per bar** (:func:`state_frame`):

- the raw state: ``UP`` when ADX >= ``trend_adx``, the efficiency ratio over ``er_bars`` >= ``er_trend``, the
  close and EMA(mid) above EMA(slow) and the swing structure not DOWN; ``DOWN`` mirrored; ``RANGE`` when
  ADX < ``range_adx`` and the efficiency ratio < ``er_range``; otherwise ``TRANSITION``; ``UNKNOWN`` during
  warm-up. Efficiency ratio = |close_t − close_{t−n}| / Σ|Δclose| over n bars (1 = a straight line);
- hysteresis: the reported state changes only after ``switch_bars`` consecutive bars agree on a new raw
  state, so one bar does not flip it;
- ``compression``: ATR percentile < ``compression_pct`` and the Bollinger width in the lowest
  ``compression_pct`` percent of its last ``pct_lookback`` bars (direction-neutral).

**Range box** (a ``RANGE`` state): the high and low of the last ``range_bars`` bars, its width in ATR and the
number of confirmed swing highs (lows) within ``zone_tolerance_atr`` × ATR of the top (bottom).

**Zones** at bar *t* within the last ``zone_lookback_bars`` bars:

- ``SWING``: clusters of confirmed swings (:func:`app.indicators.price_action.sr_zones`) with at least
  ``min_touches`` touches; below the close a cluster is ``DEMAND``, above it ``SUPPLY``; one containing the
  close takes the side of its majority of touches;
- ``BASE``: the tight base (1-``max_base_bars`` bars, each at most ``base_atr`` × ATR) right before a
  displacement leg of at most ``max_leg_bars`` bars that moves >= ``displacement_atr`` × ATR and closes beyond
  the previous ``break_lookback`` bars' extreme (the rule of ``smc.supply_demand``): ``DEMAND`` below a rally,
  ``SUPPLY`` above a drop. ``tests`` counts later bars that traded into the zone; a close through its far side
  removes it.

Signal features (:func:`signal_features`) express the map relative to one trade (side, entry, stop, target).
A frame may carry the timeframe's chart read (:mod:`app.indicators.chart_read`, TAA-L813); its features are
``ctx:<tf>_sw_*``, ``_inv_r``, ``_lvl_*``, ``_tl_atr``, ``_retrace*`` and ``_ev_*``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

from app.indicators.chart_read import ChartRead, EventKind, LevelRole, Structure
from app.indicators.common import FloatArray
from app.indicators.price_action import SwingKind, find_swings, market_structure, sr_zones
from app.indicators.trend import adx, ema
from app.indicators.volatility import atr, atr_percentile, bollinger


class MapState(StrEnum):
    UP = "UP"
    DOWN = "DOWN"
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class ZoneKind(StrEnum):
    DEMAND = "DEMAND"
    SUPPLY = "SUPPLY"


class ZoneSource(StrEnum):
    SWING = "SWING"
    BASE = "BASE"


@dataclass(frozen=True, slots=True)
class MapParams:
    ema_mid: int = 50
    ema_slow: int = 200
    adx_period: int = 14
    atr_period: int = 14
    trend_adx: float = 20.0
    range_adx: float = 18.0
    er_bars: int = 20
    er_trend: float = 0.3
    er_range: float = 0.25
    switch_bars: int = 2
    swing_k: int = 3
    range_bars: int = 30
    compression_pct: float = 20.0
    pct_lookback: int = 100
    bb_period: int = 20
    zone_lookback_bars: int = 400
    zone_tolerance_atr: float = 0.5
    min_touches: int = 2
    displacement_atr: float = 2.0
    max_leg_bars: int = 3
    break_lookback: int = 10
    base_atr: float = 0.6
    max_base_bars: int = 4
    max_tests: int = 3  # a zone traded into more often than this is spent
    max_zones: int = 6  # per kind, nearest to the close first
    zone_near_atr: float = 0.25  # "at a zone": within this many ATR of it
    room_cap_r: float = 10.0


@dataclass(frozen=True, slots=True)
class MapZone:
    kind: ZoneKind
    source: ZoneSource
    low: float
    high: float
    strength: int  # touches (SWING) or the base's bars (BASE)
    tests: int  # later bars that traded into it (BASE); 0 for SWING
    formed_at: datetime


@dataclass(frozen=True, slots=True)
class RangeBox:
    high: float
    low: float
    width_atr: float
    top_touches: int
    bottom_touches: int


@dataclass(frozen=True, slots=True)
class TimeframeMap:
    timeframe: str
    at: datetime  # close time of the last closed bar used
    state: MapState
    raw_state: MapState
    adx: float | None
    efficiency: float | None
    atr: float | None
    close: float
    compression: bool
    box: RangeBox | None
    zones: tuple[MapZone, ...] = ()
    atr_pct: float | None = None  # ATR percentile over ``MapParams.pct_lookback`` bars, 0..100 (quiet phases)
    read: ChartRead | None = None  # TAA-L813: the chart read at the same bar, when configured


@dataclass(frozen=True, slots=True)
class MarketMap:
    """The context timeframes' maps at one instant, keyed by timeframe name (``H4``, ``D1``)."""

    frames: Mapping[str, TimeframeMap] = field(default_factory=dict)
    near_atr: float = 0.25  # "at a zone": within this many ATR of it (MapParams.zone_near_atr)
    room_cap_r: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "near_atr": self.near_atr,
            "room_cap_r": self.room_cap_r,
            "frames": {tf: _tf_to_dict(m) for tf, m in self.frames.items()},
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> MarketMap:
        return cls(
            {tf: _tf_from_dict(m) for tf, m in d["frames"].items()},
            float(d["near_atr"]),
            float(d["room_cap_r"]),
        )


def _tf_to_dict(m: TimeframeMap) -> dict[str, Any]:
    return {
        "timeframe": m.timeframe,
        "at": m.at.isoformat(),
        "state": m.state.value,
        "raw_state": m.raw_state.value,
        "adx": m.adx,
        "efficiency": m.efficiency,
        "atr": m.atr,
        "close": m.close,
        "compression": m.compression,
        "atr_pct": m.atr_pct,
        "box": None if m.box is None else asdict(m.box),
        # only when present, so maps (and decision digests) without a read stay as they were
        **({} if m.read is None else {"read": m.read.to_dict()}),
        "zones": [
            {
                **asdict(z),
                "kind": z.kind.value,
                "source": z.source.value,
                "formed_at": z.formed_at.isoformat(),
            }
            for z in m.zones
        ],
    }


def _tf_from_dict(d: Mapping[str, Any]) -> TimeframeMap:
    box = d["box"]
    return TimeframeMap(
        timeframe=str(d["timeframe"]),
        at=datetime.fromisoformat(d["at"]),
        state=MapState(d["state"]),
        raw_state=MapState(d["raw_state"]),
        adx=d["adx"],
        efficiency=d["efficiency"],
        atr=d["atr"],
        close=float(d["close"]),
        compression=bool(d["compression"]),
        atr_pct=d.get("atr_pct"),  # absent in records before 2026-10-14
        read=ChartRead.from_dict(d["read"]) if d.get("read") else None,
        box=None if box is None else RangeBox(**box),
        zones=tuple(
            MapZone(
                ZoneKind(z["kind"]),
                ZoneSource(z["source"]),
                float(z["low"]),
                float(z["high"]),
                int(z["strength"]),
                int(z["tests"]),
                datetime.fromisoformat(z["formed_at"]),
            )
            for z in d["zones"]
        ),
    )


# --- per-bar state ----------------------------------------------------------------------------------------


def efficiency_ratio(close: pd.Series, n: int) -> pd.Series:
    c = close.astype(float)
    net = (c - c.shift(n)).abs()
    path = c.diff().abs().rolling(n).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        return (net / path).where(path > 0)


def _hysteresis(raw: list[str], switch_bars: int) -> list[str]:
    out: list[str] = []
    current = MapState.UNKNOWN.value
    candidate, streak = current, 0
    for value in raw:
        if value == current:
            candidate, streak = current, 0
        elif value == candidate:
            streak += 1
        else:
            candidate, streak = value, 1
        if current == MapState.UNKNOWN.value or value == MapState.UNKNOWN.value or streak >= switch_bars:
            current, candidate, streak = value, value, 0
        out.append(current)
    return out


def state_frame(candles: pd.DataFrame, p: MapParams) -> pd.DataFrame:
    """Per bar of *candles* (open/high/low/close, close-time index): indicators, states, compression."""
    high, low, close = (
        candles["high"].astype(float),
        candles["low"].astype(float),
        candles["close"].astype(float),
    )
    out = pd.DataFrame(index=candles.index)
    out["close"] = close
    out["ema_mid"] = ema(close, p.ema_mid)
    out["ema_slow"] = ema(close, p.ema_slow)
    dmi = adx(high, low, close, p.adx_period)
    out["adx"] = dmi["adx"]
    out["atr"] = atr(high, low, close, p.atr_period)
    out["er"] = efficiency_ratio(close, p.er_bars)
    out["structure"] = market_structure(high, low, p.swing_k)["trend"]
    atr_pct = atr_percentile(out["atr"], p.pct_lookback)
    width = bollinger(close, p.bb_period)["width"]
    width_pct = width.rolling(p.pct_lookback).rank(pct=True) * 100
    out["compression"] = (atr_pct < p.compression_pct) & (width_pct < p.compression_pct)
    out["atr_pct"] = atr_pct
    a, e, c = out["adx"].to_numpy(), out["er"].to_numpy(), close.to_numpy()
    mid, slow = out["ema_mid"].to_numpy(), out["ema_slow"].to_numpy()
    structure = out["structure"].to_numpy()
    raw: list[str] = []
    for i in range(len(out)):
        if not all(math.isfinite(v) for v in (a[i], e[i], mid[i], slow[i])):
            raw.append(MapState.UNKNOWN.value)
        elif (
            a[i] >= p.trend_adx
            and e[i] >= p.er_trend
            and c[i] > slow[i]
            and mid[i] > slow[i]
            and structure[i] != "DOWN"
        ):
            raw.append(MapState.UP.value)
        elif (
            a[i] >= p.trend_adx
            and e[i] >= p.er_trend
            and c[i] < slow[i]
            and mid[i] < slow[i]
            and structure[i] != "UP"
        ):
            raw.append(MapState.DOWN.value)
        elif a[i] < p.range_adx and e[i] < p.er_range:
            raw.append(MapState.RANGE.value)
        else:
            raw.append(MapState.TRANSITION.value)
    out["raw_state"] = raw
    out["state"] = _hysteresis(raw, p.switch_bars)
    return out


# --- zones ------------------------------------------------------------------------------------------------


def _bases(
    o: FloatArray, h: FloatArray, lo: FloatArray, c: FloatArray, a: FloatArray, p: MapParams, end: int
) -> list[tuple[int, int, int, float, float, int]]:
    """``(base_first, leg_end, sign, low, high, base_bars)`` of base zones completed at or before *end*."""
    out = []
    last_end = -1
    start = max(p.break_lookback + p.max_leg_bars, end - p.zone_lookback_bars + 1)
    for d in range(start, end + 1):
        if not math.isfinite(a[d]) or d <= last_end:
            continue
        for k in range(1, p.max_leg_bars + 1):
            s = d - k + 1
            move = c[d] - o[s]
            if abs(move) < p.displacement_atr * a[d]:
                continue
            sign = 1 if move > 0 else -1
            ref = h[s - p.break_lookback : s] if sign > 0 else lo[s - p.break_lookback : s]
            if len(ref) == 0 or (c[d] - (ref.max() if sign > 0 else ref.min())) * sign <= 0:
                continue
            base: list[int] = []
            i = s - 1
            while i >= 0 and len(base) < p.max_base_bars and math.isfinite(a[i]):
                if h[i] - lo[i] > p.base_atr * a[i]:
                    break
                base.append(i)
                i -= 1
            if base:
                out.append((min(base), d, sign, float(lo[base].min()), float(h[base].max()), len(base)))
            last_end = d
            break
    return out


def zones_at(candles: pd.DataFrame, states: pd.DataFrame, pos: int, p: MapParams) -> tuple[MapZone, ...]:
    """Demand and supply zones known at bar *pos* (closed bars ``<= pos`` only)."""
    a_t = float(states["atr"].iloc[pos])
    if not (math.isfinite(a_t) and a_t > 0):
        return ()
    first = max(0, pos - p.zone_lookback_bars + 1)
    window = candles.iloc[first : pos + 1]
    close = float(window["close"].iloc[-1])
    index = candles.index
    zones: list[MapZone] = []
    swings = find_swings(window["high"].astype(float), window["low"].astype(float), p.swing_k)
    for z in sr_zones(
        swings,
        as_of_pos=len(window) - 1,
        atr_value=a_t,
        tolerance_atr=p.zone_tolerance_atr,
        min_touches=p.min_touches,
    ):
        role = z.role(close)
        if role == "SUPPORT":
            kind = ZoneKind.DEMAND
        elif role == "RESISTANCE":
            kind = ZoneKind.SUPPLY
        else:
            kind = ZoneKind.DEMAND if z.low_touches >= z.high_touches else ZoneKind.SUPPLY
        zones.append(
            MapZone(kind, ZoneSource.SWING, z.low, z.high, z.touches, 0, _ts(index[first + z.last_pivot_pos]))
        )
    o, h, lo, c = (candles[col].to_numpy(dtype=float) for col in ("open", "high", "low", "close"))
    a = states["atr"].to_numpy(dtype=float)
    for _first, leg_end, sign, z_low, z_high, bars in _bases(o, h, lo, c, a, p, pos):
        later = slice(leg_end + 1, pos + 1)
        if sign > 0:
            broken = bool(np.any(c[later] < z_low))
            tests = int(np.sum(lo[later] <= z_high))
        else:
            broken = bool(np.any(c[later] > z_high))
            tests = int(np.sum(h[later] >= z_low))
        if broken or tests > p.max_tests:
            continue
        kind = ZoneKind.DEMAND if sign > 0 else ZoneKind.SUPPLY
        zones.append(MapZone(kind, ZoneSource.BASE, z_low, z_high, bars, tests, _ts(index[leg_end])))
    out: list[MapZone] = []
    for kind in ZoneKind:
        same = sorted((z for z in zones if z.kind is kind), key=lambda z: _distance(z, close))
        out += same[: p.max_zones]
    return tuple(out)


def _distance(z: MapZone, price: float) -> float:
    if z.low <= price <= z.high:
        return 0.0
    return min(abs(price - z.low), abs(price - z.high))


def _ts(value: object) -> datetime:
    return pd.Timestamp(value).to_pydatetime()  # type: ignore[arg-type]


def range_box(candles: pd.DataFrame, states: pd.DataFrame, pos: int, p: MapParams) -> RangeBox | None:
    a_t = float(states["atr"].iloc[pos])
    if pos + 1 < p.range_bars or not (math.isfinite(a_t) and a_t > 0):
        return None
    window = candles.iloc[pos - p.range_bars + 1 : pos + 1]
    top, bottom = float(window["high"].max()), float(window["low"].min())
    tol = p.zone_tolerance_atr * a_t
    swings = [
        s
        for s in find_swings(window["high"].astype(float), window["low"].astype(float), p.swing_k)
        if s.confirm_pos < len(window)
    ]
    return RangeBox(
        high=top,
        low=bottom,
        width_atr=(top - bottom) / a_t,
        top_touches=sum(1 for s in swings if s.kind is SwingKind.HIGH and top - s.price <= tol),
        bottom_touches=sum(1 for s in swings if s.kind is SwingKind.LOW and s.price - bottom <= tol),
    )


def timeframe_map(
    timeframe: str, candles: pd.DataFrame, states: pd.DataFrame, pos: int, p: MapParams
) -> TimeframeMap:
    """The map of one timeframe at bar *pos* (*states* from :func:`state_frame` over the same candles)."""
    row = states.iloc[pos]
    state = MapState(row["state"])

    def num(v: object) -> float | None:
        f = float(v)  # type: ignore[arg-type]
        return f if math.isfinite(f) else None

    return TimeframeMap(
        timeframe=timeframe,
        at=_ts(states.index[pos]),
        state=state,
        raw_state=MapState(row["raw_state"]),
        adx=num(row["adx"]),
        efficiency=num(row["er"]),
        atr=num(row["atr"]),
        close=float(row["close"]),
        compression=bool(row["compression"]),
        box=range_box(candles, states, pos, p) if state is MapState.RANGE else None,
        zones=zones_at(candles, states, pos, p),
        atr_pct=num(row["atr_pct"]),
    )


# --- relative to one trade -------------------------------------------------------------------------------


def signal_features(
    market_map: MarketMap, *, buy: bool, entry: float, stop: float | None, target: float | None
) -> dict[str, float]:
    """``ctx:<tf>_*`` features of a trade against the map (absent keys = unknown)."""
    out: dict[str, float] = {}
    sign = 1 if buy else -1
    risk = abs(entry - stop) if stop is not None else None
    for tf, m in market_map.frames.items():
        key = f"ctx:{tf.lower()}_"
        if m.state is MapState.UP:
            out[key + "trend"] = float(sign)
        elif m.state is MapState.DOWN:
            out[key + "trend"] = float(-sign)
        elif m.state is not MapState.UNKNOWN:
            out[key + "trend"] = 0.0
        out[key + "range"] = 1.0 if m.state is MapState.RANGE else 0.0
        out[key + "compression"] = 1.0 if m.compression else 0.0
        if m.box is not None and m.box.high > m.box.low:
            pos = (entry - m.box.low) / (m.box.high - m.box.low)
            out[key + "range_pos"] = round(pos if buy else 1.0 - pos, 4)
        if m.atr is None:
            continue
        near = market_map.near_atr * m.atr
        with_kind = ZoneKind.DEMAND if buy else ZoneKind.SUPPLY
        against = ZoneKind.SUPPLY if buy else ZoneKind.DEMAND
        mine = [z for z in m.zones if z.kind is with_kind and z.low - near <= entry <= z.high + near]
        out[key + "zone_with"] = 1.0 if mine else 0.0
        out[key + "zone_with_strength"] = float(max((z.strength for z in mine), default=0))
        ahead = [
            (z.low if buy else z.high) - entry
            for z in m.zones
            if z.kind is against and ((z.low if buy else z.high) - entry) * sign > 0
        ]
        nearest = min((abs(d) for d in ahead), default=None)
        if risk:
            out[key + "room_r"] = round(
                min(market_map.room_cap_r, nearest / risk) if nearest is not None else market_map.room_cap_r,
                4,
            )
        if target is not None:
            span = (target - entry) * sign
            out[key + "zone_before_tp"] = 1.0 if nearest is not None and 0 < nearest < span else 0.0
        if m.read is not None:
            out.update(
                read_features(m.read, key, buy=buy, entry=entry, risk=risk, room_cap=market_map.room_cap_r)
            )
    return out


_PHASE = {
    Structure.UP: 0.0,
    Structure.DOWN: 0.0,
    Structure.CONTRACTING: 1.0,
    Structure.BROADENING: 2.0,
    Structure.FLAT: 3.0,
}


def read_features(
    r: ChartRead, key: str, *, buy: bool, entry: float, risk: float | None, room_cap: float
) -> dict[str, float]:
    """The chart read relative to one trade (docs/CHART_READ.md §6); absent keys = unknown.

    ``inv_r`` = (entry − invalidation) × side / risk: positive when the structure's invalidation lies behind
    the entry (below 1 the stop is beyond it), negative when it lies ahead (a trade against the structure).
    ``tl_atr`` uses the line behind the trade (the support line for a BUY) when there is one, else the other.
    """
    out: dict[str, float] = {}
    sign = 1 if buy else -1
    a = r.atr
    if r.structure is not Structure.NONE:
        trend = sign if r.structure is Structure.UP else -sign if r.structure is Structure.DOWN else 0
        out[key + "sw_trend"] = float(trend)
        out[key + "sw_phase"] = _PHASE[r.structure]
        out[key + "sw_age"] = float(r.age_legs)
        out[key + "sw_broken"] = 1.0 if r.broken else 0.0
    if r.invalidation is not None and risk:
        out[key + "inv_r"] = round((entry - r.invalidation) * sign / risk, 4)
    behind = [(entry - lv.price) * sign for lv in r.levels if (entry - lv.price) * sign >= 0]
    if behind:
        out[key + "lvl_with_atr"] = round(min(behind) / a, 4)
    if risk:
        ahead = [(lv.price - entry) * sign for lv in r.levels if (lv.price - entry) * sign > 0]
        out[key + "lvl_against_r"] = round(min(room_cap, min(ahead) / risk) if ahead else room_cap, 4)
    tol = r.tol_atr * a
    out[key + "lvl_flipped"] = (
        1.0
        if any(
            lv.role is LevelRole.FLIPPED and lv.above is not buy and abs(entry - lv.price) <= tol
            for lv in r.levels
        )
        else 0.0
    )
    lines = {tl.kind.value: tl for tl in r.trendlines}
    line = lines.get("LOW" if buy else "HIGH") or lines.get("HIGH" if buy else "LOW")
    if line is not None:
        out[key + "tl_atr"] = round((entry - line.value) * sign / a, 4)
    if r.leg is not None and r.leg.retrace is not None:
        out[key + "retrace"] = r.leg.retrace
    if r.retrace_major is not None:
        out[key + "retrace_major"] = r.retrace_major
    for kind in EventKind:
        last = max((e for e in r.events if e.kind is kind), key=lambda e: e.known_at, default=None)
        out[key + "ev_" + kind.value.lower()] = 0.0 if last is None else float(last.direction * sign)
    return out
