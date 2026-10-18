"""F1 v2 (X4: the regime exit + the 10-bar scratch, f1_improve.py) with a regime measure the bot can read: its M1
window holds ~3 days, so the 20-day M15-ATR median is out of reach; the H1 frame holds months. Variants (written
before computing; threshold 1.3 as X3):
- RH1: H1 ATR(14) (mean true range) of the last closed H1 bar >= 1.3 x the median of the last 480 H1 ATR values.
- RM3: M15 ATR(14) >= 1.3 x its median over the last 288 M15 bars (3 days; from the M1 window).
- X4 (the research measure) for reference.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_v2_regime.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.argv.append("--x4")  # f1_improve.py: definitions only
sys.path.insert(0, "research/2026-10-18-moments/shadow")
import f1_improve as fi  # noqa: E402

P, plib, runner, scratch = fi.P, fi.plib, fi.runner, fi.scratch
h1 = P.m.resample("60min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = h1.close.shift()
tr = pd.concat([h1.high - h1.low, (h1.high - pc).abs(), (h1.low - pc).abs()], axis=1).max(axis=1)
ah = tr.rolling(14).mean()
ah_med = ah.rolling(480, min_periods=200).median()
ah.index = ah_med.index = h1.index + pd.Timedelta(minutes=60)
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15_3d = a15.rolling(288, min_periods=100).median()
a15_3d.index = a15.index + pd.Timedelta(minutes=15)


def run(S, strong):
    rows, free = [], pd.Timestamp(0, tz="UTC")
    for k, r in enumerate(S.itertuples()):
        if r.t < free:
            continue
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        e, s = int(r.e), int(r.side)
        if strong[k]:
            pnl, mins, ex = runner(e, s, r.sl, r.room_f, r.atr1, r.a15, 0.6 * r.tp, 180, ss)
        else:
            pnl, mins, ex = scratch(e, s, r.tp, r.sl, ss, 10, 2.0, r.unit)
        rows.append(dict(t=r.t, pnl=pnl, R=pnl / (r.sl + ss), exit=ex))
        free = r.t + pd.Timedelta(minutes=int(mins))
    return pd.DataFrame(rows)


for part in ("wdesign", "wtest"):
    S = fi.family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
    S["t"] = pd.to_datetime(S.t, utc=True)
    S = S.sort_values("t").reset_index(drop=True)
    S["a15"] = fi.a15.reindex(S.t, method="ffill").to_numpy()
    S["a15m"] = fi.a15_med.reindex(S.t, method="ffill").to_numpy()
    S["sl"] = np.maximum(S.sl, 0.5 * S.a15)
    fill = P.fill(S.e.to_numpy(), S.side.to_numpy())
    S["room_f"] = S.room.to_numpy() - (fill - S.c_dec.to_numpy()) * S.side.to_numpy()
    reg = {
        "X4 (20-day M15)": (S.a15 >= 1.3 * S.a15m).to_numpy(),
        "RH1 (H1 vs 480)": (ah.reindex(S.t, method="ffill") >= 1.3 * ah_med.reindex(S.t, method="ffill")).to_numpy(),
        "RM3 (M15 vs 3 days)": (S.a15.to_numpy() >= 1.3 * a15_3d.reindex(S.t, method="ffill").to_numpy()),
    }
    print(f"\n== {'DESIGN' if part == 'wdesign' else 'WINDOW'}")
    for name, strong in reg.items():
        z = run(S, strong)
        eq = z.pnl.cumsum()
        g = z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(f"{k[5:]} {v:+.1f}" for k, v in g.items())
        agree = np.mean(strong == reg["X4 (20-day M15)"])
        print(f"  {name:20} strong {strong.mean():.0%} (agrees with X4 {agree:.0%}): {len(z)} R {z.R.mean():+.3f}"
              f" USD {z.pnl.sum():+7.1f} DD {(eq.cummax() - eq).max():5.1f} | {per}")
