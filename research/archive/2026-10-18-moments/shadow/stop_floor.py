"""F1 CONF-72 with the stop widened to at least a share of the M15 ATR(14) (owner, 2026-10-18: "do what you said,
and widen the SL"): floors 0.5 / 0.75 / 1.0 M15 ATR, no account cap; the target unchanged (8 U) and scaled to keep
the original target/stop ratio. Chosen on the design data, then the latest six months.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/stop_floor.py
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
    S["a15"] = a15.reindex(pd.to_datetime(S.t, utc=True), method="ffill").to_numpy()
    print(f"\n== {'DESIGN 2023-11 .. 2026-02' if part == 'wdesign' else 'LATEST 2026-03 .. 10-14'}")
    for floor in (0.0, 0.5, 0.75, 1.0):
        for tp_mode in ("target 8 U", "target keeps the ratio"):
            if floor == 0 and tp_mode != "target 8 U":
                continue
            x = S.copy()
            new_sl = np.maximum(x.sl, floor * x.a15)
            if tp_mode != "target 8 U":
                x["tp"] = x.tp * new_sl / x.sl
            x["sl"] = new_sl
            z = plib.run(x, P)
            z["t"] = pd.to_datetime(z.t, utc=True)
            eq = z.pnl.cumsum()
            months = z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum()
            per = plib.by_half(z) if part == "wdesign" else " ".join(f"{k[5:]} {v:+.1f}" for k, v in months.items())
            print(f"  floor {floor:4.2f} M15 ATR, {tp_mode:22} {len(z):4} trades, win {100 * (z.exit == 'win').mean():3.0f}%, R {z.R.mean():+.3f},"
                  f" {z.pnl.sum():+7.1f} USD, worst {z.pnl.min():6.2f}, max DD {(eq.cummax() - eq).max():5.1f} | {per}")
