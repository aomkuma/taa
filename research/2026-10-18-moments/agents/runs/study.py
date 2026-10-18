"""Round 2, step 1 (notes.md): "ended vs continued". Every R15 / 2.5-ATR run whose first 40 % pullback gives RUN-A's
count-three turn; at the decision close, features a trader could know; the label from the decision (continued = a
new extreme beyond the run before its start is broken, within 120 min; ended = the start broken first) and A7's
trade with its mirror. Labels and trades only for the design rows (before 2026-03-01); the window rows keep their
features only (for the frozen rules later).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/study.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rules  # noqa: E402
from features import at_close, htf  # noqa: E402

gold, jlib = rules.gold, rules.jlib
REF = 4100.0
SPLIT = pd.Timestamp("2026-03-01", tz="UTC")
ROOT = HERE.parents[3]


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def macd_hist(c: pd.Series) -> pd.Series:
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    return m - m.ewm(span=9, adjust=False).mean()


def turns(P: jlib.Instr, C: pd.DataFrame, void: int = 60) -> pd.DataFrame:
    """RUN-A's trigger without filters: after the leg-end bar (the first 40 % pullback), the pullback extreme counts
    once 3 bars do not exceed it and a close goes beyond the bar that made it; void if the start breaks or 60 min."""
    o, h, lo, c, ot = P.o, P.h, P.lo, P.c, P.ot
    rows = []
    for r in C.itertuples():
        s = int(r.side)
        k0 = ot.searchsorted(r.t_end)
        if k0 >= len(ot) - 200 or ot[k0] != r.t_end:
            continue
        i_s, xj = ot.searchsorted(r.t), ot.searchsorted(r.t_ext)
        start, ext = r.start_px, r.start_px + s * r.size
        pl, lb, quiet = (lo[k0], k0, 0) if s > 0 else (h[k0], k0, 0)
        k, found = k0 + 1, None
        while k < k0 + void:
            x = lo[k] if s > 0 else h[k]
            if (x - pl) * s < 0:
                pl, lb, quiet = x, k, 0
                if (pl - start) * s < 0:
                    break
            else:
                quiet += 1
                turn = h[lb] if s > 0 else lo[lb]
                if quiet >= 3 and (c[k] - turn) * s > 0:
                    found = k
                    break
            k += 1
        if found is None or ot[found].hour >= 20 or ot[found].dayofweek >= 5:
            continue
        rows.append(dict(d=found, e=found + 1, t=ot[found + 1], side=s, start=start, ext=ext, run_t=r.t, t_ext=r.t_ext,
                         i_s=i_s, xj=xj, k0=k0, pl=pl, lb=lb, size=r.size, size_atr=r.size_atr, dur=r.dur,
                         mins_to_R=r.mins_to_R, atr15=r.atr15, u=o[found + 1] / REF))
    return pd.DataFrame(rows)


def label(P: jlib.Instr, S: pd.DataFrame) -> np.ndarray:
    out = []
    for r in S.itertuples():
        seg = slice(r.d + 1, min(r.d + 121, len(P.o)))
        hh, ll = P.h[seg], P.lo[seg]
        if r.side > 0:
            cont, end = hh > r.ext, ll < r.start
        else:
            cont, end = ll < r.ext, hh > r.start
        jc = np.argmax(cont) if cont.any() else 10**6
        je = np.argmax(end) if end.any() else 10**6
        out.append("neither" if jc == je == 10**6 else ("continued" if jc < je else "ended"))
    return np.array(out)


def trades(P: jlib.Instr, S: pd.DataFrame, AD: pd.DataFrame) -> pd.DataFrame:
    """A7's trade on every signal (no one-position rule) and its mirror."""
    res = []
    ad_atr = AD.ad_atr_usd.reindex(P.ot[S.d.to_numpy()]).to_numpy()
    for r, a in zip(S.itertuples(), ad_atr, strict=True):
        s = r.side
        fill = float(P.fill(np.array([r.e]), np.array([s]))[0])
        stop = r.pl - s * 0.3 * r.u
        sl = max((fill - stop) * s, 0.5 * a)
        if not (3.0 <= sl <= 10.0):
            res.append(dict(R=np.nan, mR=np.nan, sl=sl, exit="", kind=""))
            continue
        tp = 8 * r.u
        ss = P.stop_slip_ny if r.t.hour >= 12 else P.stop_slip
        x = P.trade(int(r.e), s, tp, sl, 0.6, 120, ss)
        y = P.trade(int(r.e), -s, tp, sl, 0.6, 120, ss)
        res.append(dict(R=x["pnl"] / (sl + ss), mR=y["pnl"] / (sl + ss), sl=sl, exit=x["exit"], kind=x["kind"],
                        pnl=x["pnl"]))
    return pd.DataFrame(res, index=S.index)


