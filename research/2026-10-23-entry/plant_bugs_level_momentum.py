"""Planted bugs for app/strategy/level_momentum.py against tests/unit/test_level_momentum.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_level_momentum.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("look-ahead: the forming bar read", [("    x = closed(b, t)\n    keep", "    x = b\n    keep")]),
    ("bars before since read", [("keep = x.t_open >= since", "keep = x.t_open >= 0")]),
    ("a gap of 2 starts a visit", [("GAP = 3", "GAP = 2")]),
    ("a gap of 4 needed", [("GAP = 3", "GAP = 4")]),
    ("the bounce over 6 bars", [("REACT = 7", "REACT = 6")]),
    ("the bounce from the next bar", [("after = slice(i, i + REACT)", "after = slice(i + 1, i + 1 + REACT)")]),
    ("a resistance reads the highs", [("if side > 0 else float(level - lo[after].min())", "if side > 0 else float(h[after].max() - level)")]),
    ("worn from two bounces", [("worn = len(bounces) >= 3 and bounces[-1] < bounces[-2] < bounces[-3]", "worn = len(bounces) >= 2 and bounces[-1] < bounces[-2]")]),
    ("bars at the line counted from the start", [("for v in inside[::-1]:", "for v in inside:")]),
    ("approach over 9 bars", [("APPROACH = 10", "APPROACH = 9")]),
    ("approach in USD", [("return (abs(before - level) - abs(now - level)) / unit", "return abs(before - level) - abs(now - level)")]),
    ("approach sign flipped", [("return (abs(before - level) - abs(now - level)) / unit", "return (abs(now - level) - abs(before - level)) / unit")]),
]

if __name__ == "__main__":
    main("app.strategy.level_momentum", ROOT / "tests/unit/test_level_momentum.py", BUGS)
