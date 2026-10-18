"""Tests for LV3 (lvl3.py): the owner's legs, with answers worked out by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_lvl3.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lvl3  # noqa: E402
import plib  # noqa: E402


class TestLegs:
    def test_the_pause_starts_at_its_latest_extreme(self):
        assert list(lvl3.pause_legs(np.array([10.0, 12.0, 11.0, 9.0]), -1)) == [12.0, 11.0, 9.0]
        # a run through every earlier peak restarts the count
        assert list(lvl3.pause_legs(np.array([10.0, 12.0, 11.0, 13.0, 12.0]), -1)) == [13.0, 12.0]
        # equal highs: the latest one starts the pause
        assert list(lvl3.pause_legs(np.array([12.0, 11.0, 12.0, 10.0]), -1)) == [12.0, 10.0]
        assert list(lvl3.pause_legs(np.array([10.0, 8.0, 9.0, 7.0, 8.0]), 1)) == [7.0, 8.0]

    def test_the_trigger(self):
        legs = np.array([12.0, 11.0, 9.0])
        assert lvl3.pause_trigger(legs, 3, 12.5, 1.0, -1)  # 3 legs, newest lower, the high reached 11.5
        assert not lvl3.pause_trigger(legs, 4, 12.5, 1.0, -1)  # not enough legs
        assert not lvl3.pause_trigger(legs, 3, 14.0, 1.0, -1)  # the high never reached the level zone (13)
        assert not lvl3.pause_trigger(np.array([12.0, 12.0]), 2, 12.0, 1.0, -1)  # not lower
        assert not lvl3.pause_trigger(np.array([12.0]), 1, 12.0, 1.0, -1)  # one peak is not a pause
        assert lvl3.pause_trigger(np.array([7.0, 8.0, 7.5]), 3, 6.5, 1.0, 1)  # buys: troughs above the lowest
        assert not lvl3.pause_trigger(np.array([7.0, 8.0, 7.5]), 3, 5.0, 1.0, 1)  # the low never reached 6.0

    def test_legs_needed(self):
        assert lvl3.legs_needed(lvl3.Params(n=4), 9.0) == 4
        assert lvl3.legs_needed(lvl3.Params(n=0), 4.9) == 3
        assert lvl3.legs_needed(lvl3.Params(n=0), 5.0) == 5


@pytest.fixture(scope="module")
def mar9():
    import jlib  # noqa: PLC0415

    m = jlib.m1_frame("XAUUSD")
    m = m[(m.index >= pd.Timestamp("2026-01-20", tz="UTC")) & (m.index < pd.Timestamp("2026-03-10", tz="UTC"))]
    return lvl3.Market(m, m.spread.to_numpy(float) * 0.01 + 0.08)


def th(x: str) -> pd.Timestamp:
    return pd.Timestamp(f"2026-03-09 {x}", tz="Asia/Bangkok").tz_convert("UTC")


def test_the_owners_five_legs_on_march_9(mar9):
    """The owner's count on M1 (1.5 ATR swings): 5087.4, 5086.2, 5082.6, 5082.5, 5079.9 after the 08:04 low."""
    Z = mar9.m1zz[1.5]
    st = mar9.ot_ns[Z["b"]]
    sel = (st >= th("08:04").value) & (st < th("09:00").value) & (Z["t"] == 1)
    assert np.round(Z["p"][sel], 1).tolist() == [5087.4, 5086.2, 5082.6, 5082.5, 5079.9]
    assert np.round(lvl3.pause_legs(Z["p"][sel], -1), 1).tolist() == [5087.4, 5086.2, 5082.6, 5082.5, 5079.9]


def test_no_lv3_sell_after_the_run_through_the_peaks(mar9):
    """LV2 sold at 09:29 after the 09:14 run to 5095.3; with the legs rule that is the start of a new pause."""
    M = mar9
    dec = np.nonzero(plib.window_mask(M.ot).any(axis=1).to_numpy() & np.asarray(M.ot >= pd.Timestamp("2026-02-01", tz="UTC")))[0]
    S = lvl3.signals(M, dec, lvl3.Params(k=0.5, s=1.5, n=5))
    when = M.ot[S.t.to_numpy()]
    late = S[(when >= th("09:14")) & (when <= th("09:40"))]
    assert late.empty, late
    # every signal had at least 5 legs and its newest peak / trough below / above the extreme
    assert (S.legs >= 5).all()


def test_legs_count_from_the_minute_of_the_start_not_its_bar():
    """2026-10-18 (seen by eye): a buy's start was the M15 peak 4889.5 at 20:13 Thai inside the 20:00 bar, which also
    held the 4835 low at 20:04; that low must not be counted as a leg of the dip."""
    import jlib  # noqa: PLC0415

    m = jlib.m1_frame("XAUUSD")
    m = m[(m.index >= pd.Timestamp("2026-03-01", tz="UTC")) & (m.index < pd.Timestamp("2026-04-18", tz="UTC"))]
    M = lvl3.Market(m, m.spread.to_numpy(float) * 0.01 + 0.08)
    t = int(np.searchsorted(M.ot, pd.Timestamp("2026-04-17 23:58", tz="Asia/Bangkok").tz_convert("UTC")))
    s = lvl3.setup_at(M, t, lvl3.Params(k=0.5, s=1.5, n=5))
    assert s is not None and s["t_px"] == pytest.approx(4889.49)
    ext = pd.Timestamp(s["t_ext"], tz="UTC").tz_convert("Asia/Bangkok")
    assert ext.strftime("%H:%M") == "20:13" or (M.h[np.searchsorted(M.ot_ns, s["t_ext"])] == pytest.approx(4889.49))
    assert ext > pd.Timestamp("2026-04-17 20:04", tz="Asia/Bangkok")
    Z = M.m1zz[1.5]
    q = Z["conf_at"][t] if Z["conf_at"][t] >= 0 else len(Z["p"]) - 1
    sel = [j for j in range(q + 1) if Z["t"][j] == -1 and Z["start"][j] >= s["t_ext"]]
    assert min(Z["p"][sel]) > 4840  # the 4835 low before the peak is not a leg


def test_one_signal_per_setup(mar9):
    """Once per (entry TF, the bounce's start, the level, the side): the first qualifying peak only."""
    M = mar9
    dec = np.nonzero(plib.window_mask(M.ot).any(axis=1).to_numpy() & (M.ot >= pd.Timestamp("2026-02-01", tz="UTC")))[0]
    S = lvl3.signals(M, dec, lvl3.Params(k=0.5, s=1.5, n=3))
    assert len(S) > 10
    key = list(zip(S.etf, S.t_start, S.level.round(2), S.side))
    assert len(key) == len(set(key))
