"""Why the same picture is rare (owner, 2026-10-19: "if the bot uses it for real, will it catch patterns?"): for a
sample of snaps, every earlier moment of the three-year library from another episode (>= 7 days before) is checked
against each part of the same-picture rule (picture.same_tf + the codes) separately. Per layer: how many snaps have
any earlier moment passing every part, passing every part but one (which part binds), each part's pass rate alone,
and the coverage as the parts are added one by one; per single timeframe the same without the codes.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/rarity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plib  # noqa: E402
from picture import (  # noqa: E402
    ER_DIFF,
    EPISODE_DAYS,
    FLAT,
    LEG,
    POS,
    RETR,
    RETR_FLOOR,
    RHO,
    SEG_RHO,
    SEGS,
    SIM_TOL,
    SIZE,
    as_arrays,
    same_mask,
)

PARTS = ("codes", "outline", "thirds' way", "thirds' outline", "120 bars' way", "structure", "last top/bottom",
         "pullback", "smoothness", "size", "last leg", "position")


def thirds(shapes: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Each third of every outline centred and scaled to unit norm, and whether it is flat (picture.seg_corr)."""
    out, flat = [], []
    for s0, s1 in SEGS:
        a = shapes[..., s0:s1] - shapes[..., s0:s1].mean(axis=-1, keepdims=True)
        n = np.sqrt((a * a).sum(axis=-1))
        flat.append(n < 1e-9)
        out.append(np.where(n[..., None] < 1e-9, 0.0, a / np.where(n < 1e-9, 1.0, n)[..., None]))
    return out, flat


def part_masks(A: dict, shapes: np.ndarray, segs: tuple, row: int, cand: np.ndarray) -> dict[str, np.ndarray]:
    """Per part of picture.same_tf, candidates x timeframes: True where the candidate's picture passes it."""
    segn, segf = segs
    m = {}
    m["outline"] = np.einsum("ktp,tp->kt", shapes[cand], shapes[row]) >= RHO - SIM_TOL
    way = np.ones((len(cand), shapes.shape[1]), bool)
    out = np.ones_like(way)
    for j in range(3):
        way &= A[f"seg{j}"][cand] == A[f"seg{j}"][row]
        cj = np.einsum("ktp,tp->kt", segn[j][cand], segn[j][row])
        fa, fb = segf[j][cand], segf[j][row][None, :]
        cj = np.where(fa | fb, np.where(fa & fb, 1.0, 0.0), cj)
        out &= cj >= SEG_RHO - SIM_TOL
    m["thirds' way"], m["thirds' outline"] = way, out
    m["120 bars' way"] = A["net_way"][cand] == A["net_way"][row]
    m["structure"] = A["struct"][cand] == A["struct"][row]
    m["last top/bottom"] = A["brk"][cand] == A["brk"][row]
    ra, rb = A["retr"][cand], A["retr"][row]
    with np.errstate(invalid="ignore"):
        m["pullback"] = ((ra < RETR_FLOOR) & (rb < RETR_FLOOR)) | (
            (np.minimum(ra, rb) > 0) & (np.maximum(ra, rb) <= RETR * np.minimum(ra, rb)))
        m["smoothness"] = np.abs(A["er"][cand] - A["er"][row]) <= ER_DIFF + SIM_TOL
        sa, sb = A["size"][cand], A["size"][row]
        m["size"] = np.isfinite(sa) & np.isfinite(sb) & (np.maximum(sa, sb) <= SIZE * np.minimum(sa, sb))
        la, lb = A["leg"][cand], A["leg"][row]
        legs = (A["leg_way"][cand] == A["leg_way"][row]) & (np.maximum(la, lb) <= LEG * np.minimum(la, lb))
    m["last leg"] = np.isfinite(la) & np.isfinite(lb) & (((la < FLAT) & (lb < FLAT)) | legs)
    m["position"] = (np.abs(A["pos"][cand] - A["pos"][row]) <= POS + SIM_TOL) & (A["edge"][cand] == A["edge"][row])
    return m


