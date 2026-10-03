from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.broker.fake_mt5 import FakeMT5
from app.broker.gateway import ReadOnlyMT5Gateway
from app.broker.mt5_client import MT5Client
from app.config import TimeframesConfig, load_settings
from app.core.clock import ClockStatus, ManualClock, ServerClock
from app.core.enums import Timeframe
from app.market_data.candle_service import CandleService, CandleWatermarks
from app.market_data.history_download import download_history
from app.market_data.history_store import ParquetHistoryStore, SqlHistoryStore
from app.market_data.quality import parse_breaks, validate_candles
from app.market_data.quote_service import QuoteService
from app.market_data.server_time import verify_server_time
from app.storage.database import Database

ENV = {
    "TRADING_MODE": "PAPER",
    "MT5_LOGIN": "12345678",
    "MT5_PASSWORD": "investor-pass",
    "MT5_SERVER": "FBS-Demo",
    "MT5_TERMINAL_PATH": "x",
}


def setup(start: datetime):  # type: ignore[no-untyped-def]
    clock = ManualClock(start)
    fake = FakeMT5(clock, history_days=40, future_days=10)
    s = load_settings(env_file=None, config_file="config.yaml", environ=ENV)
    client = MT5Client(s.env, s.mode, mt5_module=fake, clock=clock)
    client.connect()
    return clock, fake, ReadOnlyMT5Gateway(client, ServerClock("Europe/Athens", clock))


class TestCandleService:
    def test_only_closed_bars_with_utc_times(self) -> None:
        clock, _, gw = setup(datetime(2026, 9, 30, 10, 7, 30, tzinfo=UTC))  # mid-way through 10:00 M15 bar
        svc = CandleService(gw, TimeframesConfig(), clock)
        frame = svc.closed_candles("EURUSD", Timeframe.M15, 50)
        assert len(frame) == 50
        assert frame.last_open_time == datetime(2026, 9, 30, 9, 45, tzinfo=UTC)
        assert frame.last_close_time == datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
        assert frame.quality.ok, frame.quality.flags
        # server time is UTC+3 in September (EEST)
        assert (
            int(frame.df["time_server"].iloc[-1]) - int(frame.df["open_time"].iloc[-1].timestamp())
            == 3 * 3600
        )

    def test_grace_period_delays_fresh_bar(self) -> None:
        clock, _, gw = setup(datetime(2026, 9, 30, 10, 0, 1, tzinfo=UTC))  # 1s after boundary, grace 3s
        svc = CandleService(gw, TimeframesConfig(), clock)
        assert svc.closed_candles("EURUSD", Timeframe.M15, 5).last_open_time == datetime(
            2026, 9, 30, 9, 30, tzinfo=UTC
        )
        clock.advance(5)
        assert svc.closed_candles("EURUSD", Timeframe.M15, 5).last_open_time == datetime(
            2026, 9, 30, 9, 45, tzinfo=UTC
        )

    def test_h1_aligned_to_hour_and_consistent_with_m15(self) -> None:
        clock, _, gw = setup(datetime(2026, 9, 30, 10, 7, 0, tzinfo=UTC))
        svc = CandleService(gw, TimeframesConfig(), clock)
        h1 = svc.closed_candles("EURUSD", Timeframe.H1, 3).df
        m15 = svc.closed_candles("EURUSD", Timeframe.M15, 8).df
        last_h1 = h1.iloc[-1]
        inside = m15[(m15.open_time >= last_h1.open_time) & (m15.open_time < last_h1.close_time)]
        assert len(inside) == 4
        assert last_h1.high == pytest.approx(inside.high.max())
        assert last_h1.low == pytest.approx(inside.low.min())

    def test_weekend_gap_is_expected(self) -> None:
        clock, _, gw = setup(datetime(2026, 9, 28, 3, 0, 10, tzinfo=UTC))  # Monday morning
        svc = CandleService(gw, TimeframesConfig(), clock)
        frame = svc.closed_candles("EURUSD", Timeframe.H1, 40)
        assert frame.quality.ok, frame.quality.flags
        assert frame.quality.missing_bars == 0

    def test_stale_on_weekend_only_when_live_expected(self) -> None:
        clock, _, gw = setup(datetime(2026, 10, 3, 12, 0, tzinfo=UTC))  # Saturday
        svc = CandleService(gw, TimeframesConfig(), clock)
        frame = svc.closed_candles("EURUSD", Timeframe.M15, 10, expect_live=False)
        assert frame.quality.stale and frame.quality.ok
        frame_live = svc.closed_candles("EURUSD", Timeframe.M15, 10, expect_live=True)
        assert "DATA_STALE" in frame_live.quality.flags

    def test_watermarks_persist(self, db: Database) -> None:
        clock = ManualClock(datetime(2026, 9, 30, tzinfo=UTC))
        wm = CandleWatermarks(db, clock)
        t = datetime(2026, 9, 30, 9, 45, tzinfo=UTC)
        assert wm.is_new("EURUSD", Timeframe.M15, t)
        wm.mark("EURUSD", Timeframe.M15, t)
        assert not wm.is_new("EURUSD", Timeframe.M15, t)
        assert CandleWatermarks(db, clock).get("EURUSD", Timeframe.M15) == t  # fresh instance reads DB
        wm.mark("EURUSD", Timeframe.M15, t - timedelta(minutes=15))  # never moves backwards
        assert CandleWatermarks(db, clock).get("EURUSD", Timeframe.M15) == t


