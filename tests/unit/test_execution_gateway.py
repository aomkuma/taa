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
    def test_trading_client_only_in_demo_or_live_with_their_gates(self) -> None:
        with pytest.raises(SafetyViolation, match="DEMO or LIVE"):
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
        live = {"MT5_SERVER": "FBS-Real", "ENABLE_DEMO_TRADING": "false"}
        with pytest.raises(SafetyViolation, match="ENABLE_LIVE_TRADING"):
            build_trading(settings("LIVE", **live), fake=True)
        for phrase in ("", "I-ACCEPT-LIVE-RISK-99999999", "i-accept-live-risk-12345678"):
            with pytest.raises(SafetyViolation, match="LIVE_TRADING_CONFIRMATION"):
                build_trading(
                    settings("LIVE", ENABLE_LIVE_TRADING="true", LIVE_TRADING_CONFIRMATION=phrase, **live),
                    fake=True,
                )
        ok = settings(
            "LIVE",
            ENABLE_LIVE_TRADING="true",
            LIVE_TRADING_CONFIRMATION="I-ACCEPT-LIVE-RISK-12345678",
            **live,
        )
        bundle = build_trading(ok, fake=True, clock=ManualClock(WED))
        assert bundle.client.allow_trading and bundle.fake is not None
        assert bundle.fake.account.trade_mode == c.ACCOUNT_TRADE_MODE_REAL
        bundle.client.connect()  # a LIVE connection needs a REAL account
        gw = ExecutionGateway(bundle.client)
        gw._require_demo_account()  # the account guard passes: a REAL account in LIVE mode

    def test_gateway_refuses_read_only_and_a_mismatched_account(self) -> None:
        read_only = build_read_only(settings(), fake=True)
        with pytest.raises(SafetyViolation, match="trading-enabled"):
            ExecutionGateway(read_only.client)
        bundle = build_trading(settings(), fake=True, clock=ManualClock(WED))
        bundle.client.connect()  # a DEMO account
        bundle.client.mode = TradingMode.LIVE  # a LIVE client on a demo account: every request is refused
        with pytest.raises(SafetyViolation, match="verified REAL"):
            ExecutionGateway(bundle.client).check({})

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


