"""Corrupted comparison records must be reported as faults (eye/ZONE_LIVE.md L11.2; the replay's explainer).

The comparison and its explanations are the acceptance gate of the runner, so they are tested as one: each kind of
field is corrupted on its own and must show up; a cause is admitted only when its check proves it for the field; the
cascade excuses only what the admitted difference can change. Constructed bars (``zone_live_support``), no replay."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.broker import mt5_constants as c
from app.zone.core import Visit, plan_setup
from app.zone.live import sent_prices
from app.zone.params import ZoneParams
from tests.unit.zone_live_support import FILL, hour_time, make_full, settings
from tests.zone_replay import MAGIC, Event, Replay, ReplayConfig
from tests.zone_replay_compare import (
    Key,
    Ledger,
    Record,
    RunSetup,
    SimSetup,
    SpanPlan,
    compare_ledgers,
    compare_setups,
    extract_fills,
    gate_failures,
    key_of,
    raw_diffs,
)
from tests.zone_replay_explain import dependent, explain_all

PARAMS = ZoneParams(exec_tf="M15", cancel_frac=0.9)
H0 = 130  # the hour of the setup under test (exec rows 520 .. 523)


def visit(hour: int, side: str = "BUY", line: float = 100.0) -> Visit:
    sgn = 1 if side == "BUY" else -1
    return Visit(
        time=hour_time(hour),
        i=hour,
        side=side,
        sgn=sgn,
        line=line,
        step=10.0,
        anchor=100.0,
        z=10.0 * PARAMS.near_frac,
        h1_open=103.0,
        mom_body=0.0,
        mom_median=1.0,
        mom_run=0.0,
        ema_dist=0.0,
        atr=1.0,
        trends=(True, True, True, True),
        share=1.0,
        j0=hour * 4,
        touch_j=hour * 4,
        from_open=3.0,
    )


def build(
    sim_fills: dict[str, tuple[int, float]],
    run_fills: dict[str, tuple[int, float, float]],
    *,
    extra: dict[Key, tuple[str, str]] | None = None,
    sim_end_hour: int = 132,
    run_end_hour: int = 132,
    low_522: float = 101.32,
    **overrides: object,
):  # type: ignore[no-untyped-def]
    """A one-setup record: BUY 100 in hour 130. Bar 522 has an ask low of exactly the SENT P1 (101.32), one tick
    above the logic P1 (101.3158): the sent order fills, the logic one does not."""
    rows = [FILL, FILL, (103.0, 104.0, low_522, 103.0), FILL]
    full = make_full(150, exec_rows={H0: rows})
    v = visit(H0)
    pl = plan_setup(v, PARAMS)
    sp = sent_prices(pl, 0.01)
    k = key_of(v.time, "BUY", 100.0)
    sim = SimSetup(
        k,
        "traded",
        sim_fills,
        None,
        None,
        None,
        None,
        None,
        hour_time(sim_end_hour),
        (pl.p1, pl.p2, pl.sl, pl.tp),
    )
    run = RunSetup(
        k, "traded", "ended", run_fills, None, None, None, None, None, None, None, hour_time(run_end_hour),
        (pl.p1, pl.p2, pl.sl, pl.tp), (sp.p1, sp.p2, sp.sl, sp.tp),
    )  # fmt: skip
    for name, value in overrides.items():
        side, attr = name.split("__")
        setattr(sim if side == "sim" else run, attr, value)
    visits = {k: v}
    sim_classes = {k: "setup"}
    run_classes = {k: ("setup", 1)}
    for (hh, side, line), (sc, rc) in (extra or {}).items():
        v2 = visit(hh, side, line)
        k2 = key_of(v2.time, side, line)
        visits[k2] = v2
        sim_classes[k2], run_classes[k2] = sc, (rc, None)
    plan = SpanPlan(
        "constructed",
        "M15",
        hour_time(0),
        hour_time(H0),
        hour_time(H0 + 20),
        hour_time(H0 + 22),
        PARAMS,
        SimpleNamespace(outcomes=[SimpleNamespace(visit=x) for x in visits.values()]),  # type: ignore[arg-type]
    )
    rec = Record(
        "tick", 0, 0, 0.0, [], [], np.array([]), np.array([]), [], sim_classes, {k: sim}, run_classes, {k: run}, [],
        hour_time(H0 + 22), 15.0, 2.0, be_frac=PARAMS.be_frac, be_mode=PARAMS.be_mode, order_life_h=PARAMS.order_life_h,
    )  # fmt: skip
    return plan, rec, full, pl


def causes(plan, rec, full):  # type: ignore[no-untyped-def]
    diffs, _ex = explain_all(plan, rec, full)
    return diffs


def test_a_one_tick_rounding_difference_of_the_fills_own_level_is_admitted() -> None:
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _pl = build({"P1": (523, pl.p1)}, {"P1": (522, pl.p1, 101.32)})
    (d,) = causes(plan, rec, full)
    assert d.field == "fill P1 bar" and d.cause == "tick rounding", d.line()


def test_a_rounding_near_p1_does_not_excuse_a_wrong_be_stop() -> None:
    """Bar 522 is within a tick of P1, but the difference is a break-even stop wrong by one dollar."""
    pl = plan_setup(visit(H0), PARAMS)
    fills_s, fills_r = {"P1": (522, pl.p1)}, {"P1": (522, pl.p1, 101.32)}
    plan, rec, full, _ = build(fills_s, fills_r)
    s, r = rec.sim_setups[next(iter(rec.sim_setups))], rec.run_setups[next(iter(rec.run_setups))]
    s.be_j = r.be_j = 530
    s.be_sl, r.be_sent, r.be_sl = 105.0, 106.0, 105.0
    diffs = causes(plan, rec, full)
    assert [d.field for d in diffs] == ["be stop"] and diffs[0].cause == "", diffs[0].line()


def test_a_wrong_logic_be_stop_a_wrong_plan_price_and_a_sent_price_are_faults() -> None:
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build({"P1": (522, pl.p1)}, {"P1": (522, pl.p1, 101.32)})
    k = next(iter(rec.sim_setups))
    s, r = rec.sim_setups[k], rec.run_setups[k]
    s.be_j = r.be_j = 530
    s.be_sl, r.be_sent, r.be_sl = 105.0, 105.0, 105.5  # the sent stop agrees, the logic one does not
    r.prices = (pl.p1, pl.p2 + 0.5, pl.sl, pl.tp)
    r.sent = (101.32, pl.p2, pl.sl - 0.5, pl.tp)
    diffs = causes(plan, rec, full)
    assert {d.field for d in diffs} == {"be stop (logic)", "plan P2", "plan SL as sent"}
    assert all(d.cause == "" for d in diffs)


@pytest.mark.parametrize(
    ("field", "mutate"),
    [
        ("outcome", lambda s, r: setattr(r, "outcome", "cancel")),
        ("fill P1 bar", lambda s, r: s.fills.update(P1=(523, s.fills["P1"][1]))),
        ("fill P2", lambda s, r: s.fills.update(P2=(523, 1.0))),
        ("fill P1 price", lambda s, r: r.fills.update(P1=(522, r.fills["P1"][1], 101.4))),
        ("be bar", lambda s, r: (setattr(s, "be_j", 530), setattr(r, "be_j", 531))),
        ("exit bar", lambda s, r: (setattr(s, "exit_j", 540), setattr(r, "exit_j", 541))),
        ("exit how", lambda s, r: (setattr(s, "how", "SL"), setattr(r, "how", "TP"))),
        ("reservation end", lambda s, r: setattr(r, "end_time", r.end_time + pd.Timedelta(minutes=15))),
    ],
)
def test_every_kind_of_corrupted_field_is_reported(field: str, mutate) -> None:  # type: ignore[no-untyped-def]
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build({"P1": (522, pl.p1)}, {"P1": (522, pl.p1, 101.32)})
    k = next(iter(rec.sim_setups))
    mutate(rec.sim_setups[k], rec.run_setups[k])
    fields = [d.field for d in compare_setups(rec.sim_setups, rec.run_setups)]
    assert field in fields, fields
    # and, whatever the cause named, the corruption never passes silently: it is a listed difference
    assert any(d.field == field for d in causes(plan, rec, full))


def test_a_duplicate_chosen_setup_is_a_fault() -> None:
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build({"P1": (522, pl.p1)}, {"P1": (522, pl.p1, 101.32)})
    rec.dups.append(next(iter(rec.sim_setups)))
    (d,) = causes(plan, rec, full)
    assert d.field == "duplicate record" and d.cause == ""


def test_the_cascade_does_not_excuse_an_independent_exit_price() -> None:
    """The fill bar differs by rounding (admitted); the exit price is wrong with the same exit bar and how: a fault."""
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build({"P1": (523, pl.p1)}, {"P1": (522, pl.p1, 101.32)})
    k = next(iter(rec.sim_setups))
    s, r = rec.sim_setups[k], rec.run_setups[k]
    s.exit_j = r.exit_j = 540
    s.how = r.how = "SL"
    s.exit_price, r.exit_price, r.exit_broker = 99.0, 99.0, 100.5
    by = {d.field: d for d in causes(plan, rec, full)}
    assert by["fill P1 bar"].cause == "tick rounding"
    assert by["exit price"].cause == ""


def test_the_cascade_excuses_dependent_stages_of_the_same_setup() -> None:
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build({"P1": (523, pl.p1)}, {"P1": (522, pl.p1, 101.32)})
    k = next(iter(rec.sim_setups))
    s, r = rec.sim_setups[k], rec.run_setups[k]
    s.exit_j, r.exit_j = 540, 541
    s.how = r.how = "TP"
    s.exit_price, r.exit_price, r.exit_broker = 110.0, 110.0, 110.0
    s.end_time = hour_time(133)
    by = {d.field: d for d in causes(plan, rec, full)}
    assert by["exit bar"].cause == "follows tick rounding"
    assert by["reservation end"].cause == "follows tick rounding"


def test_dependent_rules() -> None:
    from tests.zone_replay_compare import Diff

    k = ("x",)  # type: ignore[assignment]
    fill = Diff(k, "fill P1 bar", 1, 2)  # type: ignore[arg-type]
    for field, fields, expect in [
        ("exit price", {"fill P1 bar", "exit price"}, False),
        ("exit price", {"fill P1 bar", "exit bar", "exit price"}, True),
        ("plan SL", {"fill P1 bar", "plan SL"}, False),
        ("fill P1 price", {"fill P1 bar", "fill P1 price"}, False),
        ("be stop", {"fill P1 bar", "be stop"}, True),
        ("be stop (logic)", {"be bar", "be stop (logic)"}, True),
        ("duplicate record", {"fill P1 bar"}, False),
        ("fill P1 bar", {"fill P1 bar"}, False),
    ]:
        assert dependent(fill, Diff(k, field, 1, 2), fields) is expect, (field, fields)  # type: ignore[arg-type]


def cascade_case(hour: int, sim_cls: str, run_cls: str):  # type: ignore[no-untyped-def]
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build(
        {"P1": (523, pl.p1)},
        {"P1": (522, pl.p1, 101.32)},
        extra={(hour, "SELL", 110.0): (sim_cls, run_cls)},
        sim_end_hour=132,
        run_end_hour=140,  # the runner's reservation is longer: it must not widen the window
    )
    return {(d.key[0], d.field): d for d in causes(plan, rec, full)}


def test_a_busy_mismatch_inside_the_simulations_reservation_is_a_cascade() -> None:
    by = cascade_case(131, "busy", "momentum")
    assert by[(hour_time(131), "class")].cause == "cascade"


def test_a_non_busy_mismatch_inside_the_reservation_is_a_fault() -> None:
    by = cascade_case(131, "momentum", "trend")
    assert by[(hour_time(131), "class")].cause == ""


def test_a_busy_mismatch_after_the_simulations_reservation_is_a_fault() -> None:
    """Hour 136 is inside the RUNNER's longer reservation but outside the simulation's."""
    by = cascade_case(136, "momentum", "busy")
    assert by[(hour_time(136), "class")].cause == ""


def test_the_dataclass_fields_of_the_records_are_what_the_comparison_reads() -> None:
    names = {f.name for f in dataclasses.fields(RunSetup)}
    assert {"prices", "sent", "be_sl", "be_sent"} <= names
    assert {"prices"} <= {f.name for f in dataclasses.fields(SimSetup)}


# --- the gate: every corruption must FAIL it (zero raw differences, no ERROR log) -------------------------------------


def matching_record():  # type: ignore[no-untyped-def]
    """A record with a COMPLETE, consistent ledger (a record without one fails the gate)."""
    plan, rec, full, k, _sp, _at = broker_record()
    return plan, rec, full, k


def test_a_matching_record_passes_the_gate() -> None:
    _plan, rec, _full, _k = matching_record()
    assert gate_failures(rec) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rec, k: rec.run_setups[k].fills.update(
            P1=(522, rec.sim_setups[k].fills["P1"][1], 101.40)
        ),  # 8 ticks off
        lambda rec, k: rec.run_setups[k].fills.update(
            P1=(523, rec.sim_setups[k].fills["P1"][1], 101.32)
        ),  # one bar
        lambda rec, k: setattr(rec.run_setups[k], "outcome", "cancel"),
        lambda rec, k: setattr(rec.run_setups[k], "be_j", 531),
        lambda rec, k: setattr(rec.run_setups[k], "exit_j", 541),
        lambda rec, k: setattr(rec.run_setups[k], "how", "SL"),
        lambda rec, k: setattr(rec.run_setups[k], "end_time", hour_time(133)),
        lambda rec, k: setattr(rec.run_setups[k], "dup_fills", ("P1",)),
        lambda rec, k: rec.dups.append(k),
        lambda rec, k: rec.run_classes.update({k: ("momentum", None)}),
        lambda rec, k: rec.run_setups.pop(k),
        lambda rec, k: rec.log_lines.append(("ERROR", "FAULT: a fill the logic does not allow")),
        lambda rec, k: setattr(rec.run_setups[k], "prices", (1.0, 2.0, 3.0, 4.0)),
        lambda rec, k: rec.undecided_hours.append(
            (rec.decided_first + 3600.0, "placing was not allowed through the 60 s from its first quote")
        ),
        lambda rec, k: rec.stale_events.append(rec.decided_first + 7200.0),
        lambda rec, k: rec.log_lines.append(
            ("WARNING", "setup 207 ends interrupted (the data has been stale for more than one bar)")
        ),
    ],
    ids=[
        "fill price 101.40",
        "fill bar",
        "outcome",
        "be bar",
        "exit bar",
        "exit how",
        "reservation end",
        "duplicate fill",
        "duplicate row",
        "class",
        "setup missing",
        "ERROR log line",
        "plan prices",
        "an undecided hour after the first decided one",
        "a stale-data removal",
        "an interrupted setup",
    ],
)
def test_each_corruption_fails_the_gate(mutate) -> None:  # type: ignore[no-untyped-def]
    _plan, rec, _full, k = matching_record()
    mutate(rec, k)
    assert gate_failures(rec), "the corrupted record passed the gate"


def test_an_undecided_hour_before_the_first_decided_one_passes_the_gate() -> None:
    """L11.2: the comparison runs from the runner's first decided hour on."""
    _plan, rec, _full, _k = matching_record()
    rec.undecided_hours.append((rec.decided_first - 3600.0, "before the first decision of the run"))
    assert gate_failures(rec) == []


