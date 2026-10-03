from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.broker import mt5_constants as c
from app.broker.factory import build_read_only
from app.broker.fake_mt5 import FakeAccount, FakeMT5, FakeSymbol, FakeTerminal
from app.broker.filling import allowed_fillings, resolve_filling
from app.broker.gateway import ReadOnlyMT5Gateway
from app.broker.mt5_client import MT5Client
from app.broker.retcodes import RetcodeClass, classify, describe
from app.broker.symbol_service import SymbolService
from app.config import load_settings
from app.core.clock import ManualClock, ServerClock
from app.core.enums import Side, TradingMode
from app.core.errors import AccountVerificationError, BrokerUnavailable, SafetyViolation, SymbolUnavailable

WEEKDAY = datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC)  # Wednesday, EEST (+3)

ENV = {
    "TRADING_MODE": "PAPER",
    "MT5_LOGIN": "12345678",
    "MT5_PASSWORD": "investor-pass",
    "MT5_SERVER": "FBS-Demo",
    "MT5_TERMINAL_PATH": "C:/MT5/terminal64.exe",
}


def settings(**overrides: str):  # type: ignore[no-untyped-def]
    return load_settings(env_file=None, config_file="config.yaml", environ={**ENV, **overrides})


@pytest.fixture
def wclock() -> ManualClock:
    return ManualClock(WEEKDAY)


def make(
    clock: ManualClock,
    mode: str = "PAPER",
    account: FakeAccount | None = None,
    terminal: FakeTerminal | None = None,
    **env: str,
):  # type: ignore[no-untyped-def]
    fake = FakeMT5(clock, account=account, terminal=terminal, history_days=20, future_days=3)
    s = settings(TRADING_MODE=mode, **env)
    client = MT5Client(s.env, s.mode, mt5_module=fake, clock=clock)
    return fake, client, ReadOnlyMT5Gateway(client, ServerClock("Europe/Athens", clock))


