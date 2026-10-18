"""An independent re-derivation of v2s.py's walk-forward trades, written apart from it: each trade's lean recounted
from the rule's text (lean_check.recount - plain pandas, no picture.py / rarity.py), the side from it, the entry
timeframe's ATR from bars built here, and the trade walked again bar by bar (as check_v2b.py, which agreed with
V2b's 408 trades). Every value must agree, and no trade may open before the one before it has closed.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/check_v2s.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import jlib  # noqa: E402
from lean_check import recount  # noqa: E402

PARTS = {"L3": ("smooth", "pullback", "break"), "L6": ("smooth", "pullback", "break", "way", "size", "position")}
MIN_OF = {"M1": 1, "M5": 5, "M15": 15, "M30": 30}


def main() -> None:
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    W = pd.read_parquet(HERE / "v2s_wf_trades.parquet")
    t_dec = pd.DatetimeIndex(T.t_dec)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((t_dec.tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    m = jlib.m1_frame("XAUUSD")
    o, h, lo, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp = m.spread.to_numpy(float) * 0.01 + 0.08
    atr_of = {}
    for tf, n in MIN_OF.items():
        g = m.groupby(m.index.floor(f"{n}min"))
        b = pd.DataFrame({"h": g.high.max(), "l": g.low.min(), "c": g.close.last(), "end": g.apply(lambda x: x.index[-1])})
        pc = b.c.shift(1)
        tr = np.maximum(b.h, pc) - np.minimum(b.l, pc)
        b["atr"] = tr.rolling(14).mean()
        b["done"] = b.end + pd.Timedelta(minutes=1)
        atr_of[tf] = b.set_index("done").atr
    et = m.index.tz_convert("America/New_York")
    mins = et.hour * 60 + et.minute
    ny = (((mins >= 475) & (mins < 510)) | ((mins >= 505) & (mins < 540)) | ((mins >= 565) & (mins < 600))
          | ((mins >= 595) & (mins < 630)) | ((mins >= 660) & (mins < 840))) & (et.dayofweek < 5)
    bad, prev_x = 0, -1
    for r in W.sort_values("j0").itertuples():
        level, n_s, th_s = r.cell.split("_")
        n_min, theta = int(n_s[1:]), float(th_s[2:])
        e = int(r.row)
        n_e, x = recount(T, day, e, PARTS[level])
        side = 0
        if n_e >= n_min and np.isfinite(x):
            side = 1 if x >= theta - 1e-9 else (-1 if x <= -theta + 1e-9 else 0)
        j0 = int(np.searchsorted(m.index.as_unit("ns").asi8, t_dec[e].as_unit("ns").value))  # the first M1 bar opening at or after the snap
        a = {tf: atr_of[tf][atr_of[tf].index <= t_dec[e]].iloc[-1] for tf in MIN_OF}
        etf = next((tf for tf in ("M1", "M5", "M15", "M30") if np.isfinite(a[tf]) and a[tf] >= 5.0), "M30")
        sl, tp = max(a[etf], 5.0), 10.0 * c[j0 - 1] / 4100.0
        ss = 0.20 if ny[j0] else 0.15
        entry = o[j0] + sp[j0] + 0.07 if side > 0 else o[j0] - 0.07
        end = m.index[j0] + pd.Timedelta(minutes=12 * MIN_OF[etf])
        ex, pnl, xj, j = "time", None, None, j0
        while j < len(o) and m.index[j] < end:
            if side > 0:
                if lo[j] <= entry - sl:
                    ex, pnl, xj = "stop", -sl - ss, j
                    break
                if h[j] >= entry + tp:
                    ex, pnl, xj = "win", tp, j
                    break
            else:
                if h[j] + sp[j] >= entry + sl:
                    ex, pnl, xj = "stop", -sl - ss, j
                    break
                if lo[j] + sp[j] <= entry - tp:
                    ex, pnl, xj = "win", tp, j
                    break
            j += 1
        if pnl is None:
            xj = max(j - 1, j0)
            pnl = (c[xj] - 0.07 - entry) if side > 0 else (entry - (c[xj] + sp[xj] + 0.07))
        probs = []
        if n_e != r.n_days or not (abs(x - r.lean) < 1e-12):
            probs.append(f"lean {n_e} {x:+.4f} vs {r.n_days} {r.lean:+.4f}")
        if side != r.side or side == 0:
            probs.append(f"side {side} vs {r.side}")
        if j0 != r.j0 or j0 <= prev_x:
            probs.append(f"entry bar {j0} vs {r.j0} (the previous exit {prev_x})")
        if etf != r.etf or abs(sl - r.sl) > 1e-9 or abs(tp - r.tp) > 1e-9:
            probs.append(f"plan {etf} {sl:.4f} {tp:.4f} vs {r.etf} {r.sl:.4f} {r.tp:.4f}")
        if ex != r.exit or abs(pnl - r.pnl) > 1e-9 or xj != r.xj:
            probs.append(f"exit {ex} {pnl:.4f} @{xj} vs {r.exit} {r.pnl:.4f} @{r.xj}")
        if probs:
            bad += 1
            print("MISMATCH", r.t, r.cell, "; ".join(probs), flush=True)
        prev_x = int(r.xj)
    print(f"trades: {len(W)} checked, {bad} with a mismatch")


if __name__ == "__main__":
    main()
