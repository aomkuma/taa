"""p2_trades by hand: entry B's confirmation, the last confirmed pivots, the structure exit, the tick simulation (stop
with its gap, target, structure, time, break, costs, the order on one tick), news entries, the agreement groups, the
candidates, the one-at-a-time stream, the statistics and the losers' reasons.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_p2_trades.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p2_trades as T  # noqa: E402

S = 10**9
MN = 60 * S

# --- entry B ------------------------------------------------------------------------------------------------------

#            d=0    1      2      3      4
H = np.array([105.0, 106.0, 105.5, 105.8, 106.5])
LO = np.array([103.0, 104.5, 104.8, 104.5, 105.0])
C = np.array([104.5, 105.9, 105.0, 105.6, 106.2])


def test_confirm_b_by_hand():
    # bar 1 makes a new high (106: the post-breakout high, not a pullback); bar 2's low 104.8 is 1.2 >= 1 ATR below:
    # the pullback, the high frozen at 106; bar 3 dips to 104.5 (the pullback low), closes 105.6; bar 4 closes 106.2 >
    # 106: confirmed at bar 4
    assert T.confirm_b(H, LO, C, 0, 100.0, 1.0, 1) == dict(k=4, hi=106.0, pull=104.5)


def test_confirm_b_fails():
    lo = LO.copy()
    lo[3] = 100.0  # a low reaches the pattern's extreme before the confirmation: no trade
    assert T.confirm_b(H, lo, C, 0, 100.0, 1.0, 1) is None
    assert T.confirm_b(H, LO, C, 0, 100.0, 1.0, 1, max_wait=3) is None  # the confirmation is the 4th bar after d
    # with 1.25 ATR the pullback comes only at bar 3 (106 - 104.5 = 1.5; bar 2's 1.2 is short) and bar 4 confirms;
    # with 1.6 ATR there is no pullback (bar 4 makes a new high): no trade
    assert T.confirm_b(H, LO, C, 0, 100.0, 1.25, 1) == dict(k=4, hi=106.0, pull=104.5)
    assert T.confirm_b(H, LO, C, 0, 100.0, 1.6, 1) is None


def test_confirm_b_pullback_threshold_and_new_high_bars():
    # exactly 1 ATR below counts as the pullback: bar 2's low 105.0 (106 - 1.0) is the only dip; bar 4 confirms
    lo = np.array([103.0, 104.5, 105.0, 105.3, 105.4])
    c = np.array([104.5, 105.9, 105.2, 105.6, 106.2])
    assert T.confirm_b(H, lo, c, 0, 100.0, 1.0, 1) == dict(k=4, hi=106.0, pull=105.0)
    # a bar making a new high is not the pullback even when its low is deep; the close above before any pullback is
    # not a confirmation
    h = np.array([105.0, 106.0, 106.5, 106.3, 106.0, 107.0])
    lo2 = np.array([103.0, 105.5, 104.0, 105.8, 105.4, 106.0])
    c = np.array([104.5, 105.9, 106.4, 106.0, 105.6, 106.9])
    # bar 2: new high 106.5 (its low 104.0 ignored); bar 3: 106.5 - 105.8 = 0.7 < 1; bar 4: 106.5 - 105.4 = 1.1 ->
    # pullback; bar 5 closes 106.9 > 106.5 -> confirmed, pull 105.4
    assert T.confirm_b(h, lo2, c, 0, 100.0, 1.0, 1) == dict(k=5, hi=106.5, pull=105.4)


def test_confirm_b_closes_at_the_high_is_not_above():
    c = C.copy()
    c[4] = 106.0
    assert T.confirm_b(H, LO, c, 0, 100.0, 1.0, 1) is None


def test_confirm_b_sell_is_the_mirror():
    x = T.confirm_b(-LO, -H, -C, 0, -100.0, 1.0, -1)
    assert x == dict(k=4, hi=-106.0, pull=-104.5)


# --- the structure exit -------------------------------------------------------------------------------------------

PIV = (np.array([1, 4, 7]), np.array([99.0, 105.0, 101.0]), np.array([-1, 1, -1]), np.array([3, 6, 9]))


def test_last_pivot_prices():
    lt, lp = T.last_pivot_prices(PIV, 11)
    assert np.isnan(lt[:3]).all() and lt[3:9].tolist() == [99.0] * 6 and lt[9:].tolist() == [101.0] * 2
    assert np.isnan(lp[:6]).all() and lp[6:].tolist() == [105.0] * 5


def bars(c):
    t_open = np.arange(len(c), dtype=np.int64) * MN
    return t_open, t_open + MN, np.asarray(c, float)


def test_structure_exit_time():
    lt, lp = T.last_pivot_prices(PIV, 11)
    c = np.full(11, 103.0)
    c[2] = 50.0  # before the entry: not read
    c[5] = 98.9  # below the last confirmed trough 99 at bar 5
    t_open, avail, cc = bars(c)
    assert T.structure_exit_time(t_open, avail, cc, lt, lp, 1, 3 * MN, 10 * MN) == 6 * MN  # bar 5 closes at 6 min
    c[5] = 99.0  # a close AT the trough is not below it
    t_open, avail, cc = bars(c)
    assert T.structure_exit_time(t_open, avail, cc, lt, lp, 1, 3 * MN, 9 * MN) is None
    c[5] = 103.0
    c[9] = 100.9  # below the trough 101 confirmed at bar 9; bar 9 closes at 10 min = the limit: counts
    t_open, avail, cc = bars(c)
    assert T.structure_exit_time(t_open, avail, cc, lt, lp, 1, 3 * MN, 10 * MN) == 10 * MN
    assert T.structure_exit_time(t_open, avail, cc, lt, lp, 1, 3 * MN, 10 * MN - 1) is None  # bar 9 closes after it
    # a sell: a close above the last confirmed peak (105 from bar 6)
    c = np.full(11, 103.0)
    c[7] = 105.1
    t_open, avail, cc = bars(c)
    assert T.structure_exit_time(t_open, avail, cc, lt, lp, -1, 3 * MN, 10 * MN) == 8 * MN
    assert T.structure_exit_time(t_open, avail, cc, lt, lp, -1, 7 * MN + 1, 10 * MN) is None  # bar 7 opens before


# --- the tick simulation ------------------------------------------------------------------------------------------


def ticks(rows):
    t, b = zip(*rows, strict=True)
    b = np.array(b, float)
    return np.array(t, np.int64) * S, b, b + 0.2


def test_simulate_stop_with_its_gap():
    # in at 0 s: ask 100.2 + 0.07 = 100.27; stop 98: bid 99 (10 s), then 97.5 (20 s) - filled at 97.5
    t, bid, ask = ticks([(0, 100.0), (10, 99.0), (20, 97.5), (30, 101.0)])
    x = T.simulate(t, bid, ask, 0, 1, 98.0, np.nan, None, 3600 * S)
    assert x["exit"] == "stop" and x["exit_px"] == 97.5 and x["exit_t"] == 20 * S
    assert x["entry"] == pytest.approx(100.27) and x["risk"] == pytest.approx(2.27)
    assert x["pnl"] == pytest.approx(-2.77) and x["R"] == pytest.approx(-2.77 / 2.27)
    # a tick exactly AT the stop fills it
    t, bid, ask = ticks([(0, 100.0), (10, 98.0), (20, 97.0)])
    assert T.simulate(t, bid, ask, 0, 1, 98.0, np.nan, None, 3600 * S)["exit_t"] == 10 * S


def test_simulate_target_is_a_limit():
    t, bid, ask = ticks([(0, 100.0), (10, 103.9), (20, 104.6)])
    x = T.simulate(t, bid, ask, 0, 1, 98.0, 104.0, None, 3600 * S)
    assert x["exit"] == "target" and x["exit_px"] == 104.0 and x["pnl"] == pytest.approx(3.73)


def test_simulate_structure_time_break_and_order():
    t, bid, ask = ticks([(0, 100.0), (10, 100.5), (20, 101.0), (30, 101.5)])
    x = T.simulate(t, bid, ask, 0, 1, 98.0, np.nan, 15 * S, 3600 * S)
    assert (x["exit"], x["exit_t"], x["exit_px"]) == ("structure", 20 * S, 101.0)  # the first tick at / after 15 s
    assert T.simulate(t, bid, ask, 0, 1, 98.0, np.nan, 20 * S, 3600 * S)["exit_t"] == 20 * S  # a tick AT the time
    x = T.simulate(t, bid, ask, 0, 1, 98.0, np.nan, None, 25 * S)
    assert (x["exit"], x["exit_t"]) == ("time", 30 * S)
    # the ticks end before the limit: out at the last tick
    assert T.simulate(t, bid, ask, 0, 1, 98.0, np.nan, None, 3600 * S)["exit"] == "break"
    # a gap of more than 30 minutes: out at the tick before it
    t2, b2, a2 = ticks([(0, 100.0), (10, 100.5), (10 + 1801, 90.0)])
    x = T.simulate(t2, b2, a2, 0, 1, 98.0, np.nan, None, 7200 * S)
    assert (x["exit"], x["exit_t"], x["exit_px"]) == ("break", 10 * S, 100.5)
    t3, b3, a3 = ticks([(0, 100.0), (10, 100.5), (10 + 1800, 101.0)])  # exactly 30 minutes is not a break
    assert T.simulate(t3, b3, a3, 0, 1, 98.0, np.nan, None, 7200 * S)["exit_t"] == 1810 * S
    # on one tick the stop comes before the structure exit
    t4, b4, a4 = ticks([(0, 100.0), (20, 97.0)])
    assert T.simulate(t4, b4, a4, 0, 1, 98.0, np.nan, 15 * S, 3600 * S)["exit"] == "stop"


def test_simulate_sell_costs_and_refusals():
    # a sell: in at bid 100 - 0.07 - 1.0 (a news trade) = 98.93; the stop 102 on the ask (101.9 + 0.2 = 102.1 at 10 s)
    t, bid, ask = ticks([(0, 100.0), (10, 101.9), (20, 99.0)])
    x = T.simulate(t, bid, ask, 0, -1, 102.0, np.nan, None, 3600 * S, extra=1.0)
    assert x["entry"] == pytest.approx(98.93) and x["exit"] == "stop" and x["exit_px"] == pytest.approx(102.1)
    assert x["pnl"] == pytest.approx(98.93 - 102.1) and x["risk"] == pytest.approx(3.07)
    # the sell's target on the ask: 99.0 + 0.2 = 99.2 <= 99.2
    t, bid, ask = ticks([(0, 100.0), (10, 99.0)])
    assert T.simulate(t, bid, ask, 0, -1, 102.0, 99.2, None, 3600 * S)["exit"] == "target"
    # the fill already past the stop; no tick at / after the entry
    assert T.simulate(t, bid, ask, 0, 1, 100.5, np.nan, None, 3600 * S) is None
    assert T.simulate(t, bid, ask, 11 * S, 1, 90.0, np.nan, None, 3600 * S) is None
    # the entry is the first tick AT / after t_entry
    x = T.simulate(t, bid, ask, 10 * S, -1, 102.0, np.nan, None, 3600 * S)
    assert x["entry_t"] == 10 * S and x["entry"] == pytest.approx(98.93)


# --- news, agreement, candidates, the stream ----------------------------------------------------------------------


def test_is_news():
    news = np.array([1000 * S, 5000 * S])
    assert [T.is_news(x * S, news) for x in (999, 1000, 1900, 1901, 5000)] == [False, True, True, False, True]


def test_agreement_group():
    assert T.agreement_group("M", "down", 1) == "with"
    assert T.agreement_group("", "up", 1) == "with" and T.agreement_group("", "down", -1) == "with"
    assert T.agreement_group("", "down", 1) == "against" and T.agreement_group("", "up", -1) == "against"
    assert T.agreement_group("", "mixed", 1) == "mixed / none" and T.agreement_group("", "none", -1) == "mixed / none"


def fake_tf(h, lo, c, minutes=1):
    t_open = np.arange(len(c), dtype=np.int64) * minutes * MN
    return SimpleNamespace(h=h, lo=lo, c=c, t_open=t_open, avail=t_open + minutes * MN, minutes=minutes, atr=np.ones(len(c)))


def catch(**kw):
    base = dict(tf="M1", t_dec=MN, side=1, stop=99.8, close=104.5, extreme=100.0, atr=1.0, family="w", name="W",
                level_kind="x2", height=5.0, next_level=110.0, other_pattern="", other_structure="up", at_news=False)
    base.update(kw)
    return base


def test_candidates_a_and_b():
    tfs = {"M1": fake_tf(H, LO, C)}
    Cf = pd.DataFrame([catch()])
    a = T.candidates(Cf, tfs, "A").iloc[0]
    assert (a.t_entry, a.stop, a.risk_dec, a.agree) == (MN, 99.8, pytest.approx(4.7), "with")
    b1 = T.candidates(Cf, tfs, "B1").iloc[0]  # confirmed at bar 4 (closes at 5 min); stop 104.5 - 0.2
    assert (b1.t_entry, b1.stop, b1.pull) == (5 * MN, pytest.approx(104.3), 104.5)
    assert b1.risk_dec == pytest.approx(106.2 - 104.3)
    b2 = T.candidates(Cf, tfs, "B2").iloc[0]
    assert (b2.t_entry, b2.stop) == (5 * MN, 99.8)
    # no confirmation: no B candidate; the order: by entry time, then the smaller decision risk
    lo = LO.copy()
    lo[3] = 100.0
    assert T.candidates(Cf, {"M1": fake_tf(H, lo, C)}, "B1").empty
    two = pd.DataFrame([catch(stop=99.0), catch(stop=101.0, family="ihs")])
    assert T.candidates(two, tfs, "A").family.tolist() == ["ihs", "w"]  # risk 3.5 before 5.5


class FakeTicks:
    def __init__(self, t, bid, ask):
        self.v = (t, bid, ask)

    def span(self, t_ns):
        return self.v


def test_run_stream_one_at_a_time_target_and_news():
    # the M1 bars: flat 100.5 closes (no structure exit: no confirmed pivots); ticks every 10 s
    n = 200
    tf = fake_tf(np.full(n, 101.0), np.full(n, 100.0), np.full(n, 100.5))
    tf.piv = (np.empty(0, int), np.empty(0), np.empty(0, int), np.empty(0, int))
    secs = np.arange(0, 10000, 10)
    bid = np.full(len(secs), 100.0)
    bid[secs >= 300] = 104.0  # at 300 s the bid jumps to 104
    t, ask = secs.astype(np.int64) * S, bid + 0.2
    cands = pd.DataFrame([
        dict(t_entry=0, side=1, stop=98.0, risk_dec=2.0, tf="M1", next_level=103.0),  # in 100.27; 103 > 1 risk: target
        dict(t_entry=100 * S, side=1, stop=98.0, risk_dec=2.0, tf="M1", next_level=np.nan),  # before the exit: skipped
        dict(t_entry=300 * S, side=1, stop=102.0, risk_dec=2.0, tf="M1", next_level=np.nan),  # AT the exit: taken
        dict(t_entry=4000 * S, side=1, stop=102.0, risk_dec=2.0, tf="M1", next_level=105.0),  # within one risk: no target
    ])
    news = np.array([3995 * S])
    X = T.run_stream(cands, {"M1": tf}, FakeTicks(t, bid, ask), news, 1.0)
    assert X.t_entry.tolist() == [0, 300 * S, 4000 * S]
    first, second, third = X.iloc[0], X.iloc[1], X.iloc[2]
    assert first.exit == "target" and first.exit_t == 300 * S and first.pnl == pytest.approx(103.0 - 100.27)
    assert not first.news and not second.news and second.entry == pytest.approx(104.27)
    assert second.exit == "time" and second.exit_t == (300 + 3600) * S  # 60 M1 bars
    assert third.news and np.isnan(third.target) and third.entry == pytest.approx(104.2 + 0.07 + 1.0)  # the news cost
    assert third.exit == "time" and third.exit_t == (4000 + 3600) * S


def test_one_trade_target_needs_more_than_one_risk(monkeypatch):
    # exact binary prices, no slippage: in at the ask 100.25, the stop 98.25 -> risk 2.0; a next level exactly 2.0 away
    # (102.25) is not MORE than one risk; 102.5 is
    monkeypatch.setattr(T, "SLIP", 0.0)
    tf = fake_tf(np.full(100, 101.0), np.full(100, 100.0), np.full(100, 100.5))
    t, bid = np.array([0, 10 * S, 20 * S], np.int64), np.array([100.0, 102.5, 103.0])
    ask = bid + 0.25
    nan = np.full(100, np.nan)
    r = SimpleNamespace(t_entry=0, side=1, stop=98.25, next_level=102.25)
    x = T.one_trade(r, tf, nan, nan, t, bid, ask, 0.0)
    assert x["entry"] == 100.25 and x["risk"] == 2.0 and np.isnan(x["target"])
    r.next_level = 102.5
    x = T.one_trade(r, tf, nan, nan, t, bid, ask, 0.0)
    assert x["target"] == 102.5 and x["exit"] == "target" and x["t_limit"] == 3600 * S


def test_an_m5_trade_is_held_60_m5_bars():
    # the measurer's missed bug ("M5 held 60 minutes, not 60 bars"): an M5 entry's time limit is 60 x 5 min = 300 min;
    # flat ticks every minute for 6 hours: out at the first tick at / after 300 minutes
    tf = fake_tf(np.full(100, 101.0), np.full(100, 100.0), np.full(100, 100.5), minutes=5)
    secs = np.arange(0, 6 * 3600, 60)
    t, bid = secs.astype(np.int64) * S, np.full(len(secs), 100.0)
    nan = np.full(100, np.nan)
    x = T.one_trade(SimpleNamespace(t_entry=0, side=1, stop=98.0, next_level=np.nan), tf, nan, nan, t, bid, bid + 0.2, 0.0)
    assert x["t_limit"] == 300 * MN and x["exit"] == "time" and x["exit_t"] == 300 * MN


# --- statistics and reasons -----------------------------------------------------------------------------------------


def test_weekdays():
    assert T.weekdays("P1") == 64 and T.weekdays("P2") == 66


def test_stats_by_hand():
    X = pd.DataFrame(dict(entry_t=[1, 2, 3, 4, 5], pnl=[2.0, -1.0, -1.0, 3.0, -2.0], R=[1.0, -0.5, -0.5, 1.5, -1.0],
                          exit=["target", "stop", "structure", "target", "stop"]))
    s = T.stats(X, "P1")
    sd = np.std([1.0, -0.5, -0.5, 1.5, -1.0], ddof=1)
    assert s["n"] == 5 and s["per_day"] == pytest.approx(5 / 64) and s["win"] == pytest.approx(0.4)
    assert s["R"] == pytest.approx(0.1) and s["R_lo"] == pytest.approx(0.1 - 1.96 * sd / np.sqrt(5))
    assert s["usd"] == pytest.approx(1.0) and s["dd"] == pytest.approx(2.0) and s["worst"] == -2.0
    assert (s["streak"], s["streak_usd"]) == (2, -2.0)  # -1, -1 (two) beats the last -2 (one)
    assert (s["x_stop"], s["x_target"], s["x_structure"], s["x_time"]) == (2, 2, 1, 0)
    # the time order decides the drawdown: sorted by entry_t
    s2 = T.stats(X.iloc[::-1], "P1")
    assert s2["dd"] == pytest.approx(2.0)
    assert T.stats(X.iloc[:0], "P1") == dict(n=0)
    # the drawdown starts from 0: a first trade of -3 is a drawdown of 3
    assert T.stats(pd.DataFrame(dict(entry_t=[1, 2], pnl=[-3.0, 1.0], R=[-1.0, 0.3], exit=["stop", "time"])))["dd"] == 3.0
    # a flat trade (0) breaks the losing streak
    s = T.stats(pd.DataFrame(dict(entry_t=[1, 2, 3], pnl=[-1.0, 0.0, -1.0], R=[-1.0, 0.0, -1.0], exit=["stop"] * 3)))
    assert (s["streak"], s["streak_usd"]) == (1, -1.0)
    # the streak in time order: rows given 2, 1, 3 -> the trades +2, -1, -1 -> two in a row
    s = T.stats(pd.DataFrame(dict(entry_t=[2, 1, 3], pnl=[-1.0, 2.0, -1.0], R=[-1.0, 1.0, -1.0], exit=["stop"] * 3)))
    assert (s["streak"], s["streak_usd"]) == (2, -2.0)


def test_reason_by_hand():
    # a buy in at 100.27, risk 2.27: the bid reaching 102.54 first -> ran later; 98.0 first -> wrong way
    t, bid, ask = ticks([(0, 100.0), (10, 101.0), (20, 102.6), (30, 97.0)])
    x = dict(entry_t=0, t_limit=3600 * S, side=1, entry=100.27, risk=2.27)
    assert T.reason(t, bid, ask, x) == "ran later"
    t, bid, ask = ticks([(0, 100.0), (10, 97.9), (20, 103.0)])
    assert T.reason(t, bid, ask, x) == "wrong way"
    t, bid, ask = ticks([(0, 100.0), (10, 101.0), (20, 99.0)])
    assert T.reason(t, bid, ask, x) == "no run"
    # exactly one risk our way (binary prices: in 100.25, risk 2.0, the bid 102.25) is "ran later"
    t2, b2 = np.array([0, 10 * S], np.int64), np.array([100.0, 102.25])
    assert T.reason(t2, b2, b2 + 0.25, dict(entry_t=0, t_limit=3600 * S, side=1, entry=100.25, risk=2.0)) == "ran later"
    # only within the time limit
    t, bid, ask = ticks([(0, 100.0), (10, 101.0), (40, 103.0)])
    assert T.reason(t, bid, ask, dict(x, t_limit=30 * S)) == "ran later"  # the first tick at / after the limit counts
    assert T.reason(t, bid, ask, dict(x, t_limit=9 * S)) == "no run"
    # a sell read on the ask: in 99.93, risk 2: the ask 97.7 (bid 97.5) -> ran later
    t, bid, ask = ticks([(0, 100.0), (10, 97.5)])
    assert T.reason(t, bid, ask, dict(entry_t=0, t_limit=3600 * S, side=-1, entry=99.93, risk=2.0)) == "ran later"
    # the bid 97.8 is 2.13 our way but the ask 98.0 only 1.93: a sell closes on the ask - no run
    t, bid, ask = ticks([(0, 100.0), (10, 97.8)])
    assert T.reason(t, bid, ask, dict(entry_t=0, t_limit=3600 * S, side=-1, entry=99.93, risk=2.0)) == "no run"


def test_ticks_never_load_the_exam():
    tk = T.Ticks()
    t, bid, ask = tk.span(pd.Timestamp("2026-04-17 12:00", tz="UTC").value)
    import sweep_detector as sd

    t0, _, _ = sd.learning_ticks(pd.Timestamp("2026-04-17", tz="UTC"))
    assert len(t) == len(t0) and t.max() < T.EXAM_START.value  # 2026-04-18 (the exam) is not loaded
