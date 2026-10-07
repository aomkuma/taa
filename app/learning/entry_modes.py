"""Entry-mode shadow variants (PLAN_LEARNING §L19.3; TAA-L702): the same signal entered another way.

Measurement only: these rows sit beside ``PLAN`` and ``MANAGED`` in ``shadow_trades`` and never change what
the bot trades. Every variant keeps the signal's direction and its **TP price**; the stop and the entry
change, and the lot follows the stop so the money at risk stays the plan's (floored to the volume step; below
the minimum the row is tracked in R only, like any untradable opportunity).

Distances are in risks ``r`` of the signal's own stop (its fill to the plan's SL):

| Variant | Entry | Stop |
|---|---|---|
| ``WIDE_STOP`` | at the signal (the PLAN fill) | ``wide_stop_mult`` × r from the fill |
| ``PULLBACK`` | a limit ``pullback_depth_r`` × r against the signal | the plan's SL |
| ``PULLBACK_WIDE`` | the same limit | ``pullback_wide_stop_r`` × r from the signal's fill |

The fixed multiples come from the setup review (docs/SETUP_REVIEW.md §8). The design's "learned" depths (the
winners' MAE quantiles) are not used yet: a winner's MAE is censored at its own stop, so its quantiles can
never place a stop beyond the plan's. A learned version needs the uncensored excursion (the research harness
measures it on bars, TAA-L707) and comes with TAA-L706.

**Waiting entries.** A limit row starts ``PENDING`` with ``entry_price`` = the limit. On closed bars from the
signal: it fills when the entry-side price reaches the limit (a BUY limit when the ask low ``low + spread`` is
at or below it, a SELL limit when the bid high is at or above it), always at the limit (never better). The
fill bar holds prices from before the fill, so on it only a stop touch counts (like the resolver's partial
entry bar); resolution continues from the next bar with :func:`app.advisory.shadow.advance`. A limit not
filled before ``entry_window_end`` is ``MISSED`` (no trade). The time stop stays the signal's, so every
variant has the same horizon.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.advisory.shadow import Flag, ShadowExit, ShadowState, Variant
from app.config import EntryModesConfig
from app.core.decimal_utils import floor_to_step
from app.core.enums import ExitReason, Side
from app.execution.fill_model import Bar

WAITING = frozenset({Variant.PULLBACK, Variant.PULLBACK_WIDE})


@dataclass(frozen=True, slots=True)
class EntryGeometry:
    variant: Variant
    entry: float  # the fill, or the limit while waiting
    sl: float
    tp: float | None
    lot: float | None
    window_end: datetime | None  # waiting variants only


def configured(cfg: EntryModesConfig) -> list[Variant]:
    return [Variant(v) for v in cfg.variants]


def geometry(
    variant: Variant,
    *,
    side: Side,
    fill: float,
    plan_sl: float,
    tp: float | None,
    lot: float | None,
    entry_at: datetime,
    bar_seconds: int,
    cfg: EntryModesConfig,
    volume_step: float,
    volume_min: float,
) -> EntryGeometry:
    """The variant's entry, stop and lot from the PLAN fill; an invalid plan geometry passes through."""
    sign = side.sign
    risk = (fill - plan_sl) * sign
    if risk <= 0:
        return EntryGeometry(variant, fill, plan_sl, tp, lot, None)
    entry, sl, window_end = fill, plan_sl, None
    if variant is Variant.WIDE_STOP:
        sl = fill - sign * cfg.wide_stop_mult * risk
    elif variant in WAITING:
        entry = fill - sign * cfg.pullback_depth_r * risk
        window_end = entry_at + timedelta(seconds=bar_seconds * cfg.entry_window_bars)
        if variant is Variant.PULLBACK_WIDE:
            sl = fill - sign * cfg.pullback_wide_stop_r * risk
    else:
        raise ValueError(f"not an entry mode: {variant}")
    return EntryGeometry(
        variant, entry, sl, tp, _lot(lot, risk, (entry - sl) * sign, volume_step, volume_min), window_end
    )


def _lot(lot: float | None, plan_risk: float, risk: float, step: float, minimum: float) -> float | None:
    """The plan's money at risk on the variant's stop, floored to the step; None below the minimum."""
    if lot is None or risk <= 0 or step <= 0:
        return None
    sized = float(floor_to_step(lot * plan_risk / risk, step))
    return sized if sized >= minimum else None


@dataclass(frozen=True, slots=True)
class Waiting:
    """What happened to a PENDING limit over some bars."""

    filled: bool
    missed: bool
    exit: ShadowExit | None  # a stop on the fill bar


def await_fill(state: ShadowState, bars: Iterable[Bar], *, window_end: datetime, slippage: float) -> Waiting:
    """Advance a PENDING *state* (``entry`` = the limit) until it fills, is missed or the bars end.

    On a fill the state's ``entry_at`` and ``cursor`` move to the fill bar (resolution continues after it).
    """
    sign = state.side.sign
    limit = state.entry
    for bar in bars:
        if bar.open_time < state.cursor:
            continue
        if bar.open_time >= window_end:
            state.cursor = bar.open_time
            return Waiting(False, True, None)
        if state.side is Side.BUY:
            reached = bar.low + bar.spread <= limit  # the ask
            adverse = bar.low  # a BUY exits at the bid
        else:
            reached = bar.high >= limit  # the bid
            adverse = bar.high + bar.spread  # a SELL exits at the ask
        state.cursor = bar.close_time
        if not reached:
            continue
        state.entry_at = bar.open_time
        state.flags.add(Flag.PARTIAL_BAR)
        if (adverse - state.sl) * sign <= 0:
            state.mae = max(state.mae, (limit - state.sl) * sign)
            return Waiting(
                True, False, ShadowExit(ExitReason.STOP_LOSS, state.sl - sign * slippage, bar.open_time)
            )
        state.excursion(adverse, limit)
        return Waiting(True, False, None)
    return Waiting(False, False, None)
