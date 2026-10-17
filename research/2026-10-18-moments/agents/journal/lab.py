"""The journal agent's rule lab on DESIGN data (2023-11 .. 2026-02, by half-year) against a coin-flip side on the
same minutes. Each rule is written in notes.md before it is run here.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/journal/lab.py SYM RULE [RULE ...] [--save]

--save writes the trades of the last half-year (2025-09 .. 2026-02) to trades_<SYM>_<RULE>.parquet for the charts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jlib  # noqa: E402
from rules import RULES, signals  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sym, names = args[0], args[1:]
    save = "--save" in sys.argv
    jlib.gold.below_normal_priority()
    P = jlib.Instr(sym)
    if "--gross" in sys.argv:
        P.gross()
        print("GROSS (no costs)")
    part = next((a.split("=")[1] for a in sys.argv if a.startswith("--part=")), "design")
    D = jlib.cands(sym, part)
    print(f"candidates: {part}")
    D["e"] = P.e_of(D.t)
    for name in names:
        rule = RULES[name]
        sig = signals(D, rule, P)
        print(f"\n{sym} rule {name}: {rule['doc']}")
        print(f"  signal rows {len(sig)}; tp {rule['tp']} U, be {rule['be']}, hz {rule['hz']}, stop {rule['rmin']}-{rule['rmax']} U")
        print("  window                trades /day  win     R/trade   P&L            months+  kinds 1/2/3 | coin: R (sd)  kinds  trades")
        tot, totc = [], []
        for hn, a, b in jlib.HALVES:
            x = sig[(sig.t >= pd.Timestamp(a, tz="UTC")) & (sig.t < pd.Timestamp(b, tz="UTC"))]
            kw = dict(per_sess=rule.get("per_sess", 2), once=rule.get("once", False))
            r = jlib.run(x, P, rule["tp"], rule["be"], rule["hz"], **kw)
            cs = jlib.coin_stats(x, P, rule["tp"], rule["be"], rule["hz"], seeds=10, **kw)
            unit = "USD" if sym == "XAUUSD" else "pips"
            print(jlib.line(hn, r, a, b, P, unit) + f" | {cs['R']:+.3f} ({cs['sd']:.3f}) {cs['kinds']} {cs['n']:.0f}")
            if len(r):
                r["half"] = hn
                tot.append(r)
            totc.append(cs["R"])
        allr = pd.concat(tot) if tot else pd.DataFrame()
        if len(allr):
            print(f"  ALL design: {len(allr)} trades, win {100 * (allr.exit == 'win').mean():.0f}%, {allr.R.mean():+.3f} R/trade,"
                  f" halves+ {(allr.groupby('half').R.mean() > 0).sum()}/{allr.half.nunique()}, coin mean {np.nanmean(totc):+.3f} R;"
                  f" exits {allr.exit.value_counts().to_dict()}")
            print("    account: " + jlib.account(allr, P))
            for s, g in allr.groupby("session"):
                print(f"    {jlib.SESS[int(s)]:8} {len(g):4} trades  win {100 * (g.exit == 'win').mean():3.0f}%  {g.R.mean():+.3f} R")
        if save and len(allr):
            last = allr[allr.half == jlib.HALVES[-1][0]].copy()
            extra = sig.loc[last.idx.to_numpy()].reset_index(drop=True)
            last = last.reset_index(drop=True)
            for col in extra.columns:
                if col not in last.columns:
                    last[col] = extra[col].to_numpy()
            last.to_parquet(HERE / f"trades_{sym}_{name}{'_w' if part.startswith('w') else ''}.parquet")
            allx = allr.reset_index(drop=True)
            extra = sig.loc[allx.idx.to_numpy()].reset_index(drop=True)
            for col in extra.columns:
                if col not in allx.columns:
                    allx[col] = extra[col].to_numpy()
            allx.to_parquet(HERE / f"trades_all_{sym}_{name}{'_w' if part.startswith('w') else ''}.parquet")


if __name__ == "__main__":
    main()
