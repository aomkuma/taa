"""Agent "cross", step 5: the London rule's trades with their context (design data only), to find why losers lose.

Signal: London 07:00-12:00 UTC, |eq30| >= 2.0 (eq = mean of US500 and JP225 vol-scaled 30-minute moves), first
minute then silent 60 minutes; side = the dollar up when equities are up. Each of five pairs traded on its own
(target 20 / stop 15 pips, 120 minutes), plus context at the decision bar (closed bars only):
  own30   the pair's own vol-scaled 30-minute move, signed by the trade side (> 0 = already moved our way)
  usd30   the dollar composite (without the pair) 30-minute move, signed by the trade side
  h1      the pair's H1 trend: close of the last closed H1 bar vs its EMA20, signed by the trade side (pips)
  h1slope EMA20(H1) slope over the last 3 closed H1 bars, signed (pips)
  rng60   the pair's high-low range of the last 60 minutes (pips)
  atr     the pair's H1 ATR14 from closed H1 bars (pips)
  pos     where the price sits in the last 4 hours' range, signed by side (1 = at the extreme our way)
  rel     a US release (CPI/NFP/PPI/PCE/GDP/FOMC) within 120 minutes after the decision
  hour, z (the equity z), side

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/cross/refine.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research/2026-10-18-moments")
sys.path.insert(0, "research/2026-10-18-moments/agents/cross")
import gold  # noqa: E402
from design import fires, signals  # noqa: E402
from fxlab import Inst, run  # noqa: E402
from measure import HALVES, PANEL, scaled_returns  # noqa: E402
from measure2 import dollar_ex  # noqa: E402

PAIRS = {"EURUSD": -1, "GBPUSD": -1, "USDCHF": 1, "USDCAD": 1, "USDJPY": 1}
LO, HI = pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")


def context(inst: Inst, sym: str, panel: pd.DataFrame, d: np.ndarray, side: np.ndarray) -> pd.DataFrame:
    t_ns = panel.index.as_unit("ns").asi8
    q = panel.copy()
    q["USDx"] = dollar_ex(panel, sym)
    usd_sign = 1 if sym.startswith("USD") else -1  # pair up = dollar up?
    own = pd.Series(scaled_returns(q, sym, 30, -1, t_ns), index=panel.index)
    usd = pd.Series(scaled_returns(q, "USDx", 30, -1, t_ns), index=panel.index)
    ts = inst.ot[d]
    m = pd.DataFrame({"o": inst.o, "h": inst.h, "l": inst.lo, "c": inst.c}, index=inst.ot)
    h1 = m.resample("1h", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    ema = h1.c.ewm(span=20, adjust=False).mean()
    tr = pd.concat([h1.h - h1.l, (h1.h - h1.c.shift()).abs(), (h1.l - h1.c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    # the last H1 bar closed at the decision (decision bar closes at ts + 1 min): H1 bar open <= ts + 1min - 1h
    k = h1.index.searchsorted(ts + pd.Timedelta(minutes=1) - pd.Timedelta(hours=1), side="right") - 1
    hc, he, ha = h1.c.to_numpy()[k], ema.to_numpy()[k], atr.to_numpy()[k]
    he3 = ema.to_numpy()[np.maximum(k - 3, 0)]
    rng60 = np.array([inst.h[i - 59:i + 1].max() - inst.lo[i - 59:i + 1].min() for i in d])
    hi4 = np.array([inst.h[i - 239:i + 1].max() for i in d])
    lo4 = np.array([inst.lo[i - 239:i + 1].min() for i in d])
    pos = (inst.c[d] - lo4) / np.maximum(hi4 - lo4, 1e-9)
    rel_t = gold.releases().t
    rel = np.array([((rel_t > t) & (rel_t <= t + pd.Timedelta(minutes=120))).any() for t in ts])
    return pd.DataFrame({
        "own30": own.reindex(ts).to_numpy() * side,
        "usd30": usd.reindex(ts).to_numpy() * side * usd_sign,
        "h1": (hc - he) * side, "h1slope": (he - he3) * side, "atr": ha, "rng60": rng60,
        "pos": np.where(side > 0, pos, 1 - pos), "rel": rel, "hour": ts.hour,
    })


def main() -> None:
    gold.below_normal_priority()
    sig = signals()
    panel = pd.read_parquet(PANEL)
    f = fires(sig["eq30"], (7, 12), 2.0, LO, HI)
    out = []
    for sym, dirn in PAIRS.items():
        inst = Inst(sym)
        d = inst.index_at(f.index)
        ok = d >= 0
        side = (np.sign(f.to_numpy()) * dirn).astype(int)
        r = run(inst, d[ok], side[ok], 20, 15, None, 120, f.index[ok])
        r["sym"], r["z"] = sym, f.reindex(r.t).to_numpy()
        ctx = context(inst, sym, panel, r.e.to_numpy() - 1, r.side.to_numpy())
        r = pd.concat([r.reset_index(drop=True), ctx.reset_index(drop=True)], axis=1)
        r["half"] = ""
        for n, a, b in HALVES:
            r.loc[(r.t >= pd.Timestamp(a, tz="UTC")) & (r.t < pd.Timestamp(b, tz="UTC")), "half"] = n
        out.append(r)
        print(sym, len(r), flush=True)
    pd.concat(out, ignore_index=True).to_parquet("research/2026-10-18-moments/agents/cross/refine_trades.parquet")


if __name__ == "__main__":
    main()
