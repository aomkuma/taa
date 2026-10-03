from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from app.advisory.asset_classes import AssetClass
from app.advisory.market_sessions import (
    LiquidityProfile,
    describe_hour,
    hour_of_week,
    session_state,
    sessions_for,
)
from app.config import AdvisorySessionsConfig

FX = sessions_for("EURUSD", AssetClass.FOREX_MAJOR, "USD")


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


class TestMapping:
    @pytest.mark.parametrize(
        ("symbol", "cls", "quote", "expected"),
        [
            ("EURUSD", AssetClass.FOREX_MAJOR, "USD", ("SYDNEY", "TOKYO", "LONDON", "NEW_YORK")),
            ("XAUUSD", AssetClass.METAL, "USD", ("TOKYO", "LONDON", "NEW_YORK")),
            ("USOIL", AssetClass.ENERGY, "USD", ("LONDON", "NEW_YORK")),
            ("US30", AssetClass.INDEX, "USD", ("US_EQUITIES",)),
            ("DE40", AssetClass.INDEX, "EUR", ("EUROPE_EQUITIES",)),
            ("JP225", AssetClass.INDEX, "JPY", ("TOKYO",)),
            ("AAPL", AssetClass.STOCK, "USD", ("US_EQUITIES",)),
            ("BTCUSD", AssetClass.CRYPTO, "USD", ("CRYPTO",)),
        ],
    )
    def test_asset_class_mapping(
        self, symbol: str, cls: AssetClass, quote: str, expected: tuple[str, ...]
    ) -> None:
        assert sessions_for(symbol, cls, quote) == expected

    def test_overrides(self) -> None:
        assert sessions_for("XAUUSD", AssetClass.METAL, "USD", {"XAUUSD": ["LONDON"]}) == ("LONDON",)
        with pytest.raises(ValueError):
            AdvisorySessionsConfig(overrides={"XAUUSD": ["MOON"]})


class TestDaylightSaving:
    @pytest.mark.parametrize(
        ("at", "open_names"),
        [
            # winter, both on standard time: London 08-17 UTC, New York 13-22 UTC
            (utc(2026, 2, 11, 12, 30), {"LONDON"}),
            # US already on DST (8 Mar), Europe not yet (29 Mar): New York opens at 12:00 UTC
            (utc(2026, 3, 11, 12, 30), {"LONDON", "NEW_YORK"}),
            (utc(2026, 3, 11, 7, 30), set()),  # London still opens at 08:00 UTC
            # both on summer time: London opens at 07:00 UTC
            (utc(2026, 4, 15, 7, 30), {"LONDON"}),
            # Europe back on standard time (25 Oct), US not yet (1 Nov)
            (utc(2026, 10, 28, 12, 30), {"LONDON", "NEW_YORK"}),
            (utc(2026, 10, 28, 7, 30), set()),
            (utc(2026, 11, 4, 12, 30), {"LONDON"}),  # both standard again: New York from 13:00 UTC
        ],
    )
    def test_london_new_york_in_mismatched_weeks(self, at: datetime, open_names: set[str]) -> None:
        state = session_state(("LONDON", "NEW_YORK"), at)
        assert set(state.active) == open_names
        assert state.open is bool(open_names)

    def test_sydney_follows_australian_dst(self) -> None:
        # Australia starts DST on 4 Oct 2026: Monday 07:00 Sydney = Sunday 20:00 UTC
        assert session_state(("SYDNEY",), utc(2026, 10, 11, 20, 30)).open
        assert not session_state(("SYDNEY",), utc(2026, 10, 11, 19, 30)).open
        # before the switch (AEST, +10): Monday 07:00 Sydney = Sunday 21:00 UTC
        assert not session_state(("SYDNEY",), utc(2026, 9, 27, 20, 30)).open


class TestState:
    def test_ends_at_is_the_last_active_close(self) -> None:
        state = session_state(FX, utc(2026, 9, 30, 13, 0))  # London and New York both open
        assert set(state.active) == {"LONDON", "NEW_YORK"}
        assert state.ends_at == utc(2026, 9, 30, 21, 0)  # 17:00 New York (EDT)

    def test_weekend_reports_the_next_open(self) -> None:
        state = session_state(FX, utc(2026, 10, 3, 12, 0))  # Saturday
        assert not state.open and state.active == ()
        assert state.next_open == utc(2026, 10, 4, 20, 0)  # Monday 07:00 Sydney (AEDT)

    def test_crypto_is_always_open(self) -> None:
        state = session_state(("CRYPTO",), utc(2026, 10, 3, 3, 0))
        assert state.open and state.next_open is None and state.ends_at is None

    def test_us_equities_cash_session(self) -> None:
        assert session_state(("US_EQUITIES",), utc(2026, 9, 30, 13, 30)).open  # 09:30 EDT
        assert not session_state(("US_EQUITIES",), utc(2026, 9, 30, 13, 29)).open
        assert not session_state(("US_EQUITIES",), utc(2026, 9, 30, 20, 0)).open  # 16:00 EDT


def h1_history(weeks: int = 4) -> pd.DataFrame:
    times = pd.date_range("2026-08-31 00:00", periods=weeks * 168, freq="h", tz="UTC")
    volume = np.where((times.hour >= 12) & (times.hour < 16), 900.0, 100.0)
    volume[times.dayofweek >= 5] = 0.0  # weekend: no trading
    return pd.DataFrame({"open_time": times, "tick_volume": volume})


class TestLiquidity:
    def test_profile(self) -> None:
        profile = LiquidityProfile.from_h1(h1_history())
        assert profile.weeks == 4
        assert profile.typical == 100.0
        assert profile.ratio_now(utc(2026, 9, 30, 13, 15)) == pytest.approx(9.0)
        assert profile.ratio_now(utc(2026, 9, 30, 3, 0)) == pytest.approx(1.0)
        assert profile.ratio_now(utc(2026, 10, 3, 13, 0)) is None  # Saturday: no data
        best = profile.best_hours(2)
        assert [describe_hour(h) for h in best] == ["Mon 12:00 UTC", "Mon 13:00 UTC"]

    def test_empty_history(self) -> None:
        profile = LiquidityProfile.from_h1(pd.DataFrame(columns=["open_time", "tick_volume"]))
        assert profile.typical is None and profile.ratio_now(utc(2026, 9, 30, 13, 0)) is None
        assert profile.best_hours() == []

    def test_hour_of_week(self) -> None:
        assert hour_of_week(utc(2026, 9, 28, 0, 30)) == 0  # Monday 00:30
        assert hour_of_week(utc(2026, 10, 4, 23, 0)) == 167  # Sunday 23:00
