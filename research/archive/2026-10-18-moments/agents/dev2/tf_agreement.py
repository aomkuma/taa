"""How often each TF's structure label (rule 4) agrees with M1's, at every M1 close of P1 / P2 (a description of the
readings, no outcome). Reads v31_learning.pkl (compare_ref.py).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev2/tf_agreement.py > research/2026-10-18-moments/agents/dev2/out_tf_agreement.txt
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swings as W  # noqa: E402,F401

PARTS = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18")}

with open(HERE / "v31_learning.pkl", "rb") as f:
    R = pickle.load(f)
b1 = R["M1"].bars
t = W._ns(b1.avail)
lab = {tf: (lambda r: np.where(r.at(t) >= 0, r.struct.label.to_numpy()[np.maximum(r.at(t), 0)], np.nan))(R[tf]) for tf in R}
for p, (a, b) in PARTS.items():
    k = (b1.t >= pd.Timestamp(a, tz="UTC")) & (b1.t < pd.Timestamp(b, tz="UTC"))
    k = k.to_numpy()
    row = []
    for tf in ("M5", "M15", "M30", "H1", "H4"):
        row.append(f"{tf} {np.mean(lab[tf][k] == lab['M1'][k]):.3f}")
    all_dn = np.mean(np.all([lab[tf][k] == -1 for tf in ("M1", "M5", "M15", "M30", "H1")], axis=0))
    all_up = np.mean(np.all([lab[tf][k] == 1 for tf in ("M1", "M5", "M15", "M30", "H1")], axis=0))
    print(f"{p}: share of M1 closes where the TF's label equals M1's: {', '.join(row)}; every TF M1..H1 down {all_dn:.3f}, up {all_up:.3f}")
    print(f"{p}: share of M1 closes where the threshold of the TF exceeds S (its ATR term rules): " + ", ".join(
        f"{tf} {np.mean((R[tf].thr > R[tf].s + 1e-9)[np.maximum(R[tf].at(t[k]), 0)]):.3f}" for tf in ("M5", "M15", "M30", "H1", "H4")))

# the D1 reading (rule 15), its shares of the minutes per part
rd = W.readings_at(R, t, tfs=("D1",))
for p, (a, b) in PARTS.items():
    k = ((b1.t >= pd.Timestamp(a, tz="UTC")) & (b1.t < pd.Timestamp(b, tz="UTC"))).to_numpy()
    lab_, bia = rd.D1_label.to_numpy()[k], rd.D1_bias.to_numpy()[k]
    print(f"{p}: D1 label up {np.mean(lab_ == 1):.3f}, down {np.mean(lab_ == -1):.3f}, mixed {np.mean(lab_ == 0):.3f},"
          f" unknown {np.mean(np.isnan(lab_)):.3f}; D1 bias up {np.mean(bia == 1):.3f}, down {np.mean(bia == -1):.3f}, unknown {np.mean(np.isnan(bia)):.3f}")

# the side and the trend (rule 17), their shares of the minutes per part
rd = W.readings_at(R, t)
for p, (a, b) in PARTS.items():
    k = ((b1.t >= pd.Timestamp(a, tz="UTC")) & (b1.t < pd.Timestamp(b, tz="UTC"))).to_numpy()
    txt = []
    for col in ("side", "side_bias", "trend", "trend_bias"):
        v = rd[col].to_numpy()[k]
        txt.append(f"{col}: +1 {np.mean(v == 1):.3f}, -1 {np.mean(v == -1):.3f}, 0 {np.mean(v == 0):.3f}, NaN {np.mean(np.isnan(v)):.3f}")
    print(f"{p}: " + "; ".join(txt))
