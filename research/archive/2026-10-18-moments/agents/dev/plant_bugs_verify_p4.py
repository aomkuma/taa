"""Planted bugs for verify_p4.py's own clock, run against test_verify_p4.py (the harness of plant_bugs_a1.py).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_verify_p4.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "verify_p4.py", HERE / "test_verify_p4.py"
BUGS = [
    ("summer time from the first Sunday of March", [("march = datetime(y, 3, 8 + (6 - datetime(y, 3, 8).weekday()) % 7)", "march = datetime(y, 3, 1 + (6 - datetime(y, 3, 1).weekday()) % 7)")]),
    ("summer time to the end of November's first Sunday", [("return march.date() <= day.date() < nov.date()", "return march.date() <= day.date() <= nov.date()")]),
    ("Thai = UTC + 8", [("th = t + timedelta(hours=7)", "th = t + timedelta(hours=8)")]),
    ("Asia's end included", [("if 420 <= m < 540:", "if 420 <= m <= 540:")]),
    ("London's pad on one side", [("if 780 - london_pad <= m < 840 + london_pad:", "if 780 <= m < 840 + london_pad:")]),
    ("New York always UTC - 5", [("    if us_summer(ny):\n        ny = t - timedelta(hours=4)\n", "")]),
    ("New York's window to 11:00", [('return "NY" if 570 <= ny_minute(t_ns) < 690 else None', 'return "NY" if 570 <= ny_minute(t_ns) < 660 else None')]),
]


def main() -> None:
    py = Path(sys.executable)
    src = MOD.read_text(encoding="utf-8")
    ok, line = run(src, MOD, TEST, py)
    print(f"{MOD.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits), MOD, TEST, py)
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
