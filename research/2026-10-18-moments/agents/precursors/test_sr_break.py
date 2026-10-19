"""sr_break by hand: the level + volume side, what came after, the reason, the day's trades.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_sr_break.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sr_break import after, edges, reason, side, take  # noqa: E402

S = 10**9
E = dict(m15_lo=0.3, m15_hi=0.88, pdl_lo=4.0, pdh_hi=0.9, v1=1.33, v3=1.30)


def frame(**cols):
    base = dict(m15_pos=0.5, to_pdl=10.0, to_pdh=-10.0, break60=0, vol1=1.0, vol3=1.0)
    n = max(len(v) for v in cols.values())
    return pd.DataFrame({k: cols.get(k, [v] * n) for k, v in base.items()})


def test_support_with_the_volume_sells_resistance_buys():
    X = frame(m15_pos=[0.2, 0.95, 0.5, 0.5, 0.2], vol1=[1.5, 1.5, 1.5, 1.0, 1.0], vol3=[1.0, 1.0, 1.0, 1.0, 1.31])
    # 0: the M15 low + vol1 -> sell; 1: the M15 top + vol1 -> buy; 2: mid-price -> none; 3: no volume -> none;
    # 4: the M15 low + vol3 (vol1 quiet) -> sell
    assert side(X, E).tolist() == [-1, 1, 0, 0, -1]


def test_each_support_and_each_resistance_counts_and_both_cancel():
    X = frame(to_pdl=[3.0, 10.0, 10.0, 10.0, 3.0], to_pdh=[-10.0, 1.0, -10.0, -10.0, 1.0],
              break60=[0, 0, -1, 1, 0], vol1=[2.0] * 5)
    # near the previous day's low -> sell; above the previous day's high -> buy; below the 60-minute low -> sell;
    # above the 60-minute high -> buy; near the day's low AND above its high (a narrow day) -> none
    assert side(X, E).tolist() == [-1, 1, -1, 1, 0]


def test_the_edges_are_on_the_edge():
    X = frame(m15_pos=list(np.linspace(0, 1, 11)), vol1=list(np.arange(11.0)), to_pdl=list(np.linspace(5, 15, 11)),
              to_pdh=list(np.linspace(-15, -5, 11)))
    e = edges(X.assign(vol3=X.vol1))
    assert e["m15_lo"] == pytest.approx(0.2) and e["m15_hi"] == pytest.approx(0.8) and e["v1"] == pytest.approx(8.0)
    assert e["pdl_lo"] == pytest.approx(7.0) and e["pdh_hi"] == pytest.approx(-7.0)
    # row 2: at support (0.2, to_pdl 7) but the volume 2 < 8: none; rows 8, 9: at resistance with the volume: buy
    assert side(X.assign(vol3=X.vol1), e)[[2, 8, 9]].tolist() == [0, 1, 1]


def ticks(rows, spread=0.3):
    t, b = zip(*rows)
    b = np.array(b, float)
    return np.array(t, np.int64) * S, b, b + spread


def test_after_wrong_way_ran_later_no_run():
    t, bid, ask = ticks([(0, 100.0), (60, 95.0), (120, 89.9), (300, 120.0)])
    assert after(t, bid, ask, 0, 100.0, 1) == "wrong way"  # 89.9 - 100 = -10.1 first
    t, bid, ask = ticks([(0, 100.0), (60, 95.0), (120, 110.1), (300, 80.0)])
    assert after(t, bid, ask, 0, 100.0, 1) == "ran later"
    t, bid, ask = ticks([(0, 100.0), (60, 95.0), (3700, 80.0)])
    assert after(t, bid, ask, 0, 100.0, 1) == "no run"  # the -20 comes after 60 minutes


def test_after_a_sell_on_the_ask():
    # a sell at 100: the bid 90.1 is +9.9, but the ask 90.4 is +9.6 - not 10; then the ask 89.95 (bid 89.65) is +10.05
    t, bid, ask = ticks([(0, 100.0), (60, 90.1), (120, 89.65)])
    assert after(t, bid, ask, 0, 100.0, -1) == "ran later"
    t, bid, ask = ticks([(0, 100.0), (60, 89.9)])
    assert after(t, bid, ask, 0, 100.0, -1) == "no run"  # the bid 89.9 would be +10.1, the ask 90.2 is +9.8


def test_reason():
    assert reason("wrong way", 1, -1) == "wrong way / M15 against"  # a sell while M15 rises
    assert reason("no run", -1, -1) == "no run / M15 with"
    assert reason("ran later", 0, 1) == "ran later / M15 none"


def day_frame(minutes, sides):
    return pd.DataFrame(dict(t=[pd.Timestamp("2026-01-05", tz="UTC") + pd.Timedelta(minutes=m) for m in minutes],
                             part="P1", m15_struct=0)), np.array(sides)


def test_take_enters_at_the_next_bar_one_at_a_time_three_a_day():
    day0 = pd.Timestamp("2026-01-05", tz="UTC").value
    # the price flat at 100 all day, a tick every 30 s: every trade runs to the time limit (30 minutes)
    secs = np.arange(0, 86400, 30)
    t, bid, ask = day0 + secs.astype(np.int64) * S, np.full(len(secs), 100.0), np.full(len(secs), 100.3)
    D, sd = day_frame([10, 20, 50, 100, 200, 300], [-1, -1, 1, 0, -1, 1])
    rows = take(t, bid, ask, D, sd, day0 + 86400 * S, 5.0, None, None)
    # 10 -> in at 11:00, out ~41:00; 20 busy; 50 -> in 51; 100 none; 200 -> in 201; 300: the fourth - the cap
    assert [(r["t0"] - day0) // (60 * S) for r in rows] == [11, 51, 201]
    assert [r["side"] for r in rows] == [-1, 1, -1]
    assert rows[0]["entry"] == pytest.approx(100.0 - 0.07) and rows[1]["entry"] == pytest.approx(100.3 + 0.07)
    assert all(r["exit"] == "time" for r in rows)


def test_take_skips_the_last_half_hour():
    day0 = pd.Timestamp("2026-01-05", tz="UTC").value
    secs = np.arange(0, 86400, 30)
    t, bid, ask = day0 + secs.astype(np.int64) * S, np.full(len(secs), 100.0), np.full(len(secs), 100.3)
    D, sd = day_frame([23 * 60 + 28, 23 * 60 + 29, 23 * 60 + 40], [1, 1, 1])
    rows = take(t, bid, ask, D, sd, day0 + 86400 * S, 5.0, None, None)
    # 23:28 -> in at 23:29 (< 23:30); 23:29 -> 23:30 is busy anyway; 23:40 -> 23:41: inside the last 30 minutes
    assert [(r["t0"] - day0) // (60 * S) for r in rows] == [23 * 60 + 29]
    D, sd = day_frame([23 * 60 + 40], [1])
    assert take(t, bid, ask, D, sd, day0 + 86400 * S, 5.0, None, None) == []  # alone, still not taken
