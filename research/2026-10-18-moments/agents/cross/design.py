"""Agent "cross", step 4: trades on the design data (2023-11-01 .. 2026-03-01, five halves), real costs.

Families (the directions come from step 1b / 3b, measured before any trade was simulated):
  LDN  - London 07:00-12:00 UTC: equities up -> the dollar up (EURUSD/GBPUSD sell; USDCHF/USDCAD/USDJPY buy), and
         the mirror when equities fall. Gold: equities up -> gold down (the dollar up).
  LATE - 17:00-20:00 UTC: equities up -> the dollar down (USDCHF/USDCAD sell; GBPUSD/EURUSD buy); gold up.
Signal: |z| of the input's last L minutes >= thr (first minute, then silent 60 minutes), z = equities' (mean of
US500 and JP225) or US100's vol-scaled move. Grid: input x thr x target/stop x hold x break-even. Each cell also
with a coin side on the same minutes (20 seeds).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/design.py
"""

from __future__ import annotations

import itertools
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from fxlab import Inst, kinds, run  # noqa: E402
from measure import HALVES, PANEL, scaled_returns  # noqa: E402
from screen import episodes  # noqa: E402

FAM = {
    "LDN": dict(hours=(7, 12), side={"EURUSD": -1, "GBPUSD": -1, "USDCHF": 1, "USDCAD": 1, "USDJPY": 1, "XAUUSD": -1}),
    "LATE": dict(hours=(17, 20), side={"EURUSD": 1, "GBPUSD": 1, "USDCHF": -1, "USDCAD": -1, "XAUUSD": 1}),
}
PLANS_FX = [(15, 15), (20, 15), (20, 20), (25, 20), (15, 10)]
PLANS_AU = [(5, 5), (8, 6), (10, 8)]
LO, HI = pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")


def signals() -> dict[str, pd.Series]:
    p = pd.read_parquet(PANEL)
    t_ns = p.index.as_unit("ns").asi8
    out = {}
    for L in (30, 60):
        out[f"eq{L}"] = pd.Series((scaled_returns(p, "US500", L, -1, t_ns) + scaled_returns(p, "JP225", L, -1, t_ns)) / 2, index=p.index)
    out["US100_60"] = pd.Series(scaled_returns(p, "US100", 60, -1, t_ns), index=p.index)
    return out


def fires(z: pd.Series, hours: tuple[int, int], thr: float, lo: pd.Timestamp, hi: pd.Timestamp) -> pd.Series:
    h = z.index.hour
    zz = z.where((h >= hours[0]) & (h < hours[1]) & (z.index >= lo) & (z.index < hi) & (z.index.dayofweek < 5))
    ix = episodes(zz, thr)
    return z.iloc[ix]


def evaluate(inst: Inst, f: pd.Series, dirn: int, tp: float, sl: float, be: float | None, hz: int, coins: int = 20) -> dict:
    d = inst.index_at(f.index)
    sides = (np.sign(f.to_numpy()) * dirn).astype(int)
    r = run(inst, d, sides, tp, sl, be, hz, f.index)
    if not len(r):
        return {}
    rng = np.random.default_rng(7)
    cr, cw, ck = [], [], []
    for _ in range(coins):
        c = run(inst, d, rng.choice([-1, 1], len(d)), tp, sl, be, hz, f.index)
        cr.append(c.R.mean())
        cw.append(100 * (c.exit == "win").mean())
        ck.append(c)
    out = dict(n=len(r), win=100 * (r.exit == "win").mean(), R=r.R.mean(), pips=r.pnl.mean(), coinR=np.mean(cr),
               coin_win=np.mean(cw), kinds=kinds(r), coin_kinds=kinds(pd.concat(ck)), longR=r.R[r.side > 0].mean(),
               shortR=r.R[r.side < 0].mean())
    pos = 0
    for n, a, b in HALVES:
        m = (r.t >= pd.Timestamp(a, tz="UTC")) & (r.t < pd.Timestamp(b, tz="UTC"))
        out[n] = r.R[m].mean() if m.any() else np.nan
        pos += out[n] > 0
    out["pos"] = pos
    out["gross"] = (r.pnl + 0).mean()
    return out


def main() -> None:
    gold.below_normal_priority()
    sig = signals()
    insts = {}
    rows = []
    for fam, spec in FAM.items():
        for sym, dirn in spec["side"].items():
            inst = insts.setdefault(sym, Inst(sym))
            plans = PLANS_AU if sym == "XAUUSD" else PLANS_FX
            for sname, thr in itertools.product(sig, (2.0, 2.5)):
                f = fires(sig[sname], spec["hours"], thr, LO, HI)
                for (tp, sl), hz, be in itertools.product(plans, (120, 180), (None, 0.6)):
                    o = evaluate(inst, f, dirn, tp, sl, be, hz)
                    if o:
                        rows.append(dict(fam=fam, sym=sym, sig=sname, thr=thr, tp=tp, sl=sl, hz=hz, be=be, **o))
            print(fam, sym, "done", flush=True)
    r = pd.DataFrame(rows)
    r.to_csv("research/2026-10-18-moments/agents/cross/design.csv", index=False)
    pd.set_option("display.width", 280)
    pd.set_option("display.max_rows", 400)
    cols = ["fam", "sym", "sig", "thr", "tp", "sl", "hz", "be", "n", "win", "coin_win", "R", "coinR", "pips", "pos",
            "23-11", "24-05", "24-11", "25-05", "25-11", "longR", "shortR", "kinds", "coin_kinds"]
    print("\nfamily x symbol: mean over all cells (robustness, not the best cell)")
    print(r.groupby(["fam", "sym"])[["R", "coinR", "win", "coin_win", "pos"]].mean().round(3).to_string())
    print("\ncells with pos >= 4, by R")
    print(r[r.pos >= 4].sort_values("R", ascending=False)[cols].head(60).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
