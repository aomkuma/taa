"""Too late or too early? (owner, 2026-10-18). The base signals (B0 + stop 3-10 U, the 0.5 M15-ATR floor, one per
episode, F1 exits, simulated alone) split by C4, and for each group: the stopped losers' three kinds (1 wrong way,
2 fell short, 3 too early: the target came within 120 min after the stop), the move into the entry (ret15 / ret60 in
M1 ATR, the trade's way positive), and how far the 72-h extreme was.

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/late_or_early.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402

for part in ("wdesign", "wtest"):
    P, D = plib.load(part)
    D = D.reset_index(drop=True)
    m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pc = m15.close.shift()
    tr = pd.concat([m15.high - m15.low, (m15.high - pc).abs(), (m15.low - pc).abs()], axis=1).max(axis=1)
    a15 = tr.rolling(14).mean()
    a15.index = a15.index + pd.Timedelta(minutes=15)
    side = D.side.to_numpy()
    sl0 = (P.fill(D.e.to_numpy(), side) - (D.level.to_numpy() - side * D.atr1.to_numpy())) * side
    D["sl"] = np.maximum(sl0, 0.5 * a15.reindex(pd.to_datetime(D.t, utc=True), method="ffill").to_numpy())
    pa = (D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim).to_numpy()
    ind = ((D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2).to_numpy()
    base = D.tide.to_numpy(bool) & D.at_level.to_numpy(bool) & pa & ind & (sl0 >= 3 * D.unit) & (sl0 <= 10 * D.unit)
    c4 = plib.MENU["C4 72-h extreme near/behind"](D).to_numpy(bool)
    print(f"\n== {'DESIGN' if part == 'wdesign' else 'WINDOW'}")
    for name, m in (("near the 72-h extreme (C4 passes)", base & c4), ("mid-range (C4 rejects)", base & ~c4)):
        X = D[m].copy()
        X["tt"] = pd.to_datetime(X.t, utc=True)
        X = X.sort_values(["side", "tt"])
        X = X[((X.tt.diff() > pd.Timedelta(minutes=15)) | (X.side.diff() != 0)).to_numpy()]
        rows = []
        for r in X.itertuples():
            ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
            o = P.trade(int(r.e), int(r.side), 8 * float(r.unit), float(r.sl), 0.6, 60, ss)
            rows.append((o["exit"], o["kind"], o["pnl"] / (r.sl + ss)))
        Z = pd.DataFrame(rows, columns=["exit", "kind", "R"], index=X.index)
        k = Z.kind[Z.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
        win = Z.exit == "win"
        print(f"  {name:34} {len(Z):5} trades, win {win.mean():.0%}, R {Z.R.mean():+.3f};"
              f" stopped losers: wrong way {k['1']:.0%}, fell short {k['2']:.0%}, too early {k['3']:.0%}")
        print(f"  {'':34} move into the entry (ATR, + = the trade's way): ret15 winners {X.ret15[win].median():+.2f}"
              f" / losers {X.ret15[Z.exit == 'stop'].median():+.2f}; ret60 winners {X.ret60[win].median():+.2f}"
              f" / losers {X.ret60[Z.exit == 'stop'].median():+.2f}; 72-h extreme ahead {((X.front72 - X.c_dec) * X.side / X.unit).median():.0f} U")