class TestConnection:
    def test_connect_passes_explicit_credentials(self, wclock: ManualClock) -> None:
        fake, client, _ = make(wclock)
        report = client.connect()
        assert report.account.login == 12345678
        assert fake.init_kwargs["login"] == 12345678
        assert fake.init_kwargs["server"] == "FBS-Demo"
        assert fake.init_kwargs["password_given"] and fake.init_kwargs["portable"] is True

    def test_wrong_password_fails_without_leaking(self, wclock: ManualClock) -> None:
        _, client, _ = make(wclock, MT5_PASSWORD="wrong-secret-xyz")
        with pytest.raises(BrokerUnavailable) as exc:
            client.connect()
        assert "wrong-secret-xyz" not in str(exc.value)
        assert "*****678" in str(exc.value)

    def test_wrong_server_rejected(self, wclock: ManualClock) -> None:
        fake, client, _ = make(wclock)
        fake.account.server = "FBS-Real"
        with pytest.raises(BrokerUnavailable):  # authorization mismatch at initialize
            client.connect()

    def test_paper_refuses_master_password(self, wclock: ManualClock) -> None:
        _, client, _ = make(wclock, account=FakeAccount(investor=False))
        with pytest.raises(AccountVerificationError, match="investor"):
            client.connect()

    def test_paper_master_password_allowed_with_flag(self, wclock: ManualClock) -> None:
        _, client, _ = make(wclock, account=FakeAccount(investor=False), PAPER_ALLOW_MASTER_PASSWORD="true")
        report = client.connect()
        assert report.verification.warnings

    def test_netting_account_refused(self, wclock: ManualClock) -> None:
        _, client, _ = make(wclock, account=FakeAccount(margin_mode=c.ACCOUNT_MARGIN_MODE_RETAIL_NETTING))
        with pytest.raises(AccountVerificationError, match="HEDGING"):
            client.connect()

    def test_demo_mode_refuses_real_account(self, wclock: ManualClock) -> None:
        acct = FakeAccount(investor=False, trade_mode=c.ACCOUNT_TRADE_MODE_REAL)
        _, client, _ = make(wclock, mode="DEMO", account=acct, ENABLE_DEMO_TRADING="true")
        with pytest.raises(AccountVerificationError, match="DEMO"):
            client.connect()

    def test_demo_requires_algo_trading(self, wclock: ManualClock) -> None:
        _, client, _ = make(
            wclock,
            mode="DEMO",
            account=FakeAccount(investor=False),
            ENABLE_DEMO_TRADING="true",
            terminal=FakeTerminal(trade_allowed=False),
        )
        with pytest.raises(AccountVerificationError, match="Algo Trading"):
            client.connect()

    def test_order_functions_refused_in_read_only_client(self, wclock: ManualClock) -> None:
        fake, client, _ = make(wclock)
        client.connect()
        with pytest.raises(SafetyViolation):
            client.call("order_send", {})
        with pytest.raises(SafetyViolation):
            client.call("order_check", {})
        assert fake.calls["order_send"] == 0

    def test_allow_trading_forbidden_in_paper(self) -> None:
        s = settings()
        with pytest.raises(SafetyViolation):
            MT5Client(s.env, TradingMode.PAPER, allow_trading=True)

    def test_reconnect_with_backoff(self, wclock: ManualClock) -> None:
        fake, client, _ = make(wclock)
        client.connect()
        fake.disconnect()
        fake.fail_next("initialize", times=1)
        assert client.ensure_connected() is False  # attempt 1 fails
        assert client.ensure_connected() is False  # within backoff window: no attempt
        assert fake.calls["initialize"] == 2
        fake.reconnect()
        wclock.advance(1.5)
        assert client.ensure_connected() is True
        assert fake.calls["initialize"] == 3

    def test_identity_change_on_reconnect_refused(self, wclock: ManualClock) -> None:
        fake, client, _ = make(wclock)
        client.connect()
        fake.account.currency = "EUR"
        client.connected = False
        with pytest.raises(AccountVerificationError, match="identity"):
            client.connect()

    def test_leverage_tier_change_does_not_block_reconnect(self, wclock: ManualClock) -> None:
        """FBS changes Forex leverage by equity tier; that must not look like a different account."""
        fake, client, _ = make(wclock, account=FakeAccount(tiered_leverage=True, balance=4_900.0))
        first = client.connect()
        assert first.account.leverage == 2000
        fake.account.balance = 5_100.0  # crosses the $5,000 tier
        client.connected = False
        second = client.connect()
        assert second.account.leverage == 1000