class TestQuality:
    def _frame(self, opens: list[datetime], **mods) -> pd.DataFrame:  # type: ignore[no-untyped-def]
        n = len(opens)
        df = pd.DataFrame(
            {
                "open_time": pd.DatetimeIndex(opens),
                "close_time": pd.DatetimeIndex(opens) + pd.Timedelta(minutes=15),
                "time_server": [0] * n,
                "open": [1.0] * n,
                "high": [1.1] * n,
                "low": [0.9] * n,
                "close": [1.05] * n,
                "tick_volume": [1] * n,
                "spread": [1] * n,
                "real_volume": [0] * n,
            }
        )
        for col, (idx, val) in mods.items():
            df.loc[idx, col] = val
        return df

    def test_unexpected_gap_flagged(self) -> None:
        base = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
        opens = [base + timedelta(minutes=15 * i) for i in range(4)] + [base + timedelta(minutes=15 * 9)]
        rep = validate_candles(
            self._frame(opens),
            Timeframe.M15,
            opens[-1] + timedelta(minutes=16),
            max_gap_bars=3,
            expect_live=True,
        )
        assert rep.missing_bars == 5 and "DATA_GAPS" in rep.flags

    def test_daily_break_gap_expected(self) -> None:
        base = datetime(2026, 9, 30, 20, 30, tzinfo=UTC)
        opens = [base, base + timedelta(minutes=15), datetime(2026, 9, 30, 22, 0, tzinfo=UTC)]
        rep = validate_candles(
            self._frame(opens),
            Timeframe.M15,
            opens[-1] + timedelta(minutes=16),
            max_gap_bars=0,
            expect_live=True,
            breaks=parse_breaks(["21:00-22:05"]),
        )
        assert rep.ok, rep.flags

    def test_invalid_ohlc(self) -> None:
        base = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
        opens = [base + timedelta(minutes=15 * i) for i in range(3)]
        rep = validate_candles(
            self._frame(opens, high=(1, 0.8)),
            Timeframe.M15,
            opens[-1] + timedelta(minutes=16),
            max_gap_bars=3,
            expect_live=True,
        )
        assert rep.invalid_rows == 1 and "INVALID_OHLC" in rep.flags

    def test_duplicates(self) -> None:
        base = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
        rep = validate_candles(
            self._frame([base, base]), Timeframe.M15, base, max_gap_bars=3, expect_live=False
        )
        assert "DUPLICATE_BARS" in rep.flags


