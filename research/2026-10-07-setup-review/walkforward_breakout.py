"""Which breakouts follow through and which fail? Context x direction, then an honest walk-forward check:
conditions are chosen on Oct-Mar only and measured on Apr-Oct (read-only, hypothetical, net of costs)."""

import random
import statistics
import sys

import numpy as np
import pandas as pd

sys.argv = sys.argv[:1]
src = open(__file__.replace("walkforward_breakout.py", "diagnose_breakout.py"), encoding="utf-8").read()
exec(src.split('print("\\n=== 1. timing')[0])
exec(open(__file__.replace("walkforward_breakout.py", "baseline_breakout.py"), encoding="utf-8").read().split(
    "as_is, fade, coin")[0].split("random.seed(11)")[1])

rows = []
for tr in trades:
    b = m15[tr["symbol"]]
    t = pd.Timestamp(tr["t"]).tz_localize("UTC") if pd.Timestamp(tr["t"]).tzinfo is None else pd.Timestamp(tr["t"])
    if t not in b.index:
        continue
    bar = b.loc[t]
    atr = bar["atr"]
    if not atr or np.isnan(atr):
        continue
    sign = 1 if tr["side"] == "BUY" else -1
    r, f = simulate(tr, None, 0), simulate(mirrored(tr), None, 0)
    if r is None or f is None:
        continue
    hl = bar["high"] - bar["low"]
    loc = (bar["close"] - bar["low"]) / hl if hl > 0 else 0.5
    rows.append({
        "half": "train" if str(tr["t"]) < "2026-04-01" else "test",
        "symbol": tr["symbol"], "r": r, "fade": f,
        "hour": t.hour,
        "stop_atr": abs(tr["entry"] - tr["sl"]) / atr,
        "bar_range_atr": hl / atr,
        "close_at_extreme": loc if sign > 0 else 1 - loc,
        "stretch_ema20_atr": (bar["close"] - bar["ema20"]) * sign / atr,
        "atr_pct": bar["atr_pct"],
        "squeeze_before_pct": bar["bbw_pct"],
        "range20_atr": bar["range20"] / atr,
        "htf_aligned": float(__import__("json").loads(tr["features"] or "{}").get("ctx:htf_aligned", 0.0)),
    })
df = pd.DataFrame(rows).dropna()
train, test = df[df.half == "train"], df[df.half == "test"]
print(f"rows {len(df)}: train (Oct-Mar) {len(train)}, test (Apr-Oct) {len(test)}")

features = ["hour", "stop_atr", "bar_range_atr", "close_at_extreme", "stretch_ema20_atr", "atr_pct",
            "squeeze_before_pct", "range20_atr", "htf_aligned"]

print("\n=== follow-through vs failure by context (all months): breakout R | fade R ===")
for col in features:
    q = pd.qcut(df[col], 4, duplicates="drop") if df[col].nunique() > 4 else df[col]
    g = df.groupby(q, observed=True).agg(n=("r", "size"), breakout=("r", "mean"), fade=("fade", "mean"))
    print(f"\n{col}:\n{g.round(3).to_string()}")


def ci(values: pd.Series) -> str:
    v = list(values)
    if len(v) < 10:
        return "n<10"
    means = sorted(statistics.fmean(random.choices(v, k=len(v))) for _ in range(1000))
    return f"{statistics.fmean(v):+.3f} [{means[50]:+.2f},{means[949]:+.2f}] n={len(v)}"


print("\n=== walk-forward: the best single-condition rules chosen on TRAIN, measured on TEST ===")
candidates = []
for col in features:
    edges = np.unique(np.quantile(train[col], [0.25, 0.5, 0.75]))
    for e in edges:
        for side in ("<=", ">"):
            mask_tr = train[col] <= e if side == "<=" else train[col] > e
            for direction in ("r", "fade"):
                sub = train.loc[mask_tr, direction]
                if len(sub) >= 200:
                    candidates.append((sub.mean(), col, side, e, direction))
candidates.sort(reverse=True)
for score, col, side, e, direction in candidates[:8]:
    mask_te = test[col] <= e if side == "<=" else test[col] > e
    label = f"{'breakout' if direction == 'r' else 'fade':8} {col} {side} {e:.2f}"
    print(f"{label:45} train {score:+.3f}  ->  test {ci(test.loc[mask_te, direction])}")
print(f"\nreference on TEST: breakout {ci(test['r'])}   fade {ci(test['fade'])}")
