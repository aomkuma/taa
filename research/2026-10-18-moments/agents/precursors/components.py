"""Each component of LV3 alone (notes.md "Each component of LV3 alone", written before computing): at a decision (an
M1 close inside the owner's windows), does price go 1 A (the entry TF's ATR) the component's way before 1 A the other
way, within 120 minutes? From the close, no effect = 50 %.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/components.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lvl2  # noqa: E402
import lvl3  # noqa: E402
import plib  # noqa: E402
from level_power import first_passage  # noqa: E402
from lvl import entry_tf  # noqa: E402

START = pd.Timestamp("2023-09-01", tz="UTC")
SPLIT = pd.Timestamp("2025-01-01", tz="UTC")
HORIZON = 120


def way(fp: int, side: int) -> float:
    """1.0 when the first passage went the component's way, 0.0 the other way, NaN when it did not resolve."""
    return np.nan if fp == 0 or side == 0 else float(fp == side)


def main() -> None:
    plib.gold.below_normal_priority()
    M = lvl3.Market()
    p = lvl2.Params()
    win = plib.window_mask(M.ot).any(axis=1).to_numpy()
    pre = np.asarray((M.ot >= START) & (M.ot < plib.EXAM_START))
    grid = np.asarray(M.ot.minute % 15 == 0)
    rows = []
    for t in np.nonzero(win & pre & grid)[0]:
        t = int(t)
        t_ns = int(M.ot_ns[t] + lvl2.NS_MIN)
        atrs = {tf: M.tf[tf]["atr"][M.last(tf, t_ns)] for tf in ("M1", "M5", "M15", "M30")}
        etf, a = entry_tf(atrs)
        if not (np.isfinite(a) and a > 0):
            continue
        x0 = M.c[t]
        fp = first_passage(M.h, M.lo, t, x0 + a, x0 - a, HORIZON)
        signs = [int(M.tf[tf]["trend"][M.last(tf, t_ns)]) for tf in lvl2.trend_tfs(etf)]
        a_side = signs[0] if len(set(signs)) == 1 and signs[0] != 0 else 0
        hh = [int(M.tf[tf]["trend"][M.last(tf, t_ns)]) for tf in ("H1", "H4")]
        ah_side = hh[0] if hh[0] == hh[1] and hh[0] != 0 else 0
        b = lvl2.bounce_at(M, t, p)
        rows.append(dict(t=M.ot[t], etf=etf, fp=fp, A=way(fp, a_side), A_H=way(fp, ah_side),
                         B=way(fp, b["side"]) if b else np.nan))
    G = pd.DataFrame(rows)
    # D: every LV3 signal (3-year table, s 1.5 / n 3) before the exam
    S = pd.read_parquet(HERE / "lvl3_signals_3y_s1.5_n3.parquet")
    d_rows = []
    for r in S.itertuples():
        t = int(r.t)
        if not (START <= M.ot[t] < plib.EXAM_START):
            continue
        x0 = M.c[t]
        fp = first_passage(M.h, M.lo, t, x0 + r.a, x0 - r.a, HORIZON)
        d_rows.append(dict(t=M.ot[t], D=way(fp, int(r.side))))
    Dd = pd.DataFrame(d_rows)
    out = []
    for name, frame, col in (("A every larger TF agrees", G, "A"), ("A-H H1 and H4 agree", G, "A_H"),
                             ("B A + a bounce of >= 1 A", G, "B"), ("D the LV3 signal", Dd, "D")):
        for part, sel in (("2023-09..2024-12", frame.t < SPLIT), ("2025-01..2026-04-17", frame.t >= SPLIT)):
            v = frame.loc[sel, col].dropna()
            q = v.mean() if len(v) else np.nan
            se = np.sqrt(q * (1 - q) / len(v)) if len(v) else np.nan
            out.append(dict(component=name, part=part, n=len(v), its_way=q, se=se, edge_in_se=(q - 0.5) / se))
    pd.set_option("display.width", 200)
    print("first passage of 1 A from the decision close (120 minutes): the component's way vs the other; no effect 50 %")
    print(pd.DataFrame(out).round(3).to_string(index=False))
    unres = (G.fp == 0).mean()
    print(f"\n(grid minutes {len(G)}, unresolved or both in one bar {unres:.1%})")


if __name__ == "__main__":
    main()
