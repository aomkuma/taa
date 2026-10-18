"""Are F1's entries too early? (owner, 2026-10-18) (1) the losers' kind 3 (stopped, then the target reached);
(2) the stop against the M15 swing: R and win % by the stop in M15 ATR(14), design and window.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/too_early.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402
from portfolio import family_signals  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
pc = m15.close.shift()
tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
a15 = tr.rolling(14).mean()
a15.index = a15.index + pd.Timedelta(minutes=15)
for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
    z = plib.run(S, P)
    z["t"] = pd.to_datetime(z.t, utc=True)
    z["a15"] = a15.reindex(z.t, method="ffill").to_numpy()
    z["stop_m15"] = z.sl / z.a15
    los = z[z.exit == "stop"]
    k = los.kind.value_counts().reindex(["1", "2", "3"]).fillna(0).astype(int)
    print(f"\n== {part}: {len(z)} trades, stopped {len(los)}: wrong way {k['1']}, fell short {k['2']}, too early {k['3']};"
          f" minutes to the stop median {los.mins.median():.0f} (<= 5 min: {100 * (los.mins <= 5).mean():.0f}%)")
    print(f"   the stop in M15 ATR: median {z.stop_m15.median():.2f} (winners {z[z.exit == 'win'].stop_m15.median():.2f}, stopped {los.stop_m15.median():.2f})")
    for lo_, hi_ in ((0, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 9)):
        g = z[(z.stop_m15 >= lo_) & (z.stop_m15 < hi_)]
        if len(g):
            print(f"   stop {lo_:.2f}-{hi_:.2f} M15 ATR: {len(g):3} trades, win {100 * (g.exit == 'win').mean():3.0f}%, R {g.R.mean():+.3f}, {g.pnl.sum():+7.1f} USD")
