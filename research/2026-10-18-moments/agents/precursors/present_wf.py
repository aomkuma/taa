"""The bot on the present library (owner, 2026-10-19: "the same conditions as the bot, the decisions yours - compare"):
every 5 minutes inside the windows, per cell (layer x level x N_MIN x THETA) the side present_lean.pick takes from
the evidence, V2's trade (the labels), one position at a time; the cell chosen walk-forward month by month
(wf.walk_forward, six months back, >= 20 closed trades). The exam's trades are the list I then decide by eye.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/present_wf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
from present_lean import CELLS, pick  # noqa: E402


def one_at_a_time(rows: np.ndarray, side: np.ndarray, j0: np.ndarray, xj: dict[int, np.ndarray]) -> list[tuple[int, int]]:
    """The moments (in time order) a single position can take: (row, side) for each pick whose entry bar comes after
    the previous trade's exit bar; xj[side] - each row's exit bar for that side."""
    out, busy = [], -1
    for r, s in zip(rows, side):
        if s == 0 or j0[r] <= busy:
            continue
        out.append((int(r), int(s)))
        busy = int(xj[s][r])
    return out


def main() -> None:
    import jlib  # noqa: PLC0415
    import plib  # noqa: PLC0415
    import wf  # noqa: PLC0415

    P = pd.read_parquet(HERE / "present_3y.parquet")
    E = pd.read_parquet(HERE / "present_evidence.parquet")
    idx = jlib.m1_frame("XAUUSD").index
    j0 = P.j0.to_numpy()
    xj = {1: P.buy_xj.to_numpy(), -1: P.sell_xj.to_numpy()}
    col = {1: "buy", -1: "sell"}
    cells = {}
    for (lay, lv), g in E.groupby(["layer", "level"], sort=False):
        g = g.sort_values("row")
        for n_min, theta in CELLS:
            side = np.array([pick(a, b, c, n_min, theta) for a, b, c in zip(g.n, g.mb, g.ms)])
            taken = one_at_a_time(g.row.to_numpy(), side, j0, xj)
            if not taken:
                continue
            r, s = np.array(taken).T
            D = pd.DataFrame({"row": r, "side": s, "j0": j0[r]})
            for k in ("exit", "pnl", "R", "xj", "sl", "tp", "etf"):
                D[k] = [P[f"{col[x]}_{k}"].iloc[y] for y, x in zip(r, s)]
            D["t"] = idx[D.j0.to_numpy()]
            D["x_t"] = wf.exit_time(idx, D.xj.to_numpy())
            cells[f"{lay}_{lv}_n{n_min}_th{theta}"] = D
    WF, months = wf.walk_forward(cells, "2024-05", "2026-10")
    WF.to_parquet(HERE / "present_wf_trades.parquet")
    pd.set_option("display.width", 220)
    print(months.to_string(index=False))
    ex = WF[(WF.t >= plib.EXAM_START) & (WF.t < plib.EXAM_END)]
    print("\nthe exam week by week (Thai weeks, Monday):")
    print(wf.weekly(ex).to_string(index=False))
    for name, part, a, b in (("2024-05 .. 2026-04-17 (learning)", WF[WF.t < plib.EXAM_START], "2024-05-01", "2026-04-18"),
                             ("2026-04-18 .. 2026-10-16 (the exam)", ex, "2026-04-18", "2026-10-17")):
        eq = part.pnl.cumsum()
        print(f"{name}: {len(part)} trades ({len(part) / np.busday_count(a, b):.2f} a weekday), win {(part.pnl > 0).mean():.3f}, "
              f"R {part.R.mean():+.3f}, USD {part.pnl.sum():+.1f}, max DD {(eq.cummax().clip(lower=0) - eq).max():.1f}, worst "
              f"{part.pnl.min():+.2f}, longest losing streak {wf.longest_run(part.pnl.to_numpy() < 0)}")


if __name__ == "__main__":
    main()
