"""C4 on data that chose nothing (notes.md "C4 on the older years", written before computing): gold 2020-09 ..
2023-10, never used to select C4 (the portfolio agent chose it on 2023-11 .. 2026-02). Every 15th minute of F1's
windows (UTC 00-02, 07-12, 12-17), both sides: C4-near (the 72-hour extreme of bars -4320 .. -16 still in front,
closer than 4 U) and C4-behind (already beyond it); 8 U the side's way first within 60 minutes? No effect = 50 %.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/c4_old.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402
from level_power import first_passage  # noqa: E402

FIRST, LAST = pd.Timestamp("2020-09-01", tz="UTC"), pd.Timestamp("2023-11-01", tz="UTC")
MID = pd.Timestamp("2022-04-01", tz="UTC")
TP_U, HZ = 8.0, 60


def c4_flags(hi72: float, lo72: float, c: float, unit: float, side: int) -> tuple[bool, bool]:
    """(near, behind) for one side: the 72-hour extreme the trade's way still in front and closer than half the target,
    or already behind the close."""
    gap = (hi72 - c) if side > 0 else (c - lo72)
    return (0 < gap < 0.5 * TP_U * unit), (gap <= 0)


def main() -> None:
    plib.gold.below_normal_priority()
    m = plib.gold.bars("M1")
    m = m[(m.index >= FIRST - pd.Timedelta(days=5)) & (m.index < LAST)]
    m = m[~m.index.duplicated(keep="last")]
    t = m.index
    h, lo, c = (m[k].to_numpy(float) for k in ("high", "low", "close"))
    hi72 = pd.Series(h).rolling(4305).max().to_numpy()  # bars i-4320 .. i-16 for decision bar i: read at i - 16
    lo72 = pd.Series(lo).rolling(4305).min().to_numpy()
    utc = t.hour * 60 + t.minute
    win = (utc < 120) | ((utc >= 420) & (utc < 1020))
    wd = np.asarray(t.dayofweek < 5)
    grid = np.asarray(t.minute % 15 == 0)
    rows = []
    for i in np.nonzero(np.asarray(win) & wd & grid & np.asarray(t >= FIRST))[0]:
        if i < 4320 or not np.isfinite(hi72[i - 16]):
            continue
        unit = c[i] / 4100.0
        d = TP_U * unit
        fp = first_passage(h, lo, int(i), c[i] + d, c[i] - d, HZ)
        if fp == 0:
            continue
        for side in (1, -1):
            near, behind = c4_flags(hi72[i - 16], lo72[i - 16], c[i], unit, side)
            rows.append((t[i], side, near, behind, fp == side))
    R = pd.DataFrame(rows, columns=["t", "side", "near", "behind", "went"])
    R["part"] = np.where(R.t < MID, "2020-09..2022-03", "2022-04..2023-10")
    out = []
    for name, mask in (("C4-near", R.near), ("C4-behind", R.behind), ("C4 (near or behind)", R.near | R.behind),
                       ("neither (control)", ~(R.near | R.behind))):
        g = R[mask].groupby("part").went.agg(n="size", its_way="mean")
        g["se"] = np.sqrt(g.its_way * (1 - g.its_way) / g.n)
        g["edge_in_se"] = (g.its_way - 0.5) / g.se
        out.append(g.assign(component=name).reset_index())
    pd.set_option("display.width", 200)
    print("gold 2020-09 .. 2023-10 (never used to choose C4): 8 U the side's way first within 60 minutes; no effect 50 %")
    print(pd.concat(out)[["component", "part", "n", "its_way", "se", "edge_in_se"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
