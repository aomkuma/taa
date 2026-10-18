"""Round 2 analysis: Haiku's p_buy / p_sell on the clear-signal moments (F1's C4 passes) against the answer key.
Written before looking: the score is p(the base side) - p(the other side), the original and the flipped image
averaged (the flipped answer mapped back); the question is whether a higher score means a better base-side R.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ai_charts/analyze_prob.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

parts = []
for sfx in ("_c4", "_c4w"):
    d = Path(f"data/research/ai_charts{sfx}")
    m = pd.read_parquet(d / "manifest.parquet")
    a = pd.DataFrame([json.loads(x) for x in (d / "answers_prob_claude-haiku-4-5.jsonl").read_text(encoding="utf-8").splitlines()])
    a = a.dropna(subset=["p_buy", "p_sell"]).drop_duplicates(["id", "flip"], keep="last")
    o = a[~a.flip].set_index("id")[["p_buy", "p_sell"]]
    f = a[a.flip].set_index("id")[["p_buy", "p_sell"]].rename(columns={"p_buy": "f_sell", "p_sell": "f_buy"})  # mirrored
    x = m.set_index("id").join(o).join(f)
    x["set"] = "design" if sfx == "_c4" else "window"
    x["cost"] = a.cost.sum()
    parts.append(x)
X = pd.concat(parts)
s = X.base_side.to_numpy()
X["R"] = np.where(s > 0, X.R_buy, X.R_sell)
X["usd"] = np.where(s > 0, X.usd_buy, X.usd_sell)
X["win"] = np.where(s > 0, X.exit_buy, X.exit_sell) == "win"
X["score_o"] = np.where(s > 0, X.p_buy - X.p_sell, X.p_sell - X.p_buy)
X["score_f"] = np.where(s > 0, X.f_buy - X.f_sell, X.f_sell - X.f_buy)
X["score"] = X[["score_o", "score_f"]].mean(axis=1)
print(f"moments {len(X)} (design {sum(X.set == 'design')}, window {sum(X.set == 'window')}); answered "
      f"{X.p_buy.notna().sum()} originals, {X.f_buy.notna().sum()} flips; cost {sum(p.cost.iloc[0] for p in parts):.3f} USD")
pairs = X.dropna(subset=["p_buy", "f_buy"])
print(f"flip consistency (the favoured side mirrors): {np.mean(np.sign(pairs.p_buy - pairs.p_sell) == np.sign(pairs.f_buy - pairs.f_sell)):.0%}")
print("distinct (p_buy, p_sell) answers:", X.dropna(subset=['p_buy']).groupby(['p_buy', 'p_sell']).size().sort_values(ascending=False).head(8).to_dict())
print(f"the AI favours the base side: {np.mean(X.score_o > 0):.0%} of originals")
print(f"rank correlation score vs R: {X[['score', 'R']].corr('spearman').iloc[0, 1]:+.3f}")
for st, g in [("all", X), *X.groupby("set")]:
    print(f"\n{st}: base side R {g.R.mean():+.3f} on {len(g)}")
    for lab, msk in (("AI agrees (score > 0)", g.score > 0), ("AI unsure / against (score <= 0)", g.score <= 0)):
        h = g[msk]
        print(f"  {lab:34} {len(h):3}  win {h.win.mean():4.0%}  R {h.R.mean():+.3f}  USD {h.usd.sum():+7.1f}")
    q = g.score.rank(pct=True)
    for lab, msk in (("top third of score", q > 2 / 3), ("middle third", (q > 1 / 3) & (q <= 2 / 3)), ("bottom third", q <= 1 / 3)):
        h = g[msk]
        print(f"  {lab:34} {len(h):3}  win {h.win.mean():4.0%}  R {h.R.mean():+.3f}  score {h.score.min():+.0f}..{h.score.max():+.0f}")
