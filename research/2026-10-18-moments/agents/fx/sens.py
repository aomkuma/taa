"""Step 6: is V7b a knife edge? One parameter at a time around V7b (design halves only), plus the January 2026
event count check.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/sens.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import fxlib as fx  # noqa: E402
import lab  # noqa: E402
import reltrades as rt  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]
PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]


def v7(Ps, period, dec=10.0, exit_h=14.0, stall=0.10, extra=0.5, qmin=1.0, usd_cap=None):
    out = []
    for p in PAIRS:
        P = Ps[p]
        ev = rt.build(P, dec, exit_h)
        ev = ev[ev.half.isin(period) & ev.rel].reset_index(drop=True)
        atr = ev.h1_atr.to_numpy()
        q = np.abs(ev.move.to_numpy()) / atr
        side = -np.sign(ev.move.to_numpy()).astype(int)
        side[q < qmin] = 0
        ext = np.where(side < 0, ev.whi.to_numpy(), ev.wlo.to_numpy())
        back = np.abs(ext - ev.px.to_numpy()) / (ev.whi - ev.wlo).to_numpy()
        side[back <= stall] = 0
        sl = np.maximum(np.abs(ext - ev.px.to_numpy()) + extra * atr, atr)
        if usd_cap is not None:
            side[sl * P.usd_pip[ev.d.to_numpy()] > usd_cap] = 0
        z = lab.simulate(P, ev, side, sl, None)
        if len(z):
            z["pair"] = p
            z["day"] = ev.day.to_numpy()[z.ev]
            out.append(z)
    return pd.concat(out, ignore_index=True)


def line(name, z):
    nh = [z[z.half == h].R.mean() for h in H]
    print(f"  {name:28s} n={len(z):4d} win {100 * (z.pips > 0).mean():3.0f}% net {z.R.mean():+.3f} "
          f"pos {sum(np.array(nh) > 0)}/5 | {rt.f(nh)} | USD {z.usd.sum():+6.1f}")


def main() -> None:
    Ps = {p: fx.Pair(p) for p in PAIRS}
    line("V7b base", v7(Ps, H))
    for s in (0.05, 0.15, 0.20, 0.30):
        line(f"stall {s}", v7(Ps, H, stall=s))
    for d in (9.75, 10.25, 10.5):
        line(f"decision {d} ET", v7(Ps, H, dec=d))
    for x in (13, 15, 16):
        line(f"exit {x} ET", v7(Ps, H, exit_h=x))
    for e in (0.25, 1.0):
        line(f"stop extra {e} ATR", v7(Ps, H, extra=e))
    for q in (0.5, 1.5):
        line(f"move >= {q} ATR", v7(Ps, H, qmin=q))
    line("usd cap 4 per trade", v7(Ps, H, usd_cap=4.0))
    # January 2026: release days and how many pass each condition
    for p in ("EURUSD", "GBPUSD"):
        ev = rt.build(Ps[p], 10, 14)
        ev = ev[(ev.t >= pd.Timestamp("2026-01-01", tz="UTC")) & (ev.t < pd.Timestamp("2026-02-01", tz="UTC")) & ev.rel]
        ext = np.where(ev.move > 0, ev.whi, ev.wlo)
        print(p, "Jan 2026 release days", len(ev), "q:", (ev.move.abs() / ev.h1_atr).round(2).tolist(),
              "back:", (np.abs(ext - ev.px) / (ev.whi - ev.wlo)).round(2).tolist())


if __name__ == "__main__":
    main()
