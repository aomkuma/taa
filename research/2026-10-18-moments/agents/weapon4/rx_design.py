"""R-X on design (notes.md "R-X"): round-72 (W7's frame) on other markets, the true round grid vs five placebo grids.
First checks that build_round_multi reproduces build(kinds=["round"]) on gold.

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/rx_design.py [SYM ...]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402

FX = [(0, 20)]
US = [(13.5, 20)]
MARKETS = {  # symbol: (round step, hours)
    "XAUUSD": (50.0, [(0, 20)]),
    "EURUSD": (0.005, FX), "GBPUSD": (0.005, FX), "AUDUSD": (0.005, FX), "NZDUSD": (0.005, FX),
    "USDCAD": (0.005, FX), "USDCHF": (0.005, FX), "USDJPY": (0.5, FX),
    "US500": (50.0, US), "US100": (250.0, US), "US30": (250.0, US), "JP225": (500.0, [(0, 6), (13.5, 20)]),
    "XAUAUD": (50.0, [(0, 20)]),
}
FR = [0.0, 0.2, 0.4, 0.5, 0.6, 0.8]
days = w.days_in(*w.DESIGN)


def run_one(P, S):
    z = w.run(S, P)
    zg = ev.gross(S, P, False)
    return z, zg


def main():
    w.jlib.gold.below_normal_priority()
    syms = sys.argv[1:] or list(MARKETS)
    pooled = []
    for sym in syms:
        step, hours = MARKETS[sym]
        P = w.instr(sym)
        T = w.build_round_multi(P, *w.DESIGN, hours, f"{sym}_M1_design_rgrid", step, [f * step for f in FR])
        if sym == "XAUUSD":
            for o in (0.0, 25.0):
                ref = w.build(P, 1, *w.DESIGN, [(0, 20)], f"XAUUSD_M1_design_round{o:g}", kinds=["round"], round_offset=o)
                a = w.signals(ref, 3, 10, 8, 0.6, 60, c4=4.0)
                b = w.signals(T[o], 3, 10, 8, 0.6, 60, c4=4.0)
                print(f"  check gold o={o:g}: build {len(a)} signals, multi {len(b)}, common {len(set(zip(a.t, a.side)) & set(zip(b.t, b.side)))}")
        res = {}
        for f in FR:
            S = w.signals(T[f * step], 3, 10, 8, 0.6, 60, c4=4.0)
            if not len(S):
                res[f] = None
                continue
            z, zg = run_one(P, S)
            res[f] = (S, z, zg)
        if res[0.0] is None:
            print(f"\n== {sym}: no true-grid trades")
            continue
        S0, z0, zg0 = res[0.0]
        rn, n = ev.halves(z0)
        pl = [(r[1].R.mean(), r[2].R.mean(), len(r[1])) for f, r in res.items() if f > 0 and r is not None]
        pl_net = np.mean([x[0] for x in pl]) if pl else np.nan
        pl_gross = np.mean([x[1] for x in pl]) if pl else np.nan
        ok_h = [(v > 0) for v, k in zip(rn, n) if k >= 5]
        passed = (zg0.R.mean() - pl_gross >= 0.15) and (z0.R.mean() >= 0.10) and (sum(ok_h) >= 3)
        c = w.plib.coin(S0, P, seeds=10)
        print(f"\n== {sym} (step {step:g}; 8 U ~ {8 * S0.unit.median():.4g}; spread med {np.median(P.sp0[-300000:]):.3g} + "
              f"{w.jlib.SPEC[sym]['extra']:.3g})")
        print(f"  true grid: {len(z0)} ({len(z0) / days:.2f}/d) win {100 * (z0.exit == 'win').mean():.0f}% (coin {100 * c['win']:.0f})"
              f" net {z0.R.mean():+.3f} gross {zg0.R.mean():+.3f} coin {c['R']:+.3f} | halves [{' '.join(f'{v:+.2f}({k})' for v, k in zip(rn, n))}]")
        print("  placebo grids (net / gross / n): " + "; ".join(
            f"{f:g}: {r[1].R.mean():+.3f} / {r[2].R.mean():+.3f} / {len(r[1])}" if r is not None else f"{f:g}: -" for f, r in res.items() if f > 0)
            + f" | mean {pl_net:+.3f} / {pl_gross:+.3f}")
        print(f"  -> {'PASS' if passed else 'fail'} (gross over the placebo {zg0.R.mean() - pl_gross:+.3f}, net {z0.R.mean():+.3f},"
              f" halves+ {sum(ok_h)}/{len(ok_h)})")
        if sym != "XAUUSD":
            pooled.append(z0.assign(sym=sym, Rg=np.nan))
    if pooled:
        Z = pd.concat(pooled, ignore_index=True)
        rn, n = ev.halves(Z)
        print(f"\n== pooled (no gold): {len(Z)} trades ({len(Z) / days:.2f}/d) net {Z.R.mean():+.3f}"
              f" [{' '.join(f'{v:+.2f}({k})' for v, k in zip(rn, n))}]")
        print("  by market: " + ", ".join(f"{s} {len(g)} {g.R.mean():+.3f}" for s, g in Z.groupby("sym")))


if __name__ == "__main__":
    main()
