"""p4_ny by hand: the structure relative to the trade and the news flags.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/dev/test_p4_ny.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p4_ny as N  # noqa: E402

MN = 60 * 10**9


def test_rel_struct():
    assert N.rel_struct("up", 1) == "with" and N.rel_struct("down", -1) == "with"
    assert N.rel_struct("down", 1) == "against" and N.rel_struct("up", -1) == "against"
    assert N.rel_struct("mixed", 1) == "mixed / none" and N.rel_struct("none", -1) == "mixed / none"


def test_news_flags():
    news = np.array([100 * MN, 200 * MN])
    assert N.news_flags(160 * MN, 300 * MN, news) == (True, True)  # 100 is 60 min before (included); 200 inside
    assert N.news_flags(161 * MN, 200 * MN, news) == (False, False)  # 100 is 61 min before; 200 = the limit (excluded)
    assert N.news_flags(200 * MN, 260 * MN, news) == (True, False)  # a release at the entry minute counts as before