class TestQuotesAndTime:
    def test_quote_and_median_spread(self) -> None:
        clock, _, gw = setup(datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC))
        qs = QuoteService(gw, clock)
        spec = gw.symbol_spec("EURUSD")
        for _ in range(12):
            q = qs.quote(spec)
            clock.advance(60)
        assert q.valid and q.spread_points > 0 and q.age_seconds < 2
        assert qs.median_spread("EURUSD") is not None

    def test_stale_quote_on_weekend(self) -> None:
        clock, _, gw = setup(datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
        q = QuoteService(gw, clock).quote(gw.symbol_spec("EURUSD"))
        assert not q.valid and "stale" in q.problem

    def test_price_jump(self) -> None:
        clock, _, gw = setup(datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC))
        qs = QuoteService(gw, clock)
        q = qs.quote(gw.symbol_spec("EURUSD"))
        assert not qs.is_price_jump(q, atr=0.001, max_atr_multiple=5)
        jumped = type(q)(q.symbol, q.bid + 0.02, q.ask + 0.02, q.spread_points, q.time_utc, 0, True)
        assert qs.is_price_jump(jumped, atr=0.001, max_atr_multiple=5)

    def test_server_time_verified_on_weekday(self) -> None:
        clock, _, gw = setup(datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC))
        result = verify_server_time(gw, "EURUSD", wait_seconds=5, poll_seconds=1, sleep=clock.advance)
        assert result.status is ClockStatus.VERIFIED

    def test_server_time_idle_on_weekend(self) -> None:
        clock, _, gw = setup(datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
        result = verify_server_time(gw, "EURUSD", wait_seconds=3, poll_seconds=1, sleep=clock.advance)
        assert result.status is ClockStatus.UNVERIFIED_MARKET_IDLE

    def test_server_time_mismatch_detected(self) -> None:
        clock = ManualClock(datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC))
        fake = FakeMT5(clock, history_days=5, future_days=2, tz="Europe/London")  # broker actually on UK time
        s = load_settings(env_file=None, config_file="config.yaml", environ=ENV)
        client = MT5Client(s.env, s.mode, mt5_module=fake, clock=clock)
        client.connect()
        gw = ReadOnlyMT5Gateway(client, ServerClock("Europe/Athens", clock))
        result = verify_server_time(gw, "EURUSD", wait_seconds=3, poll_seconds=1, sleep=clock.advance)
        assert result.status is ClockStatus.OFFSET_MISMATCH


class TestHistory:
    def test_download_and_parquet_round_trip(self, tmp_path: Path) -> None:
        _, _, gw = setup(datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC))
        start, end = datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 30, tzinfo=UTC)
        df = download_history(gw, "EURUSD", Timeframe.H1, start, end)
        assert len(df) > 400 and df["open_time"].is_monotonic_increasing
        store = ParquetHistoryStore(tmp_path)
        n = store.save("FBS-Demo", "EURUSD", Timeframe.H1, df, gw.symbol_spec("EURUSD"))
        assert n == len(df)
        assert store.save("FBS-Demo", "EURUSD", Timeframe.H1, df.tail(10)) == len(df)  # idempotent merge
        loaded = store.load("FBS-Demo", "EURUSD", Timeframe.H1, start=datetime(2026, 9, 10, tzinfo=UTC))
        assert loaded["open_time"].min() >= pd.Timestamp("2026-09-10", tz="UTC")
        assert store.spec("FBS-Demo", "EURUSD")["spec"]["digits"] == 5
        assert ("FBS-Demo", "EURUSD", Timeframe.H1) in store.available()

    def test_sql_store_round_trip(self, db: Database) -> None:
        _, _, gw = setup(datetime(2026, 9, 30, 10, 0, 30, tzinfo=UTC))
        df = download_history(
            gw, "XAUUSD", Timeframe.H4, datetime(2026, 9, 20, tzinfo=UTC), datetime(2026, 9, 30, tzinfo=UTC)
        )
        store = SqlHistoryStore(db)
        store.save("FBS-Demo", "XAUUSD", Timeframe.H4, df)
        store.save("FBS-Demo", "XAUUSD", Timeframe.H4, df.tail(3))  # upsert, no duplicates
        loaded = store.load("FBS-Demo", "XAUUSD", Timeframe.H4)
        assert len(loaded) == len(df)
        assert loaded["close"].tolist() == pytest.approx(df["close"].tolist())


def test_doctor_with_fake_broker() -> None:
    from app.cli.doctor import run_doctor

    s = load_settings(env_file=None, config_file="config.yaml", environ=ENV)
    report = run_doctor(s, fake=True, wait_seconds=0)
    assert report.failures == 0, report.lines
