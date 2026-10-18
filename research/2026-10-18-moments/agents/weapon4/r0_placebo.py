"""R0 / R1 / R2 on design (notes.md "R-series"): the round-number frame at offsets 0 (true round) and 10-40 (placebo
grids), C4 < 4 U / < 8 U / none; xx00 vs xx50.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/r0_placebo.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402
from gross_check import coin_halves, gross_run, halves  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
days = w.days_in(*w.DESIGN)


def line(label, S):
    z = w.run(S, P)
    zg = gross_run(S, P)
    rn, n = halves(z)
    rg, _ = halves(zg)
    c = w.plib.coin(S, P, seeds=10)
    print(f"  {label:22} {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}% net {z.R.mean():+.3f}"
          f" gross {zg.R.mean():+.3f} coin {c['R']:+.3f} (win {100 * c['win']:.0f}%) | net [{' '.join(f'{v:+.2f}' for v in rn)}]"
          f" gross+>=.10 {np.sum(rg >= 0.10)}/5 | n [{' '.join(str(k) for k in n)}]")
    return z


for o in (0, 10, 20, 25, 30, 40):
    D = w.build(P, 1, *w.DESIGN, [(0, 20)], f"XAUUSD_M1_design_round{o}", kinds=["round"], round_offset=float(o))
    print(f"\n== offset {o} ({'TRUE ROUND' if o == 0 else 'placebo'}), rows {len(D)}")
    for c4 in (4.0, 8.0, None):
        S = w.signals(D, 3, 10, 8, 0.6, 60, c4=c4)
        z = line(f"C4 {c4}", S)
        if o == 0 and c4 == 4.0:
            S100 = S[(S.level % 100).round(6) == 0]
            S50 = S[(S.level % 100).round(6) == 50]
            line("  xx00 only", S100)
            line("  xx50 only", S50)
