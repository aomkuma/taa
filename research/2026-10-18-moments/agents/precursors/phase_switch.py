"""The side by the phase (notes.md, written before it is computed): D1 running and aligned -> the D1 way; D1 back and
forth at the M30 edge -> the fade; else none. The active hours, a market entry, the surrender 3 minutes / 2 USD, then
10 / 10 for 60 minutes, one position, on the real ticks; decisions at the M15 closes and at the M5 closes.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/phase_switch.py [exam]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from surrender import active, run, summary  # noqa: E402

RUN_ER, BACK_ER, K, Y = 0.264, 0.116, 3, 2.0


def side(X: pd.DataFrame) -> np.ndarray:
    way = X.D1_way20.to_numpy()
    fade = np.where(X.M30_pos <= 0.15, 1, np.where(X.M30_pos >= 0.85, -1, 0))
    er = X.D1_er20.to_numpy()
    return np.where((er >= RUN_ER) & X.aligned.to_numpy(), way, np.where(er <= BACK_ER, fade, 0)).astype(int)


def main() -> None:
    import wf  # noqa: PLC0415
    from entry_tables import aligned_frame  # noqa: PLC0415
    from m15_trades import PARTS, part_of  # noqa: PLC0415

    A = aligned_frame()
    A["part"] = part_of(pd.DatetimeIndex(A.t))
    A = A[active(A)].copy()
    A["side"] = side(A)
    res = {}
    for tf in ("M15", "M5"):
        for p in ("P1", "P2"):
            D = A[(A.part == p) & (A.side != 0)]
            if tf == "M15":
                D = D[pd.DatetimeIndex(D.t).minute % 15 == 0]
            T = run(D.sort_values("t"), K, Y)
            res[(tf, p)] = T
            print(f"{tf} | {p}: {summary(T, *PARTS[p])} | the D1-way trades {int((T.merge(D[['t', 'D1_er20']], on='t').D1_er20 >= RUN_ER).sum())}", flush=True)
    score = {tf: min(res[(tf, 'P1')].R.mean(), res[(tf, 'P2')].R.mean()) for tf in ("M15", "M5")}
    good = {k: v for k, v in score.items() if v > 0}
    if not good:
        print("\nneither is positive in both learning parts: the exam is not read")
        return
    tf = max(good, key=good.get)
    print(f"\nchosen: {tf} (min R {good[tf]:+.3f})")
    if sys.argv[1:] != ["exam"]:
        return
    D = A[(A.part == "exam") & (A.side != 0)]
    if tf == "M15":
        D = D[pd.DatetimeIndex(D.t).minute % 15 == 0]
    T = run(D.sort_values("t"), K, Y)
    print(f"THE EXAM, once (ticks to 2026-10-14): {summary(T, '2026-04-20', '2026-10-15')}")
    T["cell"] = f"phase switch {tf}"
    pd.set_option("display.width", 220)
    print(wf.weekly(T).to_string(index=False))
    T.to_parquet(HERE / "phase_switch_exam.parquet")


if __name__ == "__main__":
    main()
