"""Owner, 2026-10-18: "the 10-bar scratch and the 60-minute exit - they close even at a loss?" F1 v2's exits by kind
on design and the window, and design with each of the two switched off.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/shadow/f1_exit_losses.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/weapon4"))
import w4lib as w  # noqa: E402

P = w.instr("XAUUSD")
orig = w.scratch


def table(z, label):
    print(f"\n{label}: {len(z)} trades, USD {z.usd.sum():+.1f}, R {z.R.mean():+.3f}")
    for ex, g in z.groupby("exit"):
        print(f"  {ex:8} {len(g):3}  avg USD {g.usd.mean():+6.2f}  sum {g.usd.sum():+7.1f}  losing {np.mean(g.usd < 0):4.0%}")


for tag, per in (("design", w.DESIGN), ("window", w.WINDOW)):
    D = w.build(P, 1, *per, [(0, 20)], f"XAUUSD_M1_{tag}_fr")
    h = pd.DatetimeIndex(D.t).hour
    S = w.signals(D[((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))], 3, 10, 8, 0.6, 60)
    w.scratch = orig
    table(w.run_v2(S, P), f"{tag.upper()} F1 v2 as in the bot")
    if tag == "design":
        w.scratch = lambda P_, e, s, tp, sl, ss, after, need: orig(P_, e, s, tp, sl, ss, 10_000, need)
        table(w.run_v2(S, P), "DESIGN without the 10-bar scratch")
        hold = w.scratch
        for mins in (120, 240):
            def longer(P_, e, s, tp, sl, ss, after, need, m=mins):
                n = len(P_.o)
                saved = P_.o
                # the 60-minute horizon is fixed inside scratch: emulate a longer one with plib-style trade
                out = P_.trade(e, s, tp, sl, 0.6, m, ss)
                return out["pnl"], out["mins"], out["exit"], out["mfe"]
            w.scratch = longer
            table(w.run_v2(S, P), f"DESIGN without the scratch, out after {mins} minutes")
        w.scratch = orig
