"""Let the market show the side (notes.md, written before it is computed). At the M15 closes in the active hours: a buy
stop b USD above and a sell stop b below the last close; the first hit within 60 minutes is the trade, the target 10
USD and the stop s from the fill, out 60 minutes after the fill; the costs; one position at a time.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/straddle.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

TARGET, WAIT, HOLD, SLIP = 10.0, 60, 60, 0.07
GRID = [(3.0, 5.0), (3.0, 10.0), (5.0, 5.0), (5.0, 10.0)]


def straddle(mk: dict, j0: int, c0: float, b: float, s: float, wait: int = WAIT, hold: int = HOLD, pessimistic: bool = True) -> dict | None:
    """From bar j0: the first of high >= c0 + b (a buy, filled at that level + spread + slippage) and low <= c0 - b (a sell,
    filled at that level - slippage) within `wait` minutes; both in one bar -> a full stop (which came first is unknown);
    the fill bar touching the stop too -> a stop; else lvl2.manage from the next bar. None when nothing triggers.
    M1 bars hide the order inside a bar: pessimistic=True (the bound from below) as above; False (the bound from above)
    skips a bar reaching both levels and does not read the fill bar's other side (its low may have come before the fill)."""
    from lvl2 import NS_MIN, manage  # noqa: PLC0415

    o, h, lo, c, sp, ot, ny = (mk[k] for k in ("o", "h", "lo", "c", "sp", "ot_ns", "ny"))
    end = ot[j0] + wait * NS_MIN
    j = j0
    while j < len(o) and ot[j] < end:
        up, dn = h[j] >= c0 + b, lo[j] <= c0 - b
        if up or dn:
            ss = 0.20 if ny[j] else 0.15
            if up and dn:
                if not pessimistic:
                    return None
                return dict(side=0, exit="both", pnl=-(s + ss) - sp[j] - SLIP, R=-1.0 - (sp[j] + SLIP) / (s + ss), xj=j, fj=j)
            side = 1 if up else -1
            entry = c0 + b + sp[j] + SLIP if up else c0 - b - SLIP
            stop = entry - side * s
            worst = lo[j] if up else h[j] + sp[j]
            if pessimistic and (worst - stop) * side <= 0:
                return dict(side=side, exit="stop", pnl=-(s + ss), R=-1.0, xj=j, fj=j)
            if j + 1 >= len(o):
                return None
            x = manage(o, h, lo, c, sp, ot, j + 1, side, entry, s, TARGET, 0.0, np.array([], np.int64), np.array([], float), 99.0,
                       int(ot[j] + hold * NS_MIN), SLIP, ss)
            return dict(side=side, exit=x["exit"], pnl=x["pnl"], R=x["pnl"] / (s + ss), xj=x["xj"], fj=j)
        j += 1
    return None


def main() -> None:
    import plib  # noqa: PLC0415

    from big_trades import summary  # noqa: PLC0415
    from m15_trades import PARTS  # noqa: PLC0415

    mm = plib.load()
    mk = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), lo=mm.low.to_numpy(float), c=mm.close.to_numpy(float),
              sp=mm.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=mm.index.as_unit("ns").asi8, ny=plib.ny_mask(mm.index))
    X = pd.read_parquet(HERE / "burst_frame.parquet")
    act = ((X.abs_t_ny_open <= 60) | (X.abs_t_fix_pm <= 60) | (X.abs_t_us_data <= 60) | (X.abs_t_comex <= 60)).to_numpy()
    X = X[act].reset_index(drop=True)
    X["j0"] = np.searchsorted(mk["ot_ns"], pd.DatetimeIndex(X.t).as_unit("ns").asi8)
    pess = sys.argv[1:] != ["optimistic"]
    print("the fill bar's other side and a bar reaching both:", "counted against (the bound from below)" if pess else "not read / skipped (the bound from above)")
    res = {}
    for b, s in GRID:
        for p in ("P1", "P2"):
            D = X[(X.part == p) & (X.j0 < len(mk["o"]))].sort_values("t")
            rows, busy = [], -1
            for r in D.itertuples():
                if r.j0 <= busy:
                    continue
                x = straddle(mk, int(r.j0), float(mk["c"][r.j0 - 1]), b, s, pessimistic=pess)
                if x is None:
                    continue
                rows.append(dict(t=r.t, **x))
                busy = int(x["xj"])
            T = pd.DataFrame(rows)
            res[(b, s, p)] = T
            print(f"b {b:g}, s {s:g} | {p}: {summary(T, *PARTS[p])}", flush=True)
    score = {(b, s): min(res[(b, s, "P1")].R.mean(), res[(b, s, "P2")].R.mean()) for b, s in GRID}
    good = {k: v for k, v in score.items() if v > 0}
    print("\nchosen:" if good else "\nno (b, s) is positive in both learning parts: the exam is not read", max(good, key=good.get) if good else "")


if __name__ == "__main__":
    main()
