"""Why does setup_breakout lose? Read-only diagnosis over the one-year replay (PLAN variant shadow trades).

1. Timing: re-simulate each signal on M5 bars with the same stop and target, entering at market (sanity check
   against the replay) or with a limit that waits for a pullback (retest) of k x ATR for W entry bars.
2. Context: the market-entry result split by conditions measured at the signal bar (M15).
All results are hypothetical, bar-based (same-bar stop and target: stop first), net of the replay's costs.
"""

import glob
import json
import random
import sqlite3
import statistics
from collections import defaultdict
from datetime import timedelta

import numpy as np
import pandas as pd

S = str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'data' / 'research')
H = str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'data' / 'history' / 'FBS-Demo')
STRATEGY = "setup_breakout"
HORIZON = timedelta(hours=72)
random.seed(7)

trades = []
for path in sorted(glob.glob(f"{S}/fam_light_*.db")):
    db = sqlite3.connect(path)
    q = (
        "select symbol, side, signal_at, entry_price, initial_sl, tp, atr, spread_points, session, setup_strength, "
        "r_multiple, r_net, features from shadow_trades where status='CLOSED' and variant='PLAN' and strategy=?"
    )
    for row in db.execute(q, (STRATEGY,)):
        trades.append(dict(zip(
            ["symbol", "side", "t", "entry", "sl", "tp", "atr", "spread", "session", "strength", "r", "r_net", "features"],
            row,
        )))
print(f"{STRATEGY}: {len(trades)} closed replay trades")

m5, m15, point = {}, {}, {}
for sym in {t["symbol"] for t in trades}:
    point[sym] = json.load(open(f"{H}/{sym}/spec.json"))["spec"]["point"]
    a = pd.read_parquet(f"{H}/{sym}/M5.parquet")
    a = a.set_index(pd.DatetimeIndex(a["open_time"])).sort_index()
    m5[sym] = a
    b = pd.read_parquet(f"{H}/{sym}/M15.parquet")
    b = b.set_index(pd.DatetimeIndex(b["close_time"])).sort_index()
    prev = b["close"].shift()
    tr = pd.concat([b["high"] - b["low"], (b["high"] - prev).abs(), (b["low"] - prev).abs()], axis=1).max(axis=1)
    b["atr"] = tr.rolling(14).mean()
    b["atr_pct"] = b["atr"].rolling(200).rank(pct=True)
    b["ema20"] = b["close"].ewm(span=20, adjust=False).mean()
    mid = b["close"].rolling(20).mean()
    b["bbw"] = 4 * b["close"].rolling(20).std() / mid
    b["bbw_pct"] = b["bbw"].shift(1).rolling(200).rank(pct=True)  # compression before the signal bar
    b["range20"] = (b["high"].rolling(20).max() - b["low"].rolling(20).min()).shift(1)
    m15[sym] = b


def simulate(tr: dict, fill_limit: float | None, wait_bars: int) -> float | None:
    """R of one trade; fill_limit None = market at the signal's entry. None = the limit never filled."""
    bars = m5[tr["symbol"]]
    t0 = pd.Timestamp(tr["t"]).tz_localize("UTC") if pd.Timestamp(tr["t"]).tzinfo is None else pd.Timestamp(tr["t"])
    path = bars.loc[t0 : t0 + HORIZON]
    if path.empty:
        return None
    hi, lo, cl = path["high"].to_numpy(), path["low"].to_numpy(), path["close"].to_numpy()
    sp = (tr["spread"] or 0) * point[tr["symbol"]]
    buy = tr["side"] == "BUY"
    sl, tp = tr["sl"], tr["tp"]
    start = 0
    fill = tr["entry"]
    if fill_limit is not None:
        window = min(len(path), wait_bars * 3)  # M15 bars -> M5 bars
        if buy:
            touched = np.nonzero(lo[:window] + sp <= fill_limit)[0]
            stopped = np.nonzero(lo[:window] <= sl)[0]
        else:
            touched = np.nonzero(hi[:window] >= fill_limit)[0]
            stopped = np.nonzero(hi[:window] + sp >= sl)[0]
        if len(touched) == 0 or (len(stopped) and stopped[0] < touched[0]):
            return None
        start, fill = int(touched[0]), fill_limit
    risk = abs(fill - sl)
    if risk <= 0:
        return None
    h, low = hi[start:], lo[start:]
    if buy:
        hit_sl, hit_tp = np.nonzero(low <= sl)[0], np.nonzero(h >= tp)[0]
    else:
        hit_sl, hit_tp = np.nonzero(h + sp >= sl)[0], np.nonzero(low + sp <= tp)[0]
    i_sl = hit_sl[0] if len(hit_sl) else 10**9
    i_tp = hit_tp[0] if len(hit_tp) else 10**9
    cost_r = (tr["r"] - tr["r_net"]) * abs(tr["entry"] - sl) / risk
    if i_sl == i_tp == 10**9:  # time stop at the horizon
        exit_price = cl[-1] - (0 if buy else -sp)
        return (exit_price - fill) / risk * (1 if buy else -1) - cost_r
    if i_sl <= i_tp:
        return -1.0 - cost_r
    return abs(tp - fill) / risk - cost_r


