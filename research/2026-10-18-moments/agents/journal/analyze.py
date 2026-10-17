"""Check a journal lesson by numbers: a rule's design trades (ours and the coin's, 10 seeds, on the same minutes)
split by a context feature in quantile bins; the charted half-year (2025-09 .. 2026-02) and the earlier ones
(2023-11 .. 2025-08, never charted) apart.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/journal/analyze.py SYM RULE feat [feat ...]
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

CUT = pd.Timestamp("2025-09-01", tz="UTC")


def main() -> None:
    sym, name, feats = sys.argv[1], sys.argv[2], sys.argv[3:]
    jlib.gold.below_normal_priority()
    P = jlib.Instr(sym)
    D = jlib.cands(sym, "design")
    D["e"] = P.e_of(D.t)
    rule = RULES[name]
    sig = signals(D, rule, P)
    sig["room_tp"] = sig.room / (rule["tp"] * sig.unit)
    sig["sl_atr"] = sig.sl / sig.atr1
    ours = jlib.run(sig, P, rule["tp"], rule["be"], rule["hz"])
    coins = [jlib.run(sig, P, rule["tp"], rule["be"], rule["hz"], coin=np.random.default_rng(200 + s)) for s in range(10)]
    coin = pd.concat(coins, ignore_index=True)
    for z in (ours, coin):
        for f in feats + ["room_tp", "sl_atr"]:
            z[f] = sig.loc[z.idx.to_numpy(), f].to_numpy()
        z["early"] = z.t < CUT
    for f in feats:
        x = ours[f]
        if x.nunique() <= 6:
            ours["bin"], coin["bin"] = ours[f].astype(str), coin[f].astype(str)
        else:
            q = np.unique(np.nanquantile(x, [0, 0.2, 0.4, 0.6, 0.8, 1.0]))
            ours["bin"] = pd.cut(ours[f], q, include_lowest=True).astype(str)
            coin["bin"] = pd.cut(coin[f], q, include_lowest=True).astype(str)
        print(f"\n{name} by {f}:   n  ours R  win%  coin R  win%  | earlier halves: n  ours R  coin R | 2025-09..02: n  ours R  coin R")
        for b, g in ours.groupby("bin", sort=True):
            c = coin[coin.bin == b]
            ge, ce = g[g.early], c[c.early]
            gl, cl = g[~g.early], c[~c.early]
            print(f"  {b:22} {len(g):4} {g.R.mean():+.3f} {100 * (g.exit == 'win').mean():4.0f}  {c.R.mean():+.3f} {100 * (c.exit == 'win').mean():4.0f}"
                  f"  | {len(ge):4} {ge.R.mean():+.3f} {ce.R.mean():+.3f} | {len(gl):4} {gl.R.mean():+.3f} {cl.R.mean():+.3f}")


if __name__ == "__main__":
    main()
