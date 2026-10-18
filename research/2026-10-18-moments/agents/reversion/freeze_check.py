"""A step as a Lab config: by half-year (or the test once with --test) with the seeded coin, cost in R, account."""
import sys, warnings
import numpy as np, pandas as pd
from common import SLIP
from diag import RULES, situations
from exp import Lab
from steps import STEPS, masks, account
warnings.filterwarnings("ignore")


def cfg_for(L, S, geom, names):
    M = masks(L, S)
    fs = [M[n] for n in names]
    def extra(F, side):
        ok = (L.B.ny_min < 930) & (L.B.ldn_min >= 420)
        for f in fs:
            ok &= f(F, side)
        return ok
    return dict(RULES[geom]) | dict(extra=extra)


if __name__ == "__main__":
    geom, step = sys.argv[1], sys.argv[2]
    test = "--test" in sys.argv
    L = Lab(); S = situations(L)
    cfg = cfg_for(L, S, geom, dict(STEPS)[step])
    o = L.run(cfg, test=test, coin_seeds=5, months=True)
    t = L.last_trades
    sp = L.B.sp[t.f.to_numpy()]
    cost = ((sp + 0.08) + np.where(t.exit == "stop", 0.17, 0.0)) / (t.sl + SLIP)
    print(f"cost in R (spread + 0.08 + stop slippage, last window): {cost.mean():.3f}")
    a = account(t.assign(t=L.B.ot[t.i.to_numpy()]))
    print("account:", {k: round(float(v), 2) for k, v in a.items()})
    pd.set_option("display.width", 250)
    print(L.last_months.round(3).to_string())
