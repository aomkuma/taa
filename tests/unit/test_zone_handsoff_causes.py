"""L8's hands-off, one test per cause, and the start that finds the magic not flat (eye/ZONE_LIVE.md L8, L7, L2).

Written from the specification against the runner's public behaviour on FakeMT5 (the world of
``tests/unit/zone_live_support.py``: the test sets the bid, moves the clock and runs a cycle). What a hands-off
looks like from outside, and what each test asserts of it (L8, "Hands-off" - *What* and *Until*):

* placing stops - no order is sent but removals (``TRADE_ACTION_REMOVE``) from the moment it is declared;
* every resting order of the magic is removed (ours: P2 before P1 of a key; the rest in any order);
* **no position is touched** - no close, no SL modify, no break-even for it (the positions are compared before
  and after), each runs on at the broker with its own SL / TP;
* every setup not ended ends ``hands-off`` (a row whose ``state`` or ``outcome`` reads ``hands-off``), logged at
  ERROR;
* **until the magic is flat**: then the runner starts anew - the first decision is at the first H1 open after it,
  with no reservation, never in the middle of an hour.

Spec lines pinned (L8 numbering of the causes):

* cause 1 - a place of unknown outcome not found within one ``exec_tf`` bar: ``test_cause1_*``
  (also: "a place is never sent again", L8 *An unknown outcome*);
* cause 2 - an order of ours left the open orders without a history state or a deal, or shown filled without its
  entry deal read: ``test_cause2_*``;
* cause 3 - a position of ours gone without an exit deal, or open without its entry deal read: ``test_cause3_*``;
* cause 4 - an order or a position of the magic that is not ours: ``test_cause4_*`` (also the removal order,
  P2 before P1);
* cause 5 - a fill whose volume is not ``lot``: ``test_cause5_*``;
* cause 6 - a removal, a close not done within one ``exec_tf`` bar, an SL modify not in force after 3 tries:
  ``test_cause6_*`` (not covered here: a placement ``n`` over 999, a P1 refused after its candidate became the
  hour's setup, a market entry with no deal - they need seams of the rewritten runner);
* cause 7 - the owner acting by hand: an exit deal that is not SL / TP / the runner's own close, a wanted order
  cancelled without a remove request, a resting order or a position differing from what the broker last
  accepted from the runner: ``test_cause7_*`` (and the controls: SL / TP exits and the runner's own modifies are
  not hands-off);
* cause 8 - an uncaught error inside a cycle: ``test_cause8_*``;
* the start (L8 *The start*, L2): ``test_start_*`` - a start that finds the magic not flat goes hands-off (its
  resting orders removed, its positions left, no row ends ``hands-off``: the rows of the previous process ended
  ``restart``), a start on a flat book does not.

The driving surface relied on (all of it already used by ``test_zone_trader.py``): ``World`` and ``make_world``,
``w.runner.exe`` (the execution gateway, wrapped here to lose or refuse sends), ``w.runner.gw`` (the read gateway),
``w.store.setups()``, ``w.fake`` (FakeMT5: orders, positions, deals, history orders, ``desk.requests``)."""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from app.broker import mt5_constants as c
from app.broker.execution import CheckResult, ExecutionGateway, SendResult
from app.broker.retcodes import classify, describe
from app.zone.core import cut_bars
from app.zone.trader import ProcessLock, ZoneRunner
from tests.unit.zone_live_support import FILL, MAGIC, Row, World, make_world

ACTION_PLACE = c.TRADE_ACTION_PENDING
HOUR0 = "2025-01-06 10:00:05"  # the hour index 130's decision
HOUR1 = "2025-01-06 11:00:05"
HOUR2 = "2025-01-06 12:00:05"
BAR = 15 * 60  # one exec_tf bar (M15), in seconds
REFUSED = 10013
SPREAD = 20  # points: the ask is the bid + 0.20

# the hour 130's first M15 bar reaches the BUY P1 (101.32), the break-even trigger (mid 105.66) and closes high
BUY_ROWS: dict[int, list[Row]] = {130: [(103.0, 105.9, 101.0, 105.8), FILL, FILL, FILL]}


