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
    ("the heartbeat at 20 minutes", [("HEARTBEAT, COOLDOWN, STOP_IDLE = 15, 4, 60", "HEARTBEAT, COOLDOWN, STOP_IDLE = 20, 4, 60")]),
    ("the heartbeat strictly after", [("    if minutes >= HEARTBEAT:", "    if minutes > HEARTBEAT:")]),
]

if __name__ == "__main__":
    main_script(HERE / "watcher.py", HERE / "test_watcher.py", BUGS, (HERE / "knowledge",))
