"""A crash or a restart at any step of a scripted day (eye/ZONE_LIVE.md L8, L11.3): whatever the moment, the runner
never places one order twice, never places before its first decision nor for a setup of an earlier process, never
leaves a position of the magic unmanaged outside hands-off (under hands-off the positions are the broker's) and
never moves a stop against a position. Each scenario is played once with no stop to count its sends, then with a
restart before every step and with a process death before / after every send."""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Any

import pytest

from app.broker import mt5_constants as c
from app.broker.execution import SendResult
from app.zone import live
from app.zone.trader import _ts
from tests.unit.test_zone_trader import (
    bar,
    hour_rows,
    restart,
    world,
)
from tests.unit.zone_live_support import World

Step = tuple[str, float]
SCENARIOS: dict[str, tuple[dict[int, Any], list[Step], float]] = {
    # fill, break-even, TP exit, the next hour
    "fill_be_tp": (
        {130: hour_rows(bar(103, 105.9, 101.0, 105.8), bar(105.8, 110.5, 105.5, 110.5))},
        [
            ("2025-01-06 10:00:07", 103.0),
            ("2025-01-06 10:02:07", 101.0),
            ("2025-01-06 10:08:00", 105.7),
            ("2025-01-06 10:15:02", 105.7),
            ("2025-01-06 10:20:00", 110.2),
            ("2025-01-06 10:21:00", 110.2),
            ("2025-01-06 11:00:03", 103.0),
            ("2025-01-06 11:01:03", 103.0),
        ],
        103.0,
    ),
    # P1 and P2 both fill, then the break-even moves both stops
    "p1_p2": (
        {130: hour_rows(bar(103, 105.9, 97.4, 105.8))},
        [
            ("2025-01-06 10:00:07", 103.0),
            ("2025-01-06 10:02:07", 101.0),
            ("2025-01-06 10:04:07", 97.4),
            ("2025-01-06 10:08:00", 105.0),
            ("2025-01-06 10:15:02", 105.0),
            ("2025-01-06 10:17:00", 105.0),
        ],
        103.0,
    ),
    # a visit, a withdrawal, the hour change
    "withdrawal": (
        {130: hour_rows(bar(103, 104, 101.2, 101.2), bar(101.2, 105.5, 101.2, 105.0))},
        [
            ("2025-01-06 10:00:07", 103.0),
            ("2025-01-06 10:05:00", 101.2),
            ("2025-01-06 10:16:00", 105.2),
            ("2025-01-06 10:31:00", 103.0),
            ("2025-01-06 11:00:03", 103.0),
            ("2025-01-06 11:30:00", 103.0),
        ],
        103.0,
    ),
    # a missed touch (in the bar after the decision's, L4) makes the other candidate the setup: the first one's
    # position is an owed close
    "owed_close": (
        {130: hour_rows(bar(107, 107.5, 106.5, 107.0), bar(107, 109.0, 101.0, 106.0))},
        [
            ("2025-01-06 10:00:07", 107.0),
            ("2025-01-06 10:17:00", 101.0),
            ("2025-01-06 10:19:00", 101.0),
            ("2025-01-06 10:30:02", 106.0),
            ("2025-01-06 10:31:30", 106.0),
            ("2025-01-06 10:45:03", 106.0),
        ],
        107.0,
    ),
}


