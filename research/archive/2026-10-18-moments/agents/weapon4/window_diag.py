"""Diagnostics after the window run (no rule chosen here): W5a's gross R on the window; F1 v2's own 35 window
trades split by whether the round frame (xx00 / xx50 level, at it, PA) fires on the same minute; the same split for
F1 v1 on design.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/window_diag.py
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
a, b = w.WINDOW
D = w.build(P, 1, a, b, [(0, 20)], "XAUUSD_M1_window")
R = w.build(P, 1, a, b, [(0, 20)], "XAUUSD_M1_window_round0", kinds=["round"], round_offset=0.0)
X = D.copy()
X["n_ind"] = 2
S5 = w.signals(X, 3, 10, 8, 0.6, 60)
z = w.run(S5, P)
zg = ev.gross(S5, P, False)
print(f"W5a window: net {z.R.mean():+.3f}, gross {zg.R.mean():+.3f} (costs {z.R.mean() - zg.R.mean():+.3f} R)")
h = pd.DatetimeIndex(D.t).hour
f1w = ((h >= 0) & (h < 2)) | ((h >= 7) & (h < 17))
S1 = w.signals(D[f1w], 3, 10, 8, 0.6, 60)
rk = set(zip(R.t, R.side))  # round rows (tide + at the round level), before PA / C4
rk_pa = set(zip(R[R.pa].t, R[R.pa].side))
for lab, zz in (("F1 v1", w.run(S1, P)), ("F1 v2", w.run_v2(S1, P))):
    at = np.array([(t, s) in rk_pa for t, s in zip(zz.t, zz.side)])
    near = np.array([(t, s) in rk for t, s in zip(zz.t, zz.side)])
    print(f"{lab} window: {len(zz)} trades {zz.usd.sum():+.1f} USD R {zz.R.mean():+.3f} | at a round 50 (frame + PA) {at.sum()}:"
          f" R {zz[at].R.mean():+.3f} USD {zz[at].usd.sum():+.1f} win {100 * zz[at].exit.isin(['win', 'trail']).mean():.0f}% |"
          f" not {(~at).sum()}: R {zz[~at].R.mean():+.3f} USD {zz[~at].usd.sum():+.1f} win {100 * zz[~at].exit.isin(['win', 'trail']).mean():.0f}%"
          f" | (round frame without PA: {near.sum()})")
# design: F1 v1 split the same way
Dd = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design")
Rd = w.build(P, 1, *w.DESIGN, [(0, 20)], "XAUUSD_M1_design_round0", kinds=["round"], round_offset=0.0)
hd = pd.DatetimeIndex(Dd.t).hour
S1d = w.signals(Dd[((hd >= 0) & (hd < 2)) | ((hd >= 7) & (hd < 17))], 3, 10, 8, 0.6, 60)
rkd = set(zip(Rd[Rd.pa].t, Rd[Rd.pa].side))
for lab, zz in (("F1 v1", w.run(S1d, P)), ("F1 v2", w.run_v2(S1d, P))):
    at = np.array([(t, s) in rkd for t, s in zip(zz.t, zz.side)])
    zz["half"] = w.plib.half_of(zz.t)
    hr_at = zz[at].R.groupby(zz[at].half).mean().reindex(ev.HN)
    hr_no = zz[~at].R.groupby(zz[~at].half).mean().reindex(ev.HN)
    print(f"{lab} design: at a round 50 {at.sum()} R {zz[at].R.mean():+.3f} [{' '.join(f'{v:+.2f}' for v in hr_at)}] |"
          f" not {(~at).sum()} R {zz[~at].R.mean():+.3f} [{' '.join(f'{v:+.2f}' for v in hr_no)}]")
