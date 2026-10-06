"""Broker position management for the DEMO account (PLAN §A11; TAA-1205).

The same A11 rules as the PAPER manager (:mod:`app.execution.management`), applied to real broker positions
that carry the bot's magic and belong to a known intent (strays are the reconciler's business):

- **SL/TP changes** go through ``order_send`` (``TRADE_ACTION_SLTP``). A change is skipped, not forced, when
  the new stop would sit closer to the price than the symbol's stops level, or when the price is inside the
  freeze level of the current stop or target (the server would refuse either). At most one change per
  position every ``modify_min_interval_seconds``, and only by ``min_sl_step_points``; ``10025`` (no changes)
  counts as done.
- **Closes** (time stop, a strategy's close signal) are market deals against the position ticket.
- **Flatten** (kill switch in FLATTEN mode) closes every bot position; it requires
  ``KILL_SWITCH_FLATTEN_ALLOWED=true`` and is refused otherwise.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import select

from app.broker.execution import SendResult
from app.broker.models import BrokerPosition
from app.config import PositionManagementConfig
from app.core.clock import Clock
from app.core.enums import ExitReason, Side, Timeframe
from app.core.errors import SafetyViolation, TaaError
from app.engine.order_manager import OrderManager
from app.execution.management import PositionView, better_stop, manage, plan_break_even
from app.market_data.data_models import SymbolSpec
from app.monitoring.alerts import EventBus, EventType
from app.risk.exposure_manager import MAGIC_RANGE
from app.storage.models import OrderIntentRow
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_models import StrategyContext

log = logging.getLogger(__name__)


class BrokerPositionManager:
    def __init__(
        self,
        orders: OrderManager,
        config: PositionManagementConfig,
        specs: Mapping[str, SymbolSpec],
        clock: Clock,
        *,
        entry_timeframe: Timeframe,
        magic_base: int,
        strategies_by_magic: Mapping[int, BaseStrategy],
        flatten_allowed: bool,
        bus: EventBus | None = None,
    ) -> None:
        self.orders = orders
        self.config = config
        self.specs = dict(specs)
        self.clock = clock
        self.entry_timeframe = entry_timeframe
        self.magic_base = magic_base
        self.strategies_by_magic = dict(strategies_by_magic)
        self.flatten_allowed = flatten_allowed
        self.bus = bus
        self._last_modify: dict[int, datetime] = {}

    # --- lookups ----------------------------------------------------------------------------------------

    def bot_positions(self, symbol: str | None = None) -> list[BrokerPosition]:
        try:
            positions = self.orders.market.positions(symbol) if symbol else self.orders.market.positions()
        except TaaError:
            log.warning("positions_get failed; positions are not managed this cycle")
            return []
        return [p for p in positions if self.magic_base <= p.magic < self.magic_base + MAGIC_RANGE]

    def _initial_stops(self) -> dict[int, float]:
        with self.orders.db.session() as sess:
            rows = sess.execute(
                select(OrderIntentRow.position_ticket, OrderIntentRow.sl).where(
                    OrderIntentRow.position_ticket.is_not(None)
                )
            ).all()
        return {int(ticket): float(sl) for ticket, sl in rows if ticket is not None}

    def _bars_held(self, position: BrokerPosition) -> int:
        held = (self.clock.now_utc() - position.time_utc).total_seconds()
        return max(0, int(held // self.entry_timeframe.seconds))

    # --- every quote ------------------------------------------------------------------------------------

    def on_quote(self, symbol: str, bid: float, ask: float, atr: float | None) -> None:
        spec = self.specs.get(symbol)
        if spec is None:
            return
        initial = self._initial_stops()
        mine = self.bot_positions(symbol)
        to_break_even = self.orders.plan_parts_closed({p.ticket for p in mine}) if mine else set()
        for pos in mine:
            first_sl = initial.get(pos.ticket)
            if first_sl is None or pos.sl <= 0:
                continue  # unknown positions and missing stops belong to the reconciler's sweep
            mark = bid if pos.side is Side.BUY else ask
            view = PositionView(pos.side, pos.price_open, first_sl, pos.sl, self._bars_held(pos))
            adj = manage(view, mark=mark, atr=atr, point=spec.point, cfg=self.config)
            if pos.ticket in to_break_even:
                plan = plan_break_even(view, mark=mark, point=spec.point, cfg=self.config)
                adj = better_stop(pos.side, adj, plan)
            if adj.close is not None:
                self.close(pos, spec, adj.close)
            elif adj.new_sl is not None:
                self._modify(pos, spec, adj.new_sl, mark, adj.note)

    def _modify(self, pos: BrokerPosition, spec: SymbolSpec, new_sl: float, mark: float, note: str) -> None:
        if (new_sl - pos.sl) * pos.side.sign <= 0:
            log.error("refused an unfavourable stop move on #%s (%s -> %s)", pos.ticket, pos.sl, new_sl)
            return
        if (mark - new_sl) * pos.side.sign <= spec.stops_level * spec.point:
            return  # inside the stops level: the server would refuse it; try again on a later quote
        frozen = spec.freeze_level * spec.point
        if frozen and any(level and abs(mark - level) <= frozen for level in (pos.sl, pos.tp)):
            return  # the current stop or target is frozen
        now = self.clock.now_utc()
        last = self._last_modify.get(pos.ticket)
        if last is not None and (now - last).total_seconds() < self.config.modify_min_interval_seconds:
            return
        self._last_modify[pos.ticket] = now
        result = self.orders.execution.send(
            self.orders.builder.modify_stops(spec, pos, new_sl, pos.tp if pos.tp > 0 else None)
        )
        if result.ok or result.retcode == 10025:
            if self.bus is not None:
                self.bus.emit(
                    EventType.STOP_MOVED,
                    symbol=pos.symbol,
                    ticket=pos.ticket,
                    old=pos.sl,
                    new=new_sl,
                    note=note,
                    paper=False,
                )
        else:
            log.warning("stop change on #%s refused: %s", pos.ticket, result.description)
            self.orders.monitor.observe_order_failure(f"modify #{pos.ticket}: {result.description}")

    # --- every bar --------------------------------------------------------------------------------------

    def on_bar(self, symbol: str, ctx: StrategyContext) -> None:
        spec = self.specs.get(symbol)
        if spec is None:
            return
        for pos in self.bot_positions(symbol):
            strategy = self.strategies_by_magic.get(pos.magic)
            if strategy is not None and strategy.should_close(ctx, pos.side):
                self.close(pos, spec, ExitReason.SIGNAL)

    # --- closing ----------------------------------------------------------------------------------------

    def close(self, pos: BrokerPosition, spec: SymbolSpec, reason: ExitReason) -> SendResult:
        tick = self.orders.market.tick(pos.symbol)
        price = pos.price_current if tick is None else (tick.bid if pos.side is Side.BUY else tick.ask)
        result = self.orders.execution.send(
            self.orders.builder.close(spec, pos, price, comment=f"taa:{reason.value.lower()}")
        )
        if result.ok:
            if self.bus is not None:
                self.bus.emit(
                    EventType.POSITION_CLOSED,
                    symbol=pos.symbol,
                    ticket=pos.ticket,
                    reason=reason.value,
                    paper=False,
                )
        else:
            log.error("close of #%s (%s) failed: %s", pos.ticket, reason.value, result.description)
            self.orders.monitor.observe_order_failure(f"close #{pos.ticket}: {result.description}")
        return result

    def flatten(self, why: str) -> list[SendResult]:
        """Close every bot position (kill switch FLATTEN). Refused unless explicitly allowed."""
        if not self.flatten_allowed:
            raise SafetyViolation("FLATTEN needs KILL_SWITCH_FLATTEN_ALLOWED=true")
        results = []
        for pos in self.bot_positions():
            spec = self.specs.get(pos.symbol)
            if spec is None:
                log.error("cannot flatten #%s: no spec for %s", pos.ticket, pos.symbol)
                continue
            results.append(self.close(pos, spec, ExitReason.KILL_SWITCH))
        log.critical("flatten (%s): %d close(s) sent", why, len(results))
        return results
