"""Round 2, step 2b (notes.md): the owner's Fibonacci grid. On M5 and M15 (the adaptive timeframes in use), from
the MT5 ZigZag(12, 5, 3) pivots (ChartReadFrame, each known from its confirmation bar): a grid from the latest
swing low (0) to the previous swing high (100) - mirrored for a high after a low - with the levels 23.6 / 38.2 / 50
/ 61.8 / 78.6 / 88.1 / 100. For 48 bars after the grid is known, each level's first touch; "held" = price moves
0.5 ATR away on the side it came from before a close 0.25 ATR through it. The placebo: random levels between 15 %
and 95 % of the grid, at least 3 % of the grid from any fib level. Design data only (2023-11 .. 2026-02).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/fibgrid.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import rules  # noqa: E402
from features import htf  # noqa: E402

from app.indicators.chart_read import ChartReadFrame  # noqa: E402
from app.indicators.price_action import SwingKind  # noqa: E402

FIBS = (0.236, 0.382, 0.5, 0.618, 0.786, 0.881, 1.0)
START, SPLIT = pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")
HL = ["H1", "H2", "H3", "H4", "H5"]
W, AWAY, THRU, MIN_GRID = 48, 0.5, 0.25, 3.0


def test_level(h, lo, c, atr, j0, j1, lv) -> tuple[str, int, int]:
    """The first touch of *lv* on bars j0..j1-1 and its outcome: (held / broken / open / none, side, touch bar).
    side +1 = came from below (a resistance test), -1 = from above (support)."""
    for j in range(j0, j1):
        if lo[j] <= lv <= h[j] or (c[j - 1] < lv < lo[j]) or (h[j] < lv < c[j - 1]):
            side = 1 if c[j - 1] < lv else -1
            a = atr[j]
            if (c[j] - lv) * side >= THRU * a:
                return "broken", side, j
            for k in range(j + 1, min(j + W, len(c))):
                away = (lo[k] <= lv - AWAY * a) if side > 0 else (h[k] >= lv + AWAY * a)
                thru = (c[k] - lv) * side >= THRU * a
                if away:
                    return "held", side, j
                if thru:
                    return "broken", side, j
            return "open", side, j
    return "none", 0, -1


def main() -> None:
    rules.gold.below_normal_priority()
    P = rules.jlib.Instr("XAUUSD")
    AD = pd.read_parquet(HERE / "adaptive.parquet", columns=["ad_tf"]).ad_tf
    rng = np.random.default_rng(7)
    rows = []
    for tf in (5, 15):
        b = htf(P.m, tf)
        cnd = b[["open", "high", "low", "close"]].copy()
        cnd.index = pd.DatetimeIndex(b.end)
        fr = ChartReadFrame(f"M{tf}", cnd, 0.01)
        h, lo, c, atr = fr.h, fr.lo, fr.c, fr.atr
        piv = fr.pivots
        ad_at = AD.reindex(cnd.index - pd.Timedelta(minutes=1), method="ffill").to_numpy()
        for p0, p1 in zip(piv[:-1], piv[1:], strict=False):
            t = cnd.index[p1.confirm_pos]
            if t < START or t >= SPLIT:
                continue
            j0 = p1.confirm_pos + 1  # the first bar after the grid is known
            a = atr[p1.confirm_pos]
            span = abs(p0.price - p1.price)
            if not np.isfinite(a) or span < MIN_GRID * a or j0 + W >= len(c):
                continue
            # 0 = the latest pivot, 100 = the previous one
            up = p1.kind is SwingKind.LOW  # a low after a high: the grid above the low
            base, sgn = p1.price, (1 if up else -1)
            fib = [(f, base + sgn * f * span) for f in FIBS]
            ok = np.ones(1000, bool)
            grid = np.linspace(0.15, 0.95, 1000)
            for f in FIBS[:-1]:
                ok &= np.abs(grid - f) >= 0.03
            plc = rng.choice(grid[ok], size=6, replace=False)
            for kind, levels in (("fib", fib), ("placebo", [(f, base + sgn * f * span) for f in plc])):
                for f, lv in levels:
                    res, side, j = test_level(h, lo, c, atr, j0, j0 + W, lv)
                    if res == "none":
                        continue
                    rows.append(dict(tf=tf, t=t, kind=kind, f=f, res=res, side=side, up=up, span_atr=span / a,
                                     ad_tf=ad_at[p1.confirm_pos], wait=j - j0))
    D = pd.DataFrame(rows)
    D["half"] = pd.cut(D.t, rules.HALVES, labels=HL, right=False)
    D.to_parquet(HERE / "fibgrid_design.parquet")
    D = D[D.res != "open"]
    D["held"] = (D.res == "held").astype(float)
    for tf in (5, 15):
        for scope, X in (("all grids", D[D.tf == tf]), ("adaptive TF in use", D[(D.tf == tf) & (D.ad_tf == tf)])):
            print(f"\n== M{tf}, {scope}: fib touches {int((X.kind == 'fib').sum())}, placebo {int((X.kind == 'placebo').sum())}")
            pl = X[X.kind == "placebo"]
            print(f"{'level':>6} {'n':>6} {'held':>6} {'plc':>6} {'diff':>6} {'halves+':>7} | from below (resistance) / from above (support)")
            for f in FIBS:
                g = X[(X.kind == "fib") & (X.f == f)]
                near = pl if f == 1.0 else pl[(pl.f - f).abs() <= 0.10]
                per = []
                for hh in HL:
                    gh, ph = g[g.half == hh], near[near.half == hh]
                    if len(gh) >= 20 and len(ph) >= 20:
                        per.append(gh.held.mean() - ph.held.mean())
                sides = []
                for sd in (1, -1):
                    gs, ps = g[g.side == sd], near[near.side == sd]
                    sides.append(f"{gs.held.mean():.3f} vs {ps.held.mean():.3f} (n {len(gs)})")
                print(f"{f * 100:6.1f} {len(g):6} {g.held.mean():6.3f} {near.held.mean():6.3f} {g.held.mean() - near.held.mean():+6.3f}"
                      f" {sum(v > 0 for v in per)}/{len(per)}     | " + " / ".join(sides))
            print(f"placebo overall: n {len(pl)}, held {pl.held.mean():.3f}")


if __name__ == "__main__":
    main()
