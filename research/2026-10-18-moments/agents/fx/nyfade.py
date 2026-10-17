"""Step 3a: the New York morning reversal (family D fade), design halves only. Where does the reversal peak, which
pairs, release days vs others, move size, decision time.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/nyfade.py > .../out_nyfade.txt
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
sys.path.insert(0, "research/2026-10-18-moments")
import fxlib as fx  # noqa: E402
import gold  # noqa: E402
import lab  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]
rel = gold.releases()
rel_days = set(pd.to_datetime(rel[rel.time_et == "08:30"].date).dt.date) if "time_et" in rel else set()


def f(v):
    return " ".join(f"{x:+6.3f}" if np.isfinite(x) else "     -" for x in v)


def main() -> None:
    print("release days (08:30 ET) in the calendar:", len(rel_days), sorted(rel.event.unique()))
    print("\n=== A. fade path: mean of -sign(move 08:00->dec) x (price at T - price at dec) in units of H1 ATR,"
          " design, all halves pooled; columns = ET hour T ===")
    Ts = [10.5, 11, 11.5, 12, 13, 14, 15, 16]
    for dec in (9.5, 10, 10.5):
        print(f"-- decision {dec} ET")
        for p in fx.PAIRS:
            P = fx.Pair(p, costs=False)
            ev = lab.events(P, fx.NYC, 8, dec, 16)
            ev = ev[ev.half.isin(H) & np.isfinite(ev.h1_atr)]
            vals = []
            for T in Ts:
                if T <= dec:
                    vals.append(np.nan)
                    continue
                ix = lab.local_index(P, fx.NYC, T)
                px = pd.Series(P.c[ix.to_numpy()], index=ix.index).reindex(ev.day).to_numpy()
                vals.append(np.nanmean(-np.sign(ev.move.to_numpy()) * (px - ev.px.to_numpy()) / ev.h1_atr.to_numpy()))
            print(f"  {p}  {f(vals)}")

    print("\n=== B. trades: fade at the decision, stop k x ATR, time exit at T ET; gross / net R by half ===")
    for p in fx.PAIRS:
        Pn, Pg = fx.Pair(p), fx.Pair(p, costs=False)
        for dec, T in ((9.5, 12), (10, 12), (10, 14), (9.5, 14), (10.5, 15)):
            ev = lab.events(Pn, fx.NYC, 8, dec, T)
            ev = ev[ev.half.isin(H) & np.isfinite(ev.h1_atr)].reset_index(drop=True)
            ev["rel"] = [d.date() in rel_days for d in ev.day]
            q = ev.move.abs() / ev.h1_atr
            side = -np.sign(ev.move.to_numpy()).astype(int)
            for k in (2.0, 3.0):
                sl = k * ev.h1_atr.to_numpy()
                zg = lab.simulate(Pg, ev, side, sl, None)
                zn = lab.simulate(Pn, ev, side, sl, None)
                zn["Rg"] = zg.R.to_numpy()
                zn["q"] = q.to_numpy()[zn.ev]
                zn["rel"] = ev.rel.to_numpy()[zn.ev]
                for lab_, m in (("all", zn.q >= 0), ("q>=1", zn.q >= 1), ("q>=1.5", zn.q >= 1.5),
                                ("rel", zn.rel), ("norel q>=1", (~zn.rel) & (zn.q >= 1))):
                    z = zn[m]
                    gh = [z[z.half == h].Rg.mean() for h in H]
                    nh = [z[z.half == h].R.mean() for h in H]
                    print(f"  {p} dec {dec:4} exit {T:2} k{k} {lab_:11s} n={len(z):4d} gross {z.Rg.mean():+.3f} "
                          f"[{f(gh)}] net {z.R.mean():+.3f} pos {sum(np.array(nh) > 0)}/5 win {100 * (z.pips > 0).mean():.0f}%")
        print()


if __name__ == "__main__":
    main()
