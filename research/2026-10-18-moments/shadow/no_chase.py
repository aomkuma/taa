import sys
from pathlib import Path
import numpy as np, pandas as pd
A = Path("research/2026-10-18-moments/agents"); sys.path.insert(0, str(A / "portfolio")); sys.path.insert(0, str(A / "journal"))
import plib
from portfolio import family_signals
P = plib.jlib.Instr("XAUUSD")
for part in ("wdesign", "wtest"):
    S = family_signals("F1", ["C4 72-h extreme near/behind", "C5 not a fast tape"], 2, part)
    for name, m in (("frozen", np.ones(len(S), bool)),
                    ("no chase: 15-min run with the trade < 4 ATR", (S.ret15 < 4).to_numpy()),
                    ("no chase: 60-min run with the trade < 8 ATR", (S.ret60 < 8).to_numpy()),
                    ("both", ((S.ret15 < 4) & (S.ret60 < 8)).to_numpy())):
        z = plib.run(S[m], P)
        z["t"] = pd.to_datetime(z.t, utc=True)
        per = plib.by_half(z) if part == "wdesign" else " ".join(f"{k[5:]} {v.pnl.sum():+.1f}({len(v)})" for k, v in z.groupby(z.t.dt.strftime("%Y-%m")))
        eq = z.pnl.cumsum(); per += f" | worst {z.pnl.min():.2f} maxDD {(eq.cummax()-eq).max():.1f}"
        print(f"{part:8} {name:45} {len(z):4} trades R {z.R.mean():+.3f} {z.pnl.sum():+7.1f} USD {per}")
