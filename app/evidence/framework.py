"""Evidence framework: records, detector base class, shared context, activation and snapshots (PLAN §A29).

Detector contract (enforced by the look-ahead harness in tests/evidence_harness.py):

- ``Detector.scan(ctx, params)`` returns **every** instance found in the frame, each stamped with the bar at
  which it became knowable (``detected_at`` = that bar's close time). An instance stamped at bar *t* may
  depend only on bars ``<= t``, so ``scan`` on the full frame, restricted to ``detected_at <= t``, equals
  ``scan`` on the frame cut at *t*.
- Which instances are still *active* at the last bar is decided centrally by :func:`activate` (age limit and
  invalidation), never by the detector, so the rule is the same for every theory.
- Evidence and snapshots are immutable. An opportunity stores the snapshot it was evaluated with; later
  redraws or recounts produce new records and never rewrite stored ones.
"""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar, TypeVar, cast

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from app.config import EvidenceConfig
from app.core.clock import ensure_utc
from app.core.enums import Timeframe
from app.core.errors import ConfigError, EvidenceError
from app.core.ids import stable_hash
from app.evidence.zigzag import zigzag
from app.indicators.common import FloatArray
from app.indicators.price_action import Swing, find_swings
from app.indicators.trend import ema
from app.indicators.volatility import atr

T = TypeVar("T")
DetailValue = float | int | str | bool


class Family(StrEnum):
    FIBONACCI = "FIBONACCI"
    LEVELS = "LEVELS"
    TREND = "TREND"
    CHART_PATTERN = "CHART_PATTERN"
    CANDLESTICK = "CANDLESTICK"
    MOMENTUM = "MOMENTUM"
    VOLATILITY_VOLUME = "VOLATILITY_VOLUME"
    ICHIMOKU = "ICHIMOKU"
    SMART_MONEY = "SMART_MONEY"
    HARMONIC = "HARMONIC"
    ELLIOTT = "ELLIOTT"
    SESSIONS = "SESSIONS"


class Direction(StrEnum):
    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"

    @property
    def sign(self) -> int:
        return {Direction.BULL: 1, Direction.BEAR: -1, Direction.NEUTRAL: 0}[self]


class Tier(StrEnum):
    T1 = "T1"  # objective: a formula or exact rule
    T2 = "T2"  # rule-based geometry with tolerances
    T3 = "T3"  # heuristic (e.g. Elliott counts)


