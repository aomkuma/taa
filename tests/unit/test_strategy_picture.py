"""Hand-worked tests for app/strategy/picture.py - pools, sweeps, squeeze (TAA-1802)."""

from __future__ import annotations

import numpy as np

from app.strategy import picture as pc


def _a(*x: float) -> np.ndarray:
    return np.array(x, dtype=float)


def test_clusters_group_by_price_and_keep_pairs():
    pts = [(1, 100.0), (5, 100.3), (9, 102.0), (12, 99.9)]
    # sorted by price: 99.9, 100.0, 100.3 within 0.35 of the running mean; 102.0 alone (dropped)
    assert pc.clusters(pts, 0.35) == [[(12, 99.9), (1, 100.0), (5, 100.3)]]


def _pool_bars():
    """Equal bottoms 100.0 (bar 3) and 100.05 (bar 7), price over them, bar 10 sweeps to 99.0 and closes back
    at 100.6 from a close of 102.5 before it; volume 3 x on the sweep."""
    lo = _a(103, 102, 101, 100.0, 101, 102, 101, 100.05, 101, 101.5, 99.0, 100.5, 101)
    h, c = lo + 1.5, lo + 1.0
    c[10] = 100.6
    v = np.full(len(lo), 100.0)
    v[10] = 300.0
    return h, lo, c, v


def test_pools_find_the_equal_bottoms_and_their_edge():
    h, lo, c, _ = _pool_bars()
    p = pc.pools(h, lo, c, atr=1.0)
    assert [(x["name"], x["level"], x["touches"]) for x in p] == [
        ("bottoms", 100.0, [(3, 100.0), (7, 100.05)])
    ]
    assert p[0]["mean"] == np.mean([100.0, 100.05])


def test_sweeps_of_the_pool():
    h, lo, c, v = _pool_bars()
    s = pc.sweeps(pc.pools(h, lo, c, 1.0)[0], h, lo, c, v, 1.0)
    assert len(s) == 1
    assert (s[0]["i"], s[0]["extreme"], s[0]["close"], s[0]["after"]) == (10, 99.0, 100.6, 2)
    assert s[0]["volume"] == 300.0 / v.mean()
    # bars 11 and 12: lows 100.5 / 101 and highs 102 / 102.5 rise -> 2 up, 0 down
    assert (s[0]["up"], s[0]["down"]) == (2, 0)


def test_no_sweep_when_it_closes_under_or_does_not_reach_0_1_atr():
    h, lo, c, v = _pool_bars()
    c[10] = 99.5
    assert pc.sweeps(pc.pools(h, lo, c, 1.0)[0], h, lo, c, v, 1.0) == []
    h, lo, c, v = _pool_bars()
    lo[10] = 99.95  # only 0.05 under the edge 100.0 (0.1 ATR needed)
    assert pc.sweeps(pc.pools(h, lo, c, 1.0)[0], h, lo, c, v, 1.0) == []


def test_pools_far_from_price_or_old_are_dropped():
    h, lo, c, _ = _pool_bars()
    c[-1] = 104.0  # the floor 100.0 is 4 ATR away (2.5 allowed)
    assert pc.pools(h, lo, c, 1.0) == []


def test_squeeze_range():
    h = _a(*([10.0] * 20))
    lo = _a(*([9.0] * 20))
    h[-1] = 11.5  # the last 12 bars span 9.0 .. 11.5 = 2.5
    assert pc.squeeze_range(h, lo, atr=1.0) == 2.5
    assert pc.squeeze_range(h, lo, atr=1.0, n=1) == 11.5 - 9.0


def test_a_sweep_on_the_last_bar_needs_0_1_atr_depth():
    # the last bar is never a bar low itself, so it cannot join the pool: 0.05 under the edge is not a sweep
    h, lo, c, v = _pool_bars()
    lo[-1], c[-1] = 99.95, 100.6
    assert pc.sweeps(pc.pools(h, lo, c, 1.0)[0], h, lo, c, v, 1.0)[-1]["i"] == 10  # only the bar-10 sweep
    lo[-1] = 99.85
    assert pc.sweeps(pc.pools(h, lo, c, 1.0)[0], h, lo, c, v, 1.0)[-1]["i"] == 12


def test_a_sweep_must_come_from_inside_the_pool():
    # the close before the last bar is already under the edge 100.0: the last bar's dip and close back is no sweep
    h, lo, c, v = _pool_bars()
    c[-2], lo[-2] = 99.8, 99.6
    lo[-1], c[-1] = 99.0, 100.6
    got = pc.sweeps(pc.pools(h, lo, c, 1.0)[0], h, lo, c, v, 1.0)
    assert [s["i"] for s in got] == [10]


def test_the_structure_after_a_sweep_needs_higher_lows_and_highs():
    h, lo, c, v = _pool_bars()
    lo[12] = 100.0  # bar 12 makes a higher high (102.5) but a lower low: neither up nor down
    s = pc.sweeps(pc.pools(h, lo, c, 1.0)[0], h, lo, c, v, 1.0)[0]
    assert (s["up"], s["down"]) == (1, 0)
