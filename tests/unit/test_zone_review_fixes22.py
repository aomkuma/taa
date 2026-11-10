"""The market closed in New York time, and the replay double's cycles (eye/ZONE_LIVE.md Words "Market closed", L2,
L11.2).

M. The four-week history of the market's hours is judged in New York time (the broker's daily break at 17:00 New
   York): after each daylight-saving change - the US one (2026-03-08) and the EU one of the server clock
   (2026-03-29) - the daily break is still a closed market; an ordinary hour is open; the weekend is closed.
R. The replay double never skips a cycle the runner could act on: inside an hour's 60 s decision window, or while
   the runner holds a latch or an L8 timer."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from app.core.clock import ServerClock
from app.zone.trader import ZoneRunner
from tests.unit.test_zone_replay_corruption import a_replay
from tests.unit.zone_live_support import hour_time, settings
from tests.zone_replay_compare import load_bars


@pytest.fixture(scope="module")
def stored_h1() -> pd.DataFrame:
    try:
        return load_bars("XAUUSD").h1
    except Exception as exc:  # the stored history is not on this machine
        pytest.skip(f"no stored XAUUSD history: {exc}")


def closed(h1: pd.DataFrame, when: str) -> bool:
    """The runner's own predicate on the stored H1 series."""
    runner: Any = SimpleNamespace(
        live=SimpleNamespace(frames={"H1": h1}),
        gw=SimpleNamespace(server_clock=ServerClock(settings("DEMO").env.BROKER_TIMEZONE)),
        _h1_server_len=-1,
        _h1_server_hours=set(),
        _h1_ny_len=-1,
        _h1_ny_hours=set(),
    )
    return bool(ZoneRunner._market_closed(runner, pd.Timestamp(when, tz="UTC")))


@pytest.mark.parametrize(
    "when",
    [
        "2026-03-02 22:00:24",  # the break before the US change (22:00 - 23:00 UTC)
        "2026-03-09 21:00:24",  # after the US change: 21:00 - 22:00 UTC, the server hour moved to 23:00
        "2026-03-16 21:00:24",
        "2026-03-30 21:00:24",  # after the EU change of the server clock
    ],
)
def test_m_the_daily_break_is_a_closed_market_across_both_daylight_saving_changes(
    stored_h1: pd.DataFrame, when: str
) -> None:
    assert closed(stored_h1, when)


@pytest.mark.parametrize("when", ["2026-03-16 15:00:24", "2026-03-30 08:00:24", "2026-03-02 21:00:24"])
def test_m_an_ordinary_hour_is_open(stored_h1: pd.DataFrame, when: str) -> None:
    assert not closed(stored_h1, when)


@pytest.mark.parametrize("when", ["2026-03-14 12:00:00", "2026-03-15 10:00:00"])
def test_m_the_weekend_is_closed(stored_h1: pd.DataFrame, when: str) -> None:
    assert closed(stored_h1, when)


# --- R: the replay double's cycles -------------------------------------------------------------------------------------


def test_r_no_cycle_is_skipped_while_the_runner_holds_a_latch_or_a_timer() -> None:
    rp = a_replay()
    try:
        r = rp.runner
        assert rp._retry_pending() is False
        now = pd.Timestamp(hour_time(130))
        for attr, value in (
            ("interrupt_owed", "stale"),
            ("unwanted", {7: "kill"}),
            ("unknown_since", {(1, "P1", 0): now}),
            ("gone_since", {7: now}),
            ("exit_since", {7: now}),
            ("remove_since", {7: now}),
            ("close_since", {7: now}),
            ("market_since", {(1, "P1", 0): now}),
            ("entries", {("position", 7): object()}),
        ):
            saved = getattr(r, attr)
            setattr(r, attr, value)
            assert rp._retry_pending() is True, attr
            setattr(r, attr, saved)
        assert rp._retry_pending() is False
    finally:
        rp.close()


def test_r_no_cycle_is_skipped_inside_an_hours_decision_window() -> None:
    rp = a_replay()
    try:
        r = rp.runner
        hour = pd.Timestamp(hour_time(131))
        r.hour = SimpleNamespace(open=hour, decided=False, undecided=None, reserved=False)  # type: ignore[assignment]
        assert rp._decision_pending(hour.timestamp() + 30.0) is True  # its 60 s from the hour's first quote
        assert rp._decision_pending(hour.timestamp() + 90.0) is False
        r.hour.decided = True
        assert rp._decision_pending(hour.timestamp() + 30.0) is False
    finally:
        rp.close()
