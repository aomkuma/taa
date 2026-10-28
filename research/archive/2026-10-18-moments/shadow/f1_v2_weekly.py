"""F1 v2 (RM3 regime exit + 10-bar scratch; f1_v2_regime.py) on the window, month by month and week by week, at
0.01 lot with real costs (owner, 2026-10-18).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_v2_weekly.py
"""

import sys

import numpy as np
import pandas as pd

sys.argv.append("--x4")
sys.path.insert(0, "research/2026-10-18-moments/shadow")
import f1_improve as fi  # noqa: E402

P = fi.P
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15_3d = a15.rolling(288, min_periods=100).median()
a15_3d.index = a15.index + pd.Timedelta(minutes=15)

S = fi.family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, "wtest").reset_index(drop=True)
S["t"] = pd.to_datetime(S.t, utc=True)
S = S.sort_values("t").reset_index(drop=True)
S["a15"] = fi.a15.reindex(S.t, method="ffill").to_numpy()
S["sl"] = np.maximum(S.sl, 0.5 * S.a15)
fill = P.fill(S.e.to_numpy(), S.side.to_numpy())
S["room_f"] = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * S.side.to_numpy()
strong = S.a15.to_numpy() >= 1.3 * a15_3d.reindex(S.t, method="ffill").to_numpy()
rows, free = [], pd.Timestamp(0, tz="UTC")
for k, r in enumerate(S.itertuples()):
    if r.t < free:
        continue
    ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
    if strong[k]:
        pnl, mins, ex = fi.runner(int(r.e), int(r.side), r.sl, r.room_f, r.atr1, r.a15, 0.6 * r.tp, 180, ss)
    else:
        pnl, mins, ex = fi.scratch(int(r.e), int(r.side), r.tp, r.sl, ss, 10, 2.0, r.unit)
    rows.append(dict(t=r.t, side="BUY" if r.side > 0 else "SELL", mode="runner" if strong[k] else "8U", exit=ex,
                     usd=pnl, R=pnl / (r.sl + ss)))
    free = r.t + pd.Timedelta(minutes=int(mins))
z = pd.DataFrame(rows)
z.to_csv("research/2026-10-18-moments/shadow/f1_v2_window_trades.csv", index=False)
print("MONTHS")
g = z.groupby(z.t.dt.strftime("%Y-%m"))
for k, v in g:
    print(f"  {k}: {len(v):2} trades, win {(v.usd > 0).sum():2}, {v.usd.sum():+7.1f} USD, R {v.R.mean():+.2f}")
print("WEEKS (Monday)")
wk = z.t.dt.tz_convert("Asia/Bangkok").dt.to_period("W-SUN").dt.start_time
for k, v in z.groupby(wk):
    print(f"  {k:%Y-%m-%d}: {len(v)} trades, {v.usd.sum():+6.1f} USD  " + ", ".join(f"{u:+.1f}" for u in v.usd))
print(f"TOTAL {len(z)} trades, {z.usd.sum():+.1f} USD, R {z.R.mean():+.3f}, weeks with trades {wk.nunique()},"
      f" positive weeks {(z.groupby(wk).usd.sum() > 0).sum()}")
