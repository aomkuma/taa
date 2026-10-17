"""Step 1: foundations on H1-scale returns, design data only (2023-11 .. 2026-02, five halves).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/foundations.py > .../out_foundations.txt
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import fxlib as fx  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]
UD = {p: (1 if p in fx.USD_BASE else -1) for p in fx.PAIRS}  # +1: price up = USD up


def fmt(v, w=6, p=1):
    return " ".join(f"{x:+{w}.{p}f}" if np.isfinite(x) else " " * (w - 1) + "-" for x in v)


def agree(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if not len(v):
        return " -"
    s = np.sign(v.sum())
    return f"{int((np.sign(v) == s).sum())}/{len(v)}"


def window_ret(P: fx.Pair, tz, d0: str, d1: str, h0: float, h1: float) -> pd.DataFrame:
    """Per local day: bid close at local hour h0 (the bar before) -> local hour h1, in pips (minute bars)."""
    loc = P.ot.tz_convert(tz)
    lm = loc.hour * 60 + loc.minute
    day = loc.normalize().tz_localize(None)
    s = pd.Series(P.c, index=P.ot)
    a = int(round(h0 * 60))
    b = int(round(h1 * 60)) - 1
    ia = pd.Series(np.flatnonzero(lm == a), index=day[lm == a])
    ib = pd.Series(np.flatnonzero(lm == b), index=day[lm == b])
    ia = ia[~ia.index.duplicated()]
    ib = ib[~ib.index.duplicated()]
    j = pd.concat({"a": ia, "b": ib}, axis=1).dropna().astype(int)
    out = pd.DataFrame({"ret": P.c[j.b.to_numpy()] - P.o[j.a.to_numpy()]}, index=j.index)
    out["t"] = P.ot[j.a.to_numpy()]
    out["hi"] = [P.h[x:y + 1].max() for x, y in zip(j.a, j.b)]
    out["lo"] = [P.lo[x:y + 1].min() for x, y in zip(j.a, j.b)]
    out["half"] = fx.half_of(out.t)
    del s
    return out[out.half.isin(H)]


def main() -> None:
    allh = {}
    for p in fx.PAIRS:
        P = fx.Pair(p)
        b = P.h1()
        b = b[(b.n >= 30)]
        b["r"] = b.c - b.c.shift(1)
        b["gap"] = (b.index.to_series().diff() != pd.Timedelta(hours=1)).to_numpy()
        b.loc[b.gap, "r"] = np.nan
        b["half"] = fx.half_of(b.index)
        b["hr"] = b.index.hour
        b["wd"] = b.index.dayofweek
        b = b[b.half.isin(H)]
        allh[p] = (P, b)

    print("=== A. Variance ratios and autocorrelation, H1 returns standardised by hour-of-day sd per half, "
          "within 00-20 UTC days ===")
    print("pair    half   VR2   VR4   VR8 | ac1   ac2   ac3   ac4  (x100) | corr(last 4h, next 4h) x100")
    for p in fx.PAIRS:
        P, b = allh[p]
        for hname in H:
            x = b[(b.half == hname) & (b.hr < 20)].copy()
            sd = x.groupby("hr").r.transform("std")
            x["z"] = (x.r / sd)
            x["z"] = x.z - x.z.mean()
            x["day"] = x.index.normalize()
            var1 = (x.z ** 2).mean()
            vr = []
            for k in (2, 4, 8):
                ss = x.groupby("day").z.transform(lambda s: s.rolling(k).sum())
                vr.append(np.nanmean(ss ** 2) / (k * var1))
            ac = []
            for lag in (1, 2, 3, 4):
                lagged = x.groupby("day").z.shift(lag)
                m = lagged.notna() & x.z.notna()
                ac.append(100 * np.corrcoef(x.z[m], lagged[m])[0, 1])
            s4 = x.groupby("day").z.transform(lambda s: s.rolling(4).sum())
            n4 = x.groupby("day").z.transform(lambda s: s[::-1].rolling(4).sum()[::-1].shift(-1))
            m = s4.notna() & n4.notna()
            c4 = 100 * np.corrcoef(s4[m], n4[m])[0, 1]
            print(f"{p} {hname}  {vr[0]:.3f} {vr[1]:.3f} {vr[2]:.3f} | {fmt(ac, 5, 1)} | {c4:+5.1f}")
        print()

    print("=== B. Drift by UTC hour (mean pips per hour, price direction), halves 23H2..25H2, agreement ===")
    hrs = list(range(0, 21))
    keep = []
    for p in fx.PAIRS:
        P, b = allh[p]
        print(f"--- {p}  (hour: " + " ".join(H) + " | all-design mean, t, agree)")
        for hr in hrs:
            x = b[b.hr == hr]
            v = [x[x.half == hn].r.mean() for hn in H]
            allx = x.r.dropna()
            t = allx.mean() / allx.std() * np.sqrt(len(allx))
            ag = agree(v)
            flag = " *" if ag.startswith(("5/", "4/")) and abs(t) > 2 else ""
            print(f"  {hr:02d}  {fmt(v, 5, 2)} | {allx.mean():+5.2f} t={t:+5.2f} {ag}{flag}")
            if flag:
                keep.append((p, hr, allx.mean(), t, ag))
    print("\nKept hour effects (4-5/5 halves and |t| > 2):")
    for k in keep:
        print("  ", k)

    print("\n=== B2. USD-direction drift by UTC hour (mean over the 7 pairs of USD-up pips, sd-scaled), halves ===")
    for hr in hrs:
        rows = []
        for hn in H:
            vals = []
            for p in fx.PAIRS:
                P, b = allh[p]
                x = b[(b.hr == hr)]
                sd = x.r.std()
                vals.append(UD[p] * x[x.half == hn].r.mean() / sd)
            rows.append(100 * np.mean(vals))
        print(f"  {hr:02d}  {fmt(rows, 6, 1)}  (x100 sd)  {agree(rows)}")

    print("\n=== C. Day of the week: 00-20 UTC return (pips), halves | all mean, t, agree ===")
    for p in fx.PAIRS:
        P, b = allh[p]
        x = b[b.hr < 20].copy()
        x["day"] = x.index.normalize()
        dd = x.groupby("day").agg(r=("r", "sum"), wd=("wd", "first"), half=("half", "first"))
        print(f"--- {p}")
        for wd in range(5):
            y = dd[dd.wd == wd]
            v = [y[y.half == hn].r.mean() for hn in H]
            t = y.r.mean() / y.r.std() * np.sqrt(len(y))
            print(f"  wd{wd}  {fmt(v, 6, 1)} | {y.r.mean():+5.1f} t={t:+5.2f} {agree(v)}")

    print("\n=== D. Session behaviour (continuation = mean of sign(first) x next, pips; corr x100), halves ===")

    def cont(name, p, tz, a0, a1, b1):
        P, _ = allh[p]
        f = window_ret(P, tz, "", "", a0, a1)
        n = window_ret(P, tz, "", "", a1, b1)
        j = f.join(n, rsuffix="_n", how="inner")
        out_c, out_r = [], []
        for hn in H:
            y = j[j.half == hn]
            out_c.append((np.sign(y.ret) * y.ret_n).mean())
            out_r.append(100 * np.corrcoef(y.ret, y.ret_n)[0, 1] if len(y) > 5 else np.nan)
        big = j[j.ret.abs() > j.ret.abs().groupby(j.half).transform("median")]
        out_b = [(np.sign(y.ret) * y.ret_n).mean() for hn in H for y in [big[big.half == hn]]]
        print(f"  {name:34s} {p}: cont {fmt(out_c, 5, 1)} {agree(out_c)} | big-half {fmt(out_b, 5, 1)} "
              f"{agree(out_b)} | corr {fmt(out_r, 5, 0)}")

    for p in fx.PAIRS:
        cont("Tokyo 09-10 JST -> 10-13 JST", p, "Asia/Tokyo", 9, 10, 13)
        cont("Asia 00-07 UTC -> London 07-12 UTC", p, "UTC", 0, 7, 12)
        cont("London 1st h 08-09 Lon -> 09-12", p, fx.LON, 8, 9, 12)
        cont("London 08-10 Lon -> 10-16", p, fx.LON, 8, 10, 16)
        cont("NY 08-09:30 ET -> 09:30-12 ET", p, fx.NYC, 8, 9.5, 12)
        cont("day 00-12 UTC -> 12-16 UTC", p, "UTC", 0, 12, 16)
        cont("day 00-14 UTC -> 14-20 UTC", p, "UTC", 0, 14, 20)
        cont("into fix 15-16 Lon -> 16-17 Lon", p, fx.LON, 15, 16, 17)
        cont("into fix 14-16 Lon -> 16-19 Lon", p, fx.LON, 14, 16, 19)
        print()

    print("=== D2. Gotobi (USDJPY, Tokyo fix 09:55 JST): 09:00-09:55 and 09:55-12:00 JST, mean pips by half ===")
    P, _ = allh["USDJPY"]
    a = window_ret(P, "Asia/Tokyo", "", "", 8, 9 + 55 / 60)
    bb = window_ret(P, "Asia/Tokyo", "", "", 9 + 55 / 60, 12)
    for name, w in (("into fix 08:00-09:55", a), ("after fix 09:55-12:00", bb)):
        dom = pd.DatetimeIndex(w.index).day
        got = np.isin(dom % 5, [0]) | (dom == pd.DatetimeIndex(w.index).days_in_month)
        for lab, m in (("gotobi", got), ("other", ~got)):
            y = w[m]
            v = [y[y.half == hn].ret.mean() for hn in H]
            print(f"  {name:24s} {lab:7s} n={len(y):4d} {fmt(v, 5, 1)} all {y.ret.mean():+5.1f} {agree(v)}")

    print("\n=== D3. Month-end London fix (last 2 business days vs other), 15:00-16:00 Lon and 16:00-17:00, USD-up pips ===")
    for p in fx.PAIRS:
        P, _ = allh[p]
        a = window_ret(P, fx.LON, "", "", 15, 16)
        bb = window_ret(P, fx.LON, "", "", 16, 17)
        idx = pd.DatetimeIndex(a.index)
        bm = idx + pd.offsets.BMonthEnd(0)
        me = (bm - idx).days <= 1
        for name, w in (("15-16", a), ("16-17", bb)):
            wi = pd.DatetimeIndex(w.index)
            mme = ((wi + pd.offsets.BMonthEnd(0)) - wi).days <= 1
            y = w[mme]
            v = [UD[p] * y[y.half == hn].ret.mean() for hn in H]
            print(f"  {p} {name} month-end n={len(y):3d} {fmt(v, 6, 1)} {agree(v)}")
        del me


if __name__ == "__main__":
    main()