# --- records ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class KeyLevel:
    name: str  # e.g. "neckline", "fib_61.8", "X"
    price: float
    at: datetime | None = None  # bar close time of a pattern point, when it has one

    def __post_init__(self) -> None:
        if not math.isfinite(self.price):
            raise EvidenceError(f"key level {self.name!r} has a non-finite price")
        if self.at is not None:
            object.__setattr__(self, "at", ensure_utc(self.at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "price": self.price,
            "at": None if self.at is None else self.at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> KeyLevel:
        return cls(d["name"], float(d["price"]), None if d["at"] is None else datetime.fromisoformat(d["at"]))


def swing_level(name: str, swing: Swing) -> KeyLevel:
    """A key level at a swing pivot, stamped with the pivot bar's close time."""
    return KeyLevel(name, swing.price, pd.Timestamp(cast(datetime, swing.pivot_at)).to_pydatetime())


@dataclass(frozen=True, slots=True)
class Evidence:
    detector_id: str
    detector_version: int
    family: Family
    tier: Tier
    name: str  # English display name; the PWA uses ``i18n_key``
    i18n_key: str
    symbol: str
    timeframe: Timeframe
    direction: Direction
    detected_at: datetime  # close time of the confirmation bar (UTC)
    quality: float  # 0..1 geometric / ratio fit
    key_levels: tuple[KeyLevel, ...] = ()
    invalidation: float | None = None  # a close beyond this (against the direction) ends the evidence
    targets: tuple[float, ...] = ()
    details: tuple[tuple[str, DetailValue], ...] = ()  # extra immutable facts, sorted by key

    def __post_init__(self) -> None:
        if not (math.isfinite(self.quality) and 0.0 <= self.quality <= 1.0):
            raise EvidenceError(f"{self.detector_id}: quality must be in [0, 1] (got {self.quality!r})")
        object.__setattr__(self, "detected_at", ensure_utc(self.detected_at))
        prices = [*self.targets, *([] if self.invalidation is None else [self.invalidation])]
        if not all(math.isfinite(p) for p in prices):
            raise EvidenceError(f"{self.detector_id}: non-finite invalidation or target")

    @property
    def evidence_id(self) -> str:
        """Stable identity: the same instance found again in a later scan gets the same id."""
        levels = ",".join(f"{lv.name}={lv.price:.10g}" for lv in self.key_levels)
        return stable_hash(
            self.detector_id,
            self.detector_version,
            self.symbol,
            self.timeframe,
            self.detected_at.isoformat(),
            self.direction,
            levels,
            length=24,
        )

    def detail(self, key: str, default: DetailValue | None = None) -> DetailValue | None:
        return dict(self.details).get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "detector_id": self.detector_id,
            "detector_version": self.detector_version,
            "family": self.family.value,
            "tier": self.tier.value,
            "name": self.name,
            "i18n_key": self.i18n_key,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "direction": self.direction.value,
            "detected_at": self.detected_at.isoformat(),
            "quality": self.quality,
            "key_levels": [lv.to_dict() for lv in self.key_levels],
            "invalidation": self.invalidation,
            "targets": list(self.targets),
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Evidence:
        ev = cls(
            detector_id=d["detector_id"],
            detector_version=int(d["detector_version"]),
            family=Family(d["family"]),
            tier=Tier(d["tier"]),
            name=d["name"],
            i18n_key=d["i18n_key"],
            symbol=d["symbol"],
            timeframe=Timeframe(d["timeframe"]),
            direction=Direction(d["direction"]),
            detected_at=datetime.fromisoformat(d["detected_at"]),
            quality=float(d["quality"]),
            key_levels=tuple(KeyLevel.from_dict(x) for x in d["key_levels"]),
            invalidation=None if d["invalidation"] is None else float(d["invalidation"]),
            targets=tuple(float(x) for x in d["targets"]),
            details=tuple(sorted(d["details"].items())),
        )
        if d.get("evidence_id") not in (None, ev.evidence_id):
            raise EvidenceError(f"evidence id mismatch for {ev.detector_id}: stored record was altered")
        return ev


@dataclass(frozen=True, slots=True)
class ActiveEvidence:
    evidence: Evidence
    as_of: datetime  # close time of the bar the evaluation was made at
    age_bars: int  # bars since detection (0 = detected on the evaluation bar)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence": self.evidence.to_dict(),
            "as_of": self.as_of.isoformat(),
            "age_bars": self.age_bars,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ActiveEvidence:
        return cls(Evidence.from_dict(d["evidence"]), datetime.fromisoformat(d["as_of"]), int(d["age_bars"]))


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    """What was known at ``as_of``. Stored with each opportunity and never updated afterwards."""

    symbol: str
    timeframe: Timeframe
    as_of: datetime
    items: tuple[ActiveEvidence, ...]
    detectors: tuple[tuple[str, int], ...]  # (detector_id, version) of every detector that produced output
    params_digest: str  # hash of the detector parameters in effect

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "as_of": self.as_of.isoformat(),
            "items": [item.to_dict() for item in self.items],
            "detectors": [list(d) for d in self.detectors],
            "params_digest": self.params_digest,
        }

    def to_json(self) -> str:
        """Canonical JSON (sorted keys, no whitespace): equal snapshots serialize to equal bytes."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def digest(self) -> str:
        return stable_hash(self.to_json())

    @classmethod
    def from_json(cls, text: str, expected_digest: str | None = None) -> EvidenceSnapshot:
        d = json.loads(text)
        snap = cls(
            symbol=d["symbol"],
            timeframe=Timeframe(d["timeframe"]),
            as_of=datetime.fromisoformat(d["as_of"]),
            items=tuple(ActiveEvidence.from_dict(x) for x in d["items"]),
            detectors=tuple((str(i), int(v)) for i, v in d["detectors"]),
            params_digest=d["params_digest"],
        )
        if expected_digest is not None and snap.digest != expected_digest:
            raise EvidenceError("evidence snapshot digest mismatch: the stored snapshot was altered")
        return snap


# --- detectors --------------------------------------------------------------------------------------------


class DetectorParams(BaseModel):
    """Base parameter model; detectors subclass it with bounded fields (unknown keys are rejected)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_age_bars: int = Field(default=3, ge=0, le=500)


class Detector(ABC):
    """A technical theory. Subclasses set the class attributes and implement :meth:`scan`."""

    id: ClassVar[str]
    name: ClassVar[str]
    family: ClassVar[Family]
    tier: ClassVar[Tier]
    version: ClassVar[int] = 1
    Params: ClassVar[type[DetectorParams]] = DetectorParams
    # detectors whose scan output this one reads through ``ctx.results`` (run first, even if not enabled)
    depends_on: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def scan(self, ctx: EvidenceContext, params: Any) -> list[Evidence]:
        """Every instance in the frame, each using only bars up to its own ``detected_at``."""

    def make(
        self,
        ctx: EvidenceContext,
        pos: int,
        direction: Direction,
        quality: float,
        *,
        key_levels: Iterable[KeyLevel] = (),
        invalidation: float | None = None,
        targets: Iterable[float] = (),
        details: Mapping[str, DetailValue] | None = None,
        variant: str | None = None,
    ) -> Evidence:
        """Build an evidence record detected at bar *pos*. ``variant`` refines the name and i18n key."""
        suffix = f".{variant}" if variant else ""
        return Evidence(
            detector_id=self.id,
            detector_version=self.version,
            family=self.family,
            tier=self.tier,
            name=f"{self.name} ({variant})" if variant else self.name,
            i18n_key=f"evidence.{self.id}{suffix}",
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            direction=direction,
            detected_at=ctx.time_at(pos),
            quality=float(min(1.0, max(0.0, quality))),
            key_levels=tuple(key_levels),
            invalidation=invalidation,
            targets=tuple(float(t) for t in targets),
            details=tuple(sorted((details or {}).items())),
        )


# --- context ----------------------------------------------------------------------------------------------

REQUIRED_COLUMNS = ("open", "high", "low", "close", "close_time")


@dataclass
class EvidenceContext:
    """One symbol/timeframe frame of **closed** candles plus memoized shared computations.

    Series are indexed by bar close time, so swing ``pivot_at``/``confirm_at`` are UTC timestamps that stay
    stable across re-fetches (positions do not).
    """

    symbol: str
    timeframe: Timeframe
    candles: pd.DataFrame
    config: EvidenceConfig = field(default_factory=EvidenceConfig)
    times: pd.DatetimeIndex = field(init=False, repr=False)
    open: pd.Series = field(init=False, repr=False)
    high: pd.Series = field(init=False, repr=False)
    low: pd.Series = field(init=False, repr=False)
    close: pd.Series = field(init=False, repr=False)
    volume: pd.Series = field(init=False, repr=False)
    # the same columns as numpy arrays, for detector loops
    o: FloatArray = field(init=False, repr=False)
    h: FloatArray = field(init=False, repr=False)
    l: FloatArray = field(init=False, repr=False)  # noqa: E741
    c: FloatArray = field(init=False, repr=False)
    v: FloatArray = field(init=False, repr=False)
    _memo: dict[tuple[object, ...], Any] = field(default_factory=dict, init=False, repr=False)
    _results: dict[str, list[Evidence]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        missing = [c for c in REQUIRED_COLUMNS if c not in self.candles.columns]
        if missing:
            raise EvidenceError(f"evidence context needs columns {missing}")
        times = pd.DatetimeIndex(self.candles["close_time"])
        if times.tz is None:
            raise EvidenceError("close_time must be timezone-aware UTC")
        times = times.tz_convert("UTC")
        if len(times) and not (times.is_monotonic_increasing and times.is_unique):
            raise EvidenceError("candles must be in strictly increasing close_time order")
        df = self.candles.reset_index(drop=True)
        self.times = times
        self.open = pd.Series(df["open"].to_numpy(dtype=float), index=times, name="open")
        self.high = pd.Series(df["high"].to_numpy(dtype=float), index=times, name="high")
        self.low = pd.Series(df["low"].to_numpy(dtype=float), index=times, name="low")
        self.close = pd.Series(df["close"].to_numpy(dtype=float), index=times, name="close")
        vol = df["tick_volume"].to_numpy(dtype=float) if "tick_volume" in df else np.full(len(df), np.nan)
        self.volume = pd.Series(vol, index=times, name="tick_volume")
        self.o, self.h, self.l, self.c = (s.to_numpy() for s in (self.open, self.high, self.low, self.close))
        self.v = vol

    @property
    def n(self) -> int:
        return len(self.times)

    @property
    def last_pos(self) -> int:
        return self.n - 1

    @property
    def as_of(self) -> datetime:
        if self.n == 0:
            raise EvidenceError("empty evidence context has no as-of time")
        return self.time_at(self.last_pos)

    def time_at(self, pos: int) -> datetime:
        return pd.Timestamp(self.times[pos]).to_pydatetime()

    def pos_of(self, at: datetime) -> int:
        pos = int(self.times.searchsorted(pd.Timestamp(ensure_utc(at))))
        if pos >= self.n or self.time_at(pos) != ensure_utc(at):
            raise EvidenceError(f"{at.isoformat()} is not a bar close time of this frame")
        return pos

    def memo(self, key: tuple[object, ...], compute: Callable[[], T]) -> T:
        if key not in self._memo:
            self._memo[key] = compute()
        value: T = self._memo[key]
        return value

    # shared computations ---------------------------------------------------------------------------------

    def atr(self, n: int | None = None) -> pd.Series:
        period = n or self.config.atr_period
        return self.memo(("atr", period), lambda: atr(self.high, self.low, self.close, period))

    def atr_array(self, n: int | None = None) -> FloatArray:
        period = n or self.config.atr_period
        return self.memo(("atr_array", period), lambda: self.atr(period).to_numpy(dtype=np.float64))

    def ema_array(self, n: int) -> FloatArray:
        return self.memo(("ema", n), lambda: ema(self.close, n).to_numpy(dtype=np.float64))

    def zigzag(self, degree: str) -> list[Swing]:
        if degree not in self.config.zigzag_degrees:
            raise ConfigError(
                f"unknown zigzag degree {degree!r}; configured: {sorted(self.config.zigzag_degrees)}"
            )
        multiple = self.config.zigzag_degrees[degree]
        return self.memo(("zigzag", degree), lambda: zigzag(self.high, self.low, self.atr(), multiple))

    def swings(self, k: int) -> list[Swing]:
        return self.memo(("swings", k), lambda: find_swings(self.high, self.low, k))

    def results(self, detector_id: str) -> list[Evidence]:
        """Scan output of a prerequisite detector (declared in ``depends_on``)."""
        if detector_id not in self._results:
            raise EvidenceError(f"{detector_id} has not run; declare it in depends_on")
        return self._results[detector_id]

    def store_results(self, detector_id: str, evidence: list[Evidence]) -> None:
        self._results[detector_id] = evidence

    def prefix(self, last_pos: int) -> EvidenceContext:
        """The same frame cut after *last_pos* (fresh memo): what was known at that bar."""
        return EvidenceContext(self.symbol, self.timeframe, self.candles.iloc[: last_pos + 1], self.config)


# --- activation -------------------------------------------------------------------------------------------


def activate(
    ctx: EvidenceContext, evidence: Sequence[Evidence], max_age_bars: Mapping[str, int]
) -> list[ActiveEvidence]:
    """Evidence still in force at the last bar of *ctx*.

    An instance is active when it is at most ``max_age_bars[detector_id]`` bars old and no close since its
    detection has crossed its invalidation level against its direction (closes, not wicks: a wick through a
    level is a probe, a close is a decision).
    """
    if ctx.n == 0:
        return []
    closes = ctx.close.to_numpy()
    as_of, last = ctx.as_of, ctx.last_pos
    out: list[ActiveEvidence] = []
    for ev in evidence:
        pos = ctx.pos_of(ev.detected_at)
        age = last - pos
        if age > max_age_bars.get(ev.detector_id, 0):
            continue
        if ev.invalidation is not None and age > 0:
            after = closes[pos + 1 : last + 1]
            if ev.direction is Direction.BULL and (after < ev.invalidation).any():
                continue
            if ev.direction is Direction.BEAR and (after > ev.invalidation).any():
                continue
        out.append(ActiveEvidence(ev, as_of, age))
    out.sort(key=lambda a: (a.evidence.family, a.evidence.detector_id, a.evidence.detected_at))
    return out