def features(P: jlib.Instr, S: pd.DataFrame, C15: pd.DataFrame) -> pd.DataFrame:
    o, h, lo, c, v, ot = P.o, P.h, P.lo, P.c, P.v, P.ot
    n = len(ot)
    s = S.side.to_numpy()
    d = S.d.to_numpy()
    i_s = S.i_s.to_numpy()
    xj = S.xj.to_numpy()
    ext, start, size = S.ext.to_numpy(), S.start.to_numpy(), S["size"].to_numpy()
    X = pd.DataFrame(index=S.index)
    # (a) server days (Europe/Athens), the 20-day average daily range
    sday = ot.tz_convert("Europe/Athens").normalize()
    key = pd.Series(sday.asi8)
    g = pd.DataFrame({"h": h, "l": lo, "k": key.to_numpy()})
    daily = g.groupby("k").agg(h=("h", "max"), l=("l", "min"), n=("h", "size"))
    daily = daily[daily.n >= 300]
    rng = daily.h - daily.l
    adr = rng.rolling(20).mean().shift(1)
    yh, yl = daily.h.shift(1), daily.l.shift(1)
    w5h, w5l = daily.h.rolling(5).max().shift(1), daily.l.rolling(5).min().shift(1)
    kd = key.to_numpy()[d]
    ADR = adr.reindex(kd).to_numpy()
    dhi = g.groupby("k").h.cummax().to_numpy()
    dlo = g.groupby("k").l.cummin().to_numpy()
    X["adr_usd"] = ADR
    X["adr_used"] = (dhi[d] - dlo[d]) / ADR
    X["size_adr"] = size / ADR
    X["from_opp_adr"] = np.where(s > 0, ext - dlo[d], dhi[d] - ext) / ADR
    # (b) levels in the run's way: where the run's extreme ended against them, in M15 ATRs (+ = beyond)
    a15 = S.atr15.to_numpy()
    ks = key.to_numpy()[i_s]
    lv = {"yday": np.where(s > 0, yh.reindex(ks).to_numpy(), yl.reindex(ks).to_numpy()),
          "d5": np.where(s > 0, w5h.reindex(ks).to_numpy(), w5l.reindex(ks).to_numpy())}
    hs = pd.Series(h, index=ot).rolling("72h").max().to_numpy()
    ls = pd.Series(lo, index=ot).rolling("72h").min().to_numpy()
    lv["h72"] = np.where(s > 0, hs[i_s - 1], ls[i_s - 1])
    # H1 fractal swings (5 bars), confirmed at the end of the second bar after
    H1 = htf(P.m, 60)
    hh, hl_ = H1.high.to_numpy(), H1.low.to_numpy()
    fh = np.zeros(len(H1), bool)
    fl = np.zeros(len(H1), bool)
    fh[2:-2] = (hh[2:-2] > np.maximum(hh[:-4], hh[1:-3])) & (hh[2:-2] >= np.maximum(hh[3:-1], hh[4:]))
    fl[2:-2] = (hl_[2:-2] < np.minimum(hl_[:-4], hl_[1:-3])) & (hl_[2:-2] <= np.minimum(hl_[3:-1], hl_[4:]))
    conf_t = (H1.index + pd.Timedelta(hours=3)).as_unit("ns").asi8
    made_t = H1.index.as_unit("ns").asi8
    sw = []
    for k in range(len(S)):
        t0 = ot[i_s[k]].value
        F = fh if s[k] > 0 else fl
        L = hh if s[k] > 0 else hl_
        a, b = np.searchsorted(made_t, t0 - 72 * 3600 * 10**9), np.searchsorted(conf_t, t0, side="right")
        idx = np.nonzero(F[a:b])[0] + a
        lvls = L[idx]
        lvls = lvls[(lvls - start[k]) * s[k] > 0]
        sw.append(np.nan if not len(lvls) else (ext[k] - lvls[np.argmin(np.abs(ext[k] - lvls))]) * s[k])
    lv["h1sw"] = np.array(sw) + 0  # already signed distance in price
    for name, L in lv.items():
        if name == "h1sw":
            dist = L / a15
        else:
            ahead = (L - start) * s > 0
            dist = np.where(ahead, (ext - L) * s / a15, np.nan)
        X[f"lvl_{name}"] = dist
    allv = np.vstack([X[f"lvl_{k}"].to_numpy() for k in lv])
    absd = np.where(np.isfinite(allv), np.abs(allv), np.inf)
    pick = np.argmin(absd, axis=0)
    X["lvl_any"] = np.where(np.isfinite(absd.min(0)), allv[pick, np.arange(len(S))], np.nan)
    # (c) the wave count: same-side 1.5-ATR runs since the 8-hour extreme before the run
    W = 480
    pushes, swing = [], []
    c15 = {sd: (pd.DatetimeIndex(g_.t).as_unit("ns").asi8) for sd, g_ in C15.groupby("side")}
    for k in range(len(S)):
        a = max(i_s[k] - W, 0)
        if s[k] > 0:
            io = a + int(np.argmin(lo[a : i_s[k] + 1]))
            org = lo[io]
        else:
            io = a + int(np.argmax(h[a : i_s[k] + 1]))
            org = h[io]
        tt = c15[s[k]]
        cnt = np.searchsorted(tt, ot[i_s[k]].value - 60 * 10**9, side="right") - np.searchsorted(tt, ot[io].value)
        pushes.append(max(cnt, 0) + 1)
        swing.append((ext[k] - org) * s[k])
    X["wave"] = pushes
    X["swing_adr"] = np.array(swing) / ADR
    # (d) acceleration, speed, volume climax
    last3 = []
    vcl = []
    vrun = []
    for k in range(len(S)):
        j0 = xj[k] - 3
        ref = c[j0] if j0 >= i_s[k] else start[k]
        last3.append((ext[k] - ref) * s[k] / size[k])
        med = np.median(v[max(i_s[k] - 1440, 0) : i_s[k]])
        vcl.append(v[max(xj[k] - 2, i_s[k]) : xj[k] + 1].max() / med)
        vrun.append(v[i_s[k] : xj[k] + 1].mean() / med)
    X["last3"] = last3
    X["speed"] = S.size_atr.to_numpy() / S.dur.to_numpy()
    X["vol_climax"] = vcl
    X["vol_run"] = vrun
    # (e) M5 / M15 RSI and MACD-histogram divergence
    hmax3 = pd.Series(h).rolling(180).max().shift(1).to_numpy()
    lmin3 = pd.Series(lo).rolling(180).min().shift(1).to_numpy()
    new3h = np.where(s > 0, ext > hmax3[i_s], ext < lmin3[i_s])
    X["new3h"] = new3h.astype(float)
    for tf, back in ((5, 180), (15, 360)):
        B = htf(P.m, tf)
        end_t = pd.DatetimeIndex(B.end).as_unit("ns").asi8
        for oname, osc in (("rsi", rsi(B.close)), ("macd", macd_hist(B.close) / B.atr)):
            ov = osc.to_numpy()
            div, runx = [], []
            for k in range(len(S)):
                t0 = ot[i_s[k]].value
                tdec = ot[d[k]].value + 60 * 10**9
                a, b = np.searchsorted(end_t, t0 - back * 60 * 10**9, side="right"), np.searchsorted(end_t, t0, side="right")
                b2 = np.searchsorted(end_t, tdec, side="right")
                pr, ru = ov[a:b], ov[b:b2]
                if not len(pr) or not len(ru):
                    div.append(np.nan)
                    runx.append(np.nan)
                    continue
                pm = np.nanmax(pr * s[k])
                rm = np.nanmax(ru * s[k])
                runx.append(rm)
                div.append(float(new3h[k] and rm < pm) if new3h[k] else np.nan)
            X[f"div_{oname}{tf}"] = div
            X[f"{oname}{tf}_runmax"] = runx
    # (f) H1 EMA20 / EMA50 distance in H1 ATRs (signed: + = beyond in the run's way)
    for span in (20, 50):
        e = H1.close.ewm(span=span, adjust=False).mean()
        dist = (c - at_close(e, H1.end, ot)) / at_close(H1.atr, H1.end, ot)
        X[f"h1_e{span}"] = dist[d] * s
    # (g) the dollar: EURUSD (inverse)
    eu = pd.read_parquet(ROOT / "data/history/FBS-Demo/EURUSD/M1.parquet", columns=["open_time", "high", "low", "close"])
    eu.index = pd.DatetimeIndex(pd.to_datetime(eu.open_time, utc=True))
    eu = eu[~eu.index.duplicated(keep="last")].sort_index().reindex(ot, method="ffill", limit=3)
    eh, el, ec = (eu[k].to_numpy(float) for k in ("high", "low", "close"))
    lc = np.log(ec)
    sc = pd.Series(np.abs(np.diff(lc, prepend=np.nan))).rolling(1440, min_periods=200).mean().shift(1).to_numpy()
    ehm3 = pd.Series(eh).rolling(180).max().shift(1).to_numpy()
    elm3 = pd.Series(el).rolling(180).min().shift(1).to_numpy()
    conf, fit = [], []
    for k in range(len(S)):
        seg = slice(i_s[k], min(xj[k] + 3, n))
        if s[k] > 0:  # gold up: a confirming dollar = EURUSD up to a new 3-hour high
            cf = np.nanmax(eh[seg]) > ehm3[i_s[k]]
        else:
            cf = np.nanmin(el[seg]) < elm3[i_s[k]]
        conf.append(float(cf) if new3h[k] else np.nan)
        fit.append((lc[xj[k]] - lc[i_s[k] - 1]) * s[k] / (sc[i_s[k]] * np.sqrt(max(S.dur.iloc[k], 1))))
    X["usd_confirm"] = conf
    X["usd_fit_z"] = fit
    # (h) session and the minutes since its open; (i) a US release inside the run
    F = pd.read_parquet(HERE / "feats.parquet", columns=["min_ldn", "min_ny", "h1_tide", "m15_tide", "m15_e20_dist",
                                                         "tv60_1440", "atr15_ratio"])
    Fd = F.reindex(ot[d])
    hr = ot[d].hour.to_numpy()
    X["session"] = np.where(hr < 7, 0, np.where(hr < 12, 1, 2))
    X["min_sess"] = np.where(hr < 7, hr * 60 + ot[d].minute.to_numpy(),
                             np.where(hr < 12, Fd.min_ldn.to_numpy() + 60, Fd.min_ny.to_numpy()))
    X["hour"] = hr
    rel = pd.DatetimeIndex(gold.releases().t).sort_values().as_unit("ns").asi8
    a0 = pd.DatetimeIndex(S.run_t).as_unit("ns").asi8 - 5 * 60 * 10**9
    b0 = pd.DatetimeIndex(S.t_ext).as_unit("ns").asi8 + 60 * 10**9
    X["rel_in_run"] = (np.searchsorted(rel, b0) > np.searchsorted(rel, a0)).astype(float)
    X["h1_tide"] = Fd.h1_tide.to_numpy() * s
    X["m15_tide"] = Fd.m15_tide.to_numpy() * s
    X["m15_e20"] = Fd.m15_e20_dist.to_numpy() * s
    X["tv60_1440"] = Fd.tv60_1440.to_numpy()
    X["atr15_ratio"] = Fd.atr15_ratio.to_numpy()
    # (j) the run's age at the decision, the pullback's depth and length
    X["age"] = (pd.DatetimeIndex(S.t) - pd.DatetimeIndex(S.run_t)).total_seconds().to_numpy() / 60
    X["depth"] = (ext - S.pl.to_numpy()) * s / size
    X["pb_min"] = d - xj
    return X


