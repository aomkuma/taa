"""The patterns gold runs from, on timeframes that agree (notes.md, written before it is computed; owner, 2026-10-19:
"find the patterns gold most likes to use to run, on the timeframes that agree with each other"). On the present library
(clock moments, every timeframe's reading, the first 10 U run within 30 minutes): for each way and timeframe, the
readings turned to the run's side, how often each is there before a run its way, the chance of a run its way and the
other way with it, and the timeframes agreeing. A pattern counts when the run its way is >= LIFT x the base and above
the other way's in both learning halves on >= MIN_N moments each; only those are read in the exam, once.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/runpat.py
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TFS = ["M1", "M5", "M15", "M30", "H1", "H4"]
STACK_TFS = ["M5", "M15", "M30", "H1", "H4"]
READINGS = ["struct", "brk", "net_way", "leg_way", "edge", "seg2"]
HALF_SPLIT = pd.Timestamp("2025-01-01", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
LIFT, MIN_N = 1.2, 500


def turned(x: np.ndarray, way: int) -> np.ndarray:
    """A reading turned to the run's way: +1 with it, -1 against, 0 flat / mixed; 9 (unknown) stays 9."""
    x = np.asarray(x)
    return np.where(x == 9, 9, x * way)


def long_form(P: pd.DataFrame) -> pd.DataFrame:
    """One row per moment and way: the half, the run its way / the other way, every reading turned to that way."""
    t = pd.DatetimeIndex(P.t_dec)
    half = np.where(t >= EXAM_START, "exam", np.where(t < HALF_SPLIT, "L1", "L2"))
    out = []
    for way, mine, other in ((1, "ran_up", "ran_dn"), (-1, "ran_dn", "ran_up")):
        D = pd.DataFrame({"t": t, "half": half, "way": way, "run": (P.cls == mine).to_numpy(), "other": (P.cls == other).to_numpy()})
        for tf in TFS:
            for r in READINGS:
                D[f"{tf}_{r}"] = turned(P[f"{tf}_{r}"].to_numpy(), way)
        out.append(D)
    return pd.concat(out, ignore_index=True)


def score(D: pd.DataFrame, mask: pd.Series) -> dict:
    """With the pattern: moments, the run its way, the other way, the lift over this half's base, the share of all runs
    its way that had the pattern before them."""
    n = int(mask.sum())
    base = D.run.mean()
    p = D.run[mask].mean() if n else np.nan
    return dict(n=n, run=p, other=D.other[mask].mean() if n else np.nan, lift=p / base if n else np.nan,
                used=(mask & D.run).sum() / max(D.run.sum(), 1))


def patterns(L: pd.DataFrame) -> dict[str, pd.Series]:
    """Every pattern, as a mask on the long form."""
    pats = {}
    for tf in TFS:
        for r in READINGS:
            pats[f"{tf} {r} with"] = L[f"{tf}_{r}"] == 1
            pats[f"{tf} {r} against"] = L[f"{tf}_{r}"] == -1
    for r in ("struct", "brk", "net_way"):
        k = sum((L[f"{tf}_{r}"] == 1).astype(int) for tf in STACK_TFS)
        for j in range(len(STACK_TFS) + 1):
            pats[f"{r} with on {j} of M5..H4"] = k == j
    for trio in combinations(STACK_TFS, 3):
        pats["struct with on " + "+".join(trio)] = np.logical_and.reduce([L[f"{tf}_struct"] == 1 for tf in trio])
        pats["brk with on " + "+".join(trio)] = np.logical_and.reduce([L[f"{tf}_brk"] == 1 for tf in trio])
    return pats


def main() -> None:
    P = pd.read_parquet(HERE / "present_3y.parquet")
    L = long_form(P)
    pats = patterns(L)
    rows = []
    for name, mask in pats.items():
        rec = {"pattern": name}
        for h in ("L1", "L2"):
            k = (L.half == h).to_numpy()
            s = score(L[k], mask[k])
            rec |= {f"{key}_{h}": v for key, v in s.items()}
        rows.append(rec)
    R = pd.DataFrame(rows)
    R["counts"] = np.logical_and.reduce([(R[f"n_{h}"] >= MIN_N) & (R[f"lift_{h}"] >= LIFT) & (R[f"run_{h}"] > R[f"other_{h}"])
                                         for h in ("L1", "L2")])
    for h in ("L1", "L2"):
        D = L[L.half == h]
        print(f"{h}: {len(D) // 2} moments; a run its way within 30 minutes (base) {D.run.mean():.3f}")
    pd.set_option("display.width", 250, "display.max_rows", 400)
    cols = ["pattern", "n_L1", "used_L1", "run_L1", "other_L1", "lift_L1", "n_L2", "used_L2", "run_L2", "other_L2", "lift_L2", "counts"]
    print("\nevery reading, one timeframe at a time (turned to the run's way):")
    single = R[R.pattern.str.match(r"^(M1|M5|M15|M30|H1|H4) ")]
    print(single[cols].round(3).to_string(index=False))
    print("\nthe timeframes agreeing (M5, M15, M30, H1, H4):")
    print(R[R.pattern.str.contains(" of M5..H4")][cols].round(3).to_string(index=False))
    print("\nstacks of three timeframes, the 15 strongest by the smaller lift of the two halves:")
    st = R[R.pattern.str.contains(r"\+")].assign(m=lambda x: np.minimum(x.lift_L1, x.lift_L2)).sort_values("m", ascending=False)
    print(st[cols].head(15).round(3).to_string(index=False))
    C = R[R.counts]
    print(f"\n{len(C)} patterns count by the rule (lift >= {LIFT} and above the other way in both halves, n >= {MIN_N}); the exam, once:")
    E = L[L.half == "exam"]
    base = E.run.mean()
    print(f"exam: {len(E) // 2} moments, base {base:.3f}")
    ex = []
    for name in C.pattern:
        mask = pats[name][(L.half == "exam").to_numpy()]
        s = score(E, mask)
        ex.append(dict(pattern=name, lift_L1=C.set_index("pattern").lift_L1[name], lift_L2=C.set_index("pattern").lift_L2[name],
                       n_exam=s["n"], used_exam=s["used"], run_exam=s["run"], other_exam=s["other"], lift_exam=s["lift"]))
    if ex:
        print(pd.DataFrame(ex).sort_values("lift_exam", ascending=False).round(3).to_string(index=False))
    R.to_csv(HERE / "runpat_learning.csv", index=False)


if __name__ == "__main__":
    main()