class TestPendingOrders:
    """Limit parts of an entry plan (TAA-1207) on the fake trade server."""

    def limit(self, bundle: BrokerBundle, side: Side = Side.BUY, **kw: object):  # type: ignore[no-untyped-def]
        bid, ask = quote(bundle)
        price = float(kw.get("price", ask - 0.001 if side is Side.BUY else bid + 0.001))  # type: ignore[arg-type]
        sign = side.sign
        return BUILDER.limit_entry(
            EURUSD_SPEC,
            side,
            float(kw.get("volume", 0.1)),  # type: ignore[arg-type]
            price,
            float(kw.get("sl", price - 0.002 * sign)),  # type: ignore[arg-type]
            price + 0.004 * sign,
            magic=7_310_000,
            comment="taa:limit",
            filling=int(kw.get("filling", c.ORDER_FILLING_RETURN)),  # type: ignore[call-overload]
            expiration_server=kw.get("expiration"),  # type: ignore[arg-type]
        )

    def test_builder(self) -> None:
        req = BUILDER.limit_entry(
            EURUSD_SPEC,
            Side.SELL,
            0.05,
            1.10123,
            1.103,
            1.098,
            magic=9,
            comment="x",
            filling=2,
            expiration_server=123,
        )
        assert (req["action"], req["type"], req["type_time"], req["expiration"]) == (
            c.TRADE_ACTION_PENDING,
            c.ORDER_TYPE_SELL_LIMIT,
            c.ORDER_TIME_SPECIFIED,
            123,
        )
        gtc = BUILDER.limit_entry(
            EURUSD_SPEC,
            Side.BUY,
            0.05,
            1.099,
            1.098,
            None,
            magic=9,
            comment="x",
            filling=2,
            expiration_server=None,
        )
        assert gtc["type_time"] == c.ORDER_TIME_GTC and "expiration" not in gtc and gtc["tp"] == 0.0
        with pytest.raises(SafetyViolation):
            BUILDER.limit_entry(
                EURUSD_SPEC,
                Side.BUY,
                0.05,
                1.099,
                0.0,
                None,
                magic=9,
                comment="x",
                filling=2,
                expiration_server=None,
            )
        assert BUILDER.remove_order(77) == {"action": c.TRADE_ACTION_REMOVE, "order": 77}
        assert RequestBuilder.pending_fillings(EURUSD_SPEC) == [c.ORDER_FILLING_RETURN, c.ORDER_FILLING_FOK]

    def test_place_list_fill_and_close_at_the_stop(self) -> None:
        bundle, gw, _ = connected()
        assert bundle.fake is not None
        placed = gw.send(self.limit(bundle))
        assert placed.ok and placed.retcode == 10008 and placed.order and placed.deal == 0
        [order] = bundle.gateway.orders()
        assert (order.ticket, order.side, order.type, order.volume) == (
            placed.order,
            Side.BUY,
            c.ORDER_TYPE_BUY_LIMIT,
            0.1,
        )
        assert order.expiration_utc is None and bundle.gateway.positions() == []
        bundle.fake.price_override["EURUSD"] = order.price_open - 0.0005  # the ask trades through the limit
        [pos] = bundle.gateway.positions()
        assert (pos.ticket, pos.identifier, pos.price_open, pos.sl, pos.comment) == (
            order.ticket,
            order.ticket,
            order.price_open,
            order.sl,
            "taa:limit",
        )
        assert bundle.gateway.orders() == []
        deal = bundle.gateway.deals(WED - timedelta(days=1), WED + timedelta(days=1))[-1]
        assert (deal.entry, deal.order, deal.position_id) == (c.DEAL_ENTRY_IN, order.ticket, order.ticket)

    def test_remove(self) -> None:
        bundle, gw, _ = connected()
        placed = gw.send(self.limit(bundle, Side.SELL))
        removed = gw.send(BUILDER.remove_order(placed.order))
        assert removed.ok and bundle.gateway.orders() == []
        assert gw.send(BUILDER.remove_order(placed.order)).retcode == 10013

    def test_broker_side_expiration(self) -> None:
        bundle, gw, clock = connected()
        expires = bundle.gateway.server_clock.utc_to_server_epoch(WED + timedelta(hours=4))
        placed = gw.send(self.limit(bundle, expiration=expires))
        assert placed.ok
        [order] = bundle.gateway.orders()
        assert order.expiration_utc == WED + timedelta(hours=4)
        clock.advance(4 * 3600 + 1)
        assert bundle.gateway.orders() == []

    @pytest.mark.parametrize(
        ("kw", "code"),
        [
            ({"price": 2.0}, 10015),  # a BUY limit above the market
            ({"sl": 1.5}, 10016),
            ({"volume": 0.015}, 10014),
            ({"filling": 7}, 10030),
            ({"expiration": 1}, 10022),  # already past
        ],
    )
    def test_rejections(self, kw: dict[str, object], code: int) -> None:
        bundle, gw, _ = connected()
        assert gw.check(self.limit(bundle, **kw)).retcode == code
        assert gw.send(self.limit(bundle, **kw)).retcode == code
        assert bundle.gateway.orders() == []

    def test_symbol_options(self) -> None:
        bundle, gw, _ = connected()
        assert bundle.fake is not None
        sym = bundle.fake.symbols["EURUSD"]
        sym.pending_return_filling = False
        assert gw.check(self.limit(bundle)).retcode == 10030
        assert gw.check(self.limit(bundle, filling=c.ORDER_FILLING_FOK)).ok
        sym.pending_expiration = False
        expires = bundle.gateway.server_clock.utc_to_server_epoch(WED + timedelta(hours=4))
        assert gw.check(self.limit(bundle, filling=c.ORDER_FILLING_FOK, expiration=expires)).retcode == 10022
