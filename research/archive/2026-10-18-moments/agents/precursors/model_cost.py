"""Part (c) (notes.md "Part (c): the model learns the after-cost result", written before it is computed): model.py's
side-blind model with one change - the label is the floor trade's own result after the costs (R > 0;
combined_trades_floorN.parquet from base_after_costs.py). The threshold is chosen on the held-back learning part by the
rule written down first; the exam is read once at that threshold, week by week.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/model_cost.py [FLOOR]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from model import CAT, NUM, design  # noqa: E402
from model_trades import take  # noqa: E402

THRESHOLDS = (0.40, 0.45, 0.50, 0.55, 0.60)
MIN_R, MIN_TRADES = 0.05, 150
FEATURES = [c for c in NUM if c != "side"]


def choose(rows: list[dict]) -> float | None:
    """The lowest threshold whose held-back trades reach MIN_R with at least MIN_TRADES trades."""
    ok = [r["th"] for r in rows if r["trades"] >= MIN_TRADES and r["R"] >= MIN_R]
    return min(ok) if ok else None


def summary(T: pd.DataFrame, a: str, b: str) -> str:
    import wf  # noqa: PLC0415

    eq = T.pnl.cumsum()
    return (f"{len(T)} trades ({len(T) / np.busday_count(a, b):.2f} a weekday), win {(T.pnl > 0).mean():.3f}, R {T.R.mean():+.3f}, "
            f"USD {T.pnl.sum():+.1f} at 0.01 lot, lowest running total {eq.min():+.1f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, "
            f"worst {T.pnl.min():+.2f}, longest losing streak {wf.longest_run(T.pnl.to_numpy() < 0)}")


def main() -> None:
    import model  # noqa: PLC0415
    import wf  # noqa: PLC0415
    from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: PLC0415
    from sklearn.metrics import roc_auc_score  # noqa: PLC0415

    floor = sys.argv[1] if sys.argv[1:] else "5"
    model.NUM = FEATURES  # design() reads model.NUM: side-blind
    A = pd.read_parquet(HERE / f"combined_trades_floor{floor}.parquet")
    A["y"] = (A.R > 0).astype(int)
    A["closed_back"] = A.closed_back.astype(float)
    A["inwin"] = A.inwin.astype(float)
    A = A.sort_values("t", kind="mergesort").reset_index(drop=True)
    cats = {c: sorted(A[c].unique()) for c in CAT}
    L, E = A[A.half == "learn"], A[A.half == "exam"]
    cut = L.t.iloc[int(len(L) * 0.8)]
    fit, val = L[L.t < cut], L[L.t >= cut]
    clf = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=400, min_samples_leaf=300,
                                         l2_regularization=1.0, early_stopping=True, validation_fraction=0.2, random_state=0)
    clf.fit(design(fit, cats), fit.y)
    val = val.assign(p=clf.predict_proba(design(val, cats))[:, 1])
    print(f"floor {floor} USD; rows: fit {len(fit)}, held back {len(val)} (from {cut.date()}), exam {len(E)}; a profitable trade: "
          f"fit {fit.y.mean():.3f}, held back {val.y.mean():.3f}; AUC held back {roc_auc_score(val.y, val.p):.3f}")
    rows = []
    for th in THRESHOLDS:
        T = take(val, th)
        rows.append(dict(th=th, picks=int((val.p >= th).sum()), trades=len(T), win=(T.pnl > 0).mean() if len(T) else np.nan,
                         R=T.R.mean() if len(T) else np.nan, usd=T.pnl.sum()))
    print("\nheld back, the picks one at a time:")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    th = choose(rows)
    if th is None:
        print(f"\nno threshold reaches R >= {MIN_R} with >= {MIN_TRADES} trades: the exam is not read")
        return
    T = take(val, th)
    print(f"\nthe threshold: p >= {th}; held back: {summary(T, '2025-10-16', '2026-04-18')}")
    E = E.assign(p=clf.predict_proba(design(E, cats))[:, 1])
    X = take(E, th)
    X["cell"] = f"cost_floor{floor}_p{th}"
    print(f"the exam, once: {summary(X, '2026-04-18', '2026-10-17')}")
    print("  by pattern:", X.groupby("pattern").agg(n=("R", "size"), R=("R", "mean"), usd=("pnl", "sum")).round(3).to_dict("index"))
    print("  by timeframe:", X.groupby("tf").agg(n=("R", "size"), R=("R", "mean"), usd=("pnl", "sum")).round(3).to_dict("index"))
    print("  buys", int((X.side > 0).sum()), "sells", int((X.side < 0).sum()))
    pd.set_option("display.width", 220)
    print("\nthe exam week by week (Thai weeks, Monday):")
    print(wf.weekly(X).to_string(index=False))
    X.to_parquet(HERE / f"model_cost_trades_floor{floor}.parquet")


if __name__ == "__main__":
    main()
