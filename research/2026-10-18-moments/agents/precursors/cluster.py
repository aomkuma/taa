"""The sets (notes.md): design snaps in time order; a snap joins the most similar set's leader at similarity >= 0.80
(0.7 x the mean shape correlation over six timeframes + 0.3 x the share of equal states), else it starts a set.
Then each set's evidence: snaps, distinct days, what followed.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/cluster.py [threshold]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from plib import HERE

THR = float(sys.argv[1]) if len(sys.argv) > 1 else 0.80
LAYER = sys.argv[2] if len(sys.argv) > 2 else "all"
W_SHAPE, W_STATE = 0.7, 0.3
NTF = 6
CLASSES = ["ran_up", "ran_dn", "slow_up", "slow_dn", "fake_up", "fake_dn", "flat", "drift"]


ALL_TFS = ("H4", "H1", "M30", "M15", "M5", "M1")
LAYERS = {"all": (ALL_TFS, True), "context": (("H4", "H1"), False), "setup": (("M30", "M15"), False),
          "trigger": (("M5", "M1"), True)}


def vectors(S: pd.DataFrame, SH: np.ndarray, tfs=ALL_TFS, glob=True) -> tuple[np.ndarray, list[str]]:
    """sim(a, b) = V[a] . V[b]: shapes are unit-scaled per timeframe (dot = correlation), states one-hot."""
    state_cols = [c for c in S.columns if c.split("_")[0] in tfs or (glob and c.startswith("g_"))]
    state_cols = [c for c in state_cols if S[c].dtype == np.int8]
    cols = np.hstack([np.arange(ALL_TFS.index(t) * 40, ALL_TFS.index(t) * 40 + 40) for t in tfs])
    blocks = [SH[:, cols] * np.sqrt(W_SHAPE / len(tfs))]
    F = len(state_cols)
    for c in state_cols:
        v = S[c].to_numpy().astype(int)
        k = v.max() + 1
        oh = np.zeros((len(v), k), np.float32)
        oh[np.arange(len(v)), v] = 1
        blocks.append(oh * np.sqrt(W_STATE / F))
    return np.hstack(blocks).astype(np.float32), state_cols


def leader_sets(V: np.ndarray, thr: float) -> tuple[np.ndarray, list[int], np.ndarray]:
    leaders: list[int] = []
    L = np.zeros((0, V.shape[1]), np.float32)
    sid = np.full(len(V), -1)
    best = np.zeros(len(V), np.float32)
    for i in range(len(V)):
        if len(leaders):
            s = L @ V[i]
            j = int(np.argmax(s))
            best[i] = s[j]
            if s[j] >= thr:
                sid[i] = j
                continue
        sid[i] = len(leaders)
        leaders.append(i)
        L = np.vstack([L, V[i][None, :]])
    return sid, leaders, best


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    SH = np.load(HERE / "snap_shapes.npy")
    d = (S.half != "W").to_numpy()
    V, cols = vectors(S, SH, *LAYERS[LAYER])
    print(f"layer {LAYER}: {LAYERS[LAYER]}")
    print(f"states {len(cols)}, vector {V.shape[1]} dims; design snaps {d.sum()}")
    Vd = V[d]
    Sd = S[d].reset_index(drop=True)
    # how similar are snaps at all? the nearest earlier design snap
    rng = np.random.default_rng(3)
    smp = rng.choice(len(Vd), 2000, replace=False)
    sims = Vd[smp] @ Vd.T
    for r, i in enumerate(smp):
        sims[r, i:] = -9  # only earlier snaps
    nn = sims.max(axis=1)
    nn = nn[nn > -9]
    print("nearest earlier design snap, similarity quantiles:",
          {q: round(float(np.quantile(nn, q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)})
    rnd = (Vd[smp[:500]] @ Vd[rng.choice(len(Vd), 500)].T).ravel()
    print("random pairs:", {q: round(float(np.quantile(rnd, q)), 3) for q in (0.5, 0.9, 0.99, 0.999)})
    sid, leaders, best = leader_sets(Vd, THR)
    Sd["set"] = sid
    Sd["day"] = Sd.S.dt.tz_convert("Asia/Bangkok").dt.normalize()
    g = Sd.groupby("set")
    sets = pd.DataFrame({"snaps": g.size(), "days": g.day.nunique(), "leader_time": Sd.S.iloc[leaders].to_numpy()})
    for c in CLASSES:
        sets[c] = g.cls.apply(lambda x, c=c: (x == c).mean())
    sets["ran10"] = sets.ran_up + sets.ran_dn
    sets["mfe_up30"] = g.mfe_up30.median()
    sets["mfe_dn30"] = g.mfe_dn30.median()
    sets["names"] = g.name.agg(lambda x: " ".join(sorted(set(x)))[:60])
    sets.to_parquet(HERE / f"sets_{LAYER}_{int(THR * 100)}.parquet")
    Sd[["S", "name", "set"]].to_parquet(HERE / f"snap_sets_{LAYER}_{int(THR * 100)}.parquet")
    print(f"\n=== threshold {THR}: {len(sets)} sets from {len(Sd)} design snaps ===")
    print("set size (snaps) distribution:", sets.snaps.value_counts().sort_index().head(12).to_dict())
    print("sets by distinct days:", pd.cut(sets.days, [0, 1, 2, 4, 9, 19, 49, 10**6]).value_counts().sort_index().to_dict())
    print(f"snaps in sets seen on >= 5 days: {sets.loc[sets.days >= 5, 'snaps'].sum()} "
          f"({sets.loc[sets.days >= 5, 'snaps'].sum() / len(Sd):.1%})")
    big = sets[sets.days >= 5].sort_values("days", ascending=False)
    cols_show = ["snaps", "days", "ran_up", "ran_dn", "slow_up", "slow_dn", "fake_up", "fake_dn", "flat", "drift",
                 "mfe_up30", "mfe_dn30", "names"]
    print(big[cols_show].head(40).round(2).to_string())


if __name__ == "__main__":
    main()
