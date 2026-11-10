# ruff: noqa: F811 - the shared fixture `worlds` is imported and used as an argument
"""Sol review 7 of the run-zone runner (eye/ZONE_LIVE.md L3, L5, L7, L8), point by point.

1. P1 is removed only once its setup's P2 is confirmed gone: a refused or unknown P2 removal keeps P1 resting
   (L3 "P2 never rests without P1 placed or filled"; L8 "P2 before P1 of the same setup") - in the normal
   cleanup and at a start. A P2 whose place is of unknown outcome is not waited for - appearing after its P1
   went, it is not wanted: removed at once, a fill of it closed (L5: a fill after the setup ended).
2. A fill of a placement already superseded is closed at market (L5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.broker import mt5_constants as c
from app.broker.execution import SendResult
from app.broker.retcodes import classify, describe
from app.zone import live
from tests.unit.test_zone_trader import flaky, restart, world, worlds  # noqa: F401 - the fixture
from tests.unit.zone_live_support import World


class RefuseRemoval:
    """The execution with the removal of chosen order tickets refused (``code``) or unanswered (``None``)."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.tickets: dict[int, int | None] = {}  # order ticket -> retcode (None: no reply, not executed)

    def check(self, request: dict[str, Any]) -> Any:
        return self.inner.check(request)

    def send(self, request: dict[str, Any]) -> SendResult:
        if request.get("action") == c.TRADE_ACTION_REMOVE and request.get("order") in self.tickets:
            code = self.tickets[int(request["order"])]
            return SendResult(code, classify(code), describe(code))
        res: SendResult = self.inner.send(request)
        return res


def refusing(w: World) -> RefuseRemoval:
    r = RefuseRemoval(w.runner.exe)
    w.runner.exe = r  # type: ignore[assignment]
    return r


def ticket_of(w: World, comment: str) -> int:
    [o] = [o for o in w.orders() if o.comment == comment]
    return int(o.ticket)


def p2_alone(w: World) -> list[str]:
    """P2 orders resting with neither a P1 order resting nor a P1 filled for their setup."""
    out = []
    keys = [live.parse_comment(o.comment) for o in w.orders()]
    filled = {k[0] for p in w.positions() if (k := live.parse_comment(p.comment)) and k[1] == "P1"}
    for k in keys:
        if (
            k is not None
            and k[1] == "P2"
            and not any(o is not None and o[0] == k[0] and o[1] == "P1" for o in keys)
            and k[0] not in filled
        ):
            out.append(live.make_comment(*k))
    return out


