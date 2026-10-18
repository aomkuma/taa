"""Q1 (design): the round frame with other anchors in place of the 72-h extreme; round 50 and round 100 grids vs
placebo grids (notes.md "Follow-up").

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/q1_anchors.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402

w.jlib.gold.below_normal_priority()
P = w.instr("XAUUSD")
days = w.days_in(*w.DESIGN)
ANCH = ["A72", "A24", "AW", "AS", "AY"]
GRIDS = {50: [0, 10, 20, 25, 30, 40], 100: [0, 20, 40, 50, 60, 80]}


def sig(D, anchor, x=4.0):
    S = w.signals(D, 3, 10, 8, 0.6, 60, c4=None)
    m = (S[f"d_{anchor}"] < x).to_numpy()
    return S[m].reset_index(drop=True)


for step, offs in GRIDS.items():
    T = w.build_round_multi(P, *w.DESIGN, [(0, 20)], f"XAUUSD_M1_design_rgrid{step if step != 50 else ''}", float(step),
                            [float(o) for o in offs])
    T = {o: w.add_anchors(d, P) for o, d in T.items()}
    print(f"\n######## round {step} grid (true = offset 0; placebos {offs[1:]})")
    for a in ANCH:
        res = {}
        for o in offs:
            S = sig(T[float(o)], a)
            if len(S) < 3:
                res[o] = None
                continue
            z = w.run(S, P)
            zg = ev.gross(S, P, False)
            res[o] = (S, z, zg)
        S0, z0, zg0 = res[0]
        rn, n = ev.halves(z0)
        pl = [r for o, r in res.items() if o != 0 and r is not None and not (step == 100 and o == 50)]
        pn, pg = np.mean([r[1].R.mean() for r in pl]), np.mean([r[2].R.mean() for r in pl])
        c = w.plib.coin(S0, P, seeds=10)
        z0 = z0.merge(S0[["t", "side", "d_A72"]], on=["t", "side"])
        beyond = z0[z0.d_A72 >= 4]
        rb, nb = ev.halves(beyond) if len(beyond) else (np.full(5, np.nan), np.zeros(5, int))
        okh = [v > 0 for v, k in zip(rn, n) if k >= 5]
        passed = z0.R.mean() >= 0.15 and zg0.R.mean() - pg >= 0.15 and sum(okh) >= 3
        print(f"\n  {a}: {len(z0)} ({len(z0) / days:.2f}/d) win {100 * (z0.exit == 'win').mean():.0f}% (coin {100 * c['win']:.0f})"
              f" net {z0.R.mean():+.3f} gross {zg0.R.mean():+.3f} coin {c['R']:+.3f} USD {z0.usd.sum():+.1f} |"
              f" placebo mean {pn:+.3f} / {pg:+.3f} | {'PASS' if passed else 'fail'}")
        print(f"     halves [{' '.join(f'{v:+.2f}({k})' for v, k in zip(rn, n))}]  kinds {w.plib.kinds(z0)} / coin {c['kinds']}")
        print("     placebos net: " + " ".join(f"{o}:{r[1].R.mean():+.2f}({len(r[1])})" for o, r in res.items() if o != 0 and r is not None))
        print(f"     not near the 72-h extreme (d_A72 >= 4 U): {len(beyond)} ({len(beyond) / days:.2f}/d) net {beyond.R.mean():+.3f}"
              f" [{' '.join(f'{v:+.2f}({k})' for v, k in zip(rb, nb))}]")
