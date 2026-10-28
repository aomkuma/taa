"""rule_bt.rule_side by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_rule_bt.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rule_bt import rule_side  # noqa: E402


def test_rule_side_by_hand():
    rows = [  # H1 way, H1 structure, M5 last leg, M5 position, M1 last leg -> the side
        (1, 1, -1, 0.40, 1, 1),  # up trend, M5 pulled back, M1 turned up: buy
        (1, 1, -1, 0.60, 1, 1),  # the position exactly at the 60 % edge: still a buy
        (1, 1, -1, 0.61, 1, 0),  # M5's close too high in its range: none
        (1, 0, -1, 0.40, 1, 0),  # the way up but the structure mixed: none
        (0, 0, -1, 0.40, 1, 0),  # flat: none
        (1, 1, 1, 0.40, 1, 0),  # M5 not pulled back: none
        (1, 1, -1, 0.40, -1, 0),  # M1 not turned: none
        (-1, -1, 1, 0.40, -1, -1),  # down trend, M5 bounced, M1 turned down, close in the upper 60 % (>= 0.4): sell
        (-1, -1, 1, 0.39, -1, 0),  # the sell's close too low in M5's range: none
    ]
    P = pd.DataFrame(rows, columns=["H1_net_way", "H1_struct", "M5_leg_way", "M5_pos", "M1_leg_way", "want"])
    assert rule_side(P).tolist() == P.want.tolist()


def test_rule_side_with_h4_by_hand():
    rows = [(1, 1, 1, -1, 0.4, 1, 1),  # H4 up agrees with the H1 up trend: buy
            (0, 1, 1, -1, 0.4, 1, 0),  # H4 flat: none
            (-1, 1, 1, -1, 0.4, 1, 0),  # H4 down against the H1 up trend: none
            (-1, -1, -1, 1, 0.6, -1, -1)]  # both down: sell
    P = pd.DataFrame(rows, columns=["H4_net_way", "H1_net_way", "H1_struct", "M5_leg_way", "M5_pos", "M1_leg_way", "want"])
    assert rule_side(P, h4=True).tolist() == P.want.tolist()
    assert rule_side(P).tolist() == [1, 1, 1, -1]  # without the H4 screen every one fires
