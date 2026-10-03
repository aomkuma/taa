from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import AppConfig, BlackoutWindow, SessionWindow
from app.market_data.trading_sessions import SessionState, TradingSessions, window_end
from app.news.calendar import ManualBlackouts, NewsFilter


def sessions(**cfg: object) -> TradingSessions:
    config = AppConfig.model_validate(cfg)
    return TradingSessions(config.sessions, config.symbols)


NY_CASH = {"days": [0, 1, 2, 3, 4], "start": "09:30", "end": "16:00", "timezone": "America/New_York"}


class TestWindows:
    def test_default_window_is_utc(self) -> None:
        s = sessions()
        v = s.check("EURUSD", datetime(2026, 9, 30, 10, 0, tzinfo=UTC))
        assert v.is_open
        assert v.closes_at == datetime(2026, 9, 30, 20, 0, tzinfo=UTC)
        assert (
            s.check("EURUSD", datetime(2026, 9, 30, 20, 0, tzinfo=UTC)).state is SessionState.SESSION_CLOSED
        )
        assert (
            s.check("EURUSD", datetime(2026, 9, 30, 6, 59, tzinfo=UTC)).state is SessionState.SESSION_CLOSED
        )

    def test_exchange_local_window_follows_dst(self) -> None:
        s = sessions(sessions={"by_symbol": {"US30": [NY_CASH]}})
        # summer (EDT, UTC-4): 09:30 New York = 13:30 UTC
        assert not s.check("US30", datetime(2026, 9, 30, 13, 29, tzinfo=UTC)).is_open
        summer = s.check("US30", datetime(2026, 9, 30, 13, 30, tzinfo=UTC))
        assert summer.is_open and summer.closes_at == datetime(2026, 9, 30, 20, 0, tzinfo=UTC)
        # winter (EST, UTC-5): 09:30 New York = 14:30 UTC
        assert not s.check("US30", datetime(2026, 11, 4, 14, 29, tzinfo=UTC)).is_open
        assert s.check("US30", datetime(2026, 11, 4, 14, 30, tzinfo=UTC)).is_open
        # other symbols keep the default window
        assert s.check("EURUSD", datetime(2026, 9, 30, 10, 0, tzinfo=UTC)).is_open

    def test_window_spanning_midnight(self) -> None:
        w = SessionWindow(days=[0], start="22:00", end="06:00")  # Monday night
        assert window_end(w, datetime(2026, 9, 28, 23, 0, tzinfo=UTC)) == datetime(
            2026, 9, 29, 6, 0, tzinfo=UTC
        )
        assert window_end(w, datetime(2026, 9, 29, 5, 59, tzinfo=UTC)) == datetime(
            2026, 9, 29, 6, 0, tzinfo=UTC
        )
        assert window_end(w, datetime(2026, 9, 29, 23, 0, tzinfo=UTC)) is None  # Tuesday night is not listed
        assert window_end(w, datetime(2026, 9, 28, 5, 0, tzinfo=UTC)) is None  # Monday morning: Sunday's part

    @pytest.mark.parametrize(
        "window",
        [
            {"start": "25:00"},
            {"start": "08:00", "end": "08:00"},
            {"timezone": "Mars/Olympus"},
            {"days": [7]},
        ],
    )
    def test_invalid_windows(self, window: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            SessionWindow.model_validate(window)


class TestBreaksAndCutoff:
    def test_daily_break_closes_the_market(self) -> None:
        s = sessions(
            symbols={"overrides": {"XAUUSD": {"daily_breaks_utc": ["21:00-22:05"]}}},
            sessions={"default": [{"start": "00:00", "end": "23:59", "days": [0, 1, 2, 3, 4]}]},
        )
        v = s.check("XAUUSD", datetime(2026, 9, 30, 21, 30, tzinfo=UTC))
        assert v.state is SessionState.MARKET_CLOSED
        before = s.check("XAUUSD", datetime(2026, 9, 30, 20, 0, tzinfo=UTC))
        assert before.is_open and before.closes_at == datetime(2026, 9, 30, 21, 0, tzinfo=UTC)
        assert s.check("XAUUSD", datetime(2026, 9, 30, 22, 5, tzinfo=UTC)).is_open

    def test_friday_cutoff(self) -> None:
        s = sessions(sessions={"default": [{"start": "00:00", "end": "23:59"}], "friday_cutoff_utc": "18:00"})
        thursday = s.check("EURUSD", datetime(2026, 10, 1, 12, 0, tzinfo=UTC))
        assert thursday.is_open and thursday.closes_at == datetime(2026, 10, 1, 23, 59, tzinfo=UTC)
        friday = s.check("EURUSD", datetime(2026, 10, 2, 12, 0, tzinfo=UTC))
        assert friday.closes_at == datetime(2026, 10, 2, 18, 0, tzinfo=UTC)
        late = s.check("EURUSD", datetime(2026, 10, 2, 18, 0, tzinfo=UTC))
        assert late.state is SessionState.SESSION_CLOSED and "Friday" in late.detail

    def test_weekend_symbols_ignore_the_cutoff(self) -> None:
        s = sessions(
            sessions={
                "by_symbol": {"BTCUSD": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "23:59"}]}
            }
        )
        assert s.check("BTCUSD", datetime(2026, 10, 3, 12, 0, tzinfo=UTC)).is_open  # Saturday
        assert not s.check("EURUSD", datetime(2026, 10, 3, 12, 0, tzinfo=UTC)).is_open


class TestNews:
    def filter(self) -> NewsFilter:
        windows = [
            BlackoutWindow(
                start_utc=datetime(2026, 10, 2, 12, 15, tzinfo=UTC),
                end_utc=datetime(2026, 10, 2, 13, 0, tzinfo=UTC),
                currencies=["usd"],
                reason="NFP",
            ),
            BlackoutWindow(
                start_utc=datetime(2026, 10, 5, 8, 0, tzinfo=UTC),
                end_utc=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
                symbols=["XAUUSD"],
            ),
            BlackoutWindow(
                start_utc=datetime(2026, 10, 7, 0, 0, tzinfo=UTC),
                end_utc=datetime(2026, 10, 7, 1, 0, tzinfo=UTC),
                reason="everything",
            ),
        ]
        return NewsFilter(ManualBlackouts(windows))

    def test_currency_symbol_and_global_blackouts(self) -> None:
        f = self.filter()
        nfp = datetime(2026, 10, 2, 12, 30, tzinfo=UTC)
        hit = f.active("EURUSD", ["EUR", "USD"], nfp)
        assert hit is not None and hit.reason == "NFP"
        assert f.active("EURGBP", ["EUR", "GBP"], nfp) is None
        assert f.active("XAUUSD", ["XAU", "USD"], datetime(2026, 10, 5, 8, 30, tzinfo=UTC)) is not None
        assert f.active("EURGBP", ["EUR", "GBP"], datetime(2026, 10, 5, 8, 30, tzinfo=UTC)) is None
        assert f.active("EURGBP", ["EUR", "GBP"], datetime(2026, 10, 7, 0, 30, tzinfo=UTC)) is not None

    def test_end_is_exclusive(self) -> None:
        assert self.filter().active("EURUSD", ["USD"], datetime(2026, 10, 2, 13, 0, tzinfo=UTC)) is None

    def test_next_start_bounds_an_opportunity_window(self) -> None:
        f = self.filter()
        after = datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
        assert f.next_start("EURUSD", ["EUR", "USD"], after) == datetime(2026, 10, 2, 12, 15, tzinfo=UTC)
        assert f.next_start("EURGBP", ["EUR", "GBP"], after) == datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
