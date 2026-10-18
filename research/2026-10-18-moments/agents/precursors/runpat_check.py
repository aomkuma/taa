"""Is runpat.py's strongest pattern real, or the run catalogue's? (notes.md "The patterns gold runs from"). The catalogue
starts no new run of a way while a run of that way is still going (catalogue skips starts inside the last run), so at a
fresh low - often inside a fall - a run down is hardly ever "starting": the label favours the turn. The check without a
catalogue: from every moment's next M1 open, does price go X up before X down (and the mirror), X = 5 and 10 U (USD at
the reference price 4,100, scaled by price like the catalogue), within 240 minutes? Read by the edge and the break on
each timeframe, turned to the reversal (a low edge -> up), in the two learning halves and the exam.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/runpat_check.py
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

HORIZON = 240
REF = 4100.0


def passages(o: np.ndarray, h: np.ndarray, lo: np.ndarray, j0: np.ndarray, dist: np.ndarray, horizon: int = HORIZON,
             chunk: int = 20000) -> tuple[np.ndarray, np.ndarray]:
    """For each entry bar j0 and distance: (up_first, down_first) - price reached open + dist before open - dist (and
    the mirror) within horizon bars; one bar reaching both counts for neither (the stop first for either trade)."""
    up_first, dn_first = np.zeros(len(j0), bool), np.zeros(len(j0), bool)
    steps = np.arange(horizon)
    for a in range(0, len(j0), chunk):
        jj = j0[a:a + chunk]
        idx = jj[:, None] + steps[None, :]
        valid = idx < len(o)
        idx = np.minimum(idx, len(o) - 1)
        e = o[jj][:, None]
        d = dist[a:a + chunk][:, None]
        hu = (h[idx] >= e + d) & valid
        hd = (lo[idx] <= e - d) & valid
        fu = np.where(hu.any(axis=1), hu.argmax(axis=1), horizon)
        fd = np.where(hd.any(axis=1), hd.argmax(axis=1), horizon)
        up_first[a:a + chunk] = fu < fd
        dn_first[a:a + chunk] = fd < fu
    return up_first, dn_first


def main() -> None:
    import jlib  # noqa: PLC0415

    P = pd.read_parquet(HERE / "present_3y.parquet")
    m = jlib.m1_frame("XAUUSD")
    o, h, lo = m.open.to_numpy(float), m.high.to_numpy(float), m.low.to_numpy(float)
    P = P[P.j0 < len(o)].reset_index(drop=True)
    j0 = P.j0.to_numpy()
    t = pd.DatetimeIndex(P.t_dec)
    half = np.where(t >= EXAM_START, "exam", np.where(t < HALF_SPLIT, "L1", "L2"))
    res = {}
    for xu in (5, 10):
        res[xu] = passages(o, h, lo, j0, xu * o[j0] / REF)
    rows = []
    for tf in ("M1", "M5", "M15", "M30", "H1", "H4"):
        for reading in ("edge", "brk"):
            x = P[f"{tf}_{reading}"].to_numpy()
            for xu in (5, 10):
                up, dn = res[xu]
                for hf in ("L1", "L2", "exam"):
                    k = half == hf
                    low, high = k & (x == -1), k & (x == 1)
                    # turned to the reversal: at a low edge / below the last bottom the way is up; at a high the way is down
                    rev = np.r_[up[low], dn[high]]
                    cont = np.r_[dn[low], up[high]]
                    rows.append(dict(reading=f"{tf} {reading}", X=xu, half=hf, n=len(rev), reversal_first=rev.mean(),
                                     continuation_first=cont.mean(), base_up=up[k].mean(), base_dn=dn[k].mean()))
    R = pd.DataFrame(rows)
    W = R.pivot_table(index=["reading", "X"], columns="half", values=["n", "reversal_first", "continuation_first"], sort=False)
    W.columns = [f"{a}_{b}" for a, b in W.columns]
    pd.set_option("display.width", 250)
    print("from the next M1 open, X up before X down (and the mirror) within 240 minutes; the reading turned to the reversal")
    print(R.groupby(["X", "half"])[["base_up", "base_dn"]].first().round(3).to_string())
    cols = [f"{a}_{b}" for b in ("L1", "L2", "exam") for a in ("n", "reversal_first", "continuation_first")]
    print(W[cols].round(3).to_string())
    # the timeframes agreeing (runpat.py's question) on the same yardstick: k of M5 .. H4 reading the way, X that way first
    rows = []
    for reading in ("struct", "brk", "net_way"):
        X = np.column_stack([P[f"{tf}_{reading}"].to_numpy() for tf in ("M5", "M15", "M30", "H1", "H4")])
        for way in (1, -1):
            k_with = (X == way).sum(axis=1)
            for xu in (5, 10):
                first = res[xu][0] if way > 0 else res[xu][1]
                other = res[xu][1] if way > 0 else res[xu][0]
                for hf in ("L1", "L2", "exam"):
                    for k in range(6):
                        s = (half == hf) & (k_with == k)
                        rows.append(dict(reading=reading, X=xu, half=hf, k=k, n=int(s.sum()), its_way=first[s].sum(), other=other[s].sum()))
    A = pd.DataFrame(rows).groupby(["reading", "X", "k", "half"], sort=False)[["n", "its_way", "other"]].sum()
    A["its_way_first"] = A.its_way / A.n
    A["other_first"] = A.other / A.n
    A = A[["n", "its_way_first", "other_first"]].unstack("half")
    A.columns = [f"{a}_{b}" for a, b in A.columns]
    print("\nthe timeframes agreeing: k of M5, M15, M30, H1, H4 reading the way (up and down pooled), X that way first:")
    print(A[[f"{a}_{b}" for b in ("L1", "L2", "exam") for a in ("n", "its_way_first", "other_first")]].round(3).to_string())


if __name__ == "__main__":
    main()
