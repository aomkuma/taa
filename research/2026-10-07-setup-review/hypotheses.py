"""Many hypotheses about why the light-family setups lose, each tested on every signal of the one-year replay by
re-simulating it on M5 bars (read-only, hypothetical; bid bars, the spread on the ask side; a bar that reaches
both the stop and another level counts as the stop first). Every row: mean R [90 % CI] all / train (Oct-Mar) /
test (Apr-Oct), so a rule that only fits one half shows up.

usage: python hypotheses.py STRATEGY ["fam_light_*"]   (the second argument picks the replay databases)
"""

import glob
import json
import random
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import timedelta

import numpy as np
import pandas as pd

S = str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'data' / 'research')
H = str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'data' / 'history' / 'FBS-Demo')
STRATEGY = sys.argv[1] if len(sys.argv) > 1 else "setup_breakout"
HORIZON = timedelta(hours=72)
random.seed(5)

trades = []
for path in sorted(glob.glob(f"{S}/{sys.argv[2] if len(sys.argv) > 2 else 'fam_light_*'}.db")):
    q = ("select symbol, side, signal_at, entry_price, initial_sl, tp, atr, spread_points, features, r_net "
         "from shadow_trades where status='CLOSED' and variant='PLAN' and strategy=?")
    for row in sqlite3.connect(path).execute(q, (STRATEGY,)):
        trades.append(dict(zip(["symbol", "side", "t", "entry", "sl", "tp", "atr", "spread", "features", "r_net"], row)))
trades.sort(key=lambda x: (x["symbol"], x["t"]))
print(f"{STRATEGY}: {len(trades)} signals")

bars, m15, point = {}, {}, {}
for sym in {t["symbol"] for t in trades}:
    point[sym] = json.load(open(f"{H}/{sym}/spec.json"))["spec"]["point"]
    a = pd.read_parquet(f"{H}/{sym}/M5.parquet")
    bars[sym] = a.set_index(pd.DatetimeIndex(a["open_time"])).sort_index()
    b = pd.read_parquet(f"{H}/{sym}/M15.parquet")
    b = b.set_index(pd.DatetimeIndex(b["close_time"])).sort_index()
    b["ema20"] = b["close"].ewm(span=20, adjust=False).mean()
    m15[sym] = b


def ts(value: str) -> pd.Timestamp:
    t = pd.Timestamp(value)
    return t.tz_localize("UTC") if t.tzinfo is None else t


# path of each trade in units of its original risk: favourable and adverse excursion per M5 bar, and the close
for tr in trades:
    path = bars[tr["symbol"]].loc[ts(tr["t"]) : ts(tr["t"]) + HORIZON]
    risk = abs(tr["entry"] - tr["sl"])
    sp = (tr["spread"] or 0) * point[tr["symbol"]]
    if tr["side"] == "BUY":
        fav = (path["high"].to_numpy() - tr["entry"]) / risk
        adv = (path["low"].to_numpy() - tr["entry"]) / risk
        close = (path["close"].to_numpy() - tr["entry"]) / risk
    else:
        fav = (tr["entry"] - (path["low"].to_numpy() + sp)) / risk
        adv = (tr["entry"] - (path["high"].to_numpy() + sp)) / risk
        close = (tr["entry"] - (path["close"].to_numpy() + sp)) / risk
    tr.update(fav=fav, adv=adv, close=close, target=abs(tr["tp"] - tr["entry"]) / risk,
              cost_share=sp / risk, half="train" if str(tr["t"]) < "2026-04-01" else "test")


def run(tr: dict, *, tp=None, tp_scale=1.0, sl_mult=1.0, be_at=None, be_to=0.0, partial=None, trail=None,
        time_bars=None) -> float:
    """Exit rules in units of the ORIGINAL risk; the result is in R of the trade's risk (sl_mult x original)."""
    target = (tr["target"] if tp is None else tp) * tp_scale
    stop = -sl_mult
    taken, best, rest = 0.0, 0.0, 1.0
    fav, adv, close = tr["fav"], tr["adv"], tr["close"]
    for i in range(len(fav)):
        if adv[i] <= stop:
            return (taken + rest * stop) / sl_mult
        if partial is not None and rest == 1.0 and fav[i] >= partial[1]:
            taken, rest = partial[0] * partial[1], 1.0 - partial[0]
        if fav[i] >= target:
            return (taken + rest * target) / sl_mult
        best = max(best, fav[i])
        if be_at is not None and best >= be_at:
            stop = max(stop, be_to)
        if trail is not None and best >= trail[0]:
            stop = max(stop, best - trail[1])
        if time_bars is not None and i + 1 >= time_bars * 3 and best < 0.5:
            return (taken + rest * close[i]) / sl_mult
    return (taken + rest * close[-1]) / sl_mult if len(close) else 0.0


