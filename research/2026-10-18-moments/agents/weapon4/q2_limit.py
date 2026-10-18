"""Q2: a limit order at the round 50 near a fresh extreme (notes.md Q2 + its clarification). Design with placebo
grids; `window` runs the frozen rule once (offset 0 only).

    PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/weapon4/q2_limit.py [window]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evalw as ev  # noqa: E402
import w4lib as w  # noqa: E402

HERE = Path(__file__).resolve().parent


def arm_table(P, start, end, step, offset, hours=((0, 20),)):
    ot, n = P.ot, len(P.ot)
    T = ot + pd.Timedelta(minutes=1)
    hrs = T.hour + T.minute / 60
    keep = (T >= pd.Timestamp(start, tz="UTC")) & (T < pd.Timestamp(end, tz="UTC")) & (T.weekday < 5)
    hk = np.zeros(n, bool)
    for a, b in hours:
        hk |= (hrs >= a) & (hrs < b)
    p = np.flatnonzero(keep & hk)
    p = p[(p > 7300) & (p + 200 < n)]
    atr = w.atr_b(P.h, P.lo, P.c)
    amed = pd.Series(atr).rolling(1440, min_periods=200).median().to_numpy()
    u = w.unit_of(P)
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
    lo5 = pd.Series(P.lo).rolling(5).min().to_numpy()
    hi5 = pd.Series(P.h).rolling(5).max().to_numpy()
    x = P.c[p]
    rows = []
    for s in (1, -1):
        R = (np.floor((x - offset) / step) * step + offset) if s > 0 else (np.ceil((x - offset) / step) * step + offset)
        dist = (x - R) * s
        untouched = ((lo5[p] - R) > 0) if s > 0 else ((R - hi5[p]) > 0)
        m = (slope * s > 0) & (ce50 * s > 0) & (dist > 0) & (dist <= 3 * atr[p]) & untouched & (atr[p] / amed[p] < 2)
        rows.append(pd.DataFrame({"t": Tp[m], "e": p[m] + 1, "side": s, "R": R[m], "atr": atr[p][m], "unit": u[p][m],
                                  "a15": a15[m], "c_dec": x[m]}))
    return w.add_anchors(pd.concat(rows, ignore_index=True), P)


def simulate(P, A, hz_order=60, tp_u=8.0, be=0.6, hz=60):
    """Orders from arming rows A, one per (day, side, R); one position at a time."""
    A = A.sort_values("t")
    A = A.assign(key=A.t.dt.strftime("%Y-%m-%d") + A.side.astype(str) + A.R.round(3).astype(str)).drop_duplicates("key")
    o, h, lo, c, sp = P.o, P.h, P.lo, P.c, P.sp
    rows, free_j = [], -1
    for r in A.itertuples():
        e0, s, R, u = int(r.e), int(r.side), float(r.R), float(r.unit)
        if e0 <= free_j:
            continue
        L = R + sp[e0 - 1] if s > 0 else R
        fill_j = entry = None
        for j in range(e0, min(e0 + hz_order, len(o) - 1)):
            if s > 0:
                if o[j] + sp[j] <= L:
                    fill_j, entry = j, o[j] + sp[j]
                elif lo[j] + sp[j] <= L:
                    fill_j, entry = j, L
            else:
                if o[j] >= L:
                    fill_j, entry = j, o[j]
                elif h[j] >= L:
                    fill_j, entry = j, L
            if fill_j is not None:
                break
            if (h[j] - R >= tp_u * u) if s > 0 else (R - lo[j] - sp[j] >= tp_u * u):
                break  # ran away first: cancelled
        if fill_j is None:
            continue
        stop = R - s * r.atr
        sl = max((entry - stop) * s, 0.5 * r.a15, 3 * u)
        if sl > 10 * u:
            continue
        ss = P.stop_slip_ny if P.ot[fill_j].hour >= 12 else P.stop_slip
        stop = entry - s * sl
        tp = tp_u * u
        res, armed, mfe = None, False, 0.0
        end = min(fill_j + hz, len(o) - 1)
        for j in range(fill_j, end):
            adv = lo[j] if s > 0 else h[j] + sp[j]
            if (adv - stop) * s <= 0:
                res = ("be" if armed else "stop", (stop - s * ss - entry) * s, j)
                break
            if j == fill_j:
                continue
            fav = h[j] if s > 0 else lo[j] + sp[j]
            if (fav - entry) * s >= tp:
                res = ("win", tp, j)
                break
            mfe = max(mfe, (fav - entry) * s)
            if not armed and mfe >= be * tp:
                armed, stop = True, entry
        if res is None:
            xj = end - 1
            px = c[xj] - (P.slip if s > 0 else -(sp[xj] + P.slip))
            res = ("time", (px - entry) * s, xj)
        kind = ""
        if res[0] == "stop":
            hit = any(((h[k] if s > 0 else lo[k] + sp[k]) - entry) * s >= tp
                      for k in range(res[2] + 1, min(fill_j + 120, len(o))))
            kind = "3" if hit else ("2" if mfe >= 0.5 * tp else "1")
        rows.append(dict(t=P.ot[fill_j], t_arm=r.t, side=s, exit=res[0], pnl=res[1], R=res[1] / (sl + ss), kind=kind,
                         mins=res[2] - fill_j + 1, usd=res[1] * w.USD_PER_PX.get(P.sym, 1.0), sl_u=sl / u, unit=u))
        free_j = res[2]
    z = pd.DataFrame(rows)
    if len(z):
        z["t"] = pd.to_datetime(z.t, utc=True)
    return z


def anchor_mask(A, which):
    m = np.zeros(len(A), bool)
    for a in which:
        m |= (A[f"d_{a}"] < 4).to_numpy()
    return m


VARIANTS = (("L1 A72", ["A72"]), ("L2 A24", ["A24"]), ("L3 W11-anchors", ["A72", "A24", "AW", "AS"]))


def main():
    w.jlib.gold.below_normal_priority()
    P = w.instr("XAUUSD")
    window = len(sys.argv) > 1 and sys.argv[1] == "window"
    per = w.WINDOW if window else w.DESIGN
    days = w.days_in(*per)
    offs = [0.0] if window else [0.0, 10.0, 20.0, 25.0, 30.0, 40.0]
    tabs = {o: arm_table(P, *per, 50.0, o) for o in offs}
    for name, which in VARIANTS:
        print(f"\n== {name} ({'WINDOW' if window else 'design'})")
        for o in offs:
            A = tabs[o]
            z = simulate(P, A[anchor_mask(A, which)])
            if not len(z):
                continue
            rn, n = ev.halves(z) if not window else (None, None)
            print(f"  offset {o:4g}: {len(z):4} ({len(z) / days:.2f}/d) win {100 * (z.exit == 'win').mean():3.0f}% R {z.R.mean():+.3f}"
                  f" USD {z.usd.sum():+7.1f} kinds {w.plib.kinds(z)} longs {100 * (z.side > 0).mean():.0f}%"
                  + ("" if window else f" | [{' '.join(f'{v:+.2f}({k})' for v, k in zip(rn, n))}]"))
            if o == 0:
                print("      " + w.account(z))
                z.to_csv(HERE / f"{'window' if window else 'design'}_{name.split()[0]}_trades.csv", index=False)
                if window:
                    for k, v in z.groupby(z.t.dt.strftime("%Y-%m")):
                        print(f"      {k}: {len(v):3} R {v.R.mean():+.3f} USD {v.usd.sum():+7.1f}")


if __name__ == "__main__":
    main()
