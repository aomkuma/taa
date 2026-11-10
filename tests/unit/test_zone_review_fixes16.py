# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 15 of the run-zone runner, batch 2 - the safety net (eye/ZONE_LIVE.md L1, L7, L8, L10).

U. The ordinary stop exits only when nothing of ours can still open a position unseen - an order of ours gone
   without its explanation included (L8 causes 1 - 2).
L. An obligation is latched the moment it falls due, whatever the later reads give: the safety removals with their
   reason and the interruption they bring; the closed market's time is taken out of a waiting stale removal's
   timer from the account and orders reads alone.
C. An orders read confirms the removals only when it was taken after the stop request and after the last placement;
   else the --now exit leaves the request unacknowledged and names what may still rest.
A. After an account switch the runner logs an ERROR every cycle while it waits (L1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from app.broker import mt5_constants as c
from tests.unit.test_zone_handsoff_causes import (
    HOUR0,
    REFUSED,
    build,
    decide,
    vanish_order,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.test_zone_review_fixes13 import market, quotes
from tests.unit.zone_live_support import LOGIN


def fail(*_a: Any, **_k: Any) -> Any:
    raise OSError("unavailable")


# --- U ----------------------------------------------------------------------------------------------------------------


def test_u_an_ordinary_stop_does_not_exit_while_an_order_of_ours_is_gone_unexplained(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    vanish_order(w, "Z1-P1-0")  # gone from the book: no history state, no deal, no position (yet)
    w.step(2)
    assert w.runner.gone_since
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(2)
    assert w.orders() == [] and w.runner.stop_acked
    assert not w.runner.finished  # it may have filled unseen
    w.to("2025-01-06 10:15:30")  # L8 cause 2: not explained within one bar - hands-off, the magic flat
    assert w.runner.finished


# --- L ----------------------------------------------------------------------------------------------------------------


def test_l_safety_removals_and_their_interruption_are_owed_though_the_cause_clears_before_the_next_cycle(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    real_positions = w.runner.gw.positions
    w.runner.gw.positions = fail  # type: ignore[method-assign]  # the later steps of the cycles fail
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.kill.activate("test", "t", "test")
    w.step(2)  # the kill switch: every order owed for removal (refused), the setups owed an interruption
    assert len(w.orders()) == 4
    w.kill.release("test", "t")  # released before the next cycle (from the local CLI)
    del ex.refuse_action[c.TRADE_ACTION_REMOVE]
    w.step(2)
    assert w.orders() == []  # the owed removals are retried and done
    w.runner.gw.positions = real_positions  # type: ignore[method-assign]
    w.step(2)
    assert [w.store.setup(i).outcome for i in (1, 2)] == ["interrupted", "interrupted"]


def test_l_the_closed_market_is_taken_out_of_a_stale_removal_timer_though_the_later_reads_fail(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    mkt = market(w)
    stale = quotes(w)
    stale["on"] = True
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.step(2)
    w.to("2025-01-06 10:15:15")  # the stale removals owed: sent, refused - their one-bar timer starts
    assert len(w.orders()) == 4
    real_positions = w.runner.gw.positions
    w.runner.gw.positions = fail  # type: ignore[method-assign]  # the later reads fail through the closure
    mkt["closed"] = True
    w.step(2)
    w.to("2025-01-06 10:25:00")
    w.to("2025-01-06 10:40:00")
    w.runner.gw.positions = real_positions  # type: ignore[method-assign]
    stale["on"], mkt["closed"] = False, False  # the reopening, the removals still refused
    w.step(2)
    assert w.runner.hands_off is None  # the 25 closed minutes did not count


# --- C ----------------------------------------------------------------------------------------------------------------


def test_c_the_stop_now_deadline_does_not_take_an_orders_read_before_the_placements_as_confirmation(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, _ = build(worlds, tmp_path)
    w.to(HOUR0)  # the decision: the cycle's orders read (empty) came before its four placements
    assert len(w.orders()) == 4 and w.runner.last_orders == []
    w.runner.gw.account = fail  # type: ignore[method-assign]  # no account / orders read from now on
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(30)
    with caplog.at_level(logging.ERROR, logger="app.zone.trader"):
        w.step(35)  # the 60 s
    assert w.runner.finished and len(w.orders()) == 4
    assert w.store.pending_stop() is not None  # never confirmed: not acknowledged
    named = " ".join(r.getMessage() for r in caplog.records if "not confirmed removed" in r.getMessage())
    assert all(k in named for k in ("Z1-P1-0", "Z1-P2-0", "Z2-P1-0", "Z2-P2-0"))


# --- A ----------------------------------------------------------------------------------------------------------------


def test_a_an_account_switch_is_logged_at_error_every_cycle_while_it_waits(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.fake.account.login = LOGIN + 5
    w.step(2)
    assert w.runner.account_switched
    with caplog.at_level(logging.ERROR, logger="app.zone.trader"):
        caplog.clear()
        w.step(2)
        w.step(2)
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR and "pinned" in r.getMessage()]
    assert len(errors) >= 2
