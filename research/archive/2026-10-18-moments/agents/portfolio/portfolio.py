"""The frozen families and the portfolio (notes.md), on design or (after the freeze) on the test window.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/portfolio/portfolio.py design|test

Per family: trades, a day, win %, R, USD at 0.01 lot, by half-year (design) / month (test), the account, the coin
(10 seeds), the side-permutation coin (the family's long share kept) and always-long on the same minutes, the
losers' kinds. Portfolios P-A (one gold position at a time across the admitted families, priority by design R),
P-B (P-A, one trade a session), P-C (P-A plus the break-even families, declared to show the count's price), and S2 on
EURUSD (the news agent's fx_results) as its own calendar slot, month by month together."""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import plib
from design import sig

HERE = plib.HERE
# FROZEN (notes.md "Frozen for the test"): family -> conditions, priority (1 = first)
FINAL = {
    "F3": (["C4 72-h extreme near/behind"], 1),
    "F1": (["C4 72-h extreme near/behind", "C5 not a fast tape"], 2),
}
EXTRA = {  # break-even families, P-C only
    "F2": (["C1 H1 leg not against"], 3),
    "F7": (["C4 72-h extreme near/behind"], 4),
}


def family_signals(fk: str, conds: list[str], prio: int, part: str) -> pd.DataFrame:
    S = sig(fk, part)
    m = np.ones(len(S), bool)
    for c in conds:
        m &= plib.MENU[c](S).to_numpy(bool)
    return S[m].assign(fam=fk, prio=prio)


def coin_perm(S: pd.DataFrame, P, seeds: int = 10, **kw) -> tuple[float, float]:
    """Sides permuted (the long share kept) and always long, on the same signal minutes."""
    rs = []
    for s in range(seeds):
        rng = np.random.default_rng(300 + s)
        rs.append(plib.run(S.assign(side=rng.permutation(S.side.to_numpy())), P, **kw).R.mean())
    al = plib.run(S.assign(side=1), P, **kw).R.mean()
    return float(np.mean(rs)), float(al)


def periods(z: pd.DataFrame, part: str) -> str:
    if part == "design":
        return plib.by_half(z)
    g = z.groupby(z.t.dt.strftime("%Y-%m"))
    return "months+ {}/{}: ".format((g.pnl.sum() > 0).sum(), g.ngroups) + " ".join(
        f"{k[5:]} {len(v)} {v.pnl.sum():+.1f}" for k, v in g)


def s2(part: str) -> pd.DataFrame:
    d = pd.read_parquet(HERE.parent / "news/fx_results.parquet")
    d = d[(d.rule == "S2") & (d.pair == "EURUSD") & (d.per == ("B" if part == "design" else "T"))].copy()
    d["usd"] = d.pips * 0.10  # 0.01 lot EURUSD = 0.10 USD a pip
    return d


def main() -> None:
    part = sys.argv[1]
    plib.jlib.gold.below_normal_priority()
    P = plib.jlib.Instr("XAUUSD")
    pp = "wdesign" if part == "design" else "wtest"
    a, b = ("2023-11-01", "2026-03-01") if part == "design" else ("2026-03-01", "2026-10-14")
    days = pd.bdate_range(a, b, inclusive="left").size
    tag = "DESIGN 2023-11 .. 2026-02" if part == "design" else "TEST 2026-03-01 .. 10-14"
    print(f"== {tag}, gold, real costs, 0.01 lot ({days} weekdays)")
    sigs = {}
    for fk, (conds, prio) in (FINAL | EXTRA).items():
        S = family_signals(fk, conds, prio, pp)
        sigs[fk] = S
        z = plib.run(S, P)
        if not len(z):
            print(f"\n{fk}: 0 trades")
            continue
        c = plib.coin(S, P)
        cp, al = coin_perm(S, P)
        print(f"\n{fk} ({' + '.join(conds)}){'  [break-even family, P-C only]' if fk in EXTRA else ''}")
        print(plib.summary(z, days, "rule"))
        print(f"    {periods(z, part)}")
        print(f"    coin R {c['R']:+.3f} (win {100 * c['win']:.0f}%), permuted sides {cp:+.3f}, always long {al:+.3f};"
              f" longs {(z.side > 0).mean() * 100:.0f}%; kinds ours {plib.kinds(z)} / coin {c['kinds']}; exits {z.exit.value_counts().to_dict()}")
        print("    sessions: " + ", ".join(f"{plib.jlib.SESS[s]} {len(g)} {g.R.mean():+.3f} R {g.pnl.sum():+.1f} USD" for s, g in z.groupby("session")))
        z.attrs = {}
        z.to_parquet(HERE / f"pf_{fk}_{part}.parquet")
    adm = pd.concat([sigs[k] for k in FINAL])
    ext = pd.concat([sigs[k] for k in FINAL | EXTRA])
    S2 = s2(part)
    print(f"\nS2 EURUSD (news agent, M1 worst-case order; {'design B' if part == 'design' else 'test T, SEEN by the news agent'}):"
          f" {len(S2)} trades, {S2.R.mean():+.2f} R, {S2.usd.sum():+.1f} USD at 0.01 lot, worst {S2.usd.min():+.2f},"
          f" max DD {float((np.maximum.accumulate(np.r_[0, S2.usd.cumsum()]) - np.r_[0, S2.usd.cumsum()]).max()):.1f}")
    for name, S, kw in (("P-A admitted, one position", adm, {}), ("P-B admitted, one a session", adm, {"per_sess_all": 1}),
                        ("P-C + break-even families", ext, {})):
        z = plib.run(S, P, prio="prio", **kw)
        z.attrs = {}
        z.to_parquet(HERE / f"pf_{name[:3]}_{part}.parquet")
        print(f"\n{name}")
        print(plib.summary(z, days, "gold"))
        print(f"    {periods(z, part)}")
        print("    by family: " + ", ".join(f"{k} {len(g)} {g.R.mean():+.3f}" for k, g in z.groupby("fam")))
        mon = z.groupby(z.t.dt.strftime("%Y-%m")).pnl.sum().rename("gold")
        m2 = S2.groupby(S2.t.dt.strftime("%Y-%m")).usd.sum().rename("S2 EURUSD")
        M = pd.concat([mon, m2], axis=1).fillna(0.0)
        M["total"] = M.sum(1)
        # the account: gold trades and S2 in time order
        ev = pd.concat([z[["t", "pnl"]].rename(columns={"pnl": "usd"}), S2[["t", "usd"]]]).sort_values("t")
        eq = ev.usd.cumsum().to_numpy()
        dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
        low = float(min(0.0, eq.min()))
        print(f"    with S2: {len(ev)} trades ({len(ev) / days:.2f}/day), {ev.usd.sum():+.1f} USD, max DD {dd:.1f}, lowest point"
              f" {low:+.1f} -> a 50 USD account at its lowest {50 + low:.1f}, 100 USD {100 + low:.1f};"
              f" months+ (total) {(M.total > 0).sum()}/{len(M)}")
        print("    month    " + " ".join(f"{k[2:]:>7}" for k in M.index))
        for col in M.columns:
            print(f"    {col:9}" + " ".join(f"{v:+7.1f}" for v in M[col].to_numpy()))


if __name__ == "__main__":
    main()
