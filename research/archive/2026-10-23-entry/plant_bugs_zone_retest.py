"""Planted bugs for app/strategy/zone_retest.py against tests/unit/test_zone_retest.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_zone_retest.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("lines every step", [("        half, band = s / 2, BAND * s\n", "        half, band = s, BAND * s\n")]),
    ("a break inside the band", [("d = 1 if c[j] - line > band else -1 if line - c[j] > band else 0", "d = 1 if c[j] - line > 0 else -1 if line - c[j] > 0 else 0")]),
    ("no close on the other side needed", [("            if not ((before - line) * d < 0).any():\n                continue\n", "")]),
    ("the line keyed by its price", [("            key = (round(a, 2), kk)\n", "            key = (round(line, 2), 0)\n")]),
    ("a touch not fresh", [("if touch and not before and (c[q] - line) * d > 0:", "if touch and (c[q] - line) * d > 0:")]),
    ("the close on the line's other side accepted", [("if touch and not before and (c[q] - line) * d > 0:", "if touch and not before:")]),
    ("a failed break not ended", [("        if (c[q] - line) * d < -band:  # back through: the break failed\n            return q\n", "")]),
    ("the extreme from the close only", [("extreme = max(extreme, float(h[q])) if d < 0 else min(extreme, float(lo[q]))", "extreme = max(extreme, float(c[q])) if d < 0 else min(extreme, float(c[q]))")]),
    ("the stop inside the extreme", [("stop = extreme + PAD * s if d < 0 else extreme - PAD * s", "stop = extreme - PAD * s if d < 0 else extreme + PAD * s")]),
    ("the band 0.3 step", [("BAND, LOOK, WAIT, PAD = 0.15, 32, 96, 0.05", "BAND, LOOK, WAIT, PAD = 0.3, 32, 96, 0.05")]),
    ("the failed bar is not the break back", [("if d == 0 or active.get(key, -1) > j:", "if d == 0 or active.get(key, -1) >= j:")]),
    ("an expired break restarts on its last bar", [("    return j + WAIT + 1  #", "    return j + WAIT  #")]),
]

if __name__ == "__main__":
    main("app.strategy.zone_retest", ROOT / "tests/unit/test_zone_retest.py", BUGS)
