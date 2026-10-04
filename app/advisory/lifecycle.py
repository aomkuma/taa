"""Market windows and the opportunity lifecycle (PLAN §A26 "Window"; TAA-6B4). Runs inside the engine.

**Market window:** ``valid_until`` is the earliest of

- the signal lifetime: bar close + N entry bars (N = the longest lifetime any user wants);
- the end of the symbol's current market session (:mod:`app.advisory.market_sessions`; 24/7 symbols have
  none);
- the start of the next news blackout for the symbol's currencies.

The reason is stored (``SIGNAL_LIFETIME``, ``SESSION_END:LONDON``, ``NEWS_BLACKOUT``). A user's own window end
(their time windows) is applied later by the personalizer.

**Statuses:** CANDIDATE (tracked) → ACTIVE (someone was alerted, :meth:`OpportunityLifecycle.mark_active`) →
one terminal state:

- **EXPIRED:** the window passed (also caught up after a restart, keeping the window's reason).
- **INVALIDATED:** price drifted more than ``risk.price_drift_atr`` × ATR from the entry, the stop was touched
  before entry, the spread stayed over its limit for ``spread_grace_seconds``, or an opposite signal appeared.
- **FOLLOWED:** a manual position (magic 0) on the same symbol and side was opened inside the window
  (detected read-only).

Prices are checked against the live quote on every tick. Quotes during an outage are unknown, so a restart
only expires windows that passed; it never invents an invalidation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import select

from app.advisory.asset_classes import AssetClass
from app.advisory.market_sessions import session_state, sessions_for
from app.advisory.statuses import OPEN, OpportunityStatus
from app.broker.gateway import MarketDataGateway
from app.config import AppConfig
from app.core.clock import Clock, ensure_utc
from app.core.enums import Side, Timeframe
from app.market_data.data_models import Tick
from app.news.calendar import NewsFilter
from app.storage.database import Database
from app.storage.models import OpportunityRow
from app.storage.models.base import LOCAL_ENGINE

log = logging.getLogger(__name__)

MANUAL_MAGIC = 0


class WindowReason(StrEnum):
    SIGNAL_LIFETIME = "SIGNAL_LIFETIME"
    SESSION_END = "SESSION_END"
    NEWS_BLACKOUT = "NEWS_BLACKOUT"


class InvalidReason(StrEnum):
    PRICE_DRIFT = "PRICE_DRIFT"
    SL_TOUCHED = "SL_TOUCHED"
    SPREAD_SPIKE = "SPREAD_SPIKE"
    OPPOSITE_SIGNAL = "OPPOSITE_SIGNAL"


@dataclass(frozen=True, slots=True)
class Transition:
    opportunity_id: str
    symbol: str
    status: OpportunityStatus
    reason: str
    at: datetime


def market_window(
    *,
    bar_close: datetime,
    timeframe: Timeframe,
    lifetime_bars: int,
    session_end: datetime | None,
    session_name: str | None,
    next_blackout: datetime | None,
) -> tuple[datetime, str]:
    candidates = [
        (ensure_utc(bar_close) + timedelta(seconds=timeframe.seconds * lifetime_bars), "SIGNAL_LIFETIME")
    ]
    if session_end is not None:
        candidates.append((ensure_utc(session_end), f"SESSION_END:{session_name or ''}".rstrip(":")))
    if next_blackout is not None:
        candidates.append((ensure_utc(next_blackout), WindowReason.NEWS_BLACKOUT.value))
    return min(candidates, key=lambda c: c[0])  # ties keep the order above (lifetime first)


class OpportunityLifecycle:
    def __init__(
        self,
        db: Database,
        gateway: MarketDataGateway,
        config: AppConfig,
        clock: Clock,
        *,
        server: str,
        lifetime_bars: Callable[[], int] = lambda: 2,
        news: NewsFilter | None = None,
        spread_grace_seconds: float = 30.0,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.config = config
        self.clock = clock
        self.server = server
        self.lifetime_bars = lifetime_bars
        self.news = news
        self.spread_grace = timedelta(seconds=spread_grace_seconds)
        self._spread_since: dict[str, datetime] = {}

    # --- windows --------------------------------------------------------------------------------------------

    def window(self, row: OpportunityRow) -> tuple[datetime, str]:
        spec = self.gateway.symbol_spec(row.symbol)
        names = sessions_for(
            row.symbol,
            AssetClass(row.asset_class),
            spec.currency_profit,
            self.config.advisory.sessions.overrides,
        )
        state = session_state(names, row.created_at)
        session_name = None
        if state.ends_at is not None:
            session_name = "/".join(state.active)
        blackout = None
        if self.news is not None:
            currencies = {spec.currency_base, spec.currency_profit}
            blackout = self.news.next_start(row.symbol, currencies, row.created_at)
        return market_window(
            bar_close=row.bar_close_at,
            timeframe=Timeframe(row.timeframe),
            lifetime_bars=self.lifetime_bars(),
            session_end=state.ends_at if state.open else None,
            session_name=session_name,
            next_blackout=blackout,
        )

    # --- the tick -------------------------------------------------------------------------------------------

    def tick(self) -> list[Transition]:
        """Open new windows, expire, invalidate and detect FOLLOWED, oldest first."""
        now = self.clock.now_utc()
        out: list[Transition] = []
        with self.db.session() as sess:
            rows = list(
                sess.execute(
                    select(OpportunityRow)
                    .where(OpportunityRow.server == self.server, OpportunityRow.status.in_(OPEN))
                    .order_by(OpportunityRow.created_at, OpportunityRow.opportunity_id)
                ).scalars()
            )
            fresh = [r for r in rows if r.valid_until is None]
            for row in fresh:
                row.valid_until, row.valid_reason = self.window(row)
                out += self._opposites(row, rows, now)
            positions = [p for p in self.gateway.positions() if p.magic == MANUAL_MAGIC]
            ticks: dict[str, Tick | None] = {}
            for row in rows:
                if row.status not in OPEN:
                    continue
                transition = self._check(row, now, positions, ticks)
                if transition is not None:
                    self._apply(row, transition)
                    out.append(transition)
        for t in out:
            log.info("opportunity %s %s: %s (%s)", t.opportunity_id[:12], t.symbol, t.status.value, t.reason)
        return out

    def catch_up(self) -> list[Transition]:
        """After a restart: expire every window that passed while the engine was down (no price checks)."""
        now = self.clock.now_utc()
        out = []
        with self.db.session() as sess:
            for row in sess.execute(
                select(OpportunityRow).where(
                    OpportunityRow.server == self.server,
                    OpportunityRow.status.in_(OPEN),
                    OpportunityRow.valid_until.is_not(None),
                    OpportunityRow.valid_until <= now,
                )
            ).scalars():
                t = Transition(
                    row.opportunity_id, row.symbol, OpportunityStatus.EXPIRED, row.valid_reason, now
                )
                self._apply(row, t)
                out.append(t)
        return out

    def mark_active(self, opportunity_id: str) -> bool:
        """Someone was alerted: CANDIDATE → ACTIVE (no-op for any other state)."""
        with self.db.session() as sess:
            row = sess.get(OpportunityRow, (LOCAL_ENGINE, opportunity_id))
            if row is None or row.status != OpportunityStatus.CANDIDATE.value:
                return False
            row.status = OpportunityStatus.ACTIVE.value
            row.status_at = self.clock.now_utc()
            row.alerted_at = row.alerted_at or row.status_at  # kept after expiry, for shadow statistics
            return True

    # --- rules ----------------------------------------------------------------------------------------------

    def _apply(self, row: OpportunityRow, t: Transition) -> None:
        row.status = t.status.value
        row.status_reason = t.reason
        row.status_at = t.at
        self._spread_since.pop(row.opportunity_id, None)

    def _opposites(
        self, new: OpportunityRow, rows: Iterable[OpportunityRow], now: datetime
    ) -> list[Transition]:
        out = []
        for row in rows:
            if (
                row is not new
                and row.symbol == new.symbol
                and row.side != new.side
                and row.status in OPEN
                and row.created_at <= new.created_at
            ):
                t = Transition(
                    row.opportunity_id, row.symbol, OpportunityStatus.INVALIDATED, "OPPOSITE_SIGNAL", now
                )
                self._apply(row, t)
                out.append(t)
        return out

    def _check(
        self, row: OpportunityRow, now: datetime, positions: list, ticks: dict[str, Tick | None]
    ) -> Transition | None:
        def done(status: OpportunityStatus, reason: str) -> Transition:
            return Transition(row.opportunity_id, row.symbol, status, reason, now)

        side = Side(row.side)
        start = ensure_utc(row.bar_close_at)
        until = ensure_utc(row.valid_until) if row.valid_until is not None else None
        for p in positions:
            opened = ensure_utc(p.time_utc)
            if (
                p.symbol == row.symbol
                and p.side is side
                and opened >= start
                and (until is None or opened <= until)
            ):
                return done(OpportunityStatus.FOLLOWED, f"position {p.ticket}")
        if until is not None and now >= until:
            return done(OpportunityStatus.EXPIRED, row.valid_reason)
        if row.symbol not in ticks:
            ticks[row.symbol] = self.gateway.tick(row.symbol)
        tick = ticks[row.symbol]
        if tick is None:
            return None
        price = tick.ask if side is Side.BUY else tick.bid
        exit_price = tick.bid if side is Side.BUY else tick.ask
        if (exit_price - row.stop_loss) * side.sign <= 0:
            return done(OpportunityStatus.INVALIDATED, InvalidReason.SL_TOUCHED.value)
        if row.atr is not None and abs(price - row.entry) > self.config.risk.price_drift_atr * row.atr:
            return done(OpportunityStatus.INVALIDATED, InvalidReason.PRICE_DRIFT.value)
        point = self.gateway.symbol_spec(row.symbol).point
        spread = (tick.ask - tick.bid) / point if point > 0 else 0.0
        if spread > self.config.spread_limit(row.symbol):
            since = self._spread_since.setdefault(row.opportunity_id, now)
            if now - since >= self.spread_grace:
                return done(OpportunityStatus.INVALIDATED, InvalidReason.SPREAD_SPIKE.value)
        else:
            self._spread_since.pop(row.opportunity_id, None)
        return None
