"""The history download must reach the newest bar the terminal holds (audit 2026-10-19, task 1a).

On 2026-10-19 (Monday, market open) ``scripts/download_history.py`` stored XAUUSD M1 only through Friday's
close: ``copy_rates_range`` served the bot terminal's stale local M1 history (5,832 bars for 2026-10-12..19,
``logs/download.log`` 15:02:06 UTC), while M5..D1 on the same run reached Monday 15:00 UTC. A second run, after a
``copy_rates_from_pos`` call, got Monday's bars (1,370 bars for 2026-10-16..19, 15:40:24 UTC).

``LazySyncFake`` emulates that terminal: ``copy_rates_range`` serves only bars that opened before
``synced_until`` until the history is synchronised. Monday 2026-10-05 10:00:30 UTC is a market-open instant after
a weekend (FakeMT5's metals close Friday 21:00 UTC and reopen Sunday 21:00 UTC).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.broker.fake_mt5 import FakeMT5
from app.broker.gateway import ReadOnlyMT5Gateway
from app.broker.mt5_client import MT5Client
from app.config import load_settings
from app.core.clock import ManualClock, ServerClock
from app.core.enums import Timeframe
from app.core.errors import DataQualityError
from app.market_data.history_download import download_history

ENV = {
    "TRADING_MODE": "PAPER",
    "MT5_LOGIN": "12345678",
    "MT5_PASSWORD": "investor-pass",
    "MT5_SERVER": "FBS-Demo",
    "MT5_TERMINAL_PATH": "x",
}
MON = datetime(2026, 10, 5, 10, 0, 30, tzinfo=UTC)  # Monday, market open, EEST (+3)
SAT = datetime(2026, 10, 3, 0, 0, tzinfo=UTC)  # the stale local history ends here (after Friday's close)
LAST_FRIDAY_M1 = pd.Timestamp("2026-10-02 20:59", tz="UTC")


class LazySyncFake(FakeMT5):
    """FakeMT5 whose local history ends at ``synced_until`` until it is synchronised.

    - ``copy_rates_range`` serves only bars that opened before ``synced_until`` while unsynchronised.
    - ``sync_on_from_pos``: a ``copy_rates_from_pos`` call synchronises it (what the 2026-10-19 runs showed).
    - ``pos_stale``: ``copy_rates_from_pos`` serves the stale history too (then only the tick shows the gap).
    - ``stale_close_shift``: the stale copy of the last local bar has its close moved by this much (a bar that
      was still forming when the terminal stored it); after the sync the bar has its real close.
    """

    def __init__(
        self,
        clock: ManualClock,
        *,
        synced_until: datetime,
        sync_on_from_pos: bool = True,
        pos_stale: bool = False,
        stale_close_shift: float = 0.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(clock, **kwargs)
        self.synced = False
        self.synced_server = self.server_clock.utc_to_server_epoch(synced_until)
        self.sync_on_from_pos = sync_on_from_pos
        self.pos_stale = pos_stale
        self.stale_close_shift = stale_close_shift

    def _stale(self, bars: np.ndarray) -> np.ndarray:
        out = bars[bars["time"] < self.synced_server].copy()
        if len(out):
            out["close"][-1] += self.stale_close_shift
        return out

    def copy_rates_range(
        self, symbol: str, timeframe: int, date_from: Any, date_to: Any
    ) -> np.ndarray | None:
        out = super().copy_rates_range(symbol, timeframe, date_from, date_to)
        return out if out is None or self.synced else self._stale(out)

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> np.ndarray | None:
        if self.pos_stale and not self.synced:
            out = super().copy_rates_from_pos(symbol, timeframe, 0, self.terminal.maxbars)
            if out is None:
                return None
            out = self._stale(out)
            end = len(out) - start_pos
            return out[max(0, end - count) : max(0, end)]
        out = super().copy_rates_from_pos(symbol, timeframe, start_pos, count)
        if self.sync_on_from_pos:
            self.synced = True
        return out


def gateway(fake: FakeMT5, clock: ManualClock) -> ReadOnlyMT5Gateway:
    s = load_settings(env_file=None, config_file="config.yaml", environ=ENV)
    client = MT5Client(s.env, s.mode, mt5_module=fake, clock=clock)
    client.connect()
    return ReadOnlyMT5Gateway(client, ServerClock("Europe/Athens", clock))


def lazy(now: datetime = MON, **kwargs: Any) -> tuple[LazySyncFake, ReadOnlyMT5Gateway]:
    clock = ManualClock(now)
    fake = LazySyncFake(clock, synced_until=SAT, history_days=20, future_days=5, **kwargs)
    return fake, gateway(fake, clock)


def fresh(now: datetime = MON) -> ReadOnlyMT5Gateway:
    clock = ManualClock(now)
    return gateway(FakeMT5(clock, history_days=20, future_days=5), clock)


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the waits instead of sleeping."""
    calls: list[float] = []
    monkeypatch.setattr(time, "sleep", calls.append)
    return calls


