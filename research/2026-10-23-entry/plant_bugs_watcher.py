"""Planted bugs for watcher.wake_reasons against test_watcher.py (plant.main_script).

    .venv/Scripts/python research/2026-10-23-entry/plant_bugs_watcher.py
"""

from __future__ import annotations

from pathlib import Path

from plant import main_script

HERE = Path(__file__).resolve().parent

BUGS = [
    ("the first call never made", [('        return ["the first call"]', "        return []")]),
    ("a close AT the watched price wakes", [("any(c > above for c in closes)", "any(c >= above for c in closes)")]),
    ("only the last close checked", [("any(c < below for c in closes)", "closes[-1:] and closes[-1] < below")]),
    ("above and below swapped", [("any(c > above for c in closes)", "any(c < above for c in closes)")]),
    ("no cooldown for behaviours", [("if moving and minutes >= COOLDOWN:", "if moving:")]),
    ("every behaviour wakes", [("moving = sorted(new_behaviours & MOVING)", "moving = sorted(new_behaviours)")]),
    ("the heartbeat at 45 minutes", [("HEARTBEAT, COOLDOWN, STOP_IDLE = 30, 15, 60", "HEARTBEAT, COOLDOWN, STOP_IDLE = 45, 15, 60")]),
    ("the cooldown at 5 minutes", [("HEARTBEAT, COOLDOWN, STOP_IDLE = 30, 15, 60", "HEARTBEAT, COOLDOWN, STOP_IDLE = 30, 5, 60")]),
    ("the heartbeat outside the windows too", [("    if in_window and minutes >= HEARTBEAT:", "    if minutes >= HEARTBEAT:")]),
    ("the spend of every day", [("if r.get(\"source\") == \"watcher\" and pd.Timestamp(r[\"as_of\"]).tz_convert(TH).date() == day)", "if r.get(\"source\") == \"watcher\")")]),
    ("manual calls counted too", [("if r.get(\"source\") == \"watcher\" and pd.Timestamp", "if pd.Timestamp")]),
    ("the spend's day in UTC", [("day = now.tz_convert(TH).date()", "day = now.date()")]),
    ("the heartbeat strictly after", [("and minutes >= HEARTBEAT:", "and minutes > HEARTBEAT:")]),
]

if __name__ == "__main__":
    main_script(HERE / "watcher.py", HERE / "test_watcher.py", BUGS, (HERE / "knowledge",))
