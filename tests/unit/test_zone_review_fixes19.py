# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 18 of the run-zone runner (eye/ZONE_LIVE.md L1, L7, L8, L10).

A. An exit or a resumption is judged on the current state: every exit needs the removals confirmed at that moment
   (not an earlier acknowledgement); L7 and a stop interrupt every unfinished row without a fill, a candidate
   dropped for the other's visit included.
B. A gate failure read at the pre-placement check is the gate failing (L7): the removals and the interruption are
   owed, and nothing more is placed in that cycle.
C. The L8 checks that need only the account and the orders run on those reads alone: an order of the magic that is
   not ours (cause 4), a removal not done within one bar (cause 6)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.broker import mt5_constants as c
from app.broker.execution import SendResult
from app.broker.retcodes import classify, describe
from tests.unit.test_zone_handsoff_causes import (
    HOUR0,
    REFUSED,
    Lossy,
    build,
    decide,
    stray_order,
    worlds,  # noqa: F401 - the fixture
)
from tests.unit.zone_live_support import FILL, World


def fail(*_a: Any, **_k: Any) -> Any:
    raise OSError("unavailable")


class Broker(Lossy):
    """Executes the listed comments and loses the answer; refuses the removal of the listed tickets."""

    def __init__(self, inner: Any) -> None:
        super().__init__(inner)
        self.lost_reply: set[str] = set()
        self.keep: set[int] = set()

    def send(self, request: dict[str, Any]) -> SendResult:
        if request.get("action") == c.TRADE_ACTION_REMOVE and int(request.get("order", 0)) in self.keep:
            self.sent.append(dict(request))
            return SendResult(REFUSED, classify(REFUSED), describe(REFUSED))
        if str(request.get("comment", "")) in self.lost_reply:
            self.sent.append(dict(request))
            self.inner.send(request)
            return SendResult(None, classify(None), describe(None))
        return super().send(request)


def broker(w: World) -> Broker:
    b = Broker(w.runner.exe.inner)  # type: ignore[attr-defined]
    w.runner.exe = b
    return b


def hide_orders(w: World, hidden: set[str]) -> None:
    real = w.runner.gw.orders

    def orders(symbol: str | None = None) -> list[Any]:
        return [o for o in real(symbol) if o.comment not in hidden]

    w.runner.gw.orders = orders  # type: ignore[method-assign]


# --- A ----------------------------------------------------------------------------------------------------------------


def test_a_a_stop_never_exits_on_an_earlier_acknowledgement_while_an_order_rests(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    b = broker(w)
    b.lost_reply.add("Z1-P1-0")  # placed at the broker, the answer lost ...
    hidden = {"Z1-P1-0"}
    hide_orders(w, hidden)  # ... and not visible yet
    w.to(HOUR0)
    w.step(2)
    assert w.runner.unknown_since
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2)
    w.step(2)
    assert w.runner.stop_acked  # the visible orders are gone
    hidden.clear()  # the order shows up: found, ours, resting - and its removal is refused
    b.keep |= {o.ticket for o in w.orders() if o.comment == "Z1-P1-0"}
    w.step(2)
    w.step(2)
    assert [o.comment for o in w.orders()] == ["Z1-P1-0"]
    assert not w.runner.finished  # the removals are not confirmed now
    b.keep.clear()
    w.step(2)
    w.step(2)
    assert w.orders() == [] and w.runner.finished


def bars_for_a_later_missed_touch() -> dict[int, list[tuple[float, float, float, float]]]:
    # the 10:15 bar's low reaches the BUY's zone: a missed BUY touch in the SELL's visit bar, nearer the open
    return {130: [FILL, (103.0, 108.8, 101.0, 103.0), FILL, FILL]}


def test_a_the_kill_switch_interrupts_a_candidate_dropped_for_the_others_visit(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path, exec_rows=bars_for_a_later_missed_touch())
    decide(w)
    w.to("2025-01-06 10:20:00", 108.75)  # the SELL's visit (its P1 fills): the hour's setup; the BUY dropped
    w.step(2, 106.0)
    assert w.runner.cands[2].chosen and w.runner.cands[1].dropped
    w.kill.activate("test", "t", "test")
    w.step(2)
    assert w.store.setup(1).outcome == "interrupted"  # L7: a candidate without a fill
    w.kill.release("test", "t")
    places = len(ex.places("Z1-"))
    w.to("2025-01-06 10:30:05", 106.0)  # the bar's missed BUY touch: an interrupted candidate takes nothing
    w.step(2)
    assert w.runner.hour is not None and w.runner.hour.chosen is w.runner.cands[2]
    assert len(ex.places("Z1-")) == places


def test_a_a_stop_ends_a_candidate_dropped_for_the_others_visit_interrupted(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.to("2025-01-06 10:05:00", 101.3)  # a BUY touch on the bid, no fill: the hour's setup; the SELL dropped
    assert w.runner.cands[1].chosen and w.runner.cands[2].dropped
    w.store.request_stop(w.clock.now_utc(), "tester")
    w.step(2, 103.0)
    w.step(2)
    assert [w.store.setup(i).outcome for i in (1, 2)] == ["interrupted", "interrupted"]


# --- B ----------------------------------------------------------------------------------------------------------------


def test_b_a_gate_failure_at_the_pre_placement_check_stops_the_cycles_placing_and_interrupts(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    real_gate = w.runner._gate
    calls = {"n": 0}

    def gate(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        if "ctx" in kwargs:  # the fresh check before a place request
            calls["n"] += 1
            if calls["n"] == 2:  # BUY P1 went; the check before BUY P2 fails
                return False, "margin: not enough"
        return real_gate(*args, **kwargs)

    w.runner._gate = gate  # type: ignore[method-assign]
    w.to(HOUR0)
    assert [r["comment"] for r in ex.places()] == ["Z1-P1-0"]  # nothing more in that cycle
    w.step(2)
    w.step(2)
    assert [w.store.setup(i).outcome for i in (1, 2)] == ["interrupted", "interrupted"]
    assert w.orders() == []


# --- C ----------------------------------------------------------------------------------------------------------------


def test_c_an_order_of_the_magic_not_ours_is_hands_off_though_the_positions_cannot_be_read(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, _ = build(worlds, tmp_path)
    decide(w)
    w.runner.gw.positions = fail  # type: ignore[method-assign]
    w.fake.orders.append(stray_order())
    w.step(2)
    assert w.runner.hands_off is not None and "not ours" in w.runner.hands_off
    w.step(2)
    assert not [o for o in w.orders() if o.comment.startswith("Z")]  # its orders removed (L8)


def test_c_a_refused_removal_turns_hands_off_after_one_bar_though_the_positions_cannot_be_read(
    worlds: list,  # type: ignore[type-arg]
    tmp_path: Path,
) -> None:
    w, ex = build(worlds, tmp_path)
    decide(w)
    w.runner.gw.positions = fail  # type: ignore[method-assign]
    ex.refuse_action[c.TRADE_ACTION_REMOVE] = REFUSED
    w.kill.activate("test", "t", "test")
    w.step(2)  # the removals owed, refused
    w.to("2025-01-06 10:16:30")  # more than one bar later
    assert w.runner.hands_off is not None and "removal" in w.runner.hands_off
