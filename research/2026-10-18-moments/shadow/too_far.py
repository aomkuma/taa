"""Round 12b (docs/OWN_SETUP.md): F1 CONF-72 + "already run too far" filters measured with yardsticks that do not
swell in a spike (H1 ATR, M15 ATR), and a stop no tighter than 1.5 M1 ATR.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/too_far.py
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
for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part)
    run60_h1 = (S.ret60 * S.atr1 / S.h1_atr).to_numpy()
    variants = {
        "F1 as frozen": np.ones(len(S), bool),
        "X1 60-min run < 1.5 H1 ATR": run60_h1 < 1.5,
        "X2 within 3 M15 ATR of M15 EMA20": (S.m15_c_e20 < 3).to_numpy(),
        "X3 stop >= 1.5 M1 ATR": (S.sl >= 1.5 * S.atr1).to_numpy(),
        "X1 + X2": (run60_h1 < 1.5) & (S.m15_c_e20 < 3).to_numpy(),
    }
    sig_0408 = S[S.t == pd.Timestamp("2026-04-08 00:03", tz="UTC")]
    for name, m in variants.items():
        z = plib.run(S[m], P)
        z["t"] = pd.to_datetime(z.t, utc=True)
        eq = z.pnl.cumsum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(
            f"{k[5:]} {v.pnl.sum():+.1f}({len(v)})" for k, v in z.groupby(z.t.dt.strftime("%Y-%m")))
        blocks = ""
        if len(sig_0408):
            blocks = " | 04-08 blocked" if not m[S.index.get_loc(sig_0408.index[0])] else " | 04-08 still taken"
        print(f"{part:8} {name:36} {len(z):4} trades R {z.R.mean():+.3f} {z.pnl.sum():+7.1f} USD maxDD {(eq.cummax() - eq).max():5.1f}{blocks} | {per}")
    if len(sig_0408):
        r = sig_0408.iloc[0]
        print(f"   04-08 signal: run60 {r.ret60 * r.atr1:.1f} USD = {r.ret60 * r.atr1 / r.h1_atr:.2f} H1 ATR (H1 ATR {r.h1_atr:.1f}); m15_c_e20 {r.m15_c_e20:.2f}; stop {r.sl:.2f} = {r.sl / r.atr1:.2f} M1 ATR")
