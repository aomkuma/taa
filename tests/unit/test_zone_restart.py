# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""The start of the zone runner (eye/ZONE_LIVE.md L8 "The start"; the tests of L11.3): nothing of a previous
process carries over - its unfinished rows end ``restart``, its requests are closed and its keys are not ours; a
magic that is not flat is hands-off until it is; the first decision is at the first H1 open after the start (or
after the flat book), never in the middle of an hour, with no reservation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.broker import mt5_constants as c
from app.zone import live
from tests.unit.test_zone_trader import (
    cands,
    flaky,
    requests,
    restart,
    world,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import MAGIC, World, ts


def buy_filled(w: World) -> Any:
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    [pos] = w.positions()
    return pos


def placed(w: World) -> list[str]:
    return [r.comment for r in requests(w, "place")]


def inject_order(w: World, ticket: int, comment: str, price: float = 101.32) -> None:
    w.fake.orders.append(
        SimpleNamespace(
            ticket=ticket,
            time_setup=0,
            type=c.ORDER_TYPE_BUY_LIMIT,
            state=1,
            volume_initial=0.01,
            volume_current=0.01,
            price_open=price,
            sl=95.0,
            tp=110.0,
            price_current=0.0,
            symbol="XAUUSD",
            magic=MAGIC,
            comment=comment,
            type_time=0,
            time_expiration=0,
            type_filling=2,
        )
    )


def inject_position(w: World, ticket: int, comment: str, price: float = 120.0) -> None:
    w.fake.positions.append(
        SimpleNamespace(
            ticket=ticket,
            symbol="XAUUSD",
            type=c.POSITION_TYPE_BUY,
            volume=0.01,
            price_open=price,
            sl=95.0,
            tp=110.0,
            price_current=price,
            profit=0.0,
            swap=0.0,
            magic=MAGIC,
            comment=comment,
            time=w.bundle.gateway.server_clock.utc_to_server_epoch(w.clock.now_utc()),
            identifier=ticket,
            margin=1.0,
        )
    )


# --- orders of the magic at the start: hands-off ------------------------------------------------------------------


def test_orders_resting_at_a_start_are_removed_p2_before_p1_and_the_next_hour_decides_anew(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    assert len(w.names()) == 4
    w2 = restart(w, worlds)  # 10:00:00, in the hour the candidates were made
    assert w2.runner.hands_off is not None and "not flat" in w2.runner.hands_off
    assert w2.orders() == []
    for sid in (1, 2):  # P2 before P1 of the same setup
        names = [r.name for r in requests(w2, "remove") if r.setup_id == sid]
        assert names == ["P2", "P1"]
    # the rows of the previous process ended `restart` at the start: none ends `hands-off` here
    assert [(r.state, r.outcome) for r in w2.store.setups()] == [("ended", "restart")] * 2
    assert w2.runner.cands == {} and w2.runner.res_end is None
    w2.step(2)  # the magic is flat: the hands-off ends; a fresh start at the next H1 open
    assert w2.runner.hands_off is None and w2.runner.decide_from == ts("2025-01-06 11:00")
    w2.to("2025-01-06 10:30:00", 103.0)
    w2.to("2025-01-06 10:59:50", 103.0)
    assert placed(w2) == ["Z1-P1-0", "Z1-P2-0", "Z2-P1-0", "Z2-P2-0"] and w2.orders() == []  # none new
    w2.to("2025-01-06 11:00:03", 103.0)
    assert w2.names() == ["Z3-P1-0", "Z3-P2-0", "Z4-P1-0", "Z4-P2-0"]


def test_a_flat_book_reached_in_the_middle_of_an_hour_decides_at_the_next_h1_open(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    w.step(2)
    f.refuse_remove = 10_000  # the removals are refused until 10:30 (retried each cycle, no escalation)
    w2 = restart(w, worlds)
    w2.to("2025-01-06 10:20:00", 103.0)
    assert len(w2.orders()) == 4 and w2.runner.hands_off is not None
    f.refuse_remove = 0
    w2.to("2025-01-06 10:30:00", 103.0)
    w2.step(2)
    assert w2.orders() == [] and w2.runner.hands_off is None
    assert w2.runner.decide_from == ts("2025-01-06 11:00")  # not 10:30, not the hour already under way
    w2.to("2025-01-06 10:45:00", 103.0)
    assert placed(w2) == ["Z1-P1-0", "Z1-P2-0", "Z2-P1-0", "Z2-P2-0"]
    w2.to("2025-01-06 11:00:03", 103.0)
    assert len(w2.names()) == 4 and w2.names()[0].startswith("Z3")


def test_the_hour_of_a_start_records_its_visits_as_undecided(worlds: list[World], tmp_path: Path) -> None:
    from tests.unit.test_zone_trader import bar, hour_rows

    rows = hour_rows(bar(107, 109.0, 101.0, 106.0))
    w = world(worlds, tmp_path, exec_rows={130: rows}, fake_bid=107.0)
    w.step(2)
    w2 = restart(w, worlds)
    w2.to("2025-01-06 10:59:00", 106.0)
    w2.to("2025-01-06 11:00:03", 106.0)
    w2.to("2025-01-06 12:00:03", 106.0)
    records = w2.store.visits(ts("2025-01-06 10:00").to_pydatetime())
    assert sorted((r.side, r.classification) for r in records) == [
        ("BUY", "undecided"),
        ("SELL", "undecided"),
    ]
    assert all(r.agreed for r in records)  # excluded from parity: never a disagreement
    assert not any(r.classification == "setup" for r in w2.store.visits())


# --- the rows of a previous process ---------------------------------------------------------------------------------


def test_a_chosen_setup_without_a_position_ends_restart_and_reserves_nothing(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(300, 101.2)  # the BUY candidate is the hour's setup, the SELL candidate is dropped
    assert cands(w)["BUY"].chosen
    w2 = restart(w, worlds)
    buy = w2.store.setup(1)
    assert (buy.state, buy.outcome, buy.chosen) == ("ended", "restart", True)
    assert w2.runner.res_end is None  # nothing of a previous process decides anything after a start
    assert w2.store.setup(2).outcome == "restart"  # its drop was not final yet (the hour had not closed)
    w2.step(2)
    assert w2.orders() == [] and w2.runner.hands_off is None
    w2.to("2025-01-06 11:00:03", 103.0)
    assert w2.runner.hour is not None and not w2.runner.hour.reserved and len(w2.names()) == 4


def test_a_never_chosen_setup_ends_restart_without_a_reservation(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w2 = restart(w, worlds)
    assert [(r.outcome, r.end_close_time, r.chosen) for r in w2.store.setups()] == [
        ("restart", None, False)
    ] * 2
    assert w2.runner.res_end is None


def test_a_position_at_the_start_is_left_to_the_broker_until_it_closes(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    pos = buy_filled(w)
    w2 = restart(w, worlds)
    assert w2.runner.hands_off is not None and w2.runner.cands == {}
    assert w2.orders() == [] and [p.ticket for p in w2.positions()] == [pos.ticket]  # P2 and the SELL gone
    assert [(r.state, r.outcome) for r in w2.store.setups()] == [("ended", "restart")] * 2
    w2.to("2025-01-06 10:59:50", 101.4)
    assert requests(w2, "close") == [] and requests(w2, "stops") == []  # no position is touched
    w2.to("2025-01-06 11:00:03", 101.4)  # hands-off: the hour is not decided
    assert w2.orders() == [] and w2.runner.hour is not None and w2.runner.hour.undecided
    w2.to("2025-01-06 11:20:00", 110.2)
    w2.step(2)  # the TP closed it at the broker: the magic is flat
    assert w2.positions() == [] and w2.runner.hands_off is None
    assert w2.runner.decide_from == ts("2025-01-06 12:00")


def test_a_place_of_a_previous_process_that_arrives_is_not_ours(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.no_reply_lost.add("Z1-P1-0")
    w.runner.start()
    w.step(2)  # the 10:00 decision: Z1-P1-0 has no reply
    w2 = restart(w, worlds)
    assert [r.state for r in requests(w2, "place") if r.comment == "Z1-P1-0"] == ["moot"]
    w2.step(2)  # the previous run's other orders are gone: the magic is flat, the hands-off of the start ends
    assert w2.orders() == [] and w2.runner.hands_off is None
    inject_order(w2, 9_501, "Z1-P1-0")  # the lost place shows up late
    w2.step(2)
    assert w2.runner.hands_off is not None and "not ours" in w2.runner.hands_off  # L8 cause 4
    w2.step(2)
    assert w2.orders() == []  # removed
    assert sum(1 for r in f.sent if r.get("comment") == "Z1-P1-0") == 1  # never sent again


def test_an_order_and_a_position_not_ours_at_a_start_are_hands_off_and_named(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    inject_order(w, 9_601, "junk", 90.0)
    inject_position(w, 9_602, "Z99-P1-0", 120.0)
    w2 = restart(w, worlds)
    w2.step(2)
    assert w2.orders() == []
    assert [p.ticket for p in w2.positions()] == [9_602] and 9_602 in w2.runner.not_ours_positions
    status = json.loads(w2.store.get_state("status") or "{}")
    assert "9602" in status["not_ours_positions"] and w2.runner.close_wanted == {}
    assert status["hands_off"]


# --- the stop row -----------------------------------------------------------------------------------------------------


def test_a_stop_row_left_open_by_a_dead_runner_is_closed_at_the_start(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    sid = w.store.request_stop(w.clock.now_utc(), "tester")  # the runner dies before it reads the row
    with caplog.at_level(logging.WARNING, logger="app.zone.trader"):
        w2 = restart(w, worlds)
    row = w2.store.stop(sid)
    assert row is not None and row.acknowledged_at is not None
    assert not w2.runner.stopping and any("left open" in r.message for r in caplog.records)


def test_every_stop_row_is_closed_when_the_runner_exits(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    first = w.store.request_stop(w.clock.now_utc(), "a")
    second = w.store.request_stop(w.clock.now_utc(), "b", now_flag=True)
    w.step(2)
    w.step(2)
    assert w.runner.finished
    for sid in (first, second):
        row = w.store.stop(sid)
        assert row is not None and row.acknowledged_at is not None


def test_a_runner_that_dies_with_an_error_closes_the_stop_row_on_the_way_out(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    sid = w.store.request_stop(w.clock.now_utc(), "tester", now_flag=False)
    w.store.request_stop(w.clock.now_utc(), "later")
    pos = SimpleNamespace(done=False)

    def sleeper(seconds: float) -> None:
        pos.done = True
        raise RuntimeError("the process is going down")

    w.runner.cycle = lambda: None  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        w.runner.run(sleep=sleeper)
    for row in (w.store.stop(sid), w.store.stop(sid + 1)):
        assert row is not None and row.acknowledged_at is not None
    assert w.runner.lock is not None and w.runner.lock._fh is None  # the lock is released too


# --- the first decision -----------------------------------------------------------------------------------------------


def test_a_start_within_the_first_minute_of_the_hour_waits_for_the_next_h1_open(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, now="2025-01-06 10:00:30")
    w.step(2)
    assert w.names() == [] and w.runner.decide_from == ts(
        "2025-01-06 11:00"
    )  # never in the middle of an hour
    w.to("2025-01-06 11:00:03", 103.0)
    assert len(w.names()) == 4


def test_a_start_after_the_first_minute_waits_for_the_next_h1_open(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, now="2025-01-06 10:01:01")
    w.to("2025-01-06 10:30:00", 103.0)
    assert w.names() == [] and w.store.setups() == [] and w.runner.decide_from == ts("2025-01-06 11:00")
    w.to("2025-01-06 11:00:03", 103.0)
    assert len(w.names()) == 4


def test_a_start_seconds_before_an_h1_open_decides_that_open(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)  # 09:59:58
    assert w.names() == [] and w.runner.decide_from == ts("2025-01-06 10:00")
    w.step(2)
    assert len(w.names()) == 4


def test_a_failed_first_read_decides_nothing(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path, start=False)
    real = w.runner.gw.positions
    w.runner.gw.positions = lambda symbol=None: (_ for _ in ()).throw(OSError("no positions"))  # type: ignore[method-assign]
    w.runner.start()
    assert not w.runner.initialized and w.runner.decide_from is None  # never an empty account
    w.runner.gw.positions = real  # type: ignore[method-assign]
    w.step(2)
    assert w.runner.initialized and len(w.names()) == 4


def test_the_live_helper_used_for_an_sl_modify_of_unknown_outcome_is_the_one_the_spec_names() -> None:
    assert live.stop_at_or_beyond(102.0, 101.52, True, 0.01) and not live.stop_at_or_beyond(
        101.0, 101.52, True, 0.01
    )
    assert live.stop_at_or_beyond(100.0, 100.5, False, 0.01) and not live.stop_at_or_beyond(
        101.0, 100.5, False, 0.01
    )