class Probe:
    """The execution seen from outside: it checks every request against the invariants and can die on the n-th."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.holder: World | None = None
        self.n = 0
        self.die_at: int | None = None
        self.die_after = False
        self.places: list[str] = []
        self.violations: list[str] = []

    def check(self, request: dict[str, Any]) -> Any:
        return self.inner.check(request)

    def send(self, request: dict[str, Any]) -> SendResult:
        w = self.holder
        assert w is not None
        action = request.get("action")
        idx = self.n
        self.n += 1
        is_place = action == c.TRADE_ACTION_PENDING or (
            action == c.TRADE_ACTION_DEAL and not request.get("position")
        )
        if is_place:
            self._check_place(w, str(request.get("comment", "")))
        elif action == c.TRADE_ACTION_SLTP:
            self._check_stop(w, request)
        if self.die_at == idx and not self.die_after:
            self.die_at = None
            raise SystemExit("died before the send")
        res: SendResult = self.inner.send(request)
        if self.die_at == idx:
            self.die_at = None
            raise SystemExit("died after the send")
        return res

    def _check_place(self, w: World, comment: str) -> None:
        key = live.parse_comment(comment)
        runner = w.runner
        if key is None:
            self.violations.append(f"place without a key: {comment}")
            return
        sid, name, _n = key
        if comment in self.places:
            self.violations.append(f"{comment} sent twice")
        self.places.append(comment)
        if runner.decide_from is None:
            self.violations.append(f"{comment} placed before the first decision")
        if runner.hands_off is not None:
            self.violations.append(f"{comment} placed under hands-off")
        row = w.store.setup(sid)
        if row is None or runner.started_at is None or _ts(row.created_at) < runner.started_at:
            self.violations.append(f"{comment} belongs to a setup made before this process")
        elif runner.decide_from is not None and _ts(row.hour_open) < runner.decide_from:
            self.violations.append(f"{comment} is of an hour before the first decision")
        for o in w.fake.orders:
            ok = live.parse_comment(o.comment)
            if ok is None:
                continue
            orow = w.store.setup(ok[0])
            if (
                orow is not None
                and runner.started_at is not None
                and _ts(orow.created_at) < runner.started_at
            ):
                self.violations.append(f"{comment} placed while the old order {o.comment} rests")
            if ok[:2] == (sid, name):
                self.violations.append(f"{comment} placed while {o.comment} rests")
        for p in w.fake.positions:
            pk = live.parse_comment(p.comment)
            if pk is not None and pk[:2] == (sid, name):
                self.violations.append(f"{comment} placed while position {p.comment} is open")
        for r in w.store.requests(kinds=("place",)):
            if (
                r.setup_id == sid
                and r.name == name
                and r.comment != comment
                and r.state in ("intent", "unknown")
                and r.order_state == "open"
            ):
                self.violations.append(f"{comment} placed while {r.comment} is an unresolved intent")

    def _check_stop(self, w: World, request: dict[str, Any]) -> None:
        for p in w.fake.positions:
            if p.ticket == request.get("position"):
                buy = p.type == c.POSITION_TYPE_BUY
                new = float(request["sl"])
                if (buy and new < p.sl - 1e-9) or (not buy and p.sl > 0 and new > p.sl + 1e-9):
                    self.violations.append(f"stop of {p.ticket} moved against it: {p.sl} -> {new}")


def unmanaged(w: World, tickets: set[int]) -> list[str]:
    r = w.runner
    if r.hands_off is not None:
        return []  # L8: under hands-off every position runs to its end at the broker
    owned = {f.position for cd in r.cands.values() for f in cd.fills.values()}
    return [
        f"position {t} is unmanaged"
        for t in sorted(tickets)
        if t not in owned and t not in r.close_wanted and t not in r.not_ours_positions
    ]


def play(
    tmp: Path,
    name: str,
    restart_before: int | None = None,
    die: tuple[int, bool] | None = None,
) -> Probe:
    rows, steps, bid0 = SCENARIOS[name]
    ws = []  # this play's own worlds: released at its end (each holds a generated fake broker series)
    w = world(ws, tmp, exec_rows=rows, fake_bid=bid0, start=False)
    probe = Probe(w.runner.exe)
    probe.holder = w
    w.runner.exe = probe  # type: ignore[assignment]
    if die is not None:
        probe.die_at, probe.die_after = die
    stops: dict[int, float] = {}
    problems: list[str] = []

    def reboot(cur: World) -> World:
        nw = restart(cur, ws)
        probe.holder = nw
        return nw

    def watch(cur: World, before: set[int]) -> None:
        problems.extend(unmanaged(cur, before & {p.ticket for p in cur.fake.positions}))
        for p in cur.fake.positions:
            buy = p.type == c.POSITION_TYPE_BUY
            old = stops.get(p.ticket)
            if old is not None and ((buy and p.sl < old - 1e-9) or (not buy and p.sl > old + 1e-9)):
                problems.append(f"stop of {p.ticket} worsened {old} -> {p.sl}")
            stops[p.ticket] = p.sl

    try:
        w.runner.start()
    except SystemExit:
        w = reboot(w)
    for k, (when, bid) in enumerate(steps):
        if restart_before == k:
            w = reboot(w)
        before = {p.ticket for p in w.fake.positions}
        try:
            w.to(when, bid)
        except SystemExit:
            w = reboot(w)
            w.to(when, bid)
        watch(w, before)
    probe.violations.extend(problems)
    probe.holder = None
    for each in ws:
        if each.runner.lock is not None:
            each.runner.lock.release()
        each.db.dispose()
    ws.clear()
    gc.collect()
    return probe


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_a_restart_before_any_step_breaks_no_invariant(tmp_path: Path, name: str) -> None:
    base = tmp_path / "base"
    base.mkdir()
    assert play(base, name).violations == []
    for k in range(len(SCENARIOS[name][1])):
        d = tmp_path / f"r{k}"
        d.mkdir()
        got = play(d, name, restart_before=k)
        assert got.violations == [], f"{name}: restart before step {k}"


@pytest.mark.parametrize("name", list(SCENARIOS))
@pytest.mark.parametrize("after", [False, True])
def test_a_death_at_any_send_breaks_no_invariant(tmp_path: Path, name: str, after: bool) -> None:
    base = tmp_path / "base"
    base.mkdir()
    sends = play(base, name).n
    assert sends > 0
    for n in range(sends):
        d = tmp_path / f"d{n}"
        d.mkdir()
        got = play(d, name, die=(n, after))
        assert got.violations == [], f"{name}: death {'after' if after else 'before'} send {n}"
