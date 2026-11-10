# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""The decisions of eye/ZONE_LIVE.md e73af00 (L1 words, L10).

A. L1 "Within one exec_tf bar": for a stale removal waiting for the reopening, the time the market is closed does not
   count toward its one-bar timer (L8 cause 6) - a closure no longer gives hands-off at the reopening.
B. L1 "Without a fill" - one definition for L7 and L10: none of its entries read or pending; a place of unknown
   outcome does not hold it, and a candidate held only by the other's pending entry is without a fill too.
C. Every --now exit first ends `interrupted` every unfinished row without a fill, a candidate dropped for the
   other's visit and not yet final included."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.broker import mt5_constants as c
from tests.unit.test_zone_handsoff_causes import (
    HOUR0,
    REFUSED,
    build,
    decide,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.test_zone_review_fixes12 import hide_entries_of
from tests.unit.test_zone_review_fixes13 import market, quotes


def fail(*_a: Any, **_k: Any) -> Any:
    raise OSError("unavailable")


# --- A ----------------------------------------------------------------------------------------------------------------


def test_a_the_closed_market_does_not_count_toward_a_waiting_stale_removal_timer(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    mkt = market(w)
    stale = quotes(w)
    stale["on"] = True  # stale quotes, the market open
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.step(2)
    w.to("2025-01-06 10:15:15")  # the stale removals are owed: sent and refused - their one-bar timer starts
    assert len(w.orders()) == 4
    mkt["closed"] = True  # the market closes for 25 minutes
    w.step(2)
    w.to("2025-01-06 10:25:00")
    w.to("2025-01-06 10:40:00")
    stale["on"], mkt["closed"] = False, False  # it reopens; the removals are still refused
    w.step(2)
    assert w.runner.hands_off is None  # the closed 25 minutes did not count toward the one bar
    w.to("2025-01-06 10:56:00")  # more than one bar of open market since the first refusal
    assert w.runner.hands_off is not None and "removal" in w.runner.hands_off


# --- B ----------------------------------------------------------------------------------------------------------------


def test_b_the_stop_now_timeout_ends_a_setup_with_a_place_of_unknown_outcome_interrupted(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    ex.lose.add("Z1-P1-0")  # setup 1's P1 sent, never answered: of unknown outcome
    w.to(HOUR0)
    w.step(2)
    assert w.runner.unknown_since
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED  # the removals are never confirmed
    w.runner.gw.positions = fail  # type: ignore[method-assign]  # the later steps of a cycle never run
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(30)
    w.step(35)  # the 60 s
    assert w.runner.finished
    assert [w.store.setup(i).outcome for i in (1, 2)] == ["interrupted", "interrupted"]


def test_b_a_stop_interrupts_the_candidate_held_only_by_the_other_ones_pending_entry(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    hide = {"on": True}
    hide_entries_of(w, "Z2-", hide)
    decide(w)
    w.to("2025-01-06 10:05:00", 103.0)
    w.bid(108.8)
    w.fake.orders_get()  # the SELL P1 fills between two cycles: its entry is pending, it can take the hour
    w.bid(103.0)
    w.step(2)
    assert w.runner.entries and w.runner.hour is not None and w.runner.hour.chosen is None
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(2)
    assert w.store.setup(1).outcome == "interrupted"  # the BUY: none of its entries read or pending
    assert w.store.setup(2).outcome is None  # the SELL waits for its entry deal (L5)


# --- C ----------------------------------------------------------------------------------------------------------------


def test_c_a_stop_now_exit_ends_a_candidate_dropped_for_the_others_visit_interrupted(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.to(
        "2025-01-06 10:05:00", 101.3
    )  # a BUY touch on the bid, no fill (the ask is 101.50): the hour's setup
    assert w.runner.cands[1].chosen and w.runner.cands[2].dropped
    assert (
        w.store.setup(2).outcome is None
    )  # dropped for the other's visit: not final before the hour's close
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2, 103.0)
    w.step(2)
    assert w.runner.finished
    assert [w.store.setup(i).outcome for i in (1, 2)] == ["interrupted", "interrupted"]
