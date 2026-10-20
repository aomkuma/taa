"""Bigger runs as trades (notes.md "Bigger runs"): at every moment of the aligned phase after an M5 pullback
(big_runs.py's group), a trade the D1 way at the next M1 open, the stop and the target X U (scaled by price like the
run catalogue), out after the hold at the last close, the auditor's costs (model_trades.trade_1atr), one position at a
time. X and the hold chosen on the learning parts by the rule written first: the highest min(R part 1, R part 2) of
those positive in both; none -> the exam is not read. The exam once, week by week.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/big_trades.py [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from entry_tables import aligned_frame  # noqa: E402
from model_trades import take, trade_1atr  # noqa: E402

REF = 4100.0
# the owner, 2026-10-19: "a 10-USD run is very little, M15 does it easily - hold short, in fast, out fast"
CHOICES = {"10U_15m": (10, 15), "10U_30m": (10, 30), "10U_60m": (10, 60), "10U_120m": (10, 120)}


def candidates(X: pd.DataFrame) -> pd.DataFrame:
    """The aligned phase after an M5 pullback: price under the M5 EMA 50 turned to the D1 way at or below L1's 40th
    percentile inside the phase; the side is the D1 way."""
    way = X.D1_way20.to_numpy()
    al = X.aligned.to_numpy()
    v = X.M5_ema50.to_numpy() * way
    cut = np.nanquantile(v[al & (X.half == "L1").to_numpy()], 0.4)
    k = al & (v <= cut)
    return X[k].assign(side=way[k].astype(int))


def run(C: pd.DataFrame, mk: dict, ot_ns: np.ndarray, xu: float, hold: int) -> pd.DataFrame:
    """Every candidate's trade, then one position at a time (the first in time)."""
    j0 = np.searchsorted(ot_ns, pd.DatetimeIndex(C.t).as_unit("ns").asi8)
    C = C.assign(j0=j0)[j0 < len(ot_ns)].copy()
    dist = xu * mk["o"][C.j0.to_numpy()] / REF
    T = pd.DataFrame([trade_1atr(mk, int(j), int(s), float(d), hold) for j, s, d in zip(C.j0, C.side, dist)], index=C.index)
    C = pd.concat([C, T], axis=1).assign(p=0.0, dist=dist)
    return take(C, 0.0)


def summary(T: pd.DataFrame, a: str, b: str) -> str:
    import wf  # noqa: PLC0415

    eq = T.pnl.cumsum()
    return (f"{len(T)} trades ({len(T) / np.busday_count(a, b):.2f} a weekday), win {(T.exit == 'win').mean():.3f}, R {T.R.mean():+.3f}, "
            f"USD {T.pnl.sum():+.1f} at 0.01 lot, lowest running total {eq.min():+.1f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, worst "
            f"{T.pnl.min():+.2f}, longest losing streak {wf.longest_run(T.pnl.to_numpy() < 0)}, exits {T.exit.value_counts().to_dict()}, "
            f"buys {int((T.side > 0).sum())} / sells {int((T.side < 0).sum())}")


def main() -> None:
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415

    mm = plib.load()
    mk = dict(o=mm.open.to_numpy(float), h=mm.high.to_numpy(float), lo=mm.low.to_numpy(float), c=mm.close.to_numpy(float),
              sp=mm.spread.to_numpy(float) * 0.01 + 0.08, ot_ns=mm.index.as_unit("ns").asi8, ny=plib.ny_mask(mm.index))
    C = candidates(aligned_frame())
    parts = {"L1": ("2023-11-01", "2025-01-01"), "L2": ("2025-01-01", "2026-04-18")}
    res = {}
    for name, (xu, hold) in CHOICES.items():
        for h, (a, b) in parts.items():
            T = run(C[C.half == h], mk, mk["ot_ns"], xu, hold)
            res[(name, h)] = T
            print(f"{name} {h}: {summary(T, a, b)}", flush=True)
    ok = {n: min(res[(n, "L1")].R.mean(), res[(n, "L2")].R.mean()) for n in CHOICES}
    good = {n: v for n, v in ok.items() if v > 0}
    if not good:
        print("\nno size is positive in both learning parts: the exam is not read")
        return
    pick = max(good, key=good.get)
    print(f"\nthe rule's size: {pick} (min R {good[pick]:+.3f})")
    if sys.argv[1:] != ["exam"]:
        return
    xu, hold = CHOICES[pick]
    T = run(C[C.half == "exam"], mk, mk["ot_ns"], xu, hold)
    print(f"THE EXAM, once - {pick}: {summary(T, '2026-04-20', '2026-10-17')}")
    T["cell"] = pick
    pd.set_option("display.width", 220)
    print(wf.weekly(T).to_string(index=False))
    T.to_parquet(HERE / "big_trades_exam.parquet")


if __name__ == "__main__":
    main()
