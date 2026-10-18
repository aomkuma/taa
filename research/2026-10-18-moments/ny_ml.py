"""Round 7, iteration 6 (docs/OWN_SETUP_ROUNDS.md): New York iteration 1 with the direction screened by a LightGBM score,
fitted walk-forward on everything before each window. Runs in data/venv-research:

    data/venv-research/Scripts/python research/2026-10-18-moments/ny_ml.py [--test]
"""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

sys.path.insert(0, "research/2026-10-18-moments")
from ny_lab import DEV, ITER, SLIP, TEST, M1, select  # noqa: E402

PARAMS = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=300, subsample=0.7,
              subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0, random_state=7, verbose=-1)


def main() -> None:
    warnings.filterwarnings("ignore")
    test = "--test" in sys.argv
    plan = ITER["1"]
    d = pd.read_parquet("data/research/own_ml_long.parquet")
    lab = pd.read_parquet("data/research/own_ml_arsenal_labels.parquet", columns=["y_8_6"])
    d = pd.concat([d, lab], axis=1)
    d["t"] = pd.to_datetime(d.t, utc=True)
    meta = {"t", "e", "mfe", "side", "y_8_6"} | {c for c in d.columns if c[:1] in ("y", "u", "m") and c[1:2].isdigit()}
    meta |= {c for c in d.columns if c.startswith(("usd", "min"))}
    feats = [c for c in d.columns if c not in meta]
    P = M1()
    rule = plan["rule"](d) & (d.session == 2)
    print(f"features {len(feats)}")
    print("  window                trades /day  win%  USD/trade    R    USD (0.01 lot) months+ | without the score")
    for name, a, b, scale in (TEST if test else DEV):
        a_t, b_t = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
        train = d[(d.t < a_t) & (d.y_8_6 >= 0)]
        win = d[(d.t >= a_t) & (d.t < b_t) & rule]
        if len(train) < 50_000:
            print(f"  {name:20} skipped (no earlier data)")
            continue
        m = LGBMClassifier(**PARAMS).fit(train[feats], (train.y_8_6 == 1).astype(int))
        cut = float(np.median(m.predict_proba(train.loc[rule[train.index], feats])[:, 1]))
        p = m.predict_proba(win[feats])[:, 1]
        r = select(win[p >= cut], P, plan, scale)
        r0 = select(win, P, plan, scale)
        days = pd.bdate_range(a, b).size
        by_m = r.usd.groupby(r.t.dt.strftime("%Y-%m")).sum()
        v = r.kind[r.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
        print(f"  {name:20} {len(r):5} {len(r) / days:4.2f} {100 * (r.exit == 'win').mean():4.0f}  {r.usd.mean():+8.2f}"
              f"  {(r.usd / (r.sl + SLIP)).mean():+.3f}  {r.usd.sum():+9.1f}   {(by_m > 0).sum()}/{len(by_m)}"
              f"   | {r0.usd.sum():+.1f} ({len(r0)})  kinds {100 * v['1']:.0f}/{100 * v['2']:.0f}/{100 * v['3']:.0f}%")


if __name__ == "__main__":
    main()