def test_the_gate_does_not_consult_the_explainer() -> None:
    """The one-tick rounding case the explainer would suggest a cause for still fails the gate."""
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build({"P1": (523, pl.p1)}, {"P1": (522, pl.p1, 101.32)})
    (d,) = causes(plan, rec, full)
    assert d.cause == "tick rounding"  # suggested ...
    assert gate_failures(rec)  # ... and still a failure


def test_extraction_keeps_repeated_fills_as_duplicates() -> None:
    entry = {"name": "P1", "j": 522, "price": 101.3, "broker_price": 101.32}
    fills, dups = extract_fills({"fills": [entry, dict(entry)]})
    assert fills == {"P1": (522, 101.3, 101.32)} and dups == ["P1"]
    assert extract_fills({"fills": [entry]})[1] == []


def test_a_duplicate_fill_is_a_raw_difference() -> None:
    _plan, rec, _full, k = matching_record()
    rec.run_setups[k].dup_fills = ("P1",)
    assert [d.field for d in raw_diffs(rec)] == ["duplicate fill"]


# --- the replay driver's gating --------------------------------------------------------------------------------------


def a_replay():  # type: ignore[no-untyped-def]
    full = make_full(150)
    return Replay(
        full, PARAMS, settings("DEMO"), ReplayConfig(tf="M15", mode="poll"), hour_time(H0), hour_time(H0 + 2)
    )


