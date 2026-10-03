"""Loss accounting (PLAN §A9 "Loss accounting"; TAA-403).

- **Periods** follow broker time (``BROKER_TIMEZONE``, EET for FBS, the same days as the broker's D1
  bars): the trading day starts at local midnight, the week on Monday. The first observation in a period
  stores its start equity (persisted), and P/L includes floating P/L because it is measured on equity.
- **Cash flows** (deal types BALANCE/CREDIT...) are booked into the open periods' ``cash_flow`` and into the
  cumulative total, so deposits and withdrawals never trip or mask a limit: ``P/L = equity − start −
  cash_flow``. A flow dated before a period's baseline was taken is already in that start equity.
- **High-water mark** is tracked on equity net of cumulative cash flows and persisted; drawdown is measured
  from it.
- **Consecutive losses** count closed bot trades (closing deals with the bot's magic), net of commission, swap
  and fees: a loss adds one, a win resets, a flat trade changes nothing. Each deal is applied once
  (``risk_deals``), so a restart never double-counts.

Partial closes count as separate trades; the bot closes positions in one deal in Milestone 1.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.broker import mt5_constants as c
from app.broker.models import Deal
from app.config import RiskConfig
from app.core.clock import Clock, ensure_utc
from app.risk.checks import Check, CheckKind
from app.risk.reasons import Reason
from app.storage.database import Database
from app.storage.models import RiskBaseline, RiskDeal, RiskState

DAY, WEEK = "DAY", "WEEK"
CLOSING_ENTRIES = (c.DEAL_ENTRY_OUT, c.DEAL_ENTRY_INOUT, c.DEAL_ENTRY_OUT_BY)


@dataclass(frozen=True, slots=True)
class LossStatus:
    as_of: datetime
    equity: float
    day_key: str
    week_key: str
    day_start: float  # start equity + cash flows booked today
    week_start: float
    hwm: float  # on equity net of cumulative cash flows
    adjusted_equity: float
    consecutive_losses: int
    last_loss_at: datetime | None

    @property
    def day_pnl(self) -> float:
        return self.equity - self.day_start

    @property
    def week_pnl(self) -> float:
        return self.equity - self.week_start

    @property
    def day_pnl_percent(self) -> float:
        return _pct(self.day_pnl, self.day_start)

    @property
    def week_pnl_percent(self) -> float:
        return _pct(self.week_pnl, self.week_start)

    @property
    def drawdown_percent(self) -> float:
        """Drawdown from the high-water mark, ≥ 0."""
        return max(0.0, _pct(self.hwm - self.adjusted_equity, self.hwm))


def _pct(value: float, base: float) -> float:
    return 100.0 * value / base if base > 0 else 0.0


def period_keys(at_utc: datetime, tz: ZoneInfo) -> tuple[str, str]:
    """(day key, ISO-week key) of the broker-local date at *at_utc*."""
    local = ensure_utc(at_utc).astimezone(tz).date()
    year, week, _ = local.isocalendar()
    return local.isoformat(), f"{year}-W{week:02d}"


class LossTracker:
    def __init__(self, db: Database, account_key: str, tz_name: str, clock: Clock) -> None:
        self.db = db
        self.account_key = account_key
        self.tz = ZoneInfo(tz_name)
        self.clock = clock

    def observe(
        self,
        equity: float,
        deals: Sequence[Deal] = (),
        *,
        is_bot: Callable[[Deal], bool] = lambda d: False,
    ) -> LossStatus:
        """Book new deals and the current equity; return the up-to-date status (one transaction)."""
        now = self.clock.now_utc()
        day_key, week_key = period_keys(now, self.tz)
        with self.db.session() as sess:
            state = sess.get(RiskState, self.account_key)
            if state is None:
                state = RiskState(
                    account_key=self.account_key, hwm=equity, cumulative_cash_flow=0.0, consecutive_losses=0
                )
                sess.add(state)
            baselines = {}
            for period, key in ((DAY, day_key), (WEEK, week_key)):
                row = sess.get(RiskBaseline, (self.account_key, period, key))
                if row is None:
                    row = RiskBaseline(
                        account_key=self.account_key,
                        period=period,
                        period_key=key,
                        start_equity=equity,
                        cash_flow=0.0,
                        created_at=now,
                        updated_at=now,
                    )
                    sess.add(row)
                baselines[period] = row
            seen = set(
                sess.execute(
                    select(RiskDeal.ticket).where(RiskDeal.account_key == self.account_key)
                ).scalars()
            )
            for deal in sorted(deals, key=lambda d: (d.time_utc, d.ticket)):
                if deal.ticket in seen:
                    continue
                if deal.is_cash_flow:
                    self._book_cash_flow(deal, state, baselines.values())
                    sess.add(self._deal_row(deal, "CASH_FLOW", deal.profit))
                elif deal.entry in CLOSING_ENTRIES and is_bot(deal):
                    self._book_close(deal, state)
                    sess.add(self._deal_row(deal, "CLOSE", deal.net))
                seen.add(deal.ticket)
            adjusted = equity - state.cumulative_cash_flow
            state.hwm = max(state.hwm, adjusted)
            state.updated_at = now
            return LossStatus(
                as_of=now,
                equity=equity,
                day_key=day_key,
                week_key=week_key,
                day_start=baselines[DAY].start_equity + baselines[DAY].cash_flow,
                week_start=baselines[WEEK].start_equity + baselines[WEEK].cash_flow,
                hwm=state.hwm,
                adjusted_equity=adjusted,
                consecutive_losses=state.consecutive_losses,
                last_loss_at=state.last_loss_at,
            )

    def reset_consecutive_losses(self) -> None:
        """Manual reset (the breaker framework audits who did it and why)."""
        with self.db.session() as sess:
            state = sess.get(RiskState, self.account_key)
            if state is not None:
                state.consecutive_losses = 0
                state.updated_at = self.clock.now_utc()

    # booking -----------------------------------------------------------------------------------------------

    def _deal_row(self, deal: Deal, kind: str, amount: float) -> RiskDeal:
        return RiskDeal(
            account_key=self.account_key, ticket=deal.ticket, kind=kind, amount=amount, time_utc=deal.time_utc
        )

    @staticmethod
    def _book_cash_flow(deal: Deal, state: RiskState, baselines: Iterable[RiskBaseline]) -> None:
        state.cumulative_cash_flow += deal.profit
        for row in baselines:
            # a flow before the baseline was taken is already inside its start equity
            if ensure_utc(deal.time_utc) >= row.created_at:
                row.cash_flow += deal.profit

    @staticmethod
    def _book_close(deal: Deal, state: RiskState) -> None:
        net = deal.net
        if net < 0:
            state.consecutive_losses += 1
            state.last_loss_at = deal.time_utc
        elif net > 0:
            state.consecutive_losses = 0


def loss_checks(status: LossStatus, risk: RiskConfig) -> list[Check]:
    """The account rules of §A8 that come from loss accounting (all ``ACCOUNT`` kind)."""
    acct = CheckKind.ACCOUNT
    paused_until = (
        None
        if status.last_loss_at is None
        else status.last_loss_at + timedelta(hours=risk.consecutive_loss_pause_hours)
    )
    streak_blocks = status.consecutive_losses >= risk.max_consecutive_losses and (
        paused_until is None or status.as_of < paused_until
    )
    return [
        Check(
            "daily_loss",
            Reason.DAILY_LOSS_LIMIT,
            -status.day_pnl_percent < risk.max_daily_loss_percent,
            acct,
            round(status.day_pnl_percent, 4),
            -risk.max_daily_loss_percent,
            "today's P/L, % of start-of-day equity",
        ),
        Check(
            "weekly_loss",
            Reason.WEEKLY_LOSS_LIMIT,
            -status.week_pnl_percent < risk.max_weekly_loss_percent,
            acct,
            round(status.week_pnl_percent, 4),
            -risk.max_weekly_loss_percent,
        ),
        Check(
            "max_drawdown",
            Reason.MAX_DRAWDOWN,
            status.drawdown_percent < risk.max_account_drawdown_percent,
            acct,
            round(status.drawdown_percent, 4),
            risk.max_account_drawdown_percent,
            "drawdown from the high-water mark, %",
        ),
        Check(
            "consecutive_losses",
            Reason.CONSECUTIVE_LOSSES,
            not streak_blocks,
            acct,
            status.consecutive_losses,
            risk.max_consecutive_losses,
            "" if paused_until is None else f"pause until {paused_until.isoformat()}",
        ),
    ]
