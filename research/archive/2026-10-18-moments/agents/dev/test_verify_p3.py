"""verify_p3 by hand: its metrics with the new exits, its re-derivation of a trade with a moving stop (break-even, the
trailing steps), a stale fill, a close exit and its own bar readings.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_verify_p3.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_p3 as V  # noqa: E402

S = 10**9
MN = 60 * S


def tk(rows):
    t, b = zip(*rows, strict=True)
    return pd.DataFrame(dict(t=[x * S for x in t], bid=list(b), ask=[x + 0.2 for x in b]))


def test_metrics_counts_the_new_exits():
    rows = [dict(entry_t=i, side=1, entry=100.0, stop=98.0, pnl=p, exit=e)
            for i, (p, e) in enumerate(((1.0, "trail"), (-2.0, "stop"), (0.5, "invalid")))]
    m = V.metrics(rows, "P1")
    assert (m["x_trail"], m["x_stop"], m["x_invalid"], m["x_structure"], m["n"]) == (1, 1, 1, 0, 3)
    assert m["R"] == pytest.approx((0.5 - 1.0 + 0.25) / 3)


def trail_trade(**kw):
    # in 100.27 (ask 100.2 + 0.07), the stop 98 (risk 2.27); BE at 20 s (bid 102.6); the steps 35 s -> 101.5
    base = dict(variant="Xb", tf="M1", side=1, t_entry=0, entry_t=0, entry=100.27, stop=98.0, exit="trail", exit_t=50 * S,
                exit_px=101.4, pnl=101.4 - 100.27, R=(101.4 - 100.27) / 2.27, target=np.nan, t_limit=3600 * S,
                t_struct=pd.NA, t_be=20 * S, trail_t=[35 * S], trail_v=[101.5], atr=1.0)
    base.update(kw)
    return base


TRAIL_TICKS = [(0, 100.0), (20, 102.6), (30, 101.2), (40, 103.0), (50, 101.4)]


def test_rederive_a_trailing_stop():
    T = tk(TRAIL_TICKS)
    assert V.rederive3(trail_trade(), T, None, None) == []
    assert V.rederive3(trail_trade(t_be=30 * S), T, None, None) == ["the break-even tick"]
    # a recorded exit later than where the moving stop was crossed
    T2 = tk([(0, 100.0), (20, 102.6), (30, 100.1), (50, 101.4)])
    assert "a tick past the stop level before the exit" in V.rederive3(trail_trade(), T2, None, None)
    # the name: a trail exit at the original stop's level is a 'stop'
    T3 = tk([(0, 100.0), (10, 101.0), (20, 97.9)])
    stop = dict(exit="stop", exit_t=20 * S, exit_px=97.9, pnl=97.9 - 100.27, R=(97.9 - 100.27) / 2.27, t_be=pd.NA)
    assert V.rederive3(trail_trade(**stop), T3, None, None) == []
    assert V.rederive3(trail_trade(**dict(stop, exit="trail")), T3, None, None) == ["the stop / trail tick, price or name"]
    # one risk our way only after the stop (103 at 30 s): no break-even tick belongs to the trade
    assert V.rederive3(trail_trade(**stop), tk([(0, 100.0), (10, 101.0), (20, 97.9), (30, 103.0)]), None, None) == []
    # a step BEFORE break-even (15 s, 101.3) does not count: the 101.2 at 30 s stays above the break-even stop
    early = trail_trade(trail_t=[15 * S, 35 * S], trail_v=[101.3, 101.5])
    assert V.rederive3(early, T, None, None) == []


def test_rederive_a_stale_fill_and_a_close_exit():
    T = tk([(61, 100.0), (120, 101.0)])
    tr = trail_trade(entry_t=61 * S, exit="time", exit_t=120 * S, exit_px=101.0, pnl=101.0 - 100.27,
                     R=(101.0 - 100.27) / 2.27, t_limit=100 * S, t_be=pd.NA)
    assert "a stale fill (no tick within 60 s of the decision)" in V.rederive3(tr, T, None, None)
    T = tk([(0, 100.0), (10, 100.5), (20, 101.0)])
    tr = trail_trade(variant="Xa", exit="invalid", exit_t=20 * S, exit_px=101.0, pnl=101.0 - 100.27,
                     R=(101.0 - 100.27) / 2.27, t_struct=15 * S, t_be=pd.NA, trail_t=None, trail_v=None)
    assert V.rederive3(tr, T, None, None) == []
    assert V.rederive3(dict(tr, t_struct=20 * S + 1), T, None, None) == ["the close exit's tick"]


class FakeBars:
    """Its own bars, by hand: M1 closes 103, 103, 99.5 (below the invalidation 100 at bar 2), troughs 99 from bar 1."""

    def __init__(self):
        t_open = np.arange(5, dtype=np.int64) * MN
        self.tf = {"M1": dict(t_open=t_open, avail=t_open + MN, c=np.array([103.0, 103.0, 99.5, 103.0, 103.0]),
                              lt=np.array([np.nan, 99.0, 99.0, 99.0, 99.0]), lp=np.full(5, np.nan))}

    first_close = V.Bars.first_close


def test_the_bar_readings():
    b = FakeBars()
    assert b.first_close("M1", 0, 5 * MN, lambda i: b.tf["M1"]["c"][i] < 100.0) == 3 * MN
    assert b.first_close("M1", 0, 3 * MN - 1, lambda i: b.tf["M1"]["c"][i] < 100.0) is None
    assert b.first_close("M1", 0, 3 * MN, lambda i: b.tf["M1"]["c"][i] < 100.0) == 3 * MN  # closing AT the limit counts
    assert b.first_close("M1", MN, 5 * MN, lambda i: i == 0) is None  # bar 0 opens before the entry
    T = tk([(0, 100.0), (10, 100.5), (180, 99.4), (200, 99.0)])
    tr = trail_trade(variant="Xa", invalid=100.0, exit="invalid", exit_t=180 * S, exit_px=99.4, pnl=99.4 - 100.27,
                     R=(99.4 - 100.27) / 2.27, t_struct=3 * MN, t_be=pd.NA, trail_t=None, trail_v=None, t_limit=5 * MN)
    assert V.rederive3(tr, T, b, 100.0) == []
    assert V.rederive3(tr, T, b, 100.5) == ["the invalidation price"]
    late = dict(tr, t_struct=4 * MN, exit_t=240 * S)  # a recorded close exit at 4 min where its own bars say 3 min
    assert V.rederive3(late, tk([(0, 100.0), (240, 99.4)]), b, 100.0) == ["the invalidation exit time"]
    # the trailing values: its own last troughs - 0.2 x ATR at each bar close from the entry to the limit
    tt = [MN, 2 * MN, 3 * MN, 4 * MN, 5 * MN]
    ok = trail_trade(t_limit=5 * MN, trail_t=tt, trail_v=[np.nan, 98.8, 98.8, 98.8, 98.8], exit_t=50 * S)
    assert "the trailing values" not in V.rederive3(ok, tk(TRAIL_TICKS), b, None)
    bad = dict(ok, trail_v=[np.nan, 98.8, 98.8, 98.9, 98.8])
    assert "the trailing values" in V.rederive3(bad, tk(TRAIL_TICKS), b, None)
