"""plan1 by hand: the period and its exam guard (no exam data is read: fake readers), the Asia window, the London and
NY pieces on hand-made ticks, one position at a time, the D1 state read before the entry, the weights, the summary,
the weeks.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_plan1.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan1 as L  # noqa: E402
from sweep_detector import ExamPeriodError  # noqa: E402

S = 10**9
MN = 60 * S
UTC = "UTC"


def ts(x: str) -> pd.Timestamp:
    return pd.Timestamp(x, tz=UTC)


# ---------------------------------------------------------------- the period and the exam guard
def test_the_period_is_the_learning_parts_unless_the_switch():
    assert L.period(False) == (ts("2025-10-18"), ts("2026-04-18"))
    assert L.period(True) == (ts("2026-04-18"), ts("2026-10-18"))
    L.check_period(*L.period(False), False)
    L.check_period(*L.period(True), True)
    with pytest.raises(ExamPeriodError):  # one day into the exam without the switch
        L.check_period(ts("2025-10-18"), ts("2026-04-19"), False)
    with pytest.raises(ExamPeriodError):
        L.check_period(*L.period(True), False)
    with pytest.raises(ValueError):  # the switch reads the exam and nothing else
        L.check_period(ts("2025-10-18"), ts("2026-04-18"), True)
    with pytest.raises(ValueError):
        L.check_period(ts("2026-04-18"), ts("2026-10-19"), True)


def test_the_switch_and_the_defaults():
    a = L.parse([])
    assert (a.slippage, a.extra, a.exam, a.repro) == (0.0, 0.0, False, False)
    assert L.parse(["--exam"]).exam is True
    with pytest.raises(SystemExit):  # refused before anything is read
        L.main(["--exam", "--repro"])


def _never(*a, **k):
    raise AssertionError("the reader was called")


def test_m1_past_the_exam_start_is_refused_before_reading():
    with pytest.raises(ExamPeriodError):
        L.load_m1(ts("2026-04-18") + pd.Timedelta(minutes=1), False, reader=_never)
    with pytest.raises(ExamPeriodError):
        L.load_m1(L.EXAM_END, False, reader=_never)
    with pytest.raises(ValueError):
        L.load_m1(ts("2026-10-19"), True, reader=_never)


def _table(times: list[str]) -> pa.Table:
    t = pd.to_datetime(times, utc=True)
    return pa.table(dict(open_time=t, open=[1.0] * len(t), high=[2.0] * len(t), low=[0.5] * len(t), close=[1.5] * len(t),
                         tick_volume=[3.0] * len(t), spread=[20.0] * len(t)))


def test_m1_reader_gets_the_period_end_and_a_row_past_it_fails():
    seen = {}

    def reader(path, columns, filters):
        seen["filters"] = filters
        return _table(["2026-04-17 20:58", "2026-04-17 20:59", "2026-04-17 20:59"])

    m = L.load_m1(ts("2026-04-18"), False, reader=reader)
    assert seen["filters"] == [("open_time", ">=", ts("2025-09-01")), ("open_time", "<", ts("2026-04-18"))]
    assert len(m) == 2 and str(m.index.tz) == "UTC"  # the duplicate kept once
    with pytest.raises(ExamPeriodError):  # a reader that leaks a row at the end is caught
        L.load_m1(ts("2026-04-18"), False, reader=lambda *a, **k: _table(["2026-04-18 00:00"]))


def test_ticks_never_open_a_day_at_or_after_the_end():
    opened = []

    def read(d):
        opened.append(d)
        return np.array([d.value + S], np.int64), np.array([1.0]), np.array([1.2])

    tk = L.PlanTicks(ts("2026-04-18"), read=read)
    assert len(tk.day(ts("2026-04-17"))[0]) == 1
    assert len(tk.day(ts("2026-04-18"))[0]) == 0
    t, _, _ = tk.span(ts("2026-04-17 23:00").value)  # Friday joined to the (exam) Saturday: only Friday's tick
    assert len(t) == 1
    assert opened == [ts("2026-04-17")]
    assert all(d < ts("2026-04-18") for d in opened)


def test_the_guards_are_restored():
    import p2_trades as P2
    import patterns as P

    old = (P.LEARN_START, P.EXAM_START, P2.SLIP)
    with L.located_in(ts("2026-04-18"), ts("2026-10-18")):
        assert (P.LEARN_START, P.EXAM_START) == (ts("2026-04-18"), ts("2026-10-18"))
    with L.entry_slippage(0.0):
        assert P2.SLIP == 0.0
    assert (P.LEARN_START, P.EXAM_START, P2.SLIP) == old == (ts("2025-10-18"), ts("2026-04-18"), 0.07)


def test_parts_and_weekdays():
    assert L.part_of(ts("2026-01-15 23:59:59").value) == "P1"
    assert L.part_of(ts("2026-01-16").value) == "P2"
    assert L.part_of(ts("2026-04-17 23:59").value) == "P2"
    assert L.part_of(ts("2026-04-18").value) == "exam"
    assert L.part_of(ts("2025-10-17 23:59").value) == ""
    assert (L.weekdays("P1"), L.weekdays("P2")) == (64, 66)


# ---------------------------------------------------------------- the Asia window
def test_asia_window_is_07_to_09_thai_by_the_entry_decision():
    t = [ts("2026-01-14 23:59:59"), ts("2026-01-15 00:00"), ts("2026-01-15 01:59:59"), ts("2026-01-15 02:00"),
         ts("2026-01-15 06:30")]
    base = pd.DataFrame(dict(t_entry=[x.value for x in t], side=1, stop=1.0, risk_dec=1.0, tf="M1"))
    out = L.asia_candidates(base)
    assert out.t_entry.tolist() == [t[1].value, t[2].value]
    assert set(out.window) == {"Asia"}


# ---------------------------------------------------------------- the tick simulator
def test_exit_tick_by_hand_and_against_the_strategists_run_trade():
    t = np.array([0, 1, 2, 3, 4], np.int64) * S
    bid = np.array([100.0, 101.0, 97.5, 99.0, 99.0])
    ask = bid + 0.2
    assert L.exit_tick(t, bid, ask, 0, 100.2, 1, 98.0, 104.0, 10 * S) == (pytest.approx(-2.7), "stop", 2)
    assert L.exit_tick(t, bid, ask, 0, 100.2, 1, 90.0, None, 3 * S)[1:] == ("time", 3)
    assert L.exit_tick(t, bid, ask, 2, 97.0, -1, 103.0, 98.0, 10 * S) is None  # neither: runs out of ticks
    assert L.exit_tick(t, bid, ask, 0, 100.0, -1, 103.0, 97.7, 10 * S) == (pytest.approx(2.3), "target", 2)
    rng = np.random.default_rng(3)
    for _ in range(300):
        n = 200
        tt = np.cumsum(rng.integers(1, 4, n)).astype(np.int64) * S
        b = 100 + np.cumsum(rng.normal(0, 0.4, n))
        a = b + rng.uniform(0.1, 0.4, n)
        side = int(rng.choice([-1, 1]))
        e = a[0] if side > 0 else b[0]
        tgt = None if rng.random() < 0.3 else e + side * rng.uniform(1, 4)
        stop, t_out = e - side * rng.uniform(1, 4), int(tt[0] + rng.integers(50, 600) * S)
        x = L.tick_run(tt, b, a, 0, e, side, stop, tgt, t_out)  # raises if the copy disagrees with run_trade
        r = L.NF.run_trade(tt, b, a, 0, e, side, stop, tgt, t_out)
        assert (x is None) == (r is None)
        if x is not None:
            assert x[:2] == r and tt[x[2]] > tt[0]
            px = b[x[2]] if side > 0 else a[x[2]]
            assert x[1] == "target" or x[0] == pytest.approx((px - e) * side)


def test_tick_run_raises_when_the_copy_disagrees(monkeypatch):
    t = np.array([0, 1, 2], np.int64) * S
    bid, ask = np.array([100.0, 101.0, 102.0]), np.array([100.2, 101.2, 102.2])
    assert L.tick_run(t, bid, ask, 0, 100.2, 1, 98.0, None, 2 * S) == (pytest.approx(1.8), "time", 2)
    monkeypatch.setattr(L.NF, "run_trade", lambda *a: (5.0, "target"))
    with pytest.raises(AssertionError):  # both give an exit, a different one
        L.tick_run(t, bid, ask, 0, 100.2, 1, 98.0, None, 2 * S)
    with pytest.raises(AssertionError):  # only one gives an exit
        L.tick_run(t, bid, ask, 0, 100.2, 1, 98.0, None, 10 * S)


# ---------------------------------------------------------------- London ORB
def test_orb_trade_by_hand():
    t0 = ts("2026-01-14 06:21").value
    t = t0 + np.array([-5, 1, 60, 120, 1800], np.int64) * S
    bid = np.array([99.0, 100.0, 101.0, 104.5, 104.5])
    ask = bid + 0.2
    # fill 100.2 at t[1], risk 2.2, target 104.6: the bid 104.5 never reaches it, the ticks end before the hour: none
    assert L.orb_trade(t, bid, ask, t0, 1, 98.0, 0.0) is None
    bid2 = np.array([99.0, 100.0, 101.0, 104.7, 104.5])  # the target 104.6 reached at t[3], filled at 104.6
    x = L.orb_trade(t, bid2, bid2 + 0.2, t0, 1, 98.0, 0.0)
    assert (x["t_in"], x["entry"], x["risk"]) == (t[1], pytest.approx(100.2), pytest.approx(2.2))
    assert (x["exit"], x["t_out"], x["pnl"], x["R"]) == ("target", t[3], pytest.approx(4.4), pytest.approx(2.0))
    bid3 = np.array([99.0, 100.0, 101.0, 104.7, 105.0])
    x = L.orb_trade(t, bid3, bid3 + 0.2, t0, 1, 98.0, 0.07)  # the slippage on the fill: 100.27, risk 2.27, target 104.81
    assert (x["entry"], x["risk"], x["exit"], x["t_out"]) == (pytest.approx(100.27), pytest.approx(2.27), "target", t[4])
    x = L.orb_trade(t, bid2, bid2 + 0.2, t0, -1, 102.0, 0.07)  # a sell at the bid - slip: 99.93, risk 2.07
    assert (x["entry"], x["risk"], x["exit"]) == (pytest.approx(99.93), pytest.approx(2.07), "stop")
    # the time exit: the first tick at / after the fill + 60 minutes
    tt = t0 + np.array([1, 60, 3600, 3601], np.int64) * S  # the limit is the fill (+1 s) + 3600 s, not the decision's
    bb = np.array([100.0, 100.5, 100.8, 101.0])
    x = L.orb_trade(tt, bb, bb + 0.2, t0, 1, 98.0, 0.0)
    assert (x["exit"], x["t_out"], x["pnl"]) == ("time", tt[3], pytest.approx(0.8))
    late = t0 + np.array([301, 400], np.int64) * S  # the first tick 5 min 1 s after the decision: no trade
    assert L.orb_trade(late, np.array([100.0, 100.0]), np.array([100.2, 100.2]), t0, 1, 98.0, 0.0) is None
    edge = t0 + np.array([300, 400, 3900], np.int64) * S  # exactly 5 min: filled; out at fill + 60 min
    assert L.orb_trade(edge, np.array([100.0, 100.0, 100.0]), np.array([100.2, 100.2, 100.2]), t0, 1, 98.0, 0.0) is not None
    assert L.orb_trade(t, bid, ask, t0, 1, 100.3, 0.0) is None  # the fill already past the stop


# ---------------------------------------------------------------- NY straddle
def _ny_day(t0: int, moves: dict[int, tuple[float, float]], n: int = 1200, step: float = 2.5):
    """Ticks every `step` s from t0 - 15 min (bid 100, ask 100.3) with some seconds overridden: {seconds: (bid, ask)}."""
    t = t0 - 900 * S + (np.arange(n) * step * S).astype(np.int64)
    bid, ask = np.full(n, 100.0), np.full(n, 100.3)
    for sec, (b, a) in moves.items():
        k = int(np.searchsorted(t, t0 + sec * S))
        bid[k:], ask[k:] = b, a
    return t, bid, ask


def test_straddle_by_hand():
    t0 = L.ny_t0(pd.Timestamp("2026-01-14"))
    assert t0 == ts("2026-01-14 13:30").value  # winter: 08:30 NY = 13:30 UTC
    t, bid, ask = _ny_day(t0, {5: (102.1, 102.4), 600: (104.0, 104.3), 1795: (99.0, 99.3)})
    x = L.straddle(t, bid, ask, t0, 0.0)
    # the reference 100.0 / 100.3: a buy stop at 102.3, a sell stop at 98.0; the ask 102.4 at +5 s: a buy at 102.4
    assert (x["side"], x["entry"], x["stop"], x["risk"]) == (1, pytest.approx(102.4), pytest.approx(94.4), 8.0)
    assert x["exit"] == "time" and t[np.searchsorted(t, x["t_out"])] >= t0 + 1800 * S
    assert x["t_out"] == t[np.searchsorted(t, t0 + 1800 * S)] and x["pnl"] == pytest.approx(99.0 - 102.4)
    x = L.straddle(t, bid, ask, t0, 0.07, 1.0)
    assert x["entry"] == pytest.approx(103.47) and x["stop"] == pytest.approx(95.47)
    t, bid, ask = _ny_day(t0, {7: (97.9, 98.2), 60: (89.0, 89.3)})  # a sell at 97.9 - 0.07, the stop 105.83 not hit
    x = L.straddle(t, bid, ask, t0, 0.07)
    assert (x["side"], x["entry"], x["stop"]) == (-1, pytest.approx(97.83), pytest.approx(105.83))
    assert x["pnl"] == pytest.approx(97.83 - 89.3)
    t, bid, ask = _ny_day(t0, {5: (97.0, 102.5)})  # both triggers on one tick: the buy first
    assert L.straddle(t, bid, ask, t0, 0.0)["side"] == 1
    t, bid, ask = _ny_day(t0, {5: (101.9, 102.2)})  # the ask 102.2 is below the buy stop 102.3 (from the ask)
    assert L.straddle(t, bid, ask, t0, 0.0) is None
    t, bid, ask = _ny_day(t0, {0: (101.0, 101.3), 10: (101.0, 102.35)})  # the reference is the tick BEFORE 08:30:00
    assert L.straddle(t, bid, ask, t0, 0.0)["entry"] == pytest.approx(102.35)
    t, bid, ask = _ny_day(t0, {60: (103.0, 103.3)})  # at + 60 s: the orders are gone
    assert L.straddle(t, bid, ask, t0, 0.0) is None
    t, bid, ask = _ny_day(t0, {5: (102.1, 102.4), 30: (94.0, 94.3)})  # the stop on the bid at the gap tick
    x = L.straddle(t, bid, ask, t0, 0.0)
    assert (x["exit"], x["pnl"]) == ("stop", pytest.approx(94.0 - 102.4))
    t, bid, ask = _ny_day(t0, {5: (102.1, 102.4)}, n=999, step=3.0)  # fewer than 1000 ticks (to + 34 min): no trade
    assert L.straddle(t, bid, ask, t0, 0.0) is None
    t, bid, ask = _ny_day(t0, {5: (102.1, 102.4)}, n=1000, step=3.0)  # 1000: traded
    assert L.straddle(t, bid, ask, t0, 0.0)["side"] == 1
    t, bid, ask = _ny_day(t0, {5: (102.1, 102.4)})
    assert L.straddle(t[300:], bid[300:], ask[300:], t0, 0.0) is None  # the day's ticks start < 10 min before


def test_ny_t0_summer_and_winter():
    assert L.ny_t0(pd.Timestamp("2025-10-20")) == ts("2025-10-20 12:30").value  # EDT
    assert L.ny_t0(pd.Timestamp("2025-11-03")) == ts("2025-11-03 13:30").value  # EST from 2 Nov
    assert L.ny_t0(pd.Timestamp("2026-03-09")) == ts("2026-03-09 12:30").value  # EDT from 8 Mar


# ---------------------------------------------------------------- one position at a time
def _trades(rows):
    return pd.DataFrame([dict(piece=p, t_in=a * MN, t_out=b * MN, pnl=1.0, R=0.1) for p, a, b in rows])


def test_one_position_at_a_time():
    T = _trades([("E", 16, 20), ("A", 0, 10), ("B", 5, 6), ("C", 10, 15), ("D", 12, 13)])
    out = L.stream(T)
    # A kept; B fills inside A: dropped; C fills at A's exit: kept; D inside C: dropped; E after C: kept
    assert out.piece.tolist() == ["A", "C", "E"]


def test_stream_agrees_with_combo_stream():
    import combo

    rng = np.random.default_rng(5)
    a = np.sort(rng.integers(0, 10_000, 300)) * MN
    T = pd.DataFrame(dict(piece="x", t_in=a, t_out=a + rng.integers(1, 120, 300) * MN, pnl=0.0, R=0.0))
    C = T.assign(t_in=pd.to_datetime(T.t_in, utc=True), t_out=pd.to_datetime(T.t_out, utc=True))
    assert L.stream(T).t_in.tolist() == [x.value for x in combo.stream(C).t_in]


# ---------------------------------------------------------------- the D1 state and the weights
def _d1(closes, start="2025-11-03"):
    """Daily bars complete (avail) at 21:00 UTC of their day."""
    days = pd.bdate_range(start, periods=len(closes), tz=UTC)
    c = np.asarray(closes, float)
    return pd.DataFrame(dict(open=c, high=c + 1, low=c - 1, close=c, avail=days + pd.Timedelta(hours=21)))


def test_the_state_reads_only_the_d1_bars_complete_before():
    # 25 bars climbing (efficiency 1: trend), then 25 bars swinging +1 / -1 (efficiency 0: sideways)
    c = list(np.arange(100.0, 125.0)) + [124.0 + (k % 2) for k in range(1, 26)]
    d1 = _d1(c)
    av = d1.avail.to_numpy()
    k_last_trend = 24
    t_at = pd.Timestamp(av[k_last_trend]).value
    assert L.trend_state(d1, [t_at])[0] == "trend"  # bar 24 complete at its avail
    assert L.trend_state(d1, [t_at - 1])[0] == "trend"  # bar 23
    late = pd.Timestamp(av[49]).value
    assert L.trend_state(d1, [late])[0] == "sideways"
    # the bars after the moment do not count: change every bar after bar 24 - the state at bar 24's avail stays
    d2 = d1.copy()
    d2.loc[25:, ["open", "high", "low", "close"]] = 1000.0
    assert L.trend_state(d2, [t_at, t_at + 3600 * S])[0] == "trend"
    assert L.trend_state(d2, [t_at + 3600 * S])[0] == "trend"
    # ... and a change of the bars before it does (power)
    d3 = d1.copy()
    d3.loc[4:24, "close"] = [124.0 + (k % 2) for k in range(21)]  # net 0 over the 20 days before bar 24
    assert L.trend_state(d3, [t_at])[0] == "sideways"
    assert L.trend_state(d3, [t_at - 1])[0] == "trend"  # one ns before bar 24 is complete: bar 23 (net 22 over a path of 40: 0.55)


def test_weights_by_mechanism_and_from_p1():
    T = pd.DataFrame(dict(piece=["Asia B2", "Asia B2", "London ORB", "London ORB", "NY straddle", "NY straddle", "NY straddle"],
                          trend=["trend", "mixed", "trend", "sideways", "trend", "mixed", "sideways"]))
    assert L.weights(T, L.W_MECH).tolist() == [0.5, 1, 0.5, 1, 1, 0.5, 0.5]
    assert L.weights(T, L.W_P1).tolist() == [0.5, 1, 1, 1, 1, 1, 0.5]  # the P1 table: Asia trend, NY sideways
    P = pd.DataFrame(dict(piece=["Asia B2"] * 3 + ["London ORB"] * 2 + ["NY straddle"] * 2,
                          trend=["trend", "trend", "mixed", "trend", "trend", "mixed", "mixed"],
                          part=["P1", "P1", "P1", "P1", "P2", "P1", "P1"],
                          R=[-1.0, 0.5, -0.2, 0.0, -5.0, 1.0, -1.0]))
    # Asia trend mean -0.25 < 0: 0.5; Asia mixed -0.2: 0.5; London trend P1 0.0 (P2 ignored): no; NY mixed 0.0: no
    assert L.p1_weights(P) == {("Asia B2", "trend"): 0.5, ("Asia B2", "mixed"): 0.5}


def test_summary_by_hand():
    T = pd.DataFrame(dict(t_in=[3, 1, 2], R=[2.0, 1.0, -1.0], pnl=[20.0, 10.0, -5.0]))  # time order: 1, 2, 3
    s = L.summary(T, np.array([1.0, 1.0, 0.5]), "P1")
    # in time order R 1, -1, 2 with w 1, 0.5, 1: mean (1 - 0.5 + 2) / 2.5 = 1.0; USD 10 - 2.5 + 20 = 27.5
    assert s["R"] == pytest.approx(1.0) and s["usd"] == pytest.approx(27.5)
    assert (s["dd"], s["worst"], s["streak"], s["streak_usd"]) == (pytest.approx(2.5), pytest.approx(-2.5), 1, pytest.approx(-2.5))
    # the half range: 1.96 sqrt((1 x 0 + 0.25 x 4 + 1 x 1) x 3 / 2) / 2.5 = 1.3579
    assert s["R_hi"] - s["R"] == pytest.approx(1.96 * np.sqrt(3.0) / 2.5)
    assert s["win"] == pytest.approx(2 / 3) and s["per_day"] == pytest.approx(3 / 64) and s["n"] == 3
    u = L.summary(T)
    r = np.array([1.0, -1.0, 2.0])
    assert u["R"] == pytest.approx(2 / 3) and u["R_hi"] - u["R"] == pytest.approx(1.96 * r.std(ddof=1) / np.sqrt(3))
    assert u["usd"] == pytest.approx(25.0) and u["dd"] == pytest.approx(5.0)
    L4 = pd.DataFrame(dict(t_in=[4, 1, 3, 2], R=[-1.0, -1.0, 0.0, -0.5], pnl=[-1.0, -3.0, 0.0, -2.0]))  # time order -3, -2, 0, -1
    s = L.summary(L4)
    assert (s["streak"], s["streak_usd"], s["dd"]) == (2, pytest.approx(-5.0), pytest.approx(6.0))  # 0.0 ends a streak


def test_weeks_are_thai_weeks():
    T = pd.DataFrame(dict(t_in=[ts("2026-01-11 16:59").value, ts("2026-01-11 17:01").value, ts("2026-01-16 05:00").value],
                          R=[1.0, -1.0, 0.5], pnl=[10.0, -10.0, 5.0], w_mech=[1.0, 0.5, 1.0], w_p1=[0.5, 1.0, 1.0]))
    W = L.weekly(T)
    # 16:59 UTC Sunday = 23:59 Thai Sunday (the week of 5 Jan); 17:01 UTC = 00:01 Thai Monday 12 Jan
    assert [str(x) for x in W.week] == ["2026-01-05", "2026-01-12"]
    assert W.trades.tolist() == [1, 2] and W.usd.tolist() == [10.0, -5.0] and W.usd_total.tolist() == [10.0, 5.0]
    assert W.R_mech.tolist() == [1.0, round((-0.5 + 0.5) / 1.5, 3)] and W.usd_mech.tolist() == [10.0, 0.0]
    assert W.R_p1.tolist() == [1.0, -0.25] and W.usd_p1.tolist() == [5.0, -5.0]
