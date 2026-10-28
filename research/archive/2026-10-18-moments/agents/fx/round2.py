"""Round 2: RF variants (10:00 ET calendar, spike vs grind, exits, AUD/NZD stop floor). Design halves; with --seen
also the SEEN test window (RF's test is already known; these are not independent tests).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/round2.py [--seen] [--steps a,b]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
import cand  # noqa: E402
import fxlib as fx  # noqa: E402
import lab  # noqa: E402
import reltrades as rt  # noqa: E402

fx.below_normal_priority()
H = cand.H
ALL = ["EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
CAL = pd.read_csv("research/2026-10-18-moments/agents/fx/cal10.csv")
CAL10 = set(pd.to_datetime(CAL.date))
_EV: dict = {}


def events(P: fx.Pair, period) -> pd.DataFrame:
    key = (P.sym, tuple(period))
    if key in _EV:
        return _EV[key]
    ev = rt.build(P, 10, 14)
    ev = ev[ev.half.isin(period) & ev.rel].reset_index(drop=True)
    i845 = lab.local_index(P, fx.NYC, 8.75)
    c845 = pd.Series(P.c[i845.to_numpy()], index=i845.index).reindex(ev.day).to_numpy()
    mv = ev.move.to_numpy()
    ev["spike"] = (c845 - ev.pre.to_numpy()) / np.where(mv == 0, np.nan, mv)
    ev["pre_share"] = (ev.pre.to_numpy() - P.o[ev.a.to_numpy()]) / np.where(mv == 0, np.nan, mv)
    ev["cal10"] = pd.to_datetime(ev.day).isin(CAL10)
    _EV[key] = ev
    return ev


def one(P, d, side, sl, hz, exit_):
    if exit_ == "time":
        return P.trade(d, side, None, sl, hz)
    if exit_ == "be1":
        return P.trade(d, side, None, sl, hz, be=sl)
    a = P.trade(d, side, sl, sl, hz)  # half with a +1R target
    b = P.trade(d, side, None, sl, hz, be=sl)  # half with BE at +1R
    if a is None or b is None:
        return None
    r = dict(b)
    for k in ("pips", "R", "usd"):
        r[k] = 0.5 * (a[k] + b[k])
    r["xi"] = max(a["xi"], b["xi"])
    r["exit"] = "stop" if (a["exit"] == "stop" and b["exit"] == "stop") else ("win" if a["exit"] == "win" else b["exit"])
    r["kind"] = a["kind"] if r["exit"] == "stop" else ""
    return r


def rule(Ps, period, cal=None, spike=None, exit_="time", floor=None, floor_pairs=("AUDUSD", "NZDUSD"),
         pairs=ALL, coin_seed=None) -> pd.DataFrame:
    rows = []
    for p in pairs:
        P = Ps[p]
        ev = events(P, period)
        rng = np.random.default_rng(coin_seed if coin_seed is not None else 0)
        for k, r in enumerate(ev.itertuples()):
            atr, mv = r.h1_atr, r.move
            if abs(mv) < atr or not (r.pre_share <= 0.25):
                continue
            side = -int(np.sign(mv))
            ext = r.whi if side < 0 else r.wlo
            rngw = r.whi - r.wlo
            if abs(ext - r.px) / rngw <= 0.10:
                continue
            if spike is not None and not (r.spike >= spike):
                continue
            d, hz, px = int(r.d), int(r.hz), r.px
            if r.cal10 and cal == "skip":
                continue
            if r.cal10 and cal == "after":
                d2 = d + 15
                if d2 >= P.n or P.tmin[d2] - P.tmin[d] != 15:
                    continue
                seg = slice(d + 1, d2 + 1)
                if (side < 0 and P.h[seg].max() > ext) or (side > 0 and P.lo[seg].min() < ext):
                    continue
                d, hz, px = d2, hz - 15, P.c[d2]
            fl = floor if (floor is not None and p in floor_pairs) else 1.0
            sl = max(abs(ext - px) + 1.0 * atr, fl * atr)
            if sl * P.usd_pip[d] > 4.0:
                continue
            s_ = side if coin_seed is None else int(rng.choice([-1, 1]))
            z = one(P, d, s_, sl, hz, exit_)
            if z is None:
                continue
            z |= dict(t=P.ot[d], half=r.half, side=s_, sl=sl, pair=p, day=r.day, atr=atr, spike=r.spike, cal10=r.cal10,
                      slk=sl / atr)
            rows.append(z)
    z = pd.DataFrame(rows)
    z["prio"] = z.pair.map({p: i for i, p in enumerate(cand.PAIRS)})
    z = z.sort_values(["day", "prio"]).groupby("day").head(3)
    return z.sort_values("t").reset_index(drop=True)


def causes(z: pd.DataFrame) -> str:
    st = z[z.exit == "stop"]
    a = st.mins <= 20
    b = ~a & (st.spike < 0.5)
    c = ~a & ~b & (st.slk < 1.5)
    d = ~a & ~b & ~c
    tl = ((z.exit != "stop") & (z.R < 0)).sum()
    return (f"stops {len(st)}: (a) <=20 min {a.sum()} [{st[a].cal10.sum()} on 10:00 days] (b) grind {b.sum()} "
            f"(c) tight {c.sum()} (d) other {d.sum()} | time/BE exits < 0: {tl}")


def line(name, z, halves):
    nh = [z[z.half == h].R.mean() for h in halves]
    r = cand.risk(z)
    hs = rt.f(nh) if len(halves) > 1 else ""
    print(f"  {name:40s} n={len(z):4d} win {100 * (z.pips > 0).mean():3.0f}% net {z.R.mean():+.3f} "
          f"pos {sum(np.array(nh) > 0)}/{len(halves)} | {hs} | pips {z.pips.sum():+7.1f} USD {z.usd.sum():+6.1f} | worst "
          f"{r['worst']:+.2f} day {r['worst_day']:+.2f} streak {r['streak']} maxDD {r['maxdd']:.1f} 6L {r['six']:.1f}")
    print(f"  {'':40s} {causes(z)}")


STEPS = {
    "RF": dict(),
    "C1 skip 10:00 days": dict(cal="skip"),
    "C1b decide 10:15 on 10:00 days": dict(cal="after"),
    "S spike>=0.5": dict(spike=0.5),
    "E1 BE at +1R": dict(exit_="be1"),
    "E2 half at +1R, BE": dict(exit_="part1"),
    "F floor 1.5 ATR AUD/NZD": dict(floor=1.5),
    "F2 floor 1.5 ATR all": dict(floor=1.5, floor_pairs=tuple(ALL)),
    "D drop AUD/NZD": dict(pairs=["EURUSD", "GBPUSD", "USDCHF", "USDCAD"]),
    "K1 C1b + S": dict(cal="after", spike=0.5),
    "K2 C1b + E2": dict(cal="after", exit_="part1"),
    "K3 C1b + S + E2": dict(cal="after", spike=0.5, exit_="part1"),
    "K4 C1b + S + E2 + D": dict(cal="after", spike=0.5, exit_="part1", pairs=["EURUSD", "GBPUSD", "USDCHF", "USDCAD"]),
}


def main() -> None:
    Ps = {p: fx.Pair(p) for p in ALL}
    seen = "--seen" in sys.argv
    steps = STEPS
    for a in sys.argv:
        if a.startswith("--combo="):
            # cumulative combination given as k=v;k=v
            pass
    print("== design (2023-11 .. 2026-02) ==")
    for name, kw in steps.items():
        line(name, rule(Ps, H, **kw), H)
    if seen:
        print("\n== SEEN test window 2026-03-01 .. 2026-10-14 (RF's test already known) ==")
        for name, kw in steps.items():
            line(name, rule(Ps, ["TEST"], **kw), ["TEST"])


if __name__ == "__main__":
    main()
