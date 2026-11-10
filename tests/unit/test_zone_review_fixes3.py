# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""The runner after Sol's third review of piece 2a (eye/ZONE_LIVE.md L1, L4, L7, L8, L10): one test for each fix,
each failing on the code before the fix."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.unit.test_zone_trader import (
    bar,
    cands,
    flaky,
    hour_rows,
    world,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import World, ts


def buy_filled(w: World) -> Any:
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    [pos] = w.positions()
    return pos


def down_scenario(w: World) -> None:
    """The BUY setup is chosen with its orders resting; bar 521 withdraws it; the BUY P1 fills in bar 522."""
    w.step(2)
    w.step(300, 101.2)
    w.clock.set(ts("2025-01-06 10:40:00").to_pydatetime())
    w.bid(101.0)
    w.fake.orders_get()
    assert len(w.positions()) == 1
    w.clock.set(ts("2025-01-06 10:45:05").to_pydatetime())


DOWN_ROWS = hour_rows(
    bar(103, 104, 101.2, 101.2), bar(101.2, 105.5, 101.2, 105.0), bar(101.5, 104.0, 101.0, 101.0)
)


# --- 1: an owed close blocks every new place (L7) -------------------------------------------------------------------


def test_an_owed_close_blocks_new_orders(worlds: list[World], tmp_path: Path) -> None:
    rows = hour_rows(bar(107, 107.5, 106.5, 107.0), bar(107, 109.0, 101.0, 106.0))
    w = world(worlds, tmp_path, exec_rows={130: rows}, fake_bid=107.0)
    w.step(2)
    w.to("2025-01-06 10:17:00", 101.0)
    w.step(2)  # the BUY is chosen and filled
    f = flaky(w)
    f.partial_close = 1000  # its close, owed after the correction below, never completes
    w.to("2025-01-06 10:30:02", 106.0)  # the closed bar shows the earlier SELL touch: the SELL takes the hour
    assert (
        w.runner.hour is not None and w.runner.hour.chosen is not None and w.runner.hour.chosen.side == "SELL"
    )
    w.step(2)
    w.step(2)
    assert len(w.positions()) == 1  # the loser's position is still open
    assert not any(o.comment.startswith("Z2") for o in w.orders())  # nothing new while the close is owed


# --- 2: one path for the closed bars, restart or not (L8) -----------------------------------------------------------


def test_a_running_process_that_missed_bars_judges_a_late_fill_against_the_earlier_withdrawal(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, exec_rows={130: DOWN_ROWS})
    down_scenario(w)
    w.runner.cycle()  # the same process, a slow cycle: bars 521 and 522 are both new
    w.runner.cycle()
    assert w.positions() == [] and w.store.setup(1).outcome == "no fill"


# --- 6: a later stop row upgrades a stop under way (L10) -----------------------------------------------------------------


def test_a_later_stop_with_now_is_acknowledged_and_exits(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    buy_filled(w)
    first = w.store.request_stop(w.clock.now_utc(), "a")
    w.step(2)
    w.step(2)
    assert w.store.stop(first).acknowledged_at is not None and not w.runner.finished  # a position is open
    second = w.store.request_stop(w.clock.now_utc(), "b", now_flag=True)
    w.step(2)
    assert w.store.stop(second).acknowledged_at is not None and w.runner.finished


# --- 7: a finished setup owes nothing and is not rebuilt (L8) --------------------------------------------------------------


def test_a_finished_setup_clears_its_owed_close(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    pos = buy_filled(w)
    buy = cands(w)["BUY"]
    buy.close_reason[pos.ticket] = "FAULT"
    w.runner.close_wanted[pos.ticket] = "owed"
    w.runner._save(buy)
    w.step(2)
    w.step(2)
    assert w.runner.close_wanted == {}  # the close done, the owed close cleared
    # L2 / L5: a setup whose first fill was taken on the forming bar's quotes ends only once that bar has closed
    # and been judged on its true extremes
    assert w.store.setup(1).state == "live" and buy.exit_pending
    for _ in range(16):  # through the rest of that M15 bar, a cycle a minute
        w.step(60)
    assert w.store.setup(1).state == "ended" and w.store.setup(1).outcome == "traded"
