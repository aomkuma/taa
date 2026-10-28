"""Where is price when the base signal fires? (owner, 2026-10-18: "price already ran, the signal came late?").
For the base signals (B0 + stop 3-10 U, one per episode) split by C4: the position inside the 72-hour range
(0 = the far end, 1 = the extreme in the trade's way), hours since that extreme was made, the move in the last
60 / 15 minutes (M1 ATR, + = the trade's way).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/where_base.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402

P = plib.jlib.Instr("XAUUSD")
n72 = 4305
for part in ("wdesign", "wtest"):
    _, D = plib.load(part)
    D = D.reset_index(drop=True)
    side = D.side.to_numpy()
    sl0 = (P.fill(D.e.to_numpy(), side) - (D.level.to_numpy() - side * D.atr1.to_numpy())) * side
    pa = (D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim).to_numpy()
    ind = ((D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2).to_numpy()
    base = D.tide.to_numpy(bool) & D.at_level.to_numpy(bool) & pa & ind & (sl0 >= 3 * D.unit) & (sl0 <= 10 * D.unit)
    c4 = plib.MENU["C4 72-h extreme near/behind"](D).to_numpy(bool)
    X = D[base].assign(c4=c4[base])
    X["tt"] = pd.to_datetime(X.t, utc=True)
    X = X.sort_values(["side", "tt"])
    X = X[((X.tt.diff() > pd.Timedelta(minutes=15)) | (X.side.diff() != 0)).to_numpy()]
    rows = []
    for r in X.itertuples():
        p = int(r.e) - 1
        seg = slice(p - 16 - n72 + 1, p - 16 + 1)
        hi, lo_ = P.h[seg].max(), P.lo[seg].min()
        far, ext = (lo_, hi) if r.side > 0 else (hi, lo_)
        pos = (P.c[p] - far) / (ext - far)
        k = (np.argmax(P.h[seg]) if r.side > 0 else np.argmin(P.lo[seg]))
        hours = (n72 - 1 - k + 16) / 60
        rows.append((pos, hours, (ext - far) * r.side / r.unit))
    X[["pos72", "hours_since", "range72_u"]] = rows
    print(f"\n== {'DESIGN' if part == 'wdesign' else 'WINDOW'}")
    for name, g in (("near the extreme (C4 passes)", X[X.c4]), ("mid-range (C4 rejects)", X[~X.c4])):
        q = lambda s: f"{s.quantile(0.25):.2f} / {s.median():.2f} / {s.quantile(0.75):.2f}"  # noqa: E731
        print(f"  {name:30} {len(g):5}: position in the 72-h range (p25/median/p75) {q(g.pos72)};"
              f" hours since the extreme {g.hours_since.median():.0f}; 72-h range {g.range72_u.median():.0f} U;"
              f" last 60 min {g.ret60.median():+.1f} ATR, last 15 min {g.ret15.median():+.1f} ATR")