def ci(values: list[float]) -> str:
    if len(values) < 20:
        return f"n={len(values)}"
    means = sorted(statistics.fmean(random.choices(values, k=len(values))) for _ in range(600))
    return f"{statistics.fmean(values):+.3f} [{means[30]:+.2f},{means[569]:+.2f}]"


def line(label: str, pick=lambda tr: True, **rules) -> None:
    sel = [tr for tr in trades if pick(tr) and len(tr["fav"])]
    res = [(tr["half"], run(tr, **rules)) for tr in sel]
    tr_ = [r for h, r in res if h == "train"]
    te_ = [r for h, r in res if h == "test"]
    print(f"  {label:46} n={len(res):4d} all {ci([r for _, r in res]):24} train {ci(tr_):24} test {ci(te_)}")


print("\n=== what happened to the losers (as traded) ===")
base = [(tr, run(tr)) for tr in trades if len(tr["fav"])]
losers = [tr for tr, r in base if r < 0]
def best_before_stop(tr: dict) -> float:
    hit = np.nonzero(tr["adv"] <= -1)[0]
    end = int(hit[0]) if len(hit) else len(tr["fav"])
    return float(np.max(tr["fav"][:end])) if end > 0 else 0.0


best = [best_before_stop(tr) for tr in losers]
print(f"  losers: {len(losers)} of {len(base)}")
for x in (0.25, 0.5, 0.75, 1.0, 1.5):
    print(f"  losers that were at +{x}R before going to -1R: {100 * sum(b >= x for b in best) / len(best):3.0f}%")
mfe = [float(np.max(tr["fav"])) for tr, _ in base]
print("  MFE percentiles over the whole horizon (R):",
      ", ".join(f"p{p}={np.percentile(mfe, p):.2f}" for p in (25, 50, 75, 90)))

print("\n=== A. exits ===")
line("A0 as traded (own target, fixed stop)")
for x in (0.5, 0.75, 1.0, 1.5):
    line(f"A1 target {x} R", tp=x)
for x in (0.5, 0.75, 1.0):
    line(f"A2 break-even after +{x} R", be_at=x, be_to=0.05)
line("A2 stop to -0.5 R after +0.5 R", be_at=0.5, be_to=-0.5)
line("A3 half off at +1 R, rest to target", partial=(0.5, 1.0))
line("A3 half off at +0.5 R, rest to target", partial=(0.5, 0.5))
line("A4 trail 1 R once +1 R", trail=(1.0, 1.0))
line("A4 trail 0.5 R once +0.5 R", trail=(0.5, 0.5))
for n in (4, 8, 16):
    line(f"A5 time stop {n} bars if not +0.5 R", time_bars=n)

print("\n=== B. stop size and costs ===")
for m in (1.5, 2.0):
    line(f"B1 stop x{m}, same target price", sl_mult=m)
    line(f"B1 stop x{m}, same R multiple", sl_mult=m, tp_scale=m)
cs = np.quantile([tr["cost_share"] for tr in trades], [0.25, 0.5, 0.75])
line(f"B2 spread <= {cs[0]:.2f} of the stop (cheapest quarter)", pick=lambda tr: tr["cost_share"] <= cs[0])
line(f"B2 spread >= {cs[2]:.2f} of the stop (dearest quarter)", pick=lambda tr: tr["cost_share"] >= cs[2])

print("\n=== C. where and when the entry is ===")


def m15_at(tr: dict) -> pd.Series | None:
    t = ts(tr["t"])
    b = m15[tr["symbol"]]
    return b.loc[t] if t in b.index else None


for tr in trades:
    bar = m15_at(tr)
    sign = 1 if tr["side"] == "BUY" else -1
    tr["stretch"] = (bar["close"] - bar["ema20"]) * sign / tr["atr"] if bar is not None and tr["atr"] else np.nan
    tr["bar_atr"] = (bar["high"] - bar["low"]) / tr["atr"] if bar is not None and tr["atr"] else np.nan
    tr["weekday"] = ts(tr["t"]).weekday()