# --- the world --------------------------------------------------------------------------------------------------


class Lossy:
    """The execution gateway with the answers a test chooses (it wraps the runner's own)."""

    def __init__(self, inner: ExecutionGateway) -> None:
        self.inner = inner
        self.lose: set[str] = set()  # comments: not executed, no answer (an unknown outcome)
        self.refuse_comment: dict[str, int] = {}  # comment -> a refusing retcode
        self.refuse_action: dict[int, int] = {}  # TRADE_ACTION_* -> a refusing retcode (every send)
        self.sent: list[dict[str, Any]] = []

    def check(self, request: dict[str, Any]) -> CheckResult:
        return self.inner.check(request)

    def send(self, request: dict[str, Any]) -> SendResult:
        self.sent.append(dict(request))
        comment = str(request.get("comment", ""))
        opens = request.get("action") == ACTION_PLACE or (
            request.get("action") == c.TRADE_ACTION_DEAL and not request.get("position")
        )
        if opens and comment in self.lose:
            return SendResult(None, classify(None), describe(None))
        code = self.refuse_comment.get(comment, self.refuse_action.get(int(request.get("action", 0))))
        if code is not None:
            return SendResult(code, classify(code), describe(code))
        return self.inner.send(request)

    def places(self, prefix: str = "") -> list[dict[str, Any]]:
        return [
            r
            for r in self.sent
            if r.get("action") == ACTION_PLACE and str(r.get("comment", "")).startswith(prefix)
        ]


@pytest.fixture
def worlds() -> Iterator[list[World]]:
    made: list[World] = []
    yield made
    for w in made:
        if w.runner.lock is not None:
            w.runner.lock.release()
        w.db.dispose()


@pytest.fixture(autouse=True)
def _errors(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.zone")


def build(
    worlds: list[World], tmp_path: Path, *, exec_rows: dict[int, list[Row]] | None = None, **kw: Any
) -> tuple[World, Lossy]:
    """A world started just before the 10:00 open (the first decision is the first H1 open after the start, L8),
    with a wrapped execution gateway."""
    kw.setdefault("spread", SPREAD)
    kw.setdefault("now", "2025-01-06 09:59:50")
    w = make_world(tmp_path, exec_rows=exec_rows, **kw)
    worlds.append(w)
    ex = Lossy(w.runner.exe)  # type: ignore[arg-type]
    w.runner.exe = ex
    return w, ex


def decide(w: World, *, orders: int = 4) -> None:
    """The 10:00 decision: the hour's two candidates, four orders."""
    w.to(HOUR0)
    w.step(2)
    assert len(w.names()) == orders, w.names()


def fill_buy_p1(w: World) -> None:
    """The BUY P1 fills at the broker; the runner then reads the fill."""
    w.bid(101.0)
    w.fake.orders_get()
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]
    w.step(2)


def order(w: World, comment: str) -> SimpleNamespace:
    return next(o for o in w.fake.orders if o.comment == comment)


def stray_order(ticket: int = 9_001) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket,
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


def stray_position(ticket: int = 9_002) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket,
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
        identifier=ticket,
        margin=1.0,
    )


def vanish_order(w: World, comment: str) -> None:
    """The order leaves the book with no history state and no deal."""
    w.fake.orders.remove(order(w, comment))


def hand_cancel(w: World, comment: str) -> None:
    """The owner cancels the order at the terminal: it leaves the book, its history state is cancelled."""
    o = order(w, comment)
    w.fake.orders.remove(o)
    w.fake.desk._archive(o, c.ORDER_STATE_CANCELED)


def hand_close(w: World, reason: int) -> None:
    """The (only) position is closed by a deal of the given reason (``DEAL_REASON_*``)."""
    [pos] = w.fake.positions
    w.fake.desk._close(pos, pos.volume, pos.price_current, w.fake.desk._id(), "", reason)


def drop_entry_deals(w: World) -> None:
    w.fake.deals[:] = [d for d in w.fake.deals if d.entry != c.DEAL_ENTRY_IN]


# --- what a hands-off looks like ----------------------------------------------------------------------------------


def marked(row: Any) -> bool:
    return "hands-off" in (row.state, row.outcome)