class TestLazySync:
    def test_fixture_reproduces_the_symptom(self) -> None:
        """Hand check of the fake itself: the raw range call stops at Friday 20:59, Monday's bars exist."""
        _, gw = lazy()
        raw = gw.rates_range("XAUUSD", Timeframe.M1, MON - timedelta(days=3), MON)
        last = gw.server_clock.server_epoch_to_utc(int(raw["time"].iloc[-1]))
        assert pd.Timestamp(last) == LAST_FRIDAY_M1
        newest = gw.rates_from_pos("XAUUSD", Timeframe.M1, 0, 1)
        assert pd.Timestamp(gw.server_clock.server_epoch_to_utc(int(newest["time"].iloc[0]))) == pd.Timestamp(
            "2026-10-05 10:00", tz="UTC"
        )

    @pytest.mark.parametrize("tf", [Timeframe.M1, Timeframe.H1])
    def test_stale_range_is_completed_after_the_sync(self, tf: Timeframe, sleeps: list[float]) -> None:
        fake, gw = lazy()
        df = download_history(gw, "XAUUSD", tf, MON - timedelta(days=3), MON)
        want = download_history(fresh(), "XAUUSD", tf, MON - timedelta(days=3), MON)
        # Monday 10:00 UTC is the newest bar but still forming at 10:00:30: the last closed one is M1 09:59 / H1
        # 09:00 (the stale download ended Friday)
        last = {Timeframe.M1: "2026-10-05 09:59", Timeframe.H1: "2026-10-05 09:00"}[tf]
        assert df["open_time"].iloc[-1] == pd.Timestamp(last, tz="UTC")
        pd.testing.assert_frame_equal(df, want)
        assert df["open_time"].is_unique and df["open_time"].is_monotonic_increasing
        assert len(sleeps) == 1  # one wait, then the re-read of the tail succeeded
        assert fake.calls["order_send"] == 0 and fake.calls["order_check"] == 0

    def test_never_synchronised_fails_loudly(self, sleeps: list[float]) -> None:
        _, gw = lazy(sync_on_from_pos=False)
        with pytest.raises(DataQualityError, match="XAUUSD M1"):
            download_history(gw, "XAUUSD", Timeframe.M1, MON - timedelta(days=3), MON)
        assert sleeps == [1.0, 2.0, 4.0, 8.0]  # four waits (15 s in all), then the error

    def test_tick_shows_the_gap_when_newest_bars_are_stale_too(self, sleeps: list[float]) -> None:
        """Both bar calls stale: only the latest tick (Monday 10:00:30) shows that Monday's bars are missing."""
        _, gw = lazy(sync_on_from_pos=False, pos_stale=True)
        with pytest.raises(DataQualityError, match="2026-10-05 10:00"):
            download_history(gw, "XAUUSD", Timeframe.M1, MON - timedelta(days=3), MON)

    def test_newest_bars_show_the_gap_without_a_tick(self, sleeps: list[float]) -> None:
        """No tick (the call fails): the newest bars alone (Monday 10:00) show the gap."""
        fake, gw = lazy(sync_on_from_pos=False)
        fake.fail_next("symbol_info_tick", times=100)
        with pytest.raises(DataQualityError, match="2026-10-05 10:00"):
            download_history(gw, "XAUUSD", Timeframe.M1, MON - timedelta(days=3), MON)

    def test_a_bar_read_again_replaces_its_first_copy(self, sleeps: list[float]) -> None:
        """Friday 20:59 was stored with a close 1.0 off; the re-read after the sync brings the real bar."""
        _, gw = lazy(stale_close_shift=1.0)
        df = download_history(gw, "XAUUSD", Timeframe.M1, MON - timedelta(days=3), MON)
        want = download_history(fresh(), "XAUUSD", Timeframe.M1, MON - timedelta(days=3), MON)
        pd.testing.assert_frame_equal(df, want)

    def test_re_read_covers_only_the_tail(self, sleeps: list[float]) -> None:
        """15 days of M1 take two 13-day chunks; the re-read after the sync is one call from the last bar."""
        fake, gw = lazy()
        df = download_history(gw, "XAUUSD", Timeframe.M1, MON - timedelta(days=15), MON)
        assert fake.calls["copy_rates_range"] == 3
        assert df["open_time"].iloc[-1] == pd.Timestamp("2026-10-05 09:59", tz="UTC")


