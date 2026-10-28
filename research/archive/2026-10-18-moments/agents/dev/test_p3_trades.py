"""p3_trades by hand: the pattern's invalidation, the close past a price, the trailing schedule, the moving stop
(break-even at +1 risk, the trailing steps, never back), the M5 turn, the late-entry and the M5 filters, the exit modes.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_p3_trades.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_trades as T  # noqa: E402  (first: it puts the dev folder on the path, also in a planted-bug copy)
import p2_trades as P2  # noqa: E402

S = 10**9
MN = 60 * S
NAN = np.nan


def ticks(rows, spread=0.2):
    t, b = zip(*rows, strict=True)
    b = np.array(b, float)
    return np.array(t, np.int64) * S, b, b + spread


def test_invalidation():
    assert T.invalidation("w", 1, [100.0, 106.0, 100.3], None) == 100.3
    assert T.invalidation("ihs", 1, [101.0, 106.0, 99.0, 106.5, 101.2], None) == 101.2  # the right shoulder
    assert T.invalidation("st", -1, [106.2, 100.8, 105.0], None) == 105.0  # the lower high
    assert T.invalidation("base", 1, None, [99.6, 100.6]) == 99.6 and T.invalidation("base", -1, None, [99.6, 100.6]) == 100.6


def test_close_exit_time():
    c = np.array([103.0, 50.0, 103.0, 99.0, 98.9, 103.0])
    t_open = np.arange(6, dtype=np.int64) * MN
    avail = t_open + MN
    # bars from 2 on (bar 1's 50 is before the entry); 99.0 = the price is not past it; 98.9 at bar 4 closes at 5 min
    assert T.close_exit_time(t_open, avail, c, 99.0, 1, 2 * MN, 6 * MN) == 5 * MN
    assert T.close_exit_time(t_open, avail, c, 99.0, 1, 2 * MN, 5 * MN - 1) is None  # bar 4 closes after the limit
    assert T.close_exit_time(t_open, avail, c, 102.0, -1, 2 * MN, 6 * MN) == 3 * MN  # a sell: 103 > 102 at bar 2
    assert T.close_exit_time(t_open, avail, c, 102.0, -1, 2 * MN + 1, 6 * MN) == 6 * MN  # bar 2 opens before


def test_trail_schedule():
    lt = np.array([np.nan, 99.0, 99.0, 101.0, 101.0])
    lp = np.array([np.nan, np.nan, 105.0, 105.0, 104.0])
    t_open = np.arange(5, dtype=np.int64) * MN
    tt, vv = T.trail_schedule(t_open, t_open + MN, lt, lp, 1, MN, 5 * MN, 0.5)
    assert tt.tolist() == [2 * MN, 3 * MN, 4 * MN, 5 * MN] and vv.tolist() == [98.5, 98.5, 100.5, 100.5]
    tt, vv = T.trail_schedule(t_open, t_open + MN, lt, lp, -1, MN, 4 * MN, 0.5)
    assert tt.tolist() == [2 * MN, 3 * MN, 4 * MN] and np.isnan(vv[0]) and vv[1:].tolist() == [105.5, 105.5]


def test_simulate3_without_a_trail_is_p2s_simulate():
    cases = [([(0, 100.0), (10, 99.0), (20, 97.5), (30, 101.0)], 98.0, NAN, None, 3600),
             ([(0, 100.0), (10, 103.9), (20, 104.6)], 98.0, 104.0, None, 3600),
             ([(0, 100.0), (10, 100.5), (20, 101.0), (30, 101.5)], 98.0, NAN, 15, 3600),
             ([(0, 100.0), (10, 100.5), (20, 101.0), (30, 101.5)], 98.0, NAN, None, 25)]
    for rows, stop, tgt, tc, lim in cases:
        t, bid, ask = ticks(rows)
        a = P2.simulate(t, bid, ask, 0, 1, stop, tgt, None if tc is None else tc * S, lim * S)
        b = T.simulate3(t, bid, ask, 0, 1, stop, tgt, None if tc is None else tc * S, lim * S)
        assert {k: b[k] for k in a} == a and np.isnan(b["stop_exit"]) == (a["exit"] != "stop") and b["t_be"] is None


NO_STEPS = (np.empty(0, np.int64), np.empty(0))


def test_break_even_at_one_risk():
    # in 100.27, the stop 98 (risk 2.27); the bid 102.6 at 20 s is one risk our way (2.33): the stop to 100.27; the bid
    # 100.1 at 30 s is below it - out 'trail' at 100.1
    t, bid, ask = ticks([(0, 100.0), (10, 101.0), (20, 102.6), (30, 100.1), (40, 95.0)])
    x = T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, None, 3600 * S, trail=NO_STEPS)
    assert (x["exit"], x["exit_t"], x["exit_px"], x["t_be"]) == ("trail", 30 * S, 100.1, 20 * S)
    assert x["stop_exit"] == pytest.approx(100.27) and x["pnl"] == pytest.approx(100.1 - 100.27)
    # before one risk our way the stop stays: 101.0 then 97.9 -> 'stop'
    t, bid, ask = ticks([(0, 100.0), (10, 101.0), (20, 97.9)])
    x = T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, None, 3600 * S, trail=NO_STEPS)
    assert (x["exit"], x["t_be"], x["stop_exit"]) == ("stop", None, 98.0)
    # one risk our way only AFTER the stop (103 at 30 s): no break-even time is reported (the look-ahead check found it)
    t, bid, ask = ticks([(0, 100.0), (10, 101.0), (20, 97.9), (30, 103.0)])
    x = T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, None, 3600 * S, trail=NO_STEPS)
    assert (x["exit"], x["exit_t"], x["t_be"]) == ("stop", 20 * S, None)


def test_break_even_at_exactly_one_risk(monkeypatch):
    # binary prices, no slippage: in 100.25 (ask), the stop 98.25 (risk 2.0); the bid 102.25 is exactly one risk
    monkeypatch.setattr(P2, "SLIP", 0.0)
    t = np.array([0, 10 * S, 20 * S], np.int64)
    bid = np.array([100.0, 102.25, 100.25])
    x = T.simulate3(t, bid, bid + 0.25, 0, 1, 98.25, NAN, None, 3600 * S, trail=NO_STEPS)
    assert x["t_be"] == 10 * S and x["exit"] == "trail" and x["exit_px"] == 100.25  # AT the break-even stop


def test_the_trailing_steps():
    # BE at 20 s (100.27); the bar closes: 15 s (before BE: ignored - it would have stopped the 101.2 at 30 s), 25 s
    # 99.0 (below BE: BE stays), 35 s 101.5 (the stop up to 101.5), 45 s 100.5 (never back); the bid 101.4 at 50 s is
    # below 101.5: out 'trail' at 101.4
    t, bid, ask = ticks([(0, 100.0), (20, 102.6), (30, 101.2), (40, 103.0), (50, 101.4), (60, 90.0)])
    steps = (np.array([15, 25, 35, 45], np.int64) * S, np.array([101.3, 99.0, 101.5, 100.5]))
    x = T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, None, 3600 * S, trail=steps)
    assert (x["exit"], x["exit_t"], x["exit_px"], x["stop_exit"]) == ("trail", 50 * S, 101.4, 101.5)
    # the bid 101.2 at 30 s did not exit: the stop was BE 100.27 then (the 35 s step not yet)
    steps_nan = (np.array([25, 35], np.int64) * S, np.array([np.nan, 101.5]))
    assert T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, None, 3600 * S, trail=steps_nan)["exit_t"] == 50 * S
    # a step AT a tick's time applies to that tick: the 35 s step -> a tick at 35 s below 101.5 exits there (not at
    # the next tick's break)
    t2, b2, a2 = ticks([(0, 100.0), (20, 102.6), (35, 101.45), (40, 102.0)])
    x = T.simulate3(t2, b2, a2, 0, 1, 98.0, NAN, None, 3600 * S, trail=steps)
    assert (x["exit"], x["exit_t"]) == ("trail", 35 * S)


def test_the_trailing_sell():
    # a sell in 99.93 (bid 100 - 0.07), the stop 102 (risk 2.07); the ask 97.8 (bid 97.6) is 2.13 our way: BE 99.93;
    # a step at 25 s of 98.5 (a sell's stop moves DOWN): the ask 98.6 (bid 98.4) at 30 s is above it - out 'trail'
    t, bid, ask = ticks([(0, 100.0), (20, 97.6), (30, 98.4)])
    steps = (np.array([25], np.int64) * S, np.array([98.5]))
    x = T.simulate3(t, bid, ask, 0, -1, 102.0, NAN, None, 3600 * S, trail=steps)
    assert (x["exit"], x["exit_px"], x["stop_exit"], x["t_be"]) == ("trail", pytest.approx(98.6), 98.5, 20 * S)
    assert x["pnl"] == pytest.approx(99.93 - 98.6)


def test_no_price_at_the_decision_no_trade():
    # the first tick 61 s after the decision (a Sunday evening without ticks): no trade; 60 s: a trade
    t, bid, ask = ticks([(61, 100.0), (120, 101.0)])
    assert T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, None, 3600 * S) is None
    t, bid, ask = ticks([(60, 100.0), (120, 101.0)])
    assert T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, None, 3600 * S)["entry_t"] == 60 * S


def test_run_stream3_keeps_ns_times_exact():
    # a break-even tick at 1.76e18 + 64 ns cannot live in a float64: the stream stores it as an integer
    base = 1_760_000_000_000_000_064
    t = np.array([base, base + 10 * S, base + 20 * S], np.int64)
    bid = np.array([100.0, 102.6, 100.1])
    tf = SimpleNamespace(t_open=np.array([base - MN], np.int64), avail=np.array([base], np.int64), c=np.array([100.0]),
                         minutes=1, piv=(np.empty(0, int), np.empty(0), np.empty(0, int), np.empty(0, int)))
    cands = pd.DataFrame([dict(t_entry=base, side=1, stop=98.0, risk_dec=2.0, tf="M1", next_level=np.nan, invalid=99.0,
                               atr=1.0)])

    class Tk:
        @staticmethod
        def span(_):
            return t, bid, bid + 0.2

    X = T.run_stream3(cands, {"M1": tf}, Tk(), np.array([0], np.int64), 0.0, "trail")
    assert X.t_be.dtype == "Int64" and int(X.t_be.iloc[0]) == base + 10 * S and X.exit.iloc[0] == "trail"


def test_the_close_exit_name_and_order():
    t, bid, ask = ticks([(0, 100.0), (10, 100.5), (20, 101.0)])
    x = T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, 15 * S, 3600 * S, close_name="invalid")
    assert (x["exit"], x["exit_t"]) == ("invalid", 20 * S)
    t, bid, ask = ticks([(0, 100.0), (20, 97.0)])  # the stop and the close exit on one tick: the stop
    assert T.simulate3(t, bid, ask, 0, 1, 98.0, NAN, 15 * S, 3600 * S, close_name="invalid")["exit"] == "stop"


def test_m5_turned():
    piv = (np.arange(4), np.array([100.0, 105.0, 101.0, 104.0]), np.array([-1, 1, -1, 1]), np.array([1, 2, 3, 4]))
    assert T.m5_turned(piv, 3, 1)  # troughs 100 -> 101: a higher low (confirmed by bar 3)
    assert not T.m5_turned(piv, 2, 1)  # only one trough confirmed by bar 2
    assert T.m5_turned(piv, 4, -1)  # peaks 105 -> 104: a lower high
    assert T.m5_turned(piv, 4, 1)  # the troughs confirmed by bar 4 are still 100 -> 101
    piv2 = (np.arange(4), np.array([101.0, 104.0, 100.0, 106.0]), np.array([-1, 1, -1, 1]), np.array([1, 2, 3, 4]))
    assert not T.m5_turned(piv2, 4, 1) and not T.m5_turned(piv2, 4, -1)  # a lower low; a higher high


# the hand case of P2's entry B: confirmed at bar 4 (close 106.2), the pull low 104.5
H = np.array([105.0, 106.0, 105.5, 105.8, 106.5])
LO = np.array([103.0, 104.5, 104.8, 104.5, 105.0])
C = np.array([104.5, 105.9, 105.0, 105.6, 106.2])


def fake_tf(h, lo, c, minutes=1, piv=None, last=0):
    t_open = np.arange(len(c), dtype=np.int64) * minutes * MN
    tf = SimpleNamespace(h=h, lo=lo, c=c, t_open=t_open, avail=t_open + minutes * MN, minutes=minutes,
                         atr=np.ones(len(c)), piv=piv)
    tf.last_complete = lambda t_ns: last
    return tf


def catch(**kw):
    base = dict(tf="M1", t_dec=MN, side=1, stop=99.8, close=104.5, extreme=100.0, atr=1.0, family="w", name="W",
                level_kind="x2", level=100.0, height=2.3, trigger=104.0, next_level=110.0, other_pattern="",
                other_structure="up", at_news=False, pts_p=[100.0, 104.0, 100.4], box_p=None)
    base.update(kw)
    return base


def tfs(m5_piv, last=3):
    return {"M1": fake_tf(H, LO, C), "M5": fake_tf(H, LO, C, 5, m5_piv, last)}


TURNED = (np.arange(4), np.array([100.0, 105.0, 101.0, 104.0]), np.array([-1, 1, -1, 1]), np.array([1, 2, 3, 4]))
NOT_TURNED = (np.arange(4), np.array([101.0, 105.0, 100.0, 104.0]), np.array([-1, 1, -1, 1]), np.array([1, 2, 3, 4]))


def test_candidates3_base_late_and_st():
    x = T.candidates3(pd.DataFrame([catch()]), tfs(TURNED), T.SETTINGS["B2"]).iloc[0]
    assert (x.t_entry, x.stop, x.close_k, x.invalid) == (5 * MN, 99.8, 106.2, 100.4)
    assert x.risk_dec == pytest.approx(106.2 - 99.8)
    # L: the confirming close 106.2 is 2.2 past the trigger 104: refused when the height is exactly that (covered),
    # kept at 2.3
    assert T.candidates3(pd.DataFrame([catch(height=float(C[4] - 104.0))]), tfs(TURNED), T.SETTINGS["L"]).empty
    assert len(T.candidates3(pd.DataFrame([catch(height=2.3)]), tfs(TURNED), T.SETTINGS["L"])) == 1
    # ST: a turn needs the M5 higher low or (M1) an M5 pattern; other families untouched
    st = T.SETTINGS["ST"]
    assert len(T.candidates3(pd.DataFrame([catch(family="st")]), tfs(TURNED), st)) == 1
    assert T.candidates3(pd.DataFrame([catch(family="st")]), tfs(NOT_TURNED), st).empty
    assert len(T.candidates3(pd.DataFrame([catch(family="st", other_pattern="W")]), tfs(NOT_TURNED), st)) == 1
    assert T.candidates3(pd.DataFrame([catch(family="st", other_pattern="W", tf="M5")]),
                         {"M1": fake_tf(H, LO, C), "M5": fake_tf(H, LO, C, 5, NOT_TURNED, 3)}, st).empty
    assert len(T.candidates3(pd.DataFrame([catch(family="w")]), tfs(NOT_TURNED), st)) == 1
    assert len(T.candidates3(pd.DataFrame([catch(family="st")]), tfs(NOT_TURNED), T.SETTINGS["B2"])) == 1


def test_candidates3_lead():
    lead = T.SETTINGS["LEAD"]
    assert len(T.candidates3(pd.DataFrame([catch(family="ihs")]), tfs(TURNED), lead)) == 1  # the H&S on M1
    assert T.candidates3(pd.DataFrame([catch(family="w")]), tfs(TURNED), lead).empty  # a W on M1
    m5 = {"M1": fake_tf(H, LO, C), "M5": fake_tf(H, LO, C, 5, TURNED, 3)}
    assert len(T.candidates3(pd.DataFrame([catch(family="w", tf="M5")]), m5, lead)) == 1  # any family on M5


def test_one_trade3_exit_modes():
    # flat 100.5 closes on the M1 bars except bar 2 (99.5, below the invalidation 100.0); ticks every 10 s
    c = np.full(100, 100.5)
    c[2] = 99.5
    tf = fake_tf(np.full(100, 101.0), np.full(100, 99.0), c)
    nan = np.full(100, np.nan)
    secs = np.arange(0, 7200, 10)
    t, bid = secs.astype(np.int64) * S, np.full(len(secs), 100.0)
    r = SimpleNamespace(t_entry=0, side=1, stop=98.0, next_level=np.nan, invalid=100.0, atr=1.0)
    x = T.one_trade3(r, tf, nan, nan, t, bid, bid + 0.2, 0.0, "invalid")
    assert (x["exit"], x["exit_t"], x["t_struct"]) == ("invalid", 3 * MN, 3 * MN)  # bar 2 closes at 3 min
    x = T.one_trade3(r, tf, nan, nan, t, bid, bid + 0.2, 0.0, "structure")  # no confirmed troughs: no structure exit
    assert x["exit"] == "time" and x["exit_t"] == 60 * MN and x["trail_t"] is None
    x = T.one_trade3(r, tf, nan, nan, t, bid, bid + 0.2, 0.0, "trail")
    assert x["exit"] == "time" and len(x["trail_t"]) == 60 and x["trail_t"][0] == MN
    x = T.one_trade3(r, tf, nan, nan, t, bid, bid + 0.2, 0.0, "invalid+trail")
    assert x["exit"] == "invalid" and x["trail_t"] is not None
    # a confirmed trough 100.6 above every close: the structure exit fires at bar 0's close; the trail mode has none
    lt = np.full(100, 100.6)
    assert T.one_trade3(r, tf, lt, nan, t, bid, bid + 0.2, 0.0, "structure")["exit"] == "structure"
    assert T.one_trade3(r, tf, lt, nan, t, bid, bid + 0.2, 0.0, "trail")["exit"] == "time"
    # an M5 trade: 60 M5 bars = 300 minutes
    tf5 = fake_tf(np.full(100, 101.0), np.full(100, 99.0), np.full(100, 100.5), minutes=5)
    assert T.one_trade3(r, tf5, nan, nan, t, bid, bid + 0.2, 0.0, "trail")["t_limit"] == 300 * MN


def test_metrics_table_counts_the_new_exits():
    A = pd.DataFrame(dict(variant="Xb", part="P1", news_cost=0.0, entry_t=[1, 2, 3], pnl=[1.0, -0.5, 2.0],
                          R=[0.5, -0.25, 1.0], exit=["trail", "trail", "invalid"]))
    m = T.metrics_table(A).iloc[0]
    assert (m.n, m.x_trail, m.x_invalid, m.x_stop) == (3, 2, 1, 0)
