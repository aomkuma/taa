"""Signal arbitration for one symbol at one decision bar (PLAN §A7).

Order of the rules (each suppressed signal keeps the reason code it was suppressed with):

1. **One signal per strategy, symbol and bar.** A second signal from the same strategy for the same bar, or
   a signal whose idempotency key was already arbitrated (e.g. a re-evaluation after a restart), is
   ``DUPLICATE_SIGNAL``.
2. **Cooldown.** After a strategy's entry signal is selected on a symbol, its further entry signals on that
   symbol are ``COOLDOWN_ACTIVE`` until ``cooldown_bars`` entry bars have passed.
3. **Conflict.** BUY and SELL candidates on the same symbol and bar cancel out: nothing is selected and every
   candidate is ``CONFLICT`` (fail closed: disagreement is not a reason to pick a side).
4. **Ranking.** Among same-direction candidates the highest :func:`rank_key` wins; the rest are
   ``LOWER_RANK``.

An existing opposite position is never reversed here; that is the decision engine's portfolio check.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.core.clock import ensure_utc
from app.strategy.signal_models import ReasonCode, Signal, SignalError

MAX_REMEMBERED_KEYS = 50_000


class Outcome(StrEnum):
    SELECTED = "SELECTED"
    SUPPRESSED = "SUPPRESSED"
    HOLD = "HOLD"  # the strategy itself held


@dataclass(frozen=True, slots=True)
class ArbitratedSignal:
    signal: Signal
    outcome: Outcome
    reason: ReasonCode | None = None


@dataclass(frozen=True, slots=True)
class Arbitration:
    selected: Signal | None
    results: tuple[ArbitratedSignal, ...]

    @property
    def reason_codes(self) -> tuple[str, ...]:
        """Why nothing was selected (empty when a signal was)."""
        if self.selected is not None:
            return ()
        reasons = sorted({r.reason.value for r in self.results if r.reason is not None})
        return tuple(reasons) or (ReasonCode.NO_SETUP.value,)


def rank_key(signal: Signal) -> tuple[float, float, float, str]:
    """Sort key, best first: score, then setup strength, then RR; the strategy name breaks exact ties."""
    return (-signal.score, -signal.setup_strength, -(signal.risk_reward or 0.0), signal.strategy)


def rank(signals: Iterable[Signal]) -> list[Signal]:
    """Entry signals best first (also used to order candidates across symbols)."""
    return sorted((s for s in signals if s.is_entry), key=rank_key)


@dataclass
class SignalArbiter:
    cooldown_bars: int
    _last_selected: dict[tuple[str, str], datetime] = field(default_factory=dict)
    _seen: set[str] = field(default_factory=set)
    _seen_order: deque[str] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be >= 0")

    def in_cooldown(self, signal: Signal) -> bool:
        last = self._last_selected.get((signal.strategy, signal.symbol))
        if last is None or self.cooldown_bars == 0:
            return False
        bars = (signal.data_timestamp_utc - last).total_seconds() / signal.timeframe.seconds
        return bars < self.cooldown_bars

    def arbitrate(self, signals: Sequence[Signal]) -> Arbitration:
        if not signals:
            return Arbitration(None, ())
        first = signals[0]
        for s in signals:
            if s.symbol != first.symbol or s.data_timestamp_utc != first.data_timestamp_utc:
                raise SignalError("arbitration takes the signals of one symbol at one bar")

        results: dict[int, ArbitratedSignal] = {}
        strategies_seen: set[str] = set()
        candidates: list[tuple[int, Signal]] = []
        for i, s in enumerate(signals):
            if s.strategy in strategies_seen or s.idempotency_key in self._seen:
                results[i] = ArbitratedSignal(s, Outcome.SUPPRESSED, ReasonCode.DUPLICATE_SIGNAL)
                continue
            strategies_seen.add(s.strategy)
            if not s.is_entry:
                results[i] = ArbitratedSignal(s, Outcome.HOLD)
            elif self.in_cooldown(s):
                results[i] = ArbitratedSignal(s, Outcome.SUPPRESSED, ReasonCode.COOLDOWN_ACTIVE)
            else:
                candidates.append((i, s))

        selected: Signal | None = None
        if len({s.action for _, s in candidates}) > 1:
            for i, s in candidates:
                results[i] = ArbitratedSignal(s, Outcome.SUPPRESSED, ReasonCode.CONFLICT)
        elif candidates:
            best_i, selected = min(candidates, key=lambda p: rank_key(p[1]))
            for i, s in candidates:
                if i == best_i:
                    results[i] = ArbitratedSignal(s, Outcome.SELECTED)
                else:
                    results[i] = ArbitratedSignal(s, Outcome.SUPPRESSED, ReasonCode.LOWER_RANK)

        for s in signals:
            self._remember(s.idempotency_key)
        if selected is not None:
            self._last_selected[(selected.strategy, selected.symbol)] = selected.data_timestamp_utc
        return Arbitration(selected, tuple(results[i] for i in range(len(signals))))

    def _remember(self, key: str) -> None:
        if key in self._seen:
            return
        self._seen.add(key)
        self._seen_order.append(key)
        while len(self._seen_order) > MAX_REMEMBERED_KEYS:
            self._seen.discard(self._seen_order.popleft())

    # persistence (restart safety, TAA-604) --------------------------------------------------------------

    def cooldown_state(self) -> dict[str, str]:
        return {f"{k[0]}|{k[1]}": t.isoformat() for k, t in sorted(self._last_selected.items())}

    def restore_cooldowns(self, state: dict[str, str]) -> None:
        for key, at in state.items():
            strategy, _, symbol = key.partition("|")
            self._last_selected[(strategy, symbol)] = ensure_utc(datetime.fromisoformat(at))
