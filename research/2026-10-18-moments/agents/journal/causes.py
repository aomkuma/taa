"""The concrete causes read off the charts of a rule's losers, coded and counted: for each cause, the share of the
stopped losers and of the winners that had it, by half-year (design data only), and the R of the trades with and
without it. Causes are defined in notes.md before this was run.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/journal/causes.py SYM trades_all_<SYM>_<RULE>.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jlib  # noqa: E402


def features(T: pd.DataFrame, P: jlib.Instr) -> pd.DataFrame:
    """Cause features at the decision bar p = e - 1 (closed bars only)."""
    e = T.e.to_numpy()
    p = e - 1
    s = T.side.to_numpy()
    a = T.atr1.to_numpy()
    o, h, lo, c = P.o, P.h, P.lo, P.c
    T = T.copy()
    T["body1"] = (c[p] - o[p]) * s / a  # the decision bar's body with the side
    T["ret3"] = (c[p] - c[p - 3]) * s / a
    T["rng1"] = (h[p] - lo[p]) / a
    # the 72-hour extreme in front of the trade (H1 swing area), as it stood 15 minutes before
    hi72 = np.array([h[i - 4320 : i - 15].max() for i in p])
    lo72 = np.array([lo[i - 4320 : i - 15].min() for i in p])
    front = np.where(s > 0, hi72, lo72)
    T["room72_tp"] = (front - c[p]) * s / T.tp.to_numpy()  # < 0: already beyond it (a breakout)
    stop_px = T.entry.to_numpy() - s * T.sl.to_numpy()
    T["stop_in_swing"] = (stop_px - T.ext15.to_numpy()) * s > 0 if "ext15" in T else False
    return T


CAUSES = {
    "C1 spike entry (bar body >= 1.5 ATR or 3-bar move >= 3 ATR with the side)": lambda T: (T.body1 >= 1.5) | (T.ret3 >= 3),
    "C2 under the 72-h extreme (0 < room < 0.5 target)": lambda T: (T.room72_tp > 0) & (T.room72_tp < 0.5),
    "C3 stop inside the last 15-min swing": lambda T: T.stop_in_swing.astype(bool),
    "C4 stretched (60-min move >= 8 ATR with the side)": lambda T: T.ret60 >= 8,
    "C5 US release within 15 min": lambda T: (T.since_rel <= 15) | (T.until_rel <= 15),
    "C6 late in the window (NY >= +120m, Asia >= +100m)": lambda T: ((T.session == 2) & (T.min_in >= 120)) | ((T.session == 0) & (T.min_in >= 100)),
    "C7 fast tape (M1 ATR >= 2x its day median)": lambda T: T.atr_ratio >= 2,
}


def main() -> None:
    sym, path = sys.argv[1], sys.argv[2]
    P = jlib.Instr(sym)
    T = pd.read_parquet(HERE / path)
    T["t"] = pd.to_datetime(T.t, utc=True)
    T = features(T, P)
    T["half"] = pd.cut(T.t, [pd.Timestamp(a, tz="UTC") for _, a, _ in jlib.HALVES] + [jlib.DESIGN_END],
                       labels=[n for n, _, _ in jlib.HALVES], right=False)
    los = T.exit == "stop"
    win = T.exit == "win"
    print(f"{path}: {len(T)} trades, stopped {int(los.sum())}, winners {int(win.sum())}, R {T.R.mean():+.3f}")
    print("cause: share of stopped losers / winners (all design), then losers/winners by half-year; R with / without")
    for name, f in CAUSES.items():
        m = np.asarray(f(T), dtype=bool)
        by = []
        for hn, g in T.groupby("half", observed=True):
            mg = np.asarray(f(g), dtype=bool)
            lg, wg = (g.exit == "stop").to_numpy(), (g.exit == "win").to_numpy()
            by.append(f"{100 * mg[lg].mean():3.0f}/{100 * mg[wg].mean():3.0f}" if lg.any() and wg.any() else "  -/  -")
        print(f"  {name}\n     {100 * m[los.to_numpy()].mean():3.0f}% / {100 * m[win.to_numpy()].mean():3.0f}%   halves {'  '.join(by)}"
              f"   R with {T.R[m].mean():+.3f} (n {int(m.sum())})  without {T.R[~m].mean():+.3f} (n {int((~m).sum())})")
    T.to_parquet(HERE / path.replace("trades_all_", "causes_"))


if __name__ == "__main__":
    main()
