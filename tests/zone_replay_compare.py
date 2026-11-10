"""The comparison of the replayed runner with the simulation (eye/ZONE_LIVE.md L11.2), both ways, and the
table per span.

``python -m tests.zone_replay_compare --span 2026-03-m15 --mode tick`` runs one replay and prints its table
(spans: 2024-03-m15, 2026-03-m15, 2026-03-m5; modes: tick, poll)."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.zone.core import PER_H, Bars, RunResult, load_bars, run_zone
from app.zone.params import ZoneParams, load_params
from tests.zone_replay import Replay, ReplayConfig, bar_path

ROOT = Path(__file__).resolve().parents[1]
SKIPS = ("momentum", "busy", "abnormal", "trend")
TICK = 0.01
EPS = 1e-6

SPANS = {
    "2024-03-m15": ("M15", "2023-10-01", "2024-03-01", "2024-04-01"),
    "2026-03-m15": ("M15", "2023-10-01", "2026-03-01", "2026-04-01"),
    "2026-03-m5": ("M5", "2025-10-13", "2026-03-01", "2026-04-01"),
    # not required by L11.2: months with more setups (19 and 10 in the simulation), as further evidence
    "2025-04-m15": ("M15", "2023-10-01", "2025-04-01", "2025-05-01"),
    "2024-05-m15": ("M15", "2023-10-01", "2024-05-01", "2024-06-01"),
}
REQUIRED = ("2024-03-m15", "2026-03-m15", "2026-03-m5")

Key = tuple[pd.Timestamp, str, float]


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


# --- the plan of a span ---------------------------------------------------------------------------------------


@dataclass
class SpanPlan:
    name: str
    tf: str
    epoch: pd.Timestamp
    start: pd.Timestamp  # the replay's first H1 open (nothing of the simulation is reserved at it)
    cmp_end: pd.Timestamp  # visits before this are compared
    end: pd.Timestamp  # the replay's end
    params: ZoneParams
    sim: RunResult


def plan_span(name: str, full: Bars, base: ZoneParams) -> SpanPlan:
    tf, epoch_s, a, b = SPANS[name]
    params = dataclasses.replace(base, exec_tf=tf)
    epoch, month_a, month_b = ts(epoch_s), ts(a), ts(b)
    # one run over the span and its tail: the setups that start in the span end inside the tail
    sim = run_zone(full, params, epoch, month_b + pd.Timedelta(days=12))
    setups = [o.setup for o in sim.outcomes if o.setup is not None]
    reserved_until = max([s.end_time for s in setups if s.visit.time < month_a] + [month_a])
    h1 = full.h1
    after = h1[h1["open_time"] > reserved_until]["open_time"]
    start = pd.Timestamp(after.iloc[0])
    inside = [s for s in setups if start <= s.visit.time < month_b]
    last_end = max([s.end_time for s in inside] + [month_b])
    end = last_end + pd.Timedelta(hours=2)
    return SpanPlan(name, tf, epoch, start, month_b, end, params, sim)


# --- what each side says -----------------------------------------------------------------------------------------


@dataclass
class SimSetup:
    key: Key
    outcome: str
    fills: dict[str, tuple[int, float]]
    be_j: int | None
    be_sl: float | None
    exit_j: int | None
    how: str | None
    exit_price: float | None
    end_time: pd.Timestamp
    prices: tuple[float, float, float, float] | None = None  # P1, P2, SL, TP (logic, unrounded)


@dataclass
class RunSetup:
    key: Key
    outcome: str | None
    state: str
    fills: dict[str, tuple[int, float, float]]  # name -> (bar, logic price, broker price)
    be_j: int | None
    be_sent: float | None
    be_sl: float | None
    exit_j: int | None
    how: str | None
    exit_price: float | None
    exit_broker: float | None
    end_time: pd.Timestamp | None
    prices: tuple[float, float, float, float] | None = None  # the row's P1, P2, SL, TP (logic)
    sent: tuple[float, float, float, float] | None = None  # ... and as sent to the broker
    dup_fills: tuple[str, ...] = ()  # fill names recorded more than once (never reduced to one)


def key_of(t: Any, side: str, line: float) -> Key:
    return (
        pd.Timestamp(t).tz_convert("UTC") if pd.Timestamp(t).tzinfo else pd.Timestamp(t, tz="UTC"),
        side,
        round(float(line), 2),
    )


def sim_side(plan: SpanPlan, until: pd.Timestamp | None = None) -> tuple[dict[Key, str], dict[Key, SimSetup]]:
    """The simulation's visit classes and setups from the replay's start to ``until`` (default: the compared
    window's end; the broker gate passes the replay's end so a correct trade of the tail is not a difference)."""
    classes: dict[Key, str] = {}
    setups: dict[Key, SimSetup] = {}
    stop = plan.cmp_end if until is None else until
    for o in plan.sim.outcomes:
        v = o.visit
        if not plan.start <= v.time < stop:
            continue
        k = key_of(v.time, v.side, v.line)
        classes[k] = o.reason if o.reason in SKIPS else "setup"
        s = o.setup
        if s is not None:
            setups[k] = SimSetup(
                k,
                s.outcome,
                {f.name: (f.j, f.price) for f in s.fills},
                s.be_j,
                s.be_sl,
                s.exit_j,
                s.how,
                s.exit_price,
                s.end_time,
                (s.p1, s.p2, s.sl, s.tp),
            )
    return classes, setups


def extract_fills(data: dict[str, Any]) -> tuple[dict[str, tuple[int, float, float]], list[str]]:
    """The runner's recorded fills by name, and the names recorded more than once (every entry is kept in the
    count: two identical P1 entries are a duplicate, not one fill)."""
    fills: dict[str, tuple[int, float, float]] = {}
    dups: list[str] = []
    for f in data.get("fills", []):
        if f["name"] in fills:
            dups.append(f["name"])
        fills[f["name"]] = (int(f["j"]), float(f["price"]), float(f["broker_price"]))
    return fills, dups


def run_side(
    rp: Replay, plan: SpanPlan
) -> tuple[dict[Key, tuple[str, int | None]], dict[Key, RunSetup], list[Key]]:
    """The runner's visit records and its chosen setups (rows), as the store has them."""
    store = rp.runner.store
    assert store is not None
    close_ns = rp.runner._exec_close_ns()
    classes: dict[Key, tuple[str, int | None]] = {}
    dup: list[Key] = []
    for r in store.visits():
        t = pd.Timestamp(r.hour_open)
        if not plan.start <= t < plan.cmp_end:
            continue
        k = key_of(t, r.side, r.line)
        if k in classes:
            dup.append(k)
        classes[k] = (r.classification, r.setup_id)
    setups: dict[Key, RunSetup] = {}
    for row in store.setups():
        if not row.chosen:
            continue
        t = pd.Timestamp(row.hour_open)
        if not plan.start <= t < plan.cmp_end:
            continue
        data = json.loads(row.fills_json or "{}")
        fills, dup_fills = extract_fills(data)
        exit_j = None
        if row.exit_time is not None:
            exit_j = int(np.searchsorted(close_ns, pd.Timestamp(row.exit_time).value, side="right"))
        k = key_of(t, row.side, row.line)
        if k in setups:
            dup.append(k)  # two chosen rows for one key: never overwritten, a fault
        setups[k] = RunSetup(
            k,
            row.outcome,
            row.state,
            fills,
            data.get("be_j"),
            data.get("be_sent"),
            row.be_sl,
            exit_j,
            row.exit_how,
            row.exit_price,
            row.exit_broker_price,
            None if row.end_close_time is None else pd.Timestamp(row.end_close_time),
            (row.p1, row.p2, row.sl, row.tp),
            (row.p1_sent, row.p2_sent, row.sl_sent, row.tp_sent),
            tuple(dup_fills),
        )
    return classes, setups, dup


