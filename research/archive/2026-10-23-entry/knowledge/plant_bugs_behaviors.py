"""Planted bugs for app/strategy/behaviors.py against tests/unit/test_strategy_behaviors.py (plant.main; TAA-1802).

    .venv/Scripts/python research/2026-10-23-entry/knowledge/plant_bugs_behaviors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from plant import ROOT, main  # noqa: E402

BUGS = [
    ("efficiency over n moves read n - 1", [("x = np.asarray(c[-(n + 1) :], dtype=float)", "x = np.asarray(c[-n:], dtype=float)")]),
    ("efficiency keeps the sign", [("return abs(float(x[-1] - x[0])) / path", "return float(x[-1] - x[0]) / path")]),
    ("efficiency path from the net", [("path = float(np.abs(np.diff(x)).sum())", "path = float(np.abs(x[-1] - x[0]))")]),
    ("efficiency without the length guard", [("    if len(x) < n + 1:\n        return math.nan\n", "")]),
    ("line break against the bar before, not k bars", [("math.floor((c[-1 - k] - anchor) / unit)", "math.floor((c[-2] - anchor) / unit)")]),
    ("line break by rounding, not the cell", [("now, before = math.floor((c[-1] - anchor) / unit), math.floor((c[-1 - k] - anchor) / unit)",
                                              "now, before = round((c[-1] - anchor) / unit), round((c[-1 - k] - anchor) / unit)")]),
    ("line break sides swapped", [('return "up" if now > before else "down" if now < before else "none"',
                                   'return "down" if now > before else "up" if now < before else "none"')]),
    ("climax range strictly over 2 ATR", [("if not (rng >= 2 * atr and", "if not (rng > 2 * atr and")]),
    ("climax volume not needed", [("and v >= 2 * v_mean and", "and")]),
    ("climax wick from the close", [("if h - max(o, c) >= 0.5 * rng:", "if h - c >= 0.5 * rng:")]),
    ("climax wick at a third", [("if h - max(o, c) >= 0.5 * rng:", "if h - max(o, c) >= 0.33 * rng:")]),
    ("runaway without yesterday's extreme", [("if run_step >= 1 and price > y_high:", "if run_step >= 1:")]),
    ("runaway at half a step", [("if run_step >= 1 and price > y_high:", "if run_step >= 0.5 and price > y_high:")]),
    ("runaway down checks the high", [("if run_step <= -1 and price < y_low:", "if run_step <= -1 and price < y_high:")]),
    ("Asia from 06:00 Thai", [("asia0, london0 = day + pd.Timedelta(hours=7)", "asia0, london0 = day + pd.Timedelta(hours=6)")]),
    ("Asia break read before London", [("    if th < london0:\n        return \"none\"\n", "")]),
    ("Asia break: both read as up", [('return "both" if up and down else', 'return')]),
    ("the sweep window off by one", [('if s["i"] >= len(c) - recent and', 'if s["i"] >= len(c) - recent - 1 and')]),
    ("the sweep sides swapped", [('"low" if pool["name"] == "bottoms" else "high"', '"high" if pool["name"] == "bottoms" else "low"')]),
    ("the day from 00:00 Thai", [("start = th.normalize() + pd.Timedelta(hours=5)", "start = th.normalize()")]),
    ("the day's start never rolls back", [("return (start if th >= start else start - pd.Timedelta(days=1)).tz_convert(\"UTC\")", "return start.tz_convert(\"UTC\")")]),
    ("the forming M15 bar read", [("(m15.index + pd.Timedelta(minutes=15) <= as_of)", "(m15.index <= as_of)")]),
    ("a swing low needs only the bar before", [("if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]:", "if lo[i] < lo[i - 1]:")]),
    ("swing highs read from the lows", [("if hi[i] > hi[i - 1] and hi[i] > hi[i + 1]:", "if lo[i] > lo[i - 1] and lo[i] > lo[i + 1]:")]),
    ("yesterday = the forming D1 bar", [("y = d1[d1.index + pd.Timedelta(days=1) <= as_of]", "y = d1[d1.index <= as_of]")]),
    ("level prices read the forming M15 bar", [("    x = m15[(m15.index >= day_start(before)) & (m15.index + pd.Timedelta(minutes=15) <= before)]", "    x = m15[(m15.index >= day_start(before)) & (m15.index <= before)]")]),
    ("level prices without yesterday", [("        out += [float(y.low.iloc[-1]), float(y.high.iloc[-1])]", "        pass")]),
    ("a level sweep without the depth", [("w_lo.min() < lv - 0.1 * atr and last > lv", "w_lo.min() < lv and last > lv")]),
    ("a level sweep without the reclaim", [("w_lo.min() < lv - 0.1 * atr and last > lv", "w_lo.min() < lv - 0.1 * atr")]),
    ("a level sweep from the wrong side", [("low = any(before > lv and", "low = any(")]),
    ("a level sweep high from the lows", [("high = any(before < lv and w_hi.max() > lv + 0.1 * atr", "high = any(before < lv and w_lo.max() > lv + 0.1 * atr")]),
    ("both sides: always low", [('return "low" if int(np.argmin(w_lo)) > int(np.argmax(w_hi)) else "high"', 'return "low"')]),
    ("the before close inside the window", [("w_lo, w_hi, before, last = lo[-recent:], h[-recent:], c[-recent - 1], c[-1]", "w_lo, w_hi, before, last = lo[-recent:], h[-recent:], c[-recent], c[-1]")]),
]

if __name__ == "__main__":
    main("app.strategy.behaviors", ROOT / "tests/unit/test_strategy_behaviors.py", BUGS)
