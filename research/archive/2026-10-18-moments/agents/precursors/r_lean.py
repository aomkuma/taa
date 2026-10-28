"""The library learns the trade's result - the premise (notes.md "The library learns the trade's result", written
before it is computed): at every snap from 2024-05, per layer and level of the same situation, the earlier snaps
(>= 7 days before) in it, one per day (the day's first), their mean R_buy and R_sell (trade_labels.py); the better
side when >= N_MIN days and its mean >= THETA; against the snap's own realized R of that side minus a coin's side
(the mean of its R_buy and R_sell), with the error by day; the placebo - the same pick against the next trading
day's same-time snap. A sample of the evidence is recounted independently (plain pandas) before any table prints.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/r_lean.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from picture import EPISODE_DAYS, KEYS, as_arrays  # noqa: E402
from rarity import part_masks, thirds  # noqa: E402

LAYER_TFS = {"ctx": ("H4", "H1"), "set": ("M30", "M15"), "trg": ("M5", "M1")}
LEVELS = {"L3": ("smoothness", "pullback", "last top/bottom"),
          "L6": ("smoothness", "pullback", "last top/bottom", "120 bars' way", "size", "position"),
          "L7": ("smoothness", "pullback", "last top/bottom", "120 bars' way", "size", "position", "structure")}
CELLS = [(n, th) for n in (5, 10) for th in (0.0, 0.1, 0.2)]


def day_means(days: np.ndarray, rb: np.ndarray, rs: np.ndarray) -> tuple[int, float, float]:
    """The matching snaps' days and R_buy / R_sell in time order: (the days, the mean R_buy and R_sell of each day's
    first)."""
    if len(days) == 0:
        return 0, float("nan"), float("nan")
    _, first = np.unique(days, return_index=True)
    return len(first), float(rb[first].mean()), float(rs[first].mean())


def pick(n: float, mb: float, ms: float, n_min: int, theta: float) -> int:
    """The better side (a tie: the buy) when >= n_min days and its mean R >= theta; else 0."""
    if not (n >= n_min and np.isfinite(mb) and np.isfinite(ms)):
        return 0
    if mb >= ms:
        return 1 if mb >= theta - 1e-9 else 0
    return -1 if ms >= theta - 1e-9 else 0


def recount(T: pd.DataFrame, ok_c: np.ndarray, day: np.ndarray, rb: np.ndarray, rs: np.ndarray, r: int,
            tfs: tuple[str, str], level: str) -> tuple[int, float, float]:
    """The evidence re-derived from the rule's text with plain pandas (lean_check.recount's rules, plus the swing
    structure): candidates ok_c (snaps with a result) >= 7 days before."""
    parts = {"L3": 3, "L6": 6, "L7": 7}[level]
    ok = pd.Series(ok_c & (day <= day[r] - 7), index=T.index)
    for tf in tfs:
        col = {k: T[f"{tf}_{k}"] for k in ("er", "retr", "brk", "net_way", "size", "pos", "edge", "struct")}
        me = {k: v.iloc[r] for k, v in col.items()}
        ok &= (col["er"] - me["er"]).abs() <= 0.1 + 1e-6
        lo_, hi_ = np.minimum(col["retr"], me["retr"]), np.maximum(col["retr"], me["retr"])
        ok &= ((col["retr"] < 1.0) & (me["retr"] < 1.0)) | ((lo_ > 0) & (hi_ <= 1.6 * lo_))
        ok &= col["brk"] == me["brk"]
        if parts >= 6:
            ok &= col["net_way"] == me["net_way"]
            lo_, hi_ = np.minimum(col["size"], me["size"]), np.maximum(col["size"], me["size"])
            ok &= np.isfinite(col["size"]) & np.isfinite(me["size"]) & (hi_ <= 1.4 * lo_)
            ok &= ((col["pos"] - me["pos"]).abs() <= 0.2 + 1e-6) & (col["edge"] == me["edge"])
        if parts >= 7:
            ok &= col["struct"] == me["struct"]
    idx = np.nonzero(ok.to_numpy())[0]
    if len(idx) == 0:
        return 0, float("nan"), float("nan")
    first = pd.Series(idx).groupby(day[idx], sort=True).first().to_numpy()
    return len(first), float(rb[first].mean()), float(rs[first].mean())


def main() -> None:
    import plib  # noqa: PLC0415
    from v2b import TFS  # noqa: PLC0415

    plib.gold.below_normal_priority()
    T = pd.read_parquet(HERE / "moments_3y.parquet")
    SH = np.load(HERE / "moment_shapes_3y.npy").astype(float)
    L = pd.read_parquet(HERE / "snap_trade_labels.parquet")
    rb, rs = np.full(len(T), np.nan), np.full(len(T), np.nan)
    rb[L.row], rs[L.row] = L.buy_R.to_numpy(), L.sell_R.to_numpy()
    t = pd.DatetimeIndex(T.t_dec)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((t.tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    ok_c = (T.kind == "snap").to_numpy() & np.isfinite(rb) & np.isfinite(rs)  # the evidence: snaps with a result
    rows = np.nonzero(ok_c & np.asarray(t >= pd.Timestamp("2024-05-01", tz="UTC")))[0]
    half = np.where(t[rows] >= plib.EXAM_START, "exam", "learn")
    # the placebo: the next trading day's snap of the same name
    S = pd.DataFrame({"row": rows, "day": day[rows], "name": T.name.to_numpy()[rows]})
    days = np.sort(S.day.unique())
    nxt = dict(zip(days[:-1], days[1:]))
    by = S.set_index(["day", "name"]).row
    nrow = np.array([by.get((nxt.get(d, -1), nm), -1) for d, nm in zip(S.day, S.name)])
    ev = []
    rng = np.random.default_rng(5)
    for lay, tfs in LAYER_TFS.items():
        idx = [TFS.index(tf) for tf in tfs]
        A = as_arrays([[{k: T[f"{tf}_{k}"].iloc[i] for k in KEYS} for tf in tfs] for i in range(len(T))])
        shp = SH[:, idx]
        segs = thirds(shp)
        out = {lv: np.full((len(rows), 3), np.nan) for lv in LEVELS}
        for j, r in enumerate(rows):
            cand = np.nonzero(ok_c & (day <= day[r] - EPISODE_DAYS))[0]
            m = part_masks(A, shp, segs, int(r), cand)
            for lv, parts in LEVELS.items():
                acc = np.logical_and.reduce([m[p].all(axis=1) for p in parts])
                c = cand[acc]
                out[lv][j] = day_means(day[c], rb[c], rs[c])
        for lv in LEVELS:  # 100 snaps per level recounted from the rule's text
            for j in rng.choice(len(rows), size=100, replace=False):
                n2, b2, s2 = recount(T, ok_c, day, rb, rs, int(rows[j]), tfs, lv)
                n1, b1, s1 = out[lv][j]
                assert n1 == n2 and ((np.isnan(b1) and np.isnan(b2)) or (abs(b1 - b2) < 1e-9 and abs(s1 - s2) < 1e-9)), (lay, lv, j)
            ev.append(pd.DataFrame({"layer": lay, "level": lv, "row": rows, "n": out[lv][:, 0], "mb": out[lv][:, 1],
                                    "ms": out[lv][:, 2]}))
        print(lay, "evidence done; 300 snaps recounted independently, all equal", flush=True)
    E = pd.concat(ev, ignore_index=True)
    E.to_parquet(HERE / "r_lean_evidence.parquet")
    res = []
    for (lay, lv), g in E.groupby(["layer", "level"], sort=False):
        n, mb, ms = g.n.to_numpy(), g.mb.to_numpy(), g.ms.to_numpy()
        for n_min, theta in CELLS:
            side = np.array([pick(a, b, c, n_min, theta) for a, b, c in zip(n, mb, ms)])
            for h in ("learn", "exam"):
                k = (side != 0) & (half == h)
                r = rows[k]
                got = np.where(side[k] > 0, rb[r], rs[r])
                d = got - (rb[r] + rs[r]) / 2
                gd = pd.Series(d).groupby(day[r])
                se = float(np.sqrt(((gd.sum() - d.mean() * gd.size()) ** 2).sum()) / max(len(d), 1)) if len(d) > 1 else np.nan
                pr = nrow[k]
                okp = pr >= 0
                gp = np.where(side[k][okp] > 0, rb[pr[okp]], rs[pr[okp]]) - (rb[pr[okp]] + rs[pr[okp]]) / 2
                res.append(dict(layer=lay, level=lv, n_min=n_min, theta=theta, half=h, picks=int(k.sum()),
                                R=float(got.mean()) if len(got) else np.nan, edge=float(d.mean()) if len(d) else np.nan,
                                se_day=se, placebo=float(gp.mean()) if len(gp) else np.nan))
    D = pd.DataFrame(res)
    D.to_csv(HERE / "r_lean_premise.csv", index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 500)
    pd.set_option("display.float_format", lambda v: f"{v:+.3f}")
    W = D.pivot_table(index=["layer", "level", "n_min", "theta"], columns="half", values=["picks", "R", "edge", "se_day", "placebo"])
    W.columns = [f"{a}_{b}" for a, b in W.columns]
    W = W[["picks_learn", "R_learn", "edge_learn", "se_day_learn", "placebo_learn", "picks_exam", "R_exam", "edge_exam",
           "se_day_exam", "placebo_exam"]]
    print("\nthe premise: R of the side picked, its edge over a coin's side (+- se by day), the placebo (next day); both halves")
    print(W.reset_index().to_string(index=False))


if __name__ == "__main__":
    main()
