"""Why did the losing TS trades lose: the wrong direction, or noise because the entry came too early (owner,
2026-10-17)? Every trade's path on gold M1 bars (bid OHLC; a SELL exits at the ask = bid + spread):

- each stopped trade: how far it ran the trade's way before the stop (MFE, R), then what price did in the
  ``AFTER`` hours after the stop: reached the original target ("too early / noise"), came back to the entry only
  ("half right"), or neither ("wrong direction"); and how far beyond the stop it went before reaching the target
  (the stop that would have survived);
- the winners: how close they came to the stop first (MAE, R), the room the entry had.

Trades come from the rule of the two-year study (default: TS-h4, the H4 EMA tide and the level within 0.5 read ATR,
2 R, at most 12 h) or from backtest trades.csv files (``--trades a.csv b.csv ...``).

usage: python ts_losers.py [--trades <trades.csv> ...]
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POINT, K, HOLD_H, AFTER_H = 0.01, 2.0, 12.0, 12.0

m1 = pd.read_parquet(ROOT / (os.environ.get("TS_HISTORY", "data/history") + "/FBS-Demo/XAUUSD/M1.parquet"), columns=["close_time", "high", "low", "spread"])
t1 = m1["close_time"].to_numpy(dtype="datetime64[ns]")
hi, lo = m1["high"].to_numpy(dtype=float), m1["low"].to_numpy(dtype=float)
sp = m1["spread"].to_numpy(dtype=float) * POINT


def idx(t: pd.Timestamp) -> int:
    return int(np.searchsorted(t1, np.datetime64(t.tz_convert(None)), side="right"))


def path(time: pd.Timestamp, buy: bool, entry: float, stop: float, tp: float) -> dict[str, float | str]:
    """The trade's M1 path: its exit within HOLD_H, and for a stop what followed in the AFTER_H hours."""
    s, e = idx(time), idx(time + pd.Timedelta(hours=HOLD_H))
    risk = abs(entry - stop)
    sign = 1 if buy else -1
    # the trade's own exit side: a BUY closes at the bid, a SELL at the ask
    fav = hi[s:e] if buy else lo[s:e] + sp[s:e]  # the best exit price each bar
    adv = lo[s:e] if buy else hi[s:e] + sp[s:e]  # the worst
    sl_hit = (adv <= stop) if buy else (adv >= stop)
    tp_hit = (fav >= tp) if buy else (fav <= tp)
    i_sl = int(np.argmax(sl_hit)) if sl_hit.any() else len(adv)
    i_tp = int(np.argmax(tp_hit)) if tp_hit.any() else len(adv)
    if i_sl == len(adv) and i_tp == len(adv):
        return {"exit": "TIME"}
    if i_tp < i_sl:
        mae = float(((entry - adv[: i_tp + 1].min()) if buy else (adv[: i_tp + 1].max() - entry)) / risk)
        return {"exit": "TP", "mae_r": mae}
    mfe = float(((fav[: i_sl + 1].max() - entry) if buy else (entry - fav[: i_sl + 1].min())) / risk)
    a0 = s + i_sl + 1  # the bars after the stop, for AFTER_H hours of clock time
    a1 = int(np.searchsorted(t1, t1[s + i_sl] + np.timedelta64(int(AFTER_H * 3600), "s"), side="right"))
    f2 = hi[a0:a1] if buy else lo[a0:a1] + sp[a0:a1]
    d2 = lo[a0:a1] if buy else hi[a0:a1] + sp[a0:a1]
    reach = (f2 >= tp) if buy else (f2 <= tp)
    back = (f2 >= entry) if buy else (f2 <= entry)
    j = int(np.argmax(reach)) if reach.any() else len(f2)
    beyond = float(((stop - d2[: j + 1].min()) if buy else (d2[: j + 1].max() - stop)) / risk) if len(d2) else 0.0
    kind = "too early / noise" if reach.any() else ("half right" if back.any() else "wrong direction")
    return {"exit": "SL", "mfe_r": mfe, "after": kind, "beyond_r": max(beyond, 0.0)}


