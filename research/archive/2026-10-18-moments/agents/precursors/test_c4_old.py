"""c4_old.c4_flags by hand.

    .venv/Scripts/python -m pytest research/2026-10-18-moments/agents/precursors/test_c4_old.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c4_old import c4_flags  # noqa: E402


def test_c4_flags():
    # unit 1 (price 4100): half the 8 U target = 4
    assert c4_flags(2003.0, 1990.0, 2000.0, 1.0, 1) == (True, False)  # the high 3 above: near
    assert c4_flags(2005.0, 1990.0, 2000.0, 1.0, 1) == (False, False)  # 5 above: too far
    assert c4_flags(1999.0, 1990.0, 2000.0, 1.0, 1) == (False, True)  # already above the 72-hour high: behind
    assert c4_flags(2010.0, 1997.0, 2000.0, 1.0, -1) == (True, False)  # a sell: the low 3 below: near
    assert c4_flags(2010.0, 2001.0, 2000.0, 1.0, -1) == (False, True)  # below the 72-hour low: behind
