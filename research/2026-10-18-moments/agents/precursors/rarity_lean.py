"""Do the same pictures lean the right way? (the step after rarity.py: the full picture almost never repeats; at
which level of sameness does the library have enough earlier days AND tell the way?) For snaps of both halves, at
each level of sameness (rarity.py's parts added one by one; each timeframe's full picture alone), the earlier
moments that match (>= 7 days before; one per day, the day's first), their lean (up share - down share, the classes
of picture.evidence), and against the snap's own outcome: with >= N_DAYS matching days and |lean| >= THETA, how often
a 10 U run followed the lean's way (ran_up / ran_dn) and how often the other way - against what the outcome rates of
the half give with no effect (edge = (way - other) - (base way - base other)).

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/rarity_lean.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402
from picture import DN_CLS, EPISODE_DAYS, KEYS, SIM_TOL, UP_CLS, as_arrays  # noqa: E402
from rarity import PARTS, part_masks, thirds  # noqa: E402

N_DAYS, THETA = 5, 0.2


def day_lean(days: np.ndarray, cls: np.ndarray) -> tuple[int, float]:
    """The matching moments' days and classes in time order: (the days, up share - down share over the days' first)."""
    if len(days) == 0:
        return 0, float("nan")
    _, first = np.unique(days, return_index=True)
    o = cls[first]
    return len(first), float(np.isin(o, UP_CLS).mean() - np.isin(o, DN_CLS).mean())


def score(side: np.ndarray, actual: np.ndarray, p_up: float, p_dn: float) -> dict:
    """side: +1 / -1 per prediction; actual: the snaps' classes; p_up, p_dn: the half's ran_up / ran_dn rates."""
    if len(side) == 0:
        return dict(n=0, way=np.nan, other=np.nan, edge=np.nan, se=np.nan)
    way = np.where(side > 0, actual == "ran_up", actual == "ran_dn")
    other = np.where(side > 0, actual == "ran_dn", actual == "ran_up")
    base = np.where(side > 0, p_up - p_dn, p_dn - p_up)
    d = way.astype(float) - other.astype(float) - base
    se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else np.nan
    return dict(n=len(d), way=float(way.mean()), other=float(other.mean()), edge=float(d.mean()), se=se)


def main() -> None:
    from library_match import LAYERS, attrs  # noqa: PLC0415
    from v2c import LAYER_TFS, LONG, TFS  # noqa: PLC0415

    plib.gold.below_normal_priority()
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    SH = np.load(HERE / "moment_shapes_3y.npy").astype(float)
    cls = T.cls.to_numpy().astype(str)
    t = pd.DatetimeIndex(T.t_dec)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((t.tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    snap = (T.kind == "snap").to_numpy()
    rng = np.random.default_rng(11)
    halves = {}
    learn = np.nonzero(snap & np.asarray(t < plib.EXAM_START) & np.asarray(t >= pd.Timestamp("2024-05-01", tz="UTC")))[0]
    halves["learning 2024-05 .. 2026-04-17"] = np.sort(rng.choice(learn, size=3000, replace=False))
    halves["exam 2026-04-18 .. 2026-10-16"] = np.nonzero(snap & np.asarray(t >= plib.EXAM_START))[0]
    base = {h: (float(np.mean(cls[r] == "ran_up")), float(np.mean(cls[r] == "ran_dn"))) for h, r in halves.items()}
    for h, (pu, pd_) in base.items():
        print(f"{h}: {len(halves[h])} snaps, ran_up {pu:.3f}, ran_dn {pd_:.3f}", flush=True)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda v: f"{v:+.3f}")
    dump = []  # every snap's matching days and lean per level (lean_check.py)
    for L in ("ctx", "set", "trg"):
        tfs = LAYER_TFS[L]
        idx = [TFS.index(tf) for tf in tfs]
        codes = np.column_stack(attrs(T, T, LAYERS[LONG[L]])).astype(int)
        A = as_arrays([[{k: T[f"{tf}_{k}"].iloc[i] for k in KEYS} for tf in tfs] for i in range(len(T))])
        shp = SH[:, idx]
        segs = thirds(shp)
        def masks(r: int) -> tuple[np.ndarray, dict, dict]:
            cand = np.nonzero(day <= day[r] - EPISODE_DAYS)[0]
            m = part_masks(A, shp, segs, r, cand)
            sim = np.round((codes[cand] == codes[r]).mean(axis=1), 9)
            lay = {"codes": sim >= 0.8 - SIM_TOL, **{k: v.all(axis=1) for k, v in m.items()}}
            single = {tf: np.logical_and.reduce([v[:, j] for v in m.values()]) for j, tf in enumerate(tfs)}
            return cand, lay, single

        rows = []
        for h, sample in halves.items():
            # the order of rarity.py (the least selective first), measured on every 10th snap of the half
            passes = {p: [] for p in PARTS}
            for r in sample[::10]:
                lay = masks(int(r))[1]
                for p in PARTS:
                    passes[p].append(lay[p].mean())
            order = sorted(PARTS, key=lambda p: -np.mean(passes[p]))
            levels: dict[str, list] = {}
            for r in sample:
                cand, lay, single = masks(int(r))
                acc = np.ones(len(cand), bool)
                for k, p in enumerate(order):
                    acc &= lay[p]
                    levels.setdefault(f"{k + 1:2d} +{p}", []).append(day_lean(day[cand[acc]], cls[cand[acc]]))
                for tf in tfs:
                    levels.setdefault(f"{tf} full picture alone", []).append(day_lean(day[cand[single[tf]]], cls[cand[single[tf]]]))
            for name, res in levels.items():
                n = np.array([x[0] for x in res])
                lean = np.array([x[1] for x in res])
                dump.append(pd.DataFrame({"layer": L, "half": h[:5], "level": name, "row": sample, "n_days": n, "lean": lean}))
                ok = (n >= N_DAYS) & (np.abs(np.nan_to_num(lean)) >= THETA)
                s = score(np.sign(lean[ok]), cls[sample[ok]], *base[h])
                rows.append(dict(half=h[:5], level=name, with_5_days=float(np.mean(n >= N_DAYS)), median_days=float(np.median(n)),
                                 trades=s["n"], way=s["way"], other=s["other"], edge=s["edge"], se=s["se"]))
        D = pd.DataFrame(rows)
        print(f"\n=== {LONG[L]}: snaps with >= {N_DAYS} matching earlier days and |lean| >= {THETA}: a 10 U run the "
              "lean's way / the other way within 30 minutes, edge over no effect (+- se) ===")
        print(D.to_string(index=False), flush=True)
    pd.concat(dump, ignore_index=True).to_parquet(HERE / "rarity_lean_snaps.parquet")


if __name__ == "__main__":
    main()
