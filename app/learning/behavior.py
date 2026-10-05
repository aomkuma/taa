"""Behavior report on the owner's manual trades (PLAN_LEARNING §L20.7; TAA-L808).

The system exists to cover a human trader's typical weaknesses. This module counts where the owner's manual
trades show them, next to what following the plan would have given. The wording in the PWA is descriptive,
never a grade, and every comparison is hypothetical.

Input is one :class:`ManualTrade` per closed manual position, built by the caller from ``manual_trade_links``
(TAA-1006) and the matched signal's plan. Nothing it reads is changed (§L0.2). Patterns:

- ``EARLY_EXIT``: closed in profit before the plan's take-profit, and afterwards price reached that
  take-profit before the initial stop (within the look-ahead); the difference is the plan's R minus the R
  taken.
- ``STOP_MOVED``: the stop was widened (moved against the trade) or removed after entry. Needs the stop
  history; without one the trade is not counted either way.
- ``REVENGE``: opened within ``revenge_minutes`` after a losing manual trade closed, or with more money at
  risk than that losing trade.
- ``OVERTRADING``: trades beyond ``max_trades_per_day`` on one UTC day, by opening order.
- ``OFF_PLAN``: no signal matched (``UNMATCHED``, or the owner marked it as an own idea).

For ``REVENGE``, ``OVERTRADING`` and ``OFF_PLAN`` the plan's alternative is not taking the trade, so the
difference is minus the R taken. A **comfort-zone** view compares the asset-class mix of the manual trades
with the mix of the opportunities shown in the same period (total variation distance, 0 = same mix,
1 = disjoint).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

import pandas as pd

from app.analytics.trade_builder import SCRATCH_R
from app.core.clock import ensure_utc
from app.core.enums import Side
from app.learning.timing import Touch, first_touch

REVENGE_MINUTES = 30
LOOKAHEAD = timedelta(hours=72)


class Pattern(StrEnum):
    EARLY_EXIT = "EARLY_EXIT"
    STOP_MOVED = "STOP_MOVED"
    REVENGE = "REVENGE"
    OVERTRADING = "OVERTRADING"
    OFF_PLAN = "OFF_PLAN"


@dataclass(frozen=True, slots=True)
class ManualTrade:
    position_id: int
    symbol: str
    side: Side
    opened_at: datetime
    closed_at: datetime
    price_open: float
    close_price: float
    r_multiple: float | None  # net, (close − open) / initial risk
    sl_initial: float | None
    tp_plan: float | None = None  # the matched signal's take-profit
    matched: bool = False  # a signal was followed (HIGH / LIKELY, or the owner's SIGNAL / CONFIRMED)
    risk_money: float | None = None  # money to the initial stop, when known
    asset_class: str | None = None
    stop_history: Sequence[float | None] | None = None  # stops seen after entry, in order; None = unknown


@dataclass(frozen=True, slots=True)
class BehaviorParams:
    revenge_minutes: int = REVENGE_MINUTES
    max_trades_per_day: int | None = None  # the owner's profile "max signals per day"; None = not checked
    lookahead: timedelta = LOOKAHEAD


@dataclass(frozen=True, slots=True)
class PatternStat:
    pattern: Pattern
    count: int
    considered: int  # trades the pattern could be judged on
    share: float
    delta_r: float  # Σ (R as planned − R as traded) over the flagged trades
    position_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BehaviorReport:
    trades: int
    patterns: Mapping[Pattern, PatternStat]
    class_mix: Mapping[str, float] = field(default_factory=dict)  # manual trades by asset class
    opportunity_mix: Mapping[str, float] = field(default_factory=dict)
    comfort_distance: float | None = None  # total variation distance of the two mixes


def _planned_r(t: ManualTrade) -> float | None:
    if t.sl_initial is None or t.tp_plan is None:
        return None
    risk = (t.price_open - t.sl_initial) * t.side.sign
    reward = (t.tp_plan - t.price_open) * t.side.sign
    return reward / risk if risk > 0 and reward > 0 else None


def early_exit(t: ManualTrade, bars: pd.DataFrame | None, lookahead: timedelta) -> bool | None:
    """True / False when it can be judged, None without a plan, a stop or bars."""
    planned = _planned_r(t)
    if planned is None or t.r_multiple is None or t.sl_initial is None or t.tp_plan is None:
        return None
    if t.r_multiple < SCRATCH_R or t.r_multiple >= planned - 1e-9:
        return False  # not closed in profit, or the target was taken
    if bars is None or bars.empty:
        return None
    touch = first_touch(t.side, bars, t.closed_at, lookahead, target=t.tp_plan, adverse=t.sl_initial)
    return None if touch is Touch.NEITHER else touch is Touch.TARGET


def stop_moved(t: ManualTrade) -> bool | None:
    if t.stop_history is None or t.sl_initial is None:
        return None
    initial = t.sl_initial
    return any(stop is None or (initial - stop) * t.side.sign > 1e-12 for stop in t.stop_history)


def _revenge(trades: Sequence[ManualTrade], minutes: int) -> set[int]:
    window = timedelta(minutes=minutes)
    flagged: set[int] = set()
    ordered = sorted(trades, key=lambda t: ensure_utc(t.opened_at))
    for t in ordered:
        opened = ensure_utc(t.opened_at)
        losses = [
            p
            for p in ordered
            if p.position_id != t.position_id
            and ensure_utc(p.closed_at) <= opened
            and p.r_multiple is not None
            and p.r_multiple <= -SCRATCH_R
        ]
        if not losses:
            continue
        last = max(losses, key=lambda p: ensure_utc(p.closed_at))
        soon = opened - ensure_utc(last.closed_at) <= window
        bigger = t.risk_money is not None and last.risk_money is not None and t.risk_money > last.risk_money
        if soon or bigger:
            flagged.add(t.position_id)
    return flagged


def _overtrading(trades: Sequence[ManualTrade], max_per_day: int | None) -> set[int]:
    if max_per_day is None:
        return set()
    by_day: dict[object, list[ManualTrade]] = defaultdict(list)
    for t in trades:
        by_day[ensure_utc(t.opened_at).date()].append(t)
    flagged: set[int] = set()
    for day in by_day.values():
        day.sort(key=lambda t: ensure_utc(t.opened_at))
        flagged.update(t.position_id for t in day[max_per_day:])
    return flagged


def _mix(classes: Iterable[str | None]) -> dict[str, float]:
    counts = Counter(c or "UNKNOWN" for c in classes)
    total = sum(counts.values())
    return {k: v / total for k, v in sorted(counts.items())} if total else {}


def _distance(a: Mapping[str, float], b: Mapping[str, float]) -> float | None:
    if not a or not b:
        return None
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def _stat(pattern: Pattern, flagged: Sequence[ManualTrade], considered: int, delta: float) -> PatternStat:
    return PatternStat(
        pattern,
        len(flagged),
        considered,
        len(flagged) / considered if considered else 0.0,
        round(delta, 6),
        tuple(sorted(t.position_id for t in flagged)),
    )


def report(
    trades: Sequence[ManualTrade],
    bars_for: Callable[[ManualTrade], pd.DataFrame | None],
    *,
    params: BehaviorParams | None = None,
    opportunity_classes: Iterable[str | None] = (),
) -> BehaviorReport:
    """Counts per pattern over closed manual trades. ``bars_for`` returns bid bars after a trade's close (for
    ``EARLY_EXIT``), or None. ``opportunity_classes`` lists the asset class of each opportunity shown."""
    params = params or BehaviorParams()
    rated = [t for t in trades if t.r_multiple is not None]

    early_flags = {t.position_id: early_exit(t, bars_for(t), params.lookahead) for t in rated}
    early = [t for t in rated if early_flags[t.position_id]]
    early_delta = sum((_planned_r(t) or 0.0) - (t.r_multiple or 0.0) for t in early)

    moved_flags = {t.position_id: stop_moved(t) for t in rated}
    moved = [t for t in rated if moved_flags[t.position_id]]

    def skipped(ids: set[int]) -> tuple[list[ManualTrade], float]:
        chosen = [t for t in rated if t.position_id in ids]
        return chosen, -sum(t.r_multiple or 0.0 for t in chosen)

    revenge, revenge_delta = skipped(_revenge(rated, params.revenge_minutes))
    over, over_delta = skipped(_overtrading(rated, params.max_trades_per_day))
    off, off_delta = skipped({t.position_id for t in rated if not t.matched})
    moved_delta = sum(-(t.r_multiple or 0.0) - 1.0 for t in moved if (t.r_multiple or 0.0) < -1.0)

    stats = {
        Pattern.EARLY_EXIT: _stat(
            Pattern.EARLY_EXIT, early, sum(1 for v in early_flags.values() if v is not None), early_delta
        ),
        Pattern.STOP_MOVED: _stat(
            Pattern.STOP_MOVED, moved, sum(1 for v in moved_flags.values() if v is not None), moved_delta
        ),
        Pattern.REVENGE: _stat(Pattern.REVENGE, revenge, len(rated), revenge_delta),
        Pattern.OVERTRADING: _stat(
            Pattern.OVERTRADING, over, len(rated) if params.max_trades_per_day is not None else 0, over_delta
        ),
        Pattern.OFF_PLAN: _stat(Pattern.OFF_PLAN, off, len(rated), off_delta),
    }
    trade_mix = _mix(t.asset_class for t in rated)
    opp_mix = _mix(opportunity_classes)
    return BehaviorReport(
        trades=len(rated),
        patterns=stats,
        class_mix=trade_mix,
        opportunity_mix=opp_mix,
        comfort_distance=_distance(trade_mix, opp_mix),
    )
