"""The owner (2026-10-18): a loser labelled "wrong way" means the other side should have won - how far did price
really run against each one, and can the cause seen at the entry (chase, stop inside the swing) pick the side? For
every F1 CONF-72 signal: the run against within 30 / 60 minutes; the other side as a 5 USD scalp; by the cause group,
on the design data and the window.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/wrong_way.py
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
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part).reset_index(drop=True)
    run60_h1 = S.ret60 * S.atr1 / S.h1_atr
    S["group"] = np.where((run60_h1 >= 1.0) | (S.m15_c_e20 >= 3), "chase", np.where(S.sl < 1.5 * S.atr1, "stop in swing", "fits the logic"))
    z = plib.run(S, P)
    z = z.merge(S[["t", "side", "group"]], on=["t", "side"], how="left")
    against, scal = [], []
    for r in z.itertuples():
        e, s = int(r.e), int(r.side)
        seg = slice(e, min(e + 60, len(P.o)))
        against.append((P.o[e] - P.lo[seg].min()) if s > 0 else (P.h[seg].max() - P.o[e]))
        m = P.trade(e, -s, 5.0 * float(r.u), 5.0 * float(r.u), None, 30, P.stop_slip)
        scal.append(m["pnl"])
    z["against60"], z["other5"] = against, scal
    print(f"\n== {part}: {len(z)} trades")
    los = z[(z.exit == "stop") & (z.kind == "1")]
    print(f"   'wrong way' losers {len(los)}: price ran against within 60 min - median {los.against60.median():.1f} USD,"
          f" q25 {los.against60.quantile(.25):.1f}, q75 {los.against60.quantile(.75):.1f}; >= 10 USD in {100 * (los.against60 >= 10).mean():.0f}%")
    print(f"   the other side, 5/5 USD scalp, on those losers only: {100 * (los.other5 > 0).mean():.0f}% win, {los.other5.sum():+.1f} USD")
    print("   the other side 5/5 scalp on ALL signals of each cause group (what we can actually trade):")
    for g, x in z.groupby("group"):
        print(f"     {g:15} {len(x):4} signals: ours {x.pnl.sum():+7.1f} USD (win {100 * (x.exit == 'win').mean():.0f}%)"
              f" | other side {x.other5.sum():+7.1f} USD (win {100 * (x.other5 > 0).mean():.0f}%)")
    if part == "wtest":
        t = los.assign(time=pd.to_datetime(los.t, utc=True).dt.tz_convert("Asia/Bangkok").dt.strftime("%d/%m %H:%M"))
        print(t[["time", "side", "pnl", "group", "against60", "other5"]].round(1).to_string(index=False))
