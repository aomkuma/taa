"""Planted bugs for app/ai/watcher.py against tests/unit/test_ai_watcher.py (plant.main; TAA-1805).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_watcher.py
"""

from __future__ import annotations

from plant import ROOT, main

BUGS = [
    ("the first call never made", [('        return ["the first call"]', "        return []")]),
    ("a close AT the watched price wakes", [("any(c > above for c in closes)", "any(c >= above for c in closes)")]),
    ("only the last close checked", [("any(c < below for c in closes)", "closes[-1:] and closes[-1] < below")]),
    ("above and below swapped", [("any(c > above for c in closes)", "any(c < above for c in closes)")]),
    ("no cooldown for behaviours", [("if moving and minutes >= COOLDOWN:", "if moving:")]),
    ("every behaviour wakes", [("moving = sorted(new_behaviours & MOVING)", "moving = sorted(new_behaviours)")]),
    ("the heartbeat at 45 minutes", [("HEARTBEAT, COOLDOWN = 30, 15", "HEARTBEAT, COOLDOWN = 45, 15")]),
    ("the cooldown at 5 minutes", [("HEARTBEAT, COOLDOWN = 30, 15", "HEARTBEAT, COOLDOWN = 30, 5")]),
    ("the heartbeat outside the windows too", [("    if in_window and minutes >= HEARTBEAT:", "    if minutes >= HEARTBEAT:")]),
    ("the heartbeat strictly after", [("and minutes >= HEARTBEAT:", "and minutes > HEARTBEAT:")]),
    ("manual calls counted too", [('if r.get("source") == SOURCE and pd.Timestamp', "if pd.Timestamp")]),
    ("the spend's day in UTC", [("day = now.tz_convert(TH).date()", "day = now.date()")]),
    ("a failed cycle stops the watcher", [("        try:\n            return self._cycle(now, closes)\n        except Exception as exc:",
                                           "        if True:\n            return self._cycle(now, closes)\n        try:\n            pass\n        except Exception as exc:")]),
    ("a failure not counted", [("            self.failures += 1\n", "")]),
    ("behaviours read at every bar", [("        if now.minute % 5 == 0:\n", "        if True:\n")]),
    ("the state not saved", [('        self.state.save(self.store / "watch_state.json")\n', "")]),
    ("the cap ignored", [("        if spent >= self.cap_usd:", "        if False:")]),
    ("the AI's own calls not sent back", [('(tail(session.read_text(encoding="utf-8"), 1500) if session.exists() else "(none)")', '"(none)"')]),
    ("the wrong model", [('MODEL = "claude-sonnet-5-5"', 'MODEL = "claude-opus-5-5"')]),
    ("the session note without the veto", [('veto = ", vetoed by " + ", ".join(rec["vetoed_by"]) if rec.get("vetoed_by") else ""', 'veto = ""')]),
]

if __name__ == "__main__":
    main("app.ai.watcher", ROOT / "tests/unit/test_ai_watcher.py", BUGS)
