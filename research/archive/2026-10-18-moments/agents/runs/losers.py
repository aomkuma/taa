"""Why RUN-A (A4) loses: every trade tagged with the situations a trader would name, counted among the full losers
and the winners, design and window (the window only described, the rule stays frozen).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/losers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402


def main() -> None:
    P = rules.jlib.Instr("XAUUSD")
    F = pd.read_parquet(HERE / "feats.parquet", columns=["m15_struct", "m15_tide", "m5_tide", "atr15_u", "d_dhi", "d_dlo",
                                                         "min_to_rel", "min_since_rel", "ret120"])
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[C.R == 15].set_index(["t", "side"])
    rel = pd.DatetimeIndex(rules.gold.releases().t).sort_values()
    for part in ("design", "window"):
        z = pd.read_parquet(HERE / f"trades_A4_{part}.parquet")
        s = z.side.to_numpy()
        dec = P.ot[z.e.to_numpy() - 1]
        X = F.reindex(dec).reset_index(drop=True)
        key = pd.MultiIndex.from_arrays([pd.DatetimeIndex(z.run_t), z.side.to_numpy()])
        z["run_atr"] = C.size_atr.reindex(key).to_numpy()
        tags = {}
        # 1 the run's start was broken within 120 min after the entry (the run was the end of the swing: a V)
        vrev = []
        for r in z.itertuples():
            seg = slice(r.e, min(r.e + 120, len(P.o)))
            vrev.append(bool(((P.lo[seg] < r.start).any()) if r.side > 0 else ((P.h[seg] > r.start).any())))
        tags["V: the run's start broken within 120 min"] = np.array(vrev)
        tags["M15 swing structure against"] = (np.abs(X.m15_struct) == 1) & (X.m15_struct * s < 0)
        tags["M15 tide against or flat"] = X.m15_tide * s <= 0
        tags["run >= 3 M15 ATR (a climax)"] = z.run_atr >= 3
        tags["entry within 1 M15 ATR of the day's extreme the trade's way"] = np.where(s > 0, X.d_dhi > -1, X.d_dlo < 1)
        near = []
        for t in z.t:
            p = rel.searchsorted(t)
            nxt = (rel[p] - t).total_seconds() / 60 if p < len(rel) else 1e9
            prv = (t - rel[p - 1]).total_seconds() / 60 if p > 0 else 1e9
            near.append(nxt <= 30 or prv <= 15)
        tags["a US release 15 min before .. 30 min after"] = np.array(near)
        tags["London 07-12 UTC"] = z.session.to_numpy() == 1
        tags["Asia 00-07 UTC"] = z.session.to_numpy() == 0
        tags["kind 3: stopped, then the target from the entry (stop inside the swing)"] = (z.exit == "stop") & (z.kind == "3")
        tags["kind 2: half way, then back to the stop"] = (z.exit == "stop") & (z.kind == "2")
        los, win = z.exit == "stop", z.exit == "win"
        print(f"\n== A4 {part}: {len(z)} trades, {los.sum()} full losers, {win.sum()} winners, {(z.exit == 'be').sum()} break-even")
        print(f"{'situation':66} {'losers':>9} {'winners':>9} {'R if removed':>12} {'n kept':>7}")
        for k, v in tags.items():
            v = np.asarray(v, bool)
            kept = z[~v]
            print(f"{k:66} {100 * v[los].mean():8.0f}% {100 * v[win].mean():8.0f}% {kept.R.mean():+12.3f} {len(kept):7}")
        print(f"(all: R {z.R.mean():+.3f})")


if __name__ == "__main__":
    main()
