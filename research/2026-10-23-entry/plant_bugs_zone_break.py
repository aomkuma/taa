"""Planted bugs for app/strategy/zone_break.py against tests/unit/test_zone_break.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_zone_break.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("lines every step, not every half", [("    half = s / 2\n", "    half = s\n")]),
    ("the band 0.3 step", [("BAND, AWAY, LOOK, WAIT, BOX_N, BOX_H, PAD = 0.15,", "BAND, AWAY, LOOK, WAIT, BOX_N, BOX_H, PAD = 0.3,")]),
    ("a box of 6 bars", [("0.5, 32, 48, 8, 0.3, 0.05", "0.5, 32, 48, 6, 0.3, 0.05")]),
    ("a box 0.35 step tall", [("0.5, 32, 48, 8, 0.3, 0.05", "0.5, 32, 48, 8, 0.35, 0.05")]),
    ("the box height strictly under", [("if box_h - box_l > BOX_H * s or", "if box_h - box_l >= BOX_H * s or")]),
    ("no distance needed", [("far = max(prev_h.max() - line, line - prev_l.min()) >= AWAY * s", "far = True")]),
    ("the straight break not checked", [("        if (c[j] - line) * (-came) > band:  # broke straight through: no consolidation\n            return None\n", "")]),
    # "the box may include the arrival bar" is an equivalent mutant: the arrival needs 0.5 step of distance, a box
    # at most 0.3 step tall can never hold the bar before it
    ("a box of 9 bars", [("0.5, 32, 48, 8, 0.3, 0.05", "0.5, 32, 48, 9, 0.3, 0.05")]),
    ("the box does not grow", [("            box_h, box_l = max(box_h, float(h[q])), min(box_l, float(lo[q]))\n", "")]),
    ("the stop inside the box", [("stop = box_l - PAD * s if side > 0 else box_h + PAD * s", "stop = box_l + PAD * s if side > 0 else box_h - PAD * s")]),
    ("through = the bounce", [("return ZoneBreak(i, line, came, q, side, side != came,", "return ZoneBreak(i, line, came, q, side, side == came,")]),
    ("came from the arrival bar's close", [("came = 1 if c[i - 1] > line else -1", "came = 1 if c[i] > line else -1")]),
    ("a break on the box edge counts", [("if c[q] > box_h or c[q] < box_l:", "if c[q] >= box_h or c[q] <= box_l:")]),
]

if __name__ == "__main__":
    main("app.strategy.zone_break", ROOT / "tests/unit/test_zone_break.py", BUGS)
