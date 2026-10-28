"""Does a wider stop help F1 CONF-72? (owner, 2026-10-18: "would doubling the SL help?") The stop x1 / x1.5 / x2 with
the same target and exits; with and without the account cap (skip a trade whose stop is above 10 USD x price/4100).

    data/venv-research/Scripts/python research/2026-10-18-moments/shadow/wider_stop.py
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
    print(f"\n== {'DESIGN 2023-11 .. 2026-02' if part == 'wdesign' else 'LATEST 2026-03 .. 10-14'}")
    for mult in (1.0, 1.5, 2.0):
        for cap in (False, True):
            if mult == 1.0 and cap:
                continue
            x = S.assign(sl=S.sl * mult)
            if cap:
                x = x[x.sl <= 10 * x.unit]
            z = plib.run(x, P)
            z["t"] = pd.to_datetime(z.t, utc=True)
            eq = z.pnl.cumsum()
            streak = mx = 0
            for v in z.pnl:
                streak = streak + 1 if v < 0 else 0
                mx = max(mx, streak)
            avg_loss = -z.pnl[z.pnl < 0].mean()
            months = z.pnl.groupby(z.t.dt.strftime("%Y-%m")).sum()
            print(f"  SL x{mult}{' capped 10 USD' if cap else '':14} {len(z):4} trades, win {100 * (z.exit == 'win').mean():3.0f}%, "
                  f"R {z.R.mean():+.3f}, {z.pnl.sum():+7.1f} USD, months+ {(months > 0).sum()}/{len(months)}, worst {z.pnl.min():6.2f},"
                  f" avg loss {avg_loss:5.2f} (6 in a row {6 * avg_loss:5.1f}), streak {mx}, max DD {(eq.cummax() - eq).max():5.1f}")
