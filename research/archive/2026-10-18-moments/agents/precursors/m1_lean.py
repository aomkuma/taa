"""The moment before the run - part 2 (notes.md, written before it is computed): each M1 reading alone, by quintile
(P1's edges): the chance of a clean 10-USD run up / down starting at the next open, by moments and by each day's first
moment, P1 and P2. Kept only when an end quintile lifts one way to >= LIFT x its base in both parts, with >= 30 days.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/m1_lean.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from phase_tables import by_days  # noqa: E402

LIFT, MIN_DAYS = 1.5, 30


def kept(rec: dict) -> list[str]:
    """Which ends (lo / hi) x ways (up / dn) lift the run to >= LIFT x the base in both parts, with enough days."""
    out = []
    for end in ("lo", "hi"):
        for way in ("up", "dn"):
            ok = all(rec[f"{p}_{end}_{way}"] >= LIFT * rec[f"{p}_base_{way}"] and rec[f"{p}_{end}_days"] >= MIN_DAYS for p in ("P1", "P2"))
            if ok:
                out.append(f"{end}->{way}")
    return out


def main() -> None:
    X = pd.read_parquet(HERE / "m1_features.parquet")
    X = X[X.part.isin(["P1", "P2"])].reset_index(drop=True)
    X["up"] = (X.run_next > 0).astype(float)
    X["dn"] = (X.run_next < 0).astype(float)
    cols = [c for c in X.columns if c not in ("t", "part", "run_next", "up", "dn")]
    P1 = (X.part == "P1").to_numpy()
    rows = []
    for col in cols:
        v = X[col].to_numpy(float)
        edges = np.unique(np.nanquantile(v[P1], [0.2, 0.4, 0.6, 0.8]))
        b = np.where(np.isnan(v), np.nan, np.searchsorted(edges, v, side="right").astype(float))
        rec = {"reading": col, "bins": len(edges) + 1}
        for p in ("P1", "P2"):
            k = (X.part == p).to_numpy()
            for way in ("up", "dn"):
                t = by_days(X[k], b[k], X[way].to_numpy()[k])
                rec[f"{p}_base_{way}"] = X.loc[k, way].mean()
                rec[f"{p}_lo_{way}"], rec[f"{p}_hi_{way}"] = t["mean"].iloc[0], t["mean"].iloc[-1]
                rec[f"{p}_lo_first_{way}"], rec[f"{p}_hi_first_{way}"] = t.day_mean.iloc[0], t.day_mean.iloc[-1]
                rec[f"{p}_lo_days"], rec[f"{p}_hi_days"] = int(t.days.iloc[0]), int(t.days.iloc[-1])
                rec[f"{p}_bins_{way}"] = " ".join(f"{x:.3f}" for x in t["mean"])
        rec["kept"] = " ".join(kept(rec))
        rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_csv(HERE / "m1_lean.csv", index=False)
    pd.set_option("display.width", 260, "display.max_rows", 100, "display.max_colwidth", 60)
    print(f"base a minute: P1 up {R.P1_base_up.iloc[0]:.4f} down {R.P1_base_dn.iloc[0]:.4f}; P2 up {R.P2_base_up.iloc[0]:.4f} down {R.P2_base_dn.iloc[0]:.4f}")
    print("\nkept (an end quintile >= 1.5 x the base one way in both parts, >= 30 days):")
    K = R[R.kept != ""]
    print(K[["reading", "kept", "P1_bins_up", "P1_bins_dn", "P2_bins_up", "P2_bins_dn"]].to_string(index=False))
    print(f"\nnoise (dropped): {', '.join(R[R.kept == ''].reading)}")


if __name__ == "__main__":
    main()
