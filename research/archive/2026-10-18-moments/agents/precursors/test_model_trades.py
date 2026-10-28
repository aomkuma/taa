"""model_trades.trade_1atr and model_trades.take by hand, and a second count of the trades on random markets.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_model_trades.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_trades import take, trade_1atr  # noqa: E402

NS_MIN = 60 * 10**9


def market(o, h, lo, c, sp=0.3, ny=False):
    n = len(o)
    return dict(o=np.array(o, float), h=np.array(h, float), lo=np.array(lo, float), c=np.array(c, float),
                sp=np.full(n, sp), ot_ns=np.arange(n, dtype=np.int64) * NS_MIN, ny=np.full(n, ny))


def test_a_buy_reaches_its_target():
    # entry at bar 1's open 100 + spread 0.3 + slippage 0.07 = 100.37; ATR 2: target 102.37, stop 98.37
    mk = market([99, 100, 101, 102], [99.5, 101.0, 102.5, 103], [98.5, 99.5, 100.0, 101], [99.2, 100.5, 102, 102.5])
    x = trade_1atr(mk, 1, 1, 2.0)
    assert x["exit"] == "win" and x["xj"] == 2 and x["pnl"] == pytest.approx(2.0) and x["R"] == pytest.approx(2.0 / 2.15)


def test_a_sell_is_stopped_on_the_ask_with_the_new_york_slippage():
    # a sell fills at the bid 100 - 0.07 = 99.93; stop 101.93 on the ask: bar 2's high 101.7 + 0.3 = 102.0 reaches it
    mk = market([99, 100, 100.5, 101], [99.5, 101.5, 101.7, 102], [98.5, 99.5, 100.0, 100.5], [99.2, 100.5, 101, 101.5], ny=True)
    x = trade_1atr(mk, 1, -1, 2.0)
    assert x["exit"] == "stop" and x["xj"] == 2 and x["ss"] == 0.20
    assert x["pnl"] == pytest.approx(-(101.93 + 0.20 - 99.93)) and x["R"] == pytest.approx(-1.0)


def test_the_stop_comes_first_when_one_bar_reaches_both():
    mk = market([100, 100, 100], [100.2, 103.0, 100.2], [99.8, 97.0, 99.8], [100, 100, 100])
    x = trade_1atr(mk, 1, 1, 2.0)
    assert x["exit"] == "stop" and x["pnl"] == pytest.approx(98.37 - 0.15 - 100.37)


def test_out_after_240_minutes_at_the_last_close():
    n = 300
    c = 100 + 0.001 * np.arange(n)
    mk = market(c, c + 0.05, c - 0.05, c)
    x = trade_1atr(mk, 10, 1, 2.0)
    # bars 10 .. 249 open before 10 + 240 minutes: out at bar 249's close less the slippage
    assert x["exit"] == "time" and x["xj"] == 249 and x["pnl"] == pytest.approx(c[249] - 0.07 - (c[10] + 0.37))


def test_take_one_at_a_time_highest_chance_first():
    t = pd.to_datetime(["2026-05-04 08:00", "2026-05-04 08:00", "2026-05-04 08:10", "2026-05-04 09:00", "2026-05-04 09:05"], utc=True)
    S = pd.DataFrame({"t": t, "p": [0.55, 0.60, 0.70, 0.51, 0.52], "side": [1, -1, 1, 1, -1],
                      "j0": [100, 100, 110, 160, 165], "xj": [130, 140, 150, 170, 180]})
    T = take(S, 0.52)
    # 08:00: the 0.60 sell first (busy to 140); the 0.55 buy at the same bar and the 08:10 buy (110 <= 140) skipped;
    # the 0.51 is below the threshold; 09:05 enters at 165 > 140
    assert T.p.tolist() == [0.60, 0.52] and T.side.tolist() == [-1, -1]


def reference(o, h, lo, c, sp, j0, side, atr, ss, hold):
    """A plain re-statement of the trade, written apart from lvl2.manage: per bar the stop (a buy's on the bid low, a
    sell's on the ask high) before the target, then out at the last close before the time is up."""
    e = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
    for j in range(j0, min(j0 + hold, len(o))):
        worst = lo[j] if side > 0 else h[j] + sp[j]
        best = h[j] if side > 0 else lo[j] + sp[j]
        if (side > 0 and worst <= e - atr) or (side < 0 and worst >= e + atr):
            return "stop", -(atr + ss), j
        if (best - e) * side >= atr:
            return "win", atr, j
    x = min(j0 + hold, len(o)) - 1
    px = c[x] - 0.07 if side > 0 else c[x] + sp[x] + 0.07
    return "time", (px - e) * side, x


def test_a_second_count_on_random_markets():
    rng = np.random.default_rng(7)
    n = 5000
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    o = np.r_[c[0], c[:-1]]
    h, lo = np.maximum(o, c) + rng.random(n) * 0.3, np.minimum(o, c) - rng.random(n) * 0.3
    sp = 0.2 + rng.random(n) * 0.2
    mk = dict(o=o, h=h, lo=lo, c=c, sp=sp, ot_ns=np.arange(n, dtype=np.int64) * NS_MIN, ny=rng.random(n) < 0.3)
    kinds = set()
    for j0 in range(5, n - 300, 37):
        for side in (1, -1):
            atr = 1.0 + rng.random() * 3
            x = trade_1atr(mk, j0, side, atr)
            ex, pnl, xj = reference(o, h, lo, c, sp, j0, side, atr, x["ss"], 240)
            assert (x["exit"], x["xj"]) == (ex, xj) and x["pnl"] == pytest.approx(pnl)
            kinds.add(ex)
    assert kinds == {"win", "stop", "time"}
