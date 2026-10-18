"""How much evidence a trigger finds (design only): for every design snap, the earlier design snaps on OTHER days
with similarity >= 0.80, per layer (all six timeframes, H4+H1, M30+M15, M5+M1), and what they say.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/evidence.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cluster import LAYERS, vectors
from plib import HERE

THR = 0.80


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    SH = np.load(HERE / "snap_shapes.npy")
    d = (S.half != "W").to_numpy()
    Sd = S[d].reset_index(drop=True)
    day = Sd.S.dt.tz_convert("Asia/Bangkok").dt.normalize().to_numpy()
    up = Sd.cls.isin(["ran_up", "slow_up"]).to_numpy()
    dn = Sd.cls.isin(["ran_dn", "slow_dn"]).to_numpy()
    ran = Sd.cls.isin(["ran_up", "ran_dn"]).to_numpy()
    rows = []
    for layer in LAYERS:
        V, _ = vectors(S, SH, *LAYERS[layer])
        V = V[d]
        cnt = np.zeros(len(V), int)
        ndays = np.zeros(len(V), int)
        for a in range(0, len(V), 1000):
            sims = V[a:a + 1000] @ V.T
            for r in range(sims.shape[0]):
                i = a + r
                ok = (sims[r] >= THR) & (np.arange(len(V)) < i) & (day != day[i])
                cnt[i] = ok.sum()
                ndays[i] = len(np.unique(day[ok]))
        Sd[f"n_{layer}"] = ndays
        q = pd.Series(ndays)
        rows.append(dict(layer=layer, none=(q == 0).mean(), ge5=(q >= 5).mean(), ge20=(q >= 20).mean(),
                         median=q.median(), p90=q.quantile(0.9)))
        print(layer, "done", flush=True)
    print("\n-- share of design snaps whose earlier evidence (other days, similarity >= 0.80) has N days --")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    Sd[["S", "name"] + [f"n_{k}" for k in LAYERS]].to_parquet(HERE / "evidence_counts.parquet")


if __name__ == "__main__":
    main()