def test_a_refused_p2_removal_keeps_p1_in_the_normal_cleanup(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0", "Z2-P1-0", "Z2-P2-0"]
    r = refusing(w)
    r.tickets[ticket_of(w, "Z1-P2-0")] = 10013  # INVALID: the broker refuses this one removal
    w.kill.activate("test", "t", "test")  # L7: every resting entry is removed
    w.step(2)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"] and p2_alone(w) == []  # Z2 went whole; Z1's P1 waits
    w.step(2)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"] and p2_alone(w) == []
    r.tickets.clear()
    w.step(2)  # P2 goes first; P1 goes once its removal is confirmed
    assert w.names() == [] and p2_alone(w) == []


def test_an_unknown_p2_removal_keeps_p1_until_p2_is_seen_gone(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    r = refusing(w)
    r.tickets[ticket_of(w, "Z2-P2-0")] = None  # no reply: the order may or may not be gone
    w.kill.activate("test", "t", "test")
    w.step(2)
    assert w.names() == ["Z2-P1-0", "Z2-P2-0"] and p2_alone(w) == []
    r.tickets.clear()
    w.step(2)
    assert w.names() == [] and p2_alone(w) == []


def test_a_refused_p2_removal_at_a_restart_keeps_p1(worlds: list[World], tmp_path: Path) -> None:
    w = world(worlds, tmp_path)
    w.step(2)
    blocked = ticket_of(w, "Z1-P2-0")
    r = refusing(w)
    r.tickets[blocked] = 10013
    w2 = restart(w, worlds)  # L8: not flat - hands-off: every resting order is removed, P2 before P1
    assert w2.names() == ["Z1-P1-0", "Z1-P2-0"] and p2_alone(w2) == []
    assert w2.runner.hands_off is not None  # orders rest: hands-off until the magic is flat
    r.tickets.clear()
    w2.step(2)
    assert w2.names() == [] and p2_alone(w2) == []


def hide_orders(w: World, comments: set[str]) -> None:
    real = w.runner.gw.orders

    def orders(symbol: str | None = None) -> list[Any]:
        return [o for o in real(symbol) if o.comment not in comments]

    w.runner.gw.orders = orders  # type: ignore[method-assign]


def late_p2(worlds: list[World], tmp_path: Path) -> tuple[World, set[str]]:
    """Z1's P2 is placed with no answer and is not visible yet; then the kill switch removes Z1's P1 - the
    runner does not wait for the invisible P2."""
    w = world(worlds, tmp_path, start=False)
    f = flaky(w)
    f.no_reply_executed.add("Z1-P2-0")  # executed at the broker, the answer lost
    hidden = {"Z1-P2-0"}
    hide_orders(w, hidden)
    w.runner.start()
    w.step(2)  # the 10:00 decision
    w.kill.activate("test", "t", "test")
    w.step(2)
    assert [r.state for r in w.store.requests(kinds=("place",)) if r.comment == "Z1-P2-0"] == ["unknown"]
    assert not any(o.comment == "Z1-P1-0" for o in w.orders())  # P1 removed: P2 was not waited for
    assert w.store.setup(1).outcome == "interrupted"  # L7
    return w, hidden


def test_a_late_p2_after_its_p1_was_removed_is_removed_at_once(worlds: list[World], tmp_path: Path) -> None:
    w, hidden = late_p2(worlds, tmp_path)
    hidden.clear()  # the P2 shows up
    w.step(2)
    assert w.names() == [] and w.positions() == []


def test_a_fill_of_a_late_p2_after_its_p1_was_removed_is_closed(worlds: list[World], tmp_path: Path) -> None:
    w, _hidden = late_p2(worlds, tmp_path)
    w.step(2, 97.5)  # the still invisible P2 fills (ask 97.7 <= 98.03)
    w.step(2, 97.5)
    assert not any(p.comment == "Z1-P2-0" for p in w.positions())  # closed at market
    assert any(d.comment == "Z1-P2-0" and d.entry == c.DEAL_ENTRY_IN for d in w.fake.deals)  # it did fill
    assert len(w.store.requests(kinds=("close",))) == 1  # one close: a fill after the setup's end


def test_a_fill_of_a_superseded_placement_is_closed(worlds: list[World], tmp_path: Path) -> None:
    """L3 / L5: the pre-close window removes Z1-P1-0 and the next bar places Z1-P1-1; the old order appearing
    and filling is a fill of a superseded placement - closed at market, never the setup's fill."""
    import copy

    from app.zone.params import ZoneParams
    from tests.unit.test_zone_trader import bar

    rows129 = [
        bar(103, 104, 102, 103),
        bar(105, 106, 104, 105),
        bar(103, 104, 102, 103),
        bar(103, 104, 102, 103),
    ]
    w = world(worlds, tmp_path, exec_rows={129: rows129}, params=ZoneParams())
    w.step(2)
    assert w.names() == ["Z1-P1-0", "Z1-P2-0"]  # L5 rule 3: P1 is free, P2 has no block of its own
    old = copy.copy(next(o for o in w.fake.orders if o.comment == "Z1-P1-0"))
    w.to("2025-01-06 10:14:50", 103)  # the coming bar blocks P1: removed ahead
    w.to("2025-01-06 10:30:02", 103)  # allowed again: the next placement
    assert w.names() == ["Z1-P1-1", "Z1-P2-1"]  # both placed again (P2 follows P1's rules, L5 rule 3)
    w.fake.orders.append(old)  # the old P1 appears - and fills - before the next cycle
    w.step(2, 101.0)
    w.step(2, 101.0)
    assert any(d.comment == "Z1-P1-0" and d.entry == c.DEAL_ENTRY_IN for d in w.fake.deals)
    assert [p.comment for p in w.positions()] == ["Z1-P1-1"]  # the new placement is the setup's fill
    assert w.runner.cands[1].fills["P1"].key == (1, "P1", 1)
    assert len(w.store.requests(kinds=("close",))) == 1  # exactly one close: the old P1
