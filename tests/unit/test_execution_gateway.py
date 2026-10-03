from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from app.broker import mt5_constants as c
from app.broker.execution import ExecutionGateway, RequestBuilder, safe_comment
from app.broker.factory import BrokerBundle, build_read_only, build_trading
from app.broker.models import BrokerPosition
from app.broker.retcodes import RetcodeClass
from app.config import Settings, load_settings
from app.core.clock import ManualClock
from app.core.enums import Side, TradingMode
from app.core.errors import AccountVerificationError, SafetyViolation
from tests.strategy_data import EURUSD_SPEC

WED = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
SAT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def settings(mode: str = "DEMO", **env: str) -> Settings:
    base = {
        "TRADING_MODE": mode,
        "MT5_LOGIN": "12345678",
        "MT5_PASSWORD": "master-pass",
        "MT5_SERVER": "FBS-Demo",
        "MT5_TERMINAL_PATH": "x",
        "ENABLE_DEMO_TRADING": "true",
    }
    base.update(env)
    return load_settings(env_file=None, config_file="config.yaml", environ=base)


def connected(at: datetime = WED) -> tuple[BrokerBundle, ExecutionGateway, ManualClock]:
    clock = ManualClock(at)
    bundle = build_trading(settings(), fake=True, clock=clock)
    bundle.client.connect()
    return bundle, ExecutionGateway(bundle.client), clock


def quote(bundle: BrokerBundle, symbol: str = "EURUSD") -> tuple[float, float]:
    tick = bundle.gateway.tick(symbol)
    assert tick is not None
    return tick.bid, tick.ask


BUILDER = RequestBuilder(deviation_points=10)


class TestRequestBuilder:
    def test_market_entry(self) -> None:
        req = BUILDER.market_entry(
            EURUSD_SPEC, Side.BUY, 0.24, 1.100004, 1.098, 1.104, magic=7_310_000, comment="taa:0190ab12-cd"
        )
        assert req["action"] == c.TRADE_ACTION_DEAL and req["type"] == c.ORDER_TYPE_BUY
        assert req["price"] == 1.1  # aligned to the tick
        assert (req["sl"], req["tp"], req["deviation"], req["magic"]) == (1.098, 1.104, 10, 7_310_000)
        assert req["type_time"] == c.ORDER_TIME_GTC and req["type_filling"] == c.ORDER_FILLING_FOK

    def test_comment_is_short_ascii(self) -> None:
        assert safe_comment("taa:ทดสอบ-0123456789abcdefghijklmnop") == "taa:-0123456789abcdefghij"
        assert len(safe_comment("x" * 40)) == 25

    def test_no_stop_no_order(self) -> None:
        with pytest.raises(SafetyViolation):
            BUILDER.market_entry(EURUSD_SPEC, Side.SELL, 0.1, 1.1, 0.0, None, magic=1, comment="")
        pos = BrokerPosition(1, "EURUSD", Side.BUY, 0.1, 1.1, 1.098, 0.0, 1.1, 0.0, 0.0, 1, "", WED, 1)
        with pytest.raises(SafetyViolation):
            BUILDER.modify_stops(EURUSD_SPEC, pos, 0.0, None)
        close = BUILDER.close(EURUSD_SPEC, pos, 1.1)
        assert (close["type"], close["position"], close["volume"]) == (c.ORDER_TYPE_SELL, 1, 0.1)

    def test_symbol_without_a_filling_mode(self) -> None:
        odd = dataclasses.replace(EURUSD_SPEC, filling_mode=0)
        with pytest.raises(Exception, match="filling"):
            BUILDER.market_entry(odd, Side.BUY, 0.1, 1.1, 1.098, None, magic=1, comment="")


class TestGuards:
    def test_trading_client_only_in_demo_with_the_flag(self) -> None:
        with pytest.raises(SafetyViolation, match="DEMO only"):
            build_trading(
                load_settings(
                    env_file=None,
                    config_file="config.yaml",
                    environ={
                        "TRADING_MODE": "PAPER",
                        "MT5_LOGIN": "1",
                        "MT5_PASSWORD": "p",
                        "MT5_SERVER": "s",
                        "MT5_TERMINAL_PATH": "x",
                    },
                ),
                fake=True,
            )
        with pytest.raises(SafetyViolation, match="ENABLE_DEMO_TRADING"):
            build_trading(settings(ENABLE_DEMO_TRADING="false"), fake=True)

    def test_gateway_refuses_read_only_and_live(self) -> None:
        read_only = build_read_only(settings(), fake=True)
        with pytest.raises(SafetyViolation, match="trading-enabled"):
            ExecutionGateway(read_only.client)
        bundle = build_trading(settings(), fake=True)
        bundle.client.mode = TradingMode.LIVE
        with pytest.raises(SafetyViolation, match="DEMO only"):
            ExecutionGateway(bundle.client)

    def test_a_real_account_is_refused(self) -> None:
        clock = ManualClock(WED)
        bundle = build_trading(settings(), fake=True, clock=clock)
        assert bundle.fake is not None
        bundle.fake.account.trade_mode = c.ACCOUNT_TRADE_MODE_REAL
        with pytest.raises(AccountVerificationError):
            bundle.client.connect()

    def test_requests_need_a_verified_connection(self) -> None:
        bundle = build_trading(settings(), fake=True, clock=ManualClock(WED))
        gw = ExecutionGateway(bundle.client)
        with pytest.raises(SafetyViolation, match="verified DEMO"):
            gw.check({})


