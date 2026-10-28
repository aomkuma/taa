"""Task D2 by the clock (the owner, 2026-10-20 12:05 Thai: the opens run in their first 30 - 60 minutes; New York can run
up to 4 hours after its open, often after 1 - 2 choppy hours): D2's core entry (trigger 2 U, stop 8 U, +0.5 USD) at the
08:30, 09:30 (the NY open) and 10:00 New York minutes; (a) held to + 30 .. + 240 minutes with its stop; (b) the move in
the trade's direction per 30-minute bucket (no stop), in R, and its size in USD. Readings (DEV_LOG.md).

    .venv/Scripts/python research/2026-10-18-moments/agents/dev/d2_buckets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import d2_straddle as D2  # noqa: E402
import p2_trades as P2  # noqa: E402
from sweep_detector import EXAM_START, LEARN_START, ExamPeriodError  # noqa: E402

NS_MIN = 60 * 10**9
HOLDS = tuple(range(30, 241, 30))
MINUTES = ((8, 30), (9, 30), (10, 0))
OPEN_OFFSET = {"08:30": -60, "09:30": 0, "10:00": 30}  # minutes from the NY open


def ny_minutes(start: pd.Timestamp, end: pd.Timestamp, minutes=MINUTES) -> list[tuple[int, str]]:
    """Every weekday's New York minutes (summer / winter time) in [start, end), UTC ns, sorted."""
    if end > EXAM_START:
        raise ExamPeriodError("the minutes may not reach the exam period")
    out = []
    for d in pd.date_range(start.tz_convert("America/New_York").date(), end.tz_convert("America/New_York").date(), freq="D"):
        if d.weekday() >= 5:
            continue
        for hh, mm in minutes:
            t = pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hh, minute=mm, tz="America/New_York").tz_convert("UTC")
            if start <= t < end:
                out.append((t.value, f"{hh:02d}:{mm:02d}"))
    return sorted(out)


def mid_at(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, at: int) -> float:
    """The last tick's mid at / before `at` (NaN when none)."""
    k = int(np.searchsorted(t, at, side="right")) - 1
    return float((bid[k] + ask[k]) / 2) if k >= 0 else np.nan


def crosses_gap(t: np.ndarray, a: int, b: int) -> bool:
    """A gap of more than 30 minutes in the ticks within [a, b], or no tick at / after b (the data's end)."""
    i = int(np.searchsorted(t, a, side="right")) - 1
    j = int(np.searchsorted(t, b, side="left"))
    if i < 0 or j >= len(t):
        return True
    return bool(np.any(np.diff(t[i:j + 1]) > D2.GAP))


def bucket_moves(t: np.ndarray, bid: np.ndarray, ask: np.ndarray, t0: int, x: dict) -> list[tuple[float, float]]:
    """(the move in the trade's direction in R, its size in USD) for buckets 1 .. 8; NaN where the bucket is left out."""
    out = []
    for b in range(1, len(HOLDS) + 1):
        a_t = int(x["entry_t"]) if b == 1 else t0 + (b - 1) * 30 * NS_MIN
        e_t = t0 + b * 30 * NS_MIN
        if crosses_gap(t, a_t, e_t):
            out.append((np.nan, np.nan))
            continue
        d = mid_at(t, bid, ask, e_t) - mid_at(t, bid, ask, a_t)
        out.append((x["side"] * d / x["risk"], abs(d)))
    return out


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    from m15_trades import part_of  # noqa: PLC0415

    ticks = P2.Ticks()
    held, moves = [], []
    for t0, ny in ny_minutes(LEARN_START, EXAM_START):
        t, bid, ask = ticks.span(t0)
        x0 = D2.straddle(t, bid, ask, t0, 2.0, 8.0, HOLDS[0], 0.5)
        if x0 is not None:
            for hold in HOLDS:
                x = D2.straddle(t, bid, ask, t0, 2.0, 8.0, hold, 0.5)
                held.append(dict(t0=t0, ny=ny, hold=hold, **x))
            for b, (r, size) in enumerate(bucket_moves(t, bid, ask, t0, x0), 1):
                moves.append(dict(t0=t0, ny=ny, bucket=b, side=x0["side"], R_move=r, usd_size=size))
        if len(ticks.spans) > 2:
            ticks.days.clear()
            ticks.spans.clear()
    H, M = pd.DataFrame(held), pd.DataFrame(moves)
    for X in (H, M):
        X["part"] = part_of(pd.to_datetime(X.t0, utc=True))
    if (H.exit_t >= EXAM_START.value).any():
        raise ExamPeriodError("a trade reached the exam")
    return H, M


def main() -> None:
    H, M = run()
    H.to_parquet(HERE / "d2_held.parquet")
    M.to_parquet(HERE / "d2_buckets.parquet")
    pd.set_option("display.width", 220)
    print("(a) held to the minute + 30 .. 240 with the 8 U stop (+0.5 USD): R per part (n, win %)")
    for ny in ("all", "08:30", "09:30", "10:00"):
        X = H if ny == "all" else H[H.ny == ny]
        print(f"  {ny}:")
        for p in ("P1", "P2"):
            cells = []
            for hold in HOLDS:
                G = X[(X.part == p) & (X.hold == hold)]
                r = G.R.to_numpy(float)
                half = 1.96 * r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan
                cells.append(f"{hold:3d}m {r.mean():+.3f} (+-{half:.2f}, {len(r)}, {np.mean(r > 0):.2f})")
            print(f"    {p}: " + " | ".join(cells))
    print("\n(b) the move in the trade's direction per 30-minute bucket (no stop), mean R / share in the trade's way / mean "
          "size USD (n)")
    for ny in ("all", "08:30", "09:30", "10:00"):
        X = M if ny == "all" else M[M.ny == ny]
        off = "" if ny == "all" else f" (bucket 1 starts at the NY open {OPEN_OFFSET[ny]:+d} min)"
        print(f"  {ny}{off}:")
        for p in ("P1", "P2"):
            cells = []
            for b in range(1, len(HOLDS) + 1):
                G = X[(X.part == p) & (X.bucket == b)].dropna(subset=["R_move"])
                cells.append(f"b{b} {G.R_move.mean():+.3f}/{np.mean(G.R_move > 0):.2f}/{G.usd_size.mean():5.1f} ({len(G)})")
            print(f"    {p}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
