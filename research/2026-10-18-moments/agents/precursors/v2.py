"""Setup OWN V2 (notes.md "Setup OWN V2"): the bot weighs each snap with the walk-forward library, places a 3 U
straddle when the run weight is high enough, and exits on the entry timeframe.

    PYTHONDONTWRITEBYTECODE=1 data/venv-research/Scripts/python research/2026-10-18-moments/agents/precursors/v2.py design
    ... v2.py window B2 0.40 1.0 1.0     (the one window run of a frozen cell)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import plib
from cluster_fp import core_cols, onehot
from plib import HERE

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "journal"))
import jlib  # noqa: E402

T0 = time.time()
LAYERS = {"context": ("H4", "H1"), "setup": ("M30", "M15"), "trigger": ("M5", "M1")}
ETF = (("M1", None, 1), ("M5", "5min", 5), ("M15", "15min", 15), ("M30", "30min", 30))
THR, MIN_N, SHRINK = 0.80, 10, 30.0
START_U, TRIG_MIN, BE_SHARE, TIME_BARS = 3.0, 30, 0.6, 6
THETAS, KTP, KSL = (0.30, 0.40, 0.50), (0.75, 1.0, 1.5), (0.75, 1.0)
pd.set_option("display.width", 250)


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.0f}s] {msg}", flush=True)


def weights(S: pd.DataFrame, F: pd.DataFrame) -> pd.DataFrame:
    day = S.S.dt.tz_convert("Asia/Bangkok").dt.normalize().to_numpy()
    ran = S.cls.isin(["ran_up", "ran_dn"]).to_numpy().astype(float)
    cont = np.where(S.cont10.to_numpy() == 1, S.start3.fillna(0).to_numpy(), 0.0)
    # the base of each snap's time from earlier days (walk-forward; the same time occurs once a day)
    base = np.full(len(S), np.nan)
    for _n, idx in S.groupby("name").indices.items():
        r = ran[idx]
        cs = np.cumsum(r) - r
        k = np.arange(len(idx))
        base[idx] = np.where(k > 0, cs / np.maximum(k, 1), np.nan)
    W = pd.DataFrame({"base": base}, index=S.index)
    gb = np.nan_to_num(base, nan=np.nanmean(ran))
    for layer, tfs in LAYERS.items():
        cols = []
        for tf in tfs:
            cols += core_cols(F, tf)
            if f"{tf}_sr_loc" in S.columns:
                cols.append(S[f"{tf}_sr_loc"].to_numpy())
        V = onehot(cols)
        n = np.zeros(len(S))
        rm = np.full(len(S), np.nan)
        bm = np.full(len(S), np.nan)
        cu = np.full(len(S), np.nan)
        cd = np.full(len(S), np.nan)
        for a in range(0, len(S), 1500):
            sims = V[a:a + 1500] @ V.T
            mask = (sims >= THR - 1e-6) & (day[None, :] < day[a:a + 1500, None])
            mf = mask.astype(np.float32)
            cnt = mf.sum(axis=1)
            n[a:a + 1500] = cnt
            with np.errstate(invalid="ignore", divide="ignore"):
                rm[a:a + 1500] = (mf @ ran) / cnt
                bm[a:a + 1500] = (mf @ gb) / cnt
                cu[a:a + 1500] = (mf @ (cont > 0).astype(np.float32)) / cnt
                cd[a:a + 1500] = (mf @ (cont < 0).astype(np.float32)) / cnt
        W[f"n_{layer}"], W[f"run_{layer}"], W[f"base_{layer}"] = n, rm, bm
        W[f"cup_{layer}"], W[f"cdn_{layer}"] = cu, cd
        log(f"{layer}: matches median {np.median(n):.0f}, >= {MIN_N}: {(n >= MIN_N).mean():.0%}")
    W["w_time"] = W.base
    form = W.base.copy()
    for layer in LAYERS:
        ok = W[f"n_{layer}"] >= MIN_N
        w = W[f"n_{layer}"] / (W[f"n_{layer}"] + SHRINK)
        form = form + np.where(ok, w * (W[f"run_{layer}"] - W[f"base_{layer}"]), 0.0)
    W["w_form"] = form
    ok = W.n_trigger >= MIN_N
    diff = W.cup_trigger - W.cdn_trigger
    W["side_only"] = np.where(ok & (diff >= 0.10), 1, np.where(ok & (diff <= -0.10), -1, 0))
    return W


def entry_tf(m: pd.DataFrame, S: pd.DataFrame) -> pd.DataFrame:
    s_ts = S.S.to_numpy()
    out = {}
    for name, rule, mins in ETF:
        if rule is None:
            b = m.reset_index(drop=True)
            bi = S.idx.to_numpy()
        else:
            b = plib.tf_bars(m, rule)
            bi = np.searchsorted(b["avail"].to_numpy(), s_ts, side="right") - 1
        h, lo, c = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
        pc = np.r_[np.nan, c[:-1]]
        tr = np.nanmax(np.vstack([h - lo, np.abs(h - pc), np.abs(lo - pc)]), axis=0)
        out[name] = pd.Series(tr).rolling(14).mean().to_numpy()[bi]
    A = pd.DataFrame(out, index=S.index)
    tf = np.select([A.M1 >= 5, A.M5 >= 5, A.M15 >= 5], ["M1", "M5", "M15"], "M30")
    atr = np.select([tf == "M1", tf == "M5", tf == "M15"], [A.M1, A.M5, A.M15], A.M30)
    mins = np.select([tf == "M1", tf == "M5", tf == "M15"], [1, 5, 15], 30)
    return pd.DataFrame({"etf": tf, "atr_e": atr, "etf_min": mins}, index=S.index)


def triggers(P: jlib.Instr, S: pd.DataFrame) -> pd.DataFrame:
    """The straddle: the first bar within 30 minutes after the snap whose ask reaches ref + 3 U (buy) or bid ref - 3 U."""
    ot = P.ot
    e0 = ot.searchsorted(pd.DatetimeIndex(S.S))
    ref = S.ref.to_numpy()
    lev = START_U * S.u.to_numpy()
    rows = []
    for k in range(len(S)):
        j = e0[k]
        side, ent, jj = 0, np.nan, -1
        while j < len(ot) and ot[j] < S.S.iloc[k] + pd.Timedelta(minutes=TRIG_MIN):
            up = P.h[j] + P.sp[j] >= ref[k] + lev[k]
            dn = P.lo[j] <= ref[k] - lev[k]
            if up and dn:
                side = 9  # both in one bar: unknown order, no trade
                break
            if up:
                side, ent, jj = 1, max(ref[k] + lev[k], P.o[j] + P.sp[j]) + P.slip, j
                break
            if dn:
                side, ent, jj = -1, min(ref[k] - lev[k], P.o[j]) - P.slip, j
                break
            j += 1
        rows.append((side, ent, jj))
    return pd.DataFrame(rows, columns=["tside", "tentry", "tj"], index=S.index)


def manage(P: jlib.Instr, j0: int, side: int, entry: float, tp: float, sl: float, hz_min: int, ss: float) -> dict:
    stop, armed, mfe = entry - side * sl, False, 0.0
    t_end = P.ot[j0] + pd.Timedelta(minutes=hz_min)
    j = j0
    res = None
    while j < len(P.ot) and P.ot[j] < t_end:
        adv = P.lo[j] if side > 0 else P.h[j] + P.sp[j]
        fav = P.h[j] if side > 0 else P.lo[j] + P.sp[j]
        if (adv - stop) * side <= 0:
            res = ("stop" if not armed else "be", (stop - side * ss - entry) * side, j)
            break
        if j > j0 and (fav - entry) * side >= tp:
            res = ("win", tp, j)
            break
        if j > j0:
            mfe = max(mfe, (fav - entry) * side)
        if not armed and mfe >= BE_SHARE * tp:
            armed, stop = True, entry
        j += 1
    if res is None:
        x = max(j - 1, j0)
        px = P.c[x] - (P.slip if side > 0 else -(P.sp[x] + P.slip))
        res = ("time", (px - entry) * side, x)
    kind = ""
    if res[0] == "stop":
        later = range(res[2] + 1, min(j0 + 120, len(P.o)))
        hit = any(((P.h[q] if side > 0 else P.lo[q] + P.sp[q]) - entry) * side >= tp for q in later)
        kind = "3" if hit else ("2" if mfe >= 0.5 * tp else "1")
    return dict(exit=res[0], pnl=res[1], xj=res[2], kind=kind)


def simulate(P, S, T, E, sel: np.ndarray, side_only: np.ndarray | None, ktp: float, ksl: float) -> pd.DataFrame:
    rows = []
    busy_until = -1
    for k in np.nonzero(sel)[0]:
        side = int(T.tside.iloc[k])
        if side not in (1, -1):
            continue
        j0 = int(T.tj.iloc[k])
        if j0 <= busy_until:
            continue
        if side_only is not None and side_only[k] != 0 and side_only[k] != side:
            continue
        atr = float(E.atr_e.iloc[k])
        tp, sl = max(5.0, ktp * atr), max(3.0, ksl * atr)
        ny = S.name.iloc[k].startswith("NY")
        ss = P.stop_slip_ny if ny else P.stop_slip
        r = manage(P, j0, side, float(T.tentry.iloc[k]), tp, sl, TIME_BARS * int(E.etf_min.iloc[k]), ss)
        busy_until = r["xj"]
        r |= dict(S=S.S.iloc[k], name=S.name.iloc[k], half=S.half.iloc[k], side=side, tp=tp, sl=sl,
                  R=r["pnl"] / (sl + ss), etf=E.etf.iloc[k])
        rows.append(r)
    return pd.DataFrame(rows)


def summary(t: pd.DataFrame, days: int) -> dict:
    if t.empty:
        return dict(trades=0)
    halves = t.groupby("half").R.mean()
    eq = t.pnl.cumsum()
    return dict(trades=len(t), per_day=round(len(t) / days, 2), win=round((t.pnl > 0).mean(), 3),
                R=round(t.R.mean(), 3), usd=round(t.pnl.sum(), 1), halves=" ".join(f"{halves.get(h, np.nan):+.2f}"
                                                                                   for h in ["H1", "H2", "H3", "H4", "H5", "W"] if h in halves.index),
                worst=round(t.pnl.min(), 1), maxdd=round((eq.cummax() - eq).max(), 1),
                kinds="/".join(f"{(t[t.exit == 'stop'].kind == q).mean():.0%}" for q in "123"))


def main() -> None:
    plib.gold.below_normal_priority()
    mode = sys.argv[1] if len(sys.argv) > 1 else "design"
    S = pd.read_parquet(HERE / "snaps.parquet")
    F = pd.read_parquet(HERE / "snap_fingerprints.parquet")
    m = plib.load()
    W = weights(S, F)
    E = entry_tf(m, S)
    P = jlib.Instr("XAUUSD")
    T = triggers(P, S)
    log(f"triggers: {T.tside.value_counts().to_dict()}")
    part = (S.half != "W").to_numpy() if mode == "design" else (S.half == "W").to_numpy()
    days = S[part].S.dt.tz_convert("Asia/Bangkok").dt.normalize().nunique()
    if mode == "design":
        print(E[part].groupby(S[part].S.dt.strftime("%Y-%m")).etf.value_counts(normalize=True).unstack().round(2).to_string())
        rows = []
        for ktp in KTP:
            for ksl in KSL:
                t = simulate(P, S, T, E, part, None, ktp, ksl)
                rows.append(dict(variant="B0 every snap", theta="-", k_tp=ktp, k_sl=ksl) | summary(t, days))
                for th in THETAS:
                    for var, sel, so in (("B1 time", W.w_time.to_numpy() >= th, None),
                                         ("B2 formation", W.w_form.to_numpy() >= th, None),
                                         ("B3 formation+side", W.w_form.to_numpy() >= th, W.side_only.to_numpy())):
                        t = simulate(P, S, T, E, part & np.nan_to_num(sel, nan=0).astype(bool), so, ktp, ksl)
                        rows.append(dict(variant=var, theta=th, k_tp=ktp, k_sl=ksl) | summary(t, days))
            log(f"k_tp {ktp} done")
        R = pd.DataFrame(rows)
        R.to_csv(HERE / "v2_design.csv", index=False)
        print(R.to_string(index=False))
    else:
        var, th, ktp, ksl = sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
        w = W.w_time if var == "B1" else W.w_form
        so = W.side_only.to_numpy() if var == "B3" else None
        sel = part & (w.to_numpy() >= th) if var != "B0" else part
        t = simulate(P, S, T, E, sel, so, ktp, ksl)
        t.to_parquet(HERE / f"v2_window_{var}.parquet")
        print(summary(t, days))
        print(t.groupby(t.S.dt.strftime("%Y-%m")).agg(n=("R", "size"), R=("R", "mean"), usd=("pnl", "sum")).round(3))


if __name__ == "__main__":
    main()
