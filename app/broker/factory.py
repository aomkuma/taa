"""Build MT5 clients/gateways from settings, using either the real terminal or FakeMT5 (dev/tests)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.broker.fake_mt5 import ALL_SYMBOLS, FakeAccount, FakeMT5
from app.broker.gateway import ReadOnlyMT5Gateway
from app.broker.mt5_client import MT5Client
from app.config import Settings
from app.core.clock import Clock, ServerClock, SystemClock


@dataclass
class BrokerBundle:
    client: MT5Client
    gateway: ReadOnlyMT5Gateway
    server_clock: ServerClock
    fake: FakeMT5 | None = None


def fake_module_for(settings: Settings, clock: Clock) -> FakeMT5:
    """A FakeMT5 whose account matches the configured credentials (investor login unless overridden)."""
    env = settings.env
    account = FakeAccount(
        login=env.MT5_LOGIN or 12345678,
        password=env.MT5_PASSWORD.get_secret_value() if env.MT5_PASSWORD else "investor-pass",
        server=env.MT5_SERVER or "FBS-Demo",
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
