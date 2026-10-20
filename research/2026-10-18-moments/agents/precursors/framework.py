"""The owner's framework, measured (notes.md, written before it is computed; owner, 2026-10-20: "D1 tells which side has
the edge; the trend from M15-1H; enter with M1-M5; in a real trend day it runs one way and pullbacks are not far; an
open runs in its first 30-60 minutes, NY up to 4 hours, sometimes choppy for 1-2 hours first").

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/framework.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402

EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")


def d1_bias(close: np.ndarray, n: int = 20, slope: int = 5) -> np.ndarray:
    """Per D1 bar k: +1 when close[k] > EMA(n)[k] and EMA rose over `slope` bars, -1 mirrored, else 0 (known at k's close)."""
    e = np.array(F.ema(np.asarray(close, float), n), float)
    e[: n - 1] = np.nan
    rise = e - pd.Series(e).shift(slope).to_numpy()
    return np.where((close > e) & (rise > 0), 1, np.where((close < e) & (rise < 0), -1, 0))


def pullback(h: np.ndarray, lo: np.ndarray, side: int) -> float:
    """The deepest move against `side` from the running extreme its way, on bar extremes (USD; >= 0)."""
    if side > 0:
        return float(np.max(np.maximum.accumulate(h) - lo))
    return float(np.max(h - np.minimum.accumulate(lo)))


def efficiency(c: np.ndarray, o0: float) -> float:
    """|net| / path for a run of closes starting from o0."""
    path = np.abs(np.diff(np.r_[o0, c])).sum()
    return float(abs(c[-1] - o0) / path) if path > 0 else 0.0


def main() -> None:
    import plib  # noqa: PLC0415

    from indicators import bars  # noqa: PLC0415
    from m15_trades import part_of  # noqa: PLC0415

    m = plib.load()
    m = m[(m.index >= pd.Timestamp("2025-06-01", tz="UTC")) & (m.index < EXAM_START)]
    d1 = bars(m, "1D")
    bias_d = d1_bias(d1.close.to_numpy(float))
    avail = pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8
    key = m.index.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
    rows = []
    for day, g in m.groupby(key):
        t0 = g.index[0]
        k = int(np.searchsorted(avail, t0.value, side="right")) - 1   # the last D1 complete before the day's first bar
        if k < 0 or len(g) < 600:
            continue
        b = int(bias_d[k])
        o, h, lo, c = (g[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        rows.append(dict(t=t0, bias=b, net=float(c[-1] - o[0]), up=float(h.max() - o[0]), dn=float(o[0] - lo.min()),
                         pb_up=pullback(h, lo, 1), pb_dn=pullback(h, lo, -1)))
    D = pd.DataFrame(rows)
    D["part"] = part_of(pd.DatetimeIndex(D.t))
    D = D[D.part.isin(["P1", "P2"])]
    print("== Study 1: the D1 bias (EMA20, its 5-day rise) and the day")
    for p, G in D.groupby("part"):
        B = G[G.bias != 0]
        s = B.bias.to_numpy()
        net = s * B.net.to_numpy()
        fav = np.where(s > 0, B.up, B.dn)
        adv = np.where(s > 0, B.dn, B.up)
        pb = np.where(s > 0, B.pb_up, B.pb_dn)
        run = fav >= 20
        print(f"  {p}: {len(G)} days, with a bias {len(B)} (buy {int((s > 0).sum())} / sell {int((s < 0).sum())}); "
              f"closed the bias's way {np.mean(net > 0):.2f}; net the bias's way median {np.median(net):+.1f} USD; "
              f"furthest the bias's way median {np.median(fav):.1f}, against {np.median(adv):.1f}; "
              f"the deepest pullback median {np.median(pb):.1f} (75 % {np.quantile(pb, .75):.1f}); on the days that ran 20+ "
              f"the bias's way ({int(run.sum())}): pullback median {np.median(pb[run]):.1f}, 75 % {np.quantile(pb[run], .75):.1f}")
        N = G[G.bias == 0]
        print(f"      no bias: {len(N)} days; |net| median {np.median(np.abs(N.net)):.1f}")
    # Study 2: the session timing
    bias_of = dict(zip(pd.DatetimeIndex(D.t).tz_convert("Europe/Athens").tz_localize(None).floor("1D"), D.bias))
    for name, zone, hh, mm, span_min, step in (("NY open 09:30 NY", "America/New_York", 9, 30, 240, 30),
                                                ("Asia 07:00 Thai", "Asia/Bangkok", 7, 0, 60, 15),
                                                ("London 13:00 Thai", "Asia/Bangkok", 13, 0, 60, 15)):
        recs = []
        for day in sorted({t.normalize() for t in m.index.tz_convert(zone)}):
            t0 = pd.Timestamp(year=day.year, month=day.month, day=day.day, hour=hh, minute=mm, tz=zone).tz_convert("UTC")
            if t0.dayofweek >= 5:
                continue
            s_key = t0.tz_convert("Europe/Athens").tz_localize(None).floor("1D")
            b = bias_of.get(s_key)
            if b is None or b == 0:
                continue
            a = int(np.searchsorted(m.index, t0))
            e = int(np.searchsorted(m.index, t0 + pd.Timedelta(minutes=span_min)))
            g = m.iloc[a:e]
            if len(g) < span_min * 0.8:
                continue
            o0 = float(g.open.iloc[0])
            r = dict(t=t0, bias=b)
            for q in range(0, span_min, step):
                w = g[(g.index >= t0 + pd.Timedelta(minutes=q)) & (g.index < t0 + pd.Timedelta(minutes=q + step))]
                if len(w):
                    r[f"m{q}"] = b * float(w.close.iloc[-1] - w.open.iloc[0])
                    r[f"a{q}"] = abs(float(w.close.iloc[-1] - w.open.iloc[0]))
                    r[f"g{q}"] = float(w.high.max() - w.low.min())
            if span_min == 240:
                h1, h2 = g[g.index < t0 + pd.Timedelta(hours=2)], g[g.index >= t0 + pd.Timedelta(hours=2)]
                r["eff12"] = efficiency(h1.close.to_numpy(), o0)
                r["run34"] = b * float(h2.close.iloc[-1] - h2.open.iloc[0]) if len(h2) else np.nan
            recs.append(r)
        S = pd.DataFrame(recs)
        S["part"] = part_of(pd.DatetimeIndex(S.t))
        S = S[S.part.isin(["P1", "P2"])]
        print(f"\n== Study 2: {name} (days with a D1 bias), per {step}-minute bucket: the move the bias's way (mean) | "
              f"|move| (median) | range (median)")
        for p, G in S.groupby("part"):
            cells = []
            for q in range(0, span_min, step):
                if f"m{q}" in G:
                    cells.append(f"+{q}: {G[f'm{q}'].mean():+.1f} | {G[f'a{q}'].median():.1f} | {G[f'g{q}'].median():.1f}")
            print(f"  {p} ({len(G)} days): " + "; ".join(cells))
            if span_min == 240:
                chop = G.eff12 < 0.3
                print(f"      first 2 h choppy (eff < 0.3): {chop.mean():.2f} of days; then the next 2 h ran 10+ the bias's way: "
                      f"{(G.run34[chop] >= 10).mean():.2f} (the other days: {(G.run34[~chop] >= 10).mean():.2f}); "
                      f"mean of the next 2 h the bias's way: choppy {G.run34[chop].mean():+.1f}, not choppy {G.run34[~chop].mean():+.1f}")


if __name__ == "__main__":
    main()
