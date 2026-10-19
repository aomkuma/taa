"""losers_p2 by hand: the losers of one variant joined to their catches, and the picture's title.

    data/venv-research/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_losers_p2.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import losers_p2 as LP  # noqa: E402


def trades():
    base = dict(tf="M1", t_dec=100, family="w", side=1, variant="B2", news_cost=0.0, pnl=-2.0, level_kind="x2")
    return pd.DataFrame([
        base,                                     # a B2 loser: kept
        dict(base, pnl=1.0),                      # a winner: out
        dict(base, variant="A"),                  # another variant: out
        dict(base, news_cost=1.0),                # another cost run: out
        dict(base, t_dec=200, family="ihs"),      # a second B2 loser: kept
    ])


def catches():
    cols = dict(start_t=0, pts_t=[1], pts_p=[1.0], pts_lab=["L1"], neck_t=None, neck_p=None, box_t=None, box_p=None,
                level=4000.0, zone=1.0, trigger=4005.0, variant="W", other_pattern="", other_structure="up", part="P1")
    return pd.DataFrame([dict(tf="M1", t_dec=100, family="w", side=1, **cols),
                         dict(tf="M1", t_dec=200, family="ihs", side=1, **dict(cols, level=4100.0)),
                         dict(tf="M1", t_dec=100, family="w", side=-1, **dict(cols, level=1.0))])


def test_losers_joined_to_their_catches():
    L = LP.losers_with_patterns(trades(), catches(), "B2")
    assert len(L) == 2 and L.level.tolist() == [4000.0, 4100.0] and L.pattern_variant.tolist() == ["W", "W"]
    assert (L.pnl < 0).all() and (L.variant == "B2").all()
    with pytest.raises(ValueError, match="without its catch"):
        LP.losers_with_patterns(trades(), catches().iloc[[1, 2]], "B2")


def test_title():
    r = pd.Series(dict(reason="wrong way x other TF with", n_reason=68, entry_t=pd.Timestamp("2026-01-06 13:46", tz="UTC").value,
                       part="P1", tf="M1", name="W", level_kind="PDH", level=4455.58, side=1, entry=4463.59, stop=4454.98,
                       exit="stop", exit_px=4454.65, pnl=-8.94, R=-1.04))
    assert LP.title_of(4, r, 431) == ("#4 wrong way x other TF with (68 of 431 losers) - 2026-01-06 20:46 Thai - P1 - M1 W at "
                                      "PDH 4455.58 - BUY in 4463.59, stop 4454.98, out stop 4454.65: -8.94 USD (-1.04 R)")
    assert np.isfinite(r.level)
