"""W6 on design: the retest of a broken 72-hour extreme, gold M1 00-20 UTC (notes.md W6).

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w6_design.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402
import w6lib  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
days = w.days_in(*w.DESIGN)
S = w6lib.signals(P, *w.DESIGN, [(0, 20)])
z = w.run(S, P)
print(w.summary(z, days, "W6 retest of the 72-h break"))
print(w.coin_line(S, P, z))
print("    " + w.account(z) + f"; exits {z.exit.value_counts().to_dict()}")
