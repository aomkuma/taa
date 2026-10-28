"""Round 2, step 2b (notes.md): the owner's rising trend line through the swing low and the later higher low (and
the falling line through a high and a lower high), alone and in confluence with a fib level of the grid from that
swing low to the previous swing high. M5 / M15 / M30 ZigZag(12, 5, 3) pivots (ChartReadFrame), each known from its
confirmation; design only. Held = 0.5 ATR away from the line before a close 0.25 ATR through it (48 bars). The
placebo: the same line shifted towards price by 0.5 .. 1.5 ATR (a line of the same slope not anchored on swings).

    PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python research/2026-10-18-moments/agents/runs/trendline.py
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
W, AWAY, THRU = 48, 0.5, 0.25


def line_test(h, lo, c, atr, j0, p_pos, p_price, slope, sgn, shift=0.0):
    """First touch of the line (value p_price + slope * (j - p_pos) + sgn * shift) from the price side (sgn +1: a
    support line below price) on bars j0 .. j0+W-1; (held / broken / open / none, touch bar, the line there)."""
    for j in range(j0, min(j0 + W, len(c))):
        v = p_price + slope * (j - p_pos) + sgn * shift
        if (c[j - 1] - v) * sgn <= 0:  # price already on the other side: not a touch from the price side
            return "none", -1, v
        probe = lo[j] if sgn > 0 else h[j]
        if (probe - v) * sgn <= 0:
            a = atr[j]
            if (v - c[j]) * sgn >= THRU * a:
                return "broken", j, v
            for k in range(j + 1, min(j + W, len(c))):
                vk = p_price + slope * (k - p_pos) + sgn * shift
                away = (h[k] >= v + AWAY * a) if sgn > 0 else (lo[k] <= v - AWAY * a)
                if away:
                    return "held", j, v
                if (vk - c[k]) * sgn >= THRU * a:
                    return "broken", j, v
            return "open", j, v
    return "none", -1, np.nan


def main() -> None:
    rules.gold.below_normal_priority()
    P = rules.jlib.Instr("XAUUSD")
    rng = np.random.default_rng(11)
    rows = []
    for tf in (5, 15, 30):
        b = htf(P.m, tf)
        cnd = b[["open", "high", "low", "close"]].copy()
        cnd.index = pd.DatetimeIndex(b.end)
        fr = ChartReadFrame(f"M{tf}", cnd, 0.01)
        h, lo, c, atr = fr.h, fr.lo, fr.c, fr.atr
        pv = fr.pivots
        for q in range(3, len(pv)):
            p2, p1, p0, pprev = pv[q], pv[q - 2], pv[q - 3], None
            if p2.kind is not p1.kind:
                continue
            sgn = 1 if p2.kind is SwingKind.LOW else -1
            if (p2.price - p1.price) * sgn <= 0:  # not a higher low (lower high)
                continue
            t = cnd.index[p2.confirm_pos]
            if t < START or t >= SPLIT:
                continue
            a0 = atr[p2.confirm_pos]
            if not np.isfinite(a0):
                continue
            slope = (p2.price - p1.price) / (p2.pivot_pos - p1.pivot_pos)
            j0 = p2.confirm_pos + 1
            if j0 + 2 * W >= len(c):
                continue
            # the fib grid from the first swing (0) to the swing before it (100)
            span = (p0.price - p1.price) * sgn
            grid = [p1.price + sgn * f * span for f in FIBS] if span > 0 else []
            res, j, v = line_test(h, lo, c, atr, j0, p1.pivot_pos, p1.price, slope, sgn)
            if res not in ("none", "open"):
                conf = bool(grid) and min(abs(v - g) for g in grid) <= 0.25 * atr[j]
                rows.append(dict(tf=tf, t=t, kind="line", res=res, conf=conf, sgn=sgn))
            shift = rng.uniform(0.5, 1.5) * a0
            res, j, v = line_test(h, lo, c, atr, j0, p1.pivot_pos, p1.price, slope, sgn, shift)
            if res not in ("none", "open"):
                conf = bool(grid) and min(abs(v - g) for g in grid) <= 0.25 * atr[j]
                rows.append(dict(tf=tf, t=t, kind="placebo", res=res, conf=conf, sgn=sgn))
    D = pd.DataFrame(rows)
    D["half"] = pd.cut(D.t, rules.HALVES, labels=HL, right=False)
    D["held"] = (D.res == "held").astype(float)
    D.to_parquet(HERE / "trendline_design.parquet")
    for tf in (5, 15, 30):
        X = D[D.tf == tf]
        print(f"\n== M{tf}")
        for name, sel in (("all touches", X.index == X.index), ("with a fib level within 0.25 ATR", X.conf),
                          ("without", ~X.conf)):
            g = X[sel]
            ln, pl = g[g.kind == "line"], g[g.kind == "placebo"]
            per = [ln[ln.half == hh].held.mean() - pl[pl.half == hh].held.mean() for hh in HL]
            print(f"  {name:34} line n {len(ln):5} held {ln.held.mean():.3f} | placebo n {len(pl):5} held {pl.held.mean():.3f}"
                  f" | diff {ln.held.mean() - pl.held.mean():+.3f}, halves + {sum(v > 0 for v in per if np.isfinite(v))}/5")


if __name__ == "__main__":
    main()
