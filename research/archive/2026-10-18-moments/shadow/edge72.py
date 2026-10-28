"""EDGE-72: the 72-hour extreme as the setup itself (2026-10-18; F1's C4, RUN-A's 72-h break and the turn-zone study
all point to gold carrying on through its 3-day extreme with the trend). Written before computing; every variant:
H1 tide with the side, C4 (the 72-h extreme in front < 4 U or behind), C5 (not a fast tape), wide windows; stop
beyond the last 15 minutes' extreme by 0.5 M1 ATR, at least 0.5 M15 ATR, 3-12 U else no trade; F1's exits (8 U,
BE 0.6, 60 min); one position at a time; real costs.
- E72a: + price action (M1 / M5 hammer, M1 engulfing, sweep and reclaim)            (no level, no indicators)
- E72b: + 2 of 3 M5 indicators                                                         (no level, no PA)
- E72c: + PA + 2/3 M5 indicators                                                       (no level)
- E72d: + at a level                                                                   (no PA, no indicators)
- F1 reference: + level + PA + 2/3 M5 (F1 with this stop)

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/edge72.py
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
    stop_px = D.ext15.to_numpy() - side * 0.5 * D.atr1.to_numpy()
    sl = (P.fill(D.e.to_numpy(), side) - stop_px) * side
    sl = np.maximum(sl, 0.5 * a15.reindex(pd.to_datetime(D.t, utc=True), method="ffill").to_numpy())
    D["sl"], D["tp"], D["be"], D["hz"], D["trail"] = sl, 8 * D.unit, 0.6, 60, False
    ok = (D.sl >= 3 * D.unit) & (D.sl <= 12 * D.unit)
    core = D.tide.astype(bool) & plib.MENU["C4 72-h extreme near/behind"](D) & plib.MENU["C5 not a fast tape"](D) & ok
    pa = D.pa_m1 | D.pa_m5 | D.engulf | D.reclaim
    ind = (D.rsi_ok.astype(int) + D.macd_ok.astype(int) + D.stoch_ok.astype(int)) >= 2
    lvl = D.at_level.astype(bool)
    days = pd.bdate_range(*(("2023-11-01", "2026-02-28") if part == "wdesign" else ("2026-03-01", "2026-10-13"))).size
    print(f"\n== {'DESIGN' if part == 'wdesign' else 'WINDOW'} ({days} weekdays)")
    for name, m in (("E72a PA", core & pa), ("E72b 2/3 M5", core & ind), ("E72c PA + 2/3 M5", core & pa & ind),
                    ("E72d level", core & lvl), ("F1 ref (level + PA + 2/3)", core & lvl & pa & ind)):
        z = plib.run(D[m.to_numpy()], P, per_sess=99)
        z["t"] = pd.to_datetime(z.t, utc=True)
        eq = z.pnl.cumsum()
        per = plib.by_half(z) if part == "wdesign" else " ".join(
            f"{k[5:]} {v:+.0f}" for k, v in z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum().items())
        print(f"  {name:26} {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}% R {z.R.mean():+.3f}"
              f" USD {z.pnl.sum():+7.1f} DD {(eq.cummax() - eq).max():5.1f} | {per}")
