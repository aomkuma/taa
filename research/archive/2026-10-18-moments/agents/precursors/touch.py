"""The first reach of a larger-timeframe level without a pierce (notes.md "Research outside ...", E1; Osler: take-profit
orders cluster at the level, so price tends to stall at the first reach). For every confirmed swing top / bottom of a
larger timeframe (H1, H4), from the first M5 bar completing after the swing is known until the swing is WIN bars old
on its own timeframe: the first M5 bar that comes within TOL of the larger timeframe's ATR of the level from the inside
without going beyond it is a touch (a sell at a top, a buy at a bottom); a bar going beyond it first ends the watch with
no touch.

    (used by combine.py)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TOL, WIN = 0.25, 120


def touches(h: np.ndarray, lo: np.ndarray, avail: np.ndarray, Y: dict, tol: float = TOL, win: int = WIN) -> pd.DataFrame:
    """h, lo, avail: the M5 bars; Y: the larger timeframe's avail, atr and piv. One row per touch."""
    pidx, pval, ptyp, pconf = Y["piv"]
    yav, yatr = Y["avail"], Y["atr"]
    out = []
    for k in range(len(pidx)):
        known = yav[int(pconf[k])]
        last = int(pidx[k]) + win - 1  # the last larger bar while the swing is inside its window
        if last >= len(yav):
            last = len(yav) - 1
        s0 = int(np.searchsorted(avail, known, side="right"))  # the first M5 bar completing after the swing is known
        s1 = int(np.searchsorted(avail, yav[last], side="right"))  # M5 bars completing by the window's last larger bar
        lvl, typ = float(pval[k]), int(ptyp[k])
        for i in range(s0, s1):
            yb = int(np.searchsorted(yav, avail[i], side="right")) - 1  # the larger bar closed by this M5 bar
            band = tol * yatr[yb]
            if typ == 1:
                if h[i] > lvl:
                    break
                if h[i] >= lvl - band:
                    out.append(dict(i=i, level_type=typ, side=-1, level=lvl, gap=(lvl - h[i]) / yatr[yb], age=yb - int(pidx[k])))
                    break
            else:
                if lo[i] < lvl:
                    break
                if lo[i] <= lvl + band:
                    out.append(dict(i=i, level_type=typ, side=1, level=lvl, gap=(lo[i] - lvl) / yatr[yb], age=yb - int(pidx[k])))
                    break
    return pd.DataFrame(out, columns=["i", "level_type", "side", "level", "gap", "age"])
