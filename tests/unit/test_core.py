from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.clock import ClockStatus, ServerClock
from app.core.decimal_utils import decimals_of, floor_to_step, is_multiple_of, round_to_tick
from app.core.enums import Side, Timeframe, TradingMode
from app.core.ids import new_id, short_id, stable_hash, uuid7


def test_floor_to_step_never_rounds_up() -> None:
    assert floor_to_step(0.129, 0.01) == Decimal("0.12")
    assert floor_to_step("1.0", "0.01") == Decimal("1.00")
    assert floor_to_step(0.0099, 0.01) == Decimal("0.00")


@given(st.decimals(min_value=0, max_value=1000, places=6), st.sampled_from(["0.01", "0.1", "1", "0.001"]))
def test_floor_to_step_properties(value: Decimal, step: str) -> None:
    result = floor_to_step(value, step)
    assert result <= value
    assert value - result < Decimal(step)
    assert is_multiple_of(result, step)


def test_round_to_tick_modes() -> None:
    assert round_to_tick(1.234567, 0.00001) == Decimal("1.23457")
    assert round_to_tick(2345.678, 0.01, "down") == Decimal("2345.67")
    assert round_to_tick(2345.671, 0.01, "up") == Decimal("2345.68")
    assert decimals_of("0.00001") == 5
    assert decimals_of(1) == 0


def test_invalid_steps() -> None:
    with pytest.raises(ValueError):
        floor_to_step(1, 0)
    with pytest.raises(ValueError):
        floor_to_step(-1, 0.01)


def test_uuid7_is_ordered_and_versioned() -> None:
    ids = [uuid7() for _ in range(2000)]
    assert all(u.version == 7 for u in ids)
    assert ids == sorted(ids, key=lambda u: u.int)
    assert len(set(ids)) == len(ids)
    assert len(short_id(new_id())) == 8
    assert stable_hash("a", 1) == stable_hash("a", 1) != stable_hash("a", 2)


def test_enums() -> None:
    assert Timeframe.M15.seconds == 900
    assert Timeframe.H4.minutes == 240
    assert Side.BUY.opposite is Side.SELL
    assert not TradingMode.PAPER.may_send_broker_orders
    assert TradingMode.LIVE.may_send_broker_orders


class TestServerClock:
    def test_eet_offsets_follow_eu_dst(self) -> None:
        sc = ServerClock("Europe/Athens")
        assert sc.expected_offset_seconds(datetime(2026, 1, 15, 12, tzinfo=UTC)) == 7200
        assert sc.expected_offset_seconds(datetime(2026, 7, 15, 12, tzinfo=UTC)) == 10800
        # EU switch: last Sunday of March 2026 = 29 March at 01:00 UTC
        assert sc.expected_offset_seconds(datetime(2026, 3, 29, 0, 59, tzinfo=UTC)) == 7200
        assert sc.expected_offset_seconds(datetime(2026, 3, 29, 1, 0, tzinfo=UTC)) == 10800
        # back on last Sunday of October 2026 = 25 October at 01:00 UTC
        assert sc.expected_offset_seconds(datetime(2026, 10, 25, 0, 59, tzinfo=UTC)) == 10800
        assert sc.expected_offset_seconds(datetime(2026, 10, 25, 1, 0, tzinfo=UTC)) == 7200

    def test_round_trip_conversion(self) -> None:
        sc = ServerClock("Europe/Athens")
        utc = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
        server_epoch = sc.utc_to_server_epoch(utc)
        assert server_epoch - int(utc.timestamp()) == 3 * 3600
        assert sc.server_epoch_to_utc(server_epoch) == utc

    def test_verify(self, clock) -> None:  # type: ignore[no-untyped-def]
        sc = ServerClock("Europe/Athens", clock)
        now = clock.now_utc()  # October 1 -> EEST (+3h)
        good = sc.verify(now.timestamp() + 3 * 3600 - 2, advancing=True)
        assert good.status is ClockStatus.VERIFIED
        wrong = sc.verify(now.timestamp() + 2 * 3600, advancing=True)
        assert wrong.status is ClockStatus.OFFSET_MISMATCH
        drift = sc.verify(now.timestamp() + 3 * 3600 + 400, advancing=True)
        assert drift.status is ClockStatus.LOCAL_CLOCK_DRIFT
        idle = sc.verify(now.timestamp(), advancing=False)
        assert idle.status is ClockStatus.UNVERIFIED_MARKET_IDLE and not idle.ok

    def test_unknown_timezone(self) -> None:
        from app.core.errors import ConfigError

        with pytest.raises(ConfigError):
            ServerClock("Mars/Olympus")
