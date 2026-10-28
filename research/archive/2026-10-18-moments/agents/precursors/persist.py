"""Does gold carry on? (notes.md, written before it is computed). From each moment's next M1 open: the first touch of
+-X (either way) within 4 hours; from there, does price reach 2X the same way before it is back at the start, within
the next 4 hours? Read by the hour, the D1 phase and the way against D1, in the latest parts and the older halves.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/persist.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))

HZ = 240


def first_hits(h: np.ndarray, lo: np.ndarray, j0: np.ndarray, level: np.ndarray, up_d: np.ndarray, dn_d: np.ndarray,
               horizon: int = HZ, chunk: int = 4000) -> tuple[np.ndarray, np.ndarray]:
    """For each start bar j0 and level: the bar offset of the first high >= level + up_d and of the first low <= level -
    dn_d within horizon bars (horizon when never)."""
    fu, fd = np.full(len(j0), horizon), np.full(len(j0), horizon)
    steps = np.arange(horizon)
    for a in range(0, len(j0), chunk):
        jj = j0[a:a + chunk]
        idx = jj[:, None] + steps[None, :]
        valid = idx < len(h)
        idx = np.minimum(idx, len(h) - 1)
        hu = (h[idx] >= (level[a:a + chunk] + up_d[a:a + chunk])[:, None]) & valid
        hd = (lo[idx] <= (level[a:a + chunk] - dn_d[a:a + chunk])[:, None]) & valid
        fu[a:a + chunk] = np.where(hu.any(axis=1), hu.argmax(axis=1), horizon)
        fd[a:a + chunk] = np.where(hd.any(axis=1), hd.argmax(axis=1), horizon)
    return fu, fd


def carry_on(o: np.ndarray, h: np.ndarray, lo: np.ndarray, j0: np.ndarray, x: float, horizon: int = HZ) -> tuple[np.ndarray, np.ndarray]:
    """(way, carried): way = +1 / -1 the side of the first X (0: none, or both in one bar); carried = 1 when from that bar
    on price reaches start + 2X that way before it is back at the start (0 back first, NaN neither / both in one bar).
    The race starts at the bar after the first touch (the touch bar's order is unknown)."""
    n = len(j0)
    start = o[j0]
    d = np.full(n, x)
    fu, fd = first_hits(h, lo, j0, start, d, d, horizon)
    way = np.where((fu < fd), 1, np.where(fd < fu, -1, 0))
    way[(fu == horizon) & (fd == horizon)] = 0
    j1 = j0 + np.where(way > 0, fu, fd) + 1
    ok = (way != 0) & (j1 < len(o))
    carried = np.full(n, np.nan)
    if ok.any():
        k = np.nonzero(ok)[0]
        # up: to start + 2X (X above the touch level) before back to the start (X below it); down mirrored
        lvl = start[k] + way[k] * x
        gu, gd = first_hits(h, lo, j1[k], lvl, np.where(way[k] > 0, x, x), np.where(way[k] > 0, x, x), horizon)
        on = np.where(way[k] > 0, gu < gd, gd < gu)
        back = np.where(way[k] > 0, gd < gu, gu < gd)
        carried[k] = np.where(on, 1.0, np.where(back, 0.0, np.nan))
    return way, carried


def main() -> None:
    import jlib  # noqa: PLC0415

    from entry_tables import aligned_frame  # noqa: PLC0415
    from m15_trades import part_of  # noqa: PLC0415

    X = aligned_frame()
    X["part"] = part_of(pd.DatetimeIndex(X.t))
    X.loc[X.part == "", "part"] = X.half
    X.loc[X.part == "exam", "part"] = "exam"
    m = jlib.m1_frame("XAUUSD")
    o, h, lo = m.open.to_numpy(float), m.high.to_numpy(float), m.low.to_numpy(float)
    j0 = np.searchsorted(m.index.as_unit("ns").asi8, pd.DatetimeIndex(X.t).as_unit("ns").asi8)
    keep = j0 < len(o) - 1
    X, j0 = X[keep].reset_index(drop=True), j0[keep]
    act = ((X.t_ny_open.abs() <= 60) | (X.t_fix_pm.abs() <= 60) | (X.t_us_data.abs() <= 60) | (X.t_comex.abs() <= 60)).to_numpy()
    phase = np.where(X.D1_er20 >= 0.264, "D1 running", np.where(X.D1_er20 <= 0.116, "D1 back and forth", "between"))
    rows = []
    for x in (5.0, 10.0, 20.0):
        way, car = carry_on(o, h, lo, j0, x)
        withd1 = way * X.D1_way20.to_numpy()
        groups = {"all": np.ones(len(X), bool), "active hours": act, "quiet hours": ~act,
                  "D1 running": phase == "D1 running", "D1 back and forth": phase == "D1 back and forth",
                  "first X with D1": withd1 > 0, "first X against D1": withd1 < 0,
                  "aligned, first X with D1": X.aligned.to_numpy() & (withd1 > 0), "aligned, first X against D1": X.aligned.to_numpy() & (withd1 < 0)}
        for g, mask in groups.items():
            rec = dict(X=x, group=g)
            for p in ("L1", "L2", "P1", "P2"):
                k = mask & (X.part == p).to_numpy() & np.isfinite(car)
                rec[p] = car[k].mean() if k.any() else np.nan
                rec[f"n_{p}"] = int(k.sum())
            rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_csv(HERE / "persist.csv", index=False)
    pd.set_option("display.width", 220, "display.max_rows", 100)
    print("once price has gone X USD (the first X from a moment), the share that reach 2X before back at the start; "
          "L1 2023-11 .. 2024-12, L2 2025-01 .. 2025-10-17, P1 2025-10-18 .. 2026-01-15, P2 2026-01-16 .. 2026-04-17:")
    print(R.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
