"""DEMO forward tracking against the backtests (app/engine/forward_track.py, owner 2026-10-14)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.engine.forward_track import BASELINES, by_day, by_setup, load_trades, report
from app.storage.database import Database
from tests.unit.test_analytics_trades import broker_row as broker_trade

V1_DAY = datetime(2026, 10, 14, 11, 0, tzinfo=UTC)


@pytest.fixture
def db() -> Database:
    d = Database("sqlite://")
    d.create_all()
    rows = [
        # harmonic before V1 went on the bot (2026-10-12): other parameters
        broker_trade(position_ticket=1, strategy="setup_harmonic_prz", entry_time=datetime(2026, 10, 9, tzinfo=UTC),
                     exit_time=datetime(2026, 10, 9, 3, tzinfo=UTC), net=-12.0, r_multiple=-1.0),
        broker_trade(position_ticket=2, strategy="setup_harmonic_prz", entry_time=V1_DAY,
                     exit_time=V1_DAY + timedelta(hours=1), net=121.7, r_multiple=1.79),
        broker_trade(position_ticket=3, strategy="setup_harmonic_prz", entry_time=V1_DAY + timedelta(hours=3),
                     exit_time=V1_DAY + timedelta(hours=20), net=-60.0, r_multiple=-1.0),
        broker_trade(position_ticket=4, strategy="setup_candle_reversal", entry_time=datetime(2026, 10, 7, tzinfo=UTC),
                     exit_time=datetime(2026, 10, 7, 2, tzinfo=UTC), net=-7.0, r_multiple=-1.0),
    ]  # fmt: skip
    with d.session() as sess:
        sess.add_all(rows)
    return d


def test_trades_before_a_baseline_are_listed_apart(db: Database) -> None:
    lines = {s.strategy: s for s in by_setup(load_trades(db))}
    v1 = lines["setup_harmonic_prz"]
    assert (v1.trades, v1.wins, v1.mean_r) == (2, 1, pytest.approx(0.395))
    assert v1.baseline is BASELINES["setup_harmonic_prz"]
    assert lines["setup_harmonic_prz (before harmonic V1)"].baseline is None
    assert lines["setup_candle_reversal"].verdict == "no baseline"


def test_the_expected_range_narrows_with_more_trades(db: Database) -> None:
    v1 = next(s for s in by_setup(load_trades(db)) if s.strategy == "setup_harmonic_prz")
    band = v1.band
    assert band is not None
    b = BASELINES["setup_harmonic_prz"]
    assert band == pytest.approx((b.mean_r - 1.645 * b.sd_r / 2**0.5, b.mean_r + 1.645 * b.sd_r / 2**0.5))
    assert v1.verdict == "inside the backtest range"


def test_days_are_thai_dates_with_a_running_total(db: Database) -> None:
    days = by_day(load_trades(db))
    # 2026-10-15 07:00 UTC is 14:00 on the 15th in Thai time; 2026-10-14 12:00 UTC is the 14th
    assert [d.isoformat() for d, *_ in days] == ["2026-10-07", "2026-10-09", "2026-10-14", "2026-10-15"]
    assert days[-1][-1] == pytest.approx(-1.0 - 1.0 + 1.79 - 1.0)


def test_the_report_with_proven_setups_only(db: Database) -> None:
    text = report(db, proven_only=True)
    assert "Closed bot trades (Thai time): 2, proven setups only." in text
    assert "setup_candle_reversal" not in text and "before harmonic V1" not in text
    assert "inside the backtest range" in text
