"""Auditor check 1b: the stored labels (own_ml_long y/usd/min, own_ml_arsenal_labels) against ny_lab.M1.trade on a
random sample, and the features against a recomputation on bars truncated at the decision bar (look-ahead test).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/auditor/label_checks.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, ".")
import gold  # noqa: E402
from ml_dataset import tf_features  # noqa: E402
from ny_lab import M1  # noqa: E402


def main() -> None:
    gold.below_normal_priority()
    rng = np.random.default_rng(1)
    P = M1()
    d = pd.read_parquet("data/research/own_ml_long.parquet")
    lab = pd.read_parquet("data/research/own_ml_arsenal_labels.parquet")
    d["t"] = pd.to_datetime(d.t, utc=True)
    assert (P.ot[d.e.to_numpy()] == d.t).all()
    print("rows", len(d), "from", d.t.min(), "to", d.t.max())
    # ---- labels
    idx = rng.choice(len(d), 3000, replace=False)
    mism = {}
    for sl in (4, 6, 8):
        bad = []
        for i in idx:
            r = d.iloc[i]
            m = P.trade(int(r.e), int(r.side), 5.0, float(sl), None, 30)
            y = int(m["exit"] == "win")
            if y != int(r[f"y{sl}"]) or abs(m["usd"] - r[f"usd{sl}"]) > 0.02 or m["mins"] != int(r[f"min{sl}"]):
                bad.append((i, r.t, int(r.side), m, int(r[f"y{sl}"]), float(r[f"usd{sl}"]), int(r[f"min{sl}"])))
        mism[f"own_ml_long y{sl}"] = bad
    for tp, sl in ((5, 4), (8, 6), (10, 8), (15, 10)):
        hz = 120 if tp >= 15 else 60
        bad = []
        for i in idx:
            r, lr = d.iloc[i], lab.iloc[i]
            if lr[f"y_{tp}_{sl}"] < 0:
                continue
            m = P.trade(int(r.e), int(r.side), float(tp), float(sl), None, hz)
            y = {"win": 1, "stop": 2, "time": 0}[m["exit"]]
            if y != int(lr[f"y_{tp}_{sl}"]) or abs(m["usd"] - lr[f"usd_{tp}_{sl}"]) > 0.02 or m["mins"] != int(lr[f"min_{tp}_{sl}"]):
                bad.append((i, r.t, int(r.side), m, int(lr[f"y_{tp}_{sl}"]), float(lr[f"usd_{tp}_{sl}"]), int(lr[f"min_{tp}_{sl}"])))
        mism[f"arsenal {tp}/{sl}"] = bad
    for k, bad in mism.items():
        print(f"labels {k}: {len(bad)} of {len(idx)} differ from M1.trade")
        for b in bad[:4]:
            print("    ", b)
    # how many label outcomes sit on an exact touch (|extreme - level| < 0.005): float-sensitive
    # ---- features vs truncated recomputation
    m1 = gold.bars("M1")
    m1 = m1[(m1.index >= pd.Timestamp("2023-09-01", tz="UTC")) & (m1.index < pd.Timestamp("2026-10-15", tz="UTC"))]
    sub = d.iloc[rng.choice(len(d), 60, replace=False)]
    worst = {}
    for r in sub.itertuples():
        p = int(r.e) - 1
        cut = m1.iloc[: p + 1]
        t = pd.DatetimeIndex([r.t])
        for rule, mins, name in (("15min", 15, "m15"), ("60min", 60, "h1")):
            f = tf_features(cut, rule, mins, name, t).iloc[0]
            for col, v in f.items():
                s = getattr(r, col)
                if col.endswith(("_c_e20", "_c_e50", "_e20_slope")):
                    s = s * r.side
                elif col.endswith("_rsi") and r.side < 0:
                    s = 100 - s
                elif col.endswith("_pos20") and r.side < 0:
                    s = 1 - s
                worst[col] = max(worst.get(col, 0.0), abs(float(v) - float(s)) if np.isfinite(v) else 0.0)
        c = cut.close.to_numpy()
        worst["ret1"] = max(worst.get("ret1", 0.0), abs((c[-1] - c[-2]) * r.side - r.ret1))
        worst["ret15"] = max(worst.get("ret15", 0.0), abs((c[-1] - c[-16]) * r.side - r.ret15))
        worst["spread"] = max(worst.get("spread", 0.0), abs(cut.spread.iloc[-1] * 0.01 - r.spread))
    print("features, largest |stored - truncated recomputation| over 60 rows (float32 storage ~1e-3 expected):")
    for k, v in worst.items():
        print(f"    {k:16} {v:.5f}")


if __name__ == "__main__":
    main()