def snapshot(w: World) -> list[tuple[Any, ...]]:
    return sorted((p.ticket, p.volume, p.sl, p.tp) for p in w.positions() if p.magic == MAGIC)


def sent_after(w: World, since: int) -> list[dict[str, Any]]:
    return w.fake.desk.requests[since:]


def assert_hands_off(
    w: World,
    caplog: pytest.LogCaptureFixture,
    *,
    hour: str = "2025-01-06 10",
    marks_rows: bool = True,
) -> list[tuple[Any, ...]]:
    """The hands-off is in force now (call it once the cause has had one ``exec_tf`` bar): the setups ended
    ``hands-off`` and logged at ERROR, no resting order of the magic; then, through the rest of the hour at
    several moments, nothing but removals is sent and the positions are as they were. Returns the positions."""
    rows = w.store.setups()
    assert rows and not [r for r in rows if r.state == "live"], [(r.id, r.state, r.outcome) for r in rows]
    if marks_rows:
        assert any(marked(r) for r in rows), [(r.id, r.state, r.outcome) for r in rows]
    assert any(rec.levelno >= logging.ERROR for rec in caplog.records), "hands-off is logged at ERROR"
    assert [o.comment for o in w.orders() if o.magic == MAGIC] == []
    before, since = snapshot(w), len(w.fake.desk.requests)
    for minute in ("20:00", "40:00", "58:00"):
        w.to(f"{hour}:{minute}")
        w.step(2)
    actions = {r.get("action") for r in sent_after(w, since)}
    assert actions <= {c.TRADE_ACTION_REMOVE}, actions  # no place, no close, no SL modify, no break-even
    assert snapshot(w) == before  # no position touched
    assert [o for o in w.orders() if o.magic == MAGIC] == []
    return before


def assert_resumes_at_next_open(w: World, next_open: str = HOUR1) -> None:
    """The magic is flat: nothing was placed in the middle of the hour (``assert_hands_off``); the first decision is
    at the next H1 open."""
    assert [p for p in w.positions() if p.magic == MAGIC] == []
    w.bid(103.0)
    since = len(w.fake.desk.requests)
    w.to(next_open)
    w.step(2)
    hour = pd.Timestamp(next_open, tz="UTC").floor("h")
    # both candidates decided at that open (whether each may rest is its own life's: a disarmed or blocked line)
    assert len(w.store.setups(hour_open=hour.to_pydatetime())) == 2, w.names()
    assert {r.get("action") for r in sent_after(w, since)} >= {ACTION_PLACE}


def assert_stays_off_while_open(w: World, next_open: str = HOUR1) -> None:
    """A position of the magic is still open: even at the next H1 open nothing is placed."""
    since = len(w.fake.desk.requests)
    w.to(next_open)
    w.step(2)
    assert w.orders() == []
    assert ACTION_PLACE not in {r.get("action") for r in sent_after(w, since)}


def take_profit_then_resume(w: World, hour_after: str = HOUR2) -> None:
    """The position runs to its TP at the broker (the BUY: 110); the book is flat; the next open decides."""
    w.bid(110.5)
    w.fake.orders_get()
    w.to("2025-01-06 11:20:00", 110.5)
    assert [p for p in w.positions() if p.magic == MAGIC] == []
    assert_resumes_at_next_open(w, hour_after)


# --- cause 1: a place of unknown outcome not found within one exec_tf bar -------------------------------------------


def test_cause1_a_place_never_found_is_never_sent_again_and_after_a_bar_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, ex = build(worlds, tmp_path)
    ex.lose.add("Z1-P1-0")  # sent, not executed, no answer: searched by its key every cycle
    w.to(HOUR0)
    w.step(2)
    w.step(300)
    assert len(ex.places("Z1-P1")) == 1  # never sent again, within the bar or after it
    assert not any(marked(r) for r in w.store.setups())  # one bar has not passed yet
    w.to("2025-01-06 10:16:10")
    w.step(2)
    assert len(ex.places("Z1-P1")) == 1
    assert_hands_off(w, caplog)
    assert len(ex.places("Z1-P1")) == 1
    assert_resumes_at_next_open(w)