class TestGateway:
    def test_symbol_spec_and_tick(self, wclock: ManualClock) -> None:
        _, client, gw = make(wclock)
        client.connect()
        spec = gw.symbol_spec("EURUSD")
        assert spec.digits == 5 and spec.contract_size == 100_000 and not spec.validation_errors()
        tick = gw.tick("EURUSD")
        assert tick is not None and tick.ask > tick.bid
        assert abs((tick.time_utc - WEEKDAY).total_seconds()) < 2  # server epoch converted back to UTC

    def test_unknown_symbol(self, wclock: ManualClock) -> None:
        _, client, gw = make(wclock)
        client.connect()
        with pytest.raises(SymbolUnavailable):
            gw.symbol_spec("NOPE")

    def test_calc_profit_sign_and_conversion(self, wclock: ManualClock) -> None:
        _, client, gw = make(wclock)
        client.connect()
        loss = gw.calc_profit(Side.BUY, "EURUSD", 1.0, 1.1000, 1.0990)
        assert loss == pytest.approx(-100.0)
        jpy = gw.calc_profit(Side.SELL, "USDJPY", 1.0, 150.0, 151.0)
        assert jpy is not None and jpy < 0
        assert gw.calc_margin(Side.BUY, "EURUSD", 1.0, 1.1) is not None

    def test_rates_range_filters_by_utc(self, wclock: ManualClock) -> None:
        from app.core.enums import Timeframe

        _, client, gw = make(wclock)
        client.connect()
        start = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
        end = datetime(2026, 9, 29, 6, 0, tzinfo=UTC)
        df = gw.rates_range("EURUSD", Timeframe.H1, start, end)
        assert len(df) == 6
        utc = gw.server_clock.server_epochs_to_utc(df["time"].to_numpy())
        assert utc[0] == start

    def test_deals_window_and_cash_flows(self, wclock: ManualClock) -> None:
        from app.broker.account_service import AccountService

        fake, client, gw = make(wclock)
        client.connect()
        sc = gw.server_clock
        fake.add_deal(ticket=1, type=c.DEAL_TYPE_BALANCE, profit=500.0, time=sc.utc_to_server_epoch(WEEKDAY))
        fake.add_deal(ticket=2, type=c.DEAL_TYPE_BUY, profit=-3.0, time=sc.utc_to_server_epoch(WEEKDAY))
        svc = AccountService(gw)
        flows = svc.cash_flows(datetime(2026, 9, 30, tzinfo=UTC), datetime(2026, 10, 1, tzinfo=UTC))
        assert [d.ticket for d in flows] == [1]

    def test_account_identity_changes(self, wclock: ManualClock) -> None:
        from app.broker.account_service import AccountService

        fake, client, gw = make(wclock)
        client.connect()
        svc = AccountService(gw)
        base = svc.snapshot()
        assert svc.identity_changes(base) == []
        fake.account.leverage = 200
        changes = svc.identity_changes(svc.snapshot())
        assert [(ch.field, ch.critical) for ch in changes] == [("leverage", False)]
        svc.acknowledge_monitored(svc.snapshot())
        assert svc.identity_changes(svc.snapshot()) == []
        fake.account.trade_mode = c.ACCOUNT_TRADE_MODE_REAL
        critical = svc.identity_changes(svc.snapshot())
        assert [(ch.field, ch.critical) for ch in critical] == [("trade_mode", True)]


class TestSymbolsAndFilling:
    def test_registry_disables_bad_symbols(self, wclock: ManualClock) -> None:
        fake, client, gw = make(wclock)
        fake.symbols["BADSYM"] = FakeSymbol("BADSYM", 1.0, 0.0001, 5, 0, "AAA", "USD")  # contract size 0
        fake.symbols["CLOSED"] = FakeSymbol(
            "CLOSED", 1.0, 0.0001, 5, 100_000, "BBB", "USD", trade_mode=c.SYMBOL_TRADE_MODE_DISABLED
        )
        client.connect()
        reg = SymbolService(gw).load(["EURUSD", "BADSYM", "CLOSED", "MISSING"])
        assert reg.available() == ["EURUSD"]
        assert "contract_size" in reg.errors["BADSYM"]
        assert "disabled" in reg.errors["CLOSED"]
        assert "MISSING" in reg.errors
        with pytest.raises(SymbolUnavailable):
            reg.get("BADSYM")

    def test_filling_rules(self, wclock: ManualClock) -> None:
        _, client, gw = make(wclock)
        client.connect()
        spec = gw.symbol_spec("EURUSD")
        assert resolve_filling(spec) == c.ORDER_FILLING_FOK
        ioc_only = replace(spec, filling_mode=c.SYMBOL_FILLING_IOC)
        assert allowed_fillings(ioc_only) == [c.ORDER_FILLING_IOC]
        none = replace(spec, filling_mode=0)
        assert resolve_filling(none) is None  # market execution never allows RETURN
        instant = replace(spec, filling_mode=0, execution_mode=c.SYMBOL_TRADE_EXECUTION_INSTANT)
        assert c.ORDER_FILLING_RETURN in allowed_fillings(instant)


def test_retcodes() -> None:
    assert classify(10009) is RetcodeClass.SUCCESS
    assert classify(None) is RetcodeClass.UNKNOWN
    assert classify(10027) is RetcodeClass.GLOBAL_HALT
    assert describe(10016) == "10016 INVALID_STOPS"


def test_factory_fake_bundle(wclock: ManualClock) -> None:
    bundle = build_read_only(settings(), fake=True, clock=wclock)
    assert bundle.fake is not None
    bundle.client.connect()
    assert bundle.gateway.account().login == 12345678
