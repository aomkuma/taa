"""Planted bugs for charts_d.py (the pick rule and the exam guard), run against test_charts_d.py with the research venv
(matplotlib) in a temporary copy (the harness of plant_bugs_a1.py).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/plant_bugs_charts_d.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant_bugs_a1 import mutate, run  # noqa: E402

MOD, TEST = HERE / "charts_d.py", HERE / "test_charts_d.py"
PY = HERE.parents[3] / "data/venv-research/Scripts/python.exe"
BUGS = [
    ("pick: a zero counts as a winner", [('for name, sel in (("winner", G.pnl > 0), ("loser", G.pnl <= 0)):', 'for name, sel in (("winner", G.pnl >= 0), ("loser", G.pnl < 0)):')]),
    ("pick: the farthest, not the nearest", [('H = G[sel].sort_values(["dist", "entry_t"], kind="stable").head(3)', 'H = G[sel].sort_values(["dist", "entry_t"], kind="stable").tail(3)')]),
    ("pick: a tie goes to the later", [('H = G[sel].sort_values(["dist", "entry_t"], kind="stable").head(3)', 'H = G[sel].sort_values(["dist", "entry_t"], ascending=[True, False], kind="stable").head(3)')]),
    ("pick: 2 a group", [('.head(3)', '.head(2)')]),
    ("guard: none", [("    if b >= EXAM.value:\n        raise RuntimeError", "    if False:\n        raise RuntimeError")]),
]


def main() -> None:
    src = MOD.read_text(encoding="utf-8")
    ok, line = run(src, MOD, TEST, PY)
    print(f"{MOD.name}: control (no bug): {'PASSED' if ok else 'FAILED'} - {line}", flush=True)
    if not ok:
        raise SystemExit("the unedited source must pass first")
    caught = 0
    for k, (name, edits) in enumerate(BUGS, 1):
        ok, line = run(mutate(src, edits), MOD, TEST, PY)
        caught += not ok
        print(f"{'MISSED' if ok else 'CAUGHT'}  #{k:02d} {name}  ({line})", flush=True)
    print(f"\n{caught} of {len(BUGS)} planted bugs caught")


if __name__ == "__main__":
    main()