def main() -> None:
    gold.below_normal_priority()
    P = jlib.Instr("XAUUSD")
    Call = pd.read_parquet(HERE / "catalogue.parquet")
    C15 = Call[Call.R == 1.5]
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_tf", "ad_atr_usd"])
    for R in (15.0, 2.5):
        C = Call[Call.R == R].sort_values("t")
        S = turns(P, C)
        X = features(P, S, C15)
        S = pd.concat([S, X], axis=1)
        S["part"] = np.where(S.t < SPLIT, "design", "window")
        S["half"] = pd.cut(S.t, rules.HALVES, labels=["H1", "H2", "H3", "H4", "H5"], right=False)
        des = S[S.part == "design"].copy()
        des["label"] = label(P, des)
        des = pd.concat([des, trades(P, des, AD)], axis=1)
        tag = "R15" if R == 15 else "A25"
        des.to_parquet(HERE / f"study_{tag}_design.parquet")
        S[S.part == "window"].to_parquet(HERE / f"study_{tag}_window_feats.parquet")
        print(f"{tag}: signals design {len(des)}, window {int((S.part == 'window').sum())}; labels "
              + " ".join(f"{k} {100 * v:.0f}%" for k, v in des.label.value_counts(normalize=True).items())
              + f"; trade R {des.R.mean():+.3f} (n {des.R.notna().sum()}), mirror {des.mR.mean():+.3f}")


if __name__ == "__main__":
    main()
