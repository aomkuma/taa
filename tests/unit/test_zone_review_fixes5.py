# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""The runner after Sol's fifth review of piece 2a (eye/ZONE_LIVE.md L2, L3, L4, L8): any state a crash can lose
between two commits is derived from the committed rows and the broker. One test for each finding that still holds
under the restart-fresh rule (L8, 2026-11-03); the crash-anywhere property is in test_zone_restart.py."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event

from app.broker import mt5_constants as c
from app.storage.models import (
    ZoneLiveSetupRow,
)
from app.zone.params import ZoneParams
from app.zone.store import ZoneStore
from tests.unit.test_zone_trader import (
    bar,
    cands,
    flaky,
    hour_rows,
    requests,
    restart,
    world,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import FILL, LOGIN, World, ts

# --- 2: an hour moves on only when every frame is up to date (L2) ---------------------------------------------------


def test_the_hour_does_not_move_on_while_the_exec_frame_is_behind(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(
        FILL, FILL, FILL, bar(103, 104, 101.2, 103)
    )  # the last bar of the hour touches the BUY line
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.to("2025-01-06 10:59:00", 103)
    w.src.fail_tfs = {"M15"}  # H1 is read, the exec frame is not
    w.to("2025-01-06 12:00:03", 103)  # two H1 bars have closed: the next hour must not start without bar 523
    assert w.store.setup(1).state == "live"  # the candidate was not dropped without its last bar
    assert w.runner.hour is not None and w.runner.hour.open == ts("2025-01-06 10:00")
    w.src.fail_tfs = set()
    w.step(2)
    assert (
        w.store.setup(1).chosen is True
    )  # the missed touch of the last bar is found, then the hour moves on
    assert w.runner.hour is not None and w.runner.hour.open == ts("2025-01-06 12:00")


# --- 3: P1 refused is derived from the committed request (L3) ---------------------------------------------------------


def test_a_crash_after_the_refusal_committed_does_not_send_another_p1(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.refuse["Z1-P1-0"] = 10015

    def crash(*args: Any, **kwargs: Any) -> None:
        raise SystemExit("the process died after the refusal was committed")

    w.runner._on_refused = crash  # type: ignore[method-assign]
    w.runner.start()
    with pytest.raises(SystemExit):
        w.step(2)
    w2 = restart(w, worlds)  # L8: the rows of the hour end at the restart; nothing is placed again
    w2.step(2)
    w2.step(2)
    assert [r.comment for r in requests(w2, "place") if r.setup_id == 1] == ["Z1-P1-0"]  # no second P1
    assert w2.store.setup(1).state == "ended" and w2.store.setup(1).outcome == "restart"
    assert w2.orders() == []


# --- 5: each visit of the hour is recorded once ----------------------------------------------------------------------


def test_a_crash_before_the_visit_records_were_written_loses_none_of_the_bar(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(107, 109.0, 101.0, 106.0))  # both lines are visited in the one H1 bar
    w = world(worlds, tmp_path, exec_rows={130: rows}, fake_bid=107.0)
    w.step(2)
    w.to("2025-01-06 10:59:00", 106.0)
    store = w.runner.store
    assert store is not None
    calls: list[int] = []

    def add_visits(*args: Any, **kwargs: Any) -> None:
        calls.append(len(args[1]))
        raise SystemExit("the process died before the records of the bar were written")

    store.add_visits = add_visits  # type: ignore[method-assign]
    with pytest.raises(SystemExit):
        w.to("2025-01-06 11:00:03", 106.0)
    assert calls == [2] and w.store.visits() == []  # all the records of the bar go in ONE call, none written
    w2 = restart(w, worlds)  # L8: the hours while down have no records (a gap), none is invented
    w2.step(2)
    assert w2.store.visits(ts("2025-01-06 10:00").to_pydatetime()) == []


# --- frames behind: exits are broker facts, a fill waits for a bar that covers it (L2, L8) -------------------------


def test_an_exit_is_absorbed_while_a_state_frame_is_behind_and_the_setups_orders_go(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, params=ZoneParams(cancel_frac=0.9, be_mode="off"))
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    assert "Z1-P2-0" in w.names()
    w.to("2025-01-06 10:59:00", 101.4)
    w.src.fail_tfs = {"D1"}  # D1 cannot be read from here on; M15 is current
    w.clock.set(ts("2025-01-06 11:05:00").to_pydatetime())
    w.bid(110.2)
    w.fake.orders_get()  # P1 hits the TP at 11:05
    assert w.positions() == []
    w.to("2025-01-06 11:15:00", 110.2)
    assert w.store.setup(1).outcome == "traded"  # the exit was absorbed whatever the lag
    assert not any(o.comment.startswith("Z1") for o in w.orders())  # and P2 did not outlive its setup


def test_a_fill_past_the_end_of_a_stuck_exec_frame_waits_for_its_bar(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(
        bar(103, 104, 101.2, 103), bar(103, 105.5, 101.0, 104)
    )  # bar 521 withdraws an unfilled BUY
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(300, 101.2)  # the BUY candidate is the hour's setup, its orders rest
    w.to("2025-01-06 10:15:02", 101.2)  # bar 520 is in and judged
    w.src.fail_tfs = {"M15"}  # the exec frame is stuck after bar 520
    w.clock.set(ts("2025-01-06 10:16:10").to_pydatetime())
    w.bid(101.0)
    w.fake.orders_get()  # the BUY P1 fills at 10:16, a time no local bar covers
    places = len(requests(w, "place"))
    w.to("2025-01-06 10:20:00", 101.0)
    assert (
        len(w.positions()) == 1 and cands(w)["BUY"].fills == {}
    )  # kept (its broker SL / TP), not judged yet
    assert len(requests(w, "place")) == places  # nothing new in the meantime
    w.src.fail_tfs = set()
    w.to(
        "2025-01-06 10:30:05", 101.0
    )  # the frame catches up: the fill is judged at bar 521, which withdrew it
    assert w.positions() == []  # closed: the withdrawal of bar 521 came before the fill
    assert cands(w).get("BUY") is None or cands(w)["BUY"].fills == {}


# --- the life of a setup under way does not wait for the other frames (L2, L5) --------------------------------------


def test_a_setup_under_way_gets_its_break_even_while_a_state_frame_is_behind(
    worlds: list[World], tmp_path: Path
) -> None:
    # a SELL is filled at 10:05; D1 cannot be read from 10:59; the 11:00-11:15 bar triggers the break-even
    rows130 = hour_rows(*[bar(108.0, 109.0, 105.0, 106.0)] * 4)  # no bar of the hour reaches the BE level
    w = world(worlds, tmp_path, exec_rows={130: rows130, 131: hour_rows(bar(108.0, 108.5, 104.0, 104.5))})
    w.step(2)
    w.step(60, 108.9)  # the SELL P1 fills
    w.step(2)
    assert [p.comment for p in w.positions()] == ["Z2-P1-0"]
    w.to("2025-01-06 10:58:00", 108.0)
    w.src.fail_tfs = {"D1"}
    w.to("2025-01-06 11:15:05", 105.0)  # bar 524 is closed and held by the exec frame
    sell = cands(w)["SELL"]
    assert sell.be_on and sell.be_sent == 108.48  # 108.6842 - 0.20, toward the TP
    assert w.positions()[0].sl == 108.48  # the stop moved while D1 was down
    assert w.runner.hour is not None and w.runner.hour.open == ts(
        "2025-01-06 10:00"
    )  # no new hour without D1


# --- the lag clears: the hour moves on, nothing of a setup under way is decided twice (L2, L8) ----------------------------------


def count_calls(w: World, name: str, key: Any = None) -> Counter[Any]:
    """Count the calls of a runner method (by ``key(*args)``), to show a decision is applied exactly once."""
    counts: Counter[Any] = Counter()
    real = getattr(w.runner, name)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        counts[key(*args) if key else "n"] += 1
        return real(*args, **kwargs)

    setattr(w.runner, name, wrapper)
    return counts


def count_new_fills(w: World) -> Counter[int]:
    """Count the fills absorbed, by position: a position already known is not a new fill."""
    counts: Counter[int] = Counter()
    real = w.runner._on_in

    def wrapper(deal: Any, *args: Any, **kwargs: Any) -> Any:
        counts[deal.position_id] += 1
        return real(deal, *args, **kwargs)

    w.runner._on_in = wrapper  # type: ignore[method-assign]
    return counts


def sends_by(f: Any, action: int, field: str) -> Counter[Any]:
    return Counter(r.get(field) for r in f.sent if r.get("action") == action)


def test_the_lag_clearing_keeps_a_setup_under_way_and_moves_the_hour_on(
    worlds: list[World], tmp_path: Path
) -> None:
    rows130 = hour_rows(*[bar(108.0, 109.0, 105.0, 106.0)] * 4)
    w = world(worlds, tmp_path, exec_rows={130: rows130, 131: hour_rows(bar(108.0, 108.5, 104.0, 104.5))})
    f = flaky(w)
    ended = count_calls(w, "_end", lambda cand, *a: cand.id)
    chosen = count_calls(w, "_choose", lambda cand, *a: cand.id)
    fills = count_new_fills(w)
    w.step(2)
    w.step(60, 108.9)  # the SELL P1 fills
    w.step(2)
    w.to("2025-01-06 10:58:00", 108.0)
    w.src.fail_tfs = {"D1"}
    w.to("2025-01-06 11:15:05", 105.0)  # the break-even is applied while D1 is down
    sell = cands(w)["SELL"]
    assert sell.be_on and w.positions()[0].sl == 108.48
    be_bar = sell.be_j
    w.src.fail_tfs = set()  # D1 recovers
    w.to("2025-01-06 11:20:00", 105.0)
    w.to("2025-01-06 11:21:00", 105.0)
    assert w.runner.hour is not None and w.runner.hour.open == ts("2025-01-06 11:00")  # the hour moved on
    assert w.runner.hour.reserved and w.runner.hour.skipped == {"BUY": "busy", "SELL": "busy"}
    assert cands(w)["SELL"].be_j == be_bar and cands(w)["SELL"].be_sent == 108.48 and len(w.positions()) == 1
    # every decision of the setup under way was applied exactly once, and every send happened once
    assert ended[2] == 0 and chosen == Counter({2: 1})
    assert list(fills.values()) == [1]
    [pos] = [p.ticket for p in w.positions()]
    assert sends_by(f, c.TRADE_ACTION_SLTP, "position") == Counter({pos: 1})  # one break-even modify
    assert all(n == 1 for n in sends_by(f, c.TRADE_ACTION_REMOVE, "order").values())  # each removal once
    assert all(n == 1 for n in sends_by(f, c.TRADE_ACTION_PENDING, "comment").values())  # each place once
    assert not sends_by(f, c.TRADE_ACTION_DEAL, "position")  # nothing was closed


def test_a_lag_across_the_h1_open_leaves_that_hour_undecided(worlds: list[World], tmp_path: Path) -> None:
    # nothing is under way; D1 is down across 11:00; the 11:00 bar touches the BUY line; D1 recovers at 11:21:
    # past the hour's first 60 s, so the hour gets no candidates (L2) - a decision is never made later
    w = world(worlds, tmp_path, exec_rows={131: hour_rows(bar(103, 104, 101.0, 103))})
    f = flaky(w)
    chosen = count_calls(w, "_choose", lambda cand, *a: cand.id)
    w.step(2)
    w.to("2025-01-06 10:58:00", 103.0)
    w.src.fail_tfs = {"D1"}
    w.to("2025-01-06 11:20:00", 103.0)
    assert w.runner.hour is not None and w.runner.hour.open == ts(
        "2025-01-06 10:00"
    )  # no decision without D1
    assert len(w.store.setups(hour_open=ts("2025-01-06 11:00").to_pydatetime())) == 0
    w.src.fail_tfs = set()
    w.to("2025-01-06 11:21:00", 103.0)
    w.to("2025-01-06 11:22:00", 103.0)
    assert w.runner.hour.open == ts("2025-01-06 11:00") and w.runner.hour.undecided
    assert w.store.setups(hour_open=ts("2025-01-06 11:00").to_pydatetime()) == []
    assert sum(chosen.values()) == 0
    w.to("2025-01-06 12:00:03", 103.0)
    assert {r.classification for r in w.store.visits(ts("2025-01-06 11:00").to_pydatetime())} == {"undecided"}
    assert len(w.store.setups(hour_open=ts("2025-01-06 12:00").to_pydatetime())) == 2  # the next hour decides
    assert all(n == 1 for n in sends_by(f, c.TRADE_ACTION_PENDING, "comment").values())  # each place once
    assert all(n == 1 for n in sends_by(f, c.TRADE_ACTION_REMOVE, "order").values())  # each removal once


def test_all_of_an_hours_candidate_rows_are_created_in_one_transaction(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, start=False)
    inserts: list[str] = []

    def second_insert_fails(mapper: Any, connection: Any, target: Any) -> None:
        inserts.append(target.side)
        if len(inserts) == 2:
            raise SystemExit("the process died between the two rows of the hour")

    w.runner.start()
    event.listen(ZoneLiveSetupRow, "after_insert", second_insert_fails)
    try:
        with pytest.raises(SystemExit):
            w.step(2)  # the 10:00 decision
    finally:
        event.remove(ZoneLiveSetupRow, "after_insert", second_insert_fails)
    assert inserts == ["BUY", "SELL"]
    assert ZoneStore(w.db, LOGIN, "FBS-Demo").setups() == []  # neither row exists: not one of the two
    w2 = restart(w, worlds)
    w2.to("2025-01-06 11:00:03", 103.0)  # the first H1 open after the restart
    assert sorted(r.side for r in w2.store.setups()) == ["BUY", "SELL"]  # both rows, made together
    assert len(w2.names()) == 4
