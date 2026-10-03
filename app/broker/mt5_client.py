"""Connection manager around the ``MetaTrader5`` module.

* explicit ``initialize(path, login, password, server, timeout, portable)``; never the implicit last account
* identity/mode verification after every (re)connect
* every call serialized through one lock (thread-safety of the module is undocumented)
* order functions are refused unless the client was built with ``allow_trading=True`` (Milestone 2)
* reconnect with exponential backoff (1 s → 60 s)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.broker.models import AccountSnapshot, TerminalSnapshot
from app.broker.verification import VerificationResult, verify_connection
from app.config import EnvSettings
from app.core.clock import Clock, SystemClock
from app.core.enums import TradingMode
from app.core.errors import AccountVerificationError, BrokerUnavailable, SafetyViolation
from app.security.redaction import mask_login

log = logging.getLogger(__name__)

TRADING_FUNCTIONS = frozenset({"order_send", "order_check"})


@dataclass
class CallStats:
    calls: int = 0
    errors: int = 0
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_error: tuple[int, str] | None = None


@dataclass
class ConnectionReport:
    account: AccountSnapshot
    terminal: TerminalSnapshot
    verification: VerificationResult
    version: tuple[Any, ...] | None = None


@dataclass
class _Backoff:
    delay: float = 1.0
    next_attempt: float = 0.0
    attempts: int = 0
    max_delay: float = 60.0

    def failed(self, now: float) -> None:
        self.attempts += 1
        self.next_attempt = now + self.delay
        self.delay = min(self.delay * 2, self.max_delay)

    def reset(self) -> None:
        self.delay, self.next_attempt, self.attempts = 1.0, 0.0, 0


def account_from_raw(raw: Any, captured_at: datetime) -> AccountSnapshot:
    return AccountSnapshot(
        login=int(raw.login),
        server=str(raw.server),
        company=str(raw.company),
        name=str(raw.name),
        currency=str(raw.currency),
        leverage=int(raw.leverage),
        trade_mode=int(raw.trade_mode),
        margin_mode=int(raw.margin_mode),
        trade_allowed=bool(raw.trade_allowed),
        trade_expert=bool(raw.trade_expert),
        balance=float(raw.balance),
        equity=float(raw.equity),
        profit=float(raw.profit),
        credit=float(raw.credit),
        margin=float(raw.margin),
        margin_free=float(raw.margin_free),
        margin_level=float(raw.margin_level),
        margin_so_call=float(raw.margin_so_call),
        margin_so_so=float(raw.margin_so_so),
        margin_so_mode=int(raw.margin_so_mode),
        captured_at_utc=captured_at,
    )


def terminal_from_raw(raw: Any) -> TerminalSnapshot:
    return TerminalSnapshot(
        connected=bool(raw.connected),
        trade_allowed=bool(raw.trade_allowed),
        tradeapi_disabled=bool(raw.tradeapi_disabled),
        dlls_allowed=bool(raw.dlls_allowed),
        build=int(raw.build),
        maxbars=int(raw.maxbars),
        ping_last_us=int(raw.ping_last),
        company=str(raw.company),
        name=str(raw.name),
        path=str(raw.path),
        data_path=str(raw.data_path),
    )


class MT5Client:
    def __init__(
        self,
        env: EnvSettings,
        mode: TradingMode,
        mt5_module: Any | None = None,
        clock: Clock | None = None,
        allow_trading: bool = False,
    ) -> None:
        if allow_trading and not mode.may_send_broker_orders:
            raise SafetyViolation(f"allow_trading is not permitted in {mode} mode")
        self.env = env
        self.mode = mode
        self.clock = clock or SystemClock()
        self.allow_trading = allow_trading
        self._mt5 = mt5_module
        self._lock = threading.RLock()
        self._backoff = _Backoff()
        self.connected = False
        self.identity: tuple[Any, ...] | None = None
        self.stats: dict[str, CallStats] = {}
        self.last_report: ConnectionReport | None = None

    # ----------------------------------------------------------------------------- module
    @property
    def mt5(self) -> Any:
        if self._mt5 is None:
            try:
                import MetaTrader5  # Windows-only package

                self._mt5 = MetaTrader5
            except ImportError as exc:
                raise BrokerUnavailable("the MetaTrader5 package is not available (Windows only)") from exc
        return self._mt5

    @property
    def module_version(self) -> str:
        return str(getattr(self.mt5, "__version__", "unknown"))

    # ----------------------------------------------------------------------------- calls
    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name in TRADING_FUNCTIONS and not self.allow_trading:
            raise SafetyViolation(f"{name} is not allowed: this client is read-only ({self.mode} mode)")
        stats = self.stats.setdefault(name, CallStats())
        with self._lock:
            t0 = time.perf_counter()
            result = getattr(self.mt5, name)(*args, **kwargs)
            latency = (time.perf_counter() - t0) * 1000
            if result is None or result is False:
                err = self.mt5.last_error()
                stats.errors += 1
                stats.last_error = (int(err[0]), str(err[1])) if err else None
        stats.calls += 1
        stats.last_latency_ms = latency
        stats.avg_latency_ms = latency if stats.calls == 1 else stats.avg_latency_ms * 0.9 + latency * 0.1
        return result

    def last_error(self) -> tuple[int, str]:
        with self._lock:
            err = self.mt5.last_error()
        return (int(err[0]), str(err[1])) if err else (0, "")

    # ------------------------------------------------------------------------ lifecycle
    def connect(self) -> ConnectionReport:
        env = self.env
        if env.MT5_LOGIN is None or env.MT5_PASSWORD is None or not env.MT5_SERVER:
            raise BrokerUnavailable("MT5_LOGIN, MT5_PASSWORD and MT5_SERVER are required to connect")
        with self._lock:
            ok = self.mt5.initialize(
                env.MT5_TERMINAL_PATH or None,
                login=env.MT5_LOGIN,
                password=env.MT5_PASSWORD.get_secret_value(),
                server=env.MT5_SERVER,
                timeout=env.MT5_TIMEOUT_MS,
                portable=env.MT5_PORTABLE,
            )
            if not ok:
                err = self.mt5.last_error()
                self.mt5.shutdown()
                self.connected = False
                raise BrokerUnavailable(
                    f"MT5 initialize failed for {mask_login(env.MT5_LOGIN)}@{env.MT5_SERVER}: {err}"
                )
            raw_terminal = self.mt5.terminal_info()
            raw_account = self.mt5.account_info()
            version = self.mt5.version()
        if raw_terminal is None or raw_account is None:
            self.shutdown()
            raise BrokerUnavailable(
                f"terminal/account info unavailable after initialize: {self.last_error()}"
            )
        terminal = terminal_from_raw(raw_terminal)
        account = account_from_raw(raw_account, self.clock.now_utc())
        result = verify_connection(self.mode, env, account, terminal)
        for warning in result.warnings:
            log.warning("MT5 verification warning: %s", warning)
        if not result.ok:
            self.shutdown()
            raise AccountVerificationError("; ".join(result.problems))
        if self.identity is not None and account.identity() != self.identity:
            self.shutdown()
            raise AccountVerificationError("account identity changed since the first connection of this run")
        self.identity = account.identity()
        self.connected = True
        self._backoff.reset()
        self.last_report = ConnectionReport(account, terminal, result, tuple(version) if version else None)
        log.info(
            "connected to MT5 %s@%s (%s, %s, %s), terminal build %s",
            mask_login(account.login),
            account.server,
            account.trade_mode_name,
            account.margin_mode_name,
            account.currency,
            terminal.build,
        )
        return self.last_report

    def is_healthy(self) -> bool:
        if not self.connected:
            return False
        try:
            term = self.call("terminal_info")
            acct = self.call("account_info") if term is not None else None
        except Exception:  # broad on purpose: any failure means unhealthy
            log.exception("MT5 health probe raised")
            return False
        return bool(term is not None and term.connected and acct is not None)

    def ensure_connected(self) -> bool:
        """Reconnect if needed, respecting exponential backoff. Never raises."""
        if self.is_healthy():
            return True
        self.connected = False
        now = self.clock.monotonic()
        if now < self._backoff.next_attempt:
            return False
        try:
            with self._lock:
                self.mt5.shutdown()
            self.connect()
            log.info("MT5 reconnected after %d attempt(s)", self._backoff.attempts + 1)
            return True
        except AccountVerificationError:
            # identity mismatch is not transient; stay down and let breakers/operators react
            log.critical("MT5 reconnect refused: account verification failed")
            self._backoff.failed(now)
            return False
        except Exception as exc:
            self._backoff.failed(now)
            log.warning("MT5 reconnect failed (retry in %.0fs): %s", self._backoff.delay, exc)
            return False

    def shutdown(self) -> None:
        with self._lock:
            try:
                self.mt5.shutdown()
            finally:
                self.connected = False
