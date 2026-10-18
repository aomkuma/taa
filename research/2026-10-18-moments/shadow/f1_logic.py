"""F1 CONF-72 trades split by whether the entry fits the owner's logic (no chase: the 60-min run < 1 H1 ATR and the
close within 3 M15 ATR of the M15 EMA20; the stop >= 1.5 M1 ATR - beyond the normal swing; the H1 leg not against),
on the design data and the window, with the luck test (would the other side, same target / stop, also have won?).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/f1_logic.py
"""

import sys
from pathlib import Path

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
    chase = (run60_h1 >= 1.0) | (S.m15_c_e20 >= 3)
    S["logic"] = "ok"
    S.loc[S.cr_H1_leg_dir < 0, "logic"] = "H1 leg against"
    S.loc[S.sl < 1.5 * S.atr1, "logic"] = "stop in noise"
    S.loc[chase, "logic"] = "chase"
    z = plib.run(S, P)
    z = z.merge(S[["t", "side", "logic"]], on=["t", "side"], how="left")
    both = []
    for r in z.itertuples():
        m = P.trade(int(r.e), -int(r.side), float(r.tp), float(r.sl), None, 60, P.stop_slip)
        both.append(m["exit"] == "win")
    z["other_wins"] = both
    print(f"\n== {part}: {len(z)} trades")
    for lg, g in z.groupby("logic"):
        print(f"   {lg:15} {len(g):4} trades win {100 * (g.exit == 'win').mean():3.0f}% R {g.R.mean():+.3f} {g.pnl.sum():+7.1f} USD"
              f" | winners where the other side would also have won: {int((g.other_wins & (g.exit == 'win')).sum())} of {int((g.exit == 'win').sum())}")
    if part == "wdesign":
        z["t"] = pd.to_datetime(z.t, utc=True)
        ok = z[z.logic == "ok"]
        print("   'ok' by half-year:", plib.by_half(ok))
