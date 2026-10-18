"""W6 signals: the retest of a broken 72-hour extreme (notes.md W6), any market, M1 decision bars in given hours."""
import numpy as np
import pandas as pd

import w4lib as w


def signals(P, start, end, hours, tp_u=8.0, be=0.6, hz=60, rmin=3.0, rmax=10.0, brk_u=0.5, look=120):
    ot, n = P.ot, len(P.ot)
    h, lo, c = P.h, P.lo, P.c
    atr = w.atr_b(h, lo, c)
    amed = pd.Series(atr).rolling(1440, min_periods=200).median().to_numpy()
    u = w.unit_of(P)
    T = ot + pd.Timedelta(minutes=1)  # the decision bar p closes at T = the entry bar's open
    hrs = T.hour + T.minute / 60
    keep = (T >= pd.Timestamp(start, tz="UTC")) & (T < pd.Timestamp(end, tz="UTC")) & (T.weekday < 5)
    hk = np.zeros(n, bool)
    for a, b in hours:
        hk |= (hrs >= a) & (hrs < b)
    keep &= hk
    p = np.flatnonzero(keep)
    p = p[(p > 4400) & (p + 200 < n)]
    p = p[ot[p + 1] == ot[p] + pd.Timedelta(minutes=1)]
    W = 4320 - look
    xs = {1: pd.Series(h).rolling(W).max().to_numpy(), -1: pd.Series(lo).rolling(W).min().to_numpy()}
    rs = {1: pd.Series(h).rolling(look).max().to_numpy(), -1: pd.Series(lo).rolling(look).min().to_numpy()}
    h1 = w.resample(P.m, 60)
    hc = h1.close
    hatr = (h1.high - h1.low).rolling(14).mean()
    e20, e50 = hc.ewm(span=20, adjust=False).mean(), hc.ewm(span=50, adjust=False).mean()
    c60 = h1.index + pd.Timedelta(minutes=60)
    Tp = T[p]
    slope = w.at_time(c60, ((e20 - e20.shift(3)) / hatr).to_numpy(), Tp)
    ce50 = w.at_time(c60, ((hc - e50) / hatr).to_numpy(), Tp)
    m15 = w.resample(P.m, 15)
    a15 = w.at_time(m15.index + pd.Timedelta(minutes=15), w.true_atr(m15).to_numpy(), Tp)
    out = []
    for s in (1, -1):
        X = xs[s][p - look - 1]
        R = rs[s][p - 1]
        broke = (R - X) * s > brk_u * u[p]
        retest = (((lo[p] if s > 0 else h[p]) - X) * s <= atr[p]) & ((c[p] - X) * s > 0)
        tide = (slope * s > 0) & (ce50 * s > 0)
        m = broke & retest & tide & (atr[p] / amed[p] < 2)
        q = p[m]
        e = q + 1
        fill = P.o[e] + (P.sp[e] + P.slip if s > 0 else -P.slip)
        stop_px = X[m] - s * atr[q]
        sl0 = (fill - stop_px) * s
        S = pd.DataFrame({"t": T[q], "e": e, "side": s, "sl0": sl0, "unit": u[q], "a15": a15[m], "X": X[m],
                          "atr": atr[q], "c_dec": c[q]})
        out.append(S)
    S = pd.concat(out, ignore_index=True)
    S = S[(S.sl0 >= rmin * S.unit) & (S.sl0 <= rmax * S.unit)].copy()
    S["sl"] = np.maximum(S.sl0, 0.5 * S.a15)
    S["session"] = w.session_of(S.t)
    S["tp"], S["be"], S["hz"], S["trail"] = tp_u * S.unit, be, hz, False
    S = S.sort_values("t")
    # one attempt per X a day and side
    S["key"] = S.t.dt.strftime("%Y-%m-%d") + S.side.astype(str) + S.X.round(3).astype(str)
    return S.drop_duplicates("key").reset_index(drop=True)
