"""Inside a range (notes.md, written before it is computed; owner, 2026-10-19: "if trading with the trend meets
obstacles, try the periods when it runs inside a range"). At M15 closes: in a range phase (D1 back and forth, or H4
sideways), price at the M30 range's low edge (<= 0.15) a buy, at its high edge (>= 0.85) a sell; 10 USD target and stop,
out after 3 / 4 M15 bars, the costs, one position at a time; the same edges outside the range phases for contrast.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/range_trades.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from big_trades import summary  # noqa: E402
from entry_tables import aligned_frame  # noqa: E402
from m15_trades import PARTS, part_of  # noqa: E402
from model_trades import take, trade_1atr  # noqa: E402

D1_BACK = 0.116  # L1's lower tercile of the 20-day efficiency (phase_tables)
EDGE = 0.15
TARGET = 10.0
HOLDS = {"3 bars": 45, "4 bars": 60}


def setups(X: pd.DataFrame, h4_cut: float) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """The phases and the fade side at the M30 edges (+1 at the low edge, -1 at the high edge, 0 elsewhere)."""
    t = pd.DatetimeIndex(X.t)
    at15 = (t.minute % 15 == 0) & (t.second == 0)
    pos = X.M30_pos.to_numpy(float)
    side = np.where(pos <= EDGE, 1, np.where(pos >= 1 - EDGE, -1, 0))
    d1 = X.D1_er20.to_numpy() <= D1_BACK
    h4 = X.H4_er30.to_numpy() <= h4_cut
    edge = at15 & (side != 0)
    return {"D1 back and forth": edge & d1, "H4 sideways": edge & h4, "either range": edge & (d1 | h4),
            "outside the ranges": edge & ~d1 & ~h4}, side


def main() -> None:
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415

    mm = plib.load()
    mk = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), lo=mm.low.to_numpy(float), c=mm.close.to_numpy(float),
              sp=mm.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=mm.index.as_unit("ns").asi8, ny=plib.ny_mask(mm.index))
    X = aligned_frame()
    X["part"] = part_of(pd.DatetimeIndex(X.t))
    X = X[X.part != ""].reset_index(drop=True)
    X["j0"] = np.searchsorted(mk["ot_ns"], pd.DatetimeIndex(X.t).as_unit("ns").asi8)
    h4_cut = float(np.nanquantile(X.H4_er30[X.part == "P1"], 1 / 3))
    S, side = setups(X, h4_cut)
    X["side"] = side
    print(f"H4 sideways: the 30-bar efficiency <= {h4_cut:.3f} (P1's lower tercile)")
    res = {}
    for name, mask in S.items():
        for hname, hold in HOLDS.items():
            for p in ("P1", "P2"):
                C = X[mask & (X.part == p).to_numpy() & (X.j0 < len(mk["o"])).to_numpy()]
                T = pd.DataFrame([trade_1atr(mk, int(j), int(s), TARGET, hold) for j, s in zip(C.j0, C.side)], index=C.index)
                T = take(pd.concat([C, T], axis=1).assign(p=0.0), 0.0)
                res[(name, hname, p)] = T
                print(f"{name} | {hname} | {p}: {summary(T, *PARTS[p])}", flush=True)
    score = {(n, h): min(res[(n, h, "P1")].R.mean(), res[(n, h, "P2")].R.mean()) for n in S if n != "outside the ranges" for h in HOLDS}
    good = {k: v for k, v in score.items() if v > 0}
    if not good:
        print("\nno range phase x hold is positive in both learning parts: the exam is not read")
        return
    n, h = max(good, key=good.get)
    print(f"\nchosen: {n} | {h} (min R {good[(n, h)]:+.3f}); THE EXAM, once:")
    C = X[S[n] & (X.part == "exam").to_numpy() & (X.j0 < len(mk["o"])).to_numpy()]
    T = pd.DataFrame([trade_1atr(mk, int(j), int(s), TARGET, HOLDS[h]) for j, s in zip(C.j0, C.side)], index=C.index)
    T = take(pd.concat([C, T], axis=1).assign(p=0.0), 0.0)
    print(summary(T, "2026-04-20", "2026-10-17"))
    T["cell"] = f"{n} {h}"
    pd.set_option("display.width", 220)
    print(wf.weekly(T).to_string(index=False))
    T.to_parquet(HERE / "range_trades_exam.parquet")


if __name__ == "__main__":
    main()
