"""Why so few F1 trades? (owner, 2026-10-18: "few signals, or rejected by the rules - and would the rejected ones
have won or lost?"). Window 2026-03-01 .. 10-14, the wide windows (Asia 00-02, London 07-12, NY 12-17 UTC), both
sides of every minute. The funnel step by step, then every group that one step removed simulated ALONE (each signal
its own trade, the F1 exits: 8 U target, break-even at 0.6, 60 min, stop as F1's with the 0.5 M15-ATR floor; real
costs, 0.01 lot). Episodes = signals of one side at least 15 minutes apart (a setup lasting several minutes counts
once).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_funnel.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402

P, D = plib.load(sys.argv[1] if len(sys.argv) > 1 else "wtest")
D = D.reset_index(drop=True)
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)

side = D.side.to_numpy()
stop_px = D.level.to_numpy() - side * D.atr1.to_numpy()
D["sl0"] = (P.fill(D.e.to_numpy(), side) - stop_px) * side
D["sl"] = np.maximum(D.sl0, 0.5 * a15.reindex(pd.to_datetime(D.t, utc=True), method="ffill").to_numpy())
D["tp"] = 8 * D.unit
pa = (D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim).to_numpy()
ind = ((D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2).to_numpy()
tide, lvl = D.tide.to_numpy(bool), D.at_level.to_numpy(bool)
stop_ok = ((D.sl0 >= 3 * D.unit) & (D.sl0 <= 10 * D.unit)).to_numpy()
c4 = plib.MENU["C4 72-h extreme near/behind"](D).to_numpy(bool)
c5 = plib.MENU["C5 not a fast tape"](D).to_numpy(bool)


def episodes(m):
    x = D[m].sort_values(["side", "t"])
    t = pd.to_datetime(x.t, utc=True)
    new = (t.diff() > pd.Timedelta(minutes=15)) | (x.side.diff() != 0)
    return int(new.sum()) if len(x) else 0


def sim(m, label):
    x = D[m]
    x = x[np.isfinite(x.sl) & (x.sl > 0)]
    x = x.assign(tt=pd.to_datetime(x.t, utc=True)).sort_values(["side", "tt"])
    first = (x.tt.diff() > pd.Timedelta(minutes=15)) | (x.side.diff() != 0)
    x = x[first.to_numpy()]  # one trade per episode (its first minute)
    out = []
    for r in x.itertuples():
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        o = P.trade(int(r.e), int(r.side), float(r.tp), float(r.sl), 0.6, 60, ss)
        out.append((o["pnl"], o["pnl"] / (r.sl + ss), o["exit"]))
    z = pd.DataFrame(out, columns=["usd", "R", "exit"])
    if not len(z):
        print(f"  {label:58} 0")
        return
    print(f"  {label:58} {len(z):5} win {100 * (z.exit == 'win').mean():3.0f}%  R {z.R.mean():+.3f}  USD {z.usd.sum():+8.1f}"
          f"  ({z.usd.sum() / len(z):+.2f} a trade)")


days = pd.bdate_range("2026-03-01", "2026-10-14").size
print(f"== funnel, window ({days} weekdays): minutes (both sides) / episodes")
steps = [("every window minute x 2 sides", np.ones(len(D), bool)),
         ("1 H1 tide with the side", tide),
         ("2 + at a level", tide & lvl),
         ("3 + price action", tide & lvl & pa),
         ("4 + 2 of 3 M5 indicators (= B0)", tide & lvl & pa & ind),
         ("5 + stop 3-10 U", tide & lvl & pa & ind & stop_ok),
         ("6 + C4 72-h extreme near", tide & lvl & pa & ind & stop_ok & c4),
         ("7 + C5 not a fast tape (= F1 signals)", tide & lvl & pa & ind & stop_ok & c4 & c5)]
for name, m in steps:
    print(f"  {name:40} {m.sum():7} min  {episodes(m):5} episodes  ({episodes(m) / days:.2f} a day)")
print("  8 one position at a time: 34 trades (portfolio run)")
print("\n== what each step removed, one trade per episode, simulated alone (F1 exits)")
sim(tide & lvl & pa & ind & stop_ok & c4 & c5, "F1 signals (all, no position limit)")
sim(tide & lvl & pa & ind & stop_ok & c4 & ~c5, "removed by C5 (fast tape)")
sim(tide & lvl & pa & ind & stop_ok & ~c4, "removed by C4 (72-h extreme far)")
sim(tide & lvl & pa & ind & ~stop_ok & (D.sl0 > 10 * D.unit).to_numpy(), "removed by the stop: > 10 U")
sim(tide & lvl & pa & ind & ~stop_ok & (D.sl0 < 3 * D.unit).to_numpy(), "removed by the stop: < 3 U (floor 0.5 M15 ATR)")
sim(tide & lvl & pa & ~ind & stop_ok & c4 & c5, "removed by the indicators (0-1 of 3)")
sim(tide & lvl & ~pa & ind & stop_ok & c4 & c5, "removed by no price action")
sim(tide & ~lvl & pa & ind & c4 & c5 & np.isfinite(D.sl).to_numpy(), "removed by not at a level")
sim(~tide & lvl & pa & ind & stop_ok & c4 & c5, "removed by the H1 tide (against)")
