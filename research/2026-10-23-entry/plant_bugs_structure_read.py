"""Planted bugs for app/strategy/structure_read.py against tests/unit/test_structure_read.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_structure_read.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("look-ahead: the forming bar read", [("    x = closed(b, t)\n    h, lo, c", "    x = b\n    h, lo, c")]),
    ("a fractal without its right-hand bars", [("for j in range(k, len(h) - k):", "for j in range(k, len(h)):")]),
    ("ties make fractals", [("if h[j] > h[j - k : j].max() and h[j] > h[j + 1 : j + 1 + k].max():", "if h[j] >= h[j - k : j].max() and h[j] >= h[j + 1 : j + 1 + k].max():")]),
    ("the first two highs, not the last", [("highs = tuple(p for _, kind, p in pts if kind == 1)[-2:]", "highs = tuple(p for _, kind, p in pts if kind == 1)[:2]")]),
    ("HH alone is an uptrend", [("if highs[1] > highs[0] and lows[1] > lows[0]:", "if highs[1] > highs[0]:")]),
    ("the down case swapped", [("elif highs[1] < highs[0] and lows[1] < lows[0]:\n            sign = -1", "elif highs[1] < highs[0] and lows[1] < lows[0]:\n            sign = 1")]),
    ("clarity: legs of one ATR", [("MIN_LEG_ATR = 2.0", "MIN_LEG_ATR = 1.0")]),
    ("clarity: alternation not checked", [("if len(last) < 4 or any(a[1] == b[1] for a, b in pairwise(last)):", "if len(last) < 4:")]),
    ("phase: two closes", [("s = np.sign(np.diff(c[-(n + 1) :]))", "s = np.sign(np.diff(c[-n:]))")]),
    # "a flat run counts" (dropping s[-1] != 0) is an equivalent mutant - an all-flat run returns 0 either way
    ("phase: two of three agreeing is a run", [("return int(s[-1]) if s[-1] != 0 and bool((s == s[-1]).all()) else 0", "return int(s[-1]) if s[-1] != 0 and int((s == s[-1]).sum()) >= 2 else 0")]),
    ("phase: the forming bar read", [("    c = closed(b, t).c\n", "    c = b.c\n")]),
    ("trend: side ignored", [("return [structure(f, t, k).sign * side for f in frames]", "return [structure(f, t, k).sign for f in frames]")]),
]

if __name__ == "__main__":
    main("app.strategy.structure_read", ROOT / "tests/unit/test_structure_read.py", BUGS)
