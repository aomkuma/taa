"""Checklist #35 - where each piece of the daily plan pays (notes.md, written before it is computed; owner, 2026-10-20:
"if a strategy profits, see in which market state it profits often - trend or sideways - note it, and when the market
runs against the strategy, lower its weight"). Per trade of `combo_trades.parquet`, from the D1 bars complete before
its entry: the 20-day efficiency (phase.efficiency; P1's terciles 0.116 / 0.264: sideways / mixed / trend) and the D1
volatility (ATR14 against its 100-day median: >= 1.25 high, else normal). R per piece x state, per part. The weights
are chosen from P1 only (0.5 where a piece's P1 R in that state < 0, else 1) and applied to P2.

    .venv/Scripts/python research/2026-10-18-moments/agents/precursors/regime.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "journal"))
import foundation as F  # noqa: E402

ER_EDGES = (0.116, 0.264)   # P1's terciles of the D1 20-day efficiency (phase.py)
HIGH_VOL = 1.25


def state_at(d1: pd.DataFrame, t: pd.DatetimeIndex) -> pd.DataFrame:
    from indicators import at  # noqa: PLC0415
    from phase import efficiency  # noqa: PLC0415

    c = d1.close.to_numpy(float)
    er = efficiency(c, 20)
    atr = F.atr(d1.high.to_numpy(float), d1.low.to_numpy(float), c, 14)
    rel = atr / pd.Series(atr).rolling(100, min_periods=50).median().to_numpy()
    k = at(pd.DatetimeIndex(d1["avail"]).as_unit("ns").asi8, t.as_unit("ns").asi8)
    e, v = er[np.maximum(k, 0)], rel[np.maximum(k, 0)]
    trend = np.where(e < ER_EDGES[0], "sideways", np.where(e > ER_EDGES[1], "trend", "mixed"))
    vol = np.where(v >= HIGH_VOL, "high vol", "normal vol")
    return pd.DataFrame(dict(er=e, vol_rel=v, trend=trend, vol=vol))


def weighted(T: pd.DataFrame, W: dict) -> pd.Series:
    return T.apply(lambda r: W.get((r.piece, r.trend), 1.0), axis=1)


def main() -> None:
    import plib  # noqa: PLC0415

    from indicators import bars  # noqa: PLC0415

    m = plib.load_learning(start=pd.Timestamp("2025-01-01", tz="UTC"))  # ends before 2026-04-18; no exam row read
    d1 = bars(m, "1D")
    name = sys.argv[1] if len(sys.argv) > 1 else "combo_trades_slip1.parquet"
    print("trades:", name)
    T = pd.read_parquet(HERE / name)
    T = pd.concat([T.reset_index(drop=True), state_at(d1, pd.DatetimeIndex(T.t_in))], axis=1)
    pd.set_option("display.width", 200)
    for key in ("trend", "vol"):
        print(f"\n== R by piece x {key} (mean R, trades), per part")
        print(T.groupby(["piece", key, "part"]).R.agg(["mean", "size"]).round(3).unstack("part").to_string())
    P1 = T[T.part == "P1"]
    W = {(p, s): 0.5 for (p, s), g in P1.groupby(["piece", "trend"]) if g.R.mean() < 0}
    print(f"\nthe weights from P1 (0.5 where the piece lost in that trend state): {W}")
    W2 = {("Asia B2", "trend"): 0.5, ("London ORB", "trend"): 0.5, ("NY straddle", "sideways"): 0.5, ("NY straddle", "mixed"): 0.5}
    print(f"the weights by mechanism (range pieces cut in a trend, the breakout piece cut outside one; chosen after seeing both parts - a hypothesis for the exam): {W2}")
    for p in ("P1", "P2"):
        G = T[T.part == p]
        w2 = weighted(G, W2)
        print(f"  {p}: by mechanism: weighted R {np.sum(G.R * w2) / np.sum(w2):+.3f}, USD {np.sum(G.pnl * w2):+.1f}")
    for p in ("P1", "P2"):
        G = T[T.part == p]
        w = weighted(G, W)
        print(f"  {p}: unweighted R {G.R.mean():+.3f} | weighted R per trade (sum R x w / sum w) {np.sum(G.R * w) / np.sum(w):+.3f} | "
              f"USD {G.pnl.sum():+.1f} -> {np.sum(G.pnl * w):+.1f}")


if __name__ == "__main__":
    main()