def test_retry_pending_sees_every_kind_of_outstanding_work_and_fails_loudly_on_a_rename() -> None:
    rp = a_replay()
    try:
        assert rp._retry_pending() is False
        rp.runner.pending[("remove", 5)] = (1, {})
        assert rp._retry_pending() is True
        rp.runner.pending.clear()
        rp.runner.close_wanted[7] = "why"
        assert rp._retry_pending() is True
        rp.runner.close_wanted.clear()
        rp.runner.cands[1] = SimpleNamespace(refusals={"P2": 1})  # type: ignore[assignment]
        assert rp._retry_pending() is True
        rp.runner.cands.clear()
        rp._open_intent = True  # a place request of unknown outcome
        assert rp._retry_pending() is True
        rp._open_intent = False
        del rp.runner.pending  # a renamed attribute must raise, not gate silently
        with pytest.raises(AttributeError):
            rp._retry_pending()
    finally:
        rp.close()


def test_quote_aging() -> None:
    rp = a_replay()
    try:
        rp.broker.tick_s, rp._last_tick_s, rp._last_stale = 1000.0, 1000.0, False
        assert rp._quote_aging(1010.0) is False  # a fresh quote
        assert rp._quote_aging(1000.0 + 30.0 - 2 * rp.cfg.cycle_seconds) is True  # about to turn stale
        rp.broker.tick_s = 2000.0
        assert rp._quote_aging(2001.0) is False
        rp._last_stale = True  # the last cycle saw a stale quote and a new tick has come
        assert rp._quote_aging(2001.0) is True
    finally:
        rp.close()


def test_ledgers_compare_expirations_and_ticket_targets() -> None:
    req = {"action": 7, "order": 9_000_001, "expiration": 1000, "price": 1.0}
    a: Ledger = (
        [(1.0, tuple(sorted((k, str(v)) for k, v in req.items())), 10009)],
        [(1.0, "modify", "Z1-P1-0", 1.0, "")],
    )
    assert compare_ledgers(a, a)[0] is True
    for change in ({"expiration": 1001}, {"order": 9_000_002}, {"position": 5}):
        b_req = {**req, **change}
        b: Ledger = ([(1.0, tuple(sorted((k, str(v)) for k, v in b_req.items())), 10009)], a[1])
        assert compare_ledgers(a, b)[0] is False, change
    c: Ledger = (a[0], [(1.0, "modify", "Z1-P1-0", 1.0, "expires 5")])
    assert compare_ledgers(a, c)[0] is False


# --- the broker side of the gate: the replay double's own ledger -----------------------------------------------------


