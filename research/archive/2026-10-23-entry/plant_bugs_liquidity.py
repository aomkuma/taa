"""Planted bugs for app/strategy/liquidity.py against tests/unit/test_strategy_liquidity.py (plant.main; TAA-1807).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_liquidity.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("the true range without the gaps", [("tr = np.maximum(h - lo, np.maximum(np.abs(h - prev), np.abs(lo - prev)))", "tr = h - lo")]),
    ("a forming bar counted as closed", [("return df[df.index + pd.Timedelta(minutes=minutes) <= as_of]", "return df[df.index < as_of]")]),
    # (counting from the level's own bar is an equivalent mutant: the bar after a swing is always inside it)
    ("taken counted a bar late", [("taken_after(h[i], True, h, lo, i + 2)", "taken_after(h[i], True, h, lo, i + 3)")]),
    ("a taken pool still moves the stop", [("live = sorted((p.price for p in pools if not p.taken), key=lambda x: (x - edge) * sign)", "live = sorted((p.price for p in pools), key=lambda x: (x - edge) * sign)")]),
    # (dropping the re-pass after a pool is an equivalent mutant: the pools are sorted out from the edge, so one
    # pass walks the whole chain; a band sets the re-pass itself)
    ("a band only to its near edge", [("near, end = (lo, hi) if up else (hi, lo)", "near, end = (lo, lo) if up else (hi, hi)")]),
    ("no edge rule", [("    if abs(edge - price) <= reach:\n        far = next(", "    if False:\n        far = next(")]),
    ("the buffer on the wrong side", [("return round(far + sign * BUFFER_ATR * a, 2)", "return round(far - sign * BUFFER_ATR * a, 2)")]),
    ("one hour of structure", [("STRUCTURE_M5 = 24", "STRUCTURE_M5 = 12")]),
    ("the volume of a bar on its low step only", [("vol[float(s)] = vol.get(float(s), 0.0) + v / len(steps)", "vol[float(steps[0])] = vol.get(float(steps[0]), 0.0) + v / len(steps)")]),
    ("round numbers off by a step", [("return [Pool(float(lo), \"round number\", False), Pool(float(lo + step), \"round number\", False)]", "return [Pool(float(lo - step), \"round number\", False), Pool(float(lo), \"round number\", False)]")]),
    ("yesterday's bar not yet closed used", [("y = d1[d1.index + pd.Timedelta(days=1) <= as_of]", "y = d1[d1.index <= as_of]")]),
]

if __name__ == "__main__":
    main("app.strategy.liquidity", ROOT / "tests/unit/test_strategy_liquidity.py", BUGS)
