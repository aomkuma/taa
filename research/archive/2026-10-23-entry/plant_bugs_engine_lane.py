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
    # TAA-1806: the AI's decision as an order for the ai_trader strategy
    ("a vetoed entry still ordered", [('size not in ("half", "full")', 'size not in ("half", "full", "none")')]),
    ("half and full swapped", [('risk_scale=0.5 if size == "half" else 1.0,', 'risk_scale=1.0 if size == "half" else 0.5,')]),
    ("the order never expires", [("valid_until=at + timedelta(minutes=pending_minutes),", "valid_until=at + timedelta(days=pending_minutes),")]),
    ("a missing stop ordered", [('if d.get("entry") is None or d.get("stop") is None:', 'if d.get("entry") is None:')]),
    ("a wait leaves the order waiting", [('if d.get("decision") in ("WAIT", "SELL", "BUY"):', 'if d.get("decision") in ("SELL", "BUY"):')]),
    ("the watch prices swapped", [('watch_above=None if d.get("watch_above") is None else float(d["watch_above"]),', 'watch_above=None if d.get("watch_below") is None else float(d["watch_below"]),')]),
    ("an exit not passed on", [('    if d.get("decision") == "EXIT":\n        strategy.request_exit(symbol)\n        return "exit"\n', "")]),
]

if __name__ == "__main__":
    main("app.engine.ai_trader", ROOT / "tests/unit/test_engine_ai_trader.py", BUGS)
