"""TS rule study: the outcome of every trigger of triggers.csv (ts_dataset.py) on gold M1 bars, then which context
rules keep a positive R per trade in both halves of the year (walk-forward check, not a fit to one sample).

Outcome of one plan: entry at the decision bar's close (a BUY at the ask: close + spread), stop beyond the
pullback's extreme by ``buffer`` entry ATR plus the spread, target ``k`` R; the first M1 bar that reaches the stop
or the target decides (the stop first when one bar reaches both, as the backtest); after ``max_days`` the trade
closes at the bar's close. Triggers are independent here (no one-position limit): a screen, not a backtest.

usage: python ts_study.py data/backtests/ts/dataset_m15/triggers.csv [split YYYY-MM-DD]
"""

import os
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POINT = 0.01
GOAL = 0.15

trig = pd.read_csv(sys.argv[1], parse_dates=["time"])
split = pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else "2026-04-01", tz="UTC")
m1 = pd.read_parquet(ROOT / (os.environ.get("TS_HISTORY", "data/history") + "/FBS-Demo/XAUUSD/M1.parquet"), columns=["close_time", "high", "low", "close"])
t1 = m1["close_time"].to_numpy(dtype="datetime64[ns]")
hi, lo, cl = (m1[c].to_numpy(dtype=float) for c in ("high", "low", "close"))


def outcome(row: pd.Series, buffer: float, k: float, max_days: float = 3.0) -> float:
    buy = row.side == "BUY"
    spread = (row.spread_points if np.isfinite(row.spread_points) else 25.0) * POINT
    sign = 1 if buy else -1
    entry = row.close + (spread if buy else 0.0)
    stop = row.pivot - sign * (buffer * row.atr + spread)
    risk = (entry - stop) * sign
    if risk <= 0:
        return np.nan
    tp = entry + sign * k * risk
    start = np.searchsorted(t1, np.datetime64(row.time.tz_convert(None)), side="right")
    end = np.searchsorted(t1, np.datetime64((row.time + pd.Timedelta(days=max_days)).tz_convert(None)))
    if start >= len(t1) or end <= start:
        return np.nan
    h, lw = hi[start:end], lo[start:end]
    if buy:  # bid bars: the stop and the target (both already spread-adjusted for the exit side) on the bid
        sl_hit, tp_hit = lw <= stop, h >= tp
    else:  # a sell closes at the ask (bid + spread): stop when bid >= stop - spread, target when bid <= tp - spread
        sl_hit, tp_hit = h >= stop - spread, lw <= tp - spread
    first_sl = np.argmax(sl_hit) if sl_hit.any() else len(h)
    first_tp = np.argmax(tp_hit) if tp_hit.any() else len(h)
    if first_sl == len(h) and first_tp == len(h):
        last = cl[end - 1] - (0.0 if buy else -spread)
        return (last - entry) * sign / risk
    return -1.0 if first_sl <= first_tp else k


def hour_bucket(t: pd.Timestamp) -> str:
    h = t.hour
    return "asia(22-07)" if h >= 22 or h < 7 else "london(07-12)" if h < 12 else "ny(12-17)" if h < 17 else "late(17-22)"


trig["half"] = np.where(trig.time < split, "H1", "H2")
trig["session"] = trig.time.map(hour_bucket)
trig["stop_bin"] = pd.cut(trig.pivot_atr, [0, 1.5, 2.5, 3.5, 5, 99], labels=["<1.5", "1.5-2.5", "2.5-3.5", "3.5-5", ">5"])
loc = trig[["H1_pivot_dist", "H4_pivot_dist"]].min(axis=1)
trig["at_level"] = pd.cut(loc, [-1, 0.25, 0.5, 1.0, 99], labels=["<=0.25", "0.25-0.5", "0.5-1", ">1"])
sign = np.where(trig.side == "BUY", 1, -1)
risk_guess = trig.pivot_atr * trig.atr  # about the stop distance
room = (trig.H4_ahead - trig.close) * sign / risk_guess
trig["h4_room"] = pd.cut(room, [-99, 1, 2, 3, 999], labels=["<1R", "1-2R", "2-3R", ">3R"]).astype(str)

PLANS = {f"b{b}_k{k}": (b, k) for b in (0.25, 0.5) for k in (1.0, 1.5, 2.0, 3.0)}
for name, (b, k) in PLANS.items():
    trig[name] = [outcome(r, b, k) for r in trig.itertuples()]
trig.to_csv(Path(sys.argv[1]).with_name("outcomes.csv"), index=False)

FEATURES = ["side", "kind", "h4_map", "h4_swings", "h1_map", "h1_swings", "session", "stop_bin", "at_level", "h4_room"]
months = max(1.0, (trig.time.max() - trig.time.min()).days / 30.4)
print(f"{len(trig)} triggers, {trig.time.min():%Y-%m-%d} .. {trig.time.max():%Y-%m-%d}, split {split:%Y-%m-%d}")
print("all triggers, per plan (R/trade all | H1 | H2):")
for name in PLANS:
    s = trig[name]
    print(f"  {name:9} {s.mean():+.3f} | {s[trig.half == 'H1'].mean():+.3f} | {s[trig.half == 'H2'].mean():+.3f}")


def stats(mask: pd.Series, plan: str) -> tuple[int, float, float, float]:
    s = trig.loc[mask, plan]
    return len(s), s.mean(), s[trig.half[mask] == "H1"].mean(), s[trig.half[mask] == "H2"].mean()


BASE = "b0.5_k2.0"
print(f"\none feature at a time ({BASE}): value n R | H1 | H2")
for f in FEATURES:
    for v, _ in trig.groupby(f, observed=True):
        n, r, a, b = stats(trig[f] == v, BASE)
        if n >= 20:
            print(f"  {f:10} {str(v):14} {n:5d} {r:+.3f} | {a:+.3f} | {b:+.3f}")

print(f"\nrules of 1-3 conditions, n >= 40, both halves >= +{GOAL} (best 25 by the weaker half), any plan:")
values = [(f, v) for f in FEATURES for v in trig[f].dropna().unique()]
found = []
for size in (1, 2, 3):
    for combo in itertools.combinations(values, size):
        if len({f for f, _ in combo}) < size:
            continue
        mask = np.logical_and.reduce([trig[f] == v for f, v in combo])
        if mask.sum() < 40:
            continue
        for plan in PLANS:
            n, r, a, b = stats(pd.Series(mask, index=trig.index), plan)
            if a >= GOAL and b >= GOAL:
                found.append((min(a, b), n, r, a, b, plan, combo))
found.sort(key=lambda x: (-x[0], -x[1]))
for weak, n, r, a, b, plan, combo in found[:25]:
    rule = " & ".join(f"{f}={v}" for f, v in combo)
    print(f"  {r:+.3f} (H1 {a:+.3f}, H2 {b:+.3f}) n {n:4d} ({n / months:4.1f}/month) {plan:9} {rule}")
print(f"({len(found)} rule/plan pairs pass)")
