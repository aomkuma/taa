"""AI chart reader pilot: the answers against the answer key and the controls (docs/AI_CHART_READER.md).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/ai_charts/analyze.py answers_<model>.jsonl
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DIR = Path("data/research/ai_charts" + __import__("os").environ.get("AI_CHARTS_SUFFIX", ""))
man = pd.read_parquet(DIR / "manifest.parquet")
a = pd.DataFrame([json.loads(x) for x in (DIR / sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()])
o = a[~a.flip].set_index("id")
f = a[a.flip].set_index("id")
d = man.set_index("id").join(o[["decision", "confidence"]]).join(f[["decision"]].rename(columns={"decision": "flip_dec"}))
mirror = {"BUY": "SELL", "SELL": "BUY", "NONE": "NONE"}
d["flip_back"] = d.flip_dec.map(mirror)
print(f"answers {len(a)}, cost {a.get('cost', pd.Series(dtype=float)).sum():.2f} USD, errors {a.decision.isna().sum()}")
print("decisions (original):", d.decision.value_counts().to_dict(), "| flipped:", d.flip_dec.value_counts().to_dict())
both = d.dropna(subset=["decision", "flip_dec"])
print(f"flip consistency (the flipped answer is the mirror): {np.mean(both.decision == both.flip_back):.0%}")


def r_of(dec, row_buy, row_sell):
    return np.where(dec == "BUY", row_buy, np.where(dec == "SELL", row_sell, np.nan))


for kind in ("base", "random"):
    x = d[d.kind == kind]
    ai = r_of(x.decision, x.R_buy, x.R_sell)
    fb = r_of(x.flip_back, x.R_buy, x.R_sell)
    usd = r_of(x.decision, x.usd_buy, x.usd_sell)
    taken = ~np.isnan(ai)
    print(f"\n{kind}: {len(x)} moments; the AI trades {taken.sum()} (BUY {np.sum(x.decision == 'BUY')}, SELL {np.sum(x.decision == 'SELL')})")
    print(f"  AI's trades: R {np.nanmean(ai):+.3f}, USD {np.nansum(usd):+.1f}, win {np.nanmean(np.where(taken, r_of(x.decision, x.exit_buy, x.exit_sell) == 'win', np.nan)):.0%}")
    print(f"  the flipped chart's answer (mapped back): R {np.nanmean(fb):+.3f} on {np.sum(~np.isnan(fb))}")
    print(f"  the coin on the AI's minutes: R {np.nanmean(np.where(taken, (x.R_buy + x.R_sell) / 2, np.nan)):+.3f}")
    if kind == "base":
        follow = np.where(x.base_side > 0, x.R_buy, x.R_sell)
        print(f"  every base signal with the base side: R {follow.mean():+.3f}; the AI agreeing with the base side:"
              f" {np.sum((x.decision == 'BUY') & (x.base_side > 0) | (x.decision == 'SELL') & (x.base_side < 0))} trades,"
              f" R {np.nanmean(np.where(((x.decision == 'BUY') & (x.base_side > 0)) | ((x.decision == 'SELL') & (x.base_side < 0)), follow, np.nan)):+.3f}")
    for lo, hi in ((0, 60), (60, 75), (75, 101)):
        m = taken & (x.confidence.fillna(0) >= lo).to_numpy() & (x.confidence.fillna(0) < hi).to_numpy()
        if m.sum():
            print(f"  confidence {lo}-{hi - 1}: {m.sum()} trades, R {np.nanmean(ai[m]):+.3f}")
