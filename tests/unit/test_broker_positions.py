from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.config import PositionManagementConfig
from app.core.enums import Timeframe
from app.core.errors import SafetyViolation
from app.engine.broker_positions import BrokerPositionManager
from app.monitoring.alerts import EventType
from app.storage.database import Database
from app.strategy.signal_models import StrategyContext
from tests.unit.test_order_manager import WED, Rig, execute, make_rig, record
from tests.unit.test_position_manager import Closer
from tests.unit.test_strategy_models import make_context

MAGIC = 7_310_000
ATR = 0.0005


@pytest.fixture
def rig(tmp_path: Path, db: Database) -> Rig:
    return make_rig(tmp_path, db)


def manager(rig: Rig, cfg: PositionManagementConfig | None = None, **kw: object) -> BrokerPositionManager:
    spec = rig.bundle.gateway.symbol_spec("EURUSD")
    base: dict[str, object] = {
        "entry_timeframe": Timeframe.M15,
        "magic_base": MAGIC,
        "strategies_by_magic": {},
        "flatten_allowed": True,
        "bus": rig.om.bus,
    }
    base.update(kw)
    return BrokerPositionManager(
        rig.om, cfg or PositionManagementConfig(), {"EURUSD": spec}, rig.clock, **base
    )  # type: ignore[arg-type]


def opened(rig: Rig) -> float:
    """Open a BUY (2 pips stop) and pin the price at its entry; returns the entry price."""
    execute(rig)
    [pos] = rig.bundle.gateway.positions()
    rig.fake.price_override["EURUSD"] = pos.price_open
    return pos.price_open


def quote(rig: Rig, bid: float) -> None:
    rig.fake.price_override["EURUSD"] = bid


def tick(rig: Rig) -> tuple[float, float]:
    t = rig.bundle.gateway.tick("EURUSD")
    assert t is not None
    return t.bid, t.ask


def sl(rig: Rig) -> float:
    return rig.bundle.gateway.positions()[0].sl


class TestStopManagement:
    def test_break_even_then_trailing_with_rate_limit(self, rig: Rig) -> None:
        entry = opened(rig)
        mgr = manager(rig)
        quote(rig, entry + 0.0021)  # past +1R
        mgr.on_quote("EURUSD", *tick(rig), ATR)
        assert sl(rig) == pytest.approx(entry + 2 * 0.00001)
        quote(rig, entry + 0.0035)  # past +1.5R, but right after the last change
        mgr.on_quote("EURUSD", *tick(rig), ATR)
        assert sl(rig) == pytest.approx(entry + 2 * 0.00001)
        rig.clock.advance(10)
        mgr.on_quote("EURUSD", *tick(rig), ATR)
        assert sl(rig) == pytest.approx(entry + 0.0035 - 2 * ATR)
        assert [e.type for e in rig.sink.events].count(EventType.STOP_MOVED) == 2

    @pytest.mark.parametrize("field", ["stops_level", "freeze_level"])
    def test_levels_that_the_server_would_refuse_are_skipped(self, rig: Rig, field: str) -> None:
        entry = opened(rig)
        rig.fake.symbols["EURUSD"] = dataclasses.replace(rig.fake.symbols["EURUSD"], **{field: 500})
        before = rig.sends()
        quote(rig, entry + 0.0021)
        manager(rig).on_quote("EURUSD", *tick(rig), ATR)
        assert rig.sends() == before  # nothing was even sent
        assert sl(rig) == pytest.approx(entry - 0.0020, abs=2e-5)

    def test_positions_without_an_intent_are_not_managed(self, rig: Rig) -> None:
        rig.fake.add_position(
            ticket=42,
            symbol="EURUSD",
            type=0,
            volume=0.1,
            price_open=1.1,
            sl=1.09,
            tp=0.0,
            price_current=1.1,
            profit=0.0,
            swap=0.0,
            magic=MAGIC,
            comment="",
            time=int(WED.timestamp()),
        )
        quote(rig, 1.1050)
        before = rig.sends()
        manager(rig).on_quote("EURUSD", *tick(rig), ATR)
        assert rig.sends() == before


class TestClosing:
    def test_time_stop(self, rig: Rig) -> None:
        entry = opened(rig)
        mgr = manager(rig, PositionManagementConfig(time_stop_bars=1))
        mgr.on_quote("EURUSD", *tick(rig), ATR)
        assert rig.bundle.gateway.positions()  # not a full bar yet
        rig.clock.advance(15 * 60)
        quote(rig, entry)
        mgr.on_quote("EURUSD", *tick(rig), ATR)
        assert rig.bundle.gateway.positions() == []
        closed = [e for e in rig.sink.events if e.type is EventType.POSITION_CLOSED]
        assert closed and closed[-1].params["reason"] == "TIME"

    def test_strategy_close_signal(self, rig: Rig) -> None:
        opened(rig)
        manager(rig, strategies_by_magic={MAGIC: Closer()}).on_bar(
            "EURUSD", StrategyContext(make_context(), {}, WED)
        )
        assert rig.bundle.gateway.positions() == []

    def test_flatten(self, rig: Rig) -> None:
        execute(rig, record(rig, key_bar=0))
        execute(rig, record(rig, key_bar=1))
        assert len(rig.bundle.gateway.positions()) == 2
        results = manager(rig).flatten("kill switch FLATTEN")
        assert all(r.ok for r in results) and rig.bundle.gateway.positions() == []

    def test_flatten_needs_permission(self, rig: Rig) -> None:
        opened(rig)
        with pytest.raises(SafetyViolation, match="FLATTEN"):
            manager(rig, flatten_allowed=False).flatten("test")
        assert rig.bundle.gateway.positions()
