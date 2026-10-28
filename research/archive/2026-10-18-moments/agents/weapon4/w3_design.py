"""W3a on design: the F1 frame on M1 (W1's rule: 8 U, BE 0.6, 60 min, stop 3-10 U + the 0.5 M15-ATR floor, C4 < 4
U, C5) on other markets, 1 U = the market's trailing 28-day median M1 ATR / 1.63; costs from its spread column with
gold's ratios. Hours: US100 / US30 / US500 13:30-20:00 UTC; JP225 00:00-06:00 + 13:30-20:00; XAUAUD 00:00-20:00.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/w3_design.py [SYM ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w4lib as w  # noqa: E402

HOURS = {"US100": [(13.5, 20)], "US30": [(13.5, 20)], "US500": [(13.5, 20)], "JP225": [(0, 6), (13.5, 20)],
         "XAUAUD": [(0, 20)]}
w.jlib.gold.below_normal_priority()
days = w.days_in(*w.DESIGN)
for sym in sys.argv[1:] or list(HOURS):
    P = w.instr(sym)
    D = w.build(P, 1, *w.DESIGN, HOURS[sym], f"{sym}_M1_design")
    print(f"\n== {sym}: spread {P.sp0[-200000:].mean():.4g} (+{w.jlib.SPEC[sym]['extra']:.3g}), slip {P.slip:.3g},"
          f" stop slip {P.stop_slip:.3g}; median unit {D.unit.median():.4g}; 8 U = {8 * D.unit.median():.4g}")
    for c4 in (4.0, None):
        S = w.signals(D, 3, 10, 8, 0.6, 60, c4=c4)
        z = w.run(S, P)
        print(w.summary(z, days, f"{sym} C4 {c4}"))
        if c4 and len(z) > 10:
            print(w.coin_line(S, P, z))
            print("    " + w.account(z) + f"; exits {z.exit.value_counts().to_dict()}")
            # gross: what costs take
            sp, sl, ss, ssn = P.sp.copy(), P.slip, P.stop_slip, P.stop_slip_ny
            P.gross()
            zg = w.run(S, P)
            P.sp, P.slip, P.stop_slip, P.stop_slip_ny = sp, sl, ss, ssn
            print(f"    gross (no costs) R {zg.R.mean():+.3f}")
