"""The run-zone runner on FakeMT5 (eye/ZONE_LIVE.md L11.3 and L11.4): the hour's candidates, the first visit, the
setup's life, the orders and their write-ahead, the break-even, the reservation, restarts and the refusals.

The replay against the simulation (L11.2) is a separate piece; these tests drive the runner by hand on a world of
constructed bars (``tests/unit/zone_live_support.py``): the test sets the bid, moves the clock and runs a cycle."""

from __future__ import annotations

import ast
import dataclasses
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from app.broker import mt5_constants as c
from app.broker.execution import CheckResult, ExecutionGateway, SendResult
from app.broker.retcodes import classify, describe
from app.core.enums import TradingMode
from app.core.errors import SafetyViolation
from app.zone import live
from app.zone.core import BarValues, start_life
from app.zone.params import ZoneParams
from app.zone.trader import ProcessLock, ZoneRunner, ZoneStartError
from tests.unit.zone_live_support import (
    FILL,
    GRID,
    LOGIN,
    MAGIC,
    Row,
    World,
    make_world,
    ts,
)

ROOT = Path(__file__).resolve().parents[2]
SPREAD = 20  # points: the ask is the bid + 0.20


@pytest.fixture
def worlds() -> Iterator[list[World]]:
    made: list[World] = []
    yield made
    for w in made:
        if w.runner.lock is not None:
            w.runner.lock.release()
        w.db.dispose()


def world(worlds: list[World], tmp_path: Path, **kw: Any) -> World:
    kw.setdefault("spread", SPREAD)
    w = make_world(tmp_path, **kw)
    worlds.append(w)
    return w


def bar(o: float, h: float, lo: float, c_: float) -> Row:
    return (o, h, lo, c_)


def hour_rows(*rows: Row) -> list[Row]:
    """An hour of exec rows: the rows given, the filler for the rest."""
    return list(rows) + [FILL] * (4 - len(rows))


def cands(w: World) -> dict[str, Any]:
    return {c_.side: c_ for c_ in w.runner.cands.values()}


def requests(w: World, kind: str | None = None) -> list[Any]:
    """The request rows of a kind; ``stops`` = the SL modifies (a ``modify`` of a position, L8)."""
    if kind == "stops":
        return [r for r in w.store.requests() if r.kind == "modify" and r.position_ticket is not None]
    if kind == "modify":
        return [r for r in w.store.requests() if r.kind == "modify" and r.position_ticket is None]
    return [r for r in w.store.requests() if kind is None or r.kind == kind]


def restart(
    w: World,
    worlds: list[World],
    params: ZoneParams | None = None,
    set_version: int | None = None,
    grids_fn: Any = None,
) -> World:
    """A new process: the same database, broker and bars, a fresh runner (the old lock is released)."""
    old = w.runner
    if old.lock is not None:
        old.lock.release()
    runner = ZoneRunner(
        cfg=old.cfg if set_version is None else dataclasses.replace(old.cfg, set_version=set_version),
        params=params or old.params,
        clock=old.clock,
        gateway=old.gw,
        execution=old.exe,
        bar_source=old.src,
        db=old.db,
        bars=old.live.bars().__class__(
            *(old.live.frames[tf] for tf in ("D1", "H4", "H1", "M15", "M5")), old.live.point
        ),
        kill_switch=old.kill,
        magic=old.magic,
        grids_fn=grids_fn or old.grids_fn,
        lock=ProcessLock(w.tmp / "runner.lock"),
    )
    runner.start()
    w2 = dataclasses.replace(w, runner=runner)
    worlds.append(w2)
    return w2


# --- the pure parts ---------------------------------------------------------------------------------------------


def test_candidates_are_the_nearest_armed_lines_and_a_line_on_the_open_is_none() -> None:
    armed = {(100.0, 10.0, 100.0): False, (100.0, 10.0, 110.0): True}
    assert live.nearest_armed(GRID, armed, 105.0, +1) == 90.0  # 100 is disarmed: passed over
    assert live.nearest_armed(GRID, armed, 105.0, -1) == 110.0
    assert live.nearest_armed(GRID, {}, 100.0, +1) == 90.0  # a line equal to the open is no candidate
    assert live.nearest_armed(GRID, {}, 100.0, -1) == 110.0
    assert live.nearest_armed(GRID, {(100.0, 10.0, 110.0): False}, 105.0, -1) == 120.0


def test_prices_are_sent_rounded_sl_away_tp_near() -> None:
    from app.zone.core import plan_setup
    from tests.unit.test_zone_bot import mk_visit

    buy = plan_setup(mk_visit("BUY", 100.0, 10.0), ZoneParams())
    sent = live.sent_prices(buy, 0.01)
    assert (sent.p1, sent.p2, sent.sl, sent.tp) == (101.32, 98.03, 95.0, 110.0)
    sell = plan_setup(mk_visit("SELL", 100.0, 10.0), ZoneParams())
    sent = live.sent_prices(sell, 0.01)
    assert (sent.p1, sent.p2, sent.sl, sent.tp) == (98.68, 101.97, 105.0, 90.0)
    assert live.tick_down(95.019, 0.01) == 95.01 and live.tick_up(95.011, 0.01) == 95.02
    assert live.be_stop_sent(101.5158, +1, 0.01) == 101.52 and live.be_stop_sent(98.4842, -1, 0.01) == 98.48


def test_a_withdrawal_and_a_closed_hour_cancel_in_one_bar_is_no_fill() -> None:
    from app.zone.core import plan_setup
    from tests.unit.test_zone_bot import mk_visit

    plan = plan_setup(mk_visit("BUY", 100.0, 10.0), ZoneParams())
    j = plan.j0 + 1
    both = BarValues(106.0, 104.0, 0.0, 100.0, 105.0)  # high reaches the withdrawal; the hour fell 5 >= 10/3
    assert live.life_at_close(plan, start_life(plan), j, both).status == "withdrawn"
    assert live.closed_hour_cancel(plan, j, 100.0, 105.0)
    assert not live.moved_away(plan, plan.j0, 106.0, 104.0)  # no withdrawal in the setup's first bar


def test_comments_round_trip() -> None:
    assert live.make_comment(12, "P2", 3) == "Z12-P2-3"
    assert live.parse_comment("Z12-P2-3") == (12, "P2", 3)
    assert live.parse_comment("Z12-P2-3 [sl]") == (12, "P2", 3)
    assert live.parse_comment("taa:1234") is None and live.parse_comment("") is None


# --- the hour -----------------------------------------------------------------------------------------------------


