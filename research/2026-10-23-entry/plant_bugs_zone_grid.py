"""Planted bugs for app/strategy/zone_grid.py against tests/unit/test_zone_grid.py (SPEC.md 4.3).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_zone_grid.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("look-ahead: a D1 row known at its open", [("np.asarray(t_open, dtype=np.int64) + NS_DAY", "np.asarray(t_open, dtype=np.int64)")]),
    ("look-ahead: a row known 23 h after its open", [("NS_DAY = 24 * 60 * 60 * 10**9", "NS_DAY = 23 * 60 * 60 * 10**9")]),
    ("the base includes the impulse bar", [("top = np.maximum(o[i - BASE_N : i], c[i - BASE_N : i])", "top = np.maximum(o[i - BASE_N + 1 : i + 1], c[i - BASE_N + 1 : i + 1])"),
                                          ("bottom = np.minimum(o[i - BASE_N : i], c[i - BASE_N : i])", "bottom = np.minimum(o[i - BASE_N + 1 : i + 1], c[i - BASE_N + 1 : i + 1])")]),
    ("the anchor's side swapped", [("current = float(top.max() if body < 0 else bottom.min())", "current = float(bottom.min() if body < 0 else top.max())")]),
    ("the shift's sign swapped", [("shift[i] = -1 if body < 0 else 1", "shift[i] = 1 if body < 0 else -1")]),
    ("strictly above the threshold", [("abs(body) >= IMPULSE * atr[i]", "abs(body) > IMPULSE * atr[i]")]),
    ("ATR(14) instead of 20", [("ATR_N = 20", "ATR_N = 14")]),
    ("impulse at 1.0 ATR", [("IMPULSE = 1.5", "IMPULSE = 1.0")]),
    ("the anchor not carried", [("        anchor[i] = current\n", "        anchor[i] = current if shift[i] else math.nan\n")]),
    ("grid_at takes the next row", [('k = int(np.searchsorted(rows.known, t, side="right")) - 1', 'k = int(np.searchsorted(rows.known, t, side="right"))\n    k = min(k, len(rows.known) - 1)')]),
    ("nearest line by floor", [("k = round((price - state.anchor) / state.step)", "k = math.floor((price - state.anchor) / state.step)")]),
    ("next line without the quarter step", [("k = math.floor(pos + min_share) + 1 if side > 0 else math.ceil(pos - min_share) - 1",
                                              "k = math.floor(pos) + 1 if side > 0 else math.ceil(pos) - 1")]),
    ("the latest shift's direction from the first", [("last = int(rows.shift[past[-1]]) if len(past) else 0", "last = int(rows.shift[past[0]]) if len(past) else 0")]),
]

if __name__ == "__main__":
    main("app.strategy.zone_grid", ROOT / "tests/unit/test_zone_grid.py", BUGS)
