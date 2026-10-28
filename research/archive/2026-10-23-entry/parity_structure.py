"""Parity (SPEC.md 4.4): app/strategy/structure_read.py against the research originals
(research/2026-10-18-moments/agents/journal/ny_b2/week.py ``structure`` with its 3-bar fractals over 200 bars, and
``run3`` = phase n = 3 on D1) at 300 decision times 2025-10-20 .. 2026-10-16 on D1 / H4 / H1 / M15.

    .venv/Scripts/python research/2026-10-23-entry/parity_structure.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/2026-10-18-moments/agents/journal/ny_b2"))
import week as W  # noqa: E402

from app.strategy import structure_read as sr  # noqa: E402
from app.strategy.plan1_b2 import Bars  # noqa: E402

HOURS = {"D1": 24, "H4": 4, "H1": 1, "M15": 0.25}
frames = {}
for tf, hrs in HOURS.items():
    d = W.Z.bars(tf)
    t = d.index.as_unit("ns").asi8
    frames[tf] = (d, Bars(t, t + int(hrs * 3600 * 10**9), d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float),
                          d.close.to_numpy(float)))
times = pd.date_range("2025-10-20", "2026-10-16", periods=300, tz="UTC")
bad = {tf: 0 for tf in HOURS}
bad_phase = 0
for t in times:
    for tf, (d, b) in frames.items():
        if W.structure(d, t, tf) != sr.structure(b, t.value).sign:
            bad[tf] += 1
    if W.run3(t) != (sr.phase(frames["D1"][1], t.value) != 0):
        bad_phase += 1
print("structure mismatches per frame (of 300):", bad)
print("phase vs run3 mismatches (of 300):", bad_phase)
print("PARITY", "OK" if not any(bad.values()) and not bad_phase else "FAILED")