def summarize(per: list[dict], parts: tuple[str, ...]) -> pd.DataFrame:
    """per: one dict per snap {part: candidates bool}; the table of coverage (share of snaps with >= 1 candidate)."""
    rows = []
    full = np.array([np.logical_and.reduce([d[p] for p in parts]).sum() for d in per])
    rows.append(dict(rule="every part", snaps_with_a_match=(full >= 1).mean(), median_matches=np.median(full)))
    for p in parts:  # one part dropped
        n = np.array([np.logical_and.reduce([d[q] for q in parts if q != p]).sum() for d in per])
        rows.append(dict(rule=f"without {p}", snaps_with_a_match=(n >= 1).mean(), median_matches=np.median(n),
                         part_alone_passes=np.mean([d[p].mean() for d in per])))
    return pd.DataFrame(rows)


def cumulative(per: list[dict], parts: tuple[str, ...]) -> pd.DataFrame:
    """The parts added one by one, the least selective first: coverage after each."""
    order = sorted(parts, key=lambda p: -np.mean([d[p].mean() for d in per]))
    rows, acc = [], [np.ones(len(d[parts[0]]), bool) for d in per]
    for p in order:
        acc = [a & d[p] for a, d in zip(acc, per)]
        n = np.array([a.sum() for a in acc])
        rows.append(dict(added=p, snaps_with_a_match=(n >= 1).mean(), median_matches=np.median(n)))
    return pd.DataFrame(rows)


def main() -> None:
    from library_match import LAYERS, attrs  # noqa: PLC0415
    from v2c import LAYER_TFS, LONG, TFS  # noqa: PLC0415

    plib.gold.below_normal_priority()
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    SH = np.load(HERE / "moment_shapes_3y.npy").astype(float)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((pd.DatetimeIndex(T.t_dec).tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    learn = np.nonzero(np.asarray((T.kind == "snap") & (pd.DatetimeIndex(T.t_dec) < plib.EXAM_START)
                                  & (pd.DatetimeIndex(T.t_dec) >= pd.Timestamp("2024-05-01", tz="UTC"))))[0]
    rng = np.random.default_rng(7)
    sample = np.sort(rng.choice(learn, size=800, replace=False))  # snaps with >= 6 months of library before them
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    for L in ("ctx", "set", "trg"):
        tfs = LAYER_TFS[L]
        idx = [TFS.index(tf) for tf in tfs]
        codes = np.column_stack(attrs(T, T, LAYERS[LONG[L]])).astype(int)
        feats = [[{k: T[f"{tf}_{k}"].iloc[i] for k in ("size", "pos", "edge", "leg_way", "leg", "net_way", "struct",
                                                        "brk", "retr", "er", "seg0", "seg1", "seg2")} for tf in tfs]
                 for i in range(len(T))]
        A = as_arrays(feats)
        shp = SH[:, idx]
        segs = thirds(shp)
        layer, single = [], {tf: [] for tf in tfs}
        for r in sample:
            cand = np.nonzero(day <= day[r] - EPISODE_DAYS)[0]
            m = part_masks(A, shp, segs, int(r), cand)
            # the parts together must be exactly the library's rule (picture.same_mask)
            assert np.array_equal(np.logical_and.reduce([v.all(axis=1) for v in m.values()]),
                                  same_mask(A, shp, int(r), cand)), r
            sim = np.round((codes[cand] == codes[r]).mean(axis=1), 9)
            layer.append({"codes": sim >= 0.8 - SIM_TOL, **{k: v.all(axis=1) for k, v in m.items()}})
            for t, tf in enumerate(tfs):
                single[tf].append({k: v[:, t] for k, v in m.items()})
        print(f"\n=== {LONG[L]}: {len(sample)} snaps (2024-05 .. 2026-04-17), earlier moments from other episodes ===")
        print(summarize(layer, PARTS).to_string(index=False))
        print("the parts added one by one:")
        print(cumulative(layer, PARTS).to_string(index=False))
        for tf in tfs:
            s = summarize(single[tf], PARTS[1:])
            print(f"-- {tf} alone (its picture only, no codes): every part {s.snaps_with_a_match.iloc[0]:.3f} of snaps, "
                  f"median {s.median_matches.iloc[0]:.0f} matches; without one part:",
                  ", ".join(f"{p} {v:.3f}" for p, v in zip(PARTS[1:], s.snaps_with_a_match.iloc[1:])), flush=True)


if __name__ == "__main__":
    main()
