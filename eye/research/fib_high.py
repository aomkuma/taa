"""Which high is 100 % of the owner's Fibo - the latest before the low, or the one the fall started from.

The owner, 2026-10-29: "research it and find me the answer". Both sides: a BUY after 3-5 legs down (each
fixed low lower than the one before) into L0, a SELL after 3-5 legs up (the mirror, by negating prices).

For each such bottom, from the bar its ZigZag low is fixed (closed bars only):
- the leg is drawn L0 (0 %) -> H (100 %), H = `latest` (the fixed high just before L0) or `start` (the
  highest fixed high of the descending run);
- entry: a limit at the entry level once a bar has traded above it after L0; withdrawn if the stop or the
  target trades first, or after FILL_BARS without a fill;
- stop: L0 - 0.5 (entry 0.618: the 0.236 level - 0.5); target: L0 + ext * (H - L0) - 0.5;
- the owner's 2R floor: no trade when R (net of the 0.30 spread) is under 2;
- held to stop or target; a bar touching both counts as the stop.
Divergence is not required here (the count alone); `--div` requires it on MACD or RSI at L0.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

from walk import frame, macd_mt5  # noqa: E402

from app.indicators.chart_read import zigzag_pivots  # noqa: E402
from app.indicators.momentum import rsi  # noqa: E402

SPREAD, BUF, FILL_BARS = 0.30, 0.50, 96


def trades(
    df: pd.DataFrame,
    sign: int,
    which: str,
    entry_x: float,
    ext: float,
    nmin: int,
    nmax: int,
    div: bool,
    before: float = 0.0,
    stop_mode: str = "owner",
) -> list[dict[str, object]]:
    """``before`` > 0: enter early at ``entry_x + before`` of the leg; ``stop_mode`` "owner" (beyond 0 %, or
    23.6 % for a 61.8 % entry), "line_usd" (the intended line - 0.5 USD) or "line_pct" (the line - 3 % of the
    leg) - the owner's idea of 2026-10-29, Claude's definitions."""
    hi = (df.high if sign > 0 else -df.low).to_numpy(np.float64)
    lo = (df.low if sign > 0 else -df.high).to_numpy(np.float64)
    close = (sign * df.close).to_numpy(np.float64)
    macd = (sign * macd_mt5(df.close)["main"]).to_numpy(np.float64)
    rs = (sign * rsi(df.close, 14) + (0.0 if sign > 0 else 100.0)).to_numpy(np.float64)
    piv = zigzag_pivots(hi, lo, 0.01, index=list(df.index), depth=12, deviation=5, backstep=3)
    out: list[dict[str, object]] = []
    for k, p in enumerate(piv):
        if p.kind != "LOW":
            continue
        # the descending run into L0: earlier lows each higher than the one after it
        lows = [p]
        j = k - 2
        while j >= 0 and piv[j].kind == "LOW" and piv[j].price > lows[-1].price:
            lows.append(piv[j])
            j -= 2
        n = len(lows)
        if not nmin <= n <= nmax or k < 1 or piv[k - 1].kind != "HIGH":
            continue
        if div:
            q = lows[1]
            if not (macd[p.pivot_pos] > macd[q.pivot_pos] or rs[p.pivot_pos] > rs[q.pivot_pos]):
                continue
        highs = [piv[i] for i in range(j + 1, k) if piv[i].kind == "HIGH"]
        h = piv[k - 1].price if which == "latest" else max(x.price for x in highs)
        l0, leg = p.price, h - p.price
        if leg <= 0:
            continue
        line = l0 + entry_x * leg
        entry = line + before * leg
        if stop_mode == "line_usd":
            stop = line - BUF
        elif stop_mode == "line_pct":
            stop = line - 0.03 * leg
        else:
            stop = (l0 + 0.236 * leg if entry_x >= 0.618 else l0) - BUF
        target = l0 + ext * leg - BUF
        r = (target - entry - SPREAD) / (entry - stop)
        if r < 2.0:
            continue
        start = p.confirm_pos  # the low is fixed here; nothing before is acted on
        if start + 1 >= len(df):
            continue
        # armed once a bar has closed above the entry level after the low is fixed (the bounce, and price
        # above the level - a plain limit below price); not armed if the stop or target trades first
        armed = None
        for b in range(start + 1, min(start + 1 + FILL_BARS, len(df))):
            if lo[b - 1] <= stop or hi[b - 1] >= target:
                break
            if close[b - 1] > entry:
                armed = b
                break
        if armed is None:
            continue
        filled = None
        for b in range(armed, min(armed + FILL_BARS, len(df))):
            if lo[b] <= stop or hi[b] >= target:
                break  # the idea failed or ran without us
            if lo[b] <= entry:
                filled = b
                break
        if filled is None:
            continue
        res = None
        for b in range(filled, len(df)):
            if lo[b] <= stop:
                res = -(entry - stop + SPREAD) / (entry - stop)
                break
            if hi[b] >= target:
                res = r
                break
        if res is None:
            continue  # still open at the end of the stored bars
        out.append(
            {
                "time": df.index[p.pivot_pos],
                "side": "BUY" if sign > 0 else "SELL",
                "n": n,
                "risk": entry - stop,
                "r": res,
                "same": abs(piv[k - 1].price - max(x.price for x in highs)) < 1e-9,
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="M15")
    ap.add_argument("--from", dest="first", default="2023-09-01")
    ap.add_argument("--to", dest="last", default="2026-10-28")
    ap.add_argument("--div", action="store_true")
    a = ap.parse_args()
    df = frame(a.tf)[a.first : a.last]
    print(f"{a.tf} {a.first}..{a.last} bars {len(df)} div={a.div}")
    print(f"{'entry':>6} {'ext':>5} {'H':>7} | {'all: n  win%  R/tr':>22} | {'differ: n  win%  R/tr':>28}")
    for entry_x in (0.236, 0.382, 0.618):
        for ext in (1.272, 1.618):
            for which in ("latest", "start"):
                rows = trades(df, 1, which, entry_x, ext, 3, 5, a.div) + trades(
                    df, -1, which, entry_x, ext, 3, 5, a.div
                )
                d = [t for t in rows if not t["same"]]

                def s(x: list[dict[str, object]]) -> str:
                    if not x:
                        return f"{0:>4} {'-':>5} {'-':>6}"
                    rr = np.array([float(t["r"]) for t in x])  # type: ignore[arg-type]
                    return f"{len(x):>4} {100 * (rr > 0).mean():>5.1f} {rr.mean():>+6.3f}"

                print(f"{entry_x:>6} {ext:>5} {which:>7} | {s(rows):>22} | {s(d):>34}")


if __name__ == "__main__":
    main()
