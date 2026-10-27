# ruff: noqa: E501
"""TR1 source events from ticks for RETEST-CONTINUATION V1 (fixed 2026-10-22, DEBUG_2026-10-22.md bugs B5/B7/B8).

The earlier historical cohorts took their TR1 source trades from the 3-year walk-forward's M1-OHLC approximation
(``walkforward.m1_fill`` / ``simulate_m1_exit``) and decided "stopped before +1R" from M1 bars touching -1R. TR1's
frozen rule fills on the first raw quote and runs the SPLIT exit on ordered bid/ask quotes, so this module reuses
TR1's own tick path (``frozen_round.generate_entries`` / ``generate_exits``) unchanged and classifies eligibility
from that tick result: SPLIT exit reason STOP with no +1R partial (the partial is booked on the first executable
+1R touch, so "no partial" is exactly "stopped before its first +1R touch").
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TR1_DIR = REPO / "research" / "2026-10-20-trend-runner"
if str(TR1_DIR) not in sys.path:
    sys.path.insert(0, str(TR1_DIR))

from frozen_round import generate_entries, generate_exits  # noqa: E402
from ticks import DEFAULT_ROOTS, refuse_exam  # noqa: E402
from tr1.boundaries import Period, PeriodName  # noqa: E402
from tr1.data import TickStore, load_m1  # noqa: E402

M1_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
M1_OLD_PATH = REPO / "data" / "history_old" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
RECENT_TICKS_FROM = pd.Timestamp("2025-10-01", tz="UTC")
MAX_SPAN = pd.Timedelta(days=21)
SETTLE = pd.Timedelta(days=3)  # memory guard: this module is for week-sized slices only


def tick_root_for(start: pd.Timestamp, end: pd.Timestamp) -> Path:
    """data/ticks holds 2025-10-01 onward; D:/taa-data holds 2021-09..2025-09. A slice must sit in one root."""
    if start >= RECENT_TICKS_FROM:
        return DEFAULT_ROOTS[0]
    if end <= RECENT_TICKS_FROM:
        return DEFAULT_ROOTS[1]
    raise ValueError("a source slice must not straddle 2025-10-01 (two tick roots)")


def m1_path_for(start: pd.Timestamp) -> Path:
    return M1_PATH if start >= pd.Timestamp("2023-09-01", tz="UTC") else M1_OLD_PATH


def stopped_before_plus1(complete: bool, reason: str, partial_taken: bool) -> bool:
    """V1 step 1: the SPLIT RUNNER ended on a stop (initial or trailed) before its first executable +1R touch.

    A time exit or a censored path is not eligible; a stop after the +1R partial is not eligible.
    """
    return bool(complete) and reason == "STOP" and not bool(partial_taken)


def source_trades(start: pd.Timestamp, end: pd.Timestamp, *, settle: pd.Timedelta = SETTLE):
    """TR1 entries anchored in [start, end) with their tick SPLIT result and V1 eligibility.

    Returns (entries_with_split, m1) where m1 covers a 50-day warm-up through end + settle.
    """
    if end <= start or end - start > MAX_SPAN:
        raise ValueError("source slice must be non-empty and at most 21 days")
    data_end = end + settle
    refuse_exam(start - pd.Timedelta(days=50), data_end)
    period = Period(PeriodName.P1, start, data_end)
    m1 = load_m1(m1_path_for(start), period, warmup_start=start - pd.Timedelta(days=50))
    store = TickStore(tick_root_for(start, data_end), period, cache_days=2)
    entries = generate_entries(period, m1, store)
    if entries.empty:
        return entries, m1
    entries = entries.loc[pd.DatetimeIndex(entries["anchor"]) < end].reset_index(drop=True)
    exits = generate_exits(period, m1, store, entries)
    split = exits.loc[exits["family"].eq("SPLIT")].set_index("entry_id")
    keep = [
        "complete",
        "exit_time",
        "exit_price",
        "reason",
        "r",
        "holding_minutes",
        "partial_taken",
        "graduated",
    ]
    out = entries.join(split[keep].add_prefix("split_"))
    out["runner_stopped_before_plus1"] = [
        stopped_before_plus1(c, r, p)
        for c, r, p in zip(
            out["split_complete"], out["split_reason"], out["split_partial_taken"], strict=True
        )
    ]
    return out, m1
