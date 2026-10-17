"""Agent "cross": the one test of a frozen rule (written in notes.md first) on 2026-03-01 .. 2026-10-14
(indices end 2026-10-05). Also prints the same rule on the design data for the record.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/test.py RULE [--design]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from design import fires, signals  # noqa: E402
from fxlab import PIP, Inst, kinds, run  # noqa: E402

# frozen rules (see notes.md); legs = (symbol, direction vs the equity sign)
RULES: dict[str, dict] = {}

DESIGN = (pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC"))
TEST = (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp("2026-10-15", tz="UTC"))


def usd_per_pip(sym: str, price_pips: np.ndarray) -> np.ndarray:
    """USD value of one pip at 0.01 lot (1,000 units; gold 1 oz: 1 USD per USD)."""
    if sym == "XAUUSD":
        return np.ones_like(price_pips)
    if sym.endswith("USD"):
        return np.full_like(price_pips, 1000 * PIP[sym])
    return 1000 * PIP[sym] / (price_pips * PIP[sym])  # USDxxx: the pip is in the quote currency


def main() -> None:
    gold.below_normal_priority()
    name = sys.argv[1]
    rule = RULES[name]
    lo, hi = DESIGN if "--design" in sys.argv else TEST
    sig = signals()
    f = fires(sig[rule["sig"]], rule["hours"], rule["thr"], lo, hi)
    parts, coins = [], []
    rng = np.random.default_rng(11)
    for sym, dirn in rule["legs"]:
        inst = Inst(sym)
        d = inst.index_at(f.index)
        sides = (np.sign(f.to_numpy()) * dirn).astype(int)
        r = run(inst, d, sides, rule["tp"], rule["sl"], rule["be"], rule["hz"], f.index)
        r["sym"] = sym
        r["usd"] = r.pnl * usd_per_pip(sym, inst.o[r.e.to_numpy()])
        parts.append(r)
        cs = []
        for _ in range(20):
            c = run(inst, d, rng.choice([-1, 1], len(d)), rule["tp"], rule["sl"], rule["be"], rule["hz"], f.index)
            c["sym"] = sym
            c["usd"] = c.pnl * usd_per_pip(sym, inst.o[c.e.to_numpy()])
            cs.append(c)
        coins.append(pd.concat(cs))
    r = pd.concat(parts, ignore_index=True)
    c = pd.concat(coins, ignore_index=True)
    days = pd.bdate_range(lo, min(hi, pd.Timestamp("2026-10-06", tz="UTC"))).size
    print(f"rule {name}: {rule}\nwindow {lo.date()} .. {hi.date()}  signals {len(f)}  trades {len(r)}  "
          f"({len(r) / days:.2f}/day over {days} weekdays)")
    print("month     n  win%  pips/tr   R/tr   USD(0.01)  | coin R/tr (20 seeds)")
    r["m"] = r.t.dt.strftime("%Y-%m")
    c["m"] = c.t.dt.strftime("%Y-%m")
    for m, g in r.groupby("m"):
        cg = c[c.m == m]
        print(f"{m}  {len(g):3}  {100 * (g.exit == 'win').mean():4.0f}  {g.pnl.mean():+7.2f}  {g.R.mean():+6.3f}  {g.usd.sum():+9.2f}"
              f"   | {cg.R.mean():+6.3f}")
    print(f"TOTAL    {len(r):3}  {100 * (r.exit == 'win').mean():4.0f}  {r.pnl.mean():+7.2f}  {r.R.mean():+6.3f}  {r.usd.sum():+9.2f}"
          f"   | coin {c.R.mean():+6.3f}, win {100 * (c.exit == 'win').mean():.0f} %")
    by_m = r.groupby("m").R.sum()
    print(f"months positive {(by_m > 0).sum()}/{len(by_m)}; exits {r.exit.value_counts().to_dict()}")
    print(f"edge over the coin: win {100 * ((r.exit == 'win').mean() - (c.exit == 'win').mean()):+.1f} points, "
          f"R {r.R.mean() - c.R.mean():+.3f}")
    print(f"losers' kinds 1/2/3: ours {kinds(r)} | coin {kinds(c)}")
    for sym, g in r.groupby("sym"):
        print(f"  {sym}: n {len(g)} win {100 * (g.exit == 'win').mean():.0f}% R {g.R.mean():+.3f} pips {g.pnl.mean():+.2f} "
              f"USD {g.usd.sum():+.2f}; long R {g.R[g.side > 0].mean():+.3f} short R {g.R[g.side < 0].mean():+.3f}")
    r.to_csv(f"research/2026-10-18-moments/agents/cross/trades_{name}_{'design' if '--design' in sys.argv else 'test'}.csv",
             index=False)


if __name__ == "__main__":
    main()
