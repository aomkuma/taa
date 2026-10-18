"""Why gold runs the way it does - part (c): every reading together (notes.md, written before it is computed). Learned
on L1, checked on L2, the exam once at the threshold L2 chooses; what carries the weight and which way it pushes.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/why_model.py [10|5]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

QS = (0.55, 0.58, 0.60, 0.62, 0.65)
GAP_MIN = 60  # a pick is a trade: the next one at least an hour later


def spaced(t: pd.Series, keep: np.ndarray, gap_min: int = GAP_MIN) -> np.ndarray:
    """Of the kept moments (time order), each at least gap_min minutes after the last one taken."""
    out = np.zeros(len(t), bool)
    last = None
    for i in np.nonzero(keep)[0]:
        if last is None or (t.iloc[i] - last) >= pd.Timedelta(minutes=gap_min):
            out[i] = True
            last = t.iloc[i]
    return out


def picks(D: pd.DataFrame, p: np.ndarray, q: float) -> pd.DataFrame:
    """Buys at p >= q, sells at p <= 1 - q, spaced; the win = the side's X came first."""
    side = np.where(p >= q, 1, np.where(p <= 1 - q, -1, 0))
    k = spaced(D.t.reset_index(drop=True), side != 0)
    S = D.reset_index(drop=True)[k].assign(side=side[k], p=p[k])
    S["win"] = np.where(S.side > 0, S.up, S.dn)
    return S


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: PLC0415
    from sklearn.inspection import permutation_importance  # noqa: PLC0415
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415

    xu = int(sys.argv[1]) if sys.argv[1:] else 10
    X = pd.read_parquet(HERE / "why_frame.parquet")
    X["up"], X["dn"] = X[f"up{xu}"], X[f"dn{xu}"]
    X = X[X.up | X.dn].sort_values("t", kind="mergesort").reset_index(drop=True)  # one side came first
    feats = [c for c in X.columns if c not in ("t", "half", "up5", "dn5", "up10", "dn10", "up", "dn")]
    L1, L2, E = (X[X.half == h] for h in ("L1", "L2", "exam"))
    clf = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=400, min_samples_leaf=300, l2_regularization=1.0,
                                         early_stopping=True, validation_fraction=0.2, random_state=0)
    clf.fit(L1[feats].to_numpy(float), L1.up.astype(int))
    p2 = clf.predict_proba(L2[feats].to_numpy(float))[:, 1]
    print(f"X = {xu} U; moments with a side first: L1 {len(L1)}, L2 {len(L2)}, exam {len(E)}; up first: L1 {L1.up.mean():.3f}, "
          f"L2 {L2.up.mean():.3f}; AUC on L2 {roc_auc_score(L2.up, p2):.3f}")
    q10 = pd.qcut(p2, 10, labels=False, duplicates="drop")
    print("L2 by predicted decile:", pd.DataFrame({"d": q10, "p": p2, "y": L2.up.to_numpy()}).groupby("d").agg(p=("p", "mean"), up=("y", "mean")).round(3).to_dict("list"))
    days2 = np.busday_count("2025-01-01", "2026-04-18")
    rows = []
    for q in QS:
        S = picks(L2, p2, q)
        rows.append(dict(q=q, trades=len(S), a_weekday=len(S) / days2, win=S.win.mean() if len(S) else np.nan, buys=int((S.side > 0).sum()),
                         buy_win=S.win[S.side > 0].mean() if (S.side > 0).any() else np.nan, sells=int((S.side < 0).sum()),
                         sell_win=S.win[S.side < 0].mean() if (S.side < 0).any() else np.nan))
    Q = pd.DataFrame(rows)
    print("\nL2, the picks (one an hour at most):")
    print(Q.round(3).to_string(index=False))
    pi = permutation_importance(clf, L2[feats].to_numpy(float), L2.up.astype(int), n_repeats=3, random_state=0, scoring="roc_auc")
    imp = pd.Series(pi.importances_mean, index=feats).sort_values(ascending=False)
    print("\nwhat carries the weight on L2 (AUC lost when shuffled), and which way it pushes (mean predicted up-first by the "
          "reading's quintile on L2, lowest -> highest):")
    for f in imp.index[:15]:
        qb = pd.qcut(L2[f].rank(method="first"), 5, labels=False)
        push = pd.Series(p2).groupby(qb.to_numpy()).mean().round(3).tolist()
        real = L2.up.groupby(qb.to_numpy()).mean().round(3).tolist()
        print(f"  {f:16s} {imp[f]:.4f}  predicted {push}  real {real}")
    ok = Q[(Q.a_weekday >= 2) & (Q.a_weekday <= 4)]
    if ok.empty:
        print("\nno q gives 2-4 picks a weekday on L2: the exam is not read")
        return
    q = float(ok.sort_values("win", ascending=False).q.iloc[0])
    pe = clf.predict_proba(E[feats].to_numpy(float))[:, 1]
    S = picks(E, pe, q)
    print(f"\nthe threshold q = {q} (L2: {ok.set_index('q').loc[q, 'a_weekday']:.2f} a weekday, win {ok.set_index('q').loc[q, 'win']:.3f}); "
          f"THE EXAM, once: AUC {roc_auc_score(E.up, pe):.3f}; {len(S)} picks ({len(S) / np.busday_count('2026-04-20', '2026-10-17'):.2f} a weekday), "
          f"win {S.win.mean():.3f}; buys {int((S.side > 0).sum())} win {S.win[S.side > 0].mean():.3f}, sells {int((S.side < 0).sum())} "
          f"win {S.win[S.side < 0].mean():.3f}")
    S.to_parquet(HERE / f"why_exam_picks_{xu}.parquet")


if __name__ == "__main__":
    main()
