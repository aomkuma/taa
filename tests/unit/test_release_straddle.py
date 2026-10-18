"""Setup OWN S2, the CPI / NFP release-minute straddle (app/strategy/release_straddle.py), and the release calendar
(app/news/releases.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core.enums import Side
from app.core.errors import ConfigError
from app.news.releases import Release, load_releases, of_events, parse_releases
from app.strategy.release_straddle import ReleaseStraddle, StraddleParams

CPI = Release(datetime(2026, 9, 11, 12, 30, tzinfo=UTC), "CPI")  # 08:30 New York (EDT)
PPI = Release(datetime(2026, 9, 10, 12, 30, tzinfo=UTC), "PPI")
BID = 4000.0  # 1 U = 1.0 USD


def at(seconds: float) -> datetime:
    return CPI.at + timedelta(seconds=seconds)


def straddle(**kw: object) -> ReleaseStraddle:
    return ReleaseStraddle(StraddleParams(**kw), (PPI, CPI))  # type: ignore[arg-type]


class TestCalendar:
    def test_new_york_time_to_utc_across_dst(self) -> None:
        rows = [
            {"date": "2026-03-06", "time_et": "08:30", "event": "NFP"},  # EST, UTC-5
            {"date": "2026-09-11", "time_et": "08:30", "event": "cpi"},  # EDT, UTC-4
        ]
        got = parse_releases(rows)
        assert got[0] == Release(datetime(2026, 3, 6, 13, 30, tzinfo=UTC), "NFP")
        assert got[1] == Release(datetime(2026, 9, 11, 12, 30, tzinfo=UTC), "CPI")
        assert of_events(got, ["cpi"]) == (got[1],)

    def test_bad_rows_and_missing_files_fail_closed(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            parse_releases([{"date": "2026-13-01", "time_et": "08:30", "event": "CPI"}])
        with pytest.raises(ConfigError):
            parse_releases([{"date": "2026-03-01", "time_et": "08:30", "event": " "}])
        with pytest.raises(ConfigError):
            load_releases(tmp_path / "none.csv")
        f = tmp_path / "r.csv"
        f.write_text("date,time_et,event,note\n2026-10-14,08:30,CPI,\n", encoding="utf-8")
        assert load_releases(f) == (Release(datetime(2026, 10, 14, 12, 30, tzinfo=UTC), "CPI"),)


class TestStraddle:
    def test_the_first_trigger_crossed_after_the_release_is_the_entry(self) -> None:
        s = straddle()
        assert s.on_quote(at(-5), BID, BID + 0.4) is None
        assert s.on_quote(at(-1), BID, BID + 0.4) is None  # the reference: ask 4000.4, bid 4000
        assert s.on_quote(at(0.5), BID + 1.0, BID + 1.4) is None  # inside the triggers
        e = s.on_quote(at(1.2), BID + 2.5, BID + 2.9)
        assert e is not None and e.side is Side.BUY
        assert e.trigger == pytest.approx(BID + 0.4 + 2.0) and e.stop_distance == pytest.approx(8.0)
        assert e.close_at == at(60)
        assert s.on_quote(at(2), BID - 5, BID - 4.6) is None  # once per release (one cancels the other)

    def test_a_sell_on_the_bid(self) -> None:
        s = straddle(trigger_u=3.0)
        s.on_quote(at(-1), BID, BID + 0.4)
        assert s.on_quote(at(1), BID - 2.9, BID - 2.5) is None
        e = s.on_quote(at(2), BID - 3.0, BID - 2.6)
        assert e is not None and e.side is Side.SELL and e.trigger == pytest.approx(BID - 3.0)

    def test_a_pre_release_spike_does_not_trade(self) -> None:
        s = straddle()
        assert s.on_quote(at(-0.5), BID + 9, BID + 9.4) is None  # moves the reference only

    def test_no_reference_quote_no_trade(self) -> None:
        s = straddle()
        assert s.on_quote(at(1), BID + 9, BID + 9.4) is None
        assert s.on_quote(at(2), BID + 20, BID + 20.4) is None

    def test_the_window_closes(self) -> None:
        s = straddle()
        s.on_quote(at(-1), BID, BID + 0.4)
        assert s.on_quote(at(60), BID + 10, BID + 10.4) is None  # 08:31:00: the release minute is over

    def test_only_the_chosen_events(self) -> None:
        s = straddle()
        ppi = PPI.at
        s.on_quote(ppi - timedelta(seconds=1), BID, BID + 0.4)
        assert s.on_quote(ppi + timedelta(seconds=1), BID + 5, BID + 5.4) is None
        assert s.upcoming(ppi) is None and s.upcoming(CPI.at) == CPI


class TestOwnS2:
    def test_never_fires_on_a_bar_and_reads_quotes_only_near_a_release(self) -> None:
        from app.strategy.release_straddle import OwnS2

        s = OwnS2()
        s.attach_calendar((PPI, CPI))
        assert s.releases == (CPI,)
        assert s.busy(at(-20)) and s.busy(at(30)) and not s.busy(at(-60)) and not s.busy(at(61))
        assert s.on_quote("XAUUSD", at(-1), BID, BID + 0.4) is None
        e = s.on_quote("XAUUSD", at(1), BID + 3, BID + 3.4)
        assert e is not None and e.side is Side.BUY
        assert s.on_quote("EURUSD", at(1), BID + 3, BID + 3.4) is None  # its own reference per symbol
