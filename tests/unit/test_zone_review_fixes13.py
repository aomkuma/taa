# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 13 of the run-zone runner (eye/ZONE_LIVE.md L2, L4, L5, L7, L8, L10), by root.

1. The expected bar (L2): a closed bar is expected once this process read a quote inside it, every frame alike
   (D1, H4, H1, exec_tf); until it is readable the data is not fresh and no hour begins.
2. What can still open a position unseen (L5, L10): a setup waiting for its entry deal keeps its orders as they are
   (no withdrawal, no removal by its rules - safety removals go on); an ordinary stop exits only when nothing of
   ours can still open a position unseen; every --now exit first ends the setups known without a fill.
3. Owed removals and their reason (L7, L2): the stale debt is latched when it falls due and outlives the market's
   close; a stale-only removal waits while the market is closed.
4. An outcome kept (L4): a candidate dropped for the other's visit keeps its life outcome until the hour's close.
5. Evidence under hands-off (L5): an entry deal read under hands-off is recorded on its placement, never judged."""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from app.broker import mt5_constants as c
from app.zone.params import ZoneParams
from tests.unit.test_zone_handsoff_causes import (
    HOUR0,
    REFUSED,
    build,
    decide,
    stray_order,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.test_zone_review_fixes11 import pending_entry
from tests.unit.test_zone_review_fixes12 import hide_entries_of, late_bars
from tests.unit.zone_live_support import FILL, World, ts


def fail(*_a: Any, **_k: Any) -> Any:
    raise OSError("unavailable")


def removes(ex: Any) -> int:
    return sum(1 for r in ex.sent if r.get("action") == c.TRADE_ACTION_REMOVE)


def market(w: World, closed: bool = False) -> dict[str, bool]:
    """The market's closed state as the test sets it (the constructed series has no earlier weeks)."""
    state = {"closed": closed}
    w.runner._market_closed = lambda now: state["closed"]  # type: ignore[method-assign]
    return state


def quotes(w: World) -> dict[str, bool]:
    """Quotes 60 s old while ``stale['on']`` (older than the 30 s of stale_quote_seconds)."""
    real = w.runner.gw.tick
    stale = {"on": False}

    def tick(symbol: str) -> Any:
        t = real(symbol)
        return dataclasses.replace(t, time_utc=t.time_utc - timedelta(seconds=60)) if stale["on"] else t

    w.runner.gw.tick = tick  # type: ignore[method-assign]
    return stale


# --- 1: the expected bar --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tf", "opens"),
    [
        ("D1", "2025-01-05 22:00"),
        ("H4", "2025-01-06 18:00"),
    ],  # both close at 22:00 UTC, the server's midnight
)
def test_1_a_late_d1_or_h4_bar_closed_at_the_open_holds_the_decision(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    tf: str,
    opens: str,
) -> None:
    w, ex = build(worlds, tmp_path, now="2025-01-06 21:59:50")
    late = late_bars(w, tf, ts(opens))  # both broker reads still report the older bar
    w.to("2025-01-06 22:00:05")
    w.step(2)
    assert ex.places() == [] and w.runner.cands == {}  # the grid in force at the hour is not known yet
    late["on"] = False
    w.step(2)  # read and processed inside the 60 s of the hour's first quote
    assert len(w.names()) == 4


