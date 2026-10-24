"""Planted bugs for app/engine/ai_trader.py against tests/unit/test_engine_ai_trader.py (plant.main; TAA-1805).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_engine_lane.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("the first copy of a bar kept", [('.drop_duplicates("t", keep="last")', '.drop_duplicates("t", keep="first")')]),
    ("the frame not sorted", [('return out.set_index("t").sort_index()[', 'return out.set_index("t")[')]),
    ("now = the bar's open (reads a forming bar)", [("now = opened + pd.Timedelta(minutes=1)", "now = opened")]),
    ("the same bar twice", [("if self._last_open is not None and opened <= self._last_open:", "if self._last_open is not None and opened < self._last_open:")]),
    ("the closes after the last check, not from it", [("self._frames.m1.index >= since]", "self._frames.m1.index > since]")]),
    ("a call running is ignored", [("            if not self._running.done():\n                return False\n", "")]),
    # (a 'closes not carried' bug that set `since` after it was used had no effect - an equivalent mutant, dropped)
    ("a smaller M1 count", [("COUNTS = {Timeframe.M1: 7200,", "COUNTS = {Timeframe.M1: 720,")]),
    ("the journal from elsewhere", [('return self.journal_path.read_text(encoding="utf-8") if self.journal_path.exists() else ""', 'return ""')]),
    ("suspensions ignored", [('path = self.store / "suspended.json"', 'path = self.store / "none.json"')]),
]

if __name__ == "__main__":
    main("app.engine.ai_trader", ROOT / "tests/unit/test_engine_ai_trader.py", BUGS)
