"""The auditor's tests of the first developer's PLAN-1 runner `dev/plan1.py` (read only; audit round 3, 2026-10-20).

The developer's own `dev/test_plan1.py` (19 tests) checks the pieces by hand. These tests cover what it leaves open:
- the exam switch: `main()` without `--exam` never builds the exam, `--repro` reads only the learning M1, and `build`
  hands every piece the period, a tick reader that stops at the period's end and the run's slippage (the default 0);
- B2's wiring inside `asia_b2`: the slippage B2's simulator sees while it runs, `locate`'s bounds while it runs, the
  rows kept by their entry decision in [start, end);
- one position at a time, by its definition (not by the same loop): kept trades never overlap, and every dropped
  trade fills inside a kept trade that filled no later;
- a trade outside the period stops `build`.
Nothing here reads market data: every reader and piece is replaced by a stub that records its arguments.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/audit2/test_plan1_audit.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DEV = Path(__file__).resolve().parents[1] / "dev"
sys.path.insert(0, str(DEV))
import plan1 as L  # noqa: E402
from sweep_detector import ExamPeriodError  # noqa: E402

S = 10**9
MN = 60 * S
LEARN = (pd.Timestamp("2025-10-18", tz="UTC"), pd.Timestamp("2026-04-18", tz="UTC"))
EXAM = (pd.Timestamp("2026-04-18", tz="UTC"), pd.Timestamp("2026-10-18", tz="UTC"))


class Stop(Exception):
    """Raised by a stub to end a run after its arguments were recorded."""


# ---------------------------------------------------------------- the exam switch
def test_main_without_the_switch_never_builds_the_exam(monkeypatch):
    seen = []

    def build(exam, slip, extra, m=None):
        seen.append((exam, slip, extra, m))
        raise Stop

    monkeypatch.setattr(L, "build", build)
    monkeypatch.setattr(L, "load_m1", lambda *a, **k: pytest.fail("main read M1 itself"))
    for argv, want in (([], (False, 0.0, 0.0, None)),
                       (["--slippage", "0.07", "--extra", "1"], (False, 0.07, 1.0, None)),
                       (["--exam"], (True, 0.0, 0.0, None))):  # the stub records the switch; nothing is read
        with pytest.raises(Stop):
            L.main(argv)
        assert seen.pop() == want


def test_repro_reads_only_the_learning_m1(monkeypatch):
    seen = {}
    monkeypatch.setattr(L, "load_m1", lambda end, exam, reader=None: seen.setdefault("m1", (end, exam)) and "M")
    monkeypatch.setattr(L, "repro", lambda m: seen.setdefault("repro", m))
    monkeypatch.setattr(L, "build", lambda *a, **k: pytest.fail("--repro went to build directly"))
    L.main(["--repro"])
    assert seen == {"m1": (LEARN[1], False), "repro": "M"}


def _m1(start: str, days: int) -> pd.DataFrame:
    """A few hours of M1 bars a day (enough for indicators.bars); prices are irrelevant here."""
    idx = pd.DatetimeIndex([d + pd.Timedelta(minutes=k) for d in pd.bdate_range(start, periods=days, tz="UTC")
                            for k in range(0, 600, 10)])
    x = np.linspace(100, 110, len(idx))
    return pd.DataFrame(dict(open=x, high=x + 1, low=x - 1, close=x, tick_volume=1.0, spread=20.0), index=idx)


def _stub_pieces(monkeypatch, seen: dict, asia_rows=()):
    def asia(m, start, end, ticks, slip):
        seen["asia"] = (start, end, ticks.end, slip)
        return L.piece_rows("Asia B2", list(asia_rows))

    def london(mk, days, ticks, slip):
        seen["london"] = (days[0], days[-1], len(days), ticks.end, slip)
        return L.piece_rows("London ORB", [])

    def ny(days, ticks, slip, extra):
        seen["ny"] = (days[0], days[-1], ticks.end, slip, extra)
        return L.piece_rows("NY straddle", [])

    monkeypatch.setattr(L, "asia_b2", asia)
    monkeypatch.setattr(L, "london_orb", london)
    monkeypatch.setattr(L, "ny_straddle", ny)
    monkeypatch.setattr(L, "load_m1", lambda *a, **k: pytest.fail("build read M1 although m was given"))


def test_build_hands_every_piece_the_period_the_tick_end_and_the_slippage(monkeypatch):
    seen: dict = {}
    _stub_pieces(monkeypatch, seen)
    state = L.trend_state

    def trend_state(d1, t):
        seen["d1"] = d1
        return state(d1, t)

    monkeypatch.setattr(L, "trend_state", trend_state)
    every, A = L.build(False, 0.0, 0.0, _m1("2025-10-01", 30))
    assert len(every) == 0 and len(A) == 0
    # the state reads server-day D1 bars: 30 days of 00:00-09:50 UTC bars are 30 bars, each complete at its last
    # minute + 1 (09:51 UTC; avail, which state_at compares with the fill time)
    d1 = seen["d1"]
    assert len(d1) == 30 and (pd.DatetimeIndex(d1["avail"]).strftime("%H:%M") == "09:51").all()
    # learning: 2025-10-18 (a Saturday) .. 2026-04-17; the ticks stop at 2026-04-18; slippage 0 on every piece
    assert seen["asia"] == (LEARN[0], LEARN[1], LEARN[1], 0.0)
    assert seen["london"] == (pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-04-17", tz="UTC"), 130, LEARN[1], 0.0)
    assert seen["ny"] == (pd.Timestamp("2025-10-20", tz="UTC"), pd.Timestamp("2026-04-17", tz="UTC"), LEARN[1], 0.0, 0.0)
    seen.clear()
    L.build(False, 0.07, 1.0, _m1("2025-10-01", 30))
    assert seen["asia"][3] == 0.07 and seen["london"][4] == 0.07 and seen["ny"][3:] == (0.07, 1.0)
    seen.clear()
    L.build(True, 0.0, 0.0, _m1("2026-04-01", 30))  # only when asked: the exam, its ticks to 2026-10-18
    assert seen["asia"] == (EXAM[0], EXAM[1], EXAM[1], 0.0)
    assert seen["london"][:2] == (pd.Timestamp("2026-04-20", tz="UTC"), pd.Timestamp("2026-10-16", tz="UTC"))


def test_a_trade_outside_the_period_stops_build(monkeypatch):
    late = dict(t_dec=LEARN[1].value - MN, t_in=LEARN[1].value, t_out=LEARN[1].value + MN, side=1, entry=1.0, stop=0.0,
                risk=1.0, pnl=0.0, R=0.0, exit="time")
    _stub_pieces(monkeypatch, {}, asia_rows=[late])
    with pytest.raises(ExamPeriodError):
        L.build(False, 0.0, 0.0, _m1("2025-10-01", 30))


# ---------------------------------------------------------------- B2's wiring
class _TF:
    def __init__(self):
        self.avail = np.array([LEARN[0].value - 10 * MN, LEARN[0].value + MN], np.int64)
        self.c = np.array([1.0, 1.0])

    def scan(self, a, b):
        return [a, b]


def test_asia_b2_runs_b2_with_this_runs_slippage_and_bounds_and_keeps_entries_in_the_period(monkeypatch):
    import p2_trades as P2
    import p3_trades as T3
    import patterns as P

    old = (P2.SLIP, P.LEARN_START, P.EXAM_START)
    seen = {}
    monkeypatch.setattr(P, "level_inputs", lambda m: "Y")
    monkeypatch.setattr(P, "TF", lambda m, k: _TF())

    def locate(scan, tf, Y, news):
        seen.setdefault("bounds", set()).add((P.LEARN_START, P.EXAM_START))
        seen["scan"] = scan
        return pd.DataFrame(dict(entry=[1.0]))

    monkeypatch.setattr(P, "locate", locate)
    monkeypatch.setattr(P, "agree", lambda a, b, tf: a)
    # three candidates: Asia 2026-04-17 01:00 UTC (08:00 Thai), Asia 2026-04-18 01:00 (in the exam), London 06:30
    t_entry = [pd.Timestamp(x, tz="UTC").value for x in ("2026-04-17 01:00", "2026-04-18 01:00", "2026-04-17 06:30")]
    monkeypatch.setattr(T3, "candidates3", lambda C, tfs, s: pd.DataFrame(dict(t_entry=t_entry, side=1, stop=0.0)))

    def run_stream3(cands, tfs, ticks, news, cost, mode):
        seen["slip"], seen["cands"], seen["mode"], seen["cost"] = P2.SLIP, list(cands.t_entry), mode, cost
        return pd.DataFrame(dict(t_entry=cands.t_entry, entry_t=cands.t_entry + S, exit_t=cands.t_entry + 10 * MN, side=1,
                                 entry=2.0, stop=1.0, risk=1.0, pnl=0.5, R=0.5, exit="time"))

    monkeypatch.setattr(T3, "run_stream3", run_stream3)
    out = L.asia_b2(pd.DataFrame(), LEARN[0], LEARN[1], ticks=None, slip=0.0)
    assert seen["slip"] == 0.0 and seen["mode"] == "structure" and seen["cost"] == 0.0
    assert seen["bounds"] == {LEARN}  # locate ran inside the period's bounds
    assert seen["scan"] == [1, 2]  # the scan starts at the first bar complete at / after the period's start
    assert seen["cands"] == t_entry[:2]  # the Asia window only (07:00-09:00 Thai)
    assert out.t_dec.tolist() == [t_entry[0]] and out.t_in.tolist() == [t_entry[0] + S]  # the exam's entry dropped
    assert (P2.SLIP, P.LEARN_START, P.EXAM_START) == old  # restored
    L.asia_b2(pd.DataFrame(), LEARN[0], LEARN[1], ticks=None, slip=0.07)
    assert seen["slip"] == 0.07 and P2.SLIP == old[0]


# ---------------------------------------------------------------- one position at a time, by its definition
def _check_stream(T: pd.DataFrame, out: pd.DataFrame) -> None:
    kept = list(zip(out.t_in, out.t_out, strict=True))
    assert all(a[0] <= b[0] for a, b in zip(kept, kept[1:], strict=False))  # in fill order
    assert all(b[0] >= a[1] for a, b in zip(kept, kept[1:], strict=False))  # never two open at once (a fill AT an exit is free)
    ks = set(out.id)
    for r in T.itertuples():
        if r.id in ks:
            continue
        # a dropped trade fills while a kept trade is open (that trade filled no later than it)
        assert any(a <= r.t_in < b for a, b in kept), r


def test_one_position_at_a_time_by_its_definition():
    rng = np.random.default_rng(11)
    for _ in range(200):
        n = int(rng.integers(1, 40))
        a = rng.integers(0, 600, n)
        T = pd.DataFrame(dict(id=np.arange(n), piece=rng.choice(["x", "y", "z"], n), t_in=a * MN,
                              t_out=(a + rng.integers(1, 90, n)) * MN, pnl=0.0, R=0.0))
        out = L.stream(T.sample(frac=1.0, random_state=int(rng.integers(1 << 30))))  # input order must not matter
        _check_stream(T, out)
    # by hand: a fill exactly at the open trade's exit is taken; one 1 ns before it is not
    T = pd.DataFrame(dict(id=[0, 1, 2], t_in=[0, 10 * MN - 1, 10 * MN], t_out=[10 * MN, 20 * MN, 30 * MN], pnl=0.0, R=0.0))
    assert L.stream(T).id.tolist() == [0, 2]


@pytest.mark.xfail(strict=True, reason="QUESTION / proposal: argparse takes abbreviations by default, so `--exa` turns "
                   "the exam on; `argparse.ArgumentParser(..., allow_abbrev=False)` would accept only the full `--exam`")
def test_the_exam_switch_takes_no_abbreviation():
    with pytest.raises(SystemExit):
        L.parse(["--exa"])
