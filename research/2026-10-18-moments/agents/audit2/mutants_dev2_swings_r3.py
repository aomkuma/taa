"""The measurer's two planted bugs in dev2/swings.py that no unit test caught (precursors/plant_dev2_v31.py), against
the two round-3 tests in audit2/test_dev2_swings.py (the file is mutated in memory only).

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_dev2_swings_r3
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEV2 = ROOT / "research" / "2026-10-18-moments" / "agents" / "dev2"
TEST = ["research/2026-10-18-moments/agents/audit2/test_dev2_swings.py"]
MINE = [TEST[0] + "::test_known_at_leaves_out_a_pivot_confirmed_on_the_next_bar",
        TEST[0] + "::test_running_starts_after_the_pivot_bar"]

GAPS = [
    ("running leg includes the pivot bar", "s = slice(int(pb[-1]) + 1, d + 1)", "s = slice(int(pb[-1]), d + 1)"),
    ("known_at counts pivots confirmed on the next bar", 'n = int(np.searchsorted(piv[3], d, side="right"))',
     'n = int(np.searchsorted(piv[3], d + 1, side="right"))'),
]

TARGETS = [("swings", DEV2 / "swings.py", MINE, GAPS), ("swings", DEV2 / "swings.py", TEST, GAPS)]
