"""Which signal a manual MT5 trade followed (PLAN §A34; TAA-1006). Pure and deterministic.

The owner trades by hand next to the engine, following the signals it shows. MT5 only says such a position is
not the bot's (magic outside its range), so the engine matches it to a signal by itself:

- **Candidates:** the engine's accepted EXECUTION decisions and the ADVISORY opportunities, same symbol and
  side. One signal seen by both (same idempotency key) is one candidate.
- **Time:** opened between the signal's bar close and its expiry plus :data:`GRACE_BARS` bars.
- **Price:** the open price within ``tolerance_r`` × the signal's stop distance of its entry.
- **Score:** closeness in price (60 %) and in time (40 %); the best candidate wins.
- **Confidence:** HIGH when exactly one signal qualifies, LIKELY when several do (the best one is kept),
  UNMATCHED when none does: a manual idea of the owner's own.

Matching never changes trading: manual positions count toward the bot's limits either way.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.core.clock import ensure_utc
from app.core.enums import Side

RULE_VERSION = "1"
GRACE_BARS = 1
DEFAULT_TOLERANCE_R = 0.5
PRICE_WEIGHT = 0.6


class Confidence(StrEnum):
    HIGH = "HIGH"
    LIKELY = "LIKELY"
    UNMATCHED = "UNMATCHED"


@dataclass(frozen=True, slots=True)
class SignalCandidate:
    key: str  # the signal's idempotency key (strategy/symbol/bar/side): one signal, however many records
    symbol: str
    side: Side
    entry: float
    stop: float
    issued_at: datetime  # the signal's bar close (or its decision time)
    expires_at: datetime
    bar_seconds: int
    strategy: str
    decision_id: str | None = None  # the engine's EXECUTION decision, when the bot saw it too
    opportunity_id: str | None = None  # the advisory opportunity, when an alert showed it


@dataclass(frozen=True, slots=True)
class ManualFill:
    position_id: int
    symbol: str
    side: Side
    price_open: float
    opened_at: datetime


@dataclass(frozen=True, slots=True)
class Match:
    confidence: Confidence
    candidate: SignalCandidate | None = None
    score: float | None = None
    distance_r: float | None = None  # |open − entry| in units of the signal's stop distance
    candidates: int = 0  # how many signals qualified


def merge(candidates: Iterable[SignalCandidate]) -> list[SignalCandidate]:
    """One candidate per signal key: the EXECUTION decision and the opportunity of the same signal merge."""
    out: dict[str, SignalCandidate] = {}
    for c in candidates:
        seen = out.get(c.key)
        if seen is None:
            out[c.key] = c
            continue
        out[c.key] = SignalCandidate(
            key=c.key,
            symbol=c.symbol,
            side=c.side,
            entry=seen.entry,
            stop=seen.stop,
            issued_at=min(seen.issued_at, c.issued_at),
            expires_at=max(seen.expires_at, c.expires_at),
            bar_seconds=seen.bar_seconds,
            strategy=seen.strategy,
            decision_id=seen.decision_id or c.decision_id,
            opportunity_id=seen.opportunity_id or c.opportunity_id,
        )
    return list(out.values())


def _score(fill: ManualFill, c: SignalCandidate, tolerance_r: float) -> tuple[float, float] | None:
    risk = abs(c.entry - c.stop)
    if c.symbol != fill.symbol or c.side is not fill.side or risk <= 0:
        return None
    opened = ensure_utc(fill.opened_at)
    start, end = (
        ensure_utc(c.issued_at),
        ensure_utc(c.expires_at) + timedelta(seconds=GRACE_BARS * c.bar_seconds),
    )
    if not start <= opened <= end:
        return None
    distance = abs(fill.price_open - c.entry) / risk
    if distance > tolerance_r:
        return None
    window = max((end - start).total_seconds(), 1.0)
    late = (opened - start).total_seconds() / window
    score = PRICE_WEIGHT * (1 - distance / tolerance_r) + (1 - PRICE_WEIGHT) * (1 - late)
    return round(score, 4), round(distance, 4)


def match(
    fill: ManualFill, candidates: Sequence[SignalCandidate], *, tolerance_r: float = DEFAULT_TOLERANCE_R
) -> Match:
    scored = []
    for c in merge(candidates):
        result = _score(fill, c, tolerance_r)
        if result is not None:
            scored.append((result[0], result[1], c))
    if not scored:
        return Match(Confidence.UNMATCHED)
    scored.sort(key=lambda t: (-t[0], t[1], t[2].key))
    score, distance, best = scored[0]
    confidence = Confidence.HIGH if len(scored) == 1 else Confidence.LIKELY
    return Match(confidence, best, score, distance, len(scored))


@dataclass(frozen=True, slots=True)
class Ranked:
    candidate: SignalCandidate
    qualifies: bool  # within the time window and the price tolerance
    score: float | None
    distance_r: float | None


def rank(
    fill: ManualFill, candidates: Sequence[SignalCandidate], *, tolerance_r: float = DEFAULT_TOLERANCE_R
) -> list[Ranked]:
    """Every signal on the fill's symbol and side, for the owner to pick from: the qualifying ones first (best
    score first), then the rest by price distance."""
    out: list[Ranked] = []
    for c in merge(candidates):
        if c.symbol != fill.symbol or c.side is not fill.side:
            continue
        risk = abs(c.entry - c.stop)
        result = _score(fill, c, tolerance_r)
        distance = round(abs(fill.price_open - c.entry) / risk, 4) if risk > 0 else None
        out.append(Ranked(c, result is not None, None if result is None else result[0], distance))
    out.sort(
        key=lambda r: (not r.qualifies, -(r.score or 0.0), r.distance_r or float("inf"), r.candidate.key)
    )
    return out
