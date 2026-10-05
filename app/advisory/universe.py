"""Symbol universe (PLAN §A25; TAA-6A1): what the advisory ranking looks at.

- **Discovery** with one ``symbols_get(group)`` call (R22): ``advisory.universe.include`` patterns first, then
  ``exclude`` patterns. Each symbol is classified (:mod:`app.advisory.asset_classes`) and enabled by its
  class switch (all on, except Forex exotics and unclassified symbols) or a per-symbol override.
- **Catalog:** the result is kept in ``symbol_catalog`` and refreshed every ``refresh_hours`` (daily by
  default) and once at every process start, so a changed config or classifier applies after a restart; a
  symbol the broker no longer offers stays in the table with ``present = false``.
- **Monitored set** = the bot's allowlist ∪ favourites ∪ custom lists ∪ auto top-N of the ranking, in that
  priority, de-duplicated and capped at ``monitored_cap`` (default 60) so terminal load stays bounded.

The universe is advice only: it never adds a symbol to what the bot trades (``symbols.allowed``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.advisory.asset_classes import AssetClass, classify
from app.broker.gateway import MarketDataGateway
from app.config import UniverseConfig
from app.core.clock import Clock, ensure_utc
from app.market_data.data_models import SymbolSpec
from app.storage.database import Database
from app.storage.models import SymbolCatalogRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    spec: SymbolSpec
    asset_class: AssetClass
    enabled: bool
    reason: str = ""

    @property
    def symbol(self) -> str:
        return self.spec.name


def evaluate_entry(spec: SymbolSpec, config: UniverseConfig) -> CatalogEntry:
    asset_class = classify(spec)
    override = config.symbols.get(spec.name)
    if override is not None:
        return CatalogEntry(
            spec, asset_class, override, "" if override else "disabled by a per-symbol override"
        )
    enabled = config.classes[asset_class.value]
    return CatalogEntry(
        spec, asset_class, enabled, "" if enabled else f"asset class {asset_class.value} is opt-in"
    )


class SymbolCatalog:
    def __init__(
        self, db: Database, gateway: MarketDataGateway, config: UniverseConfig, clock: Clock, *, server: str
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.config = config
        self.clock = clock
        self.server = server
        self._refreshed = False  # this process has not rediscovered yet

    def last_refresh(self) -> datetime | None:
        with self.db.session() as sess:
            return sess.execute(
                select(func.max(SymbolCatalogRow.refreshed_at)).where(SymbolCatalogRow.server == self.server)
            ).scalar_one_or_none()

    def refresh(self, *, force: bool = False) -> list[CatalogEntry]:
        """Rediscover when due (or forced); otherwise return the stored catalog."""
        now = self.clock.now_utc()
        last = self.last_refresh()
        due = last is None or now - ensure_utc(last) >= timedelta(hours=self.config.refresh_hours)
        if not (force or due or not self._refreshed):
            return self.entries(enabled_only=False)
        specs = self.gateway.symbols(self.config.group)
        entries = [evaluate_entry(spec, self.config) for spec in specs]
        seen = {e.symbol for e in entries}
        with self.db.session() as sess:
            for entry in entries:
                row = sess.get(SymbolCatalogRow, (LOCAL_ENGINE, self.server, entry.symbol))
                if row is None:
                    row = SymbolCatalogRow(server=self.server, symbol=entry.symbol, first_seen_at=now)
                    sess.add(row)
                row.asset_class = entry.asset_class.value
                row.enabled = entry.enabled
                row.reason = entry.reason
                row.path = entry.spec.path[:128]
                row.description = entry.spec.description[:128]
                row.spec = asdict(entry.spec)
                row.refreshed_at = now
                row.present = True
            for row in sess.execute(
                select(SymbolCatalogRow).where(SymbolCatalogRow.server == self.server)
            ).scalars():
                if row.symbol not in seen:
                    row.present = False
                    row.refreshed_at = now
        log.info(
            "symbol catalog refreshed: %d symbols, %d enabled", len(entries), sum(e.enabled for e in entries)
        )
        self._refreshed = True
        return entries

    def entries(self, *, enabled_only: bool = True) -> list[CatalogEntry]:
        with self.db.session() as sess:
            query = select(SymbolCatalogRow).where(
                SymbolCatalogRow.server == self.server, SymbolCatalogRow.present.is_(True)
            )
            if enabled_only:
                query = query.where(SymbolCatalogRow.enabled.is_(True))
            rows = sess.execute(query.order_by(SymbolCatalogRow.symbol)).scalars().all()
            return [
                CatalogEntry(SymbolSpec(**row.spec), AssetClass(row.asset_class), row.enabled, row.reason)
                for row in rows
            ]


def monitored_set(
    *,
    allowlist: Sequence[str],
    favourites: Sequence[str] = (),
    lists: Mapping[str, Sequence[str]] | None = None,
    ranked: Sequence[str] = (),
    auto_top_n: int = 30,
    cap: int = 60,
    available: Iterable[str] | None = None,
    unaffordable: Iterable[str] = (),
) -> list[str]:
    """Allowlist, favourites, custom lists, then the ranking's top N; de-duplicated, in priority, capped.

    *unaffordable* (the ranking's minimum-lot or margin gate failed for the account) are left out wherever
    they are listed: every entry on them would be refused, so scanning them only costs time."""
    known = None if available is None else set(available)
    skip = set(unaffordable)
    ordered: list[str] = []
    for group in (allowlist, favourites, *(lists or {}).values(), list(ranked)[:auto_top_n]):
        for symbol in group:
            if symbol not in ordered and symbol not in skip and (known is None or symbol in known):
                ordered.append(symbol)
    if len(ordered) > cap:
        log.info("monitored set capped at %d of %d symbols", cap, len(ordered))
    return ordered[:cap]
