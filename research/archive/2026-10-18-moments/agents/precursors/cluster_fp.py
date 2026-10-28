"""Sets by the formation fingerprint (notes.md): similarity = the share of equal attributes (each timeframe's 20 formation
/ indicator attributes, the support / resistance of M15 .. H4, the global states), one set at >= 0.80; per layer.
Reads: sets, the evidence a trigger finds (earlier snaps on other days), the sets' outcomes and how many lean by chance
(outcomes shuffled among snaps of the same time).

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/cluster_fp.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from plib import HERE

THR = 0.80
LAYERS = {"all": ("H4", "H1", "M30", "M15", "M5", "M1"), "context": ("H4", "H1"), "setup": ("M30", "M15"),
          "trigger": ("M5", "M1")}
pd.set_option("display.width", 250)


CORE = len(sys.argv) > 1 and sys.argv[1] == "core"


def core_cols(F: pd.DataFrame, tf: str) -> list[np.ndarray]:
    w = F[f"{tf}_fp_where"].to_numpy()
    where4 = np.select([w == 0, w == 1, w == 2, w == 3, w == 4], [0, 1, 2, 2, 3], 4)  # middle third -> upper half
    stack = F[f"{tf}_fp_ema"].to_numpy() // 2
    return [F[f"{tf}_fp_npiv"].to_numpy(), F[f"{tf}_fp_leg"].to_numpy(), F[f"{tf}_fp_pk1"].to_numpy(),
            F[f"{tf}_fp_tr1"].to_numpy(), where4, F[f"{tf}_fp_rsi_up"].to_numpy(), F[f"{tf}_fp_macd_h"].to_numpy(), stack]


def attributes(S: pd.DataFrame, F: pd.DataFrame, tfs: tuple[str, ...], glob: bool) -> list[np.ndarray]:
    cols = []
    for tf in tfs:
        if CORE:
            cols += core_cols(F, tf)
        else:
            cols += [F[c].to_numpy() for c in F.columns if c.startswith(f"{tf}_fp_")]
        for k in (("sr_loc",) if CORE else ("sr_loc", "sr_imp")):
            if f"{tf}_{k}" in S.columns:
                cols.append(S[f"{tf}_{k}"].to_numpy())
    if glob:
        cols += [S[c].to_numpy() for c in S.columns if c.startswith("g_")]
    return cols


def onehot(cols: list[np.ndarray]) -> np.ndarray:
    blocks = []
    for v in cols:
        v = v.astype(int)
        oh = np.zeros((len(v), v.max() + 1), np.float32)
        oh[np.arange(len(v)), v] = 1
        blocks.append(oh)
    return np.hstack(blocks) / np.sqrt(len(cols))  # dot = the share of equal attributes


def leaders(V: np.ndarray, thr: float) -> np.ndarray:
    L = np.zeros((0, V.shape[1]), np.float32)
    sid = np.full(len(V), -1)
    for i in range(len(V)):
        if len(L):
            s = L @ V[i]
            j = int(np.argmax(s))
            if s[j] >= thr - 1e-6:
                sid[i] = j
                continue
        sid[i] = len(L)
        L = np.vstack([L, V[i][None, :]])
    return sid


def set_table(Sd: pd.DataFrame, sid: np.ndarray, cls: np.ndarray) -> pd.DataFrame:
    x = pd.DataFrame({"set": sid, "day": Sd.day.to_numpy(), "cls": cls})
    g = x.groupby("set")
    t = pd.DataFrame({"snaps": g.size(), "days": g.day.nunique()})
    up = x.cls.isin(["ran_up", "slow_up"])
    dn = x.cls.isin(["ran_dn", "slow_dn"])
    t["up"] = up.groupby(x.set).mean()
    t["down"] = dn.groupby(x.set).mean()
    t["ran10"] = x.cls.isin(["ran_up", "ran_dn"]).groupby(x.set).mean()
    t["fake"] = x.cls.isin(["fake_up", "fake_dn"]).groupby(x.set).mean()
    t["flat"] = (x.cls == "flat").groupby(x.set).mean()
    return t


def main() -> None:
    S = pd.read_parquet(HERE / "snaps.parquet")
    F = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    d = (S.half != "W").to_numpy()
    Sd = S[d].reset_index(drop=True)
    Fd = F[d].reset_index(drop=True)
    Sd["day"] = Sd.S.dt.tz_convert("Asia/Bangkok").dt.normalize()
    day = Sd.day.to_numpy()
    rng = np.random.default_rng(5)
    # the null: outcomes shuffled among design snaps of the same time (keeps each time's base rates)
    cls_null = Sd.cls.to_numpy().copy()
    for _name, idx in Sd.groupby("name").indices.items():
        cls_null[idx] = rng.permutation(cls_null[idx])
    rows = []
    for layer, tfs in LAYERS.items():
        cols = attributes(Sd, Fd, tfs, glob=(layer in ("all", "trigger")) and not CORE)
        V = onehot(cols)
        nd = np.zeros(len(V), int)
        for a in range(0, len(V), 1000):
            sims = V[a:a + 1000] @ V.T
            for r in range(sims.shape[0]):
                i = a + r
                ok = (sims[r] >= THR - 1e-6) & (np.arange(len(V)) < i) & (day != day[i])
                nd[i] = len(np.unique(day[ok]))
        sid = leaders(V, THR)
        T = set_table(Sd, sid, Sd.cls.to_numpy())
        Tn = set_table(Sd, sid, cls_null)
        big = T[T.days >= 10]
        bign = Tn[T.days >= 10]
        lean = int(((big.up - big.down).abs() >= 0.25).sum())
        lean_n = int(((bign.up - bign.down).abs() >= 0.25).sum())
        rows.append(dict(layer=layer, attributes=len(cols), sets=len(T), sets_10days=len(big),
                         snaps_in_10day_sets=f"{big.snaps.sum() / len(Sd):.0%}", trigger_no_evidence=f"{(nd == 0).mean():.0%}",
                         trigger_ge5_days=f"{(nd >= 5).mean():.0%}", trigger_ge20_days=f"{(nd >= 20).mean():.0%}",
                         lean_ge_0_25=lean, lean_by_chance=lean_n))
        Sd[f"set_{layer}"] = sid
        Sd[f"ev_{layer}"] = nd
        T.to_parquet(HERE / f"fpsets_{'core_' if CORE else ''}{layer}.parquet")
        print(f"\n=== {layer} ({len(cols)} attributes): {len(T)} sets; the 15 seen on the most days ===")
        print(T.sort_values("days", ascending=False).head(15).round(2).to_string())
    print("\n-- summary (design snaps; similarity = share of equal attributes; >= 0.80) --")
    print(pd.DataFrame(rows).to_string(index=False))
    Sd[["S", "name"] + [c for c in Sd.columns if c.startswith(("set_", "ev_"))]].to_parquet(HERE / f"fpsets_{'core_' if CORE else ''}members.parquet")


if __name__ == "__main__":
    main()
