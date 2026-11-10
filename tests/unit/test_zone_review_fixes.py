"""The runner after Sol's review of piece 2a (eye/ZONE_LIVE.md L1, L3, L4, L6, L7, L8, L10): one test for each fix,
each failing on the code before the fix."""

# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.broker import mt5_constants as c
from app.zone.params import ZoneParams
from tests.unit.test_zone_trader import (
    FILL,
    bar,
    cands,
    flaky,
    hour_rows,
    requests,
    restart,
    world,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import MAGIC, World, ts


def server_now(w: World) -> int:
    return w.bundle.gateway.server_clock.utc_to_server_epoch(w.clock.now_utc())


def out_deal(w: World, position: Any, volume: float, price: float, reason: int, ticket: int) -> None:
    w.fake.add_deal(
        ticket=ticket,
        order=ticket,
        position_id=position.ticket,
        symbol="XAUUSD",
        type=c.DEAL_TYPE_SELL,
        entry=c.DEAL_ENTRY_OUT,
        volume=volume,
        price=price,
        profit=1.0,
        commission=0.0,
        swap=0.0,
        fee=0.0,
        magic=MAGIC,
        comment="[tp]",
        time=server_now(w),
        reason=reason,
    )


# --- 1: an UNKNOWN-class reply is an unknown outcome (L8) ------------------------------------------------------------


def test_a_timeout_reply_is_an_unknown_outcome_and_never_a_second_order(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    f.unknown_code["Z1-P2-0"] = 10012  # TIMEOUT: executed, the answer says nothing sure
    for _ in range(4):
        w.step(2)
    assert [o.comment for o in w.orders() if o.comment.startswith("Z1-P2")] == ["Z1-P2-0"]
    rows = [r for r in requests(w, "place") if r.setup_id == 1 and r.name == "P2"]
    assert (
        len(rows) == 1 and rows[0].state == "sent" and rows[0].order_ticket is not None
    )  # found by its comment


# --- 2: a partial close leaves the position open (L8) ------------------------------------------------------------------


def test_a_partial_exit_deal_does_not_end_the_setup_or_the_required_close(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    [pos] = w.positions()
    out_deal(w, pos, 0.005, 105.0, c.DEAL_REASON_TP, 8_000_001)  # half of it closed: volume stays open
    w.runner.close_wanted[pos.ticket] = "required"
    w.step(2)
    buy = cands(w)["BUY"]
    assert (
        w.positions() == [] and buy.status == "live" and buy.closed == {}
    )  # the close went on; not ended yet
    w.step(2)
    w.to("2025-01-06 10:15:05", 103.0)  # the outcome once the first fill's bar is judged on its close (L5)
    assert cands(w).get("BUY") is None or cands(w)["BUY"].status == "ended"
    assert w.store.setup(1).outcome == "traded"


# --- 3: orders of a setup that is not live are removed at start (L8) --------------------------------------------------------


def test_a_restart_removes_the_orders_of_a_setup_that_is_not_live(
    worlds: list[World], tmp_path: Path
) -> None:
    # the crash came after the bars withdrew the setup (bar 521) and the SELL was dropped, before any removal: the
    # replay derives both facts and the orders of both are removed
    rows = hour_rows(bar(103, 104, 101.2, 101.2), bar(101.2, 105.5, 101.2, 105.0))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(300, 101.2)
    w.clock.set(ts("2025-01-06 10:30:05").to_pydatetime())
    w.bid(103.0)
    w2 = restart(w, worlds)
    w2.step(2)
    assert not [o for o in w2.orders() if o.comment.startswith(("Z1-", "Z2-"))]


# --- 4: another account latches everything (L1) -----------------------------------------------------------------------


def test_a_switched_account_is_latched_and_nothing_is_removed_from_it(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    sent = len(w.fake.desk.requests)
    real = w.runner.gw.account
    calls = {"n": 0}

    def account() -> Any:
        calls["n"] += 1
        a = real()
        return dataclasses.replace(a, login=a.login + 5)  # the cycle's snapshot (the gate's too) sees it

    w.runner.gw.account = account  # type: ignore[method-assign]
    w.kill.activate("test", "t", "test")  # an ordinary failed gate would remove every order
    w.step(2)
    assert w.runner.account_switched and len(w.fake.desk.requests) == sent and len(w.orders()) == 4
    w.runner.gw.account = real  # type: ignore[method-assign]
    w.kill.release("test", "t")
    w.step(2)
    w.step(2)
    assert w.runner.account_switched and len(w.fake.desk.requests) == sent  # switching back changes nothing


# --- 5: the break-even counts only fills on the closed bar or before it ------------------------------------------------------


def test_a_fill_in_the_new_bar_cannot_trigger_the_break_even_of_the_bar_before(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 105.9, 103.0, 103.0))  # bar 520 reached the BE level 105.66
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.to("2025-01-06 10:15:01", 101.0)  # the fill falls in bar 521, seen in the same cycle as bar 520's close
    buy = cands(w)["BUY"]
    assert buy.fills["P1"].j == 521 and buy.be_on is False


# --- 6: a missed touch takes the hour from a chosen setup (L4) -----------------------------------------------------------------


def test_a_missed_touch_takes_the_hour_and_the_other_position_is_closed(
    worlds: list[World], tmp_path: Path
) -> None:
    # the open is 107: the SELL line is nearer (3 against 7). The BUY is chosen by a quote and fills in bar 521; the
    # bar's high 109 shows the SELL touch the quotes missed, in the same bar and nearer the open: it is the first visit
    rows = hour_rows(bar(107, 107.5, 106.5, 107.0), bar(107, 109.0, 101.0, 105.0))
    w = world(worlds, tmp_path, exec_rows={130: rows}, fake_bid=107.0)
    w.step(2)
    w.to("2025-01-06 10:17:00", 101.0)
    w.step(2)
    assert w.runner.hour is not None and w.runner.hour.chosen is cands(w)["BUY"] and len(w.positions()) == 1
    w.to("2025-01-06 10:30:02", 105.0)
    assert w.runner.hour.chosen is not None and w.runner.hour.chosen.side == "SELL"
    assert w.store.setup(1).outcome == "dropped" and w.store.setup(2).chosen is True
    w.step(2)
    assert w.positions() == []  # the BUY position was closed at market


# --- 7: fills the logic does not allow (L8) ----------------------------------------------------------------------------------------


def test_a_fill_after_the_hour_of_an_unvisited_candidate_is_closed(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    f.refuse_remove = 1000  # the end-of-hour removals fail, the BUY P1 stays
    w.step(2)
    w.to("2025-01-06 10:59:50", 103)
    assert "Z1-P1-0" in w.names()
    w.src.fail = True  # the new hour cannot start (no bars): the old hour is all the runner knows
    w.to("2025-01-06 11:00:10", 101.0)  # the price reaches P1 after the hour is over
    # the local bars do not cover that time yet: the position is kept (it has its SL / TP) and judged later
    assert len(w.positions()) == 1 and cands(w)["BUY"].fills == {}
    w.src.fail = False
    w.step(2)
    w.step(2)  # judged at its true bar: after the hour, never visited
    assert w.positions() == [] and w.store.setup(1).chosen is False
    assert json.loads(w.store.setup(1).fills_json)["fills"] == []  # never part of a setup


def test_a_fill_after_the_withdrawal_level_was_reached_is_closed(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    f = flaky(w)
    f.refuse_remove = 1000
    w.step(2)
    w.to("2025-01-06 10:15:05", 105.2)  # bar 521: the high is 5.2 above the BUY line: withdrawn (rule 1)
    assert "Z1-P1-0" in w.names()  # the removal was refused
    w.step(2, 101.0)  # and the order fills
    assert w.positions() == [] and cands(w)["BUY"].fills == {}


# --- 8: Ctrl+C is a stop that keeps managing (L10) ---------------------------------------------------------------------------


def test_ctrl_c_keeps_managing_until_flat(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    assert len(w.positions()) == 1
    calls = {"n": 0}

    def sleeper(seconds: float) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt
        w.clock.advance(seconds)
        if calls["n"] == 16:
            w.bid(110.2)  # the TP, long after ten cycles

    w.runner.run(sleep=sleeper)
    assert calls["n"] >= 16 and w.positions() == [] and w.orders() == []
    assert w.runner.finished and w.store.setup(1).outcome == "traded"


# --- 11: the reservation runs to the bar of the LAST position's exit (L6) ----------------------------------------------------------


def test_the_reservation_ends_at_the_close_of_the_bar_of_the_last_exit(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 104, 97.5, 103))
    w = world(worlds, tmp_path, exec_rows={130: rows}, params=ZoneParams(cancel_frac=0.9, be_mode="off"))
    w.step(2)
    w.step(60, 101.0)
    w.step(60, 97.5)  # both positions open
    w.step(2)
    p1, p2 = sorted(w.positions(), key=lambda p: p.comment)
    w.to("2025-01-06 10:10:00", 103)
    w.fake.positions.remove(p1)
    out_deal(w, p1, 0.01, 110.0, c.DEAL_REASON_TP, 8_000_002)
    w.step(2)
    assert cands(w)["BUY"].status == "live"
    w.to("2025-01-06 10:20:00", 103)  # the next bar
    w.fake.positions.remove(p2)
    out_deal(w, p2, 0.01, 110.0, c.DEAL_REASON_TP, 8_000_003)
    w.step(2)
    row = w.store.setup(1)
    assert row.state == "ended" and row.exit_how == "TP"
    assert row.end_close_time == ts("2025-01-06 10:30").to_pydatetime()  # not 10:15, the first exit's bar


# --- 12: after an interruption an unvisited candidate waits for the next hour (L7) ----------------------------------------------------


def test_after_the_kill_switch_clears_a_candidate_waits_for_the_next_hour(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.kill.activate("test", "t", "test")
    w.step(2)
    assert w.orders() == []
    w.kill.release("test", "t")
    w.step(2)
    w.step(2)
    assert w.orders() == []  # not in the same hour
    w.to("2025-01-06 11:00:03", 103)
    assert len(w.names()) == 4  # the next hour's decision


def test_the_kill_switch_ends_a_chosen_setup_without_a_fill_interrupted(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    w.step(300, 101.2)  # the BUY candidate is the hour's setup
    w.kill.activate("test", "t", "test")
    w.step(2)
    assert w.orders() == []
    assert w.store.setup(1).outcome == "interrupted" and w.runner.res_end is None  # no reservation
    w.kill.release("test", "t")
    w.step(2)
    w.step(2)
    assert w.orders() == []  # it never comes back
    w.to("2025-01-06 11:00:03", 103)
    assert w.runner.hour is not None and not w.runner.hour.reserved and len(w.names()) == 4


# --- 13: P1 refused is dropped, whatever the code (L3) ------------------------------------------------------------------------------------


@pytest.mark.parametrize("code", [10024, 10020])
def test_a_p1_refused_with_a_transient_code_is_dropped_too(
    worlds: list[World], tmp_path: Path, code: int
) -> None:
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.refuse["Z1-P1-0"] = code
    f.refuse["Z1-P1-1"] = code
    w.runner.start()
    w.step(2)
    assert w.store.setup(1).state == "dropped" and w.store.setup(1).outcome == "dropped"
    assert "refused" in w.store.setup(1).note
    assert [r.comment for r in requests(w, "place") if r.setup_id == 1] == ["Z1-P1-0"]  # no retry


# --- 14: --fake never writes the history store -----------------------------------------------------------------------------------------------


def test_zone_run_on_fake_builds_the_runner_without_persisting_bars(tmp_path: Path) -> None:
    from app.cli.zone import build_runner
    from app.config import load_settings
    from app.zone.core import MARKET_DIRS
    from app.zone.params import seed

    if not MARKET_DIRS["XAUUSD"].exists():
        pytest.skip("no stored bars")
    env = tmp_path / ".env"
    env.write_text(
        "TRADING_MODE=DEMO\nMT5_LOGIN=12345678\nMT5_PASSWORD=x\nMT5_SERVER=FBS-Demo\nMT5_TERMINAL_PATH=x\n"
        f"ENABLE_DEMO_TRADING=true\nENGINE_DB_URL=sqlite:///{(tmp_path / 'e.db').as_posix()}\n",
        encoding="utf-8",
    )
    db = tmp_path / "bot_config.db"
    seed(db, "XAUUSD", "default", "test", datetime(2025, 1, 1, tzinfo=UTC))
    settings = load_settings(env_file=str(env))
    args = argparse.Namespace(db=str(db), market="XAUUSD", set="default", fake=True)
    runner = build_runner(settings, args)
    assert runner.persist is None  # only a real DEMO / LIVE connection may write data/history
    assert runner.cfg.mode.value == "DEMO" and runner.cfg.set_version >= 1
    runner.db.dispose()


# --- test gaps ------------------------------------------------------------------------------------------------------------------------------


def test_a_friday_exit_does_not_block_mondays_open_through_the_runner(
    worlds: list[World], tmp_path: Path
) -> None:
    rows = hour_rows(bar(103, 104, 101.0, 101.5), FILL, FILL, bar(101.5, 110.5, 101.4, 110.5))
    w = world(
        worlds,
        tmp_path,
        now="2025-01-10 19:59:58",
        last_hour=300,
        exec_rows={236: rows},
        params=ZoneParams(cancel_frac=0.9, be_mode="off"),
    )
    w.step(2)
    w.step(60, 100.5)  # deep enough that the fake's spread at 20:01 still fills P1 (the ask <= 101.32)
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]
    w.to("2025-01-10 20:50:00", 101.4)
    w.step(120, 110.2)  # the TP at 20:52, inside the last bar before the Friday close
    w.step(2, 110.2)
    assert w.runner.res_end == ts("2025-01-10 21:00")
    w.to("2025-01-13 00:00:05", 103)  # Monday's first hour
    hour = w.runner.hour
    assert hour is not None and hour.open == ts("2025-01-13 00:00")
    assert hour.reserved is False and hour.skipped == {} and set(hour.cands) == {"BUY", "SELL"}


def test_three_refused_break_even_modifies_are_hands_off(worlds: list[World], tmp_path: Path) -> None:
    rows = hour_rows(bar(103, 105.9, 101.0, 105.8))
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(60, 101.0)
    w.step(2)
    f = flaky(w)
    f.refuse_stops = 100
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)  # the break-even is on: the first refused modify
    assert len(w.positions()) == 1 and cands(w)["BUY"].be_on
    w.step(2)  # the second
    w.step(2)  # the third
    w.step(2)  # not in force after 3 tries: hands-off
    assert w.runner.hands_off is not None and "3 tries" in w.runner.hands_off
    w.step(2)
    assert [p.sl for p in w.positions()] == [95.0]  # the broker SL / TP kept, no market close
    stops = requests(w, "stops")
    assert len(stops) == 3 and {r.retcode for r in stops} == {10016}  # each attempt is its own committed row
    assert not any(r.kind == "close" for r in requests(w))
    assert w.store.setup(1).outcome == "hands-off"


def test_a_stale_quote_places_nothing_and_after_a_bar_removes_the_entries(
    worlds: list[World], tmp_path: Path
) -> None:
    w = world(worlds, tmp_path, start=False)
    real = w.runner.gw.tick
    stale = {"on": True}

    def tick(symbol: str) -> Any:
        t = real(symbol)
        return dataclasses.replace(t, time_utc=t.time_utc - timedelta(seconds=60)) if stale["on"] else t

    w.runner.gw.tick = tick  # type: ignore[method-assign]
    w.runner._market_closed = lambda now: False  # type: ignore[method-assign]
    w.runner.start()
    w.step(2)  # 10:00: a stale quote, no decision yet
    assert w.orders() == [] and w.runner.cands == {}
    stale["on"] = False
    w.step(2)  # a cycle that may place, inside the hour's first 60 s: the decision
    assert len(w.names()) == 4
    stale["on"] = True
    w.step(60)
    assert len(w.names()) == 4  # a short staleness keeps what rests
    w.step(960)  # more than one M15 bar
    assert w.orders() == []


def test_a_visit_record_that_disagrees_with_the_runner_is_marked(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    rows = hour_rows(bar(103, 104, 101.2, 101.2), bar(101.2, 102, 101.2, 102), FILL, FILL)
    w = world(worlds, tmp_path, exec_rows={130: rows})
    w.step(2)
    w.step(300, 101.2)
    assert w.runner.hour is not None
    w.to("2025-01-06 10:59:00", 103)  # the bars of the hour are all processed
    w.runner.hour.chosen = None  # the runner "forgot" its setup: the simulation's record says there was one
    with caplog.at_level(logging.ERROR, logger="app.zone.trader"):
        w.to("2025-01-06 11:00:03", 103)
    [rec] = w.store.visits(ts("2025-01-06 10:00").to_pydatetime())
    assert (rec.classification, rec.agreed, rec.note) == ("setup", False, "disagrees with the runner")
    assert any("FAULT: the visit record" in r.message for r in caplog.records)


def test_a_stale_quote_while_the_market_is_closed_removes_nothing(
    worlds: list[World], tmp_path: Path
) -> None:
    """Words / L7: no quote newer than ``stale_quote_seconds`` and no H1 bar at this weekday and hour in the
    previous four weeks: the market is closed - nothing is stale-removed (the constructed series has no earlier
    weeks, so a stale quote here reads as a closed market)."""
    w = world(worlds, tmp_path, start=False)
    real = w.runner.gw.tick
    stale = {"on": False}

    def tick(symbol: str) -> Any:
        t = real(symbol)
        return dataclasses.replace(t, time_utc=t.time_utc - timedelta(seconds=60)) if stale["on"] else t

    w.runner.gw.tick = tick  # type: ignore[method-assign]
    w.runner.start()
    w.step(2)
    assert len(w.names()) == 4
    stale["on"] = True
    w.step(960)
    w.step(960)
    # the BUY candidate's orders still rest (the SELL one withdrew by rule 1, its own life)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"] and w.runner.stale_since is None