seen = defaultdict(set)
for tr in trades:
    day = (tr["symbol"], ts(tr["t"]).date())
    tr["first_of_day"] = day not in seen["d"]
    seen["d"].add(day)
for lo, hi in ((-9, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 99)):
    line(f"C1 entry {lo:g}..{hi:g} ATR beyond EMA20", pick=lambda tr, lo=lo, hi=hi: lo < tr["stretch"] <= hi)
for lo, hi in ((0, 1.0), (1.0, 2.0), (2.0, 99)):
    line(f"C1 signal bar {lo:g}..{hi:g} ATR long", pick=lambda tr, lo=lo, hi=hi: lo < tr["bar_atr"] <= hi)
line("C2 first signal of the day on the symbol", pick=lambda tr: tr["first_of_day"])
line("C2 later signals of the day", pick=lambda tr: not tr["first_of_day"])
for d, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
    line(f"C3 {name}", pick=lambda tr, d=d: tr["weekday"] == d)
line("C3 BUY", pick=lambda tr: tr["side"] == "BUY")
line("C3 SELL", pick=lambda tr: tr["side"] == "SELL")


print("\n=== D. 'breaks out, comes back to the entry, then really runs' ===")
vind = 0
for tr in losers:
    hit = np.nonzero(tr["adv"] <= -1)[0]
    if len(hit) and np.any(tr["fav"][hit[0] + 1 :] >= tr["target"]):
        vind += 1
print(f"  D1 stopped trades whose ORIGINAL target was reached later (within 72 h): {100 * vind / len(losers):.0f}%")


def run_retest(tr: dict, depth: float, stop: float, wait_bars: int, tp_scale: float = 1.0) -> float | None:
    """A limit `depth` original risks against the signal, valid `wait_bars` M15 bars; stop at `stop` (original
    units, from the signal's entry); target the signal's target x tp_scale. None: never filled."""
    fav, adv, close = tr["fav"], tr["adv"], tr["close"]
    window = min(len(adv), wait_bars * 3)
    touched = np.nonzero(adv[:window] <= -depth)[0]
    if len(touched) == 0:
        return None
    i0 = int(touched[0])
    risk = stop - depth
    target = tr["target"] * tp_scale
    for i in range(i0, len(fav)):
        if adv[i] <= -stop:
            return -1.0
        if i > i0 and fav[i] >= target:
            return (target + depth) / risk
    return (close[-1] + depth) / risk


def run_reentry(tr: dict, within_bars: int) -> float:
    """As traded; if stopped, enter again when price comes back to the entry within `within_bars` M15 bars."""
    first = run(tr)
    hit = np.nonzero(tr["adv"] <= -1)[0]
    if first > -0.99 or not len(hit):
        return first
    j0 = int(hit[0]) + 1
    back = np.nonzero(tr["fav"][j0 : j0 + within_bars * 3] >= 0)[0]
    if not len(back):
        return first
    k = j0 + int(back[0])
    second = {**tr, "fav": tr["fav"][k:] , "adv": tr["adv"][k:], "close": tr["close"][k:]}
    return first + run(second)


def line2(label: str, fn) -> None:
    res = [(tr["half"], fn(tr)) for tr in trades if len(tr["fav"])]
    filled = [(h, r) for h, r in res if r is not None]
    tr_ = [r for h, r in filled if h == "train"]
    te_ = [r for h, r in filled if h == "test"]
    print(f"  {label:46} n={len(filled):4d}/{len(res)} all {ci([r for _, r in filled]):24} train {ci(tr_):24} test {ci(te_)}")


for depth, stop in ((0.5, 2.0), (0.5, 2.5), (1.0, 2.0), (1.0, 3.0)):
    line2(f"D2 retest -{depth} R, stop -{stop} R, 16 bars", lambda tr, d=depth, s=stop: run_retest(tr, d, s, 16))
for n in (4, 16):
    line2(f"D3 re-enter at the entry within {n} bars of the stop", lambda tr, n=n: run_reentry(tr, n))
line("D4 stop x2 + trail 0.5 R once +0.5 R (original units x2)", sl_mult=2.0, trail=(1.0, 1.0))
line("D4 stop x2 + target 1 R of the wider stop", sl_mult=2.0, tp=2.0)
