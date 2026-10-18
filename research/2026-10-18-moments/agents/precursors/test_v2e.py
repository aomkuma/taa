"""v2e.py by hand: a limit order's fill, the turn entry, and a limit trade whose fill bar also touched the target.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_v2e.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2e import NS_MIN, limit_fill, stop_fill, trades_for, turn_entry  # noqa: E402

SP = 0.2


def bars(rows, spreads=None):
    o, h, lo, c = (np.array([r[k] for r in rows], float) for k in range(4))
    sp = np.full(len(rows), SP) if spreads is None else np.array(spreads, float)
    return o, h, lo, c, sp, np.arange(len(rows)) * NS_MIN


def test_limit_fill_by_hand():
    o, h, lo, c, sp, t = bars([(100.0, 100.5, 99.5, 100.0),  # the ask low 99.7
                               (99.6, 99.9, 98.9, 99.2),  # the ask low 99.1: not 99.0 yet
                               (99.0, 99.4, 98.7, 99.3),  # the ask low 98.9: a buy limit at 99.0 fills at 99.0
                               (100.2, 101.0, 100.1, 100.9)])
    assert limit_fill(o, h, lo, sp, t, 0, 1, 99.0, 10 * NS_MIN) == (2, 99.0)
    assert limit_fill(o, h, lo, sp, t, 1, 1, 99.85, 10 * NS_MIN) == (1, 99.8)  # bar 1 opens with the ask (99.8) below it
    j, px = limit_fill(o, h, lo, sp, t, 0, 1, 99.0, 2 * NS_MIN)  # only bars 0 and 1 open before t_last
    assert j == -1 and math.isnan(px)
    assert limit_fill(o, h, lo, sp, t, 0, -1, 100.8, 10 * NS_MIN) == (3, 100.8)  # a sell limit: the bid high reaches it
    assert limit_fill(o, h, lo, sp, t, 3, -1, 100.15, 10 * NS_MIN) == (3, 100.2)  # bar 3 opens above it: its open


def test_turn_entry_buy_by_hand():
    o, h, lo, c, sp, t = bars([(100.0, 100.4, 99.6, 99.8),  # j0: the extreme so far (99.6)
                               (99.8, 99.9, 99.0, 99.2),  # a new low 99.0: wait for a close above 99.9
                               (99.2, 99.95, 99.3, 99.8),  # 99.8: not above 99.9
                               (99.8, 100.1, 99.5, 100.0),  # 100.0 > 99.9: the signal
                               (100.1, 100.6, 100.0, 100.5)])
    j, entry, sl = turn_entry(o, h, lo, c, sp, t, 0, 1, 10 * NS_MIN, 5.0, 0.07)
    assert j == 4 and math.isclose(entry, 100.1 + SP + 0.07)  # the next open, at the ask, + slip
    assert math.isclose(sl, entry - (99.0 - 0.3))  # beyond the extreme by 0.3
    assert turn_entry(o, h, lo, c, sp, t, 0, 1, 10 * NS_MIN, 1.5, 0.07)[0] == -1  # the stop (1.67) over the cap
    assert turn_entry(o, h, lo, c, sp, t, 0, 1, 3 * NS_MIN, 5.0, 0.07)[0] == -1  # the signal bar opens at t_last


def test_turn_entry_outside_bar_is_a_new_extreme():
    # bar 1 makes a new low (99.4) and closes (100.5) above the old extreme bar's high (100.4): a new extreme, not a
    # signal; bar 2 closes 100.7 above bar 1's high (100.6): the signal, entering at bar 3's open
    o, h, lo, c, sp, t = bars([(100.0, 100.4, 99.6, 99.8), (99.8, 100.6, 99.4, 100.5), (100.5, 100.8, 100.0, 100.7),
                               (100.7, 100.9, 100.5, 100.8)])
    j, entry, sl = turn_entry(o, h, lo, c, sp, t, 0, 1, 10 * NS_MIN, 5.0, 0.07)
    assert j == 3 and math.isclose(entry, 100.7 + SP + 0.07)
    assert math.isclose(sl, entry - (99.4 - 0.3))


def test_turn_entry_sell_by_hand():
    o, h, lo, c, sp, t = bars([(100.0, 100.4, 99.6, 100.2),  # the ask high 100.6
                               (100.2, 101.0, 100.3, 100.9),  # the ask high 101.2: a new extreme; its low 100.3
                               (100.9, 100.8, 100.35, 100.4),  # a wide spread (0.6): the ask high 101.4, a new extreme
                               (100.4, 100.5, 100.0, 100.1),  # 100.1 < bar 2's low 100.35: the signal
                               (100.0, 100.2, 99.5, 99.6)], spreads=[0.2, 0.2, 0.6, 0.2, 0.2])
    j, entry, sl = turn_entry(o, h, lo, c, sp, t, 0, -1, 10 * NS_MIN, 5.0, 0.07)
    assert j == 4 and math.isclose(entry, 100.0 - 0.07)
    assert math.isclose(sl, (100.8 + 0.6 + 0.3) - entry)  # beyond bar 2's ask high


def test_limit_trade_target_not_on_its_fill_bar():
    idx = pd.date_range("2026-07-15 08:00", periods=8, freq="min", tz="UTC")
    rows = [(4100.0, 4101.0, 4099.0, 4100.0),  # the snap's price: the close before j0
            (4100.0, 4100.5, 4098.0, 4099.0),  # j0: the ask low 4098.2, not 4097
            (4098.0, 4108.0, 4096.5, 4100.0),  # fills the buy limit at 4097; its high 4108 would be the target (4107)
            (4100.0, 4106.0, 4095.0, 4104.0),  # neither the stop (4092) nor the target
            (4104.0, 4107.5, 4103.0, 4107.0),  # the target
            (4107.0, 4108.0, 4106.0, 4107.0), (4107.0, 4108.0, 4106.0, 4107.0), (4107.0, 4108.0, 4106.0, 4107.0)]
    o, h, lo, c = (np.array([r[k] for r in rows]) for k in range(4))
    mk = dict(o=o, h=h, lo=lo, c=c, sp=np.full(8, SP), ot_ns=idx.as_unit("ns").asi8, ny=np.zeros(8, bool), index=idx)
    lv = pd.DataFrame({"row": [0], "L3_n": [6], "L3_lean": [0.5], "L6_n": [6], "L6_lean": [0.5],
                       "s_ns": [idx.as_unit("ns").asi8[1]], "j0": [1]})
    D = trades_for(("limit", 3, 5, 15, 10), lv, ("L3", 5, 0.2), mk)
    assert len(D) == 1
    r = D.iloc[0]
    assert (r.je, r.entry, r.sl, r.tp) == (2, 4097.0, 5.0, 10.0)
    assert r.exit == "win" and r.xj == 4 and r.pnl == 10.0  # not on bar 2
    # the same with the fill bar's low through the stop (4092): stopped on the fill bar
    lo2 = lo.copy()
    lo2[2] = 4091.0
    D = trades_for(("limit", 3, 5, 15, 10), lv, ("L3", 5, 0.2), dict(mk, lo=lo2))
    assert D.iloc[0].exit == "stop" and D.iloc[0].xj == 2 and math.isclose(D.iloc[0].pnl, -5.15)


def test_stop_fill_by_hand():
    o, h, lo, c, sp, t = bars([(100.0, 100.5, 99.8, 100.4),  # the ask high 100.7
                               (100.6, 101.2, 100.5, 101.0),  # the ask high 101.4: a buy stop at 101.0 fills
                               (99.0, 99.2, 98.6, 98.8)])  # opens at 99.0 (bid)
    j, px = stop_fill(o, h, lo, sp, t, 0, 1, 101.0, 10 * NS_MIN, 0.07)
    assert j == 1 and math.isclose(px, 101.07)  # the level + slip
    j, px = stop_fill(o, h, lo, sp, t, 1, 1, 100.7, 10 * NS_MIN, 0.07)
    assert j == 1 and math.isclose(px, 100.87)  # bar 1 opens with the ask (100.8) above it: the open + slip
    assert stop_fill(o, h, lo, sp, t, 0, 1, 101.0, 1 * NS_MIN, 0.07)[0] == -1  # only bar 0 before t_last
    j, px = stop_fill(o, h, lo, sp, t, 0, 1, 100.6, 10 * NS_MIN, 0.07)  # bar 0: the bid high 100.5, the ask high 100.7
    assert j == 0 and math.isclose(px, 100.67)  # a buy stop fills on the ask
    j, px = stop_fill(o, h, lo, sp, t, 0, -1, 99.7, 10 * NS_MIN, 0.07)  # a sell stop: the bid low reaches it on bar 2
    assert j == 2 and math.isclose(px, 99.0 - 0.07)  # bar 2 opens below it: its open - slip
    j, px = stop_fill(o, h, lo, sp, t, 0, -1, 99.85, 10 * NS_MIN, 0.07)  # bar 0's low 99.8 reaches 99.85
    assert j == 0 and math.isclose(px, 99.85 - 0.07)


def test_stop_trade_by_hand():
    idx = pd.date_range("2026-07-15 08:00", periods=8, freq="min", tz="UTC")
    rows = [(4100.0, 4100.5, 4099.5, 4100.0),  # the snap's price 4100: a buy stop at 4101 (D 1)
            (4100.0, 4100.6, 4097.0, 4098.0),  # j0: the ask high 4100.8 - not yet (a dip)
            (4098.6, 4101.5, 4098.5, 4101.2),  # the ask high 4101.7: fills at 4101.07; the stop 4098.07 not touched
            (4101.2, 4104.0, 4100.0, 4103.5),
            (4103.5, 4106.5, 4103.0, 4106.0),  # the 5 U target (4101.07 + 5) = 4106.07 reached
            (4106.0, 4107.0, 4105.0, 4106.5), (4106.5, 4107.0, 4105.0, 4106.5), (4106.5, 4107.0, 4105.0, 4106.5)]
    o, h, lo, c = (np.array([r[k] for r in rows]) for k in range(4))
    mk = dict(o=o, h=h, lo=lo, c=c, sp=np.full(8, SP), ot_ns=idx.as_unit("ns").asi8, ny=np.zeros(8, bool), index=idx)
    lv = pd.DataFrame({"row": [0], "L3_n": [6], "L3_lean": [0.5], "L6_n": [6], "L6_lean": [0.5],
                       "s_ns": [idx.as_unit("ns").asi8[1]], "j0": [1]})
    r = trades_for(("stop", 1, 3, 15, 5), lv, ("L3", 5, 0.2), mk).iloc[0]
    assert r.je == 2 and math.isclose(r.entry, 4101.07) and r.sl == 3.0 and r.tp == 5.0
    assert r.exit == "win" and r.xj == 4
    # the fill bar's low through the stop (4098.07): stopped on the fill bar (the stop first)
    lo2 = lo.copy()
    lo2[2] = 4098.0
    r = trades_for(("stop", 1, 3, 15, 5), lv, ("L3", 5, 0.2), dict(mk, lo=lo2)).iloc[0]
    assert r.exit == "stop" and r.xj == 2 and math.isclose(r.pnl, -3.15)
