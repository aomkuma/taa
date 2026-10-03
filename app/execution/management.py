"""Position-management rules (PLAN §A11), shared by the backtester and the PAPER position manager (TAA-603).

Evaluated on closed bars only; a change applies from the next bar on.

- **Break-even:** once the position is ``break_even_trigger_r`` R in profit, the stop moves to the entry plus
  ``break_even_buffer_points`` (costs), on the profitable side.
- **Trailing:** from ``trailing_start_r`` R, the stop trails ``trailing_atr_multiple`` × ATR behind the mark.
- **Invariants:** the stop only ever moves in the favourable direction, never through the current price, never
  removed, and by at least ``min_sl_step_points`` per change.
- **Time stop:** after ``time_stop_bars`` bars the position is closed (``TIME``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import PositionManagementConfig
from app.core.enums import ExitReason, Side


@dataclass(frozen=True, slots=True)
class PositionView:
    side: Side
    entry: float
    initial_sl: float
    sl: float
    bars_held: int


@dataclass(frozen=True, slots=True)
class Adjustment:
    new_sl: float | None = None
    stop_kind: ExitReason | None = None  # BREAK_EVEN or TRAILING_STOP: how a later stop-out is labelled
    close: ExitReason | None = None
    note: str = ""


def manage(
    pos: PositionView,
    *,
    mark: float,
    atr: float | None,
    point: float,
    cfg: PositionManagementConfig,
) -> Adjustment:
    """*mark* is the price the position would close at now (bid for BUY, ask for SELL)."""
    if cfg.time_stop_bars is not None and pos.bars_held >= cfg.time_stop_bars:
        return Adjustment(close=ExitReason.TIME_STOP, note=f"held {pos.bars_held} bars")
    sign = pos.side.sign
    risk = abs(pos.entry - pos.initial_sl)
    if risk <= 0:
        return Adjustment()
    gain_r = (mark - pos.entry) * sign / risk
    best, kind, note = pos.sl, None, ""
    if gain_r >= cfg.break_even_trigger_r:
        be = pos.entry + sign * cfg.break_even_buffer_points * point
        if (be - best) * sign > 0:
            best, kind, note = be, ExitReason.BREAK_EVEN, f"break-even at +{gain_r:.2f}R"
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
