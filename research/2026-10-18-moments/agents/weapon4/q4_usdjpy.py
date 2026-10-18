"""Q4 (design): USDJPY round-72 (0.50 grid) with Q2's limit entry, true grid vs placebos; and the market-entry R-X line
for reference (rx_design.py: 129 trades, +0.044 R).

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/q4_usdjpy.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalw as ev  # noqa: E402
import q2_limit as q2  # noqa: E402
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("USDJPY")
days = w.days_in(*w.DESIGN)
for name, which in (("A72", ["A72"]), ("W11 anchors", ["A72", "A24", "AW", "AS"])):
    print(f"\n== USDJPY limit at the 0.50 grid, {name}")
    for o in (0.0, 0.1, 0.2, 0.25, 0.3, 0.4):
        A = q2.arm_table(P, *w.DESIGN, 0.5, o)
        z = q2.simulate(P, A[q2.anchor_mask(A, which)])
        if not len(z):
            continue
        rn, n = ev.halves(z)
        print(f"  offset {o:4g}: {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}% R {z.R.mean():+.3f}"
              f" kinds {w.plib.kinds(z)} | [{' '.join(f'{v:+.2f}({k})' for v, k in zip(rn, n))}]")
