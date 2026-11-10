# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 12 of the run-zone runner (eye/ZONE_LIVE.md L2, L4, L5, L7, L8, L10).

D. The hour's decision waits until the close steps of every bar closed at its open are done (L2): an exec_tf bar
   that closed at the open but is not published yet holds the hour (the 60 s still count from its first quote).
A. The pending entry is ONE per-setup registry (L5): a position or a filled order of ours seen without its entry
   deal holds ITS setup's bar loop, deals and judgements - not the other setups' (L4's hour-wide order is kept
   where the pending entry can still take the hour); the ordinary stop exit waits for every pending entry (L10).
B. ONE function judges the cycle's conditions from what has been read so far (L2, L7, L8, L10): a failed read of
   anything vetoes placing for the whole cycle; nothing is stale-removed while the market is closed; the stop is
   acknowledged from the account / orders read alone."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from app.broker import mt5_constants as c
from app.broker.execution import SendResult
from app.broker.retcodes import classify, describe
from tests.unit.test_zone_handsoff_causes import (
    HOUR0,
    REFUSED,
    Lossy,
    build,
    decide,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.test_zone_review_fixes10 import hidden_entry_deals
from tests.unit.zone_live_support import FILL, World, ts


def fail(*_a: Any, **_k: Any) -> Any:
    raise OSError("unavailable")


def late_bars(w: World, tf: str, hide_from: pd.Timestamp) -> dict[str, bool]:
    """The broker has not published the ``tf`` bars opening at or after ``hide_from`` yet: both reads (the bars
    and the broker's last closed bar) agree on the older bar."""
    on = {"on": True}
    real_closed = w.src.closed_bars
    real_last = w.src.last_closed_open

    def closed_bars(t: str, after: pd.Timestamp | None) -> pd.DataFrame:
        df = real_closed(t, after)
        if on["on"] and t == tf:
            df = df[df["open_time"] < hide_from].reset_index(drop=True)
        return df

    def last_closed_open(t: str) -> pd.Timestamp | None:
        last = real_last(t)
        if on["on"] and t == tf and last is not None and last >= hide_from:
            df = real_closed(t, None)
            df = df[df["open_time"] < hide_from]
            return None if df.empty else pd.Timestamp(df["open_time"].iloc[-1])
        return last

    w.src.closed_bars = closed_bars  # type: ignore[method-assign]
    w.src.last_closed_open = last_closed_open  # type: ignore[method-assign]
    return on


def hide_entries_of(w: World, prefix: str, hide: dict[str, bool]) -> None:
    """The entry deals whose comment starts with ``prefix`` are not readable while ``hide['on']``."""
    real = w.runner.gw.deals

    def deals(start: Any, end: Any) -> Any:
        got = real(start, end)
        if not hide["on"]:
            return got
        return [d for d in got if not (d.entry == c.DEAL_ENTRY_IN and str(d.comment).startswith(prefix))]

    w.runner.gw.deals = deals  # type: ignore[method-assign]


class KeepOrders(Lossy):
    """Refuses the removal of the listed order tickets (they keep resting)."""

    def __init__(self, inner: Any) -> None:
        super().__init__(inner)
        self.keep: set[int] = set()

    def send(self, request: dict[str, Any]) -> SendResult:
        if request.get("action") == c.TRADE_ACTION_REMOVE and int(request.get("order", 0)) in self.keep:
            self.sent.append(dict(request))
            return SendResult(REFUSED, classify(REFUSED), describe(REFUSED))
        return super().send(request)


# --- D: the decision waits for the bars closed at the open --------------------------------------------------------


def test_d_the_decision_waits_for_the_exec_bar_closed_at_the_open(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    late = late_bars(w, "M15", ts("2025-01-06 09:45"))
    w.to(HOUR0)  # 10:00:05 - the 09:45 bar closed at the open is not published; both reads agree on 09:30
    w.step(2)
    assert ex.places() == [] and w.runner.cands == {}  # no decision before that bar's close steps
    late["on"] = False
    w.step(2)  # the bar is read and processed, inside the 60 s of the hour's first quote
    assert len(w.names()) == 4
    assert {cd.plan.j0 for cd in w.runner.cands.values()} == {520}  # the hour's own first exec bar


def test_d_a_bar_published_after_the_60_seconds_leaves_the_hour_undecided(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    late = late_bars(w, "M15", ts("2025-01-06 09:45"))
    w.to(HOUR0)
    w.step(30)
    w.step(30)  # 10:01:05 - past the 60 s from the hour's first quote
    late["on"] = False
    w.step(2)
    assert ex.places() == []
    assert w.runner.hour is not None and w.runner.hour.open == ts("2025-01-06 10:00")
    assert w.runner.hour.undecided  # never decided later in the hour


# --- A: the pending entry holds its own setup ---------------------------------------------------------------------


def test_a_a_pending_entry_of_the_dropped_candidate_does_not_stop_the_chosen_setups_break_even(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    # the 10:00 bar reaches the BUY P1 (101.32) and the break-even trigger (mid 105.66)
    w, ex0 = build(worlds, tmp_path, exec_rows={130: [(103.0, 109.0, 101.0, 105.8), FILL, FILL, FILL]})
    ex = KeepOrders(ex0.inner)
    w.runner.exe = ex  # type: ignore[assignment]
    hide = {"on": True}
    hide_entries_of(w, "Z2-", hide)  # the SELL's entry deals are not readable
    decide(w)
    ex.keep |= {o.ticket for o in w.orders() if o.comment.startswith("Z2-")}  # the SELL's orders stay
    w.to("2025-01-06 10:05:00", 103.0)
    w.bid(101.0)
    w.fake.orders_get()  # the BUY P1 fills
    w.step(2)
    buy = w.runner.cands[1]
    assert buy.chosen and "P1" in buy.fills
    w.bid(108.8)
    w.fake.orders_get()  # the SELL P1 (removal refused) fills too: its position is seen, its deal is not
    w.step(2, 105.0)
    assert any(p.comment == "Z2-P1-0" for p in w.positions())
    assert w.runner.entries  # the SELL's pending entry
    w.to("2025-01-06 10:15:02", 105.0)  # the break-even bar has closed
    assert buy.be_on  # the chosen BUY's bar loop went on
    [p1] = [p for p in w.positions() if p.comment == "Z1-P1-0"]
    assert p1.sl == buy.be_sent
    assert "Z1-P2-0" not in w.names()  # its P2 removed by the break-even


def test_a_a_pending_entry_that_can_still_take_the_hour_holds_the_other_candidate(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ex = build(worlds, tmp_path)
    hide = {"on": True}
    hide_entries_of(w, "Z2-", hide)
    decide(w)
    w.to("2025-01-06 10:05:00", 103.0)
    w.bid(108.8)
    w.fake.orders_get()  # the SELL P1 fills between two cycles ...
    w.bid(103.0)  # ... and the quotes never show its touch
    w.step(2)
    assert w.runner.entries and w.runner.hour is not None and w.runner.hour.chosen is None
    w.to("2025-01-06 10:15:10", 101.3)  # a BUY touch in a later bar (no BUY fill: the ask is 101.50)
    w.step(2, 103.0)
    hide["on"] = False
    w.step(2)  # the SELL's deal is read: its earlier fill takes the hour
    sell, buy = w.runner.cands[2], w.runner.cands[1]
    assert w.runner.hour.chosen is sell
    assert buy.drop_reason == "other"  # dropped for the other's visit - never chosen first and eclipsed


def test_a_an_ordinary_stop_does_not_exit_while_a_filled_order_awaits_its_entry_deal(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    hide = {"on": True}
    hidden_entry_deals(w, hide)
    w.runner.gw.positions = lambda symbol=None: []  # type: ignore[method-assign, misc]
    decide(w)
    w.to("2025-01-06 10:05:00", 103.0)
    w.bid(101.0)
    w.fake.orders_get()  # the BUY P1 fills: only the order history shows it
    w.step(2, 103.0)
    assert w.runner.entries
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(2)
    assert w.orders() == [] and w.runner.stop_acked
    assert not w.runner.finished  # the filled order's entry is pending


# --- B: one judgement of the cycle's conditions -------------------------------------------------------------------


def test_b_the_stop_is_acknowledged_from_the_orders_read_though_the_history_keeps_failing(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.runner.gw.history_orders = fail  # type: ignore[method-assign]
    sid = w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(2)
    assert w.orders() == []
    assert w.runner.stop_acked
    row = w.store.stop(sid)
    assert row is not None and row.acknowledged_at is not None


def test_b_stop_now_exits_once_the_removals_are_confirmed_though_the_history_keeps_failing(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.runner.gw.history_orders = fail  # type: ignore[method-assign]
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(2)
    assert w.orders() == [] and w.runner.finished  # not only at the 60 s deadline
    assert w.store.pending_stop() is None


def test_b_a_failed_terminal_read_vetoes_placing_for_the_whole_cycle(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    real = w.runner.gw.terminal
    fails = {"n": 0}

    def terminal() -> Any:
        if fails["n"] > 0:
            fails["n"] -= 1
            raise OSError("terminal unavailable")
        return real()

    w.runner.gw.terminal = terminal  # type: ignore[method-assign]
    fails["n"] = 1  # the decision cycle's first terminal read fails; the later ones succeed
    w.to(HOUR0)
    assert ex.places() == []
    w.step(2)  # the next cycle reads everything: the decision
    assert len(w.names()) == 4


def stale_quotes_and_failing_positions(w: World) -> None:
    real_tick = w.runner.gw.tick

    def tick(symbol: str) -> Any:
        t = real_tick(symbol)
        return dataclasses.replace(t, time_utc=t.time_utc - timedelta(seconds=60))

    w.runner.gw.tick = tick  # type: ignore[method-assign]
    w.runner.gw.positions = fail  # type: ignore[method-assign]


def test_b_an_inherited_stale_condition_removes_nothing_while_the_market_is_closed(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    """The constructed series has no earlier weeks: with no quote newer than 30 s the market reads closed."""
    w, _ = build(worlds, tmp_path)
    decide(w)
    stale_quotes_and_failing_positions(w)
    w.step(2)  # the stale timer starts (a failed read); the cycle ends before its later steps
    w.step(960)  # more than one bar later, the market closed
    assert len(w.names()) == 4


def test_b_the_same_stale_condition_removes_the_orders_while_the_market_is_open(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.runner._market_closed = lambda now: False  # type: ignore[method-assign]
    stale_quotes_and_failing_positions(w)
    w.step(2)
    w.step(960)
    assert w.orders() == []
