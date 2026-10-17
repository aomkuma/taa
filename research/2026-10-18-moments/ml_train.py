"""Round 3 (docs/OWN_SETUP.md): LightGBM learns "+5 USD before the stop" from ml_dataset.py's minutes.

A. Fixed: fit on 2025-10-14 .. 2026-02-14, choose the stop and the score cut on 2026-02-14 .. 04-14 (validation),
   test once on 2026-04-14 .. 10-14, month by month.
B. Monthly re-fit: each test month is predicted by a model fitted on the six months before it minus the last two
   (those two choose the stop and the cut).
One position at a time; at a minute the side with the higher score. Runs in data/venv-research:

    data/venv-research/Scripts/python research/2026-10-18-moments/ml_train.py
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score

D_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/research/own_ml.parquet"
TRAIN_FROM = sys.argv[2] if len(sys.argv) > 2 else "2025-10-14"
STOPS = (4, 6, 8)
RATES = (0.002, 0.005, 0.01, 0.02, 0.05)  # the share of candidate rows traded (top scores)
META = {"t", "e", "mfe", "side"} | {f"{p}{s}" for p in ("y", "usd", "min") for s in STOPS}
PARAMS = dict(
    n_estimators=400,
    learning_rate=0.03,
    num_leaves=15,
    min_child_samples=300,
    subsample=0.7,
    subsample_freq=1,
    colsample_bytree=0.7,
    reg_lambda=5.0,
    random_state=7,
    verbose=-1,
)


def trades(d: pd.DataFrame, score: np.ndarray, cut: float, sl: int) -> pd.DataFrame:
    x = d.assign(score=score)
    x = x[x.score >= cut].sort_values(["t", "score"], ascending=[True, False]).drop_duplicates("t")
    keep, free = [], pd.Timestamp(0, tz="UTC")
    for t, m in zip(x.t, x[f"min{sl}"], strict=True):
        ok = t >= free
        keep.append(ok)
        if ok:
            free = t + pd.Timedelta(minutes=int(m))
    return x[np.array(keep, dtype=bool)]


def fit(d: pd.DataFrame, feats: list[str], sl: int) -> LGBMClassifier:
    m = LGBMClassifier(**PARAMS)
    m.fit(d[feats], d[f"y{sl}"])
    return m


def choose(train: pd.DataFrame, val: pd.DataFrame, feats: list[str]) -> tuple[int, float, LGBMClassifier, str]:
    best = (-np.inf, None, None, None, "")
    days = val.t.dt.normalize().nunique()
    for sl in STOPS:
        m = fit(train, feats, sl)
        s = m.predict_proba(val[feats])[:, 1]
        for rate in RATES:
            cut = float(np.quantile(s, 1 - rate))
            tr = trades(val, s, cut, sl)
            if len(tr) < 0.3 * days:
                continue
            total = tr[f"usd{sl}"].sum()
            if total > best[0]:
                best = (total, sl, cut, m, f"sl {sl} rate {rate}: val {len(tr)} trades, {tr[f'usd{sl}'].mean():+.2f} USD/trade")
    return best[1], best[2], best[3], best[4]


def report(name: str, tr: pd.DataFrame, sl: int, days: int) -> None:
    usd = tr[f"usd{sl}"]
    by_m = usd.groupby(tr.t.dt.to_period("M").astype(str)).sum() if len(tr) else pd.Series(dtype=float)
    print(f"  {name}: {len(tr)} trades, hit +5 {100 * tr[f'y{sl}'].mean():.1f}%, {usd.mean():+.2f} USD/trade"
          f" ({usd.mean() / sl:+.3f} R), {usd.sum():+.1f} USD at 0.01 lot, {len(tr) / days:.2f}/day,"
          f" months+ {(by_m > 0).sum()}/{len(by_m)}")


def main() -> None:
    warnings.filterwarnings("ignore", category=UserWarning)
    d = pd.read_parquet(D_PATH)
    d["t"] = pd.to_datetime(d.t, utc=True)
    feats = [c for c in d.columns if c not in META]
    T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    print(f"rows {len(d)}, features {len(feats)}")

    print("\nA. fixed model")
    tr_, va, te = d[(d.t >= T(TRAIN_FROM)) & (d.t < T("2026-02-14"))], d[(d.t >= T("2026-02-14")) & (d.t < T("2026-04-14"))], d[d.t >= T("2026-04-14")]
    sl, cut, m, note = choose(tr_, va, feats)
    print("  chosen on validation:", note)
    s = m.predict_proba(te[feats])[:, 1]
    print(f"  test AUC {roc_auc_score(te[f'y{sl}'], s):.3f}")
    picked = trades(te, s, cut, sl)
    report("test 2026-04-14 .. 10-14", picked, sl, te.t.dt.normalize().nunique())
    for mo, g in picked.groupby(picked.t.dt.to_period("M").astype(str)):
        print(f"     {mo}: {len(g):3} trades, hit {100 * g[f'y{sl}'].mean():3.0f}%, {g[f'usd{sl}'].sum():+7.1f} USD")
    imp = pd.Series(m.feature_importances_, index=feats).sort_values(ascending=False)
    print("  top features:", ", ".join(f"{k} {v}" for k, v in imp.head(15).items()))
    for rate in RATES:  # the whole curve, for reading only (the choice above stays)
        c2 = float(np.quantile(s, 1 - rate))
        print(f"     (curve) top {100 * rate:4.1f}%: ", end="")
        report("", trades(te, s, c2, sl), sl, te.t.dt.normalize().nunique())

    print("\nB. monthly re-fit (fit 4 months, choose on 2, test the next month)")
    allp = []
    for k in range(6):
        m0 = T("2026-04-14") + pd.DateOffset(months=k)
        a = T(TRAIN_FROM) if TRAIN_FROM != "2025-10-14" else m0 - pd.DateOffset(months=6)
        b, c_ = m0 - pd.DateOffset(months=2), m0 + pd.DateOffset(months=1)
        tr_, va, te = d[(d.t >= a) & (d.t < b)], d[(d.t >= b) & (d.t < m0)], d[(d.t >= m0) & (d.t < c_)]
        sl, cut, m, note = choose(tr_, va, feats)
        s = m.predict_proba(te[feats])[:, 1]
        p = trades(te, s, cut, sl).assign(sl=sl, usd=lambda x, sl=sl: x[f"usd{sl}"], y=lambda x, sl=sl: x[f"y{sl}"])
        allp.append(p)
        print(f"  {m0:%Y-%m-%d}: {note}; test AUC {roc_auc_score(te[f'y{sl}'], s):.3f}, {len(p)} trades,"
              f" hit {100 * p.y.mean():.0f}%, {p.usd.sum():+.1f} USD, {p.usd.mean() / sl:+.3f} R")
    P = pd.concat(allp)
    days = d[d.t >= T("2026-04-14")].t.dt.normalize().nunique()
    by_m = P.usd.groupby(P.t.dt.to_period("M").astype(str)).sum()
    print(f"  all: {len(P)} trades, hit +5 {100 * P.y.mean():.1f}%, {P.usd.mean():+.2f} USD/trade,"
          f" {(P.usd / P.sl).mean():+.3f} R, {P.usd.sum():+.1f} USD, {len(P) / days:.2f}/day, months+ {(by_m > 0).sum()}/{len(by_m)}")


if __name__ == "__main__":
    main()
