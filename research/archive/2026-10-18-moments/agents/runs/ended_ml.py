"""Round 2, step 5 (notes.md): can all the step-1 features together tell "ended" from "continued" beyond the
geometry? LightGBM vs the geometry alone (p_geo), walk-forward over the design half-years (train on the earlier
halves, test on the next), R15 and 2.5-ATR signals pooled per population. Design only.

    data/venv-research/Scripts/python research/2026-10-18-moments/agents/runs/ended_ml.py
"""

from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
HL = ["H1", "H2", "H3", "H4", "H5"]
DROP = {"d", "e", "t", "side", "start", "ext", "run_t", "t_ext", "i_s", "xj", "k0", "pl", "lb", "size", "dur", "atr15",
        "u", "part", "half", "label", "R", "mR", "sl", "exit", "kind", "pnl", "adr_usd"}


def main() -> None:
    m1 = pd.read_parquet(HERE.parents[3] / "data/history/FBS-Demo/XAUUSD/M1.parquet", columns=["open_time", "close"])
    m1.index = pd.DatetimeIndex(pd.to_datetime(m1.open_time, utc=True))
    m1 = m1[~m1.index.duplicated(keep="last")].close
    for tag in ("R15", "A25"):
        z = pd.read_parquet(HERE / f"study_{tag}_design.parquet")
        z = z[z.label != "neither"].copy()
        # the decision close: the bar before the entry bar e (its open time is t - 1 min)
        cd = m1.reindex(pd.DatetimeIndex(z.t) - pd.Timedelta(minutes=1)).to_numpy()
        z["pgeo"] = (cd - z.start) * z.side / ((z.ext - z.start) * z.side)
        z["y"] = (z.label == "continued").astype(int)
        feats = [c for c in z.columns if c not in DROP and c != "y"]
        print(f"\n== {tag}: {len(z)} decided signals, {len(feats)} features")
        for k in range(2, 5):
            tr = z[z.half.isin(HL[:k])]
            te = z[z.half == HL[k]]
            g = LogisticRegression().fit(tr[["pgeo"]].fillna(0.7), tr.y)
            pg = g.predict_proba(te[["pgeo"]].fillna(0.7))[:, 1]
            mdl = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.02, num_leaves=15, min_child_samples=40,
                                     subsample=0.8, subsample_freq=1, colsample_bytree=0.7, verbose=-1)
            mdl.fit(tr[feats], tr.y)
            pm = mdl.predict_proba(te[feats])[:, 1]
            # the model's information beyond the geometry: AUC of the residual ranking among similar p_geo
            te = te.assign(pm=pm, pg=pg)
            q = pd.qcut(te.pgeo.rank(method="first"), 5, labels=False)
            within = [roc_auc_score(x.y, x.pm) for _, x in te.groupby(q) if x.y.nunique() == 2]
            top = te[te.pm - te.pg >= (te.pm - te.pg).quantile(0.8)]
            bot = te[te.pm - te.pg <= (te.pm - te.pg).quantile(0.2)]
            print(f"  train {HL[0]}..{HL[k - 1]} -> test {HL[k]} (n {len(te)}): AUC geometry {roc_auc_score(te.y, pg):.3f},"
                  f" model {roc_auc_score(te.y, pm):.3f}; within p_geo quintiles {np.mean(within):.3f};"
                  f" model-over-geometry top 20 %: continued {top.y.mean():.3f} vs expected {top.pg.mean():.3f},"
                  f" bottom 20 %: {bot.y.mean():.3f} vs {bot.pg.mean():.3f}")
        imp = pd.Series(mdl.feature_importances_, index=feats).sort_values(ascending=False)
        print("  top features (last fold):", ", ".join(f"{k} {v}" for k, v in imp.head(10).items()))


if __name__ == "__main__":
    main()
