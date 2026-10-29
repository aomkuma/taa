"""Entering before the intended Fibo line, with a stop just beyond it - the owner's idea, 2026-10-29.

Uses ``fib_high.trades``; the 100 % follows the depth measured on M5 / M15 (61.8 % with the high the fall
began from, 23.6 % with the latest high, 38.2 % both). Target 161 %, at least 2R, both sides, 3-5 legs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fib_high import trades
from walk import frame

HIGH = {0.236: ("latest",), 0.382: ("latest", "start"), 0.618: ("start",)}


def line(rows: list[dict[str, object]]) -> str:
    if not rows:
        return f"{0:>4} {'-':>5} {'-':>7}"
    rr = np.array([float(t["r"]) for t in rows])  # type: ignore[arg-type]
    return f"{len(rows):>4} {100 * (rr > 0).mean():>5.1f} {rr.mean():>+7.3f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="M5")
    ap.add_argument("--from", dest="first", default="2025-10-06")
    ap.add_argument("--to", dest="last", default="2026-10-28")
    a = ap.parse_args()
    df = frame(a.tf)[a.first : a.last]
    print(f"{a.tf} {a.first}..{a.last}  (n  won%  R/trade)")
    for x, highs in HIGH.items():
        for h in highs:
            for before, stop_mode in [
                (0.0, "owner"),
                (0.05, "line_usd"),
                (0.10, "line_usd"),
                (0.15, "line_usd"),
                (0.05, "line_pct"),
                (0.10, "line_pct"),
                (0.15, "line_pct"),
                (0.10, "owner"),
            ]:
                rows = trades(df, 1, h, x, 1.618, 3, 5, False, before, stop_mode)
                rows += trades(df, -1, h, x, 1.618, 3, 5, False, before, stop_mode)
                label = (
                    "at the line, owner's stop" if before == 0 else f"+{before:.0%} early, stop {stop_mode}"
                )
                print(f"line {x:<5} {h:<6} {label:<30} {line(rows)}")


if __name__ == "__main__":
    main()
