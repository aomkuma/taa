"""The probability from every layer together (owner, 2026-10-19: "combine every discipline and look at its
probability"). On combined_events.parquet (combine.py): the chance that a candidate trade reaches 1 ATR its way before
1 ATR against, learned on the learning half (its last fifth by time held back to stop the learning and to pick the
thresholds), read once on the exam: the calibration by predicted probability, the hit rate of the picks above the
thresholds, which layers carry the weight, and plain tables of the strongest pairs.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/model.py [noside]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
NUM = ["depth", "closed_back", "second_share", "gap", "H1_pos_side", "H1_lean", "H4_pos_side", "H4_lean", "round50",
       "H1_way", "H1_struct", "H4_way", "H4_struct", "hour_utc", "inwin", "atr_rel", "side"]
CAT = ["kind", "tf"]


def design(D: pd.DataFrame, cats: dict[str, list]) -> np.ndarray:
    X = [D[NUM].astype(float).to_numpy()]
    for c in CAT:
        X.append(np.column_stack([(D[c] == v).to_numpy(float) for v in cats[c]]))
    return np.column_stack(X)


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: PLC0415
    from sklearn.inspection import permutation_importance  # noqa: PLC0415
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415

    global NUM
    tag = ""
    if sys.argv[1:] == ["noside"]:  # the check: the same model not told the trade's side (so it cannot learn a drift)
        NUM = [c for c in NUM if c != "side"]
        tag = "_noside"
    A = pd.read_parquet(HERE / "combined_events.parquet")
    A = A[A.fp1 != "none"].copy()
    A["y"] = (A.fp1 == "win").astype(int)
    A["closed_back"] = A.closed_back.astype(float)
    A["inwin"] = A.inwin.astype(float)
    A = A.sort_values("t").reset_index(drop=True)
    cats = {c: sorted(A[c].unique()) for c in CAT}
    L, E = A[A.half == "learn"], A[A.half == "exam"]
    cut = L.t.iloc[int(len(L) * 0.8)]
    fit, val = L[L.t < cut], L[L.t >= cut]
    clf = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=400, min_samples_leaf=300,
                                         l2_regularization=1.0, early_stopping=True, validation_fraction=0.2, random_state=0)
    clf.fit(design(fit, cats), fit.y)
    pv, pe = clf.predict_proba(design(val, cats))[:, 1], clf.predict_proba(design(E, cats))[:, 1]
    print(f"rows: fit {len(fit)}, held-back learning {len(val)} (from {cut.date()}), exam {len(E)}; base win: "
          f"fit {fit.y.mean():.3f}, held-back {val.y.mean():.3f}, exam {E.y.mean():.3f}")
    print(f"AUC (0.5 = no skill): held-back learning {roc_auc_score(val.y, pv):.3f}, exam {roc_auc_score(E.y, pe):.3f}")
    for name, part, p in (("held-back learning", val, pv), ("exam", E, pe)):
        q = pd.qcut(p, 10, labels=False, duplicates="drop")
        T = pd.DataFrame({"decile": q, "p": p, "y": part.y.to_numpy()}).groupby("decile").agg(n=("y", "size"), predicted=("p", "mean"),
                                                                                           realized=("y", "mean"))
        print(f"\n{name}: by predicted probability (deciles)")
        print(T.round(3).to_string())
    for th in (0.52, 0.54, 0.56, 0.58):
        kv, ke = pv >= th, pe >= th
        print(f"picks with p >= {th}: held-back {int(kv.sum())} win {val.y[kv].mean() if kv.any() else np.nan:.3f} | exam {int(ke.sum())} "
              f"win {E.y[ke].mean() if ke.any() else np.nan:.3f} (se {np.sqrt(.25 / max(ke.sum(), 1)):.3f})")
    pi = permutation_importance(clf, design(val, cats), val.y, n_repeats=5, random_state=0, scoring="roc_auc")
    names = NUM + [f"{c}={v}" for c in CAT for v in cats[c]]
    imp = pd.Series(pi.importances_mean, index=names).sort_values(ascending=False)
    print("\nwhat carries the weight (held-back AUC lost when the layer is shuffled):")
    print(imp.head(12).round(4).to_string())
    E.assign(p=pe).to_parquet(HERE / f"model_exam_scored{tag}.parquet")
    val.assign(p=pv).to_parquet(HERE / f"model_heldback_scored{tag}.parquet")  # the threshold's own part (model_trades.py)


if __name__ == "__main__":
    main()
