"""The continuation play - the owner's 29/10 sell, generalised (Claude's definitions, BOT_RESEARCH).

On the small timeframe, the latest fixed leg in the trade's direction (a buy: a fixed LOW, then the fixed
HIGH after it), 0 % at the low, 100 % at the high. A limit at the line - or 10 % of the leg early with the
stop 0.5 USD beyond the line - once the high is fixed and while price is above the line; withdrawn when price
trades above the high first, or after FILL_BARS. Stop beyond 0 % (beyond 23.6 % for the 61.8 % line),
target 161.8 %, at least 2R net of the spread. A bar touching the entry is a fill even if it also reaches the
stop (the fix of 2026-10-29). Context on the larger timeframe, from its pivots fixed by then:
``none``; ``trend`` - its last two fixed highs and lows rising; ``trend<3`` - rising, and the current run has
made fewer than 3 higher highs. A sell is the mirror (prices negated).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from walk import frame

from app.indicators.chart_read import zigzag_pivots

SPREAD, BUF, FILL_BARS = 0.30, 0.50, 96


def pivots(df: pd.DataFrame, sign: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, list]:  # type: ignore[type-arg]
    hi = (df.high if sign > 0 else -df.low).to_numpy(np.float64)
    lo = (df.low if sign > 0 else -df.high).to_numpy(np.float64)
    close = (sign * df.close).to_numpy(np.float64)
    return hi, lo, close, zigzag_pivots(hi, lo, 0.01, index=list(df.index), depth=12, deviation=5, backstep=3)


def context_ok(big: list, big_conf: np.ndarray, t: pd.Timestamp, mode: str) -> bool:  # type: ignore[type-arg]
    if mode == "none":
        return True
    k = int(np.searchsorted(big_conf, np.datetime64(t.tz_convert(None)), side="right"))
    known = big[:k]
    highs = [p.price for p in known if p.kind == "HIGH"]
    lows = [p.price for p in known if p.kind == "LOW"]
    if len(highs) < 2 or len(lows) < 2 or not (highs[-1] > highs[-2] and lows[-1] > lows[-2]):
        return False
    if mode == "trend":
        return True
    run = 1
    for a, b in zip(reversed(highs[:-1]), reversed(highs[1:]), strict=True):
        if b > a:
            run += 1
        else:
            break
    return run - 1 < 3  # higher highs made in the current run


def trades(small: pd.DataFrame, big: pd.DataFrame, sign: int, x: float, early: bool, ctx: str) -> list[float]:
    hi, lo, close, piv = pivots(small, sign)
    _, _, _, bpiv = pivots(big, sign)
    bconf = np.array([np.datetime64(pd.Timestamp(p.confirm_at).tz_convert(None)) for p in bpiv])
    out: list[float] = []
    for k in range(1, len(piv)):
        h, low = piv[k], piv[k - 1]
        if h.kind != "HIGH" or low.kind != "LOW" or h.price <= low.price:
            continue
        leg = h.price - low.price
        line = low.price + x * leg
        entry = line + (0.10 * leg if early else 0.0)
        stop = line - BUF if early else (low.price + 0.236 * leg if x >= 0.618 else low.price) - BUF
        target = low.price + 1.618 * leg - BUF
        r = (target - entry - SPREAD) / (entry - stop)
        if r < 2.0 or entry >= h.price:
            continue
        start = h.confirm_pos
        if start + 1 >= len(small) or not context_ok(bpiv, bconf, small.index[start], ctx):
            continue
        filled = None
        for b in range(start + 1, min(start + 1 + FILL_BARS, len(small))):
            if close[b - 1] <= entry and b == start + 1:
                break  # price already under the line when the leg is fixed - no limit above price
            if lo[b] <= entry:
                filled = b
                break
            if hi[b] > h.price:
                break  # a new high first: the leg goes on without a pullback
        if filled is None:
            continue
        res = None
        for b in range(filled, len(small)):
            if lo[b] <= stop:
                res = -(entry - stop + SPREAD) / (entry - stop)
                break
            if hi[b] >= target:
                res = r
                break
        if res is not None:
            out.append(res)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", default="M5")
    ap.add_argument("--big", default="M15")
    ap.add_argument("--from", dest="first", default="2025-10-06")
    ap.add_argument("--to", dest="last", default="2026-10-28")
    a = ap.parse_args()
    small = frame(a.small)[a.first : a.last]
    big = frame(a.big)[a.first : a.last]
    print(f"continuation on {a.small}, context {a.big}, {a.first}..{a.last}  (n  won%  R/trade)")
    for x in (0.382, 0.618):
        for early in (False, True):
            for ctx in ("none", "trend", "trend<3"):
                rr = np.array(trades(small, big, 1, x, early, ctx) + trades(small, big, -1, x, early, ctx))
                label = f"line {x}  {'10% early, stop at line' if early else 'at the line'}  context {ctx}"
                s = f"{len(rr):>4} {100 * (rr > 0).mean():>5.1f} {rr.mean():>+7.3f}" if len(rr) else "   0"
                print(f"{label:<55} {s}")


if __name__ == "__main__":
    main()
