"""F1b: is there a stable profitable subgroup among the base signals C4 rejects (the 72-h extreme far in front)?
(owner, 2026-10-18: at least one trade a day). Base = H1 tide + level + PA + 2/3 M5 + stop 3-10 U, the 0.5 M15-ATR
floor, F1 exits (8 U, BE 0.6, 60 min), one trade per episode (15 min), simulated alone. Candidate splits written
before computing; a split counts only if positive in >= 4 of 5 design half-years; then the window once:
- room24: the 24-hour extreme in front (bars -1440 .. -16) near (< 4 U) or behind
- H1 strong: the H1 close >= 2 H1-ATR-ranges beyond its EMA50 (h1_c_e50 >= 2)
- M15 with: M15 EMA20 rising the trade's way and the close beyond its EMA50
- pos240 >= 0.5 (the close in the upper half of the 4-hour range for a buy)
- room in front >= 8 U (space for the target)
- session: Asia / London / New York separately

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/c4_rejected.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

A = Path("research/2026-10-18-moments/agents")
sys.path.insert(0, str(A / "portfolio"))
sys.path.insert(0, str(A / "journal"))
import plib  # noqa: E402

m15b = None


def prep(part):
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
    D["tp"] = 8 * D.unit
    pa = (D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim).to_numpy()
    ind = ((D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2).to_numpy()
    base = D.tide.to_numpy(bool) & D.at_level.to_numpy(bool) & pa & ind & (sl0 >= 3 * D.unit) & (sl0 <= 10 * D.unit)
    c4 = plib.MENU["C4 72-h extreme near/behind"](D).to_numpy(bool)
    X = D[base & ~c4].copy()
    X["tt"] = pd.to_datetime(X.t, utc=True)
    X = X.sort_values(["side", "tt"])
    X = X[((X.tt.diff() > pd.Timedelta(minutes=15)) | (X.side.diff() != 0)).to_numpy()]
    p = X.e.to_numpy() - 1
    s = X.side.to_numpy()
    hi24 = pd.Series(P.h).rolling(1425).max().to_numpy()
    lo24 = pd.Series(P.lo).rolling(1425).min().to_numpy()
    X["room24_u"] = (np.where(s > 0, hi24[p - 16], lo24[p - 16]) - X.c_dec) * s / X.unit
    out = []
    for r in X.itertuples():
        ss = P.stop_slip_ny if int(r.session) == 2 else P.stop_slip
        o = P.trade(int(r.e), int(r.side), float(r.tp), float(r.sl), 0.6, 60, ss)
        out.append((o["pnl"], o["pnl"] / (r.sl + ss)))
    X["usd"], X["R"] = zip(*out)
    return X


SPLITS = {
    "all C4-rejected": lambda X: np.ones(len(X), bool),
    "room24 near/behind": lambda X: (X.room24_u < 4).to_numpy(),
    "H1 strong (c_e50 >= 2)": lambda X: (X.h1_c_e50 >= 2).to_numpy(),
    "M15 with": lambda X: ((X.m15_e20_slope > 0) & (X.m15_c_e50 > 0)).to_numpy(),
    "pos240 >= 0.5": lambda X: (X.pos240 >= 0.5).to_numpy(),
    "room in front >= 8 U": lambda X: (X.room / X.unit >= 8).to_numpy(),
    "Asia": lambda X: (X.session == 0).to_numpy(),
    "London": lambda X: (X.session == 1).to_numpy(),
    "New York": lambda X: (X.session == 2).to_numpy(),
    "room24 + M15 with": lambda X: ((X.room24_u < 4) & (X.m15_e20_slope > 0) & (X.m15_c_e50 > 0)).to_numpy(),
}
Dd, Dt = prep("wdesign"), prep("wtest")
days_d, days_t = pd.bdate_range("2023-11-01", "2026-02-28").size, pd.bdate_range("2026-03-01", "2026-10-14").size
for name, f in SPLITS.items():
    a, b = Dd[f(Dd)], Dt[f(Dt)]
    h = plib.half_of(a.tt)
    g = a.R.groupby(h).mean().reindex([x[0] for x in plib.HALVES])
    print(f"{name:24} design {len(a):5} ({len(a) / days_d:.2f}/d) R {a.R.mean():+.3f} halves+ {(g > 0).sum()}/{g.notna().sum()}"
          f" [{' '.join(f'{v:+.2f}' for v in g)}] | window {len(b):4} ({len(b) / days_t:.2f}/d) R {b.R.mean():+.3f} USD {b.usd.sum():+7.1f}")
