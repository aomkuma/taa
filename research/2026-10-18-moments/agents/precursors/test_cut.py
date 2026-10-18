"""cut.keep and cut.take_sessions by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_cut.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cut import keep, take_sessions  # noqa: E402


def test_keep_takes_out_the_three_buckets():
    D = pd.DataFrame({"H1_struct": [1, -1, 0, 1, 1], "hour_utc": [3, 3, 16, 17, 9],
                      "kind": ["double_turn", "double_turn", "pierce_reversal", "double_neck", "touch_H1"]})
    # row 1 against the H1 structure, row 3 in the late session (17 UTC), row 4 a touch
    assert keep(D).tolist() == [True, False, True, False, False]


def test_one_position_and_one_trade_a_session():
    t = pd.to_datetime(["2026-05-04 01:00", "2026-05-04 01:00", "2026-05-04 02:00", "2026-05-04 06:00", "2026-05-04 07:30",
                        "2026-05-04 08:00", "2026-05-05 01:00"], utc=True)
    S = pd.DataFrame({"t": t, "hour_utc": t.hour, "p": [1, 4, 2, 3, 1, 2, 1], "j0": [10, 10, 70, 310, 400, 430, 1500],
                      "xj": [50, 60, 90, 320, 420, 460, 1510]})
    T = take_sessions(S)
    # 01:00: the H1 (p 4) first, busy to 60; 02:00 and 06:00 the same Asia session - skipped (free again, but used);
    # 07:30 London taken (busy to 420); 08:00 London again - skipped; the next day's Asia taken
    assert T.t.dt.strftime("%m-%d %H:%M").tolist() == ["05-04 01:00", "05-04 07:30", "05-05 01:00"] and T.p.tolist() == [4, 1, 1]


def test_a_busy_position_passes_the_session_on():
    t = pd.to_datetime(["2026-05-04 06:30", "2026-05-04 07:10", "2026-05-04 08:00"], utc=True)
    S = pd.DataFrame({"t": t, "hour_utc": t.hour, "p": [1, 1, 1], "j0": [100, 140, 200], "xj": [180, 150, 230]})
    # the Asia trade runs into London (busy to 180): the 07:10 London candidate is skipped, London's 08:00 taken
    assert take_sessions(S).t.dt.strftime("%H:%M").tolist() == ["06:30", "08:00"]


def test_the_exit_bar_is_still_busy():
    t = pd.to_datetime(["2026-05-04 06:30", "2026-05-04 07:10", "2026-05-04 07:20"], utc=True)
    S = pd.DataFrame({"t": t, "hour_utc": t.hour, "p": [1, 1, 1], "j0": [100, 180, 190], "xj": [180, 200, 220]})
    # the London candidate entering at bar 180 - the Asia trade's exit bar - waits; the next one (190) is taken
    assert take_sessions(S).j0.tolist() == [100, 190]
