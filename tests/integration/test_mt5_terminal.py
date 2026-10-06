"""Contract tests against a REAL MetaTrader 5 terminal (read-only).

Skipped by default. To run on the Windows engine host with a configured ``.env`` (investor password):

    $env:TAA_MT5_TESTS="1"; .venv\\Scripts\\python -m pytest -m mt5 tests/integration/test_mt5_terminal.py

They assert the same contract the FakeMT5-based unit tests rely on, so differences in broker behavior
show up here first. Nothing in this file can place an order: the client is read-only.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

from app.broker.factory import build_read_only
from app.config import load_settings
from app.core.enums import Side, Timeframe, TradingMode
from app.market_data.candle_service import CandleService

pytestmark = [
    pytest.mark.mt5,
    pytest.mark.skipif(os.environ.get("TAA_MT5_TESTS") != "1", reason="set TAA_MT5_TESTS=1 to run"),
]


@pytest.fixture(scope="module")
def bundle():  # type: ignore[no-untyped-def]
    settings = load_settings()
    assert settings.mode is TradingMode.PAPER, "run terminal contract tests in PAPER mode only"
    b = build_read_only(settings)
    b.client.connect()
    yield settings, b
    b.client.shutdown()


def test_account_is_read_only_and_hedging(bundle) -> None:  # type: ignore[no-untyped-def]
    settings, b = bundle
    acct = b.gateway.account()
    assert acct.login == settings.env.MT5_LOGIN
    assert acct.is_hedging
    if not settings.env.PAPER_ALLOW_MASTER_PASSWORD:
        assert not acct.trade_allowed


def test_symbols_valid(bundle) -> None:  # type: ignore[no-untyped-def]
    settings, b = bundle
    for name in settings.config.symbols.allowed:
        spec = b.gateway.symbol_spec(name)
        assert spec.validation_errors() == [], name


def test_closed_candles_and_time_conversion(bundle) -> None:  # type: ignore[no-untyped-def]
    settings, b = bundle
    frame = CandleService(b.gateway, settings.config.timeframes).closed_candles(
        settings.config.symbols.reference_symbol, Timeframe.M15, 100, expect_live=False
    )
    assert len(frame) == 100
    now = b.client.clock.now_utc()
    assert frame.last_close_time is not None and frame.last_close_time <= now
    offset = int(frame.df["time_server"].iloc[-1]) - int(frame.df["open_time"].iloc[-1].timestamp())
    assert offset == b.server_clock.expected_offset_seconds(frame.last_open_time)


def test_calc_profit_sign(bundle) -> None:  # type: ignore[no-untyped-def]
    settings, b = bundle
    sym = settings.config.symbols.reference_symbol
    spec = b.gateway.symbol_spec(sym)
    tick = b.gateway.tick(sym)
    assert tick is not None
    loss = b.gateway.calc_profit(Side.BUY, sym, 1.0, tick.ask, tick.ask - 100 * spec.tick_size)
    assert loss is not None and loss < 0


def test_history_deals_query(bundle) -> None:  # type: ignore[no-untyped-def]
    _, b = bundle
    now = b.client.clock.now_utc()
    deals = b.gateway.deals(now - timedelta(days=30), now)
    assert isinstance(deals, list)


def test_symbol_catalog_and_ticks(bundle) -> None:  # type: ignore[no-untyped-def]
    settings, b = bundle
    specs = b.gateway.symbols()
    assert len(specs) >= len(settings.config.symbols.allowed)
    assert all(s.path for s in specs[:20])
    sym = settings.config.symbols.reference_symbol
    end = b.client.clock.now_utc()
    ticks = b.gateway.ticks_range(sym, end - timedelta(days=7), end)
    assert list(ticks.columns) == ["time_utc", "bid", "ask"]


@pytest.mark.skipif(
    os.environ.get("TAA_MT5_TRADING_TESTS") != "1",
    reason="set TAA_MT5_TRADING_TESTS=1 (a DEMO account with its master password) to run",
)
def test_order_check_answers_through_the_client() -> None:
    """order_check only, never order_send. On 2026-10-06 every order_check through MT5Client.call answered
    None, (-2, "Unnamed arguments not allowed"), because an empty **kwargs reached the C module."""
    from app.broker.execution import ExecutionGateway, RequestBuilder
    from app.broker.factory import build_trading

    os.environ.setdefault("TRADING_MODE", "DEMO")
    os.environ.setdefault("ENABLE_DEMO_TRADING", "true")
    settings = load_settings(env_file=".env", config_file="config.yaml")
    assert settings.mode is TradingMode.DEMO, "the order_check contract runs on a DEMO account only"
    b = build_trading(settings)
    b.client.connect()
    try:
        gw = ExecutionGateway(b.client)
        builder = RequestBuilder(10)
        sym = settings.config.symbols.reference_symbol
        spec = b.gateway.symbol_spec(sym)
        tick = b.gateway.tick(sym)
        assert tick is not None
        far = 200 * spec.tick_size
        market = builder.market_entry(
            spec, Side.BUY, spec.volume_min, tick.ask, tick.ask - far, None, magic=1, comment="taa:check"
        )
        assert gw.check(market).retcode is not None
        for filling in RequestBuilder.pending_fillings(spec):
            limit = builder.limit_entry(
                spec,
                Side.BUY,
                spec.volume_min,
                tick.ask - far,
                tick.ask - 2 * far,
                None,
                magic=1,
                comment="taa:check",
                filling=filling,
                expiration_server=None,
            )
            assert gw.check(limit).retcode is not None
    finally:
        b.client.shutdown()
