"""Feed probe on FakeMT5: depth of market, tick history depth, tick character (TAA-L001)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.broker import mt5_constants as c
from app.broker.factory import build_read_only
from app.broker.fake_mt5 import FakeMT5
from app.broker.gateway import ReadOnlyMT5Gateway
from app.core.clock import ManualClock
from app.market_data.feed_probe import format_report, oldest_tick_week, probe, probe_book
from tests.integration.test_engine_paper import settings

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)  # Wednesday, market open


@pytest.fixture
def setup(tmp_path: Path) -> tuple[FakeMT5, ReadOnlyMT5Gateway]:
    clock = ManualClock(NOW)
    s = settings(tmp_path)
    bundle = build_read_only(s, fake=True, clock=clock)
    bundle.client.connect()
    fake = bundle.client.mt5
    assert isinstance(fake, FakeMT5)
    return fake, bundle.gateway


def no_sleep(_: float) -> None:
    return None


def test_an_empty_book_is_reported_as_empty(setup: tuple[FakeMT5, ReadOnlyMT5Gateway]) -> None:
    fake, gateway = setup
    report = probe_book(gateway, "EURUSD", samples=3, interval=0, sleep=no_sleep)
    assert report.available and report.verdict == "EMPTY" and report.max_levels == 0
    assert fake.calls["market_book_release"] == 1  # always released


def test_a_populated_changing_book(setup: tuple[FakeMT5, ReadOnlyMT5Gateway]) -> None:
    fake, gateway = setup
    states = iter(
        [[(c.BOOK_TYPE_SELL, 1.1002, 5.0), (c.BOOK_TYPE_BUY, 1.1000, 3.0)], [(c.BOOK_TYPE_BUY, 1.1001, 2.0)]]
    )

    def step(_: float) -> None:
        fake.book["EURUSD"] = next(states, fake.book["EURUSD"])

    fake.book["EURUSD"] = [(c.BOOK_TYPE_BUY, 1.0999, 1.0)]
    report = probe_book(gateway, "EURUSD", samples=3, interval=1.0, sleep=step)
    assert report.verdict == "CHANGING" and report.max_levels == 2 and report.has_sizes
    assert report.distinct_snapshots == 3


def test_an_unknown_symbol_has_no_book(setup: tuple[FakeMT5, ReadOnlyMT5Gateway]) -> None:
    _, gateway = setup
    assert probe_book(gateway, "NOPE", samples=2, interval=0, sleep=no_sleep).verdict == "UNAVAILABLE"


def test_tick_history_depth_is_found_by_week(setup: tuple[FakeMT5, ReadOnlyMT5Gateway]) -> None:
    _, gateway = setup
    oldest, capped = oldest_tick_week(gateway, "EURUSD", NOW, max_weeks=20)
    assert oldest is not None and oldest.weekday() == 2 and not capped
    # FakeMT5 keeps 60 days of history: the oldest Wednesday with ticks is within the last week of it
    assert timedelta(days=53) <= NOW - oldest <= timedelta(days=60)


def test_the_depth_search_stops_at_its_limit(setup: tuple[FakeMT5, ReadOnlyMT5Gateway]) -> None:
    fake, gateway = setup
    oldest, capped = oldest_tick_week(gateway, "EURUSD", NOW, max_weeks=4)
    assert capped and oldest is not None and timedelta(days=35) <= NOW - oldest < timedelta(days=36)
    assert fake.calls["copy_ticks_range"] <= 5  # weeks 0, 1, 2, 4 (+ the limit): no search beyond it


def test_probe_reports_every_symbol_and_formats(setup: tuple[FakeMT5, ReadOnlyMT5Gateway]) -> None:
    fake, gateway = setup
    reports = probe(gateway, ["EURUSD"], NOW, book_samples=2, book_interval=0, max_weeks=4, sleep=no_sleep)
    (r,) = reports
    assert r.ticks is not None and r.ticks.ticks > 0 and r.ticks.per_minute > 0
    assert r.ticks.last_share == 0.0 and r.ticks.volume_share == 0.0  # like FX/CFD on FBS
    assert r.history_days == 35 and r.history_capped
    text = "\n".join(format_report(reports))
    assert "depth of market: EMPTY" in text and "or more (search limit reached)" in text
    assert fake.calls["order_send"] == 0 and fake.calls["order_check"] == 0
