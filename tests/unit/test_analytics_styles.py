"""Style tags: setup, direction, holding, session, regime, volatility, weekday/hour, symbol (TAA-1002)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.analytics.styles import (
    Holding,
    Setup,
    holding_style,
    setup_of,
    style_tags,
    volatility_bucket,
)
from app.analytics.trade_builder import EntryContext, trades_from_shadow
from app.core.enums import Regime, Session, Side, VolatilityState
from tests.analytics_data import T0, shadow_row, trade


class TestSetup:
    @pytest.mark.parametrize(
        ("codes", "strategy", "expected"),
        [
            (["FIB_PULLBACK"], "", Setup.PULLBACK),
            (["TREND_PULLBACK"], "", Setup.PULLBACK),
            (["RANGE_BREAKOUT"], "", Setup.BREAKOUT),
            (["NECKLINE_BREAK"], "", Setup.BREAKOUT),
            ([], "setup_fib_pullback", Setup.PULLBACK),  # shadow rows: no reason codes, the strategy name
            ([], "setup_breakout", Setup.BREAKOUT),
            (["HARMONIC_PRZ"], "setup_harmonic_prz", Setup.OTHER),
            ([], "", Setup.OTHER),
        ],
    )
    def test_from_reason_codes_then_strategy(self, codes: list[str], strategy: str, expected: Setup) -> None:
        assert setup_of(codes, strategy) is expected

    def test_reason_codes_win_over_the_strategy_name(self) -> None:
        assert setup_of(["RANGE_BREAKOUT"], "setup_fib_pullback") is Setup.BREAKOUT

    def test_substrings_do_not_match(self) -> None:
        assert setup_of(["BREAKEVEN_MOVED"], "") is Setup.OTHER


class TestHolding:
    @pytest.mark.parametrize(
        ("held", "expected"),
        [
            (timedelta(minutes=59), Holding.SCALP),
            (timedelta(hours=1), Holding.INTRADAY),
            (timedelta(hours=23, minutes=59), Holding.INTRADAY),
            (timedelta(hours=24), Holding.SWING),
        ],
    )
    def test_boundaries(self, held: timedelta, expected: Holding) -> None:
        assert holding_style(held) is expected


class TestVolatility:
    def test_state_wins(self) -> None:
        assert volatility_bucket(VolatilityState.HIGH, 10.0) == "HIGH"

    @pytest.mark.parametrize(
        ("pct", "expected"),
        [(24.9, "LOW"), (25.0, "NORMAL"), (74.9, "NORMAL"), (75.0, "HIGH"), (90.0, "EXTREME")],
    )
    def test_percentile_buckets(self, pct: float, expected: str) -> None:
        assert volatility_bucket(None, pct) == expected

    def test_unknown(self) -> None:
        assert volatility_bucket(None, None) == "UNKNOWN"


class TestStyleTags:
    def test_full_tag_set(self) -> None:
        ctx = EntryContext(
            session=Session.LONDON_NY_OVERLAP,
            regime=Regime.TRENDING,
            volatility=VolatilityState.NORMAL,
            reason_codes=("FIB_PULLBACK",),
        )
        tags = style_tags(trade(context=ctx))
        assert tags.as_dict() == {
            "setup": "PULLBACK",
            "direction": "LONG",
            "holding": "INTRADAY",
            "session": "LONDON_NY_OVERLAP",
            "regime": "TRENDING",
            "volatility": "NORMAL",
            "weekday": "WED",
            "hour": 10,
            "symbol": "EURUSD",
            "strategy": "setup_fib_pullback",
            "scope": "BACKTEST",
            "variant": None,
            "source": None,
        }

    def test_unknown_context_is_tagged_unknown_and_session_from_the_entry_time(self) -> None:
        tags = style_tags(trade(side=Side.SELL, strategy="", context=EntryContext()))
        assert tags.direction == "SHORT"
        assert tags.regime == "UNKNOWN" and tags.volatility == "UNKNOWN" and tags.strategy == "UNKNOWN"
        assert tags.session == "LONDON"  # Wednesday 10:00 UTC = 11:00 London, 06:00 New York

    @pytest.mark.parametrize(
        ("at", "expected"),
        [
            (datetime(2026, 9, 30, 1, 0, tzinfo=UTC), "ASIA"),
            (datetime(2026, 9, 30, 13, 0, tzinfo=UTC), "LONDON_NY_OVERLAP"),
            (datetime(2026, 9, 30, 18, 0, tzinfo=UTC), "NEW_YORK"),
            (datetime(2026, 9, 30, 22, 30, tzinfo=UTC), "OFF"),
        ],
    )
    def test_session_fallback(self, at: datetime, expected: str) -> None:
        t = trade(entry_time=at, exit_time=at + timedelta(minutes=30), context=EntryContext())
        assert style_tags(t).session == expected

    def test_weekday_and_hour_in_utc(self) -> None:
        bangkok = datetime(2026, 10, 1, 2, 0, tzinfo=ZoneInfo("Asia/Bangkok"))  # Wed 19:00 UTC
        t = trade(entry_time=bangkok, exit_time=bangkok + timedelta(hours=30))
        tags = style_tags(t)
        assert (tags.weekday, tags.hour, tags.holding) == ("WED", 19, "SWING")

    def test_shadow_trade_keeps_variant_and_source(self) -> None:
        (t,) = trades_from_shadow([shadow_row(variant="MANAGED", source="REPLAY")]).trades
        tags = style_tags(t)
        assert (tags.scope, tags.variant, tags.source) == ("SHADOW", "MANAGED", "REPLAY")
        assert (tags.setup, tags.session, tags.regime) == ("BREAKOUT", "LONDON", "TRENDING")

    def test_deterministic(self) -> None:
        t = trade(entry_time=T0)
        assert style_tags(t) == style_tags(t)