class TestNoFalseAlarm:
    def test_fresh_terminal_is_unchanged_and_never_waits(self, sleeps: list[float]) -> None:
        clock = ManualClock(MON)
        fake = FakeMT5(clock, history_days=20, future_days=5)
        gw = gateway(fake, clock)
        df = download_history(gw, "XAUUSD", Timeframe.M1, MON - timedelta(days=3), MON)
        assert sleeps == []
        assert fake.calls["copy_rates_range"] == 1  # 3 days fit one M1 chunk (13 days); no re-read
        assert df["open_time"].iloc[-1] == pd.Timestamp(
            "2026-10-05 09:59", tz="UTC"
        )  # 10:00 is still forming

    def test_window_on_a_minute_boundary(self, sleeps: list[float]) -> None:
        """end = 10:00:00: the 10:00 bar is outside [start, end); the newest bar inside is 09:59."""
        now = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
        df = download_history(fresh(now), "XAUUSD", Timeframe.M1, now - timedelta(days=1), now)
        assert sleeps == [] and df["open_time"].iloc[-1] == pd.Timestamp("2026-10-05 09:59", tz="UTC")

    def test_market_closed_saturday(self, sleeps: list[float]) -> None:
        now = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
        df = download_history(fresh(now), "XAUUSD", Timeframe.M1, now - timedelta(days=2), now)
        assert sleeps == [] and df["open_time"].iloc[-1] == LAST_FRIDAY_M1

    def test_past_window_is_not_checked_against_newer_bars(self, sleeps: list[float]) -> None:
        """A window that ended before the newest bar: nothing newer than its end is expected."""
        _, gw = lazy()
        end = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
        df = download_history(gw, "XAUUSD", Timeframe.M1, end - timedelta(days=1), end)
        assert sleeps == [] and df["open_time"].iloc[-1] == pd.Timestamp("2026-10-01 11:59", tz="UTC")

    def test_d1_bar_from_the_tick_uses_the_server_midnight(self, sleeps: list[float]) -> None:
        """D1 opens at server midnight (Monday 00:00 EEST = Sunday 21:00 UTC): the check sees Monday's bar, no false
        alarm; Monday's D1 is still forming, so the last returned is Friday's (Friday 00:00 EEST = Thursday 21:00 UTC)."""
        df = download_history(fresh(), "XAUUSD", Timeframe.D1, MON - timedelta(days=10), MON)
        assert sleeps == [] and df["open_time"].iloc[-1] == pd.Timestamp("2026-10-01 21:00", tz="UTC")

    def test_window_before_the_newest_bar_with_no_bars(self, sleeps: list[float]) -> None:
        """A weekend window (Saturday 12:00 .. Sunday 12:00): no bar in it, Friday's last bar is before it."""
        now = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
        df = download_history(fresh(now), "XAUUSD", Timeframe.M1, now - timedelta(days=1), now)
        assert sleeps == [] and df.empty


class TestClosedBarsOnly:
    """CLAUDE.md: closed candles only - a bar still forming at the window's end is never returned (or stored)."""

    @pytest.mark.parametrize(
        ("tf", "last"),
        [
            (Timeframe.M1, "2026-10-05 09:59"),  # 10:00 closes at 10:01, after 10:00:30
            (Timeframe.M15, "2026-10-05 09:45"),  # 10:00 closes at 10:15
            (Timeframe.H1, "2026-10-05 09:00"),
            (
                Timeframe.H4,
                "2026-10-05 05:00",
            ),  # server 08:00 .. 12:00 EEST = 05:00 .. 09:00 UTC: closed at 09:00
            (Timeframe.D1, "2026-10-01 21:00"),  # Monday's server day is forming; Friday's is the last closed
        ],
    )
    def test_the_forming_bar_is_not_returned(self, tf: Timeframe, last: str, sleeps: list[float]) -> None:
        df = download_history(fresh(), "XAUUSD", tf, MON - timedelta(days=10), MON)
        assert df["open_time"].iloc[-1] == pd.Timestamp(last, tz="UTC")
        assert (df["close_time"] <= pd.Timestamp(MON)).all()

    def test_a_bar_closing_exactly_at_the_end_is_kept(self, sleeps: list[float]) -> None:
        end = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)  # the 09:59 bar closes at 10:00:00 = the end
        df = download_history(fresh(end), "XAUUSD", Timeframe.M1, end - timedelta(days=1), end)
        assert df["open_time"].iloc[-1] == pd.Timestamp("2026-10-05 09:59", tz="UTC")
