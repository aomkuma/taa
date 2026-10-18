"""Step 3 (notes.md): the rules built from the run catalogue, simulated with the journal's real costs (jlib.Instr:
spread column + 0.08, entry slippage 0.07, stop slippage 0.15 / New York 0.20), one position at a time, against the
coin side on the same minutes; the losers' three kinds.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/rules.py RULE [--window]

Without --window only the design data (2023-11-01 .. 2026-02-28) is simulated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
A = HERE.parent
sys.path.insert(0, str(A / "journal"))
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import gold  # noqa: E402
import jlib  # noqa: E402


def _m1(sym: str) -> pd.DataFrame:
    m = gold.bars("M1")
    m = m[(m.index >= pd.Timestamp("2023-08-01", tz="UTC")) & (m.index < pd.Timestamp("2026-10-17", tz="UTC"))]
    m = m[~m.index.duplicated(keep="last")]
    return m[["open", "high", "low", "close", "tick_volume", "spread"]].astype(float)


jlib.m1_frame = _m1  # the store now reaches 2026-10-16 20:54 UTC
REF = 4100.0
DESIGN = ("2023-11-01", "2026-03-01")
WINDOW = ("2026-03-01", "2026-10-17")
HALVES = pd.to_datetime(["2023-11-01", "2024-05-01", "2024-11-01", "2025-05-01", "2025-09-01", "2026-03-01"], utc=True)

# every rule: written in notes.md before it is computed
RULES = {
    # RUN-A: the second leg - after a run's first 40 % pullback, the count-three turn, in the run's way
    "A0": dict(kind="A", R=10, tp="retest", be=0.6, hz=120, void=60),
    "A1": dict(kind="A", R=10, tp=8, be=0.6, hz=120, void=60),
    "A2": dict(kind="A", R=15, tp="retest", be=0.6, hz=120, void=60),
    "A3": dict(kind="A", R=15, tp=8, be=0.6, hz=120, void=60),
    "A4": dict(kind="A", R=15, tp=8, be=0.6, hz=120, void=60, tide=True, nochase=1.75, min_stop_atr=0.6),
    "A6": dict(kind="A", R=15, tp=8, be=0.6, hz=120, void=60, tide=True, nochase=1.75, min_stop_atr=0.6, max_age=120),
    "A7": dict(kind="A", R=15, tp=8, be=0.6, hz=120, void=60, tide=True, nochase=1.75, min_stop_ad=0.5, max_age=120,
               usd_bounds=True),
    "A8": dict(kind="A", R=15, tp=8, be=0.6, hz=120, void=60, tide=True, nochase=1.75, min_stop_ad=0.5, max_age=120,
               usd_bounds=True, no_max=True),
    "A5": dict(kind="A", R=2.5, tp=8, be=0.6, hz=120, void=60, tide=True, nochase=1.75, min_stop_atr=0.6),
    # RUN-B: a fresh day extreme whose count-three bounce fails to reclaim the old extreme -> with the break
    "B0": dict(kind="B", tp=8, be=0.6, hz=120, stop="bounce", h0=6),
    "B1": dict(kind="B", tp=5, be=0.6, hz=120, stop="bounce", h0=6),
    "B2": dict(kind="B", tp=8, be=0.6, hz=120, stop="level", h0=6),
}


def sess(t: pd.Timestamp) -> int:
    return 0 if t.hour < 7 else (1 if t.hour < 12 else 2)


def signals_A(P: jlib.Instr, cfg: dict) -> pd.DataFrame:
    C = pd.read_parquet(HERE / "catalogue.parquet")
    C = C[C.R == cfg["R"]].sort_values("t")
    o, h, lo, c = P.o, P.h, P.lo, P.c
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - pc), np.abs(lo - pc)], axis=1)
    atr1 = pd.Series(tr).rolling(14).mean().to_numpy()
    # the catalogue's bar index is into catalogue.load(); map by time
    pos = P.ot
    F = pd.read_parquet(HERE / "feats.parquet", columns=["h1_tide", "m15_e20_dist", "atr15_u"])
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_tf", "ad_atr_usd"])
    rows = []
    for r in C.itertuples():
        s = int(r.side)
        k0 = pos.searchsorted(r.t_end)
        if k0 >= len(pos) - 200 or pos[k0] != r.t_end:
            continue
        start, ext = r.start_px, r.start_px + s * r.size
        pl, lb, quiet = (lo[k0], k0, 0) if s > 0 else (h[k0], k0, 0)
        k = k0 + 1
        found = None
        while k < k0 + cfg["void"]:
            x = lo[k] if s > 0 else h[k]
            if (x - pl) * s < 0:
                pl, lb, quiet = x, k, 0
                if (pl - start) * s < 0:  # the run fully retraced: void
                    break
            else:
                quiet += 1
                turn = h[lb] if s > 0 else lo[lb]
                if quiet >= 3 and (c[k] - turn) * s > 0:
                    found = k
                    break
            k += 1
        if found is None:
            continue
        e = found + 1
        if pos[found].hour >= 20 or pos[found].dayofweek >= 5:  # decisions 00:00-20:00 UTC weekdays (notes.md)
            continue
        if cfg.get("max_age") is not None and (pos[e] - r.t).total_seconds() / 60 > cfg["max_age"]:
            continue
        u = o[e] / REF
        stop = pl - s * 0.3 * u
        fx = F.loc[pos[found]]
        if cfg.get("tide") and fx.h1_tide != s:
            continue
        if cfg.get("nochase") is not None and fx.m15_e20_dist * s > cfg["nochase"]:
            continue
        ad = AD.loc[pos[found]]
        min_stop = cfg.get("min_stop_atr", 0.0) * fx.atr15_u * c[found] / REF
        min_stop = max(min_stop, cfg.get("min_stop_ad", 0.0) * float(ad.ad_atr_usd))
        rows.append(dict(t=pos[e], e=e, side=s, stop=stop, ext=ext, u=u, run_t=r.t, start=start, min_stop=min_stop,
                         lvl=ext, why=f"run {r.t:%H:%M} {r.size:.1f}", ad_atr=float(ad.ad_atr_usd), ad_tf=float(ad.ad_tf)))
    return pd.DataFrame(rows)


def signals_B(P: jlib.Instr, cfg: dict) -> pd.DataFrame:
    o, h, lo, c = P.o, P.h, P.lo, P.c
    n = len(o)
    ot = P.ot
    day = ot.normalize()
    dlo = pd.Series(lo).groupby(day.to_numpy()).cummin().to_numpy()
    dhi = pd.Series(h).groupby(day.to_numpy()).cummax().to_numpy()
    pmin = pd.Series(lo).rolling(10).min().shift(1).to_numpy()
    pmax = pd.Series(h).rolling(10).max().shift(1).to_numpy()
    nmin = np.r_[pd.Series(lo).rolling(3).min().to_numpy()[3:], np.full(3, np.nan)]
    nmax = np.r_[pd.Series(h).rolling(3).max().to_numpy()[3:], np.full(3, np.nan)]
    m15 = P.m.resample("15min", label="left", closed="left").agg({"high": "max", "low": "min"}).dropna()
    a15 = (m15.high - m15.low).rolling(14).mean()
    a15.index = a15.index + pd.Timedelta(minutes=15)
    atr15 = a15.reindex(ot + pd.Timedelta(minutes=1), method="ffill").to_numpy()
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_tf", "ad_atr_usd"])
    rows = []
    for sw in (1, -1):  # sw: the swing (a low = +1); the trade goes against the swing: with the break
        if sw > 0:
            ok = (lo < pmin) & (nmin > lo)
        else:
            ok = (h > pmax) & (nmax < h)
        for j in np.nonzero(ok)[0]:
            if j < 2000 or j + 200 >= n or day[j - 1] != day[j] or ot[j].hour < cfg["h0"] or ot[j].hour >= 20:
                continue
            d = j + 3
            if day[d] != day[j]:
                continue
            old = dlo[j - 1] if sw > 0 else dhi[j - 1]
            ext = lo[j] if sw > 0 else h[j]
            if (ext - old) * sw >= 0:  # not a new day extreme
                continue
            if (c[d] - old) * sw > 0:  # the bounce closed back beyond the old extreme: reclaimed, no trade
                continue
            s = -sw
            e = d + 1
            u = o[e] / REF
            if cfg["stop"] == "bounce":
                bounce = h[j : d + 1].max() if s < 0 else lo[j : d + 1].min()
                stop = bounce - s * 0.3 * u
            else:
                stop = old - s * 0.5 * atr15[d]
            ad = AD.reindex([ot[d]]).iloc[0]
            rows.append(dict(t=ot[e], e=e, side=s, stop=stop, u=u, lvl=old, why=f"new day {'low' if sw > 0 else 'high'}",
                             ad_atr=float(ad.ad_atr_usd), ad_tf=float(ad.ad_tf)))
    return pd.DataFrame(rows).sort_values("t") if rows else pd.DataFrame()


def simulate(S: pd.DataFrame, P: jlib.Instr, cfg: dict, coin: np.random.Generator | None = None) -> pd.DataFrame:
    out, free = [], pd.Timestamp(0, tz="UTC")
    for r in S.itertuples():
        if r.t < free:
            continue
        s = int(r.side)
        fill = float(P.fill(np.array([r.e]), np.array([s]))[0])
        sl = (fill - r.stop) * s
        if hasattr(r, "min_stop") and np.isfinite(r.min_stop):
            sl = max(sl, float(r.min_stop))
        lo_b, hi_b = (3.0, 10.0) if cfg.get("usd_bounds") else (3 * r.u, 10 * r.u)
        if cfg.get("no_max"):
            hi_b = np.inf
        if not (lo_b <= sl <= hi_b):
            continue
        if cfg["tp"] == "retest":
            tp = (r.ext - fill) * s
            if tp < 5 * r.u:
                tp = 5 * r.u
        else:
            tp = cfg["tp"] * r.u
        side = s if coin is None else int(coin.choice([-1, 1]))
        ses = sess(r.t)
        ss = P.stop_slip_ny if ses == 2 else P.stop_slip
        x = P.trade(int(r.e), side, tp, sl, cfg["be"], cfg["hz"], ss)
        x |= dict(t=r.t, e=int(r.e), side=side, sl=sl, tp=tp, R=x["pnl"] / (sl + ss), session=ses, u=r.u, why=r.why,
                  start=getattr(r, "start", np.nan), run_t=getattr(r, "run_t", pd.NaT),
                  lvl=r.lvl, ad_atr=r.ad_atr, ad_tf=r.ad_tf, stop_ad=sl / r.ad_atr)
        out.append(x)
        free = r.t + pd.Timedelta(minutes=int(x["mins"]))
    return pd.DataFrame(out)


def report(name: str, z: pd.DataFrame, a: str, b: str, by: str) -> str:
    if not len(z):
        return f"  {name}: 0 trades"
    days = pd.bdate_range(a, b, inclusive="left").size
    eq = z.pnl.cumsum()
    streak = mx = 0
    for v in z.pnl:
        streak = streak + 1 if v < 0 else 0
        mx = max(mx, streak)
    key = z.t.dt.strftime("%Y-%m") if by == "month" else pd.cut(z.t, HALVES, right=False)
    g = z.groupby(key, observed=True)
    per = " ".join(f"{(str(k)[2:7] if by == 'month' else str(k.left)[2:7])} {v.R.mean():+.2f}({len(v)},{v.pnl.sum():+.0f})"
                   for k, v in g)
    los = z[z.exit == "stop"]
    kd = los.kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    avg_loss = -los.pnl.mean() if len(los) else 0
    return (f"  {name}: {len(z)} trades ({len(z) / days:.2f}/day), win {100 * (z.exit == 'win').mean():.0f}%, R {z.R.mean():+.3f},"
            f" {z.pnl.sum():+.1f} USD at 0.01 lot; worst {z.pnl.min():.2f}, streak {mx},"
            f" max DD {(eq.cummax() - eq).max():.1f}, 6 avg losses {6 * avg_loss:.1f}; stop {z.sl.median():.2f} tp {z.tp.median():.2f}"
            f" (stop {z.stop_ad.median():.2f} x the trading-TF ATR, TF M{z.ad_tf.mode().iloc[0]:.0f} most);"
            f" losers 1/2/3 {100 * kd['1']:.0f}/{100 * kd['2']:.0f}/{100 * kd['3']:.0f}%\n     {per}")


def main() -> None:
    gold.below_normal_priority()
    name = sys.argv[1]
    cfg = RULES[name]
    P = jlib.Instr("XAUUSD")
    S = signals_A(P, cfg) if cfg["kind"] == "A" else signals_B(P, cfg)
    parts = [("DESIGN", *DESIGN, "half")]
    if "--window" in sys.argv:
        parts.append(("WINDOW", *WINDOW, "month"))
    for part, a, b, by in parts:
        x = S[(S.t >= pd.Timestamp(a, tz="UTC")) & (S.t < pd.Timestamp(b, tz="UTC"))]
        z = simulate(x, P, cfg)
        print(f"== {name} {part} {a} .. {b}: signals {len(x)}")
        print(report("rule", z, a, b, by))
        rs = [simulate(x, P, cfg, np.random.default_rng(100 + k)) for k in range(10)]
        cr = np.mean([r.R.mean() for r in rs])
        ck = pd.concat(rs)
        ck = ck[ck.exit == "stop"].kind.value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
        print(f"  coin (10 seeds, same minutes): R {cr:+.3f} (sd {np.std([r.R.mean() for r in rs]):.3f}),"
              f" USD {np.mean([r.pnl.sum() for r in rs]):+.1f}, losers 1/2/3 {100 * ck['1']:.0f}/{100 * ck['2']:.0f}/{100 * ck['3']:.0f}%")
        z.to_parquet(HERE / f"trades_{name}_{part.lower()}.parquet")


if __name__ == "__main__":
    main()
