"""Planted bugs for audit 4: fingerprint.zigzag (against audit2/test_swings.py) and zones.py (against the earlier
precursors/test_zones.py).

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_swings
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PRE = ROOT / "research" / "2026-10-18-moments" / "agents" / "precursors"
ZZ_TESTS = ["research/2026-10-18-moments/agents/audit2/test_swings.py"]
ZONE_TESTS = ["research/2026-10-18-moments/agents/precursors/test_zones.py"]

ZIGZAG = [
    ("the start-up fix removed", "if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr:", "if h[hi_i] - lo[lo_i] >= thr:"),
    ("the start-up picks the later extreme", "                if lo_i < hi_i:\n", "                if lo_i > hi_i:\n"),
    ("an equal high does not move the peak", "if h[i] >= h[ext_i]:", "if h[i] > h[ext_i]:"),
    ("an equal low does not move the trough", "if lo[i] <= lo[ext_i]:", "if lo[i] < lo[ext_i]:"),
    ("a new high can also confirm (if, not elif)",
     "                ext_i = i\n            elif h[ext_i] - lo[i] >= thr:", "                ext_i = i\n            if h[ext_i] - lo[i] >= thr:"),
    ("strictly above the threshold", "elif h[ext_i] - lo[i] >= thr:", "elif h[ext_i] - lo[i] > thr:"),
    ("the trough tracked from the peak bar", "piv.append((ext_i, h[ext_i], 1, i))\n                direction, ext_i = -1, i",
     "piv.append((ext_i, h[ext_i], 1, i))\n                direction, ext_i = -1, ext_i"),
    ("the confirming bar recorded as the pivot bar", "piv.append((ext_i, lo[ext_i], -1, i))", "piv.append((ext_i, lo[ext_i], -1, ext_i))"),
]
ZONES = [
    ("a swing known one bar early", 'S["known"] = av[S.i.to_numpy() + k]', 'S["known"] = av[S.i.to_numpy() + k - 1]'),
    ("a swing known at its own bar", 'S["known"] = av[S.i.to_numpy() + k]', 'S["known"] = av[S.i.to_numpy()]'),
    # dropped as equivalent: keeping swings without k bars after them (F.fractals' centred window is NaN there)
    ("fractals of 3 bars (k = 1)", "def swings(b: pd.DataFrame, k: int = K)", "def swings(b: pd.DataFrame, k: int = 1)"),
    ("zones from every swing, known or not", "    sel = S[(S.known <= t_ns) & (S.i > bi - win)]", "    sel = S[(S.i > bi - win)]"),
    ("the merge tolerance from the next bar's ATR", "TOL_ATR * atr[bi]), float(atr[bi])", "TOL_ATR * atr[min(bi + 1, len(atr) - 1)]), float(atr[bi])"),
    ("the 5-day high includes the forming bar", 'float(Y["h"][a0:bi + 1].max())', 'float(Y["h"][a0:bi + 2].max())'),
    ("a zone of 2 swings counted as strong", "if z.touches >= 3 or (z.tops and z.lows):", "if z.touches >= 2 or (z.tops and z.lows):"),
]
TARGETS = [
    ("fingerprint", PRE / "fingerprint.py", ZZ_TESTS, ZIGZAG),
    ("zones", PRE / "zones.py", ZONE_TESTS, ZONES),
]
