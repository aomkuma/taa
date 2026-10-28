"""Shared evaluation for weapon4 (design): net / gross / coin by half-year, D2, the count, what a rule adds beyond
F1's own trades (minutes not inside an F1 trade)."""
import numpy as np
import pandas as pd

import w4lib as w

HN = [x[0] for x in w.HALVES]


def halves(z):
    h = w.plib.half_of(z.t)
    return z.R.groupby(h).mean().reindex(HN).to_numpy(), z.R.groupby(h).size().reindex(HN).fillna(0).astype(int).to_numpy()


def runner_of(v2):
    return (lambda S, P, **kw: w.run_v2(S, P, **kw)) if v2 else (lambda S, P, **kw: w.run(S, P, **kw))


def gross(S, P, v2):
    keep = P.sp.copy(), P.slip, P.stop_slip, P.stop_slip_ny
    P.gross()
    z = runner_of(v2)(S, P)
    P.sp, P.slip, P.stop_slip, P.stop_slip_ny = keep
    return z


def coin(S, P, v2, seeds=10):
    acc, wins = [], []
    for s in range(seeds):
        rng = np.random.default_rng(100 + s)
        if v2:
            z = w.run_v2(S, P, coin=rng)
        else:
            z = w.plib.run(S, P, coin=rng)
            z["t"] = pd.to_datetime(z.t, utc=True)
        acc.append(halves(z)[0])
        wins.append(((z.exit == "win") | (z.exit == "trail")).mean() if v2 else (z.exit == "win").mean())
    return np.nanmean(np.array(acc), 0), float(np.mean(wins))


def busy_mask(z, ref):
    """True for trades of z whose entry falls inside a trade of ref."""
    if ref is None or not len(ref):
        return np.zeros(len(z), bool)
    a = ref.t.to_numpy()
    b = (ref.t + pd.to_timedelta(ref.mins, unit="min")).to_numpy()
    tt = z.t.to_numpy()
    k = np.searchsorted(a, tt, side="right") - 1
    return (k >= 0) & (tt < b[np.clip(k, 0, None)])


def report(label, S, P, v2=False, f1=None, days=None):
    days = days or w.days_in(*w.DESIGN)
    z = runner_of(v2)(S, P)
    zg = gross(S, P, v2)
    rn, n = halves(z)
    rg, _ = halves(zg)
    rc, cw = coin(S, P, v2)
    d2 = (np.sum(rg >= 0.10) >= 4) and (rn[-1] >= 0.10)
    win = ((z.exit == "win") | (z.exit == "trail")).mean() if v2 else (z.exit == "win").mean()
    print(f"  {label:30} {len(z):4} ({len(z) / days:.2f}/d) win {100 * win:3.0f}% (coin {100 * cw:.0f}) net {z.R.mean():+.3f}"
          f" gross {zg.R.mean():+.3f} USD {z.usd.sum():+7.1f} | D2 {'PASS' if d2 else 'fail'}")
    print("      net   " + " ".join(f"{v:+.2f}({k})" for v, k in zip(rn, n)))
    print("      gross " + " ".join(f"{v:+.2f}" for v in rg) + "   coin " + " ".join(f"{v:+.2f}" for v in rc))
    if f1 is not None:
        same_t = z.t.isin(set(f1.t)).to_numpy()
        new = z[~same_t & ~busy_mask(z, f1)]
        nd = new[~new.t.dt.date.isin(set(f1.t.dt.date))]
        rn2, n2 = halves(new) if len(new) else (np.full(5, np.nan), np.zeros(5, int))
        print(f"      beyond F1 (not F1's minutes, not inside an F1 trade): {len(new)} ({len(new) / days:.2f}/d) net"
              f" {new.R.mean():+.3f} [{' '.join(f'{v:+.2f}({k})' for v, k in zip(rn2, n2))}]; on days without F1"
              f" {len(nd)} ({len(nd) / days:.2f}/d) {nd.R.mean():+.3f}")
    return z
