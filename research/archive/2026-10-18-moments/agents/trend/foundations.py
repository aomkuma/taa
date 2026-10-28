"""Step 1 (design data only, before 2026-03-01): where does gold continue at 60-240 minute horizons?

(a) Variance ratios and the autocorrelation of consecutive k-minute returns (k = 15, 30, 60, 120, 240), returns
    scaled by the trailing volatility, by half-year.
(b) Per session open: the first 15/30/60 minutes' return vs the next 60/120/180 minutes' return (sign agreement,
    correlation, mean signed continuation in USD), and the same split by the first hour's range relative to its
    20-day average (trend-day candidates).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/foundations.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402

lab.gold.below_normal_priority()


def vr_table(B: lab.Bars) -> None:
    s = pd.Series(B.c, index=B.ot)
    s = s[s.index < lab.DESIGN_END]
    g15 = s.resample("15min").last().dropna()
    r = np.log(g15).diff()
    gap = g15.index.to_series().diff() != pd.Timedelta(minutes=15)
    r[gap] = np.nan
    # scale by trailing volatility (RMS over the previous 5 days of 15-min returns, ~ 480 bars)
    vol = r.pow(2).rolling(480, min_periods=200).mean().shift(1).pow(0.5)
    z = (r / vol).clip(-8, 8)
    print("(a) variance ratio VR(k) and lag-1 correlation of consecutive k-minute returns (vol-scaled 15-min base)")
    print(f"{'half':18}" + "".join(f"  VR{k:>4} rho{k:>4}" for k in (30, 60, 120, 240)))
    for name, a, b in lab.HALVES:
        zz = z[(z.index >= a) & (z.index < b)]
        line = f"{name:18}"
        for k in (30, 60, 120, 240):
            q = k // 15
            # non-overlapping blocks aligned to the clock; require all q pieces valid
            blk = zz.groupby(zz.index.floor(f"{k}min"))
            cnt = blk.count()
            R = blk.sum()[cnt == q]
            vr = (R.pow(2).mean()) / (q * zz.pow(2).mean())
            Rn = R.shift(-1)
            adj = (R.index.to_series().shift(-1) - R.index.to_series()) == pd.Timedelta(minutes=k)
            rho = np.corrcoef(R[adj].to_numpy(), Rn[adj].to_numpy())[0, 1]
            line += f"  {vr:6.3f} {rho:+7.3f}"
        print(line)


def session_table(B: lab.Bars) -> None:
    opens = lab.session_opens(B.ot, "2021-09-01", "2026-03-01")
    rows = []
    for sess, ts in opens.items():
        for t in ts:
            e = B.idx_at(t)
            if e >= len(B.o) - 300 or B.ot[e] != t:
                continue
            p0 = B.o[e]
            for f in (15, 30, 60):
                if B.ot[e + f] != t + pd.Timedelta(minutes=f):
                    continue
                pf = B.c[e + f - 1]
                hi, lo = B.h[e : e + f].max(), B.lo[e : e + f].min()
                for n in (60, 120, 180):
                    j = e + f + n - 1
                    if j >= len(B.o) or B.ot[j] - t > pd.Timedelta(minutes=f + n + 30):
                        continue
                    rows.append(dict(sess=sess, t=t, f=f, n=n, first=pf - p0, rng=hi - lo, nxt=B.c[j] - pf))
    d = pd.DataFrame(rows)
    d["half"] = d.t.map(lab.half_of)
    # first-hour range relative to its 20-session average, per session
    fr = d[(d.f == 60) & (d.n == 60)][["sess", "t", "rng"]].sort_values("t")
    fr["rel"] = fr.groupby("sess").rng.transform(lambda x: x / x.rolling(20, min_periods=10).mean().shift(1))
    d = d.merge(fr[["sess", "t", "rel"]], on=["sess", "t"], how="left")
    d["cont"] = np.sign(d["first"]) * d["nxt"]
    print("\n(b) first f minutes -> next n minutes: agreement %, mean signed continuation USD, corr; all design halves")
    tab = d.groupby(["sess", "f", "n"]).apply(
        lambda x: pd.Series(dict(N=len(x), agree=100 * (np.sign(x["first"]) == np.sign(x.nxt)).mean(),
                                 cont=x.cont.mean(), corr=np.corrcoef(x["first"], x.nxt)[0, 1])), include_groups=False)
    print(tab.round(3).to_string())
    print("\n(b2) f=60, n=120: mean signed continuation USD by half-year (sign stability)")
    x = d[(d.f == 60) & (d.n == 120)]
    print(x.pivot_table(index="sess", columns="half", values="cont", aggfunc="mean").round(2).to_string())
    print("\n(b3) f=60, n=120, split by the first hour's range relative to its 20-day mean: agree % / cont USD / N")
    x = x.dropna(subset=["rel"]).copy()
    x["relq"] = pd.cut(x.rel, [0, 0.8, 1.0, 1.25, 1.6, 99])
    print(x.groupby(["sess", "relq"], observed=True).apply(
        lambda y: pd.Series(dict(N=len(y), agree=100 * (np.sign(y["first"]) == np.sign(y.nxt)).mean(), cont=y.cont.mean())),
        include_groups=False).round(2).to_string())
    # first-hour return relative to its range: a strong close at one end
    x["pos"] = x["first"] / x.rng
    x["posq"] = pd.cut(x.pos.abs(), [0, 0.3, 0.5, 0.7, 1.01])
    print("\n(b4) f=60, n=120, by |first-hour net move| / first-hour range (close at the end of the range = trendy)")
    print(x.groupby(["sess", "posq"], observed=True).apply(
        lambda y: pd.Series(dict(N=len(y), agree=100 * (np.sign(y["first"]) == np.sign(y.nxt)).mean(), cont=y.cont.mean())),
        include_groups=False).round(2).to_string())


def h1_table(B: lab.Bars) -> None:
    s = pd.Series(B.c, index=B.ot)
    s = s[s.index < lab.DESIGN_END]
    h = s.resample("60min").last().dropna()
    r = h.diff()
    r[h.index.to_series().diff() != pd.Timedelta(hours=1)] = np.nan
    vol = r.abs().rolling(120, min_periods=50).mean().shift(1)
    z = (r / vol).clip(-8, 8)
    print("\n(c) H1 returns (vol-scaled): lag-1/2/3 autocorrelation and the next-hour mean after |z| > 1.5, by half")
    for name, a, b in lab.HALVES:
        zz = z[(z.index >= a) & (z.index < b)]
        ac = [zz.autocorr(k) for k in (1, 2, 3)]
        nxt = zz.shift(-1)
        big = zz.abs() > 1.5
        cont = (np.sign(zz[big]) * nxt[big]).mean()
        print(f"  {name:18} ac1 {ac[0]:+.3f} ac2 {ac[1]:+.3f} ac3 {ac[2]:+.3f}  after big hour: {cont:+.3f} sd (N {big.sum()})")
    # momentum of the last 3-4 hours -> next 2 hours
    print("\n(d) last 4 H1 bars' return (vol-scaled) sign -> next 2 hours, by half-year: corr, signed mean (sd units)")
    r4 = z.rolling(4).sum()
    n2 = z.shift(-1) + z.shift(-2)
    for name, a, b in lab.HALVES:
        sel = (z.index >= a) & (z.index < b)
        u, v = r4[sel], n2[sel]
        ok = u.notna() & v.notna()
        print(f"  {name:18} corr {np.corrcoef(u[ok], v[ok])[0, 1]:+.3f}  signed {(np.sign(u[ok]) * v[ok]).mean():+.3f}")


def main() -> None:
    B = lab.Bars()
    vr_table(B)
    session_table(B)
    h1_table(B)


if __name__ == "__main__":
    main()
