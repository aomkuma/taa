"""Position manager for PAPER positions (PLAN §A11; TAA-603). Milestone 2 reuses it for broker positions.

Every quote (1–2 s): the shared rules of :mod:`app.execution.management` (break-even, ATR trailing, time
stop). Every new closed entry bar: the bar count for the time stop, and the strategy's own close signal
(:meth:`BaseStrategy.should_close`). MAE/MFE are tracked by the simulated broker on every quote.

Stop invariants, enforced here before any change:

- a position always has a stop: a missing one is re-attached from its intent, or the position is closed;
- the stop only moves in the favourable direction (the rules never propose otherwise; checked again here);
- the new stop keeps at least the broker's stops level (plus the freeze level) from the current price;
- at most one change per position every ``modify_min_interval_seconds``, and only by ``min_sl_step_points``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime

from app.config import PositionManagementConfig
from app.core.clock import Clock
from app.core.enums import ExitReason
from app.engine.paper import PaperExecution
from app.execution.fill_model import mark_price
from app.execution.management import PositionView, manage
from app.market_data.data_models import SymbolSpec
from app.monitoring.alerts import EventBus, EventType
from app.strategy.base_strategy import BaseStrategy
from app.strategy.signal_models import StrategyContext

log = logging.getLogger(__name__)


class PositionManager:
    def __init__(
        self,
        paper: PaperExecution,
        config: PositionManagementConfig,
        specs: Mapping[str, SymbolSpec],
        clock: Clock,
        *,
        strategies_by_magic: Mapping[int, BaseStrategy],
        bus: EventBus | None = None,
    ) -> None:
        self.paper = paper
        self.config = config
        self.specs = dict(specs)
        self.clock = clock
        self.strategies_by_magic = dict(strategies_by_magic)
        self.bus = bus
        self._last_modify: dict[int, datetime] = {}

    def on_quote(self, symbol: str, bid: float, ask: float, atr: float | None) -> None:
        spec = self.specs[symbol]
        now = self.clock.now_utc()
        for pos in [p for p in self.paper.broker.positions.values() if p.symbol == symbol]:
            if pos.close_requested:
                continue
            if pos.sl is None:
                self._missing_stop(pos.ticket, pos.request.sl)
                continue
            if pos.request.sl is None:
                continue
            mark = mark_price(pos.side, bid, ask - bid)
            adj = manage(
                PositionView(pos.side, pos.entry_price, pos.request.sl, pos.sl, pos.bars_held),
                mark=mark,
                atr=atr,
                point=spec.point,
                cfg=self.config,
            )
            if adj.close is not None:
                self.paper.request_close(pos.ticket, adj.close)
                continue
            if adj.new_sl is None:
                continue
            if (adj.new_sl - pos.sl) * pos.side.sign <= 0:
                log.error(
                    "refused an unfavourable stop move on #%s (%s -> %s)", pos.ticket, pos.sl, adj.new_sl
                )
                continue
            min_gap = (spec.stops_level + spec.freeze_level) * spec.point
            if (mark - adj.new_sl) * pos.side.sign <= min_gap:
                continue  # too close to the price for the broker to accept; retry on a later quote
            last = self._last_modify.get(pos.ticket)
            if last is not None and (now - last).total_seconds() < self.config.modify_min_interval_seconds:
                continue
            old = pos.sl
            self.paper.modify_stop(pos.ticket, adj.new_sl, adj.stop_kind)
            self._last_modify[pos.ticket] = now
            if self.bus is not None:
                self.bus.emit(
                    EventType.STOP_MOVED,
                    symbol=symbol,
                    ticket=pos.ticket,
                    old=old,
                    new=adj.new_sl,
                    kind=None if adj.stop_kind is None else adj.stop_kind.value,
                    note=adj.note,
                    paper=True,
                )

    def on_bar(self, symbol: str, ctx: StrategyContext) -> None:
        """A new closed entry bar: count it for the time stop and ask the owning strategy about closing."""
        for pos in [p for p in self.paper.broker.positions.values() if p.symbol == symbol]:
            pos.bars_held += 1
            strategy = self.strategies_by_magic.get(pos.request.magic)
            if strategy is not None and not pos.close_requested and strategy.should_close(ctx, pos.side):
                log.info("strategy %s closes #%s on %s", strategy.name, pos.ticket, symbol)
                self.paper.request_close(pos.ticket, ExitReason.SIGNAL)

    def _missing_stop(self, ticket: int, initial: float | None) -> None:
        if initial is not None:
            log.critical("position #%s had no stop; re-attached %s from its intent", ticket, initial)
            self.paper.modify_stop(ticket, initial, None)
        else:
            log.critical("position #%s has no stop and none to re-attach: closing it", ticket)
            self.paper.request_close(ticket, ExitReason.STOP_LOSS)
