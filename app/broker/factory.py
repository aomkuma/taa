"""Build MT5 clients/gateways from settings, using either the real terminal or FakeMT5 (dev/tests)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.broker import mt5_constants as c
from app.broker.fake_mt5 import ALL_SYMBOLS, FakeAccount, FakeMT5
from app.broker.gateway import ReadOnlyMT5Gateway
from app.broker.mt5_client import MT5Client
from app.config import Settings
from app.core.clock import Clock, ServerClock, SystemClock
from app.core.enums import TradingMode
from app.core.errors import SafetyViolation


@dataclass
class BrokerBundle:
    client: MT5Client
    gateway: ReadOnlyMT5Gateway
    server_clock: ServerClock
    fake: FakeMT5 | None = None


def fake_module_for(settings: Settings, clock: Clock) -> FakeMT5:
    """A FakeMT5 whose account matches the configured credentials.

    PAPER gets an investor (read-only) login; DEMO a trading login, as with the master password; LIVE a
    trading login on a REAL account (tests and drills only: a fake account never moves money).
    """
    env = settings.env
    account = FakeAccount(
        login=env.MT5_LOGIN or 12345678,
        password=env.MT5_PASSWORD.get_secret_value() if env.MT5_PASSWORD else "investor-pass",
        server=env.MT5_SERVER or "FBS-Demo",
        investor=not settings.mode.may_send_broker_orders,
        trade_mode=c.ACCOUNT_TRADE_MODE_REAL
        if settings.mode is TradingMode.LIVE
        else c.ACCOUNT_TRADE_MODE_DEMO,
    )
    return FakeMT5(clock, account=account, symbols=ALL_SYMBOLS, tz=env.BROKER_TIMEZONE)


def build_read_only(
    settings: Settings, *, fake: bool = False, clock: Clock | None = None, mt5_module: Any | None = None
) -> BrokerBundle:
    clock = clock or SystemClock()
    module = mt5_module
    fake_module = None
    if fake and module is None:
        fake_module = fake_module_for(settings, clock)
        module = fake_module
    client = MT5Client(settings.env, settings.mode, mt5_module=module, clock=clock, allow_trading=False)
    server_clock = ServerClock(settings.env.BROKER_TIMEZONE, clock)
    return BrokerBundle(client, ReadOnlyMT5Gateway(client, server_clock), server_clock, fake_module)


def live_confirmation(login: int) -> str:
    """The account-bound phrase LIVE needs (``app.risk.mode_gates.confirmation_phrase`` checks it again)."""
    return f"I-ACCEPT-LIVE-RISK-{login}"


def build_trading(
    settings: Settings, *, fake: bool = False, clock: Clock | None = None, mt5_module: Any | None = None
) -> BrokerBundle:
    """A trading-enabled bundle: DEMO with ``ENABLE_DEMO_TRADING=true``, or LIVE with
    ``ENABLE_LIVE_TRADING=true`` and the account-bound ``LIVE_TRADING_CONFIRMATION`` (PLAN §A3; TAA-1401).
    Anything else is refused.

    The account itself is checked again after connecting (``verify_connection`` requires a DEMO account in
    DEMO mode and a REAL one in LIVE mode), by the live gate before every order and by
    :class:`~app.broker.execution.ExecutionGateway` before every request.
    """
    env = settings.env
    if settings.mode is TradingMode.DEMO:
        if not env.ENABLE_DEMO_TRADING:
            raise SafetyViolation("DEMO trading needs ENABLE_DEMO_TRADING=true")
    elif settings.mode is TradingMode.LIVE:
        if not env.ENABLE_LIVE_TRADING:
            raise SafetyViolation("LIVE trading needs ENABLE_LIVE_TRADING=true")
        if env.MT5_LOGIN is None or live_confirmation(env.MT5_LOGIN) != env.LIVE_TRADING_CONFIRMATION:
            raise SafetyViolation(
                "LIVE trading needs LIVE_TRADING_CONFIRMATION=I-ACCEPT-LIVE-RISK-<MT5_LOGIN> for this login"
            )
    else:
        raise SafetyViolation(f"broker orders need DEMO or LIVE (TRADING_MODE={settings.mode.value})")
    clock = clock or SystemClock()
    module = mt5_module
    fake_module = None
    if fake and module is None:
        fake_module = fake_module_for(settings, clock)
        module = fake_module
    client = MT5Client(settings.env, settings.mode, mt5_module=module, clock=clock, allow_trading=True)
    server_clock = ServerClock(settings.env.BROKER_TIMEZONE, clock)
    return BrokerBundle(client, ReadOnlyMT5Gateway(client, server_clock), server_clock, fake_module)
