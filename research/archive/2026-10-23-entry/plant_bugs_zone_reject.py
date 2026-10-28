"""Planted bugs for app/strategy/zone_reject.py against tests/unit/test_zone_reject.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_zone_reject.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("the wick on the wrong side", [("wick = (min(o[q], c[q]) - lo[q]) if came > 0 else (h[q] - max(o[q], c[q]))", "wick = (h[q] - max(o[q], c[q])) if came > 0 else (min(o[q], c[q]) - lo[q])")]),
    ("a wick of a third", [("WICK = 0.5", "WICK = 0.33")]),
    ("four bars", [("REJECT_BARS = 3", "REJECT_BARS = 4")]),
    ("the close side not checked", [("if rng > 0 and wick >= WICK * rng and (c[q] - line) * came > 0:", "if rng > 0 and wick >= WICK * rng:")]),
    ("a close through not ending it", [("            if (c[q] - line) * (-came) > band:  # through the line: no rejection\n                break\n", "")]),
    ("the extreme of the rejection bar only", [("ext = float(lo[i : q + 1].min()) if came > 0 else float(h[i : q + 1].max())", "ext = float(lo[q]) if came > 0 else float(h[q])")]),
    ("the stop inside", [("stop = ext - PAD * s if came > 0 else ext + PAD * s", "stop = ext + PAD * s if came > 0 else ext - PAD * s")]),
    ("swept reversed", [("swept = ext < line if came > 0 else ext > line", "swept = ext > line if came > 0 else ext < line")]),
    ("the side reversed", [("out.append(Rejection(i, line, came, q,", "out.append(Rejection(i, line, -came, q,")]),
    ("the search starts after the arrival", [("for q in range(i, min(i + REJECT_BARS, n)):", "for q in range(i + 1, min(i + 1 + REJECT_BARS, n)):")]),
]

if __name__ == "__main__":
    main("app.strategy.zone_reject", ROOT / "tests/unit/test_zone_reject.py", BUGS)
