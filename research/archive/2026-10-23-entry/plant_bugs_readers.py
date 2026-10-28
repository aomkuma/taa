"""Planted bugs for app/strategy/rhythm.py and picture.py against their tests in tests/unit (TAA-1802).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_readers.py
"""

from __future__ import annotations

from plant import ROOT, main

RHYTHM = [
    ("down needs only lower highs", [("down = highs[-1] < highs[-2] and lows[-1] < lows[-2]", "down = highs[-1] < highs[-2]")]),
    ("the big trend ignored", [("return -1 if down and big_sign < 0 else 1 if up and big_sign > 0 else 0",
                                "return -1 if down else 1 if up else 0")]),
    ("up and down swapped", [("return -1 if down and big_sign < 0 else 1 if up and big_sign > 0 else 0",
                              "return 1 if down and big_sign < 0 else -1 if up and big_sign > 0 else 0")]),
    ("one high is a sequence", [("if len(highs) < 2 or len(lows) < 2:", "if len(lows) < 2:")]),
    ("the first two swings, not the last", [("down = highs[-1] < highs[-2] and lows[-1] < lows[-2]", "down = highs[1] < highs[0] and lows[1] < lows[0]")]),
    ("the ATR from the first bar", [("atr = float(mt5_atr(h, lo, c, 14)[-1])", "atr = float(mt5_atr(h, lo, c, 14)[14])")]),
]

PICTURE = [
    ("clusters of one kept", [("return [c for c in out if len(c) >= 2]", "return [c for c in out if len(c) >= 1]")]),
    ("clusters by the first point, not the mean", [("abs(p[1] - np.mean([q[1] for q in out[-1]])) <= tol", "abs(p[1] - out[-1][0][1]) <= tol")]),
    ("pools far from price kept", [("if abs(mean - price) > 2.5 * atr or", "if abs(mean - price) > 25 * atr or")]),
    ("the pool's edge is its mean", [('level = min(p for _, p in cl) if name == "bottoms" else max(p for _, p in cl)', "level = mean")]),
    ("a sweep without depth", [("swept = lo[i] < level - 0.1 * atr and c[i] > level", "swept = lo[i] < level and c[i] > level")]),
    ("a sweep without the close back", [("swept = lo[i] < level - 0.1 * atr and c[i] > level", "swept = lo[i] < level - 0.1 * atr")]),
    ("a sweep from anywhere", [("came = c[i - 1] > level if bottoms else c[i - 1] < level", "came = True")]),
    ("the structure since counts highs only", [("\"up\": sum(bool(lo[k] > lo[k - 1] and h[k] > h[k - 1]) for k in after)", "\"up\": sum(bool(h[k] > h[k - 1]) for k in after)")]),
    ("the squeeze from the closes", [("return float((h[-n:].max() - lo[-n:].min()) / atr)", "return float((h[-n:].max() - h[-n:].min()) / atr)")]),
]

if __name__ == "__main__":
    main("app.strategy.rhythm", ROOT / "tests/unit/test_strategy_rhythm.py", RHYTHM)
    main("app.strategy.picture", ROOT / "tests/unit/test_strategy_picture.py", PICTURE)
