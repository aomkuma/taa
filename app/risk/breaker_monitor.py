"""Turns observations into breaker trips and healthy reports (PLAN §A10 triggers; TAA-404).

The engine loop feeds every observation here; the :class:`BreakerBoard` decides what a trip or a healthy
report changes. Triggers that need persistence over time (a disconnect longer than the grace period, a wide
spread lasting ``spread_persist_seconds``) keep their "unhealthy since" timers in memory: after a restart
the timer starts again, which can only delay a trip by one grace period, and the board itself (persisted)
still holds every breaker that had already tripped.
"""

from __future__ import annotations

from datetime import datetime

from app.config import BreakerConfig, RiskConfig
from app.core.clock import Clock
from app.risk.circuit_breaker import BreakerBoard, BreakerName
from app.risk.loss_tracker import LossStatus, loss_checks
from app.risk.reasons import Reason

LOSS_BREAKERS = {
    Reason.DAILY_LOSS_LIMIT: BreakerName.DAILY_LOSS,
    Reason.WEEKLY_LOSS_LIMIT: BreakerName.WEEKLY_LOSS,
    Reason.MAX_DRAWDOWN: BreakerName.MAX_DRAWDOWN,
    Reason.CONSECUTIVE_LOSSES: BreakerName.CONSECUTIVE_LOSSES,
}


class BreakerMonitor:
    def __init__(self, board: BreakerBoard, config: BreakerConfig, risk: RiskConfig, clock: Clock) -> None:
        self.board = board
        self.config = config
        self.risk = risk
        self.clock = clock
        self._since: dict[tuple[BreakerName, str], datetime] = {}
        self._slippage_hits: dict[tuple[str, str], int] = {}

    def _persisting(self, name: BreakerName, key: str, bad: bool, grace_seconds: float) -> bool:
        """True once *bad* has held continuously for *grace_seconds*."""
        if not bad:
            self._since.pop((name, key), None)
            return False
        start = self._since.setdefault((name, key), self.clock.now_utc())
        return (self.clock.now_utc() - start).total_seconds() >= grace_seconds

    def _verdict(self, name: BreakerName, key: str, bad: bool, reason: str, **metrics: object) -> None:
        if bad:
            self.board.trip(name, reason, key, metrics)
        else:
            self.board.report_healthy(name, key)

    # global health -----------------------------------------------------------------------------------------

    def observe_connection(self, connected: bool, detail: str = "") -> None:
        grace = self.config.connection_grace_seconds
        if connected:
            self._persisting(BreakerName.CONNECTION, "", False, grace)
            self.board.report_healthy(BreakerName.CONNECTION)
        elif self._persisting(BreakerName.CONNECTION, "", True, grace):
            self.board.trip(BreakerName.CONNECTION, detail or f"disconnected for > {grace:g} s")
        # disconnected inside the grace period: no verdict yet

    def observe_clock(self, verified: bool, detail: str = "") -> None:
        self._verdict(BreakerName.CLOCK, "", not verified, detail or "server time not verified")

    def observe_storage(self, write_ok: bool, free_gb: float | None) -> None:
        low_disk = free_gb is not None and free_gb < self.config.disk_min_free_gb
        reason = "database write failed" if not write_ok else f"free disk {free_gb:.2f} GB"
        self._verdict(BreakerName.STORAGE, "", not write_ok or low_disk, reason, free_gb=free_gb)

    def account_changed(self, detail: str) -> None:
        self.board.trip(BreakerName.ACCOUNT_CHANGE, detail)

    def record_exception(self, where: str, exc: BaseException) -> None:
        self.board.trip(BreakerName.UNHANDLED_EXCEPTION, f"{where}: {type(exc).__name__}: {exc}")

    def observe_losses(self, status: LossStatus) -> None:
        """Loss breakers reset on their own schedule (next day/week, cooldown, manual), not on a good tick."""
        for check in loss_checks(status, self.risk):
            if not check.passed:
                self.board.trip(
                    LOSS_BREAKERS[check.reason],
                    f"{check.name} {check.value} (limit {check.threshold})",
                    metrics={"value": check.value, "threshold": check.threshold},
                )

    # per symbol --------------------------------------------------------------------------------------------

    def observe_quote(
        self,
        symbol: str,
        *,
        bid: float,
        ask: float,
        spread_points: float,
        spread_limit: float,
        tick_age_seconds: float,
        in_session: bool,
        previous_mid: float | None = None,
        atr: float | None = None,
        median_spread: float | None = None,
    ) -> None:
        cfg = self.config
        mid = (bid + ask) / 2
        jump = (
            previous_mid is not None
            and atr is not None
            and atr > 0
            and abs(mid - previous_mid) > cfg.invalid_price_jump_atr * atr
        )
        invalid = bid <= 0 or ask <= 0 or ask < bid or jump
        self._verdict(
            BreakerName.INVALID_PRICE, symbol, invalid, f"bid {bid} ask {ask}" + (" (jump)" if jump else "")
        )
        if invalid:
            return  # a spread or a freshness of an invalid quote means nothing
        too_wide = spread_points > spread_limit
        spike = (
            median_spread is not None
            and median_spread > 0
            and spread_points > cfg.spread_spike_multiple * median_spread
        )
        lasting = self._persisting(BreakerName.SPREAD, symbol, too_wide, cfg.spread_persist_seconds)
        if spike or lasting:
            reason = f"spread {spread_points:g} pts (limit {spread_limit:g}, median {median_spread})"
            self.board.trip(BreakerName.SPREAD, reason, symbol, {"spread": spread_points})
        elif not too_wide:
            self.board.report_healthy(BreakerName.SPREAD, symbol)
        # wide but not for long enough yet: no verdict
        stale = in_session and tick_age_seconds > cfg.stale_data_seconds
        self._verdict(
            BreakerName.STALE_DATA,
            symbol,
            stale,
            f"last tick {tick_age_seconds:.0f} s old",
            age=tick_age_seconds,
        )

    def observe_fill(self, symbol: str, slippage_points: float) -> None:
        """A fill above the slippage limit trips at once; three fills above half of it in one day trip too."""
        limit = self.risk.max_slippage_points
        day = self.clock.now_utc().date().isoformat()
        if slippage_points > limit:
            self.board.trip(BreakerName.SLIPPAGE, f"slippage {slippage_points:g} pts > {limit:g}", symbol)
            return
        if slippage_points > limit / 2:
            key = (symbol, day)
            self._slippage_hits[key] = self._slippage_hits.get(key, 0) + 1
            if self._slippage_hits[key] >= 3:
                self.board.trip(BreakerName.SLIPPAGE, f"3 fills above {limit / 2:g} pts today", symbol)