class TestFakeTradeServer:
    def entry(self, bundle: BrokerBundle, side: Side = Side.BUY, **kw: float):  # type: ignore[no-untyped-def]
        bid, ask = quote(bundle)
        price = ask if side is Side.BUY else bid
        sl = kw.get("sl", price - 0.002 if side is Side.BUY else price + 0.002)
        tp = kw.get("tp", price + 0.004 if side is Side.BUY else price - 0.004)
        return BUILDER.market_entry(
            EURUSD_SPEC,
            side,
            kw.get("volume", 0.1),
            kw.get("price", price),
            sl,
            tp,
            magic=7_310_000,
            comment="taa:t",
        )

    def test_open_modify_close(self) -> None:
        bundle, gw, _ = connected()
        assert gw.check(self.entry(bundle)).ok
        result = gw.send(self.entry(bundle))
        assert result.ok and result.retcode == 10009 and result.deal and result.volume == 0.1
        [pos] = bundle.gateway.positions()
        assert pos.magic == 7_310_000 and pos.sl > 0
        modified = gw.send(BUILDER.modify_stops(EURUSD_SPEC, pos, pos.sl + 0.0005, pos.tp))
        assert modified.ok
        assert bundle.gateway.positions()[0].sl == pytest.approx(pos.sl + 0.0005)
        same = gw.send(
            BUILDER.modify_stops(EURUSD_SPEC, bundle.gateway.positions()[0], pos.sl + 0.0005, pos.tp)
        )
        assert same.retcode == 10025
        bid, _ = quote(bundle)
        closed = gw.send(BUILDER.close(EURUSD_SPEC, bundle.gateway.positions()[0], bid))
        assert closed.ok and bundle.gateway.positions() == []
        deals = bundle.gateway.deals(WED - timedelta(days=1), WED + timedelta(days=1))
        assert [d.entry for d in deals] == [c.DEAL_ENTRY_IN, c.DEAL_ENTRY_OUT]

    @pytest.mark.parametrize(
        ("kw", "code"),
        [
            ({"volume": 0.015}, 10014),
            ({"sl": 1.5}, 10016),  # a BUY stop above the price
            ({"price": 1.0}, 10004),  # far outside the deviation
        ],
    )
    def test_server_rejections(self, kw: dict[str, float], code: int) -> None:
        bundle, gw, _ = connected()
        assert gw.check(self.entry(bundle, **kw)).retcode == code
        result = gw.send(self.entry(bundle, **kw))
        assert result.retcode == code and not result.ok
        assert bundle.gateway.positions() == []

    def test_market_closed_on_saturday(self) -> None:
        bundle, gw, _ = connected(SAT)
        assert gw.send(self.entry(bundle)).retcode == 10018

    def test_unknown_outcome_is_reported_as_unknown(self) -> None:
        bundle, gw, _ = connected()
        assert bundle.fake is not None
        bundle.fake.desk.force(None)
        lost = gw.send(self.entry(bundle))
        assert lost.retcode is None and lost.retcode_class is RetcodeClass.UNKNOWN
        assert bundle.gateway.positions() == []
        bundle.fake.desk.force(None, executes=True)  # the order went through but the answer was lost
        hidden = gw.send(self.entry(bundle))
        assert hidden.retcode_class is RetcodeClass.UNKNOWN
        assert len(bundle.gateway.positions()) == 1

    def test_stops_are_executed_by_the_server(self) -> None:
        bundle, gw, _ = connected()
        gw.send(self.entry(bundle))
        assert bundle.fake is not None
        bundle.fake.positions[0].sl = 2.0  # the price is now through the stop
        assert bundle.gateway.positions() == []
        out = bundle.gateway.deals(WED - timedelta(days=1), WED + timedelta(days=1))[-1]
        assert out.entry == c.DEAL_ENTRY_OUT

    def test_order_send_counts_every_attempt(self) -> None:
        bundle, gw, _ = connected()
        assert bundle.fake is not None
        before = bundle.fake.calls["order_send"]
        gw.send(self.entry(bundle))
        assert bundle.fake.calls["order_send"] == before + 1
