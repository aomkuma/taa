"""Round-number break-through with stop orders on FX: wider geometry (development; notes.md round 6)."""
import sys, warnings
import numpy as np
import sim
from common import DEV, TEST, gold
from fx import FXBars, round_exp
warnings.filterwarnings("ignore")
gold.below_normal_priority()
windows = TEST if "--test" in sys.argv else DEV
for pair in ("EURUSD", "GBPUSD", "USDJPY", "USDCHF"):
    B = FXBars(pair)
    sim.COST.update(xsp=0.2 * B.pip, stop_slip=0.2 * B.pip, stop_slip_ny=0.2 * B.pip, slip=0.2 * B.pip, tick=B.point)
    for sl, tp, hold, D in ((20, 30, 480, 20), (30, 30, 480, 20), (20, 40, 600, 20), (30, 30, 480, 10)):
        res = round_exp(B, windows, D=D, sl=sl, tp=tp, hold=hold)
        r = res["round"][1]
        p = (res["p37"][1].R + res["p63"][1].R) / 2
        beats = int((r.R > res["p37"][1].R).sum() + (r.R > res["p63"][1].R).sum())
        print(f"{pair} through {sl}/{tp} {hold}m D{D}: R " + " ".join(f"{v:+.3f}" for v in r.R)
              + f" | mean {r.R.mean():+.3f} placebo {p.mean():+.3f} beats {beats}/{2 * len(r)} | n {int(r.n.sum())}"
              f" ({r.n.sum() / 600:.2f}/d) pips {r.pips.sum():+.0f}", flush=True)