def summary(label: str, values: list[float], signals: int) -> None:
    if not values:
        print(f"{label:40} filled 0")
        return
    means = sorted(statistics.fmean(random.choices(values, k=len(values))) for _ in range(1000))
    print(
        f"{label:40} filled {len(values):4d}/{signals} ({100 * len(values) / signals:3.0f}%) "
        f"win {100 * sum(v > 0 for v in values) / len(values):3.0f}% meanR {statistics.fmean(values):+.3f} "
        f"90%CI[{means[50]:+.2f},{means[949]:+.2f}] totalR {sum(values):+.0f}"
    )


print("\n=== 1. timing: market entry vs waiting for a retest (same stop and target) ===")
base = [simulate(tr, None, 0) for tr in trades]
pairs = [(b, tr["r_net"]) for b, tr in zip(base, trades) if b is not None]
print(f"sanity: my market re-simulation vs the replay: corr {np.corrcoef(*zip(*pairs))[0, 1]:.2f}, "
      f"mean {statistics.fmean(p[0] for p in pairs):+.3f} vs {statistics.fmean(p[1] for p in pairs):+.3f}")
summary("market (as now)", [b for b in base if b is not None], len(trades))
for k in (0.25, 0.5, 0.75, 1.0):
    for wait in (4, 8, 16):
        res = []
        for tr in trades:
            sign = 1 if tr["side"] == "BUY" else -1
            limit = tr["entry"] - sign * k * tr["atr"]
            if (limit - tr["sl"]) * sign <= 0:  # the pullback would reach the stop
                continue
            r = simulate(tr, limit, wait)
            if r is not None:
                res.append(r)
        summary(f"retest {k:.2f} ATR within {wait} bars", res, len(trades))

print("\n=== 2. context of the market entries (replay result, net) ===")
rows = []
for tr in trades:
    b = m15[tr["symbol"]]
    t = pd.Timestamp(tr["t"]).tz_localize("UTC") if pd.Timestamp(tr["t"]).tzinfo is None else pd.Timestamp(tr["t"])
    if t not in b.index:
        continue
    bar = b.loc[t]
    sign = 1 if tr["side"] == "BUY" else -1
    atr = bar["atr"]
    if not atr or np.isnan(atr):
        continue
    body = (bar["close"] - bar["open"]) * sign / atr
    rng = (bar["high"] - bar["low"]) / atr
    close_loc = ((bar["close"] - bar["low"]) / (bar["high"] - bar["low"])) if bar["high"] > bar["low"] else 0.5
    close_loc = close_loc if sign > 0 else 1 - close_loc
    feats = json.loads(tr["features"] or "{}")
    rows.append({
        "r": tr["r_net"],
        "session": tr["session"],
        "hour": t.hour,
        "stop_atr": abs(tr["entry"] - tr["sl"]) / atr,
        "bar_range_atr": rng,
        "bar_body_atr": body,
        "close_at_extreme": close_loc,
        "stretch_ema20_atr": (bar["close"] - bar["ema20"]) * sign / atr,
        "atr_pct": bar["atr_pct"],
        "squeeze_before_pct": bar["bbw_pct"],
        "range20_atr": bar["range20"] / atr,
        "htf_aligned": feats.get("ctx:htf_aligned", 0.0),
        "regime_trending": feats.get("ctx:regime=TRENDING", 0.0),
        "strength": tr["strength"],
        "rr": abs(tr["tp"] - tr["entry"]) / abs(tr["entry"] - tr["sl"]),
    })
df = pd.DataFrame(rows)
print(f"trades with context: {len(df)}  overall meanR {df['r'].mean():+.3f}")
for col in ["session", "htf_aligned", "regime_trending"]:
    g = df.groupby(col)["r"].agg(["count", "mean"])
    print(f"\n{col}:\n{g.round(3).to_string()}")
for col in ["hour"]:
    g = df.groupby(pd.cut(df[col], [0, 6, 9, 12, 15, 18, 21, 24], right=False))["r"].agg(["count", "mean"])
    print(f"\n{col} (UTC):\n{g.round(3).to_string()}")
for col in ["stop_atr", "bar_range_atr", "bar_body_atr", "close_at_extreme", "stretch_ema20_atr", "atr_pct",
            "squeeze_before_pct", "range20_atr", "strength", "rr"]:
    q = pd.qcut(df[col], 4, duplicates="drop")
    g = df.groupby(q, observed=True)["r"].agg(["count", "mean"])
    print(f"\n{col} quartiles:\n{g.round(3).to_string()}")
df.to_csv(f"{S}/breakout_context.csv", index=False)
