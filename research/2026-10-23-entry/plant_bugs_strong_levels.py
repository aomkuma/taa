"""Planted bugs for app/strategy/strong_levels.py against tests/unit/test_strong_levels.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_strong_levels.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("look-ahead: a bar counted at its open", [("keep = b.avail <= t", "keep = b.t_open <= t")]),
    ("look-ahead: a fractal before its right bars close", [("for j in range(start, n - k):", "for j in range(start, n):")]),
    ("a tie is a swing", [("if x.h[j] > left_h.max() and x.h[j] > right_h.max():", "if x.h[j] >= left_h.max() and x.h[j] >= right_h.max():")]),
    ("the turn reads one bar too many", [("after = slice(j + 1, min(n, j + 1 + TURN_BARS))", "after = slice(j, min(n, j + 1 + TURN_BARS))")]),
    ("the low's turn measured to the low", [("float(x.h[after].max() - x.lo[j])", "float(x.lo[after].max() - x.lo[j])")]),
    ("merge to the first, not the mean", [("if group and s.price - float(np.mean([g.price for g in group])) > tol:", "if group and s.price - group[0].price > 2 * tol:")]),
    ("strong with one touch", [("if lv.touches >= 2 or lv.turn >= MAJOR_STEP * step", "if lv.touches >= 1 or lv.turn >= MAJOR_STEP * step")]),
    ("a major turn strictly above", [("lv.turn >= MAJOR_STEP * step", "lv.turn > MAJOR_STEP * step")]),
    ("shift anchors dropped", [('out += [Level(float(a), 1, math.nan, 0, "shift") for a in shift_anchors if math.isfinite(a)]', "out += []")]),
    ("room aims at the level, not its band", [("ahead = [lv.price - band for lv in levels if lv.price - band > entry] if side > 0 else [", "ahead = [lv.price for lv in levels if lv.price > entry] if side > 0 else [")]),
    ("room takes the farthest level", [("edge = min(ahead) if side > 0 else max(ahead)", "edge = max(ahead) if side > 0 else min(ahead)")]),
    ("pool band floor 0.5", [("POOL_BAND_MIN = 1.0", "POOL_BAND_MIN = 0.5")]),
    ("pool band 0.1 step", [("POOL_BAND_STEP = 0.05", "POOL_BAND_STEP = 0.1")]),
    ("pools past the stop missed (the bug the tests caught)", [("lo, hi = (stop - band, entry) if side > 0 else (entry, stop + band)", "lo, hi = (stop, entry) if side > 0 else (entry, stop + band)")]),
    ("round numbers every 5", [("ROUND_USD = 10.0", "ROUND_USD = 5.0")]),
    ("the margin from the farthest pool", [("margin = min((p - stop) * side for p in inside) if inside else math.nan", "margin = max((p - stop) * side for p in inside) if inside else math.nan")]),
]

if __name__ == "__main__":
    main("app.strategy.strong_levels", ROOT / "tests/unit/test_strong_levels.py", BUGS)
