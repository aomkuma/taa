"""The frozen gold news rules (notes.md) on the USD majors, unchanged in logic, translated before any FX result was
computed:

- S2 (CPI / NFP release-minute straddle, M1 worst-case ordering as straddle_m1.py): trigger D, stop S and the fill
  gap scale by the ratio of the pair's median daily range to gold's (gold at 4000; both over 2023-11 .. 2026-02):
  D = 2, S = 8, gap = 1 gold-USD -> pips. Exit at the release minute's close.
- P1 (FOMC press conference follow): unit-free already (14:40 ET, side since 14:30, stop 2 x the mean 1-minute
  range of 14:30-14:39 floored at the 13:00-13:59 mean, exit 16:39 ET).
Costs: the bar's spread column x the pair's point + 0.2 pip slippage each way. Periods: B = 2023-11 .. 2026-02
(design years, but these rules were never fitted on FX), T = 2026-03-01 .. 2026-10-14.

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/news/fx.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments/agents/news")
sys.path.insert(0, "research/2026-10-18-moments")
import gold  # noqa: E402
import lab  # noqa: E402

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
B0, T0 = pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")


class Pair(lab.Gold):
    def __init__(self, name: str) -> None:  # noqa: D107 - same arrays as lab.Gold
        m = pd.read_parquet(f"data/history/FBS-Demo/{name}/M1.parquet")
        m.index = pd.DatetimeIndex(pd.to_datetime(m["open_time"], utc=True))
        m = m.sort_index()
        self.point = 0.001 if name.endswith("JPY") else 0.00001
        self.pip = self.point * 10
        self.ot = m.index
        self.o, self.h, self.lo, self.c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.sp = m["spread"].to_numpy(float) * self.point
        self.pos = pd.Series(np.arange(len(m)), index=m.index)
        d = m[(m.index >= B0) & (m.index < T0)].resample("1D").agg({"high": "max", "low": "min"}).dropna()
        self.adr = float((d.high - d.low).median())


def gold_adr() -> float:
    m = gold.bars("M1")
    m = m[(m.index >= B0) & (m.index < T0)]
    d = m.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    return float(((d.high - d.low) / d.close).median() * 4000)


def straddle(P: Pair, i: int, D: float, S: float, gap: float, slip: float):
    o, h, lo, c, sp = P.o[i], P.h[i], P.lo[i], P.c[i], P.sp[i]
    up, dn = o + sp + D, o - D
    hu, hd = h + sp >= up, lo <= dn
    if not (hu or hd):
        return None
    if hu and hd:
        s, how = (1 if c < o else -1), "whip"
    else:
        s, how = (1 if hu else -1), "time"
    entry = (up + gap + slip) if s > 0 else (dn - gap - slip)
    adv = (lo - entry) if s > 0 else (entry - h - sp)
    if adv <= -S:
        return s, -S - slip, how if how == "whip" else "stop"
    ex = (c - slip) if s > 0 else (c + sp + slip)
    return s, (ex - entry) * s, how


def main() -> None:
    gadr = gold_adr()
    ev = lab.events(extra=True)
    ev = ev[ev.t >= B0]
    rows = []
    print(f"gold median daily range 2023-11 .. 2026-02 at 4000: {gadr:.1f} USD")
    for name in PAIRS:
        P = Pair(name)
        f = P.adr / gadr
        slip = 0.2 * P.pip
        lab.SLIP = slip  # Gold.trade and fill read the module's slippage
        print(f"{name}: median daily range {P.adr / P.pip:.0f} pips; D {2 * f / P.pip:.1f}, S {8 * f / P.pip:.1f},"
              f" gap {f / P.pip:.1f} pips")
        for r in ev.itertuples():
            i = P.pos.get(r.t)
            if i is None:
                continue
            i = int(i)
            per = "B" if r.t < T0 else "T"
            if r.main in ("CPI", "NFP"):
                out = straddle(P, i, 2 * f, 8 * f, f, slip)
                if out:
                    rows.append(dict(rule="S2", pair=name, t=r.t, main=r.main, per=per, side=out[0],
                                     pips=out[1] / P.pip, R=out[1] / (8 * f + slip), how=out[2]))
            if r.main == "PC":
                s0 = i - 30
                if s0 < 70 or P.ot[s0] != r.t - pd.Timedelta(minutes=30):
                    continue
                pre = (P.h[s0 - 60 : s0] - P.lo[s0 - 60 : s0]).mean()
                e = i + 10
                mv = P.c[e - 1] - P.o[i]
                s = 1 if mv > 0 else -1
                sl = max(2 * (P.h[e - 10 : e] - P.lo[e - 10 : e]).mean(), pre)
                for who, side in (("rule", s), ("opp", -s)):
                    out = P.trade(e, side, sl, None, 120, kind_tp=2 * sl)
                    rows.append(dict(rule="P1" if who == "rule" else "P1opp", pair=name, t=r.t, main="PC", per=per,
                                     side=side, pips=out["usd"] / P.pip, R=out["R"], how=out["exit"],
                                     kind=out["kind"]))
    d = pd.DataFrame(rows)
    d.to_parquet("research/2026-10-18-moments/agents/news/fx_results.parquet")
    pd.set_option("display.width", 220)
    g = d.groupby(["rule", "pair", "per"]).agg(n=("R", "size"), pos=("pips", lambda v: (v > 0).mean()),
                                               pips=("pips", "mean"), R=("R", "mean"), sum_pips=("pips", "sum"))
    print(g.round(2).to_string())
    print("\nall pairs pooled:")
    print(d.groupby(["rule", "per"]).agg(n=("R", "size"), pos=("pips", lambda v: (v > 0).mean()),
                                         R=("R", "mean")).round(3).to_string())
    x = d[d.rule == "S2"].copy()
    x["m"] = x.t.dt.strftime("%Y-%m")
    bm = x[x.per == "T"].groupby("m").R.sum()
    print("\nS2 test months, R summed over pairs:", bm.round(2).to_dict())


if __name__ == "__main__":
    main()
