"""The owner's trade (notes.md "The owner's trade: M15, 10 USD, three or four bars", written before it is computed):
decisions at the M15 closes inside the owner's windows; the D1 way at the next M1 open, the target and the stop 10 USD,
out after 3 or 4 M15 bars, the auditor's costs, one position at a time; entries (A) the aligned phase, (B) A after an
M5 pullback. Learning on 2025-10-18 .. 2026-01-15 and 2026-01-16 .. 2026-04-17; the exam once for the chosen pair.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/m15_trades.py
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
from model_trades import take, trade_1atr  # noqa: E402

TARGET = 10.0
HOLDS = {"3 bars": 45, "4 bars": 60}
PARTS = {"P1": ("2025-10-18", "2026-01-16"), "P2": ("2026-01-16", "2026-04-18"), "exam": ("2026-04-18", "2026-10-17")}


def part_of(t: pd.DatetimeIndex) -> np.ndarray:
    out = np.full(len(t), "", dtype=object)
    for name, (a, b) in PARTS.items():
        out[(t >= pd.Timestamp(a, tz="UTC")) & (t < pd.Timestamp(b, tz="UTC"))] = name
    return out


def entries(X: pd.DataFrame) -> dict[str, np.ndarray]:
    """At M15 closes: (A) aligned; (B) aligned after an M5 pullback (P1's 40th percentile inside the phase)."""
    t = pd.DatetimeIndex(X.t)
    at15 = (t.minute % 15 == 0) & (t.second == 0)
    way = X.D1_way20.to_numpy()
    al = X.aligned.to_numpy() & at15
    v = X.M5_ema50.to_numpy() * way
    cut = np.nanquantile(v[al & (X.part == "P1").to_numpy()], 0.4)
    return {"A aligned": al, "B aligned + M5 pullback": al & (v <= cut)}


def main() -> None:
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415

    mm = plib.load()
    mk = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), lo=mm.low.to_numpy(float), c=mm.close.to_numpy(float),
              sp=mm.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=mm.index.as_unit("ns").asi8, ny=plib.ny_mask(mm.index))
    X = aligned_frame()
    X["part"] = part_of(pd.DatetimeIndex(X.t))
    X = X[X.part != ""].reset_index(drop=True)
    X["side"] = X.D1_way20.astype(int)
    X["j0"] = np.searchsorted(mk["ot_ns"], pd.DatetimeIndex(X.t).as_unit("ns").asi8)
    E = entries(X)
    res = {}
    for ename, mask in E.items():
        for hname, hold in HOLDS.items():
            for p in ("P1", "P2"):
                C = X[mask & (X.part == p).to_numpy() & (X.j0 < len(mk["o"])).to_numpy()]
                T = pd.DataFrame([trade_1atr(mk, int(j), int(s), TARGET, hold) for j, s in zip(C.j0, C.side)], index=C.index)
                T = take(pd.concat([C, T], axis=1).assign(p=0.0), 0.0)
                res[(ename, hname, p)] = T
                print(f"{ename} | {hname} | {p}: {summary(T, *PARTS[p])}", flush=True)
    score = {(e, h): min(res[(e, h, "P1")].R.mean(), res[(e, h, "P2")].R.mean()) for e in E for h in HOLDS}
    good = {k: v for k, v in score.items() if v > 0}
    if not good:
        print("\nno entry x hold is positive in both learning parts: the exam is not read")
        return
    e, h = max(good, key=good.get)
    print(f"\nchosen: {e} | {h} (min R {good[(e, h)]:+.3f}); THE EXAM, once:")
    C = X[E[e] & (X.part == "exam").to_numpy() & (X.j0 < len(mk["o"])).to_numpy()]
    T = pd.DataFrame([trade_1atr(mk, int(j), int(s), TARGET, HOLDS[h]) for j, s in zip(C.j0, C.side)], index=C.index)
    T = take(pd.concat([C, T], axis=1).assign(p=0.0), 0.0)
    print(summary(T, "2026-04-20", "2026-10-17"))
    T["cell"] = f"{e} {h}"
    pd.set_option("display.width", 220)
    print(wf.weekly(T).to_string(index=False))
    T.to_parquet(HERE / "m15_trades_exam.parquet")


if __name__ == "__main__":
    main()
