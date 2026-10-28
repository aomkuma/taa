"""Why gold runs the way it does - part (b): each component alone (notes.md "Why gold runs the way it does"). For every
reading (the indicators of indicators.py, the footprints of footprints.py, the pictures of the present library), its
values cut into five bins at the first learning half's quintiles; per bin, from the next M1 open, how often price went
X up before X down and X down before X up (X = 5 and 10 U, runpat_check.passages), in both learning halves. A reading
"leans" where up-first minus down-first moves the same way from its lowest to its highest bin in both halves; ranked
by the smaller of the two halves' moves. The exam is not read here.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/why.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from runpat import EXAM_START, HALF_SPLIT  # noqa: E402

PICTURE = ["struct", "brk", "net_way", "leg_way", "leg", "pos", "edge", "er", "retr", "size", "seg2"]


def frame() -> pd.DataFrame:
    """The moments with every reading and the outcomes (cached in why_frame.parquet)."""
    f = HERE / "why_frame.parquet"
    if f.exists():
        return pd.read_parquet(f)
    import jlib  # noqa: PLC0415
    from runpat_check import REF, passages  # noqa: PLC0415

    P = pd.read_parquet(HERE / "present_3y.parquet")
    X = pd.concat([pd.read_parquet(HERE / "indicators_3y.parquet"), pd.read_parquet(HERE / "footprints_3y.parquet")], axis=1)
    for tf in ("M1", "M5", "M15", "M30", "H1", "H4"):
        for r in PICTURE:
            X[f"{tf}_{r}"] = P[f"{tf}_{r}"].to_numpy()
    t = pd.DatetimeIndex(P.t_dec)
    X["hour_utc"] = t.hour + t.minute / 60
    X["weekday"] = t.dayofweek
    X["t"] = t
    X["half"] = np.where(t >= EXAM_START, "exam", np.where(t < HALF_SPLIT, "L1", "L2"))
    m = jlib.m1_frame("XAUUSD")
    o, h, lo = m.open.to_numpy(float), m.high.to_numpy(float), m.low.to_numpy(float)
    j0 = P.j0.to_numpy()
    ok = j0 < len(o)
    for xu in (5, 10):
        up, dn = np.zeros(len(P), bool), np.zeros(len(P), bool)
        u, d = passages(o, h, lo, j0[ok], xu * o[j0[ok]] / REF)
        up[ok], dn[ok] = u, d
        X[f"up{xu}"], X[f"dn{xu}"] = up, dn
    X = X[ok].reset_index(drop=True)
    X.to_parquet(f)
    return X


def lean(X: pd.DataFrame, col: str, xu: int) -> dict:
    """Up-first minus down-first by quintile bin (edges from L1) in L1 and L2; the move from the lowest to the highest bin."""
    x = X[col].astype(float)
    L1 = X.half == "L1"
    edges = np.unique(np.nanquantile(x[L1], [0, 0.2, 0.4, 0.6, 0.8, 1.0]))
    if len(edges) < 3:
        return {}
    b = np.clip(np.searchsorted(edges[1:-1], x, side="right"), 0, len(edges) - 2)
    b = np.where(x.isna(), -1, b)
    out = {"reading": col, "X": xu, "bins": len(edges) - 1}
    for h in ("L1", "L2"):
        k = (X.half == h).to_numpy() & (b >= 0)
        g = pd.DataFrame({"b": b[k], "tilt": X[f"up{xu}"].to_numpy()[k].astype(float) - X[f"dn{xu}"].to_numpy()[k].astype(float)})
        t = g.groupby("b").tilt.agg(["mean", "size"])
        out[f"lo_{h}"], out[f"hi_{h}"] = t["mean"].iloc[0], t["mean"].iloc[-1]
        out[f"move_{h}"] = t["mean"].iloc[-1] - t["mean"].iloc[0]
        out[f"n_lo_{h}"], out[f"n_hi_{h}"] = int(t["size"].iloc[0]), int(t["size"].iloc[-1])
    same = np.sign(out["move_L1"]) == np.sign(out["move_L2"])
    out["steady"] = bool(same)
    out["strength"] = min(abs(out["move_L1"]), abs(out["move_L2"])) if same else 0.0
    return out


def main() -> None:
    X = frame()
    cols = [c for c in X.columns if c not in ("t", "half", "up5", "dn5", "up10", "dn10")]
    rows = [r for xu in (5, 10) for c in cols if (r := lean(X, c, xu))]
    R = pd.DataFrame(rows).sort_values(["X", "strength"], ascending=[True, False])
    R.to_csv(HERE / "why_lean.csv", index=False)
    pd.set_option("display.width", 250, "display.max_rows", 200)
    for xu in (5, 10):
        L = X[X.half != "exam"]
        print(f"\nX = {xu} U: up first {L[f'up{xu}'].mean():.3f}, down first {L[f'dn{xu}'].mean():.3f} (learning); "
              f"up-first minus down-first in the lowest / highest bin of each reading, L1 | L2 - the 30 steadiest:")
        S = R[R.X == xu].head(30)
        print(S[["reading", "lo_L1", "hi_L1", "move_L1", "lo_L2", "hi_L2", "move_L2", "n_lo_L2", "n_hi_L2"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
