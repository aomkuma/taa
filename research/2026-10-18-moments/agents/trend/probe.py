"""Probe one rule family on the design data: per half-year, per side, the neighbourhood of parameters, and a
coin-flip side on the same entries.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/probe.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402
import sim  # noqa: E402

EV = "research/2026-10-18-moments/agents/trend/orb_events.parquet"


def evaluate(B, d: pd.DataFrame, side: np.ndarray, stop: str, exit_: str, hz: int, kmult: float = 1.0) -> pd.DataFrame:
    P = sim.paths(B, d.e.to_numpy(), side, 260)
    # distances from the breakout side's fill (a coin side keeps the same distance)
    e, s0 = d.e.to_numpy(), d.side.to_numpy()
    fill0 = np.where(s0 > 0, B.o[e] + B.sp[e] + sim.SLIP, B.o[e] - sim.SLIP)
    if stop == "opp":
        risk = np.where(s0 > 0, fill0 - d.lo.to_numpy(), d.hi.to_numpy() - fill0)
    elif stop == "mid":
        risk = (fill0 - (d.hi + d.lo).to_numpy() / 2) * s0
    else:
        risk = float(stop[3:]) / 100 * d.adr.to_numpy()
    risk = risk * kmult
    kw: dict = {}
    tp = None
    if exit_.startswith("trail"):
        a, b = (float(x) for x in exit_[5:].split("/"))  # trail distance / start, in R
        kw = dict(trail=a * risk, trail_start=b * risk)
    elif exit_.startswith("tp"):
        tp = float(exit_[2:]) * risk
    o = sim.run(P, risk, tp, hz, kind_tp=(tp if tp is not None else 2 * risk), **kw)
    return pd.DataFrame(dict(t=d.t.to_numpy(), side=side, usd=o["usd"], R=o["R"], exit=o["exit"], mins=o["mins"],
                             kind=o["kind"], risk=risk, half=d.half.to_numpy()))


def summary(r: pd.DataFrame, label: str) -> None:
    hn = [h[0] for h in lab.HALVES]
    hs = r.groupby("half").R.mean().reindex(hn)
    k = r.kind[r.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    print(f"  {label:42} N {len(r):4}  R {r.R.mean():+.3f}  win {100 * (r.usd > 0).mean():3.0f}%  usd {r.usd.mean():+6.2f}"
          f"  halves+ {(hs > 0).sum()}/{hs.notna().sum()}  kinds {100 * k['1']:.0f}/{100 * k['2']:.0f}/{100 * k['3']:.0f}"
          f"  | " + " ".join(f"{v:+.2f}" for v in hs.to_numpy()))


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    ev = pd.read_parquet(EV)
    ev = ev[(ev.t < lab.DESIGN_END)].reset_index(drop=True)
    rng = np.random.default_rng(7)
    with_h1 = np.where(ev.side > 0, ev.h1_up, ev.h1_dn)
    base = ev[(ev.sess == "ny830") & (ev.f == 60) & with_h1 & (ev.delay <= 15)].reset_index(drop=True)
    print("ny830 f60, with H1, delay <= 15: per side")
    r = evaluate(B, base, base.side.to_numpy(), "opp", "trail1/1", 180)
    summary(r, "all")
    summary(r[r.side > 0], "longs")
    summary(r[r.side < 0], "shorts")
    for s in range(3):
        c = evaluate(B, base, rng.choice([-1, 1], len(base)), "opp", "trail1/1", 180)
        summary(c, f"coin side {s}")
    c = evaluate(B, base, np.ones(len(base), int), "opp", "trail1/1", 180)
    summary(c, "always long on the same entries")
    print("\nneighbourhood (the same entries):")
    for stop in ("opp", "mid", "adr10", "adr15", "adr20"):
        for ex in ("trail1/1", "trail0.75/1", "trail1.5/1", "trail1/0.5", "trail2/2", "tp1", "tp2", "tp3", "tp99"):
            for hz in (120, 180):
                summary(evaluate(B, base, base.side.to_numpy(), stop, ex, hz), f"{stop} {ex} {hz}")
    print("\nthe same rule in other sessions / range lengths / delays:")
    for sess in ("asia", "london", "ny830", "ny930"):
        for f in (15, 30, 60):
            for dl in (15, 30, 120):
                x = ev[(ev.sess == sess) & (ev.f == f) & np.where(ev.side > 0, ev.h1_up, ev.h1_dn) & (ev.delay <= dl)]
                x = x.reset_index(drop=True)
                if len(x) < 80:
                    continue
                summary(evaluate(B, x, x.side.to_numpy(), "opp", "trail1/1", 180), f"{sess} f{f} delay<={dl}")


if __name__ == "__main__":
    main()
