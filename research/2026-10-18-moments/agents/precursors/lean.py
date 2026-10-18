"""Do the core-formation sets lean (design)? The trader's view from the snap price: which of +X / -X comes first
(X = 10 and 5 U) and the first 3 U then 10 U; per set seen on >= 30 days, z = (up - down) / sqrt((up + down) / n),
against the same with outcomes shuffled among snaps of the same time (20 shuffles).

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/lean.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from plib import HERE

pd.set_option("display.width", 250)


def zs(sid: np.ndarray, out: np.ndarray, day: np.ndarray, min_days: int) -> pd.DataFrame:
    x = pd.DataFrame({"set": sid, "o": out, "day": day})
    g = x.groupby("set")
    t = pd.DataFrame({"n": g.size(), "days": g.day.nunique(), "up": g.o.apply(lambda v: (v > 0).mean()),
                      "down": g.o.apply(lambda v: (v < 0).mean())})
    t = t[t.days >= min_days]
    t["z"] = (t.up - t.down) / np.sqrt((t.up + t.down).clip(lower=1e-9) / t.n)
    return t


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    S = S[S.half != "W"].reset_index(drop=True)
    M = pd.read_parquet(HERE / "fpsets_core_members.parquet")
    assert (M.S.to_numpy() == S.S.to_numpy()).all()
    day = S.S.dt.tz_convert("Asia/Bangkok").dt.normalize().to_numpy()
    s3 = S.start3.fillna(0).to_numpy()
    cont = S.cont10.to_numpy()
    outs = {"first10": S.first10.fillna(0).to_numpy(), "first5": S.first5.fillna(0).to_numpy(),
            "3U then 10U": np.where(cont == 1, s3, 0)}
    rng = np.random.default_rng(9)
    idx_by_name = S.groupby("name").indices
    rows = []
    for layer in ("context", "setup", "trigger", "all"):
        sid = M[f"set_{layer}"].to_numpy()
        for oname, o in outs.items():
            t = zs(sid, o, day, 30)
            null = []
            for _ in range(20):
                on = o.copy()
                for idx in idx_by_name.values():
                    on[idx] = rng.permutation(on[idx])
                tn = zs(sid, on, day, 30)
                null.append(((tn.z.abs() >= 3).sum(), (tn.z.abs() >= 2.5).sum()))
            null = np.array(null)
            rows.append(dict(layer=layer, outcome=oname, sets_30days=len(t), z3=int((t.z.abs() >= 3).sum()),
                             z3_chance=round(null[:, 0].mean(), 1), z25=int((t.z.abs() >= 2.5).sum()),
                             z25_chance=round(null[:, 1].mean(), 1)))
            if oname == "first10":
                top = t.reindex(t.z.abs().sort_values(ascending=False).index).head(8)
                print(f"\n{layer} / first10: the most leaning sets seen on >= 30 days")
                print(top.round(3).to_string())
    print("\n-- leaning sets (|z| >= 3 and >= 2.5) against shuffled outcomes --")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