# --- cause 2: an order left without a history state or a deal, or shown filled without its entry deal ----------------


def test_cause2_an_order_gone_without_a_history_state_or_a_deal_is_hands_off_after_a_bar(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    vanish_order(w, "Z1-P2-0")
    w.step(2)
    w.to("2025-01-06 10:16:10")
    w.step(2)
    assert_hands_off(w, caplog)
    assert_resumes_at_next_open(w)


def test_cause2_an_order_shown_filled_in_the_history_without_its_entry_deal_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    o = order(w, "Z1-P1-0")
    w.fake.orders.remove(o)
    w.fake.desk._archive(o, c.ORDER_STATE_FILLED)  # filled, per the history; no deal, no position
    w.step(2)
    w.to("2025-01-06 10:16:10")
    w.step(2)
    assert_hands_off(w, caplog)
    assert_resumes_at_next_open(w)


# --- cause 3: a position gone without an exit deal, or open without its entry deal ---------------------------------


def test_cause3_a_position_gone_without_an_exit_deal_is_hands_off_after_a_bar(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    decide(w)
    fill_buy_p1(w)
    w.fake.positions[:] = []  # gone, with no deal
    w.step(2)
    w.to("2025-01-06 10:16:10")
    w.step(2)
    assert_hands_off(w, caplog)
    assert_resumes_at_next_open(w)


def test_cause3_a_position_open_without_its_entry_deal_is_left_alone_and_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.bid(101.0)
    w.fake.orders_get()  # the BUY P1 fills at the broker ...
    drop_entry_deals(w)  # ... and its entry deal is never readable
    assert [p.comment for p in w.positions()] == ["Z1-P1-0"]
    w.step(2)
    w.to("2025-01-06 10:16:10", 101.0)
    w.step(2)
    kept = assert_hands_off(w, caplog)
    assert [t[2:] for t in kept] == [(95.0, 110.0)]  # the broker's own SL / TP, as placed
    assert_stays_off_while_open(w)
    take_profit_then_resume(w)


# --- cause 4: an order or a position of the magic that is not ours ---------------------------------------------------


def test_cause4_a_stray_order_removes_everything_p2_before_p1_and_then_resumes(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    ours = {o.ticket: o.comment for o in w.orders()}
    since = len(w.fake.desk.requests)
    w.fake.orders.append(stray_order())
    w.step(2)
    w.step(2)
    assert_hands_off(w, caplog)
    removed = [r.get("order") for r in sent_after(w, since) if r.get("action") == c.TRADE_ACTION_REMOVE]
    assert 9_001 in removed  # the stray is removed too: every resting order of the magic
    names = [ours[t] for t in removed if t in ours]
    for key in ("Z1", "Z2"):  # L8: ours P2 before P1 of a key
        assert names.index(f"{key}-P2-0") < names.index(f"{key}-P1-0")
    assert_resumes_at_next_open(w)


def test_cause4_a_stray_position_is_left_to_the_owner_until_the_magic_is_flat(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.fake.positions.append(stray_position())
    w.step(2)
    w.step(2)
    kept = assert_hands_off(w, caplog)
    assert [t[0] for t in kept] == [9_002]  # never closed, never modified
    assert_stays_off_while_open(w)
    w.fake.positions[:] = []  # the owner closes it
    w.to("2025-01-06 11:30:00")
    assert w.orders() == []  # flat: the hands-off is over, but the decision waits for the next open
    assert_resumes_at_next_open(w, HOUR2)


def test_cause4_an_order_of_a_forgotten_key_appearing_later_is_not_ours(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """After a hands-off ends, the keys of the run are no longer ours: a late order with one is a stranger (4)."""
    w, ex = build(worlds, tmp_path)
    ex.lose.add("Z1-P1-0")
    w.to(HOUR0)
    w.step(2)
    w.to("2025-01-06 10:16:10")
    w.step(2)
    assert_hands_off(w, caplog)
    late = stray_order(9_100)
    late.comment = "Z1-P1-0"  # the lost order turns up on the broker after all
    w.fake.orders.append(late)
    w.to("2025-01-06 10:59:00")
    assert [o for o in w.orders() if o.ticket == 9_100] == []  # a stranger: removed, not managed
    assert not [o for o in w.orders() if o.magic == MAGIC]


# --- cause 5: a fill whose volume is not lot -------------------------------------------------------------------------


def test_cause5_a_partial_fill_is_hands_off_with_the_position_left(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    o = order(w, "Z1-P1-0")
    o.volume_current = 0.005  # half of it filled: the other half still rests
    w.fake.positions.append(
        SimpleNamespace(
            ticket=o.ticket,
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
            identifier=o.ticket,
            margin=1.0,
        )
    )
    w.fake.desk._deal(
        "XAUUSD",
        c.ORDER_TYPE_BUY,
        c.DEAL_ENTRY_IN,
        0.005,
        101.32,
        0.0,
        o.ticket,
        o.ticket,
        None,
        w.fake.desk._now_server(),
        magic=MAGIC,
        comment="Z1-P1-0",
    )
    w.bid(101.0)
    w.step(2)
    w.step(2)  # no wait for a bar: a partial volume is known the moment the fill is read
    kept = assert_hands_off(w, caplog)
    # not closed, not completed by the runner (the broker may fill the order's remainder before it is removed)
    assert kept and {t[1] for t in kept} == {0.005}
    assert_stays_off_while_open(w)


# --- cause 6: a removal / a close not done within a bar, an SL modify not in force after 3 tries ------------------------


def test_cause6_a_removal_refused_for_a_bar_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    fill_buy_p1(w)  # the first visit: the SELL candidate's orders must be removed - refused
    w.step(60, 101.0)
    assert not any(marked(r) for r in w.store.setups())  # not yet: retried each cycle for one bar
    w.to("2025-01-06 10:16:10", 101.0)
    w.step(2)
    ex.refuse_action.clear()  # the broker works again: the remaining orders go
    w.step(2)
    w.step(2)
    assert_hands_off(w, caplog)


def test_cause6_a_close_refused_for_a_bar_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_DEAL] = REFUSED  # no market close (nor entry) is accepted
    w.bid(101.0)
    w.fake.orders_get()  # the BUY P1 fills at the broker before the runner looks
    w.bid(109.0)
    w.fake.orders_get()  # and the SELL P1: L4's race, the later one must be closed at once
    assert len(w.positions()) == 2
    w.step(2)
    w.step(60)
    assert not any(marked(r) for r in w.store.setups())
    w.to("2025-01-06 10:16:10")
    w.step(2)
    ex.refuse_action.clear()
    snap = snapshot(w)
    assert len(snap) == 2  # the refused close left both positions standing
    kept = assert_hands_off(w, caplog)
    assert kept == snap  # and hands-off never closes the loser later


def test_cause6_an_sl_modify_not_in_force_after_three_tries_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, ex = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    decide(w)
    fill_buy_p1(w)
    ex.refuse_action[c.TRADE_ACTION_SLTP] = 10016
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)  # the break-even is due at this close: its SL modify is refused
    for _ in range(6):
        w.step(2)
    tries = [r for r in ex.sent if r.get("action") == c.TRADE_ACTION_SLTP]
    assert len(tries) == 3  # exactly three tries, then the runner lets go
    assert [t[2] for t in snapshot(w)] == [95.0]  # the position keeps the SL it had
    assert_hands_off(w, caplog)
    assert len([r for r in ex.sent if r.get("action") == c.TRADE_ACTION_SLTP]) == 3


# --- cause 7: the owner acting by hand ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason", [c.DEAL_REASON_CLIENT, c.DEAL_REASON_MOBILE, c.DEAL_REASON_WEB, c.DEAL_REASON_SO]
)
def test_cause7_an_exit_by_hand_or_a_stop_out_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture, reason: int
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    hand_close(w, reason)
    w.step(2)
    w.step(2)  # no wait for a bar: the exit deal is read
    assert_hands_off(w, caplog)
    assert_resumes_at_next_open(w)


@pytest.mark.parametrize(("reason", "bid"), [(c.DEAL_REASON_TP, 110.5), (c.DEAL_REASON_SL, 94.0)])
def test_cause7_control_an_sl_or_tp_exit_is_not_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture, reason: int, bid: float
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    w.bid(bid)
    w.fake.orders_get()
    assert {d.reason for d in w.fake.deals if d.entry == c.DEAL_ENTRY_OUT} == {reason}
    w.step(2)
    w.step(2)
    assert not any(marked(r) for r in w.store.setups())
    assert not any(rec.levelno >= logging.ERROR for rec in caplog.records)


def test_cause7_control_the_runners_own_close_is_not_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The break-even with the price already beyond the stop is a market close by the runner (DEAL_REASON_EXPERT)."""
    rows: dict[int, list[Row]] = {130: [(103.0, 105.9, 100.9, 100.95), FILL, FILL, FILL]}
    w, _ = build(worlds, tmp_path, exec_rows=rows)
    decide(w)
    fill_buy_p1(w)
    w.step(60, 105.7)
    w.step(60, 100.95)
    w.to("2025-01-06 10:15:02", 100.95)
    w.step(2, 100.95)
    assert w.positions() == []
    assert [d.reason for d in w.fake.deals if d.entry == c.DEAL_ENTRY_OUT] == [c.DEAL_REASON_EXPERT]
    assert not any(marked(r) for r in w.store.setups())
    assert not any(rec.levelno >= logging.ERROR for rec in caplog.records)


def test_cause7_a_wanted_order_cancelled_by_hand_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    hand_cancel(w, "Z1-P1-0")
    w.step(2)
    w.step(2)
    assert_hands_off(w, caplog)
    assert_resumes_at_next_open(w)


def _set(attr: str, value: Callable[[Any], Any]) -> Callable[[Any], None]:
    def go(obj: Any) -> None:
        setattr(obj, attr, value(getattr(obj, attr)))

    return go


@pytest.mark.parametrize(
    "change",
    [
        _set("price_open", lambda v: v + 0.5),
        _set("volume_current", lambda v: v * 2),
        _set("sl", lambda v: v - 1.0),
        _set("tp", lambda v: v + 1.0),
        _set("time_expiration", lambda v: v + 3600),
    ],
    ids=["price", "volume_current", "sl", "tp", "expiration"],
)
def test_cause7_a_resting_order_changed_by_hand_is_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture, change: Callable[[Any], None]
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    change(order(w, "Z2-P1-0"))
    w.step(2)
    w.step(2)
    assert_hands_off(w, caplog)
    assert_resumes_at_next_open(w)


@pytest.mark.parametrize(
    "change",
    [
        _set("sl", lambda v: v - 1.0),
        _set("tp", lambda v: v - 1.0),
        _set("volume", lambda v: v * 2),
    ],
    ids=["sl", "tp", "volume"],
)
def test_cause7_a_position_changed_by_hand_is_hands_off_and_left_as_the_owner_set_it(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture, change: Callable[[Any], None]
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    [pos] = w.fake.positions
    change(pos)
    mine = (pos.volume, pos.sl, pos.tp)
    w.step(2)
    w.step(2)
    kept = assert_hands_off(w, caplog)
    assert [t[1:] for t in kept] == [mine]  # the runner did not put it back
    assert_stays_off_while_open(w)


def test_cause7_control_the_runners_own_modifies_are_not_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The break-even's SL move and the hourly expiry extension are accepted by the broker: not 'by hand'."""
    w, _ = build(worlds, tmp_path, exec_rows=BUY_ROWS)
    decide(w)
    fill_buy_p1(w)
    w.step(60, 105.7)
    w.to("2025-01-06 10:15:02", 105.7)
    assert [p.sl for p in w.positions()] == [101.52]  # the break-even moved the stop
    w.to("2025-01-06 10:51:30", 105.7)  # the expiry extension of the hour's setup
    w.step(2)
    assert not any(marked(r) for r in w.store.setups())
    assert not any(rec.levelno >= logging.ERROR for rec in caplog.records)


# --- cause 8: an uncaught error inside a cycle ------------------------------------------------------------------------


def test_cause8_an_uncaught_error_in_a_cycle_ends_the_cycle_and_goes_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    real = w.runner.gw.orders
    left = {"n": 1}

    def broken(symbol: str | None = None) -> Any:
        if left["n"] > 0:
            left["n"] -= 1
            raise RuntimeError("a bug, not a broker failure")
        return real(symbol)

    w.runner.gw.orders = broken  # type: ignore[method-assign]
    w.step(2)  # the cycle logs the error at ERROR and ends: it does not raise
    assert any(rec.levelno >= logging.ERROR for rec in caplog.records)
    w.step(2)
    w.step(2)
    kept = assert_hands_off(w, caplog)
    assert [t[0] for t in kept] == [w.fake.positions[0].ticket]  # the position is left to the broker
    assert_stays_off_while_open(w)
    take_profit_then_resume(w)


# --- the start --------------------------------------------------------------------------------------------------------


def new_process(w: World, worlds: list[World]) -> World:
    """A restart: a fresh runner on the same database, broker and bars (the old lock is released)."""
    old = w.runner
    if old.lock is not None:
        old.lock.release()
    runner = ZoneRunner(
        cfg=old.cfg,
        params=old.params,
        clock=old.clock,
        gateway=old.gw,
        execution=old.exe,
        bar_source=old.src,
        db=old.db,
        bars=cut_bars(w.full, pd.Timestamp(old.clock.now_utc())),
        kill_switch=old.kill,
        magic=old.magic,
        grids_fn=old.grids_fn,
        lock=ProcessLock(w.tmp / "runner.lock"),
    )
    runner.start()
    w2 = dataclasses.replace(w, runner=runner)
    worlds.append(w2)
    return w2


def test_start_with_resting_orders_removes_them_places_nothing_and_ends_no_row_hands_off(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.to("2025-01-06 10:03:00")
    w2 = new_process(w, worlds)  # the old process died with its four orders resting
    since = len(w2.fake.desk.requests)
    w2.step(2)
    w2.step(2)
    assert w2.orders() == []  # the magic is not flat at the start: hands-off, the orders removed
    rows = w2.store.setups()
    assert rows and all(r.state != "live" for r in rows)
    assert not any(marked(r) for r in rows)  # the rows ended `restart`: none ends hands-off here
    w2.to("2025-01-06 10:40:00")
    w2.step(2)
    assert ACTION_PLACE not in {
        r.get("action") for r in sent_after(w2, since)
    }  # never in the middle of an hour
    assert_resumes_at_next_open(w2)  # flat now: the first decision is the next H1 open, no reservation


def test_start_with_a_position_open_leaves_it_to_the_broker_until_it_is_flat(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    fill_buy_p1(w)
    pos = snapshot(w)
    w.to("2025-01-06 10:03:00", 101.0)
    w2 = new_process(w, worlds)
    since = len(w2.fake.desk.requests)
    w2.step(2)
    w2.step(2)
    assert w2.orders() == []  # the leftover P2 and the other candidate's orders are removed
    assert snapshot(w2) == pos  # the position is not touched
    assert not any(marked(r) for r in w2.store.setups())
    w2.to("2025-01-06 10:30:00")
    w2.to("2025-01-06 10:45:00", 105.7)  # even a break-even-sized move: nothing is modified
    assert {r.get("action") for r in sent_after(w2, since)} <= {c.TRADE_ACTION_REMOVE}
    assert snapshot(w2) == pos
    assert_stays_off_while_open(w2)
    take_profit_then_resume(w2)


def test_start_on_a_flat_book_is_not_hands_off_and_waits_for_the_next_open(
    worlds: list[World], tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    w, _ = build(worlds, tmp_path, now="2025-01-06 10:20:00")
    since = len(w.fake.desk.requests)
    w.step(2)
    w.to("2025-01-06 10:40:00")
    assert w.orders() == [] and len(w.fake.desk.requests) == since  # never in the middle of an hour
    assert not any(rec.levelno >= logging.ERROR for rec in caplog.records)
    w.to("2025-01-06 10:59:50")
    w.to(HOUR1)
    w.step(2)
    assert len(w.names()) == 4
    assert not any(marked(r) for r in w.store.setups())
