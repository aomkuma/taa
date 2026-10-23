"""Planted bugs for observe.py (the hour's scoring) against test_observe.py - the same rule as plant.py, for a
research module that is not in a package (plant.main_script).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_observe.py
"""

from __future__ import annotations

from pathlib import Path

from plant import main_script

HERE = Path(__file__).resolve().parent

BUGS = [
    ("the hour includes the bar at as_of (look-ahead)", [("(m1.index < as_of)]\n    if seg.empty", "(m1.index <= as_of)]\n    if seg.empty")]),
    ("the hour starts after the reading's bar", [("seg = m1[(m1.index >= pd.Timestamp", "seg = m1[(m1.index > pd.Timestamp")]),
    ("with / against swapped for a down rhythm", [("(up, down) if s > 0 else (down, up)", "(up, down)")]),
    ("held on a tie or worse", [('out["with"] > out["against"]', 'out["with"] >= out["against"] - 1')]),
    ("against strictly beyond 1 ATR", [('if out["against"] >= AGAINST * atr:', 'if out["against"] > AGAINST * atr:')]),
    ("the against surprise from the move with", [('if out["against"] >= AGAINST * atr:', 'if out["with"] >= AGAINST * atr:')]),
    ("the no-rhythm run at 1.0 ATR", [("BIG_RANGE, AGAINST, RUN = 2.0, 1.0, 1.5", "BIG_RANGE, AGAINST, RUN = 2.0, 1.0, 1.0")]),
    ("the big hour at 3 ATR", [("BIG_RANGE, AGAINST, RUN = 2.0, 1.0, 1.5", "BIG_RANGE, AGAINST, RUN = 3.0, 1.0, 1.5")]),
    ("the first line from the last bar, not the first", [("    for bar in seg.itertuples():", "    for bar in list(seg.itertuples())[::-1]:")]),
    ("the line above needs a close beyond", [('a, b = bar.high >= prev["line_above"]', 'a, b = bar.close >= prev["line_above"]')]),
    ("the scorecard counts hours without a rhythm", [('if r.get("score", {}).get("rhythm_held") is not None', 'if "with" in r.get("score", {}) or r.get("score")')]),
    ("the scorecard's means over all 20 slots", [('/ len(scored)\n    a = ', '/ 20\n    a = ')]),
    ("the table pairs a reading with its own score", [("for prev, nxt in zip(rows, rows[1:], strict=False):", "for prev, nxt in zip(rows, rows, strict=False):")]),
    ("the table keeps hours without bars", [('if not sc.get("bars") or not prev.get("H1_atr"):', 'if not prev.get("H1_atr"):')]),
    ("the table in USD, not ATR", [("seen.setdefault(b, []).append((hour, (sc[\"high\"] - p) / atr, (p - sc[\"low\"]) / atr, (sc[\"last\"] - p) / atr))",
                                     "seen.setdefault(b, []).append((hour, (sc[\"high\"] - p), (p - sc[\"low\"]), (sc[\"last\"] - p)))")]),
    ("the table's hours in UTC", [('hour = pd.Timestamp(prev["as_of"]).tz_convert(TH).hour', 'hour = pd.Timestamp(prev["as_of"]).hour')]),
    ("the table's net up counts flat", [("{sum(x[3] > 0 for x in xs)} / {n}", "{sum(x[3] >= 0 for x in xs)} / {n}")]),
    ("the table least seen first", [("key=lambda kv: -len(kv[1])", "key=lambda kv: len(kv[1])")]),
    ("back-fill up to now itself", [("    while mark < now - pd.Timedelta(minutes=10) and len(out) < 72:", "    while mark <= now and len(out) < 72:")]),
    ("back-fill skips the 30-minute guard", [("    if mark <= last + pd.Timedelta(minutes=30):\n        mark += pd.Timedelta(hours=1)\n", "")]),
    ("back-fill a closed market", [("        if j > i:\n            out.append(mark)", "        if j >= i:\n            out.append(mark)")]),
    ("back-fill without a cap", [("and len(out) < 72:", "and len(out) < 720:")]),
    ("back-fill on the hour, not hh:05", [('mark = last.floor("h") + pd.Timedelta(minutes=5)', 'mark = last.floor("h")')]),
]

if __name__ == "__main__":
    main_script(HERE / "observe.py", HERE / "test_observe.py", BUGS, (HERE / "knowledge",))
