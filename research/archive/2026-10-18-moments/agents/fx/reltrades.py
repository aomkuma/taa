"""Step 3c: the release-day New York reversal as trades (design halves only), variants V0.. (see notes.md).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/fx/reltrades.py [--test]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/fx")
sys.path.insert(0, "research/2026-10-18-moments")
import fxlib as fx  # noqa: E402
import gold  # noqa: E402
import lab  # noqa: E402

fx.below_normal_priority()
H = [h for h, _, _ in fx.HALVES]
rel = gold.releases()
r830 = rel[rel.time_et == "08:30"].copy()
REL_DAYS = set(pd.to_datetime(r830.date))


def f(v, p=3):
    return " ".join(f"{x:+6.{p}f}" if np.isfinite(x) else "     -" for x in v)


def build(P: fx.Pair, dec: float, exit_h: float) -> pd.DataFrame:
    ev = lab.events(P, fx.NYC, 8, dec, exit_h)
    pre = lab.local_index(P, fx.NYC, 8.5)
    ev["pre"] = pd.Series(P.c[pre.to_numpy()], index=pre.index).reindex(ev.day).to_numpy()
    ev["rel"] = ev.day.isin(REL_DAYS)
    return ev[np.isfinite(ev.h1_atr)].reset_index(drop=True)


VARIANTS = {
    # name: dict(days, dec, exit, q, stop, tp)
    "V0 all days, fade, 2ATR, 14ET": dict(days="all", dec=10, exit=14, q=0, stop="atr2", tp=None),
    "V1 release days only": dict(days="rel", dec=10, exit=14, q=0, stop="atr2", tp=None),
    "V2 + |move| >= 1 ATR": dict(days="rel", dec=10, exit=14, q=1, stop="atr2", tp=None),
    "V3 + stop beyond the 08-10 extreme +0.5ATR": dict(days="rel", dec=10, exit=14, q=1, stop="ext", tp=None),
    "V4 + target 50% retrace of the move": dict(days="rel", dec=10, exit=14, q=1, stop="ext", tp="half"),
    "V5 V3 with exit 16 ET": dict(days="rel", dec=10, exit=16, q=1, stop="ext", tp=None),
    "V6 V3 with 3ATR stop": dict(days="rel", dec=10, exit=14, q=1, stop="atr3", tp=None),
}


def run_variant(Ps, v, period_mask) -> pd.DataFrame:
    out = []
    for p, (Pn, Pg) in Ps.items():
        ev = build(Pn, v["dec"], v["exit"])
        ev = ev[period_mask(ev)].reset_index(drop=True)
        if v["days"] == "rel":
            ev = ev[ev.rel].reset_index(drop=True)
        q = (ev.move.abs() / ev.h1_atr).to_numpy()
        side = -np.sign(ev.move.to_numpy()).astype(int)
        side[q < v["q"]] = 0
        atr = ev.h1_atr.to_numpy()
        if v["stop"] == "atr2":
            sl = 2 * atr
        elif v["stop"] == "atr3":
            sl = 3 * atr
        else:  # beyond the window's extreme on the move's side + 0.5 ATR, from the decision close; at least 1 ATR
            ext = np.where(side < 0, ev.whi.to_numpy(), ev.wlo.to_numpy())
            sl = np.maximum(np.abs(ext - ev.px.to_numpy()) + 0.5 * atr, atr)
        tp = None if v["tp"] is None else 0.5 * np.abs(ev.move.to_numpy())
        zn = lab.simulate(Pn, ev, side, sl, tp)
        zg = lab.simulate(Pg, ev, side, sl, tp)
        if not len(zn):
            continue
        zn["Rg"] = zg.R.to_numpy()
        zn["pair"] = p
        zn["q"] = q[zn.ev]
        zn["day"] = ev.day.to_numpy()[zn.ev]
        out.append(zn)
    return pd.concat(out, ignore_index=True)


def report(name, z, halves):
    nh = [z[z.half == h].R.mean() for h in halves]
    gh = [z[z.half == h].Rg.mean() for h in halves]
    print(f"{name:44s} n={len(z):4d} days={z.day.nunique():3d} win {100 * (z.pips > 0).mean():3.0f}% "
          f"gross {z.Rg.mean():+.3f} net {z.R.mean():+.3f} | net by half {f(nh)} | gross {f(gh)} | "
          f"pips {z.pips.sum():+7.0f} USD {z.usd.sum():+6.1f} | stop {z.sl.median():.1f}p | kinds {fx.kinds(z)}")


def main() -> None:
    test = "--test" in sys.argv
    Ps = {p: (fx.Pair(p), fx.Pair(p, costs=False)) for p in fx.PAIRS}
    if test:
        raise SystemExit("the test runs from test.py with the frozen rule")
    mask = lambda ev: ev.half.isin(H)  # noqa: E731
    for name, v in VARIANTS.items():
        z = run_variant(Ps, v, mask)
        report(name, z, H)
        z.to_parquet(f"research/2026-10-18-moments/agents/fx/rel_{name.split()[0]}.parquet")
        if name.startswith(("V3", "V5")):
            for p in fx.PAIRS:
                report(f"   {p}", z[z.pair == p], H)


if __name__ == "__main__":
    main()