def test_the_hours_candidates_get_their_orders(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0", "Z2-P1-0", "Z2-P2-0"]
    prices = w.order_prices()
    assert prices == {"Z1-P1-0": 101.32, "Z1-P2-0": 98.03, "Z2-P1-0": 108.68, "Z2-P2-0": 111.97}
    o = {x.comment: x for x in w.orders()}
    assert o["Z1-P1-0"].type == c.ORDER_TYPE_BUY_LIMIT and o["Z2-P1-0"].type == c.ORDER_TYPE_SELL_LIMIT
    assert (o["Z1-P1-0"].sl, o["Z1-P1-0"].tp) == (95.0, 110.0)
    assert (o["Z2-P1-0"].sl, o["Z2-P1-0"].tp) == (115.0, 100.0)
    assert {x.magic for x in w.orders()} == {MAGIC} and {x.volume_initial for x in w.orders()} == {0.01}
    # the backstop: ORDER_TIME_SPECIFIED, the close of the H1 bar + 1 minute (server time = UTC + 2 in January)
    expect = w.bundle.gateway.server_clock.utc_to_server_epoch(ts("2025-01-06 11:01").to_pydatetime())
    assert {(x.type_time, x.time_expiration) for x in w.orders()} == {(c.ORDER_TIME_SPECIFIED, expect)}
    rows = w.store.setups()
    assert [(r.side, r.line, r.p1_sent, r.state, r.chosen) for r in rows] == [
        ("BUY", 100.0, 101.32, "live", False),
        ("SELL", 110.0, 108.68, "live", False),
    ]
    assert all(r.account_login == LOGIN for r in rows)


def test_the_first_visit_removes_the_other_candidates_orders(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(300, 101.2)  # within Z of 100 (<= 101.3158) but the ask 101.4 is above P1 101.32: a visit, no fill
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"]
    assert w.runner.hour is not None and w.runner.hour.chosen is cands(w)["BUY"]
    assert w.store.setup(2).state == "dropped" and w.store.setup(1).chosen is True


def test_a_skipped_first_visit_leaves_the_other_candidate(worlds: list[World], tmp_path: Path) -> None:
    # hour 129 fell 2.0 on its H1 bar (103.5 -> 101.5): a body toward the BUY line as large as the median range
    # (5a: momentum), the low 101.5 staying out of reach of the line (101.3158)
    rows129 = [
        bar(103.5, 103.6, 102.0, 102.5),
        bar(102.5, 102.6, 101.8, 102.0),
        bar(102.0, 102.2, 101.6, 101.8),
        bar(101.8, 102.0, 101.5, 101.5),
    ]
    w = world(worlds, tmp_path, exec_rows={129: rows129})
    w.step(2)
    assert w.runner.hour is not None and w.runner.hour.skipped == {"BUY": "momentum"}
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"]  # only the SELL candidate (setup 1)
    w.step(300, 101.2)  # the skipped BUY line is visited: nothing changes
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"] and w.runner.hour.chosen is None
    w.step(300, 108.9)  # the SELL candidate's own visit
    assert w.runner.hour.chosen is not None and w.runner.hour.chosen.side == "SELL"


def test_both_filled_before_one_was_removed_closes_the_later(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.bid(101.0)
    w.fake.orders_get()  # the BUY P1 fills at the broker before the runner looks
    w.bid(109.0)
    w.fake.orders_get()  # and the SELL P1
    assert len(w.positions()) == 2
    w.step(2)
    assert w.runner.hour is not None and w.runner.hour.chosen is cands(w)["BUY"]
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]  # the later deal's position is closed at market
    w.step(2)
    assert not any(o.comment.startswith("Z2") for o in w.orders())
    assert "P1" in cands(w)["BUY"].fills and w.store.setup(2).state == "dropped"


def test_a_marketable_order_is_a_market_order_and_fills_at_p_in_the_logic(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, fake_bid=100.9)  # the ask 101.1 is already through the BUY P1 101.32
    w.step(2)
    w.step(2)
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]
    req = requests(w, "place")[0]
    assert req.market is True and req.comment == "Z1-P1-0"
    fill = cands(w)["BUY"].fills["P1"]
    assert fill.price == pytest.approx(101.31578947)  # the logic price P1
    assert fill.broker_price == pytest.approx(w.positions()[0].price_open) and fill.broker_price < 101.32
    assert "Z1-P2-0" in w.names()  # P2 rests once P1 is filled


# --- the setup's life -----------------------------------------------------------------------------------------------


def test_the_closed_hour_cancel_comes_before_any_visit(worlds: list[World], tmp_path: Path) -> None:
    # the hour before fell from 103 to 101.5 (a body of 1.5 toward BUY, under the median range 2): the BUY setup
    # is cancelled at the first bar j0 of the hour, though the line was never visited
    rows129 = hour_rows(
        bar(103, 104, 102, 103), bar(103, 104, 102, 103), bar(103, 104, 102, 103), bar(103, 103, 101.5, 101.5)
    )
    params = ZoneParams(cancel_frac=0.12)  # c = 1.2
    w = world(worlds, tmp_path, exec_rows={129: rows129}, params=params)
    w.step(2)
    assert w.names() == []  # not placed: the cancel holds at the open
    w.to("2025-01-06 10:15:02")  # bar j0 closed
    buy = w.store.setup(1)
    assert (buy.state, buy.outcome, buy.chosen) == ("ended", "cancel", False)
    assert w.store.last_reservation_end() is None  # never visited: no reservation


def test_a_blocked_p1_touched_on_the_bid_but_not_the_ask_does_not_cancel(
    worlds: list[World], tmp_path: Path
) -> None:
    # c = 1.2: BUY P1 101.32 is blocked at 103 (101.32 - 103 = -1.68 -> 1.68 >= 1.2); the bar's low 101.2 is on the
    # bid only (the ask low is 101.4 > P1): the simulation does not cancel
    params = ZoneParams(cancel_frac=0.12)
    rows = hour_rows(bar(103, 104, 101.2, 103))
    w = world(worlds, tmp_path, exec_rows={130: rows}, params=params)
    w.step(2)
    assert w.names() == []  # blocked: removed / not placed
    w.step(300, 101.2)
    w.to("2025-01-06 10:15:02", 103)
    assert w.store.setup(1).state == "live" and w.store.setup(1).outcome is None


def test_p2_rests_with_p1_when_only_its_own_price_would_be_blocked(
    worlds: list[World], tmp_path: Path
) -> None:
    # c = 3.33: P1 101.32 is open (1.68 < 3.33), P2 98.03 is 4.97 away. L5 rule 3: the block is P1's alone and
    # removes both; P2 has none of its own - so with P1 free both rest, and P2 stays after P1 fills.
    w = world(worlds, tmp_path, params=ZoneParams())
    w.step(2)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"]
    w.step(60, 101.0)  # the BUY P1 fills
    w.step(2)
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]
    assert "Z1-P2-0" in w.names()


