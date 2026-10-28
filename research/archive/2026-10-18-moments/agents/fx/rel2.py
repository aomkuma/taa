"""Step 5: attack the largest loser group of V3 (fading a move that is still at its extreme at 10:00 ET), design
halves only. Variants (written in notes.md before the run):
  V7  = V3, skip when the 10:00 close is within 10 % of the 08-10 range from the extreme (no stall yet).
  V8  = V3 with a wait: from 10:00 to 11:00 ET, enter at the first M1 close that is >= 15 % of the running range
        (08:00 .. now) back from the running extreme; stop beyond the running extreme + 0.5 ATR (>= 1 ATR); exit 14 ET.
  V8b = V8 without USDJPY (step 1: the one trending pair; its New York path continues, out_nyfade A).
  V8c = V8b, at most 3 pairs a day: the largest |move| / ATR at 10:00.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
sys.path.insert(0, "research/2026-10-18-moments")
import fxlib as fx  # noqa: E402
import lab  # noqa: E402
import reltrades as rt  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]


def wait_entries(P: fx.Pair, ev: pd.DataFrame, side: np.ndarray, frac: float, until: pd.Series):
    """For each event: the decision bar (first close from 10:00 ET up to *until* that is >= frac of the running range
    back from the running extreme) and the stop distance; -1 if none."""
    dec = np.full(len(ev), -1)
    sl = np.full(len(ev), np.nan)
    hz = np.zeros(len(ev), int)
    uix = until.reindex(ev.day).to_numpy()
    for k, r in enumerate(ev.itertuples()):
        if side[k] == 0 or not np.isfinite(uix[k]):
            continue
        a, d, u = int(r.a), int(r.d), int(uix[k])
        up = side[k] < 0  # we fade an up move
        hi_run = np.maximum.accumulate(P.h[a:u + 1])
        lo_run = np.minimum.accumulate(P.lo[a:u + 1])
        c = P.c[a:u + 1]
        rng = hi_run - lo_run
        back = (hi_run - c) if up else (c - lo_run)
        ok = np.flatnonzero((back >= frac * rng) & (rng > 0))
        ok = ok[ok >= d - a]
        if not len(ok):
            continue
        j = ok[0]
        ext = hi_run[j] if up else lo_run[j]
        dist = abs(ext - c[j]) + 0.5 * r.h1_atr
        dec[k] = a + j
        sl[k] = max(dist, r.h1_atr)
        hz[k] = int(r.hz - (j - (d - a)))  # same exit clock time
    return dec, sl, hz


def run(Ps, mode: str, period: list[str], cap: int | None = None, pairs=None, prio=None) -> pd.DataFrame:
    out = []
    for p in (pairs or fx.PAIRS):
        Pn, Pg = Ps[p]
        ev = rt.build(Pn, 10, 14)
        ev = ev[ev.half.isin(period) & ev.rel].reset_index(drop=True)
        q = (ev.move.abs() / ev.h1_atr).to_numpy()
        side = -np.sign(ev.move.to_numpy()).astype(int)
        side[q < 1] = 0
        atr = ev.h1_atr.to_numpy()
        if mode == "V7":
            ext = np.where(side < 0, ev.whi.to_numpy(), ev.wlo.to_numpy())
            rng_ = (ev.whi - ev.wlo).to_numpy()
            back = np.abs(ext - ev.px.to_numpy()) / rng_
            side[back <= 0.10] = 0
            sl = np.maximum(np.abs(ext - ev.px.to_numpy()) + 0.5 * atr, atr)
            e2 = ev
        else:
            until = lab.local_index(Pn, fx.NYC, 11)
            dec, sl, hz = wait_entries(Pn, ev, side, 0.15, until)
            side[dec < 0] = 0
            e2 = ev.copy()
            e2["d"] = np.where(dec >= 0, dec, ev.d)
            e2["hz"] = np.where(dec >= 0, hz, ev.hz)
            e2["t"] = Pn.ot[e2.d.to_numpy()]
        zn = lab.simulate(Pn, e2, side, sl, None)
        zg = lab.simulate(Pg, e2, side, sl, None)
        rng = np.random.default_rng(11)
        coin = np.where(side != 0, rng.choice([-1, 1], len(side)), 0)
        zc = lab.simulate(Pn, e2, coin, sl, None)
        if not len(zn):
            continue
        zn["Rg"] = zg.R.to_numpy()
        zn["coinR"] = zc.set_index("ev").R.reindex(zn.ev).to_numpy()
        zn["coin_kind"] = zc.set_index("ev").kind.reindex(zn.ev).to_numpy()
        zn["coin_exit"] = zc.set_index("ev").exit.reindex(zn.ev).to_numpy()
        zn["pair"] = p
        zn["q"] = q[zn.ev]
        zn["day"] = ev.day.to_numpy()[zn.ev]
        out.append(zn)
    z = pd.concat(out, ignore_index=True)
    if cap:
        if prio:  # a fixed order of the pairs (cheapest spread first), not the move's size
            z["prio"] = z.pair.map({p: i for i, p in enumerate(prio)})
            z = z.sort_values(["day", "prio"]).groupby("day").head(cap).sort_values("t")
        else:
            z = z.sort_values(["day", "q"], ascending=[True, False]).groupby("day").head(cap).sort_values("t")
    return z.reset_index(drop=True)


def risk(z: pd.DataFrame) -> str:
    z = z.sort_values("t")
    eq = z.usd.cumsum()
    dd = (eq.cummax().clip(lower=0) - eq).max()
    streak = mx = 0
    for v in (z.R < 0):
        streak = streak + 1 if v else 0
        mx = max(mx, streak)
    avg_loss = -z[z.usd < 0].usd.mean()
    return (f"worst {z.usd.min():+.2f} USD, worst day {z.groupby('day').usd.sum().min():+.2f}, streak {mx}, "
            f"maxDD {dd:.1f} USD, 6 avg losses {6 * avg_loss:.1f} USD")


def main() -> None:
    Ps = {p: (fx.Pair(p), fx.Pair(p, costs=False)) for p in fx.PAIRS}
    no_jpy = [p for p in fx.PAIRS if p != "USDJPY"]
    cheap = ["EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
    todo = (("V7 skip no-stall", "V7", None, None, None), ("V8 wait for 15% pullback", "V8", None, None, None),
            ("V8b without USDJPY", "V8", None, no_jpy, None), ("V8c b + max 3 pairs/day", "V8", 3, no_jpy, None))
    if "--v7" in sys.argv:
        todo = (("V7b without USDJPY", "V7", None, no_jpy, None),
                ("V7c b + max 3/day cheapest", "V7", 3, no_jpy, cheap),
                ("V7d b + max 2/day cheapest", "V7", 2, no_jpy, cheap))
    for name, mode, cap, pairs, prio in todo:
        z = run(Ps, mode, H, cap, pairs, prio)
        z.to_parquet(f"research/2026-10-18-moments/agents/fx/rel_{name.split()[0]}.parquet")
        nh = [z[z.half == h].R.mean() for h in H]
        print(f"{name:26s} n={len(z):4d} days={z.day.nunique()} win {100 * (z.pips > 0).mean():.0f}% (coin "
              f"{100 * (z.coinR > 0).mean():.0f}%) gross {z.Rg.mean():+.3f} net {z.R.mean():+.3f} coin {z.coinR.mean():+.3f} | "
              f"{rt.f(nh)} | USD {z.usd.sum():+.1f} | stop med {z.sl.median():.1f}p | kinds {fx.kinds(z)} coin "
              f"{fx.kinds(z.assign(exit=z.coin_exit, kind=z.coin_kind))}")
        print("    ", risk(z))
        for p in (pairs or fx.PAIRS):
            y = z[z.pair == p]
            print(f"     {p} n={len(y):3d} net {y.R.mean():+.3f} coin {y.coinR.mean():+.3f} | {rt.f([y[y.half == h].R.mean() for h in H])}")


if __name__ == "__main__":
    main()
