"""Straight lines like the owner's: the step fixed between zone shifts (v1 lets it breathe daily). Same H4-turn reading as
zone_band.py: the share of learning-period turns within +-0.10 step of a line, for the step fixed at the shift day's ATR,
and fixed at the ATR N days after the shift (the owner drew his lines with the ATR of the days he drew them)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zone_grid_v1 as Z  # noqa: E402

h4 = Z.bars("H4")
g = Z.daily_grid(Z.bars("D1"))
x = h4[(h4.index >= "2025-10-20") & (h4.index < "2026-04-18")]
hi, lo = x.high.values, x.low.values
shift_i = np.flatnonzero(g["shift"].values != "")
for lag in ("breathing", 0, 3, 5, 10):
    fr = []
    for i in range(1, len(x) - 1):
        for p, ok in ((hi[i], hi[i] > hi[i - 1] and hi[i] > hi[i + 1]), (lo[i], lo[i] < lo[i - 1] and lo[i] < lo[i + 1])):
            if not ok:
                continue
            k = g.index.searchsorted(x.index[i], side="right") - 1
            anc = g.anchor.values[k]
            if lag == "breathing":
                stp = g.step.values[k]
            else:
                s0 = shift_i[shift_i <= k]
                if not len(s0):
                    continue
                j = min(s0[-1] + lag, k)  # the step known by then (never a later day)
                stp = g.step.values[j]
            pos = (p - anc) / stp
            fr.append(abs(pos - np.round(pos)))
    fr = np.array(fr)
    print(f"step {lag!s:>9}: turns {len(fr)}, within +-0.10 step {100 * (fr <= 0.10).mean():.0f} %, within +-0.20 {100 * (fr <= 0.20).mean():.0f} %, median {np.median(fr):.3f}")