# --- differences ---------------------------------------------------------------------------------------------------


@dataclass
class Diff:
    key: Key
    field: str
    sim: Any
    run: Any
    bar: int | None = None  # the exec bar that explains it
    cause: str = ""
    why: str = ""

    def line(self, ex_open: pd.Series | None = None) -> str:
        when = ""
        if self.bar is not None and ex_open is not None:
            when = f" bar {self.bar} ({ex_open.iloc[self.bar]:%Y-%m-%d %H:%M})"
        return (
            f"{self.key[0]:%Y-%m-%d %H:%M} {self.key[1]} {self.key[2]}: {self.field}: sim {self.sim!r} runner "
            f"{self.run!r}{when} -> {('suggested (advisory): ' + self.cause) if self.cause else 'no suggestion'} {self.why}"
        )


def close_to(a: float | None, b: float | None, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol + EPS


def compare_visits(
    sim: dict[Key, str], run: dict[Key, tuple[str, int | None]], run_setups: dict[Key, RunSetup]
) -> list[Diff]:
    out: list[Diff] = []
    for k in sorted(set(sim) | set(run)):
        s = sim.get(k)
        r = run.get(k)
        if s is None:
            out.append(Diff(k, "visit", None, r[0] if r else None))
        elif r is None:
            out.append(Diff(k, "visit", s, None))
        elif s != r[0]:
            out.append(Diff(k, "class", s, r[0]))
        elif s == "setup" and k not in run_setups:
            out.append(Diff(k, "class", s, "setup but no chosen row"))
    return out


def compare_setups(sim: dict[Key, SimSetup], run: dict[Key, RunSetup], tol: float = TICK) -> list[Diff]:
    out: list[Diff] = []
    for k in sorted(set(sim) | set(run)):
        s, r = sim.get(k), run.get(k)
        if s is None or r is None:
            out.append(Diff(k, "setup", "present" if s else None, "present" if r else None))
            continue
        if r.dup_fills:
            out.append(Diff(k, "duplicate fill", None, list(r.dup_fills)))
        if s.outcome != r.outcome:
            out.append(Diff(k, "outcome", s.outcome, r.outcome))
        for name in sorted(set(s.fills) | set(r.fills)):
            a, b = s.fills.get(name), r.fills.get(name)
            if a is None or b is None:
                out.append(Diff(k, f"fill {name}", a, b))
                continue
            if a[0] != b[0]:
                out.append(Diff(k, f"fill {name} bar", a[0], b[0]))
            if not close_to(a[1], b[2], tol) or not close_to(a[1], b[1], EPS):
                out.append(Diff(k, f"fill {name} price", a[1], (b[1], b[2])))
        if s.be_j != r.be_j:
            out.append(Diff(k, "be bar", s.be_j, r.be_j))
        elif s.be_j is not None:
            if not close_to(s.be_sl, r.be_sent, tol):
                out.append(Diff(k, "be stop", s.be_sl, r.be_sent))
            if not close_to(s.be_sl, r.be_sl, EPS):
                out.append(Diff(k, "be stop (logic)", s.be_sl, r.be_sl))
        if s.prices is not None and r.prices is not None:
            for nm, a, b, c in zip(
                ("P1", "P2", "SL", "TP"), s.prices, r.prices, r.sent or (None,) * 4, strict=True
            ):
                if not close_to(a, b, EPS):
                    out.append(Diff(k, f"plan {nm}", a, b))
                if c is not None and not close_to(a, c, 0.005 if nm in ("P1", "P2") else TICK):
                    out.append(Diff(k, f"plan {nm} as sent", a, c))
        if s.exit_j != r.exit_j:
            out.append(Diff(k, "exit bar", s.exit_j, r.exit_j))
        if s.how != r.how:
            out.append(Diff(k, "exit how", s.how, r.how))
        elif s.exit_j is not None and not (
            close_to(s.exit_price, r.exit_broker, tol) and close_to(s.exit_price, r.exit_price, EPS)
        ):
            out.append(Diff(k, "exit price", s.exit_price, (r.exit_price, r.exit_broker)))
        if s.end_time != r.end_time:
            out.append(Diff(k, "reservation end", s.end_time, r.end_time))
    return out


# --- one span, one mode -----------------------------------------------------------------------------------------------


@dataclass
class Record:
    """Everything of one replay the comparison and its explanations need (picklable: the runner is not)."""

    mode: str
    cycles: int
    skipped: int
    seconds: float
    events: list[Any]
    requests: list[Any]
    cycle_t: np.ndarray
    cycle_b: np.ndarray
    log_lines: list[tuple[str, str]]
    sim_classes: dict[Key, str]
    sim_setups: dict[Key, SimSetup]
    run_classes: dict[Key, tuple[str, int | None]]
    run_setups: dict[Key, RunSetup]
    dups: list[Key]
    end: pd.Timestamp  # where the replay stopped
    preclose: float
    cycle_seconds: float
    # the replay broker's own ledger (checked by tests/zone_replay_broker_gate.py), independent of the runner's rows
    setup_rows: dict[int, dict[str, Any]] = field(
        default_factory=dict
    )  # every setup row of the runner, by id
    deals: list[dict[str, Any]] = field(default_factory=list)  # every deal the broker made
    end_orders: list[tuple[str, float]] = field(
        default_factory=list
    )  # resting orders at the end: (comment, price)
    end_positions: list[tuple[str, float]] = field(default_factory=list)  # open positions at the end
    broker_ledger_present: bool = (
        False  # set only by ``broker_ledger``: without it the gate has no broker evidence
    )
    sim_all_setups: dict[Key, SimSetup] = field(
        default_factory=dict
    )  # the simulation's setups to the replay's end
    bar0: int = 0  # the exec row of the first bar of the replay
    bar_close_ns: np.ndarray | None = None  # the close times of the replay's exec bars
    bar_open_ns: np.ndarray | None = None  # ... and their open times
    cycle_a: np.ndarray | None = None  # the ask (cents) of each cycle: the SELL fallback of L5 reads it
    bar_spread: np.ndarray | None = None  # ... and their spreads (points), for ask = bid + spread
    px_open: np.ndarray | None = (
        None  # the exec bars' open prices from ``px_start`` (rule 3 reads open[j - per_h])
    )
    px_start: int = 0
    per_h: int = 4
    be_frac: float | None = None  # the plan's break-even fraction and mode: the P2 deadlines read them
    be_mode: str | None = None
    order_life_h: int | None = None  # the plan's order life (the expiry bar)
    # the runner's hours and stale data (L11.2): an uninterrupted replay has no undecided hour after its
    # first decided one, no stale-data removal and no interrupted setup
    decided_first: float | None = None
    undecided_hours: list[tuple[float, str]] = field(default_factory=list)
    stale_events: list[float] = field(default_factory=list)


def visit_near(bids: np.ndarray, buy: bool, line: float, z: float) -> np.ndarray:
    """Bid ticks (cents) within Z of the line, the band UNROUNDED as in the simulation (BUY: bid <= L + Z; SELL:
    bid >= L - Z)."""
    px = bids / 100.0
    return px <= line + z if buy else px >= line - z


def broker_ledger(rp: Replay, plan: SpanPlan) -> dict[str, Any]:
    """The replay broker's deals, resting orders and open positions, and every setup row, for the broker gate."""
    store = rp.runner.store
    assert store is not None
    fr = rp.full.frame(plan.tf)
    close_ns = fr["close_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
    open_ns = fr["open_time"].dt.tz_convert("UTC").to_numpy(dtype="datetime64[ns]").astype("int64")
    j0 = int(np.searchsorted(open_ns, plan.start.value, side="left"))
    j1 = int(np.searchsorted(close_ns, rp.end.value, side="right"))
    rows = {}
    per_h = PER_H[plan.tf]
    o_px, h_px, l_px, c_px = (fr[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    for r in store.setups(all_accounts=True):
        hour_s = pd.Timestamp(r.hour_open).value / 1e9
        z = plan.params.near_frac * r.step
        visit_t = (
            None  # the path's first tick within Z of the line in the hour's bars (independent of the runner)
        )
        visit_close = None
        jh = int(np.searchsorted(open_ns, pd.Timestamp(r.hour_open).value, side="left"))
        for jj in range(jh, min(jh + per_h, len(open_ns))):
            if open_ns[jj] / 1e9 >= hour_s + 3600:
                break
            bids, times = bar_path(
                o_px[jj],
                h_px[jj],
                l_px[jj],
                c_px[jj],
                open_ns[jj] / 1e9,
                close_ns[jj] / 1e9,
                rp.cfg.preclose_seconds,
            )
            near = visit_near(bids, r.side == "BUY", r.line, z)
            idx = np.flatnonzero(near)
            if len(idx):
                visit_t = float(times[idx[0]])
                visit_close = close_ns[jj] / 1e9
                break
        rows[int(r.id)] = {
            "hour_s": hour_s,
            "j_hour": jh,
            "p1": r.p1,
            "p2": r.p2,
            "sgn": 1 if r.side == "BUY" else -1,
            "cancel": plan.params.cancel_frac * r.step,
            "visit_t": visit_t,
            "visit_close": visit_close,
            "vband": (r.line + z) if r.side == "BUY" else (r.line - z),
            "key": key_of(pd.Timestamp(r.hour_open), r.side, r.line),
            "side": r.side,
            "chosen": bool(r.chosen),
            "state": r.state,
            "p1_sent": r.p1_sent,
            "p2_sent": r.p2_sent,
            "sl_sent": r.sl_sent,
            "tp_sent": r.tp_sent,
        }
    deals = [
        {
            "t": d.time_utc.timestamp(),
            "entry": d.entry,
            "comment": d.comment,
            "price": d.price,
            "position": d.position_id,
            "reason": d.reason,
            "volume": d.volume,
            "type": d.type,
            "magic": d.magic,
        }
        for d in rp.broker.deals_
    ]
    return {
        "broker_ledger_present": True,
        "sim_all_setups": sim_side(plan, rp.end)[1],
        "setup_rows": rows,
        "deals": deals,
        "end_orders": [(o.comment, o.price) for o in rp.broker.orders_.values()],
        "end_positions": [(p.comment, p.price_open) for p in rp.broker.positions_.values()],
        "bar0": j0,
        "bar_close_ns": close_ns[j0:j1],
        "bar_open_ns": open_ns[j0:j1],
        "bar_spread": fr["spread"].to_numpy(int)[j0:j1],
        "cycle_a": np.array([a for _t, _b, a in rp.cycle_log]),
        "px_open": o_px[max(j0 - per_h, 0) : j1],
        "px_start": max(j0 - per_h, 0),
        "per_h": per_h,
    }


def run_span(
    name: str,
    mode: str,
    full: Bars | None = None,
    base: ZoneParams | None = None,
    gate: bool = True,
    plan: SpanPlan | None = None,
    until: pd.Timestamp | None = None,
    progress: bool = False,
) -> tuple[SpanPlan, Record]:
    from tests.unit.zone_live_support import settings

    full = full if full is not None else load_bars("XAUUSD")
    if base is None:
        base, _v = load_params(ROOT / "data" / "bot_config.db", "XAUUSD", "default")
    plan = plan or plan_span(name, full, base)
    end = plan.end if until is None else min(until, plan.end)
    cfg = ReplayConfig(tf=plan.tf, mode=mode, epoch=plan.epoch, gate=gate)
    t0 = time.time()
    rp = Replay(full, plan.params, settings("DEMO"), cfg, plan.start, end)
    rp.progress = progress
    try:
        rp.run()
        sim_c, sim_s = sim_side(plan)
        run_c, run_s, dups = run_side(rp, plan)
        rec = Record(
            mode,
            rp.cycles,
            rp.skipped,
            time.time() - t0,
            list(rp.broker.events),
            list(rp.broker.requests),
            np.array([t for t, _b, _a in rp.cycle_log]),
            np.array([b for _t, b, _a in rp.cycle_log]),
            list(rp.collect.lines),
            sim_c,
            sim_s,
            run_c,
            run_s,
            dups,
            end,
            cfg.preclose_seconds,
            cfg.cycle_seconds,
            be_frac=plan.params.be_frac,
            be_mode=plan.params.be_mode,
            order_life_h=plan.params.order_life_h,
            decided_first=rp.decided_first,
            undecided_hours=sorted(rp.undecided_hours.items()),
            stale_events=list(rp.stale_events),
            **broker_ledger(rp, plan),
        )
    finally:
        rp.close()
    return plan, rec


def raw_diffs(rec: Record) -> list[Diff]:
    out = compare_visits(rec.sim_classes, rec.run_classes, rec.run_setups) + compare_setups(
        rec.sim_setups, rec.run_setups
    )
    return out + [Diff(k, "duplicate record", None, "two rows") for k in rec.dups]


def raw_report(plan: SpanPlan, rec: Record, full: Bars) -> str:
    ex_open = full.frame(plan.tf)["open_time"]
    lines = [
        f"{plan.name} {rec.mode}: replay {plan.start} .. {rec.end}, compare to {plan.cmp_end}",
        f"  cycles {rec.cycles} (skipped {rec.skipped}), {rec.seconds:.0f} s; "
        f"sim visits {len(rec.sim_classes)}, runner records {len(rec.run_classes)}, "
        f"sim setups {len(rec.sim_setups)}, runner setups {len(rec.run_setups)}",
        f"  sim classes {dict(Counter(rec.sim_classes.values()))}",
        f"  runner classes {dict(Counter(v[0] for v in rec.run_classes.values()))}",
        f"  runner log lines (WARNING+): {len(rec.log_lines)}",
    ]
    lines += [f"    {lvl}: {msg[:200]}" for lvl, msg in rec.log_lines[:40]]
    lines += ["  differences:"] + [f"    {d.line(ex_open)}" for d in raw_diffs(rec)]
    return "\n".join(lines)


def save(plan: SpanPlan, rec: Record, path: Path) -> None:
    import pickle

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump((plan, rec), fh)


def load(path: Path) -> tuple[SpanPlan, Record]:
    import pickle

    class _Unpickler(pickle.Unpickler):
        def find_class(self, module: str, name: str) -> Any:  # a record saved by ``python -m`` names __main__
            if module == "__main__":
                module = __name__
            return super().find_class(module, name)

    with open(path, "rb") as fh:
        plan, rec = _Unpickler(fh).load()
    problems = validate_record(rec)
    if problems:
        raise ValueError(f"{path}: not a usable replay record: {problems}")
    return plan, rec  # type: ignore[no-any-return]


def validate_record(rec: Any) -> list[str]:
    """What a record must carry for the gate: the broker's ledger, not only the runner's summaries."""
    out: list[str] = []
    if not isinstance(rec, Record):
        return ["not a Record"]
    for name in ("setup_rows", "deals", "end_orders", "end_positions", "sim_all_setups"):
        if not isinstance(getattr(rec, name, None), dict | list):
            out.append(f"{name} missing")
    if not getattr(rec, "broker_ledger_present", False):
        out.append("no broker ledger (a record from before the broker gate: run it again)")
    if getattr(rec, "be_frac", None) is None or getattr(rec, "be_mode", None) is None:
        out.append("no break-even parameters (be_frac / be_mode): run it again")
    if getattr(rec, "order_life_h", None) is None:
        out.append("no order_life_h: run it again")
    if getattr(rec, "bar_close_ns", None) is None:
        out.append("no bar close times")
    if getattr(rec, "bar_open_ns", None) is None:
        out.append("no bar open times")
    ca = getattr(rec, "cycle_a", None)
    if ca is None or len(ca) != len(getattr(rec, "cycle_t", [])):
        out.append("no cycle quotes (the ask of every cycle is required)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--span", choices=sorted(SPANS), required=True)
    ap.add_argument("--mode", choices=("tick", "poll"), required=True)
    ap.add_argument("--no-gate", action="store_true", help="run a cycle at every tick / slot (slow)")
    ap.add_argument(
        "--hours", type=float, default=0.0, help="stop the replay this many hours after its start"
    )
    ap.add_argument("--save", type=Path, default=None, help="pickle the record here")
    args = ap.parse_args(argv)
    full = load_bars("XAUUSD")
    base, _v = load_params(ROOT / "data" / "bot_config.db", "XAUUSD", "default")
    plan = plan_span(args.span, full, base)
    until = plan.start + pd.Timedelta(hours=args.hours) if args.hours else None
    plan, rec = run_span(
        args.span, args.mode, full, base, gate=not args.no_gate, plan=plan, until=until, progress=True
    )
    if args.save:
        save(plan, rec, args.save)
    print(raw_report(plan, rec, full))
    return 0


if __name__ == "__main__":
    from tests.zone_replay_compare import main as _main  # the classes of a pickle must live in the module

    sys.exit(_main())


def gate_failures(rec: Record) -> list[str]:
    """THE GATE (eye/ZONE_LIVE.md L11.2, "the gate is strict"): zero raw differences (prices within a tick, bars
    exact), no duplicate records, nothing wrong in the replay broker's own ledger (``zone_replay_broker_gate``: entries with
    SL / TP / lot / magic / unique comment, fills and exits equal to the simulation's, stops moved toward profit to the
    break-even, nothing resting or open that should not be) and no runner log line at ERROR or above. Whatever is returned is why the run
    does not pass; an empty list is a pass. No cause classifier is consulted."""
    from tests.zone_replay_broker_gate import broker_failures

    evidence = validate_record(rec)
    out = [f"no broker evidence: {m}" for m in evidence]
    out += [f"difference: {d.line()}" for d in raw_diffs(rec)]
    if not evidence:
        out += [f"broker: {m}" for m in broker_failures(rec)]
    out += [f"runner {lvl}: {msg[:200]}" for lvl, msg in rec.log_lines if lvl in ("ERROR", "CRITICAL")]
    out += interruption_failures(rec)
    return out


def interruption_failures(rec: Record) -> list[str]:
    """L11.2 - an uninterrupted replay: no undecided hour after the runner's first decided one, no stale-data
    removal, no setup ended `interrupted`."""
    out: list[str] = []
    first = rec.decided_first
    for t, why in rec.undecided_hours:
        if first is not None and t > first:
            out.append(f"undecided hour {pd.Timestamp(t, unit='s', tz='UTC')}: {why}")
    out += [
        f"stale data: a removal fell due at {pd.Timestamp(t, unit='s', tz='UTC')}" for t in rec.stale_events
    ]
    out += [f"interrupted: {msg[:200]}" for _lvl, msg in rec.log_lines if "ends interrupted" in msg]
    return out


Ledger = tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]


def ledger_of(rp: Replay) -> Ledger:
    """Every request the runner sent (the whole request: type, price, SL, TP, expiration, order / position ticket
    targets, comment, result) and every broker event, with times."""
    reqs = [
        (round(t, 3), tuple(sorted((k, str(v)) for k, v in q.items())), rc) for t, q, rc in rp.broker.requests
    ]
    evs = [(round(e.t, 3), e.kind, e.comment, e.price, e.detail) for e in rp.broker.events]
    return reqs, evs


def compare_ledgers(a: Ledger, b: Ledger) -> tuple[bool, str]:
    """Whether two ledgers are identical, and the first difference if not."""
    for name, x, y in (("request", a[0], b[0]), ("event", a[1], b[1])):
        if len(x) != len(y):
            return False, f"{name} count {len(x)} vs {len(y)}"
        for i, (p, q) in enumerate(zip(x, y, strict=True)):
            if p != q:
                return False, f"{name} {i} differs: {p} vs {q}"
    return True, "identical"


def gate_check(mode: str, start: str, end: str, tf: str = "M15") -> tuple[bool, str]:
    """Run the same window gated and ungated; the ledgers (requests with expiration and ticket targets, and
    broker events) must be identical."""
    from tests.unit.zone_live_support import settings

    full = load_bars("XAUUSD")
    base, _v = load_params(ROOT / "data" / "bot_config.db", "XAUUSD", "default")
    params = dataclasses.replace(base, exec_tf=tf)
    out: dict[bool, tuple[Ledger, int]] = {}
    for gate in (True, False):
        rp = Replay(
            full, params, settings("DEMO"), ReplayConfig(tf=tf, mode=mode, gate=gate), ts(start), ts(end)
        )
        try:
            rp.run()
            out[gate] = (ledger_of(rp), rp.cycles)
        finally:
            rp.close()
    same, why = compare_ledgers(out[True][0], out[False][0])
    return same, (
        f"{mode} {start} .. {end}: gated {out[True][1]} cycles, ungated {out[False][1]}; "
        f"{len(out[True][0][0])} requests, {len(out[True][0][1])} events; {why}"
    )
