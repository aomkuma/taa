"""Planted bugs for app/strategy/big_trend.py against tests/unit/test_big_trend.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_big_trend.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("look-ahead: the forming bar read", [("    x = closed(b, t)\n    h, lo, c", "    x = b\n    h, lo, c")]),
    ("a turn strictly beyond the size", [("if direction >= 0 and hi - lo[i] >= size and hi_i < i:", "if direction >= 0 and hi - lo[i] > size and hi_i < i:")]),
    # the branch that recorded a swing before the first turn was unreachable (removed), so no bug for it
    ("the running leg ignored", [("    if leg < 0 and lows and extreme < lows[-1]:", "    if False:")]),
    ("the running leg always counted", [("    if leg < 0 and lows and extreme < lows[-1]:", "    if leg < 0 and lows:")]),
    ("down needs only lower highs", [("sign = -1 if lh >= 1 and ll >= 1 else", "sign = -1 if lh >= 1 else")]),
    ("the run counts the oldest pair", [("for newer, older in zip(values[::-1], values[-2::-1], strict=False):", "for newer, older in zip(values[1:], values, strict=False):")]),
    ("the size 2 x ATR", [("SIZE_ATR = 3.0", "SIZE_ATR = 2.0")]),
    ("the size from ATR(20)", [("    atr = mt5_atr(h, lo, c, 14)\n    size", "    atr = mt5_atr(h, lo, c, 20)\n    size")]),
    ("the up leg's extreme taken as the low", [("return out, direction, (hi if direction > 0 else low if direction < 0 else math.nan)", "return out, direction, (low if direction > 0 else hi if direction < 0 else math.nan)")]),
]

if __name__ == "__main__":
    main("app.strategy.big_trend", ROOT / "tests/unit/test_big_trend.py", BUGS)
