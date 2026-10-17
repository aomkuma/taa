"""Step 2: session families x pairs x side mode x exits x filters, design halves only. Saves grid1.parquet and the
per-trade table trades1.parquet (net and gross).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/grid1.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import fxlib as fx  # noqa: E402
import lab  # noqa: E402

fx.below_normal_priority()
OUT = "research/2026-10-18-moments/agents/fx/"
FAMS = {
    "A_lon_8-10>16": (fx.LON, 8, 10, 16),
    "B_asia_0-7>12utc": ("UTC", 0, 7, 12),
    "C_fix_14-16>19": (fx.LON, 14, 16, 19),
    "D_ny_8-9.5>12": (fx.NYC, 8, 9.5, 12),
    "E_tok_9-10>13": ("Asia/Tokyo", 9, 10, 13),
    "F_day_0-12>16utc": ("UTC", 0, 12, 16),
    "G_lon_7-8>12": (fx.LON, 7, 8, 12),
}
SLK = (1.0, 1.5, 2.0)
TPK = (None, 1.5, 2.5)


def main() -> None:
    allz = []
    for p in fx.PAIRS:
        Pn, Pg = fx.Pair(p), fx.Pair(p, costs=False)
        for fam, (tz, a0, a1, b1) in FAMS.items():
            ev = lab.events(Pn, tz, a0, a1, b1)
            ev = ev[ev.half.isin([h for h, _, _ in fx.HALVES])].reset_index(drop=True)
            ev = ev[np.isfinite(ev.h1_atr) & (ev.h1_atr > 0)].reset_index(drop=True)
            base = np.sign(ev.move.to_numpy()).astype(int)
            for mode, sgn in (("cont", 1), ("fade", -1)):
                side = base * sgn
                for k in SLK:
                    sl = k * ev.h1_atr.to_numpy()
                    for m in TPK:
                        tp = None if m is None else m * sl
                        zn = lab.simulate(Pn, ev, side, sl, tp)
                        zg = lab.simulate(Pg, ev, side, sl, tp)
                        z = zn[["ev", "t", "half", "side", "sl", "R", "pips", "usd", "exit", "kind", "mins", "mfe", "mae"]].copy()
                        z["Rg"] = zg.set_index("ev").R.reindex(z.ev).to_numpy()
                        z = z.assign(pair=p, fam=fam, mode=mode, slk=k, tpk=(0 if m is None else m))
                        z["q"] = (ev.move.abs() / ev.h1_atr).to_numpy()[z.ev]
                        tr = np.sign(ev.h1_c - ev.h1_ema50).to_numpy() * (np.sign(ev.h1_slope).to_numpy() == np.sign(ev.h1_c - ev.h1_ema50).to_numpy())
                        z["with_trend"] = (tr[z.ev] * z.side.to_numpy())
                        allz.append(z)
            print(p, fam, len(ev), flush=True)
    t = pd.concat(allz, ignore_index=True)
    t.to_parquet(OUT + "trades1.parquet")


if __name__ == "__main__":
    main()
