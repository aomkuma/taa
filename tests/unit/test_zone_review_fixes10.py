# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 10 of the run-zone runner (eye/ZONE_LIVE.md L5 rule 3, L7, L8 "A broker condition ends only when it is
explained" and "Safety first in each cycle", L4 visit records).

R1. A broker condition (an unknown place, a pending entry, the stale data) ends only when its explanation is read:
    a position that disappears before its entry deal arrives keeps its block on placing and its timer; repeated
    failures of the forming H1 read never end the stale condition.
R2. The removals owed and the stop deadline come before every other step of a cycle, and an error in another step
    never holds them back.
T.  A blocked P1 whose fill test is met by the quotes (ask <= P1) cancels the setup at once; the bar's close only
    decides `cancel` or `no fill`.
V.  A setup's outcome is written to every visit row linked to it."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from app.broker import mt5_constants as c
from app.broker.execution import SendResult
from app.broker.retcodes import classify, describe
from app.zone.params import ZoneParams
from tests.unit.test_zone_handsoff_causes import (
    HOUR0,
    REFUSED,
    Lossy,
    build,
    decide,
    drop_entry_deals,
    stray_order,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import FILL, ts


class LostReply(Lossy):
    """Executes the listed comments at the broker and loses the answer (an unknown outcome)."""

    def __init__(self, inner: Any) -> None:
        super().__init__(inner)
        self.lost_reply: set[str] = set()

    def send(self, request: dict[str, Any]) -> SendResult:
        if str(request.get("comment", "")) in self.lost_reply:
            self.sent.append(dict(request))
            self.inner.send(request)
            return SendResult(None, classify(None), describe(None))
        return super().send(request)


def boom(*_a: Any, **_k: Any) -> None:
    raise RuntimeError("boom")


# --- R1: a broker condition ends only when it is explained ---------------------------------------------------------------


def test_r1_an_unknown_p1_found_as_a_position_that_vanishes_before_its_deal_keeps_placing_blocked(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, ex0 = build(worlds, tmp_path)
    ex = LostReply(ex0.inner)
    ex.lost_reply.add("Z1-P1-0")
    w.runner.exe = ex  # type: ignore[assignment]
    w.to(HOUR0)  # P1 placed, the answer lost
    w.bid(101.0)
    w.fake.orders_get()  # P1 fills at the broker ...
    drop_entry_deals(w)  # ... and its entry deal is not readable
    w.step(2)  # the position explains the place; the entry is pending
    w.to("2025-01-06 10:10:00", 101.0)
    w.fake.positions[:] = []  # the position disappears with no deal at all
    w.step(2)
    w.to("2025-01-06 10:12:00", 103.0)
    w.step(2)
    assert ex.places("Z1-P2") == []  # placing stays blocked until a deal explains the entry
    assert w.runner.hands_off is None  # one bar has not passed yet
    w.to("2025-01-06 10:16:10", 103.0)
    w.step(2)
    # cause 3, timed from the sighting of the position (the magic is flat, so the hands-off ends at once)
    assert any(
        "without its entry deal" in r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR
    )
    assert ex.places("Z1-P2") == []


def hidden_entry_deals(w: Any, hide: dict[str, bool]) -> None:
    real = w.runner.gw.deals

    def deals(start: Any, end: Any) -> Any:
        got = real(start, end)
        return [d for d in got if d.entry != c.DEAL_ENTRY_IN] if hide["on"] else got

    w.runner.gw.deals = deals


def unknown_then_position_at_1014(worlds: list, tmp_path: Path) -> tuple[Any, dict[str, bool], LostReply]:  # type: ignore[type-arg]
    w, ex0 = build(worlds, tmp_path)
    ex = LostReply(ex0.inner)
    ex.lost_reply.add("Z1-P1-0")
    w.runner.exe = ex  # type: ignore[assignment]
    hide = {"on": True}
    hidden_entry_deals(w, hide)
    w.to(HOUR0)  # sent at 10:00, no answer; the order rests at the broker
    w.bid(101.0)
    w.fake.orders_get()  # filled at the broker before the runner's next cycle
    w.to("2025-01-06 10:14:00", 101.0)  # first seen as a position, its deal not readable yet
    return w, hide, ex


def test_r1_an_unknown_place_seen_as_a_position_late_is_timed_from_the_sighting(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, hide, _ = unknown_then_position_at_1014(worlds, tmp_path)
    w.to("2025-01-06 10:15:10", 101.0)  # a bar after the place, not after the sighting
    assert w.runner.hands_off is None
    hide["on"] = False
    w.to("2025-01-06 10:16:00", 101.0)  # its entry deal is read
    w.step(2)
    assert w.runner.hands_off is None
    assert "P1" in w.runner.cands[1].fills


def test_r1_a_position_seen_and_never_explained_for_a_bar_is_hands_off(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    w, _hide, _ = unknown_then_position_at_1014(worlds, tmp_path)
    w.to("2025-01-06 10:28:30", 101.0)
    assert w.runner.hands_off is None
    w.to("2025-01-06 10:30:10", 101.0)
    assert w.runner.hands_off is not None
    assert any(
        "without its entry deal" in r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR
    )


def test_r1_repeated_failures_of_the_forming_h1_read_reach_the_stale_removal(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    assert len(w.names()) == 4

    def fail() -> None:
        raise OSError("forming bar unavailable")

    w.src.forming_h1 = fail  # type: ignore[method-assign]
    for _ in range(18):  # 18 minutes of a read that fails every cycle
        w.step(60)
    assert w.orders() == []  # the stale data was never explained away: the orders are removed
    assert w.runner.hands_off is None


# --- R2: safety first in each cycle --------------------------------------------------------------------------------


def test_r2_hands_off_removals_do_not_wait_for_the_bars_step(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.fake.orders.append(stray_order())
    w.runner._advance = boom  # type: ignore[method-assign]
    w.step(2)
    w.step(2)
    assert w.orders() == []
    assert w.runner.hands_off is not None


def test_r2_stop_now_finishes_after_60_seconds_whatever_another_step_does(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.runner._advance = boom  # type: ignore[method-assign]
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)
    w.step(30)
    assert not w.runner.finished
    w.step(35)
    assert w.runner.finished


def test_r2_the_stop_deadline_is_checked_before_the_broker_is_read(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.store.request_stop(w.clock.now_utc(), "tester", now_flag=True)
    w.step(2)

    def fail(*_a: Any, **_k: Any) -> None:
        raise OSError("down")

    w.runner.gw.account = fail  # type: ignore[method-assign]
    w.step(65)
    assert w.runner.finished


def test_r2_an_order_judged_not_wanted_earlier_is_removed_before_any_other_step(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    real = w.runner._wants
    w.runner._wants = lambda *a, **k: False  # type: ignore[method-assign]
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.step(2)  # judged not wanted; the removals are refused
    assert len(w.names()) == 4
    ex.refuse_action.clear()
    w.runner._wants = real  # type: ignore[method-assign]
    seen: list[int] = []

    def steps(_ctx: Any) -> None:
        seen.append(len(w.orders()))  # the other steps start after the removals owed
        raise RuntimeError("boom")

    w.runner._steps = steps  # type: ignore[method-assign]
    w.step(2)
    assert seen == [0]


# --- T: a blocked P1 touched in the quotes ------------------------------------------------------------------------------


def test_t_a_blocked_p1_met_by_the_ask_cancels_the_setup_even_when_the_bars_spread_hides_it(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    # c = 2.0: BUY P1 101.32 is blocked in bar j0 (open 104.5 an hour ago: 3.18) and free in the next (open 103: 1.68).
    # The ask (bid 100.9 + spread) meets P1 during j0; the bar spread (0.5) puts low + spread above P1, so its close misses it.
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
    assert w.names() == []  # blocked
    w.step(60, 100.9)  # the ask is under P1
    w.to("2025-01-06 10:15:02", 103.0)
    row = w.store.setup(1)
    assert (row.state, row.outcome) == ("ended", "cancel")
    w.step(2)
    w.to("2025-01-06 10:20:00", 103.0)
    assert not any(o.comment.startswith("Z1") for o in w.orders())


# --- V: the outcome reaches every visit row of the setup ---------------------------------------------------------------


def test_v_the_outcome_is_written_to_every_visit_row_linked_to_the_setup(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    t = ts("2025-01-06 09:00").to_pydatetime()
    base = {"hour_open": t, "side": "BUY", "line": 100.0, "agreed": True, "note": ""}
    w.store.add_visits(
        t + timedelta(hours=1),
        [
            {**base, "classification": "setup", "setup_id": 7, "outcome": None},
            {**base, "classification": "busy", "setup_id": 7, "outcome": None},
            {**base, "classification": "busy", "setup_id": None, "outcome": None},
        ],
    )
    w.store.set_visit_outcome(7, "cancel")
    got = [(r.classification, r.setup_id, r.outcome) for r in w.store.visits()]
    assert got == [("setup", 7, "cancel"), ("busy", 7, "cancel"), ("busy", None, None)]
