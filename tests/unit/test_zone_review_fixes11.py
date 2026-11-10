# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 11 of the run-zone runner (eye/ZONE_LIVE.md L5 "Every other judgement of the setup waits too", L8
"Safety first in each cycle", L10).

A. A pending entry (a position of the setup seen before its entry deal) is a barrier on the whole setup: its
   interruption, a latched touch, the close steps and its end wait until the entry deal is read - also when the
   position disappears. Removals for safety do not wait.
B. A fixed cycle skeleton: the stop deadline from memory first; then only the account and the open orders are read;
   the removals owed; then every other read and step. Nothing else holds the removals back.
C. The `--now` timeout exit with removals unconfirmed leaves the stop request unacknowledged."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.broker import mt5_constants as c
from app.zone.params import ZoneParams
from app.zone.trader import PendingEntry
from tests.unit.test_zone_handsoff_causes import (
    BUY_ROWS,
    HOUR0,
    REFUSED,
    build,
    decide,
    stray_order,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.test_zone_review_fixes10 import hidden_entry_deals
from tests.unit.zone_live_support import FILL


def fail(*_a: Any, **_k: Any) -> Any:
    raise OSError("unavailable")


def boom(*_a: Any, **_k: Any) -> None:
    raise RuntimeError("boom")


def pending_entry(worlds: list, tmp_path: Path, **kw: Any):  # type: ignore[no-untyped-def, type-arg]
    """The BUY P1 filled at the broker and seen as a position, its entry deal not readable yet."""
    w, ex = build(worlds, tmp_path, **kw)
    hide = {"on": True}
    hidden_entry_deals(w, hide)
    decide(w)
    w.bid(101.0)
    w.fake.orders_get()
    w.step(2)
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]
    assert w.runner.entries  # the pending entry
    return w, ex, hide


# --- A: the pending entry is a barrier on the setup ------------------------------------------------------------------


def test_a_a_stop_does_not_interrupt_a_setup_with_a_pending_entry_and_the_deal_is_its_fill(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex, hide = pending_entry(worlds, tmp_path)
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    assert w.store.setup(1).state == "live"  # not interrupted
    assert [o for o in w.orders() if o.comment.startswith("Z")] == []  # the removals for safety did not wait
    hide["on"] = False
    w.step(2)
    w.step(2)
    assert w.store.setup(1).outcome != "interrupted"
    assert "P1" in w.runner.cands[1].fills  # the deal is the setup's fill
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]  # and the position is not closed at market
    assert not [r for r in ex.sent if r.get("action") == c.TRADE_ACTION_DEAL and r.get("position")]


def test_a_the_touch_latch_does_not_fire_while_the_entry_is_pending(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    rows129 = [(104.5, 105.0, 102.5, 103.0), FILL, FILL, FILL]
    rows130 = [(103.0, 104.0, 100.9, 103.0), FILL, FILL, FILL]
    w, _ = build(
        worlds,
        tmp_path,
        exec_rows={129: rows129, 130: rows130},
        params=ZoneParams(cancel_frac=0.2),
        spread=50,
    )
    w.to(HOUR0, 103.0)
    w.step(2)
    # a pending entry of the setup (as if its position had been seen without its deal)
    now = w.runner.now()
    w.runner.entries[("position", 5_000_099)] = PendingEntry("position", 5_000_099, (1, "P1", 0), now, now)
    w.step(60, 100.9)  # the ask is under the blocked P1
    assert w.runner.cands[1].cancel_seen is None


def test_a_a_position_that_vanishes_before_its_deal_does_not_let_the_close_steps_advance(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    hide = {"on": True}
    hidden_entry_deals(w, hide)
    real_history = w.runner.gw.history_orders
    w.runner.gw.history_orders = lambda a, b: [  # type: ignore[method-assign]
        h for h in real_history(a, b) if h.state != c.ORDER_STATE_FILLED
    ]
    decide(w)
    w.to("2025-01-06 10:10:00", 103.0)
    nj = w.runner.next_j
    w.bid(101.0)
    w.fake.orders_get()
    w.step(2)
    w.fake.positions[:] = []  # gone before its deal arrived
    w.step(2)
    w.to("2025-01-06 10:15:30", 103.0)  # the bar of the entry has closed
    assert w.runner.next_j == nj  # the closed bar of the entry was not judged
    assert w.runner.hands_off is None  # a bar has not passed since the sighting
    assert w.runner.entries


def test_a_hands_off_does_not_wait_for_a_pending_entry_and_its_deal_is_not_judged(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex, hide = pending_entry(worlds, tmp_path)
    w.fake.orders.append(stray_order())  # cause 4: hands-off at once
    w.step(2)
    assert w.runner.hands_off is not None
    assert w.store.setup(1).state != "live"  # the setup ended hands-off, not held by its pending entry
    hide["on"] = False
    w.step(2)
    w.step(2)
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]  # no position touched
    cand = w.runner.cands.get(1)
    assert cand is None or "P1" not in cand.fills  # no fill judged
    assert not [r for r in ex.sent if r.get("action") == c.TRADE_ACTION_DEAL and r.get("position")]


def test_a_an_ordinary_stop_does_not_exit_while_an_entry_is_pending(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ex, _hide = pending_entry(worlds, tmp_path)
    real_history = w.runner.gw.history_orders
    w.runner.gw.history_orders = lambda a, b: [  # type: ignore[method-assign]
        h for h in real_history(a, b) if h.state != c.ORDER_STATE_FILLED
    ]
    w.fake.positions[:] = []  # no position is open, the entry deal never came
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.to("2025-01-06 10:05:00", 103.0)
    w.step(2)
    assert w.orders() == [] and w.runner.stop_acked
    assert not w.runner.finished  # the pending entry holds the exit
    w.to("2025-01-06 10:16:10", 103.0)
    w.step(2)
    assert w.runner.finished  # hands-off at the entry's one-bar timer has its own exit


# --- B: the cycle skeleton -------------------------------------------------------------------------------------------


def test_b_a_stop_removes_the_orders_though_the_history_read_fails(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.runner.gw.history_orders = fail  # type: ignore[method-assign]
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    assert w.orders() == []


def test_b_a_stop_removes_the_orders_though_the_bar_update_raises(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.runner._update_bars_into = boom  # type: ignore[method-assign]
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    assert w.orders() == []


def test_b_an_active_stop_now_exits_after_60_seconds_though_the_store_cannot_be_read(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.store.pending_stop = fail  # type: ignore[method-assign]
    w.store.pending_stops = fail  # type: ignore[method-assign]
    w.step(30)
    assert not w.runner.finished
    w.step(35)
    assert w.runner.finished


# --- C: the timeout exit leaves the request unacknowledged ----------------------------------------------------------


def test_c_the_now_timeout_with_orders_resting_leaves_the_request_unacknowledged(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(65)
    assert w.runner.finished
    assert len(w.orders()) == 4
    assert w.store.pending_stop() is not None  # not acknowledged: the removals were never confirmed


def test_c_the_acknowledgement_follows_the_confirmed_removal(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(2)
    assert w.runner.finished and w.orders() == []
    assert w.store.pending_stop() is None
