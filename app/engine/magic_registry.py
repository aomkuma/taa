"""Stable magic numbers per bot and strategy (PLAN_LEARNING §L21.8; TAA-L901).

A position is tied to the strategy that manages it by its magic number. Before this registry the magic was
``MAGIC_NUMBER_BASE + index`` of the *enabled* strategies, so enabling, disabling or reordering a strategy
while positions were open handed them to another strategy's exit rules. Now each ``(bot_id, strategy)`` gets
its slots once, persisted in ``magic_registry``, and keeps them forever:

- magic = ``base + bot_slot × 100 + strategy_slot`` (inside the bot range ``[base, base + MAGIC_RANGE)``);
- **compatibility:** on the first start with an empty registry the enabled strategies of the ``default`` bot
  get slots in their config order, which are exactly the old index-based numbers, so open positions keep
  theirs;
- a strategy seen later gets the next slot after the highest one ever assigned to its bot: slots are never
  reused, even after a strategy is removed from the config;
- slots, not absolute numbers, are stored, so changing ``MAGIC_NUMBER_BASE`` moves the whole block (as
  before).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.core.clock import Clock
from app.core.errors import ConfigError
from app.risk.exposure_manager import MAGIC_RANGE
from app.storage.database import Database
from app.storage.models import MagicRegistryRow

DEFAULT_BOT = "default"
SLOTS_PER_BOT = 100
MAX_BOTS = MAGIC_RANGE // SLOTS_PER_BOT


class MagicRegistry:
    def __init__(self, db: Database, base: int, clock: Clock) -> None:
        self.db = db
        self.base = base
        self.clock = clock

    def magic(self, bot_slot: int, strategy_slot: int) -> int:
        return self.base + bot_slot * SLOTS_PER_BOT + strategy_slot

    def ensure(self, strategies: Sequence[str], bot_id: str = DEFAULT_BOT) -> dict[str, int]:
        """Assign missing slots (in the given order) and return strategy → magic for ``strategies``."""
        if len(set(strategies)) != len(strategies):
            raise ConfigError(f"duplicate strategy names for bot {bot_id!r}")
        with self.db.session() as sess:
            rows = list(sess.scalars(select(MagicRegistryRow)))
            mine = {r.strategy: r for r in rows if r.bot_id == bot_id}
            if mine:
                bot_slot = next(iter(mine.values())).bot_slot
            else:
                used = {r.bot_slot for r in rows}
                bot_slot = 0 if bot_id == DEFAULT_BOT and 0 not in used else max(used | {0}) + 1
                if bot_slot >= MAX_BOTS:
                    raise ConfigError(f"no magic block left for bot {bot_id!r} (max {MAX_BOTS} bots)")
            next_slot = max((r.strategy_slot for r in mine.values()), default=-1) + 1
            now = self.clock.now_utc()
            for name in strategies:
                if name in mine:
                    continue
                if next_slot >= SLOTS_PER_BOT:
                    raise ConfigError(f"bot {bot_id!r} has used all {SLOTS_PER_BOT} strategy slots")
                row = MagicRegistryRow(
                    bot_id=bot_id, strategy=name, bot_slot=bot_slot, strategy_slot=next_slot, assigned_at=now
                )
                sess.add(row)
                mine[name] = row
                next_slot += 1
            return {name: self.magic(mine[name].bot_slot, mine[name].strategy_slot) for name in strategies}

    def all(self) -> dict[int, tuple[str, str]]:
        """Every magic ever assigned → (bot_id, strategy)."""
        with self.db.session() as sess:
            return {
                self.magic(r.bot_slot, r.strategy_slot): (r.bot_id, r.strategy)
                for r in sess.scalars(select(MagicRegistryRow))
            }
