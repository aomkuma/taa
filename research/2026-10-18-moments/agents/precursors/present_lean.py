"""The present library's evidence and its premise (notes.md "The present library", written before it is computed). At
every moment from 2024-05: per layer (context H4+H1, setup M30+M15, trigger M5+M1) and level (L3 smoothness +
pullback + the close against the last top / bottom; L6 + the 120 bars' way, size, position), the earlier moments
(>= 7 days before) in the same situation, grouped by day - each day's mean R_buy / R_sell of V2's trade over its
matching moments, then the mean over the days. The better side when >= N_MIN days and its mean >= THETA; its realized
R against a coin's side at the same moment, with the error by day; the placebo - the same pick against the same clock
time on the next trading day. Two sides (owner, 2026-10-19: "when the bot runs, compare both sides"): the bot's
evidence (fast: the situation's equal readings first, then the tolerances) and mine (`recount`, plain pandas from the
rules' text) must agree on a sample before any table prints.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/present_lean.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from picture import ER_DIFF, EPISODE_DAYS, POS, RETR, RETR_FLOOR, SIM_TOL, SIZE  # noqa: E402

LAYER_TFS = {"ctx": ("H4", "H1"), "set": ("M30", "M15"), "trg": ("M5", "M1")}
LEVELS = {"L3": ("smoothness", "pullback", "last top/bottom"),
          "L6": ("smoothness", "pullback", "last top/bottom", "120 bars' way", "size", "position")}
EQUAL = {"last top/bottom": ("brk",), "120 bars' way": ("net_way",), "position": ("edge",)}  # parts with equal readings
CELLS = [(n, th) for n in (5, 10) for th in (0.0, 0.1, 0.2)]


def tolerance_mask(V: dict, r: int, cand: np.ndarray, tfs: tuple[str, ...], parts: tuple[str, ...]) -> np.ndarray:
    """The parts with a tolerance (picture.same_tf's rule), every timeframe: smoothness within ER_DIFF; the deepest
    pullbacks both under RETR_FLOOR or within a factor RETR; sizes within a factor SIZE; positions within POS."""
    ok = np.ones(len(cand), bool)
    for tf in tfs:
        if "smoothness" in parts:
            ok &= np.abs(V[f"{tf}_er"][cand] - V[f"{tf}_er"][r]) <= ER_DIFF + SIM_TOL
        if "pullback" in parts:
            a, b = V[f"{tf}_retr"][cand], V[f"{tf}_retr"][r]
            with np.errstate(invalid="ignore"):
                ok &= ((a < RETR_FLOOR) & (b < RETR_FLOOR)) | ((np.minimum(a, b) > 0) & (np.maximum(a, b) <= RETR * np.minimum(a, b)))
        if "size" in parts:
            a, b = V[f"{tf}_size"][cand], V[f"{tf}_size"][r]
            with np.errstate(invalid="ignore"):
                ok &= np.isfinite(a) & np.isfinite(b) & (np.maximum(a, b) <= SIZE * np.minimum(a, b))
        if "position" in parts:
            ok &= np.abs(V[f"{tf}_pos"][cand] - V[f"{tf}_pos"][r]) <= POS + SIM_TOL
    return ok


def day_means(days: np.ndarray, rb: np.ndarray, rs: np.ndarray) -> tuple[int, float, float]:
    """Each day's mean R_buy and R_sell over its matching moments, then the mean over the days: (days, buy, sell)."""
    if len(days) == 0:
        return 0, float("nan"), float("nan")
    u, inv = np.unique(days, return_inverse=True)
    cnt = np.bincount(inv)
    return len(u), float((np.bincount(inv, rb) / cnt).mean()), float((np.bincount(inv, rs) / cnt).mean())


def pick(n: float, mb: float, ms: float, n_min: int, theta: float) -> int:
    """The better side (a tie: the buy) when >= n_min days and its mean R >= theta; else 0."""
    if not (n >= n_min and np.isfinite(mb) and np.isfinite(ms)):
        return 0
    if mb >= ms:
        return 1 if mb >= theta - 1e-9 else 0
    return -1 if ms >= theta - 1e-9 else 0


def evidence(P: pd.DataFrame, day: np.ndarray, ok_c: np.ndarray, rows: np.ndarray, tfs: tuple[str, ...],
             parts: tuple[str, ...]) -> np.ndarray:
    """The bot's side: (days, mean R_buy, mean R_sell) for each of rows - candidates (ok_c, >= EPISODE_DAYS before)
    with the same equal readings, then the tolerances."""
    keys = [f"{tf}_{k}" for tf in tfs for p in parts for k in EQUAL.get(p, ())]
    V = {c: P[c].to_numpy(float) for c in P.columns if c.split("_", 1)[0] in tfs}
    rb, rs = P.buy_R.to_numpy(float), P.sell_R.to_numpy(float)
    gid = P.groupby(keys, sort=False, dropna=False).ngroup().to_numpy() if keys else np.zeros(len(P), int)
    members = {g: np.nonzero((gid == g) & ok_c)[0] for g in np.unique(gid)}  # in time order
    out = np.full((len(rows), 3), np.nan)
    for j, r in enumerate(rows):
        mem = members[gid[r]]
        cand = mem[: np.searchsorted(day[mem], day[r] - EPISODE_DAYS, side="right")]
        c = cand[tolerance_mask(V, int(r), cand, tfs, parts)]
        out[j] = day_means(day[c], rb[c], rs[c])
    return out


def recount(P: pd.DataFrame, day: np.ndarray, ok_c: np.ndarray, r: int, tfs: tuple[str, ...], level: str) -> tuple[int, float, float]:
    """My side, from the rules' text with plain pandas: earlier moments (7 days) with a result, on every timeframe of
    the layer the smoothness within 0.1, the deepest pullbacks both under 1 ATR or within 1.6x, the same close against
    the last top / bottom; L6 also the same 120-bar way, sizes within 1.4x, positions within 0.2 and the same edge;
    each day's mean, then the mean over the days."""
    keep = pd.Series(ok_c & (day <= day[r] - 7), index=P.index)
    for tf in tfs:
        col = lambda k: P[f"{tf}_{k}"]  # noqa: E731
        me = lambda k: P[f"{tf}_{k}"].iloc[r]  # noqa: E731
        keep &= (col("er") - me("er")).abs() <= 0.1 + 1e-6
        lo_, hi_ = np.minimum(col("retr"), me("retr")), np.maximum(col("retr"), me("retr"))
        keep &= ((col("retr") < 1.0) & (me("retr") < 1.0)) | ((lo_ > 0) & (hi_ <= 1.6 * lo_))
        keep &= col("brk") == me("brk")
        if level == "L6":
            keep &= col("net_way") == me("net_way")
            lo_, hi_ = np.minimum(col("size"), me("size")), np.maximum(col("size"), me("size"))
            keep &= np.isfinite(col("size")) & np.isfinite(me("size")) & (hi_ <= 1.4 * lo_)
            keep &= ((col("pos") - me("pos")).abs() <= 0.2 + 1e-6) & (col("edge") == me("edge"))
    hit = P[keep.to_numpy()]
    if hit.empty:
        return 0, float("nan"), float("nan")
    per_day = hit.groupby(day[keep.to_numpy()])[["buy_R", "sell_R"]].mean()
    return len(per_day), float(per_day.buy_R.mean()), float(per_day.sell_R.mean())


def main() -> None:
    import plib  # noqa: PLC0415

    plib.gold.below_normal_priority()
    P = pd.read_parquet(HERE / "present_3y.parquet")
    t = pd.DatetimeIndex(P.t_dec)
    day0 = pd.Timestamp("2000-01-01", tz="Asia/Bangkok")
    day = ((t.tz_convert("Asia/Bangkok").normalize() - day0).days).to_numpy()
    ok_c = np.isfinite(P.buy_R.to_numpy(float)) & np.isfinite(P.sell_R.to_numpy(float))
    rows = np.nonzero(ok_c & np.asarray(t >= pd.Timestamp("2024-05-01", tz="UTC")))[0]
    half = np.where(t[rows] >= plib.EXAM_START, "exam", "learn")
    rb, rs = P.buy_R.to_numpy(float), P.sell_R.to_numpy(float)
    # the placebo: the moment at the same clock time on the next trading day
    S = pd.DataFrame({"row": np.arange(len(P)), "day": day, "hm": t.strftime("%H:%M")})
    days = np.sort(np.unique(day))
    nxt = dict(zip(days[:-1], days[1:]))
    by = S.set_index(["day", "hm"]).row
    by = by[~by.index.duplicated()]
    hm = S.hm.to_numpy()
    nrow = np.array([by.get((nxt.get(day[r], -1), hm[r]), -1) for r in rows])
    rng = np.random.default_rng(9)
    ev = []
    for lay, tfs in LAYER_TFS.items():
        for lv, parts in LEVELS.items():
            out = evidence(P, day, ok_c, rows, tfs, parts)
            for j in rng.choice(len(rows), size=150, replace=False):  # both sides agree before anything is read
                n2, b2, s2 = recount(P, day, ok_c, int(rows[j]), tfs, lv)
                n1, b1, s1 = out[j]
                assert n1 == n2 and ((np.isnan(b1) and np.isnan(b2)) or (abs(b1 - b2) < 1e-9 and abs(s1 - s2) < 1e-9)), (lay, lv, j)
            ev.append(pd.DataFrame({"layer": lay, "level": lv, "row": rows, "n": out[:, 0], "mb": out[:, 1], "ms": out[:, 2]}))
            print(lay, lv, "evidence done; 150 moments recounted on my side, all equal", flush=True)
    E = pd.concat(ev, ignore_index=True)
    E.to_parquet(HERE / "present_evidence.parquet")
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
                if len(d) > 1:
                    gd = pd.Series(d).groupby(day[r])
                    se = float(np.sqrt(((gd.sum() - d.mean() * gd.size()) ** 2).sum()) / len(d))
                else:
                    se = np.nan
                pr = nrow[k]
                okp = (pr >= 0) & ok_c[np.maximum(pr, 0)]
                gp = np.where(side[k][okp] > 0, rb[pr[okp]], rs[pr[okp]]) - (rb[pr[okp]] + rs[pr[okp]]) / 2
                res.append(dict(layer=lay, level=lv, n_min=n_min, theta=theta, half=h, picks=int(k.sum()),
                                days=len(np.unique(day[r])), R=float(got.mean()) if len(got) else np.nan,
                                edge=float(d.mean()) if len(d) else np.nan, se_day=se,
                                placebo=float(gp.mean()) if len(gp) else np.nan))
    D = pd.DataFrame(res)
    D.to_csv(HERE / "present_premise.csv", index=False)
    pd.set_option("display.width", 230)
    pd.set_option("display.max_rows", 500)
    pd.set_option("display.float_format", lambda v: f"{v:+.3f}")
    W = D.pivot_table(index=["layer", "level", "n_min", "theta"], columns="half",
                      values=["picks", "days", "R", "edge", "se_day", "placebo"])
    W.columns = [f"{a}_{b}" for a, b in W.columns]
    W = W[[f"{a}_{h}" for h in ("learn", "exam") for a in ("picks", "days", "R", "edge", "se_day", "placebo")]]
    for h in ("learn", "exam"):
        k = half == h
        print(f"{h}: {int(k.sum())} moments; a coin's side earns {((rb[rows[k]] + rs[rows[k]]) / 2).mean():+.3f} R")
    print("\nthe premise: R of the side picked, its edge over a coin's side (+- se by day), the placebo (next day); both halves")
    print(W.reset_index().to_string(index=False))


if __name__ == "__main__":
    main()
