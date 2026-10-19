"""Planted bugs for p4_trades.py (Task P4): each a small edit run against test_p4_trades.py in a temporary copy (the
harness of plant_bugs_a1.py); every one must make a test fail (CAUGHT).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_p4.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "p4_trades.py", HERE / "test_p4_trades.py"
BUGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Asia's end included", [("if 7 * 60 <= m < 9 * 60:", "if 7 * 60 <= m <= 9 * 60:")]),
    ("Asia's start excluded", [("if 7 * 60 <= m < 9 * 60:", "if 7 * 60 < m < 9 * 60:")]),
    ("the Thai clock read as UTC", [('th = t.tz_convert("Asia/Bangkok")', "th = t")]),
    ("London's pad only on one side", [("if 13 * 60 - london_pad <= m < 14 * 60 + london_pad:", "if 13 * 60 <= m < 14 * 60 + london_pad:")]),
    ("London on London's clock", [("if 13 * 60 - london_pad <= m < 14 * 60 + london_pad:", "if 13 * 60 - london_pad <= m < 14 * 60 + london_pad and False:")]),
    ("New York at a fixed UTC-5 (no summer time)", [('ny = t.tz_convert("America/New_York")', 'ny = t.tz_convert("Etc/GMT+5")')]),
    ("New York + 1 hour only", [("if 9 * 60 + 30 <= mn < 11 * 60 + 30:", "if 9 * 60 + 30 <= mn < 10 * 60 + 30:")]),
    ("New York from 09:00", [("if 9 * 60 + 30 <= mn < 11 * 60 + 30:", "if 9 * 60 <= mn < 11 * 60 + 30:")]),
    ("in_windows keeps every candidate", [("    return out[out.window.notna()].reset_index(drop=True)", "    return out.reset_index(drop=True)")]),
    ("WN: the half hour's end included", [("    return 600 <= m < 630", "    return 600 <= m <= 630")]),
    ("WN: from 09:30, not 10:00", [("    return 600 <= m < 630", "    return 570 <= m < 630")]),
    # (an earlier bug - "the Asia / London entries filtered too" - was equivalent: 10:00 - 10:30 NY never falls in them)
    ("WN filters nothing", [('keep = [not (w == "NY" and ny_after_ten(t))', 'keep = [True or (w == "NY" and ny_after_ten(t))')]),
    ("metrics: a window's trades not split", [('for w, H in [("all", G)] + [(w, G[G.window == w]) for w in WINDOWS]:', 'for w, H in [("all", G)] + [(w, G) for w in WINDOWS]:')]),
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
