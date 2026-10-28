"""The frozen rules T1 / T0 (notes.md) - the step table, month by month, the coin side and the side permutation.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/test.py --design
    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/test.py --check
    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/trend/test.py --test
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/trend")
import lab  # noqa: E402
import probe  # noqa: E402

TEST_START = pd.Timestamp("2026-03-01", tz="UTC")


def events(window: str) -> pd.DataFrame:
    ev = pd.read_parquet(probe.EV)
    ev = ev[(ev.sess == "ny830") & (ev.f == 60)]
    ev = ev[ev.t < lab.DESIGN_END] if window == "design" else ev[(ev.t >= TEST_START) & (ev.t < lab.TEST_END)]
    ev = ev.reset_index(drop=True)
    ev["withH1"] = np.where(ev.side > 0, ev.h1_up, ev.h1_dn)
    ev["rng_adr"] = ev.rng / ev.adr
    return ev


def steps(ev: pd.DataFrame) -> list[tuple[str, np.ndarray, str]]:
    w = ev.withH1.to_numpy()
    return [
        ("0 every breakout of the 08:30-09:30 range, time exit", np.ones(len(ev), bool), "tp99"),
        ("0b + trailing exit", np.ones(len(ev), bool), "trail1/1"),
        ("1 + the H1 trend agrees", w, "trail1/1"),
        ("2 + by 10:00 ET", w & (ev.delay <= 30).to_numpy(), "trail1/1"),
        ("3 = T1: + range < 0.35 ADR", w & (ev.delay <= 30).to_numpy() & (ev.rng_adr < 0.35).to_numpy(), "trail1/1"),
        ("T0: step 1 + by 09:45 ET", w & (ev.delay <= 15).to_numpy(), "trail1/1"),
    ]


def kinds(r: pd.DataFrame) -> str:
    k = r.kind[r.kind != ""].value_counts(normalize=True).reindex(["1", "2", "3"]).fillna(0)
    return f"{100 * k['1']:.0f}/{100 * k['2']:.0f}/{100 * k['3']:.0f}% of {int((r.kind != '').sum())}"


def report(B, ev: pd.DataFrame, by: str) -> None:
    rng = np.random.default_rng(2026)
    for name, m, ex in steps(ev):
        x = ev[m].reset_index(drop=True)
        r = probe.evaluate(B, x, x.side.to_numpy(), "opp", ex, 180)
        days = pd.bdate_range(ev.t.min().normalize(), ev.t.max().normalize()).size
        coins = [probe.evaluate(B, x, rng.choice([-1, 1], len(x)), "opp", ex, 180) for _ in range(300)]
        perms = [probe.evaluate(B, x, rng.permutation(x.side.to_numpy()), "opp", ex, 180).R.mean() for _ in range(300)]
        cR = np.array([c.R.mean() for c in coins])
        cU = np.array([c.usd.sum() for c in coins])
        ck = pd.concat(coins)
        grp = r.t.dt.strftime("%Y-%m") if by == "month" else r.half
        g = r.groupby(grp)
        print(f"\n== {name}: N {len(r)} ({len(r) / days:.2f}/day)  R {r.R.mean():+.3f}  win {100 * (r.usd > 0).mean():.0f}%"
              f"  USD {r.usd.sum():+.1f} ({r.usd.mean():+.2f}/trade)  {by}s+ {(g.R.mean() > 0).sum()}/{g.ngroups}")
        print(f"   coin side (300 draws): R {cR.mean():+.3f} +- {cR.std():.3f}, USD {cU.mean():+.1f}; ours beats {100 * (cR < r.R.mean()).mean():.0f}%"
              f" | permuted sides R {np.mean(perms):+.3f} +- {np.std(perms):.3f}, ours beats {100 * (np.array(perms) < r.R.mean()).mean():.0f}%")
        print(f"   losers' kinds ours {kinds(r)} | coin {kinds(ck)};  exits {r.exit.value_counts().to_dict()};"
              f" longs {int((r.side > 0).sum())} R {r.R[r.side > 0].mean():+.3f}, shorts {int((r.side < 0).sum())} R {r.R[r.side < 0].mean():+.3f}")
        tab = pd.DataFrame({"N": g.size(), "win%": g.usd.apply(lambda u: 100 * (u > 0).mean()), "USD": g.usd.sum(),
                            "R/trade": g.R.mean(), "risk USD": g.risk.median()})
        print(tab.round(2).to_string())


def check(B) -> None:
    ev = events("design")
    m = steps(ev)[4][1]
    x = ev[m].reset_index(drop=True)
    r = probe.evaluate(B, x, x.side.to_numpy(), "opp", "trail1/1", 180)
    for i in (0, len(x) // 2, len(x) - 1):
        row, o = x.iloc[i], r.iloc[i]
        e = int(row.e)
        print(f"\n{row.t} ET range {row.t.tz_convert(lab.NY)}: hi {row.hi:.2f} lo {row.lo:.2f} rng {row.rng:.2f} adr {row.adr:.2f}"
              f" side {row.side} delay {row.delay} H1 up {row.h1_up} dn {row.h1_dn}")
        print(f"  entry bar {B.ot[e]} open {B.o[e]:.2f} spread {B.sp[e]:.2f}; exit {o.exit} after {o.mins} min, usd {o.usd:+.2f}, R {o.R:+.3f}, risk {o.risk:.2f}")
        k = e - 1
        print(f"  breakout bar {B.ot[k]} close {B.c[k]:.2f}; previous closes {np.round(B.c[k - 3 : k], 2)}")
        j = e + int(o.mins) - 1
        print(f"  exit bar {B.ot[j]} o/h/l/c {B.o[j]:.2f}/{B.h[j]:.2f}/{B.lo[j]:.2f}/{B.c[j]:.2f};"
              f" path best high {B.h[e : j + 1].max():.2f} low {B.lo[e : j + 1].min():.2f}")
        # recompute the range from the raw bars
        t0 = row.t
        sl = (B.ot >= t0) & (B.ot < t0 + pd.Timedelta(minutes=60))
        print(f"  range recomputed hi {B.h[sl].max():.2f} lo {B.lo[sl].min():.2f} from {sl.sum()} bars")
        q = B.trade(e, int(row.side), float(o.risk), None, e + 180, trail=float(o.risk), trail_start=float(o.risk))
        print(f"  loop simulator: {q['exit']} {q['usd']:+.2f} after {q['mins']} min")


def main() -> None:
    lab.gold.below_normal_priority()
    B = lab.Bars()
    if "--check" in sys.argv:
        check(B)
    elif "--design" in sys.argv:
        report(B, events("design"), "half")
    elif "--test" in sys.argv:
        report(B, events("test"), "month")


if __name__ == "__main__":
    main()
