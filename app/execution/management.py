"""Position-management rules (PLAN §A11), shared by the backtester and the PAPER position manager (TAA-603).

Evaluated on closed bars only; a change applies from the next bar on.

- **Break-even:** once the position is ``break_even_trigger_r`` R in profit, the stop moves to the entry plus
  ``break_even_buffer_points`` (costs), on the profitable side. With ``break_even_target_share`` the trigger
  is instead that share of the way to the take-profit, reached by the best price since the last call (Setup
  OWN: 0.6 of a fixed target, whatever the stop; docs/OWN_SETUP.md).
- **Trailing:** from ``trailing_start_r`` R, the stop trails ``trailing_atr_multiple`` × ATR behind the mark.
- **Invariants:** the stop only ever moves in the favourable direction, never through the current price, never
  removed, and by at least ``min_sl_step_points`` per change.
- **Time stop:** after ``time_stop_bars`` bars the position is closed (``TIME``).
- **Entry plans** (PLAN §A31, TAA-1207): once another part of the same plan has closed (a SAME_PRICE part at
  its earlier target), the remaining parts' stops move to break-even (:func:`plan_break_even`), whichever of
  that and the rules above is the better stop.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import PositionManagementConfig
from app.core.enums import ExitReason, Side
from app.strategy.signal_models import PositionAdvice


@dataclass(frozen=True, slots=True)
class PositionView:
    side: Side
    entry: float
    initial_sl: float
    sl: float
    bars_held: int
    tp: float | None = None  # for ``break_even_target_share``


@dataclass(frozen=True, slots=True)
class Adjustment:
    new_sl: float | None = None
    stop_kind: ExitReason | None = None  # BREAK_EVEN or TRAILING_STOP: how a later stop-out is labelled
    close: ExitReason | None = None
    note: str = ""


def plan_break_even(
    pos: PositionView, *, mark: float, point: float, cfg: PositionManagementConfig
) -> Adjustment:
    """Break-even after another part of the position's entry plan closed. Favourable only, never through the
    current price."""
    sign = pos.side.sign
    be = pos.entry + sign * cfg.break_even_buffer_points * point
    if (be - pos.sl) * sign <= 0 or (mark - be) * sign <= 0:
        return Adjustment()
    return Adjustment(
        new_sl=be, stop_kind=ExitReason.BREAK_EVEN, note="break-even: another part of the plan has closed"
    )


def from_advice(advice: PositionAdvice | None, side: Side, *, mark: float, sl: float) -> Adjustment | None:
    """A strategy's own advice (``BaseStrategy.manage_position``) as an adjustment: a stop that is not
    favourable is dropped; one already through the current price closes at market (a stop there would be
    refused), labelled as the stop."""
    if advice is None:
        return None
    if advice.close is not None:
        return Adjustment(close=advice.close, note=advice.note)
    if advice.new_sl is None or (advice.new_sl - sl) * side.sign <= 0:
        return None
    if (mark - advice.new_sl) * side.sign <= 0:
        return Adjustment(
            close=advice.stop_kind or ExitReason.SIGNAL, note=f"{advice.note} (through the price)"
        )
    return Adjustment(new_sl=advice.new_sl, stop_kind=advice.stop_kind, note=advice.note)


def with_advice(side: Side, rules: Adjustment, own: Adjustment | None) -> Adjustment:
    """The configured rules' adjustment and the strategy's: a close wins, else the more favourable stop."""
    if own is None or rules.close is not None:
        return rules
    if own.close is not None:
        return own
    return better_stop(side, rules, own)


def better_stop(side: Side, first: Adjustment, second: Adjustment) -> Adjustment:
    """The adjustment with the more favourable stop (a close always wins)."""
    if first.close is not None or second.new_sl is None:
        return first
    if first.new_sl is None or (second.new_sl - first.new_sl) * side.sign > 0:
        return second
    return first


def manage(
    pos: PositionView,
    *,
    mark: float,
    atr: float | None,
    point: float,
    cfg: PositionManagementConfig,
    reach: float | None = None,
) -> Adjustment:
    """*mark* is the price the position would close at now (bid for BUY, ask for SELL); *reach* the best such
    price since the last call (a bar's high for a BUY, its ask low for a SELL), None: the mark."""
    if cfg.time_stop_bars is not None and pos.bars_held >= cfg.time_stop_bars:
        return Adjustment(close=ExitReason.TIME_STOP, note=f"held {pos.bars_held} bars")
    sign = pos.side.sign
    risk = abs(pos.entry - pos.initial_sl)
    if risk <= 0:
        return Adjustment()
    gain_r = (mark - pos.entry) * sign / risk
    best, kind, note = pos.sl, None, ""
    to_target = None if pos.tp is None else (pos.tp - pos.entry) * sign
    share = cfg.break_even_target_share
    by_target = (
        share is not None
        and to_target is not None
        and to_target > 0
        and ((mark if reach is None else reach) - pos.entry) * sign >= share * to_target
    )
    if gain_r >= cfg.break_even_trigger_r or by_target:
        be = pos.entry + sign * cfg.break_even_buffer_points * point
        if (be - best) * sign > 0:
            why = f"{share:g} of the target" if by_target else f"+{gain_r:.2f}R"
            best, kind, note = be, ExitReason.BREAK_EVEN, f"break-even at {why}"
    if gain_r >= cfg.trailing_start_r and atr is not None and atr > 0:
        trail = mark - sign * cfg.trailing_atr_multiple * atr
        if (trail - best) * sign > 0:
            best, kind, note = (
                trail,
                ExitReason.TRAILING_STOP,
                f"trail {cfg.trailing_atr_multiple:g} ATR at +{gain_r:.2f}R",
            )
    moved = (best - pos.sl) * sign
    if kind is None or moved < cfg.min_sl_step_points * point or (mark - best) * sign <= 0:
        return Adjustment()
    return Adjustment(new_sl=best, stop_kind=kind, note=note)
