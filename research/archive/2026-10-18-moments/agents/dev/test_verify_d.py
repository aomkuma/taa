"""verify_d (the second computation of Task D) by hand: its metrics, its tick walk, its decision, its M1 trade, its
straddle, its events, its cell selection.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_verify_d.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_d as V  # noqa: E402

S = 10**9
MN = 60 * S
T0 = pd.Timestamp("2026-01-14 06:00", tz="UTC").value


def test_its_metrics():
    # pnl 2 (risk 2), -1, 0, -1, 3 (risk 1): R 1, -1, 0, -1, 3 -> mean 0.4; a zero is not a win (2 of 5); USD 3; the
    # running sum 2, 1, 1, 0, 3 -> max DD 2; the zero breaks the losing streak (1 loss, -1)
    rows = [dict(entry_t=k, pnl=p, risk=r) for k, (p, r) in enumerate([(2.0, 2.0), (-1.0, 1.0), (0.0, 1.0), (-1.0, 1.0), (3.0, 1.0)])]
    m = V.metrics(rows, "P1")
    assert (m["n"], m["win"], m["usd"], m["dd"], m["worst"], m["streak"], m["streak_usd"]) == (5, 0.4, 3.0, 2.0, -1.0, 1, -1.0)
    assert m["R"] == pytest.approx(0.4)
    half = 1.96 * math.sqrt(sum((x - 0.4) ** 2 for x in (1, -1, 0, -1, 3)) / 4 / 5)
    assert m["R_lo"] == pytest.approx(0.4 - half)


def test_its_walk():
    t = [T0 + k * MN for k in range(5)]
    bid = [100.0, 101.0, 98.0, 110.0, 111.0]
    ask = [b + 0.1 for b in bid]
    assert V.walk(t, bid, ask, 0, 1, 100.17, 98.5, 106.0, T0 + 60 * MN) == (98.0, "stop", t[2])  # a gap through: its bid
    assert V.walk(t, bid, ask, 0, 1, 100.17, 97.0, 106.0, T0 + 60 * MN) == (106.0, "target", t[3])
    assert V.walk(t, bid, ask, 0, 1, 100.17, 97.0, None, T0 + 3 * MN) == (110.0, "time", t[3])
    assert V.walk(t, bid, ask, 0, 1, 100.17, 98.5, None, T0 + 2 * MN) == (98.0, "stop", t[2])  # the stop and the time on one tick
    t2 = [T0, T0 + MN, T0 + 32 * MN]
    assert V.walk(t2, [100.0, 101.0, 90.0], [100.1, 101.1, 90.1], 0, 1, 100.17, 97.0, None, T0 + 60 * MN) == (101.0, "break", t2[1])
    assert V.walk(t, bid, ask, 0, -1, 99.93, 101.1, None, T0 + 60 * MN) == (101.1, "stop", t[1])  # a sell on the ask


def fake_data(c20: float = 101.6) -> V.Data:
    D = object.__new__(V.Data)
    n = 90
    D.t = np.array([T0 + k * MN for k in range(n)], np.int64)
    D.h, D.lo, D.c, D.o = np.full(n, 101.0), np.full(n, 99.0), np.full(n, 100.0), np.full(n, 100.0)
    D.h[7], D.lo[3], D.c[20] = 101.5, 98.5, c20
    D.spr = np.full(n, 0.1)
    D.h1_av, D.h1_atr = np.array([T0 - 60 * MN, T0]), np.array([5.0, 2.0])
    return D


def test_its_decision():
    d = V.decision(fake_data(), T0, 15)
    assert (d["status"], d["side"], d["stop"], d["t_dec"], d["i"]) == ("trade", 1, 98.5, T0 + 21 * MN, 20)
    D = fake_data()
    D.h1_atr = np.array([5.0, 1.9])  # the range 3.0 > 1.5 x 1.9
    assert V.decision(D, T0, 15)["status"] == "wide"
    D = fake_data(c20=101.5)  # at the high: no break
    assert V.decision(D, T0, 15)["status"] == "no break"
    D = fake_data()
    D.t = D.t + 6 * MN  # the first bar at 06:06
    assert V.decision(D, T0, 15)["status"] == "late open"


def test_its_m1_trade():
    D = fake_data()
    D.o[21], D.h[23] = 101.7, 108.61  # the fill 101.7 + 0.1 + 0.07 = 101.87; the stop 98.5 -> the target 108.61
    x = V.d1_m1(D, 20, 1, 98.5, 2.0, 60)
    assert x["entry"] == pytest.approx(101.87) and x["exit"] == "target" and x["R"] == pytest.approx(2.0) and x["exit_t"] == D.t[23]


def test_its_straddle():
    t = [T0 - 5 * S, T0 + 5 * S, T0 + 10 * S, T0 + 900 * S]
    bid = [4000.0, 4001.9, 4002.1, 4010.0]
    ask = [4000.4, 4002.3, 4002.5, 4010.4]
    x = V.straddle(t, bid, ask, T0, 2.0, 8.0, 15, 0.5)
    assert (x["side"], x["entry_t"], x["exit"]) == (1, T0 + 10 * S, "time") and x["entry"] == pytest.approx(4003.07)
    assert x["R"] == pytest.approx((4010.0 - 4003.07) / 8)
    assert V.straddle([T0 - 31 * S] + t[1:], bid, ask, T0, 2.0, 8.0, 15, 0.5) is None  # the reference too old


def test_its_events():
    ev = V.events()
    week = [pd.Timestamp(t, tz="UTC").strftime("%m-%d %H:%M") + " " + ny for t, ny in ev
            if pd.Timestamp("2026-03-06", tz="UTC") <= pd.Timestamp(t, tz="UTC") < pd.Timestamp("2026-03-10", tz="UTC")]
    assert week == ["03-06 13:30 08:30", "03-06 15:00 10:00", "03-09 12:30 08:30", "03-09 14:00 10:00"]  # EST, then EDT
    assert pd.Timestamp(ev[0][0], tz="UTC") >= pd.Timestamp("2025-10-18", tz="UTC") and ev[-1][0] < V.EXAM.value


def test_its_cell_selection():
    rows = [dict(src="ticks", L=15, k=2.0, X=60, traded=True, level_ahead=np.nan, adr20=70.0, entry_t=1),
            dict(src="ticks", L=15, k=2.0, X=60, traded=True, level_ahead=101.0, adr20=70.0, entry_t=2),
            dict(src="ticks", L=15, k=2.0, X=60, traded=True, level_ahead=np.nan, adr20=60.0, entry_t=3),
            dict(src="ticks", L=15, k=2.0, X=60, traded=np.nan, level_ahead=np.nan, adr20=70.0, entry_t=4),
            dict(src="ticks", L=15, k=2.0, X=60, traded=True, level_ahead=np.nan, adr20=64.0, entry_t=6),
            dict(src="m1", L=15, k=2.0, X=60, traded=True, level_ahead=np.nan, adr20=70.0, entry_t=5)]
    A = pd.DataFrame(rows)
    pick = lambda lab: [r["entry_t"] for r in V.select(A, None, lab)]  # noqa: E731
    assert pick("D1|D1|ticks") == [1, 2, 3, 6] and pick("D1|D1L|ticks") == [1, 3, 6]
    assert pick("D1|D1 + S|ticks") == [1, 2, 6] and pick("D1|D1L + S|ticks") == [1, 6] and pick("D1|D1|m1") == [5]  # 64 >= 63.3


def test_its_mid_and_gap():
    t = [T0, T0 + MN, T0 + 40 * MN]
    bid, ask = [100.0, 102.0, 90.0], [100.2, 102.2, 90.2]
    assert V.own_mid(t, bid, ask, T0 + MN) == pytest.approx(102.1) and math.isnan(V.own_mid(t, bid, ask, T0 - 1))
    assert V.own_gap(t, T0, T0 + 30 * MN) and not V.own_gap(t, T0, T0 + MN) and V.own_gap(t, T0, T0 + 41 * MN)
    ev = V.events(((9, 30),))
    assert all(pd.Timestamp(x, tz="UTC").tz_convert("America/New_York").strftime("%H:%M") == "09:30" for x, _ in ev)
