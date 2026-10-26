"""The shared position-management rules (app/execution/management.py): break-even on a touch (owner 2026-10-25)."""

from __future__ import annotations

from app.config import PositionManagementConfig, StrategyManagement
from app.core.enums import ExitReason, Side
from app.execution.management import PositionView, manage

BUY = PositionView(Side.BUY, entry=4000.0, initial_sl=3990.0, sl=3990.0, bars_held=3)


def test_break_even_on_a_touch_uses_the_best_price_since_the_last_call():
    # risk 10: the bar closed at 4009.6 (+0.96 R) but its high touched 4012.6 (+1.26 R) - the 07-07 07:15 case
    close_only = PositionManagementConfig(break_even_buffer_points=0, min_sl_step_points=0)
    assert manage(BUY, mark=4009.6, atr=None, point=0.01, cfg=close_only, reach=4012.6).new_sl is None
    touch = close_only.model_copy(update={"break_even_on_touch": True})
    adj = manage(BUY, mark=4009.6, atr=None, point=0.01, cfg=touch, reach=4012.6)
    assert (
        adj.new_sl == 4000.0 and adj.stop_kind is ExitReason.BREAK_EVEN and adj.note == "break-even at +1.26R"
    )
    assert manage(BUY, mark=4009.6, atr=None, point=0.01, cfg=touch, reach=4009.9).new_sl is None  # +0.99 R
    assert manage(BUY, mark=4010.0, atr=None, point=0.01, cfg=touch).new_sl == 4000.0  # live: the quote


def test_the_touch_is_set_per_strategy():
    cfg = PositionManagementConfig(by_strategy={"ai_trader": StrategyManagement(break_even_on_touch=True)})
    assert cfg.for_strategy("ai_trader").break_even_on_touch is True
    assert cfg.for_strategy("other").break_even_on_touch is False
