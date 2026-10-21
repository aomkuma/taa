"""Hand-worked tests of row 60 (lt60.py): the long-hold simulator, the trend, the bar availability, the guard."""

import numpy as np
import pandas as pd
import pytest

import lt60 as L

M = 60 * 10**9


def ticks(bids, spread=0.2, step=M):
    b = np.asarray(bids, float)
    return np.arange(len(b)) * step, b, b + spread


def test_buy_target_and_stop():
    t, bid, ask = ticks([100.0, 101.0, 112.0, 90.0])
    # buy at ask 100.2; d 10; target 1.5 R = 115.2 not reached; stop 90.2: tick 3 (bid 90) -> stop at that tick's price
    pnl, R, why, te = L.lsim(t, bid, ask, 0, 1, 10.0, 1.5, 10 * M)
    assert why == "stop" and pnl == pytest.approx(90.0 - 100.2) and R == pytest.approx(-1.02) and te == 3 * M
    # target 1 R = 110.2: tick 2 (bid 112) -> filled at the level
    pnl, R, why, _ = L.lsim(t, bid, ask, 0, 1, 10.0, 1.0, 10 * M)
    assert why == "target" and pnl == pytest.approx(10.0) and R == pytest.approx(1.0)


def test_sell_uses_ask_and_time_exit_is_the_last_tick_before_the_limit():
    t, bid, ask = ticks([100.0, 98.0, 99.0, 50.0])
    # sell at bid 100; no target; time limit 3 min -> the last tick before it is tick 2 (ask 99.2) -> +0.8
    pnl, R, why, te = L.lsim(t, bid, ask, 0, -1, 10.0, None, 3 * M)
    assert why == "time" and pnl == pytest.approx(0.8) and te == 2 * M


def test_no_gap_exit_and_gap_fill():
    t = np.array([0, M, 3 * 24 * 3600 * 10**9])  # a weekend gap between ticks 1 and 2
    bid = np.array([100.0, 99.0, 80.0])
    # buy at 100.2, d 10 -> the stop is first breached after the weekend, filled at the gapped price 80
    pnl, R, why, _ = L.lsim(t, bid, bid + 0.2, 0, 1, 10.0, None, 4 * 24 * 3600 * 10**9)
    assert why == "stop" and pnl == pytest.approx(80.0 - 100.2)


def test_refusals():
    t, bid, ask = ticks([100.0, 101.0])
    assert L.lsim(t, bid, ask, 10 * M, 1, 10.0, 1.0, 20 * M) is None  # no tick within 5 min
    assert L.lsim(t, bid, ask, 0, 1, 0.0, 1.0, 20 * M) is None  # d must be > 0
    assert L.lsim(t, bid, ask, 0, 1, 10.0, 1.0, 0) is None  # nothing after the fill before the limit


def test_d1_trend_and_avail():
    c = np.arange(30.0)
    assert L.d1_trend(c, 25) == 1 and L.d1_trend(c[::-1], 25) == -1 and L.d1_trend(c, 19) == 0
    o = np.array([0, 3600, 7200 + 3600]) * 10**9
    # bar 1's next bar opens 2 h later (a break) -> complete at its own open + 1 h, not later
    assert L.avail_of(o, 3600 * 10**9).tolist() == [3600 * 10**9, 7200 * 10**9, (7200 + 7200) * 10**9]


def test_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "FROZEN", tmp_path / "none.json")
    with pytest.raises(RuntimeError):
        L.period_of("test")
    assert L.ticks(pd.Timestamp("2023-10-01", tz="UTC"), L.LEARN[1]) is None
    assert L.window(pd.Timestamp("2023-10-01", tz="UTC").value, pd.Timestamp("2023-10-02", tz="UTC").value,
                    L.LEARN[1], {}) is None


def test_choose():
    T = pd.DataFrame({"cand": ["PDB"] * 3, "setting": ["target 1.5 R", "time only", "time only"], "atr": [5.0, 5.0, 20.0],
                      "R": [0.1, 0.2, -9.0]})
    assert L.choose(T)["PDB"] == "time only"  # the 20-ATR trade is not calm


def test_late_fill_refused():
    t = np.array([0, 10 * M, 11 * M])
    b = np.array([100.0, 100.0, 120.0])
    assert L.lsim(t, b, b + 0.2, M, 1, 10.0, 1.0, 20 * M) is None  # the first tick after t_in is 9 min late


def test_trend_is_exactly_n_bars_back():
    c = np.zeros(30)
    c[5], c[6], c[25] = 10.0, 0.0, 5.0
    assert L.d1_trend(c, 25, 20) == -1  # 5 - c[5] (10); 19 bars back would give +1


def test_ticks_refuse_the_end_day_itself(monkeypatch):
    calls = []
    monkeypatch.setattr(L, "TICKS", type("P", (), {"__truediv__": lambda s, f: calls.append(f) or s,
                                                     "exists": lambda s: False})())
    assert L.ticks(pd.Timestamp("2023-10-02", tz="UTC"), pd.Timestamp("2023-10-02", tz="UTC")) is None
    assert calls == []