def test_the_break_even_once_p2_removed_ahead(worlds: list[World], tmp_path: Path) -> None:
    rows = hour_rows(bar(103, 105.9, 101.0, 105.8))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(60, 101.0)
    w.step(2)  # P1 filled at 101.32; the SELL candidate dropped
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"] and "Z1-P2-0" in w.names()
    # mid = 101.3158 + 0.5 * (110 - 101.3158) = 105.6579: the BUY trigger is certain the moment the bid reaches it
    w.step(60, 105.7)
    assert "Z1-P2-0" not in w.names()  # P2 removed ahead of the bar's close (BUY only)
    assert w.positions()[0].sl == 95.0  # the SL move itself waits for the close
    w.to("2025-01-06 10:15:02", 105.7)
    buy = cands(w)["BUY"]
    assert buy.be_on and buy.be_sl == pytest.approx(101.3158 + 0.2, abs=1e-3) and buy.be_sent == 101.52
    assert w.positions()[0].sl == 101.52
    assert len(requests(w, "stops")) == 1
    w.step(30, 105.7)
    w.to("2025-01-06 10:30:02", 105.7)
    assert len(requests(w, "stops")) == 1  # the break-even goes on once


def test_the_break_even_moves_the_sl_of_both_open_positions(worlds: list[World], tmp_path: Path) -> None:
    rows = hour_rows(bar(103, 105.9, 97.5, 105.8))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(60, 101.0)  # P1 fills
    w.step(60, 97.5)  # P2 fills (the ask is under 98.03)
    w.step(2)
    assert sorted(p.comment for p in w.positions()) == ["Z1-P1-0", "Z1-P2-0"]
    w.step(60, 105.0)
    w.to("2025-01-06 10:15:02", 105.0)
    buy = cands(w)["BUY"]
    avg = (101.31578947 + 98.02631579) / 2  # the mean of the setup's logic fill prices
    assert buy.be_on and buy.be_sl == pytest.approx(avg + 0.2, abs=1e-3)
    assert {p.sl for p in w.positions()} == {99.88}  # both positions, the tick toward the TP
    assert len(requests(w, "stops")) == 2


def test_a_be_with_the_price_already_beyond_closes_at_market_and_exits_be_at_the_stop(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 105.9, 100.9, 100.95))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(60, 101.0)
    w.step(60, 105.7)  # the trigger is certain
    w.step(60, 100.95)  # and the price falls back under the BE stop before the bar closes
    w.to("2025-01-06 10:15:02", 100.95)
    w.step(2, 100.95)
    assert w.positions() == []  # closed at market (the modify would have been refused: beyond the stop)
    buy = w.store.setup(1)
    assert (buy.state, buy.outcome, buy.exit_how) == ("ended", "traded", "BE")
    assert buy.exit_price == pytest.approx(101.5158, abs=1e-3)  # the BE stop, in the setup's logic
    assert buy.exit_broker_price == pytest.approx(100.95, abs=0.05)  # the broker's price beside it
    assert not w.orders()  # the leftover P2 is gone


def test_the_leftover_p2_goes_when_the_last_position_closes_and_the_reservation_is_the_bars_close(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 110.5, 101.0, 110.5))
    w = world(worlds, tmp_path, exec_rows={130: rows}, params=ZoneParams(cancel_frac=0.9, be_mode="off"))
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    assert "Z1-P2-0" in w.names() and len(w.positions()) == 1
    w.step(600, 110.2)  # 10:12:07 -> through the TP 110: the broker closes the position
    w.step(2, 110.2)
    assert w.positions() == [] and w.orders() == []  # an unfilled P2 never outlives its setup
    w.to("2025-01-06 10:15:02", 110.2)  # the outcome once the first fill's bar is judged on its close (L5)
    row = w.store.setup(1)
    assert (row.outcome, row.exit_how) == ("traded", "TP")
    # the exit was inside the bar 10:00-10:15 (its first cycle after the exit): the reservation is that bar's close
    assert row.end_close_time == ts("2025-01-06 10:15").to_pydatetime()


def test_an_exit_in_the_last_bar_of_an_hour_reserves_the_next_hour(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 104, 101.0, 101.5), FILL, FILL, bar(101.5, 110.5, 101.4, 110.5))
    w = world(worlds, tmp_path, exec_rows={130: rows}, params=ZoneParams(cancel_frac=0.9, be_mode="off"))
    w.step(2)
    w.step(60, 101.0)
    w.to("2025-01-06 10:50:00", 101.4)
    w.step(120, 110.2)  # the TP at 10:52 inside the bar 10:45-11:00
    w.to("2025-01-06 11:00:03", 103)  # the hour 131 opens at 11:00: its open is <= the reservation end 11:00
    assert w.store.setup(1).end_close_time == ts("2025-01-06 11:00").to_pydatetime()
    assert w.runner.hour is not None and w.runner.hour.open == ts("2025-01-06 11:00")
    assert w.runner.hour.reserved is True and w.runner.hour.skipped == {"BUY": "busy", "SELL": "busy"}
    assert w.orders() == []
    w.to("2025-01-06 12:00:03", 103)  # the next hour is free again
    assert w.runner.hour.reserved is False


