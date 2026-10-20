"""Planted bugs for the audit of dev2/swings.py::zigzag (mutated in memory only; the file is never changed) against
audit2/test_dev2_swings.py.

    .venv/Scripts/python research/2026-10-18-moments/agents/audit2/plant.py mutants_dev2_swings
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEV2 = ROOT / "research" / "2026-10-18-moments" / "agents" / "dev2"
TEST = ["research/2026-10-18-moments/agents/audit2/test_dev2_swings.py"]

ZZ = [
    ("the start-up fix removed (one bar, two turns)", "if hi_i != lo_i and h[hi_i] - lo[lo_i] >= thr[i]:", "if h[hi_i] - lo[lo_i] >= thr[i]:"),
    ("the start-up takes the later extreme", "                if lo_i < hi_i:", "                if lo_i > hi_i:"),
    ("a tie moves the peak later", "            if h[i] > h[ext]:", "            if h[i] >= h[ext]:"),
    ("a tie moves the trough later", "            if lo[i] < lo[ext]:", "            if lo[i] <= lo[ext]:"),
    ("the extending bar may also confirm (if, not elif)", "            elif h[ext] - lo[i] >= thr[i]:", "            if h[ext] - lo[i] >= thr[i]:"),
    ("strictly above the threshold", "            elif h[ext] - lo[i] >= thr[i]:", "            elif h[ext] - lo[i] > thr[i]:"),
    ("the threshold read at the pivot bar", "            elif h[ext] - lo[i] >= thr[i]:", "            elif h[ext] - lo[i] >= thr[ext]:"),
    ("the confirming bar recorded as the peak's bar", "piv.append((ext, float(h[ext]), 1, i))", "piv.append((i, float(h[ext]), 1, i))"),
    ("the trough tracked from the peak bar", "                piv.append((ext, float(h[ext]), 1, i))\n                direction, ext = -1, i",
     "                piv.append((ext, float(h[ext]), 1, i))\n                direction, ext = -1, ext"),
    ("the threshold of the next bar (look-ahead)", "            elif h[i] - lo[ext] >= thr[i]:", "            elif h[i] - lo[ext] >= thr[min(i + 1, n - 1)]:"),
]

TARGETS = [("swings", DEV2 / "swings.py", TEST, ZZ)]