def test_1_an_expected_exec_bar_not_readable_makes_the_data_not_fresh(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    late = late_bars(w, "M15", ts("2025-01-06 10:00"))  # the 10:00 bar: quotes were read in it
    w.to("2025-01-06 10:15:05")
    assert w.runner.stale_since is not None  # not fresh: placing stops, the stale timer runs (L7)
    assert len(w.names()) == 4
    w.to("2025-01-06 10:30:10")  # more than one bar later, still not readable
    assert w.orders() == []  # L7: the resting orders are removed
    late["on"] = False


# --- 2: what can still open a position unseen -----------------------------------------------------------------------


def test_2_a_setup_waiting_for_its_entry_deal_keeps_its_orders_through_a_withdrawal_quote(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    hide = {"on": True}
    hide_entries_of(w, "Z1-", hide)
    decide(w)
    p2 = next(o.ticket for o in w.orders() if o.comment == "Z1-P2-0")
    w.to("2025-01-06 10:14:00", 101.0)
    w.fake.orders_get()  # the BUY P1 fills at 10:14, its deal not readable yet
    w.step(2, 103.0)
    assert w.runner.entries
    w.to("2025-01-06 10:15:05", 105.5)  # bar 521: a quote at the withdrawal level (L + away = 105)
    w.step(2)
    assert "Z1-P2-0" in w.names()  # its orders' judgements wait for the entry deal
    hide["on"] = False
    w.step(2, 103.0)  # the deal: P1 filled at 10:14 - rules 1 - 3 no longer apply, P2 rests
    w.step(2)
    assert "P1" in w.runner.cands[1].fills
    assert "Z1-P2-0" in w.names()
    assert not [r for r in ex.sent if r.get("action") == c.TRADE_ACTION_REMOVE and r.get("order") == p2]


def test_2_an_ordinary_stop_does_not_exit_while_a_place_of_unknown_outcome_is_unexplained(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    ex.lose.add("Z1-P1-0")  # sent, never answered, not executed: of unknown outcome
    w.to(HOUR0)
    w.step(2)
    assert w.runner.unknown_since
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(2)
    assert w.orders() == [] and w.runner.stop_acked
    assert not w.runner.finished  # the place may still open a position unseen
    w.to("2025-01-06 10:15:10", 103.0)  # L8 cause 1: not found within one bar - hands-off (the magic flat)
    assert w.runner.finished


def blocked_world(worlds: list, tmp_path: Path) -> tuple[World, Any]:  # type: ignore[type-arg]
    """Two live candidates whose P1 is blocked at j0 (rule 3): no order rests."""
    rows129 = [(104.5, 105.0, 102.5, 103.0), FILL, FILL, FILL]
    rows130 = [(103.0, 104.0, 102.0, 103.0), FILL, FILL, FILL]
    w, ex = build(
        worlds,
        tmp_path,
        exec_rows={129: rows129, 130: rows130},
        params=ZoneParams(cancel_frac=0.2),
        spread=50,
    )
    w.to(HOUR0, 103.0)
    w.step(2)
    assert w.orders() == [] and {cd.is_live for cd in w.runner.cands.values()} == {True}
    return w, ex


def test_2_a_stop_now_exit_ends_the_setups_known_without_a_fill_interrupted(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = blocked_world(worlds, tmp_path)
    ids = sorted(w.runner.cands)
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    assert w.runner.finished
    assert [w.store.setup(i).outcome for i in ids] == ["interrupted", "interrupted"]


def test_2_the_stop_now_timeout_exit_ends_the_setups_known_without_a_fill_interrupted(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED  # the removals are never confirmed
    w.runner.gw.positions = fail  # type: ignore[method-assign]  # and the later steps never run
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(30)
    assert not w.runner.finished
    w.step(35)  # the 60 s
    assert w.runner.finished and len(w.orders()) == 4
    assert [w.store.setup(i).outcome for i in (1, 2)] == ["interrupted", "interrupted"]


# --- 3: owed removals and their reason ------------------------------------------------------------------------------


def test_3_a_stale_removal_owed_at_the_close_is_sent_after_the_reopening(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)  # 10:00:07
    mkt = market(w)
    stale = quotes(w)
    real_positions = w.runner.gw.positions
    w.runner.gw.positions = fail  # type: ignore[method-assign]  # the later reads fail: the stale timer runs
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.step(2)
    w.to("2025-01-06 10:15:15")  # more than one bar: the removals are owed (and refused)
    assert removes(ex) > 0 and len(w.orders()) == 4
    w.runner.gw.positions = real_positions  # type: ignore[method-assign]
    stale["on"], mkt["closed"] = True, True  # the market closes
    w.step(2)
    w.step(2)
    stale["on"], mkt["closed"] = False, False  # it reopens with fresh data
    del ex.refuse_action[c.TRADE_ACTION_REMOVE]
    w.step(2)
    w.step(2)
    assert w.orders() == []  # the debt was kept through the close
    assert [w.store.setup(i).outcome for i in (1, 2)] == ["interrupted", "interrupted"]


def test_3_a_stale_only_removal_is_not_retried_while_the_market_is_closed(
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
    w.to("2025-01-06 10:15:15")  # the stale removals are owed and refused
    assert removes(ex) > 0 and len(w.orders()) == 4
    sent = removes(ex)
    mkt["closed"] = True
    w.step(2)
    w.step(2)
    assert removes(ex) == sent  # L7: nothing is stale-removed while the market is closed
    mkt["closed"] = False
    w.step(2)
    assert removes(ex) > sent  # owed still: sent at the first cycle after the reopening


# --- 4: an outcome kept ---------------------------------------------------------------------------------------------


def test_4_a_candidate_dropped_after_its_cancel_keeps_that_outcome_when_a_missed_touch_gives_it_the_hour(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    # 10:00 bar closes 101.40: at 10:15 the closed-hour cancel of the BUY (open an hour ago 103.50 - 101.40 =
    # 2.1 >= 0.2 x 10), decided `cancel` at 10:30; 10:30 bar: the SELL visited by a quote, and the bar's low
    # reaches the BUY's zone - the BUY's touch in that bar comes first in the candidates' order (nearer o)
    rows129 = [(103.0, 103.6, 102.6, 103.5), (103.5, 103.6, 102.6, 103.0), FILL, FILL]
    rows130 = [
        (103.0, 103.2, 101.35, 101.4),
        (101.4, 102.0, 101.35, 101.8),
        (101.8, 108.8, 101.2, 103.0),
        FILL,
    ]
    w, _ = build(
        worlds,
        tmp_path,
        exec_rows={129: rows129, 130: rows130},
        params=ZoneParams(cancel_frac=0.2, away_frac=2.0),
    )
    w.to(HOUR0, 103.0)
    w.step(2)
    buy, sell = w.runner.cands[1], w.runner.cands[2]
    assert (buy.side, sell.side) == ("BUY", "SELL")
    w.to("2025-01-06 10:30:05", 103.0)
    assert buy.outcome == "cancel"
    w.to("2025-01-06 10:35:00", 108.75)  # the SELL's visit: it takes the hour
    assert w.runner.hour is not None and w.runner.hour.chosen is sell
    w.to("2025-01-06 10:45:05", 103.0)  # the 10:30 bar's close: the BUY's missed touch takes the hour back
    assert w.runner.hour.chosen is buy
    assert (buy.outcome, buy.dropped) == ("cancel", False)
    assert w.runner.res_by.get(buy.id) == ts("2025-01-06 10:30")  # it reserves by its cancel (L6)


# --- 5: evidence under hands-off ------------------------------------------------------------------------------------


def test_5_an_entry_deal_read_under_hands_off_is_recorded_on_its_placement_and_never_judged(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex, hide = pending_entry(worlds, tmp_path)
    w.fake.orders.append(stray_order())  # cause 4: hands-off at once
    w.step(2)
    assert w.runner.hands_off is not None
    hide["on"] = False
    w.step(2)
    row = w.store.request_by_comment("Z1-P1-0")
    assert row is not None and row.order_state == "filled"
    assert row.deal_ticket is not None and row.position_ticket is not None
    cand = w.runner.cands.get(1)
    assert cand is None or "P1" not in cand.fills  # recorded only: no fill judged
    assert not [r for r in ex.sent if r.get("action") == c.TRADE_ACTION_DEAL and r.get("position")]
