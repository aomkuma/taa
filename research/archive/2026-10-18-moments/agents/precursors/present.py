"""The present library (notes.md "The present library", written before it is computed; owner, 2026-10-19: "the library's
pictures must be what the bot sees in the present"): moments taken by the clock - every 5 minutes inside the owner's
windows while the market trades - never chosen by what followed. Each keeps what the bot saw (every timeframe's
picture and outline, `moments.pictures_at`, the function that rebuilds moments_3y exactly) and, known only later, what
followed: the first 10 U run starting within 30 minutes (the run catalogue) and V2's buy and sell from it
(`trade_labels.trades_at`).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/present.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
# this folder's moments.py before plib (plib puts the research folder first, whose moments.py would shadow it)
from moments import FIRST, pictures_at  # noqa: E402, I001
import plib  # noqa: E402

STEP_MIN = 5
HORIZON_MIN = 30
NS_MIN = 60 * 10**9


def clock_moments(m_index: pd.DatetimeIndex, first: pd.Timestamp, end: pd.Timestamp, step_min: int = STEP_MIN) -> pd.DatetimeIndex:
    """Every step-minute clock time t in [first, end) inside the owner's windows (plib.window_mask of t) whose M1 bar
    closing at t (opening at t - 1 minute) exists - chosen by the clock and the data present at t, nothing later."""
    grid = pd.date_range(first, end, freq=f"{step_min}min")
    grid = grid[grid < end]  # [first, end): date_range keeps a lone start equal to the end
    inside = plib.window_mask(grid).any(axis=1).to_numpy()
    have = (grid - pd.Timedelta(minutes=1)).isin(m_index)
    return grid[inside & have]


def run_label(t_ns: np.ndarray, start_ns: np.ndarray, side: np.ndarray, horizon_min: int = HORIZON_MIN) -> np.ndarray:
    """For each decision time: the first run whose start bar opens in [t, t + horizon) - 'ran_up' (side +1) or
    'ran_dn' (side -1); 'none' without one. Two runs starting on the same bar: the up run."""
    if len(start_ns) == 0:
        return np.full(len(t_ns), "none")
    order = np.lexsort((-side, start_ns))  # by start time, then the up run first
    s, d = start_ns[order], side[order]
    k = np.searchsorted(s, t_ns, side="left")
    ok = k < len(s)
    k = np.minimum(k, len(s) - 1)
    hit = ok & (s[k] < t_ns + horizon_min * NS_MIN)
    return np.where(hit, np.where(d[k] > 0, "ran_up", "ran_dn"), "none")


def main() -> None:
    from trade_labels import market, trades_at  # noqa: PLC0415

    plib.gold.below_normal_priority()
    m = plib.load()
    t = clock_moments(m.index, FIRST, plib.EXAM_END)
    t_ns = t.as_unit("ns").asi8
    print(f"moments: {len(t)} ({t.min()} .. {t.max()}), {len(pd.unique(t.tz_convert('Asia/Bangkok').normalize()))} days", flush=True)
    C = pd.read_parquet(HERE / "runs_10.parquet")
    cls = run_label(t_ns, pd.DatetimeIndex(C.t).as_unit("ns").asi8, C.side.to_numpy())
    pics, SH = pictures_at(m, t_ns)
    mj, mk = market()
    L = trades_at(mj, mk, t_ns)
    P = pd.concat([pd.DataFrame({"t_dec": t, "cls": cls}), pics, L], axis=1)
    P.to_parquet(HERE / "present_3y.parquet")
    np.save(HERE / "present_shapes_3y.npy", SH)
    print("saved", P.shape, SH.shape, "| what followed:", pd.Series(cls).value_counts().to_dict(), flush=True)


if __name__ == "__main__":
    main()