def broker_record():  # type: ignore[no-untyped-def]
    """A complete consistent record: BUY 100, P1 filled in bar 522, break-even on bar 530 (stop 105.0), exit by the
    BE stop in bar 540, with the broker's requests, events and deals to match."""
    pl = plan_setup(visit(H0), PARAMS)
    plan, rec, full, _ = build(
        {"P1": (522, pl.p1)},
        {"P1": (522, pl.p1, 101.32)},
        sim__be_j=530,
        sim__be_sl=105.0,
        sim__exit_j=540,
        sim__how="BE",
        sim__exit_price=105.0,
        sim__end_time=hour_time(135),
        run__be_j=530,
        run__be_sent=105.0,
        run__be_sl=105.0,
        run__exit_j=540,
        run__how="BE",
        run__exit_price=105.0,
        run__exit_broker=105.0,
        run__end_time=hour_time(135),
    )
    k = next(iter(rec.sim_setups))
    sp = sent_prices(pl, 0.01)
    f = full.frame("M15")
    close_ns = f["close_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
    open_ns = f["open_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
    rec.bar0, rec.bar_close_ns, rec.bar_open_ns = 516, close_ns[516:560], open_ns[516:560]
    rec.px_open, rec.px_start, rec.per_h = f["open"].to_numpy(float)[512:560], 512, 4
    at = lambda j, off: open_ns[j] / 1e9 + off  # noqa: E731
    rec.setup_rows = {
        1: {"hour_s": hour_time(H0).value / 1e9, "j_hour": H0 * 4, "p1": pl.p1, "p2": pl.p2, "sgn": 1, "cancel": 9.0, "visit_t": at(520, 0), "key": k, "side": "BUY", "chosen": True, "state": "ended", "p1_sent": sp.p1, "p2_sent": sp.p2, "sl_sent": sp.sl, "tp_sent": sp.tp},
        2: {"hour_s": hour_time(H0 + 1).value / 1e9, "j_hour": (H0 + 1) * 4, "p1": 108.0, "p2": 107.0, "sgn": -1, "cancel": 9.0, "visit_t": None, "key": key_of(hour_time(H0 + 1), "SELL", 110.0), "side": "SELL", "chosen": False, "state": "dropped", "p1_sent": 108.0, "p2_sent": 107.0, "sl_sent": 115.0, "tp_sent": 100.0},
    }  # fmt: skip
    rec.broker_ledger_present = True
    rec.decided_first = hour_time(H0).value / 1e9  # the runner's first decided hour
    rec.cycle_a = np.array([])
    rec.sim_all_setups = dict(rec.sim_setups)
    entry = {
        "action": 5,
        "symbol": "XAUUSD",
        "_order": 5001,
        "type": 2,
        "type_time": 2,
        "_exp_s": (at(520, 5) // 3600) * 3600 + 3660,
        "price": sp.p1,
        "sl": sp.sl,
        "tp": sp.tp,
        "volume": 0.01,
        "magic": MAGIC,
        "comment": "Z1-P1-0",
    }
    sltp = {
        "action": 6,
        "symbol": "XAUUSD",
        "position": 11,
        "sl": 105.0,
        "tp": sp.tp,
        "magic": MAGIC,
        "_order": 0,
    }
    rec.requests = [(at(520, 5), entry, 10008), (at(531, 2), sltp, 10009)]
    rec.events = [
        Event(at(520, 5), "place", "Z1-P1-0", sp.p1),
        Event(at(522, 100), "fill", "Z1-P1-0", sp.p1),
        Event(at(531, 2), "sltp", "Z1-P1-0", 105.0, "tp x"),
        Event(at(540, 50), "exit", "Z1-P1-0", 105.0),
    ]
    deal = {"magic": MAGIC, "volume": 0.01, "reason": 3}
    rec.deals = [
        {
            **deal,
            "t": at(522, 100),
            "entry": 0,
            "type": 0,
            "comment": "Z1-P1-0",
            "price": 101.32,
            "position": 11,
        },
        {
            **deal,
            "t": at(540, 50),
            "entry": 1,
            "type": 1,
            "comment": "",
            "price": 105.0,
            "position": 11,
            "reason": c.DEAL_REASON_SL,  # the BE stop hit at the broker
        },
    ]
    return plan, rec, full, k, sp, at


def test_a_consistent_broker_ledger_passes_the_gate() -> None:
    _plan, rec, _full, _k, _sp, _at = broker_record()
    assert gate_failures(rec) == []


def _double_send(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.requests.append((at(520, 6), dict(rec.requests[0][1]), 10008))
    rec.deals.insert(
        1,
        {
            "magic": MAGIC,
            "volume": 0.01,
            "reason": 3,
            "t": at(522, 101),
            "entry": 0,
            "comment": "Z1-P1-0",
            "price": 101.32,
            "position": 12,
        },
    )


def _extra_position(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.deals.insert(
        1,
        {
            "magic": MAGIC,
            "volume": 0.01,
            "reason": 3,
            "t": at(523, 5),
            "entry": 0,
            "comment": "Z1-P2-0",
            "price": 100.0,
            "position": 13,
        },
    )


def _bad_request(**change):  # type: ignore[no-untyped-def]
    def mutate(rec, k, sp, at):  # type: ignore[no-untyped-def]
        rec.requests[0] = (rec.requests[0][0], {**rec.requests[0][1], **change}, 10008)

    return mutate


def _stop_away(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.events.insert(1, Event(at(526, 3), "sltp", "Z1-P1-0", 94.0, "tp x"))


def _stop_wrong_bar(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.events[1] = Event(at(534, 3), "sltp", "Z1-P1-0", 105.0, "tp x")


def _stop_not_be(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.events[1] = Event(at(531, 2), "sltp", "Z1-P1-0", 103.0, "tp x")


def _two_setups_open(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.deals.insert(
        1,
        {
            "magic": MAGIC,
            "volume": 0.01,
            "reason": 3,
            "t": at(523, 1),
            "entry": 0,
            "comment": "Z2-P1-0",
            "price": 108.0,
            "position": 14,
        },
    )


@pytest.mark.parametrize(
    "mutate",
    [
        _double_send,
        _bad_request(sl=0.0),
        _bad_request(tp=0.0),
        _bad_request(tp=123.0),
        _bad_request(volume=0.02),
        _bad_request(magic=1),
        _bad_request(comment="P1 please"),
        _bad_request(price=101.0),
        _extra_position,
        lambda rec, k, sp, at: setattr(
            rec, "end_orders", [("Z1-P2-1", 101.0)]
        ),  # a resting order after the end
        lambda rec, k, sp, at: setattr(
            rec, "end_positions", [("Z1-P1-0", 101.32)]
        ),  # open where the simulation closed
        _stop_away,
        _stop_wrong_bar,
        _stop_not_be,
        _two_setups_open,
        lambda rec, k, sp, at: rec.deals.__setitem__(
            0, {**rec.deals[0], "price": 101.40}
        ),  # a wrong fill price
        lambda rec, k, sp, at: rec.deals.__setitem__(
            1, {**rec.deals[1], "t": at(541, 5)}
        ),  # an exit in another bar
        lambda rec, k, sp, at: rec.deals.__setitem__(
            1, {**rec.deals[1], "reason": c.DEAL_REASON_CLIENT}
        ),  # the exit by hand
        lambda rec, k, sp, at: rec.deals.__setitem__(
            1, {**rec.deals[1], "reason": c.DEAL_REASON_TP}
        ),  # a TP deal where the simulation's exit is the BE stop
        lambda rec, k, sp, at: rec.deals.__setitem__(
            1, {**rec.deals[1], "reason": c.DEAL_REASON_EXPERT}
        ),  # a close by the runner where none was requested
        lambda rec, k, sp, at: rec.deals.__setitem__(
            0, {**rec.deals[0], "reason": c.DEAL_REASON_CLIENT}
        ),  # the entry by hand
        lambda rec, k, sp, at: rec.deals.append(
            {
                "magic": MAGIC,
                "volume": 0.01,
                "reason": c.DEAL_REASON_CLIENT,
                "t": at(541, 5),
                "entry": 1,
                "type": 1,
                "comment": "",
                "price": 104.0,
                "position": 99,
            }
        ),  # an exit of a position nobody opened
    ],
    ids=[
        "same comment sent twice, two fills",
        "entry without SL",
        "entry without TP",
        "entry with another TP",
        "lot 0.02",
        "another magic",
        "malformed comment",
        "entry price not the setup's",
        "extra broker position",
        "resting order after the setup's end",
        "open position the simulation closed",
        "SL moved away from profit",
        "break-even in another bar",
        "stop is not the simulation's BE stop",
        "two setups open at once",
        "fill price 101.40",
        "exit in another bar",
        "exit reason CLIENT",
        "exit reason TP for a BE stop",
        "exit reason EXPERT without a close request",
        "entry reason CLIENT",
        "an exit without its entry",
    ],
)
def test_each_broker_side_corruption_fails_the_gate(mutate) -> None:  # type: ignore[no-untyped-def]
    _plan, rec, _full, k, sp, at = broker_record()
    mutate(rec, k, sp, at)
    failures = gate_failures(rec)
    assert failures, "the corrupted broker ledger passed the gate"
    assert any(f.startswith("broker:") for f in failures), failures


# --- the broker gate, round two: evidence required, both ways, lives, modifies, types, closes, the tail --------------


def test_a_record_without_a_broker_ledger_fails_the_gate() -> None:
    _plan, rec, _full, _k = matching_record()
    rec.broker_ledger_present = False
    assert any(f.startswith("no broker evidence") for f in gate_failures(rec))
    _plan, bare, _full2, _ = build({}, {})  # a record built without the ledger fields at all
    assert any(f.startswith("no broker evidence") for f in gate_failures(bare))


def test_load_refuses_a_record_without_a_broker_ledger(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import pickle

    from tests.zone_replay_compare import load

    plan, bare, _full, _ = build({}, {})
    path = tmp_path / "old.pkl"
    path.write_bytes(pickle.dumps((plan, bare)))
    with pytest.raises(ValueError, match="broker ledger"):
        load(path)
    plan, rec, _f, _k = matching_record()
    good = tmp_path / "good.pkl"
    good.write_bytes(pickle.dumps((plan, rec)))
    assert load(good)[1].broker_ledger_present


def _drop_deals(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.deals = []


def _drop_be_event(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.events = [e for e in rec.events if e.kind != "sltp"]


def _drop_out_deal(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.deals = [d for d in rec.deals if d["entry"] == 0]


def _volume(i, v):  # type: ignore[no-untyped-def]
    def mutate(rec, k, sp, at):  # type: ignore[no-untyped-def]
        rec.deals[i] = {**rec.deals[i], "volume": v}

    return mutate


def _second_p1_while_resting(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.events.insert(1, Event(at(521, 1), "place", "Z1-P1-1", sp.p1))
    rec.events.insert(2, Event(at(521, 3), "cancel", "Z1-P1-1", sp.p1))


def _order_outlives_setup(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.events.append(Event(at(550, 1), "place", "Z1-P2-0", sp.p2))
    rec.events.append(
        Event(at(552, 1), "expire", "Z1-P2-0", sp.p2)
    )  # after the simulated end, before the span end


def _modify_with(**change):  # type: ignore[no-untyped-def]
    def mutate(rec, k, sp, at):  # type: ignore[no-untyped-def]
        req = {
            "action": 7,
            "order": 5001,
            "price": sp.p1,
            "sl": sp.sl,
            "tp": sp.tp,
            "expiration": 1,
            "_order": 0,
        }
        rec.requests.append((at(525, 1), {**req, **change}, 10009))

    return mutate


def _sltp_without_tp(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.requests[1] = (rec.requests[1][0], {**rec.requests[1][1], "tp": 0.0}, 10009)


def _second_close(rec, k, sp, at):  # type: ignore[no-untyped-def]
    close = {
        "action": 1,
        "symbol": "XAUUSD",
        "position": 11,
        "type": 1,
        "volume": 0.01,
        "magic": MAGIC,
        "_order": 0,
    }
    rec.requests += [(at(540, 49), close, 10009), (at(540, 50), dict(close), 10036)]


def _duplicate_out(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.deals.append(dict(rec.deals[-1]))


@pytest.mark.parametrize(
    "mutate",
    [
        _drop_deals,
        _drop_be_event,
        _drop_out_deal,
        _volume(0, 0.02),
        _volume(1, 0.02),
        _second_p1_while_resting,
        _order_outlives_setup,
        _modify_with(sl=0.0),
        _modify_with(tp=0.0),
        _modify_with(price=99.0),
        _sltp_without_tp,
        _bad_request(symbol="EURUSD"),
        _bad_request(type=3),  # a SELL limit for a BUY setup
        _bad_request(action=1, type=0, price=150.0),  # a BUY market entry far above the setup's P1
        _bad_request(action=1, type=1, price=101.32),  # a SELL market order for a BUY setup
        _second_close,
        _duplicate_out,
    ],
    ids=[
        "all deals deleted",
        "BE event deleted",
        "exit deal deleted",
        "entry deal of 0.02",
        "exit deal of 0.02",
        "P1-1 placed while P1-0 rests",
        "an order outlives its setup but expires before the span end",
        "expiry modify with sl=0",
        "expiry modify with tp=0",
        "modify moves the price",
        "BE modify removes the TP",
        "wrong symbol",
        "wrong order type",
        "market entry that is not marketable",
        "market entry on the wrong side",
        "second close of one position",
        "duplicate exit deal",
    ],
)
def test_each_second_round_broker_corruption_fails_the_gate(mutate) -> None:  # type: ignore[no-untyped-def]
    _plan, rec, _full, k, sp, at = broker_record()
    mutate(rec, k, sp, at)
    failures = gate_failures(rec)
    assert any(f.startswith("broker:") for f in failures), failures


def test_a_correct_trade_of_the_tail_beyond_the_compared_window_passes() -> None:
    """The simulation's side of the broker ledger runs to the replay's end: a tail trade that the runner and the
    broker made as the simulation did is not a difference. Without the simulation's tail setup it fails."""
    _plan, rec, _full, _k, _sp, at = broker_record()
    k3 = key_of(hour_time(136), "BUY", 90.0)
    sim3 = SimSetup(k3, "traded", {"P1": (545, 91.3)}, None, None, 552, "SL", 85.0, hour_time(139), None)
    rec.setup_rows[3] = {
        "key": k3, "side": "BUY", "chosen": True, "state": "ended",
        "p1_sent": 91.3, "p2_sent": 90.0, "sl_sent": 85.0, "tp_sent": 100.0,
        "hour_s": hour_time(136).value / 1e9, "j_hour": 544, "p1": 91.3, "p2": 90.0, "sgn": 1, "cancel": 20.0, "visit_t": at(545, 9),
    }  # fmt: skip
    entry = {"action": 5, "symbol": "XAUUSD", "type": 2, "type_time": 2, "_exp_s": (at(544, 5) // 3600) * 3600 + 3660, "price": 91.3, "sl": 85.0, "tp": 100.0, "volume": 0.01,
             "magic": MAGIC, "comment": "Z3-P1-0", "_order": 5003}  # fmt: skip
    rec.requests.append((at(544, 5), entry, 10008))
    rec.events += [
        Event(at(544, 5), "place", "Z3-P1-0", 91.3),
        Event(at(545, 9), "fill", "Z3-P1-0", 91.3),
        Event(at(552, 9), "exit", "Z3-P1-0", 85.0),
    ]
    d = {"magic": MAGIC, "volume": 0.01, "reason": 3}
    rec.deals += [
        {**d, "t": at(545, 9), "entry": 0, "comment": "Z3-P1-0", "price": 91.3, "position": 21},
        {
            **d,
            "t": at(552, 9),
            "entry": 1,
            "comment": "",
            "price": 85.0,
            "position": 21,
            "reason": c.DEAL_REASON_SL,
        },
    ]
    without = gate_failures(rec)
    assert any("the simulation has no such fill" in f for f in without)  # the simulation's tail is missing
    rec.sim_all_setups[k3] = sim3
    assert gate_failures(rec) == []


# --- the broker gate, round three: BE before any exit, removal deadlines, expiry, closes, unfinished tails -----------


def _exit_in_the_bar_after_be_without_a_move(rec, k, sp, at):  # type: ignore[no-untyped-def]
    """BE triggered at 530, the SL never modified, the exit comes in bar 531."""
    rec.events = [e for e in rec.events if e.kind != "sltp"]
    rec.requests = [r for r in rec.requests if r[1].get("action") != 6]
    rec.sim_setups[k].exit_j = rec.sim_all_setups[k].exit_j = 531
    rec.deals[-1] = {**rec.deals[-1], "t": at(531, 50)}


def _gtc_limit(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.requests[0] = (rec.requests[0][0], {**rec.requests[0][1], "type_time": 0}, 10008)


def _wrong_expiry(rec, k, sp, at):  # type: ignore[no-untyped-def]
    rec.requests[0] = (
        rec.requests[0][0],
        {**rec.requests[0][1], "_exp_s": rec.requests[0][1]["_exp_s"] + 600},
        10008,
    )


def _modify_extension(t_off, new_off=3600.0, tt=2):  # type: ignore[no-untyped-def]
    def mutate(rec, k, sp, at):  # type: ignore[no-untyped-def]
        exp = rec.requests[0][1]["_exp_s"]
        req = {
            "action": 7,
            "order": 5001,
            "price": sp.p1,
            "sl": sp.sl,
            "tp": sp.tp,
            "type_time": tt,
            "_exp_s": exp + new_off,
            "_order": 0,
        }
        rec.requests.append((exp + t_off, req, 10009))

    return mutate


def _close_with(**change):  # type: ignore[no-untyped-def]
    def mutate(rec, k, sp, at):  # type: ignore[no-untyped-def]
        close = {
            "action": 1,
            "symbol": "XAUUSD",
            "position": 11,
            "type": 1,
            "volume": 0.01,
            "magic": MAGIC,
            "_order": 0,
        }
        rec.requests.append((at(540, 49), {**close, **change}, 10009))

    return mutate


@pytest.mark.parametrize(
    "mutate",
    [
        _exit_in_the_bar_after_be_without_a_move,
        _gtc_limit,
        _wrong_expiry,
        _modify_extension(-3000.0),  # an hour extension 50 minutes early
        _modify_extension(-300.0, new_off=7200.0),  # the wrong extension
        _modify_extension(-300.0, tt=0),  # the expiry removed
        _close_with(volume=0.005),
        _close_with(type=0),
        _close_with(symbol="EURUSD"),
        _close_with(magic=2),
    ],
    ids=[
        "BE at 530, no SL move, exit in the next bar",
        "GTC limit",
        "expiry not the H1 close + 1 minute",
        "expiry extended 50 minutes early",
        "expiry extended by two hours",
        "modify removes the expiry",
        "close of half the volume",
        "close on the same side",
        "close of another symbol",
        "close with another magic",
    ],
)
def test_each_third_round_broker_corruption_fails_the_gate(mutate) -> None:  # type: ignore[no-untyped-def]
    _plan, rec, _full, k, sp, at = broker_record()
    mutate(rec, k, sp, at)
    failures = gate_failures(rec)
    assert any(f.startswith("broker:") for f in failures), failures


def test_a_legitimate_extension_passes() -> None:
    _plan, rec, _full, k, sp, at = broker_record()
    _modify_extension(-300.0)(rec, k, sp, at)
    assert gate_failures(rec) == []


def test_an_unfinished_tail_is_neither_demanded_nor_a_failure() -> None:
    """Simulated actions after the replay's end are not demanded, and a pending tail order of a setup that has not
    ended at the end is fine."""
    _plan, rec, _full, _k, _sp, _at = broker_record()
    k4 = key_of(
        hour_time(H0 + 21), "BUY", 80.0
    )  # the last hour of the replay (bars 604..607 are beyond bar 560)
    rec.sim_all_setups[k4] = SimSetup(
        k4, "traded", {"P1": (562, 81.3)}, 566, 82.0, None, None, None, hour_time(170), None
    )
    assert gate_failures(rec) == [], "a simulated fill after the end of the replay is not demanded"
    # a legitimately pending order of a setup that has not ended
    k5 = key_of(hour_time(H0 + 20), "BUY", 85.0)
    rec.sim_all_setups[k5] = SimSetup(k5, "pending", {}, None, None, None, None, None, hour_time(170), None)
    rec.setup_rows[5] = {
        "hour_s": hour_time(H0 + 20).value / 1e9, "j_hour": 600, "p1": 86.3, "p2": 85.0, "sgn": 1, "cancel": 20.0, "visit_t": None,
        "key": k5, "side": "BUY", "chosen": True, "state": "live", "p1_sent": 86.3, "p2_sent": 85.0, "sl_sent": 80.0, "tp_sent": 95.0,
    }  # fmt: skip
    t = float(rec.bar_close_ns[-1]) / 1e9 - 600
    entry = {
        **rec.requests[0][1],
        "comment": "Z5-P1-0",
        "price": 86.3,
        "sl": 80.0,
        "tp": 95.0,
        "_order": 5005,
    }
    entry["_exp_s"] = (t // 3600) * 3600 + 3660
    rec.requests.append((t, entry, 10008))
    rec.events.append(Event(t, "place", "Z5-P1-0", 86.3))
    rec.end_orders = [("Z5-P1-0", 86.3)]
    assert gate_failures(rec) == []


# --- round four: the BE fallback close and the discovery deadline of the losing candidate ---------------------------


def _fallback_record(bid_cents: int, close_dt: float = 0.0):  # type: ignore[no-untyped-def]
    """BE at bar 530 (stop 105.0), no stop move: the runner found the price already beyond the stop at the first
    cycle after the bar's close and closed at market (the exit is then in bar 531)."""
    _plan, rec, _full, k, _sp, _at = broker_record()
    t_close = float(rec.bar_close_ns[530 - rec.bar0]) / 1e9
    rec.events = [e for e in rec.events if e.kind not in ("sltp", "exit")]
    rec.requests = [r for r in rec.requests if r[1].get("action") != 6]
    close = {
        "action": 1,
        "symbol": "XAUUSD",
        "position": 11,
        "type": 1,
        "volume": 0.01,
        "magic": MAGIC,
        "_order": 0,
    }
    rec.requests.append((t_close + close_dt, close, 10009))
    rec.events.append(Event(t_close + close_dt, "close", "Z1-P1-0", 104.9))
    rec.sim_setups[k].exit_j = rec.sim_all_setups[k].exit_j = 531
    rec.sim_setups[k].exit_price = rec.sim_all_setups[k].exit_price = 105.0
    rec.deals[-1] = {**rec.deals[-1], "t": t_close + close_dt, "price": 105.0}
    rec.run_setups[k].exit_j = 531
    rec.run_setups[k].exit_price = rec.run_setups[k].exit_broker = 105.0
    rec.cycle_t = np.array(
        [t_close - 2.0, t_close, t_close + close_dt] if close_dt else [t_close - 2.0, t_close]
    )
    rec.cycle_b = np.array([10600, bid_cents, bid_cents] if close_dt else [10600, bid_cents])
    rec.cycle_a = rec.cycle_b + 5
    return rec


def test_a_valid_be_fallback_close_passes() -> None:
    assert gate_failures(_fallback_record(10490)) == []  # the bid is already below the BE stop 105.0


def test_a_be_fallback_close_with_the_quote_not_beyond_the_stop_fails() -> None:
    assert any(f.startswith("broker:") for f in gate_failures(_fallback_record(10600)))


def test_a_be_fallback_close_at_the_wrong_time_fails() -> None:
    assert any(f.startswith("broker:") for f in gate_failures(_fallback_record(10490, close_dt=30.0)))


def test_no_stop_move_and_no_close_fails() -> None:
    rec = _fallback_record(10490)
    rec.requests = [r for r in rec.requests if r[1].get("action") != 1]
    assert any("no stop move" in f for f in gate_failures(rec))


# --- round five: the recorded ask, the stop as sent, deals in the discovery, every market close justified -----------


def _sell_ledger(be_sl: float, bid_c: int, ask_c: int):  # type: ignore[no-untyped-def]
    from tests.zone_replay_broker_gate import Ledger, _fallback_ok

    _plan, rec, _full, k, _sp, _at = broker_record()
    t_close = float(rec.bar_close_ns[530 - rec.bar0]) / 1e9
    rec.sim_all_setups[k].be_sl = be_sl
    rec.cycle_t, rec.cycle_b, rec.cycle_a = np.array([t_close]), np.array([bid_c]), np.array([ask_c])
    rec.bar_spread = np.full(len(rec.bar_close_ns), 5)  # a reconstruction bid + spread would say 105.0x
    led = Ledger(rec)
    led.pos_buy[11] = False  # the position is a SELL
    return lambda: _fallback_ok(led, 11, led.sim_of(1), t_close)


def test_a_sell_fallback_uses_the_recorded_ask_and_the_stop_as_sent() -> None:
    # logic stop 105.005 is sent as 105.00 (toward the TP side for a SELL): an ask of 105.00 is beyond it
    assert _sell_ledger(105.005, 10490, 10500)() is True
    # the bid + the next bar's spread would reach 105.0, but the recorded ask is 104.96: not beyond
    assert _sell_ledger(105.005, 10491, 10496)() is False


def test_a_buy_fallback_compares_with_the_stop_as_sent() -> None:
    from tests.zone_replay_broker_gate import Ledger, _fallback_ok

    _plan, rec, _full, k, _sp, _at = broker_record()
    t_close = float(rec.bar_close_ns[530 - rec.bar0]) / 1e9
    rec.sim_all_setups[k].be_sl = 104.995  # sent as 105.00 (BUY rounds up): a bid of 105.00 is beyond it
    rec.cycle_t, rec.cycle_b, rec.cycle_a = np.array([t_close]), np.array([10500]), np.array([10505])
    led = Ledger(rec)
    assert _fallback_ok(led, 11, led.sim_of(1), t_close) is True


def _market_close_after_be_move(rec, k, sp, at):  # type: ignore[no-untyped-def]
    """The BE stop was set (a move exists) and then the runner closes at market one tick above it in the exit bar."""
    close = {
        "action": 1,
        "symbol": "XAUUSD",
        "position": 11,
        "type": 1,
        "volume": 0.01,
        "magic": MAGIC,
        "_order": 0,
    }
    rec.requests.append((at(540, 49), close, 10009))


def test_an_unjustified_market_close_fails_even_when_the_stop_move_exists() -> None:
    _plan, rec, _full, k, sp, at = broker_record()
    _market_close_after_be_move(rec, k, sp, at)
    fails = gate_failures(rec)
    assert any("not L5's BE fallback" in f for f in fails), fails


def test_a_record_without_cycle_quotes_fails_the_gate() -> None:
    _plan, rec, _full, _k = matching_record()
    rec.cycle_a = None
    assert any(f.startswith("no broker evidence") and "no cycle quotes" in f for f in gate_failures(rec))
    rec.cycle_a = np.array([1, 2])  # not one ask per cycle
    assert any("no cycle quotes" in f for f in gate_failures(rec))


def test_the_visit_band_is_not_rounded() -> None:
    """BUY band L + Z = 101.306: a bid of 101.31 is no touch (rounding the band to 101.31 would invent one)."""
    from tests.zone_replay_compare import visit_near

    bids = np.array([10131, 10130])
    assert visit_near(bids, True, 101.0, 0.306).tolist() == [False, True]  # 101.31 is no touch, 101.30 is
    assert visit_near(np.array([10119, 10121]), False, 101.2, 0.0).tolist() == [False, True]


def test_a_record_without_the_break_even_parameters_fails_validation_and_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import pickle

    from tests.zone_replay_compare import load

    plan, rec, _f, _k = matching_record()
    rec.be_frac = None
    assert any(f.startswith("no broker evidence") and "be_frac" in f for f in gate_failures(rec))
    path = tmp_path / "nobe.pkl"
    path.write_bytes(pickle.dumps((plan, rec)))
    with pytest.raises(ValueError, match="be_frac"):
        load(path)


def _with_p2(cancel_p2_dt: float | None, p1_end: tuple[str, float] | None):  # type: ignore[no-untyped-def]
    """P2 placed at +6 of bar 520 and cancelled at ``cancel_p2_dt`` of bar 521; the broker record's P1 (placed at +5,
    filled in bar 522) is replaced by one that ends unfilled at ``p1_end`` (kind, time in bar 520) when given."""
    _plan, rec, _full, _k, sp, at = broker_record()
    p2 = {**rec.requests[0][1], "comment": "Z1-P2-0", "price": sp.p2, "_order": 5002}
    rec.requests.append((at(520, 6), p2, 10008))
    rec.events.insert(1, Event(at(520, 6), "place", "Z1-P2-0", sp.p2))
    if cancel_p2_dt is not None:
        rec.events.insert(2, Event(at(521, cancel_p2_dt), "cancel", "Z1-P2-0", sp.p2))
    if p1_end is not None:
        rec.events = [e for e in rec.events if e.kind != "fill" or e.comment != "Z1-P1-0"]
        rec.events.insert(2, Event(at(520, p1_end[1]), p1_end[0], "Z1-P1-0", 100.0))
    return rec


def _p1_failures(rec) -> list[str]:  # type: ignore[no-untyped-def]
    return [f for f in gate_failures(rec) if "no P1 of the setup is alive" in f]


def test_p2_lives_only_while_p1_is_alive_or_filled() -> None:
    assert _p1_failures(_with_p2(100.0, None)) == []  # P1 placed first and filled in bar 522
    rec = _with_p2(100.0, ("cancel", 50.0))  # P1 cancelled unfilled at +50, P2 still resting until bar 521
    assert _p1_failures(rec) != []
    rec = _with_p2(100.0, None)
    rec.requests = [r for r in rec.requests if r[1].get("comment") != "Z1-P1-0"]
    rec.events = [e for e in rec.events if e.comment != "Z1-P1-0"]  # a refused P1: no P1 ever placed
    assert _p1_failures(rec) != []


def test_p2_removed_in_the_cycle_that_p1_ends_passes() -> None:
    rec = _with_p2(None, ("cancel", 50.0))
    rec.events.insert(3, Event(rec.events[2].t, "cancel", "Z1-P2-0", 99.0))  # the same cycle
    assert _p1_failures(rec) == []


def test_an_order_resting_past_its_setups_end_fails() -> None:
    _plan, rec, _full, k, _sp, at = broker_record()
    rec.sim_all_setups[k].end_time = pd.Timestamp(at(522, 900), unit="s", tz="UTC")  # bar 522's close
    rec.events.insert(1, Event(at(524, 1), "cancel", "Z1-P1-0", 100.0))
    assert any("simulated end" in f for f in gate_failures(rec))


@pytest.mark.parametrize(
    "change",
    [{"tp": 0.0}, {"tp": 90.0}, {"sl": 0.0}, {"sl": 120.0}],
    ids=["tp zero", "tp below the price (BUY)", "sl zero", "sl above the price (BUY)"],
)
def test_an_entry_needs_sl_and_tp_on_the_correct_sides(change) -> None:  # type: ignore[no-untyped-def]
    _plan, rec, *_rest = broker_record()
    if "tp" in change:
        rec.setup_rows[1]["tp_sent"] = change[
            "tp"
        ]  # the row agrees: only the positivity / side checks catch it
    if "sl" in change:
        rec.setup_rows[1]["sl_sent"] = change["sl"]
    rec.requests[0] = (rec.requests[0][0], {**rec.requests[0][1], **change}, 10008)
    assert any(f.startswith("broker:") for f in gate_failures(rec))


def test_a_modify_must_keep_sl_and_tp_set() -> None:
    _plan, rec, _full, _k, sp, at = broker_record()
    mod = {"action": 7, "order": 5001, "price": sp.p1, "sl": sp.sl, "tp": sp.tp, "type_time": 2, "_order": 0}
    mod["_exp_s"] = rec.requests[0][1]["_exp_s"] + 3600
    rec.requests.append((at(520, 3000), mod, 10009))
    assert not any("unset" in f or "correct sides" in f for f in gate_failures(rec))
    rec.requests[-1] = (at(520, 3000), {**mod, "tp": 0.0}, 10009)
    assert any("unset" in f for f in gate_failures(rec))


def test_a_record_without_the_bar_open_times_fails_validation_and_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import pickle

    from tests.zone_replay_compare import load

    plan, rec, _f, _k = matching_record()
    rec.bar_open_ns = None
    assert any(f.startswith("no broker evidence") and "bar open" in f for f in gate_failures(rec))
    path = tmp_path / "noopen.pkl"
    path.write_bytes(pickle.dumps((plan, rec)))
    with pytest.raises(ValueError, match="bar open"):
        load(path)


def _expiry_record(cancel_dt: float):  # type: ignore[no-untyped-def]
    """The setup never fills; its order life is 2 hours, so the expiry bar is 528 (j0 520 + 2 x 4): the order is
    removed ``cancel_dt`` s after bar 528's open."""
    _plan, rec, _full, k, _sp, at = broker_record()
    rec.order_life_h = 2
    sim = rec.sim_all_setups[k]
    sim.outcome, sim.fills = "no fill", {}
    sim.end_time = pd.Timestamp(rec.bar_close_ns[528 - rec.bar0], unit="ns", tz="UTC")
    rec.events = [e for e in rec.events if e.kind not in ("fill", "exit", "sltp")]
    rec.events.insert(1, Event(at(528, cancel_dt), "cancel", "Z1-P1-0", 100.0))
    return rec


def test_an_order_is_removed_at_the_expiry_bars_open_not_later_in_that_bar() -> None:
    def expiry_failures(rec):  # type: ignore[no-untyped-def]
        return [f for f in gate_failures(rec) if "expiry bar" in f]

    assert expiry_failures(_expiry_record(0.0)) == []
    assert expiry_failures(_expiry_record(500.0)) != []


def test_a_stops_request_needs_tp_strictly_beyond_sl() -> None:
    _plan, rec, _full, _k, _sp, _at = broker_record()
    req = rec.requests[1][1]
    assert not any("wrong side of SL" in f for f in gate_failures(rec))  # BUY: TP 110 > SL 105
    rec.requests[1] = (rec.requests[1][0], {**req, "tp": req["sl"]}, rec.requests[1][2])  # BUY TP == SL
    assert any("wrong side of SL" in f for f in gate_failures(rec))
    rec.requests[1] = (rec.requests[1][0], {**req, "sl": 100.0, "tp": 100.0}, rec.requests[1][2])
    from tests.zone_replay_broker_gate import Ledger

    led = Ledger(rec)
    led.pos_buy[11] = False  # a SELL position with SL = TP = 100
    out: list[str] = []
    from tests.zone_replay_broker_gate import _stops

    _stops(led, out)
    assert any("wrong side of SL" in f for f in out)