def from_study() -> pd.DataFrame:
    d = pd.read_csv(ROOT / "data/backtests/ts/outcomes_two_years_d1.csv", parse_dates=["time"])
    loc = d[["H1_pivot_dist", "H4_pivot_dist"]].min(axis=1)
    buy = d.side == "BUY"
    f = pd.read_parquet(ROOT / (os.environ.get("TS_HISTORY", "data/history") + "/FBS-Demo/XAUUSD/H4.parquet")).sort_values("close_time")
    f["e"] = f.close.ewm(span=50, adjust=False).mean()
    f["s"] = f.e - f.e.shift(5)
    x = pd.merge_asof(d[["time"]], f[["close_time", "close", "e", "s"]], left_on="time", right_on="close_time")
    tide = (((x.close > x.e) & (x.s > 0) & buy) | ((x.close < x.e) & (x.s < 0) & ~buy)).to_numpy()
    r = d[tide & (loc <= 0.5)].copy()
    spread = r.spread_points.fillna(25.0) * POINT
    b = r.side == "BUY"
    r["entry"] = np.where(b, r.close + spread, r.close)
    r["stop"] = np.where(b, r["pivot"] - 0.25 * r.atr - spread, r["pivot"] + 0.25 * r.atr + spread)
    risk = (r.entry - r.stop).abs()
    r["tp"] = np.where(b, r.entry + K * risk, r.entry - K * risk)
    return r[["time", "side", "entry", "stop", "tp"]]


def from_trades(files: list[str]) -> pd.DataFrame:
    t = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    t = t[t.symbol == "XAUUSD"]
    return pd.DataFrame({
        "time": pd.to_datetime(t.entry_time, utc=True, format="ISO8601"),
        "side": t.side, "entry": t.entry_price, "stop": t.sl_initial, "tp": t.tp_initial,
    })


trades = from_trades(sys.argv[2:]) if len(sys.argv) > 2 and sys.argv[1] == "--trades" else from_study()
rows = [path(r.time, r.side == "BUY", r.entry, r.stop, r.tp) for r in trades.itertuples()]
o = pd.DataFrame(rows, index=trades.index).join(trades)
n = len(o)
sl, tp = o[o.exit == "SL"], o[o.exit == "TP"]
print(f"{n} trades: target {len(tp)} ({len(tp) / n:.0%}), stop {len(sl)} ({len(sl) / n:.0%}), time exit {(o.exit == 'TIME').sum()}")
print(f"\nthe {len(sl)} stopped trades, what price did in the {AFTER_H:g} h after the stop:")
for kind in ("too early / noise", "half right", "wrong direction"):
    g = sl[sl.after == kind]
    print(f"  {kind:18} {len(g):4d} ({len(g) / max(1, len(sl)):.0%})  MFE before the stop: median {g.mfe_r.median():.2f} R")
print("\nhow far the stopped trades had run the trade's way first (MFE):")
for lo_, hi_ in ((0, 0.25), (0.25, 0.5), (0.5, 1.0), (1.0, 9)):
    g = sl[(sl.mfe_r >= lo_) & (sl.mfe_r < hi_)]
    print(f"  {lo_:g}-{hi_:g} R: {len(g):4d} ({len(g) / max(1, len(sl)):.0%})")
noise = sl[sl.after == "too early / noise"]
if len(noise):
    q = noise.beyond_r.quantile([0.25, 0.5, 0.75]).round(2).tolist()
    print(f"\n'too early' trades went beyond the stop by {q} R (p25/p50/p75) before reaching the target;"
          f" a stop {1 + q[1]:.2f} R wide would have kept half of them")
if len(tp):
    print(f"winners came within this of the stop first (MAE): median {tp.mae_r.median():.2f} R, "
          f"p75 {tp.mae_r.quantile(0.75):.2f} R, >= 0.8 R: {(tp.mae_r >= 0.8).mean():.0%}")
o["side_"] = o.side
print("\nby side:", o[o.exit == "SL"].groupby("side_").after.value_counts(normalize=True).round(2).to_dict())