def test_a_friday_exit_does_not_block_mondays_open(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.runner.res_end = ts("2025-01-10 21:00")  # the close of the Friday bar the exit was in
    assert w.runner._reserved(ts("2025-01-10 21:00")) and not w.runner._reserved(ts("2025-01-13 00:00"))


def test_the_expiry_bar_itself_ends_the_reservation(worlds: list[World], tmp_path: Path) -> None:
    # order_life_h = 1: the setup expires at the bar j0 + 4 (11:00); it was visited (no fill), so it reserves
    params = ZoneParams(cancel_frac=0.9, order_life_h=1)
    w = world(worlds, tmp_path, params=params)
    w.step(2)
    w.step(300, 101.2)
    w.to("2025-01-06 10:55:00", 101.2)
    w.to("2025-01-06 11:00:03", 101.2)  # bar 524 opens: expiry, the orders are removed at its open
    assert "Z1" not in "".join(w.names())
    w.to("2025-01-06 11:15:03", 101.2)
    row = w.store.setup(1)
    assert (row.outcome, row.state, row.chosen) == ("no fill", "ended", True)
    assert row.end_close_time == ts("2025-01-06 11:15").to_pydatetime()


def test_a_missed_touch_is_found_at_the_bars_close(worlds: list[World], tmp_path: Path) -> None:
    # the second bar's low touched Z of the BUY line between two cycles
    rows = hour_rows(FILL, bar(103, 104, 100.9, 103))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.to("2025-01-06 10:20:00", 103)
    assert w.runner.hour is not None and w.runner.hour.chosen is None
    w.to("2025-01-06 10:30:02", 103)
    assert w.runner.hour.chosen is cands(w)["BUY"]
    assert w.store.setup(1).chosen is True and w.store.setup(2).state == "dropped"


def test_no_missed_touch_is_looked_for_in_the_bar_of_the_decision(
    worlds: list[World], tmp_path: Path
) -> None:
    # L4: the decision bar's extremes may come from before the decision - its low within Z is no visit
    rows = hour_rows(bar(103, 104, 100.9, 103))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(300, 103)
    w.to("2025-01-06 10:15:02", 103)
    assert w.runner.hour is not None and w.runner.hour.chosen is None
    assert w.store.setup(1).chosen is False


# --- the pre-close window -----------------------------------------------------------------------------------------


def test_the_pre_close_window_removes_what_the_coming_bar_would_and_places_it_again(
    worlds: list[World], tmp_path: Path
) -> None:
    # the opens of the hour before: 103, 105, 103, 103. Bar 520 sees open[516] = 103 (P1 open: 1.68 < 3.33); the
    # coming bar 521 sees open[517] = 105 (3.68 >= 3.33: blocked); bar 522 sees open[518] = 103 again.
    rows129 = [
        bar(103, 104, 102, 103),
        bar(105, 106, 104, 105),
        bar(103, 104, 102, 103),
        bar(103, 104, 102, 103),
    ]
    w = world(worlds, tmp_path, exec_rows={129: rows129}, params=ZoneParams())
    w.step(2)
    assert w.names() == [
        "Z1-P1-0",
        "Z1-P2-0",
    ]  # P1's block alone decides (L5 rule 3): P1 is free, so both rest
    w.to("2025-01-06 10:14:40", 103)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"]  # outside the window
    w.to(
        "2025-01-06 10:14:50", 103
    )  # the last 15 seconds of the bar: the coming bar blocks P1 - and with it P2
    assert w.names() == []
    w.to("2025-01-06 10:15:02", 103)  # the bar 521 has opened: the true values agree, still blocked
    assert w.names() == []
    w.to("2025-01-06 10:29:50", 103)
    assert w.names() == []
    w.to("2025-01-06 10:30:02", 103)  # the bar 522 sees open[518] = 103: allowed again, new comments
    assert w.names() == ["Z1-P1-1", "Z1-P2-1"]


def test_the_pre_close_window_judges_the_closed_hour_cancel_with_the_bid_as_the_coming_close(
    worlds: list[World], tmp_path: Path
) -> None:
    from app.zone.trader import Ctx

    w = world(worlds, tmp_path, params=ZoneParams())
    w.step(2)
    cand = cands(w)["BUY"]
    ex = w.runner._exec()
    now = w.runner.now()
    quiet = Ctx(now, tick=SimpleNamespace(bid=103.0), n=len(ex), ex=ex, ahead=True)  # type: ignore[arg-type]
    assert w.runner._before_fill_ok(cand, "P1", quiet)
    # open[517] = 103: a bid of 99.5 as the coming close is a fall of 3.5 >= 3.33: the cancel is expected
    falling = Ctx(now, tick=SimpleNamespace(bid=99.5), n=len(ex), ex=ex, ahead=True)  # type: ignore[arg-type]
    assert not w.runner._before_fill_ok(cand, "P1", falling)
    not_ahead = Ctx(now, tick=SimpleNamespace(bid=99.5), n=len(ex), ex=ex, ahead=False)  # type: ignore[arg-type]
    assert w.runner._before_fill_ok(cand, "P1", not_ahead)  # the same bid is no reason outside the window


# --- the bars ---------------------------------------------------------------------------------------------------


def test_the_m15_frame_is_kept_fresh_with_exec_m5(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path, exec_tf="M5")
    w.step(2)
    assert w.runner.live.tfs == ("D1", "H4", "H1", "M15", "M5")
    w.to("2025-01-06 10:16:00", 103)
    assert w.runner.live.last_open("M15") == w.src.last_closed_open("M15") == ts("2025-01-06 10:00")
    assert w.runner.live.last_open("M5") == w.src.last_closed_open("M5") == ts("2025-01-06 10:10")


# --- write-ahead and unknown outcomes ---------------------------------------------------------------------------------


class FlakyExecution:
    """The real ExecutionGateway with the answers a test chooses."""

    def __init__(self, inner: ExecutionGateway) -> None:
        self.inner = inner
        self.refuse: dict[str, int] = {}  # comment -> retcode
        self.refuse_remove = 0
        self.no_reply_executed: set[str] = set()  # comments: executed, the answer lost
        self.no_reply_lost: set[str] = set()  # comments: not executed, no answer
        self.crash_on: set[str] = set()
        self.crash_next = False  # the next send dies (after its intent row committed, before the send)
        self.unknown_code: dict[str, int] = {}  # comment -> a UNKNOWN-class retcode returned after executing
        self.refuse_stops = 0
        self.partial_close = 0  # the next N closes answer DONE_PARTIAL without closing
        self.sent: list[dict[str, Any]] = []

    def check(self, request: dict[str, Any]) -> CheckResult:
        return self.inner.check(request)

    def send(self, request: dict[str, Any]) -> SendResult:
        self.sent.append(dict(request))
        comment = str(request.get("comment", ""))
        if self.crash_next:
            self.crash_next = False
            raise SystemExit("the process died before the send")
        if comment in self.crash_on:
            raise SystemExit("the process died")
        if comment in self.refuse:
            code = self.refuse[comment]
            return SendResult(code, classify(code), describe(code))
        if request.get("action") == c.TRADE_ACTION_REMOVE and self.refuse_remove > 0:
            self.refuse_remove -= 1
            return SendResult(10013, classify(10013), describe(10013))
        if (
            request.get("action") == c.TRADE_ACTION_DEAL
            and request.get("position")
            and self.partial_close > 0
        ):
            self.partial_close -= 1
            return SendResult(10010, classify(10010), describe(10010))
        if request.get("action") == c.TRADE_ACTION_SLTP and self.refuse_stops > 0:
            self.refuse_stops -= 1
            return SendResult(10016, classify(10016), describe(10016))
        if comment in self.no_reply_lost:
            return SendResult(None, classify(None), describe(None))
        res = self.inner.send(request)
        if comment in self.unknown_code:
            code = self.unknown_code[comment]
            return SendResult(code, classify(code), describe(code))
        if comment in self.no_reply_executed:
            return SendResult(None, classify(None), describe(None))
        return res


def flaky(w: World) -> FlakyExecution:
    f = FlakyExecution(w.runner.exe)  # type: ignore[arg-type]
    w.runner.exe = f
    return f


def test_a_crash_before_the_send_leaves_an_intent_that_is_never_sent_again(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.crash_on.add("Z1-P1-0")
    w.runner.start()
    with pytest.raises(SystemExit):
        w.step(2)  # the 10:00 decision places; the process dies before the send
    [row] = [r for r in requests(w, "place") if r.comment == "Z1-P1-0"]
    assert row.state == "intent" and w.names() == []
    w2 = restart(w, worlds)  # L8: the previous run's rows end `restart`, its requests are closed (moot)
    w2.step(2)
    assert w2.names() == [] and not any(r.comment == "Z1-P1-1" for r in requests(w2, "place"))
    assert [r.state for r in requests(w2, "place") if r.comment == "Z1-P1-0"] == ["moot"]
    assert w2.runner.cands == {} and w2.runner.hands_off is None  # flat: the next decision is at 11:00
    assert {r.outcome for r in w2.store.setups()} == {"restart"}


def test_an_accepted_order_whose_answer_was_lost_is_found_by_its_comment(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    f.no_reply_executed.add("Z1-P1-0")
    w.step(2)
    assert "Z1-P1-0" in w.names()
    assert requests(w, "place")[0].state in ("unknown", "sent")
    w.step(2)
    w.step(2)
    row = [r for r in requests(w, "place") if r.comment == "Z1-P1-0"]
    assert len(row) == 1 and row[0].state == "sent" and row[0].order_ticket is not None
    assert w.names().count("Z1-P1-0") == 1  # never a duplicate


def test_an_accepted_order_visible_only_after_several_cycles_is_never_duplicated(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    hidden = {"n": 3}
    real_orders = w.runner.gw.orders

    def late_orders(symbol: str | None = None) -> list[Any]:
        out = real_orders(symbol)
        if hidden["n"] > 0:
            hidden["n"] -= 1
            return [o for o in out if o.comment != "Z1-P1-0"]
        return out

    w.runner.gw.orders = late_orders  # type: ignore[method-assign]
    for _ in range(5):
        w.step(2)
    assert w.names().count("Z1-P1-0") == 1 and "Z1-P1-1" not in w.names()
    assert [r.state for r in requests(w, "place") if r.name == "P1" and r.setup_id == 1] == ["sent"]


def test_a_remove_with_an_unknown_outcome_is_judged_by_the_ticket(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    f = flaky(w)
    real_send = f.inner.send

    def lose_first_remove(request: dict[str, Any]) -> SendResult:
        res = real_send(request)
        if request.get("action") == c.TRADE_ACTION_REMOVE and not getattr(lose_first_remove, "done", False):
            lose_first_remove.done = True  # type: ignore[attr-defined]
            return SendResult(None, classify(None), describe(None))
        return res

    f.inner.send = lose_first_remove  # type: ignore[method-assign]
    w.kill.activate("test", "t", "test")  # the kill switch: every resting entry is removed
    w.step(2)
    w.step(2)
    assert w.orders() == []
    removes = requests(w, "remove")
    assert (
        sorted(r.state for r in removes).count("sent") == 4
    )  # the executed one was judged by the ticket: done (``sent``, closed)
    assert sum(1 for r in f.sent if r.get("action") == c.TRADE_ACTION_REMOVE) == 4  # not sent again


def test_a_modify_not_executed_is_judged_by_the_expiry_and_sent_again(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(300, 101.2)  # BUY chosen, it lives on past the hour
    f = flaky(w)
    real_send = f.inner.send
    lost = {"n": 1}

    def lose_modify(request: dict[str, Any]) -> SendResult:
        if request.get("action") == c.TRADE_ACTION_MODIFY and lost["n"] > 0:
            lost["n"] -= 1
            return SendResult(None, classify(None), describe(None))
        return real_send(request)

    f.inner.send = lose_modify  # type: ignore[method-assign]
    w.to("2025-01-06 10:51:00", 101.2)  # 10 minutes before the expiry 11:01: extend
    w.step(2)
    want = w.bundle.gateway.server_clock.utc_to_server_epoch(ts("2025-01-06 12:01").to_pydatetime())
    assert {o.time_expiration for o in w.orders()} == {want}
    assert {r.state for r in requests(w, "modify")} == {"sent"}  # judged done by the expiry


def test_the_broker_expiry_is_set_and_extended_each_hour(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(300, 101.2)
    clock = w.bundle.gateway.server_clock
    exp = lambda hh: clock.utc_to_server_epoch(ts(f"2025-01-06 {hh}").to_pydatetime())  # noqa: E731
    assert {o.time_expiration for o in w.orders()} == {exp("11:01")}
    w.to("2025-01-06 10:40:00", 101.2)
    assert {o.time_expiration for o in w.orders()} == {exp("11:01")}  # not yet 10 minutes before
    w.to("2025-01-06 10:51:00", 101.2)
    assert {o.time_expiration for o in w.orders()} == {exp("12:01")}
    w.to("2025-01-06 10:52:00", 101.2)
    assert len([r for r in requests(w, "modify")]) == 2  # one modify per order, once an hour


# --- refusals -----------------------------------------------------------------------------------------------------------


def test_p1_refused_drops_the_candidate_and_p2_never_rests_alone(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.refuse["Z1-P1-0"] = 10015
    w.runner.start()
    w.step(2)  # the 10:00 decision
    w.step(2)
    assert not any(o.comment.startswith("Z1") for o in w.orders())
    assert w.store.setup(1).state == "dropped" and w.store.setup(1).outcome == "dropped"
    assert "refused" in w.store.setup(1).note
    assert [o.comment for o in w.orders()] == ["Z2-P1-0", "Z2-P2-0"]  # the other candidate is untouched
    assert not any(r.comment == "Z1-P2-0" for r in requests(w, "place"))


def test_p2_refused_is_retried_then_the_setup_goes_on_with_p1(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    for n in range(3):
        f.refuse[f"Z1-P2-{n}"] = 10015
    w.runner.start()
    for _ in range(6):
        w.step(2)
    assert "Z1-P1-0" in w.names() and not any(o.comment.startswith("Z1-P2") for o in w.orders())
    refused = [r for r in requests(w, "place") if r.name == "P2" and r.setup_id == 1]
    assert [r.state for r in refused] == ["refused"] * 3  # retried each cycle, three refusals
    assert cands(w)["BUY"].p2_off and not cands(w)["BUY"].dropped


def test_a_remove_refused_while_the_order_fills_closes_the_fill(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(300, 101.2)  # the BUY candidate is the hour's setup (chosen), SELL dropped
    f = flaky(w)
    f.refuse_remove = 100
    w.kill.activate("test", "t", "test")
    w.step(2)
    assert len(w.orders()) == 2  # the removals were refused
    assert w.store.setup(1).outcome == "interrupted"  # L7: a setup without a fill ends interrupted
    w.bid(101.0)  # and the BUY P1 fills meanwhile
    w.step(2)
    assert w.positions() == []  # a fill after the setup's end is closed at market (L5)
    assert "P1" not in cands(w)["BUY"].fills and cands(w)["BUY"].faults
    assert w.store.last_reservation_end() is None  # interrupted: no reservation


def test_a_partial_fill_is_hands_off(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    order = next(o for o in w.fake.orders if o.comment == "Z1-P1-0")
    order.volume_current = 0.005  # half of it filled: the other half still rests
    w.fake.positions.append(
        SimpleNamespace(
            ticket=order.ticket,
            symbol="XAUUSD",
            type=c.POSITION_TYPE_BUY,
            volume=0.005,
            price_open=101.32,
            sl=95.0,
            tp=110.0,
            price_current=101.0,
            profit=0.0,
            swap=0.0,
            magic=MAGIC,
            comment="Z1-P1-0",
            time=w.bundle.gateway.server_clock.utc_to_server_epoch(w.clock.now_utc()),
            identifier=order.ticket,
            margin=1.0,
        )
    )
    w.step(2, 101.0)
    assert w.runner.hands_off is not None and "not 0.01" in w.runner.hands_off  # L8 cause 5
    w.step(2, 101.0)
    assert w.orders() == []  # every order of the magic removed
    assert requests(w, "close") == [] and requests(w, "stops") == []  # no position is touched
    assert {p.sl for p in w.positions()} == {95.0}
    assert {r.outcome for r in w.store.setups()} == {"hands-off"}


# --- restart ------------------------------------------------------------------------------------------------------------


def test_an_order_and_a_position_of_the_magic_not_ours_are_hands_off(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.fake.orders.append(
        SimpleNamespace(
            ticket=9_001,
            time_setup=0,
            type=c.ORDER_TYPE_BUY_LIMIT,
            state=1,
            volume_initial=0.01,
            volume_current=0.01,
            price_open=90.0,
            sl=85.0,
            tp=95.0,
            price_current=0.0,
            symbol="XAUUSD",
            magic=MAGIC,
            comment="junk",
            type_time=0,
            time_expiration=0,
            type_filling=2,
        )
    )
    w.fake.positions.append(
        SimpleNamespace(
            ticket=9_002,
            symbol="XAUUSD",
            type=c.POSITION_TYPE_SELL,
            volume=0.01,
            price_open=120.0,
            sl=125.0,
            tp=0.0,
            price_current=120.0,
            profit=0.0,
            swap=0.0,
            magic=MAGIC,
            comment="Z99-P1-0",
            time=0,
            identifier=9_002,
            margin=1.0,
        )
    )
    w.step(2)
    assert w.runner.hands_off is not None and "not ours" in w.runner.hands_off
    w.step(2)
    assert w.orders() == []  # every order of the magic removed, ours and not ours
    assert [p.ticket for p in w.positions() if p.magic == MAGIC] == [9_002]  # never closed
    status = json.loads(w.store.get_state("status") or "{}")
    assert status["hands_off"] and "9001" in status["not_ours_orders"]


def test_another_accounts_row_is_not_ours(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    rows = w.store.setups()
    assert rows and all(r.account_server == "FBS-Demo" for r in rows)
    other = dataclasses.replace(w, runner=w.runner)
    other.store.login = LOGIN + 1
    assert other.store.setups() == []  # the rows of another login are not read


def test_an_account_switch_stops_everything_until_a_restart(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    sent = len(w.fake.desk.requests)
    w.fake.account.login = LOGIN + 5
    w.kill.activate("test", "t", "test")  # even a removal would be a touch from another account
    w.step(2)
    w.step(2)
    assert w.runner.account_switched and len(w.fake.desk.requests) == sent
    assert len(w.orders()) == 4


# --- the gate, the modes, the kill switch, the data ---------------------------------------------------------------


def test_live_without_the_two_env_values_is_refused(worlds: list[World], tmp_path: Path) -> None:
    with pytest.raises(SafetyViolation, match="ENABLE_LIVE_TRADING"):
        make_world(tmp_path, mode="LIVE")
    with pytest.raises(SafetyViolation, match="LIVE_TRADING_CONFIRMATION"):
        make_world(tmp_path, mode="LIVE", ENABLE_LIVE_TRADING="true")


def test_live_with_the_two_values_trades_without_a_day_plan(worlds: list[World], tmp_path: Path) -> None:
    w = world(
        worlds,
        tmp_path,
        mode="LIVE",
        ENABLE_LIVE_TRADING="true",
        LIVE_TRADING_CONFIRMATION=f"I-ACCEPT-LIVE-RISK-{LOGIN}",
    )
    w.step(2)
    assert len(w.names()) == 4  # the gate passes with no day plan: the zone runner does not use it
    assert w.runner.last_gate == (True, "")


def test_paper_and_backtest_refuse_to_start(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path, start=False)
    for mode in (TradingMode.PAPER, TradingMode.BACKTEST):
        runner = ZoneRunner(
            cfg=dataclasses.replace(w.runner.cfg, mode=mode),
            params=w.params,
            clock=w.clock,
            gateway=w.runner.gw,
            execution=w.runner.exe,
            bar_source=w.src,
            db=w.db,
            bars=w.runner.live.bars(),
            kill_switch=w.kill,
            magic=MAGIC,
        )
        with pytest.raises(ZoneStartError, match="DEMO or LIVE"):
            runner.start()


def test_the_gate_is_evaluated_fresh_before_each_order(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path, start=False)
    calls = {"n": 0}
    real = w.runner.gw.terminal

    def terminal() -> Any:
        calls["n"] += 1
        return real()

    w.runner.gw.terminal = terminal  # type: ignore[method-assign]
    w.runner.start()
    calls["n"] = 0
    w.step(2)  # the 10:00 decision places the four orders
    assert calls["n"] >= 1 + 4  # the cycle's evaluation and one before each of the four orders
    w.fake.terminal.trade_allowed = False  # Algo Trading switched off at the terminal
    w.step(2)
    assert (
        w.runner.last_gate[0] is False
    )  # the gate failed: no order, and the resting entries are being removed
    assert [r.state for r in requests(w, "remove")] != [] and len(requests(w, "place")) == 4


def test_the_kill_switch_removes_entries_and_places_nothing_but_positions_are_managed(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 105.9, 101.0, 105.8))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    assert len(w.positions()) == 1
    w.kill.activate("test", "t", "test")
    w.step(60, 105.7)  # the break-even trigger (BUY: certain at the high so far)
    assert w.orders() == []  # every resting entry removed
    w.to("2025-01-06 10:15:02", 105.7)
    assert w.positions()[0].sl == 101.52  # and the position is still managed: the break-even modify
    w.to("2025-01-06 11:00:03", 103)
    assert w.orders() == []  # nothing new, even at the next hour


def test_a_lost_connection_places_nothing_and_resumes(worlds: list[World], tmp_path: Path) -> None:
    # a first start in the middle of the previous hour waits for the 10:00 open (L8): the orders come after it
    w = world(worlds, tmp_path, now="2025-01-06 09:59:50")
    w.fake.disconnect()
    w.to("2025-01-06 10:00:05")
    w.step(2)
    assert w.orders() == [] and len(w.fake.desk.requests) == 0
    w.fake.reconnect()
    w.step(2)
    assert len(w.names()) == 4 and len(set(w.names())) == 4  # placed once the connection is back
    w.fake.disconnect()
    w.step(2)
    w.fake.reconnect()
    w.step(2)
    assert len(w.names()) == 4 and len(requests(w, "place")) == 4  # and none twice


def test_stale_data_places_nothing_and_after_a_bar_removes_the_entries(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    assert len(w.names()) == 4
    w.src.fail = True  # the bars cannot be read: not fresh
    w.step(60)
    assert len(w.names()) == 4  # a short staleness keeps the resting orders
    w.step(960)  # more than one M15 bar later
    assert w.orders() == []


def test_a_second_runner_is_refused(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    second = ProcessLock(tmp_path / "runner.lock")
    with pytest.raises(ZoneStartError, match="another zone runner"):
        second.acquire()
    del w


def test_zone_stop_is_acknowledged_and_nothing_is_placed_after_it(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    assert len(w.names()) == 4
    sid = w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    assert w.orders() == []
    w.step(2)
    row = w.store.stop(sid)
    assert row is not None and row.acknowledged_at is not None
    assert w.runner.finished  # no position was open: the runner exits
    assert not any(r.state == "intent" for r in requests(w))


def test_zone_stop_keeps_managing_a_position_until_it_is_flat(worlds: list[World], tmp_path: Path) -> None:
    rows = hour_rows(bar(103, 105.9, 101.0, 105.8))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    sid = w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(2)
    assert w.orders() == [] and len(w.positions()) == 1
    assert w.store.stop(sid).acknowledged_at is not None and not w.runner.finished  # type: ignore[union-attr]
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)
    assert w.positions()[0].sl == 101.52  # the break-even still works


# --- independence (L11.4) ---------------------------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return out


def test_app_zone_imports_nothing_from_eye_or_the_fibonacci_bot_or_the_strategy_engine() -> None:
    forbidden = (
        "eye",
        "bot2e",
        "bot_config",
        "bot_research",
        "app.engine.orchestrator",
        "app.engine.decision_engine",
        "app.strategy",
    )
    for path in sorted((ROOT / "app" / "zone").glob("*.py")):
        for name in _imports(path):
            assert not any(name == f or name.startswith(f + ".") for f in forbidden), (
                f"{path.name} imports {name}"
            )
    trader = _imports(ROOT / "app" / "zone" / "trader.py")
    assert not any("checklist" in n or "arbitration" in n for n in trader)
    core = _imports(ROOT / "app" / "zone" / "core.py") | _imports(ROOT / "app" / "zone" / "live.py")
    assert not any(n.startswith(("app.broker", "app.storage", "app.risk", "app.engine")) for n in core)


def test_pandas_is_the_only_time_type_the_tests_rely_on() -> None:
    assert pd.Timestamp("2025-01-06 10:00", tz="UTC") == ts("2025-01-06 10:00")


def test_the_visit_records_agree_with_what_the_runner_did_and_the_arming_follows_the_bar(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 104, 101.2, 101.2), bar(101.2, 102, 101.2, 102), FILL, FILL)
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(300, 101.2)  # the BUY visit, the BUY candidate is the hour's setup
    w.to("2025-01-06 11:00:03", 103)  # the H1 bar 130 has closed
    records = w.store.visits(ts("2025-01-06 10:00").to_pydatetime())
    assert [(r.side, r.line, r.classification, r.agreed, r.setup_id) for r in records] == [
        ("BUY", 100.0, "setup", True, 1)
    ]
    assert (
        w.runner.armed[(100.0, 10.0, 100.0)] is False
    )  # the visited line is disarmed, ordered or not, live or not
    assert w.runner.hour is not None and w.runner.hour.reserved  # the setup still lives: the hour 131 is busy
    assert w.runner.hour.skipped == {"BUY": "busy", "SELL": "busy"}


def test_a_line_visited_while_the_hour_was_skipped_is_still_disarmed(
    worlds: list[World], tmp_path: Path
) -> None:
    rows129 = [
        bar(103.5, 103.6, 102.0, 102.5),
        bar(102.5, 102.6, 101.8, 102.0),
        bar(102.0, 102.2, 101.6, 101.8),
        bar(101.8, 102.0, 101.5, 101.5),
    ]
    rows = hour_rows(bar(101.5, 104, 101.0, 103), FILL, FILL, FILL)  # the skipped BUY line is touched
    w = world(worlds, tmp_path, exec_rows={129: rows129, 130: rows})
    w.step(2)
    assert w.runner.hour is not None and w.runner.hour.skipped == {"BUY": "momentum"}
    w.to("2025-01-06 11:00:03", 103)
    assert w.runner.armed[(100.0, 10.0, 100.0)] is False
    assert [(r.side, r.classification) for r in w.store.visits()] == [("BUY", "momentum")]


def test_the_sell_break_even_is_judged_at_the_close_and_its_stop_rounds_toward_the_tp(
    worlds: list[World], tmp_path: Path
) -> None:
    # SELL P1 108.68 fills; mid = 108.6842 + 0.5 * (100 - 108.6842) = 104.3421; the trigger reads the bar's low
    # plus its spread (0.20) and so is known only at the close: P2 goes at the close, not ahead
    rows = hour_rows(bar(103, 108.9, 104.0, 104.1))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(60, 108.9)
    w.step(2)
    assert [p.comment for p in w.positions()] == ["Z2-P1-0"] and "Z2-P2-0" in w.names()
    w.step(60, 104.0)
    assert "Z2-P2-0" in w.names()  # a SELL P2 is not removed ahead
    w.to("2025-01-06 10:15:02", 104.1)
    sell = cands(w)["SELL"]
    assert sell.be_on and sell.be_sent == 108.48  # 108.6842 - 0.20 -> the tick toward the TP (down)
    w.step(2, 104.1)
    assert "Z2-P2-0" not in w.names() and w.positions()[0].sl == 108.48


def test_the_orders_of_a_candidate_not_visited_go_in_the_last_seconds_of_the_hour(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.to("2025-01-06 10:59:40", 103)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"]  # the SELL candidate moved away (rule 1) long before
    w.to("2025-01-06 10:59:50", 103)
    assert w.orders() == []  # L4: the end of the hour
    w.to("2025-01-06 11:00:03", 103)  # the next hour decides again: the same prices under new rows
    assert w.names() == ["Z3-P1-0", "Z3-P2-0", "Z4-P1-0", "Z4-P2-0"]
    assert w.store.setup(1).state == "ended" and w.store.setup(1).outcome == "no fill"


def test_the_command_line_has_run_status_and_stop(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from app.cli.__main__ import build_parser, main

    parser = build_parser()
    assert parser.parse_args(["zone", "stop", "--now"]).now is True
    assert parser.parse_args(["zone", "run", "--set", "x", "--fake"]).fake is True
    env = tmp_path / ".env"
    env.write_text(
        "TRADING_MODE=DEMO\nMT5_LOGIN=12345678\nMT5_PASSWORD=x\nMT5_SERVER=FBS-Demo\nMT5_TERMINAL_PATH=x\n"
        f"ENGINE_DB_URL=sqlite:///{(tmp_path / 'e.db').as_posix()}\n",
        encoding="utf-8",
    )
    assert main(["--env-file", str(env), "zone", "status"]) == 0
    assert "no runner has written a status yet" in capsys.readouterr().out
    assert main(["--env-file", str(env), "zone", "stop", "--wait", "0.2"]) == 2  # nobody reads the request
    assert "not acknowledged" in capsys.readouterr().out


# --- hands-off, cause 6: the triggers of the placing itself (L3, L8) ---------------------------------------------------


def test_a_placement_number_over_999_is_hands_off(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.store.count_places = lambda setup_id, name: 1000  # type: ignore[method-assign]
    w.step(2)  # the 10:00 decision: its first place would be number 1000
    assert w.runner.hands_off is not None and "over 999" in w.runner.hands_off
    assert w.orders() == [] and not requests(w, "place")


def test_a_p1_refused_after_its_candidate_became_the_hours_setup_is_hands_off(
    worlds: list[World], tmp_path: Path
) -> None:
    # the pre-close window removes P1 (the coming bar blocks it) and the bar after places it again - refused
    rows129 = [
        bar(103, 104, 102, 103),
        bar(105, 106, 104, 105),
        bar(103, 104, 102, 103),
        bar(103, 104, 102, 103),
    ]
    w = world(worlds, tmp_path, exec_rows={129: rows129}, params=ZoneParams())
    f = flaky(w)
    f.refuse["Z1-P1-1"] = 10015
    w.step(2)
    w.step(300, 101.2)  # a visit (the ask is above P1): the BUY candidate is the hour's setup
    assert cands(w)["BUY"].chosen
    w.to("2025-01-06 10:14:50", 103)
    w.to("2025-01-06 10:30:02", 103)  # Z1-P1-1 refused
    assert w.runner.hands_off is not None and "P1 refused" in w.runner.hands_off
    assert w.store.setup(1).outcome == "hands-off"


class NoDealMarket:
    """The execution answers a market entry DONE without executing it (no deal ever comes)."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def check(self, request: dict[str, Any]) -> CheckResult:
        return self.inner.check(request)

    def send(self, request: dict[str, Any]) -> SendResult:
        if request.get("action") == c.TRADE_ACTION_DEAL and not request.get("position"):
            return SendResult(10009, classify(10009), describe(10009))
        res: SendResult = self.inner.send(request)
        return res


# (a market entry that gets no deal within one bar -> hands-off: tests/unit/test_zone_review_fixes8.py,
# test_10_a_market_p1_without_a_deal_holds_back_p2_and_is_hands_off_after_a_bar - L7 places nothing beside
# the unconfirmed market P1, so the magic is flat and the hands-off is seen in the log, not in `hands_off`)


# --- L2: the hour's decision counts from the hour's first quote (the reopening after a break) ----------------------


def reopening_at(w: World, first: str) -> None:
    """The market reopens minutes into the H1 bar: until ``first`` the broker's quote is the last one before the
    break (09:55), from ``first`` on the live quote."""
    real = w.runner.gw.tick
    at = ts(first)

    def tick(symbol: str) -> Any:
        t = real(symbol)
        if w.runner.now() < at:
            return dataclasses.replace(t, time_utc=ts("2025-01-06 09:55").to_pydatetime())
        return dataclasses.replace(t, time_utc=w.runner.now().to_pydatetime())

    w.runner.gw.tick = tick  # type: ignore[method-assign]


def cycle_through(w: World, start: str, end: str, bid: float = 103) -> None:
    """The live runner keeps cycling (every ``cycle_seconds``) through the break: one cycle each 2 s from
    ``start`` up to and including ``end``. L2: the hour's first quote is counted from the last read before it."""
    t, stop = ts(start), ts(end)
    while t <= stop:
        w.to(t, bid)
        t += pd.Timedelta(seconds=2)


def test_a_reopening_hour_whose_first_quote_comes_at_05_is_decided(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, start=False)
    reopening_at(w, "2025-01-06 10:05:00")
    w.runner.start()
    cycle_through(w, "2025-01-06 10:00:00", "2025-01-06 10:04:58")
    assert (
        w.names() == [] and w.runner.hour is not None and not w.runner.hour.decided
    )  # no quote of the hour yet
    assert not w.runner.hour.undecided
    cycle_through(
        w, "2025-01-06 10:05:00", "2025-01-06 10:05:02"
    )  # the first quote: the decision within 60 s
    assert w.runner.hour.decided and len(w.names()) == 4
    # the first quote as the runner knows it: the last read before it (10:04:58), not the quote's own stamp
    assert w.runner.hour.first_quote_at is not None and w.runner.hour.first_quote_at >= ts(
        "2025-01-06 10:04:58"
    )


def test_a_reopening_hour_with_placing_blocked_through_60_s_from_its_first_quote_is_undecided(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, start=False)
    reopening_at(w, "2025-01-06 10:05:00")
    w.runner.start()
    cycle_through(w, "2025-01-06 10:00:00", "2025-01-06 10:04:58")
    w.kill.activate("test", "t", "test")  # placing is not allowed from the first quote on
    cycle_through(w, "2025-01-06 10:05:00", "2025-01-06 10:05:40")
    assert w.runner.hour is not None and not w.runner.hour.decided and not w.runner.hour.undecided
    cycle_through(w, "2025-01-06 10:05:42", "2025-01-06 10:06:08")  # past 60 s after the first quote
    w.kill.release("test", "t")
    w.to("2025-01-06 10:06:20", 103)
    assert w.runner.hour.undecided and not w.runner.hour.decided and w.names() == []
    w.to("2025-01-06 11:00:03", 103)  # the next hour (its first quote at its open) decides as usual
    assert w.runner.hour.decided and len(w.names()) == 4
