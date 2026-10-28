# ruff: noqa: E501
"""RETEST-CONTINUATION V1 simulator (PLAN.md, "Frozen RETEST-CONTINUATION V1 entry rule"), fixed 2026-10-22.

The signal steps (reclaim, retest, structural invalidation, continuation) read completed M5 bars built from broker
M1 bars. Everything that is a price the account would get - the entry, the stops, the trail, the 8-hour exit, MFE and
MAE - is read from the bid/ask ticks (bid marks/stops a BUY, ask a SELL; equal-time quotes keep file order).
DEBUG_2026-10-22.md lists every change against the backup in ``_original_2026-10-22/`` and the reason for it.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "2026-10-18-moments" / "agents" / "precursors"))
from foundation import atr as mt5_atr
from ticks import refuse_exam

COLLECTION_START = pd.Timestamp("2026-10-21T00:00:00Z")
POINT = 0.01
MAX_WAIT = pd.Timedelta(hours=8)
MAX_HOLD = pd.Timedelta(hours=8)
RETEST_BARS = 6
CONFIRM_BARS = 2
ENTRY_QUOTE_WINDOW = pd.Timedelta(minutes=2)
PRICE_COLUMNS = ("open", "high", "low", "close", "spread")


class Quotes(Protocol):
    """The tick interface the simulator needs (``ticks.TickSource`` or a test double)."""

    def span(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame: ...

    def iter_from(self, start: pd.Timestamp, *, max_days: int = 10) -> Iterator[pd.DataFrame]: ...


def _utc(value: object, field: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None or str(ts.tz) != "UTC":
        raise ValueError(f"{field} must be timezone-aware UTC")
    return ts


def _validate_bars(m1: pd.DataFrame, *, historical: bool = False) -> None:
    if not isinstance(m1.index, pd.DatetimeIndex) or m1.index.tz is None or str(m1.index.tz) != "UTC":
        raise ValueError("M1 index must be timezone-aware UTC")
    if m1.index.has_duplicates or not m1.index.is_monotonic_increasing:
        raise ValueError("M1 timestamps must be unique and increasing")
    if (m1.index.second != 0).any() or (m1.index.microsecond != 0).any():
        raise ValueError("M1 timestamps must be minute opens")
    if not historical and len(m1) and m1.index.min() < COLLECTION_START:
        raise ValueError("candidate observer refuses pre-boundary M1 rows")
    if not set(PRICE_COLUMNS).issubset(m1.columns):
        raise ValueError(f"M1 bars must contain {PRICE_COLUMNS}")
    values = m1[list(PRICE_COLUMNS)].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("M1 bars contain non-finite price/spread")
    if (m1["spread"] < 0).any() or (m1["high"] < m1["low"]).any():
        raise ValueError("invalid spread or OHLC range")


def m5_bars(m1: pd.DataFrame, side: int) -> pd.DataFrame:
    """Completed M5 signal candles; a bar is complete at its clock end (TR1 FOUNDATION convention).

    BUY bars are the broker's bid bars. SELL bars keep the original V1 choice (ambiguity A1 in DEBUG_2026-10-22.md):
    each M1 price is lifted by that minute's recorded spread. ATR(14) is MT5's ATR.mq5 (first value at bar 14).
    """
    offset = m1["spread"] * POINT if side < 0 else 0.0
    executable = pd.DataFrame(index=m1.index)
    for col in ("open", "high", "low", "close"):
        executable[col] = m1[col] + offset
    grouped = executable.groupby(executable.index.floor("5min"), sort=True)
    m5 = grouped.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")
    )
    m5["close_time"] = m5.index + pd.Timedelta(minutes=5)
    data_end = m1.index.max() + pd.Timedelta(minutes=1) if len(m1) else pd.Timestamp.min.tz_localize("UTC")
    m5 = m5.loc[m5["close_time"] <= data_end].copy()  # the forming bar is never a signal
    m5["atr14"] = mt5_atr(
        m5["high"].to_numpy(float), m5["low"].to_numpy(float), m5["close"].to_numpy(float), 14
    )
    return m5


def _tighten_stop(side: int, current: float, candidate: float) -> float:
    """Move a protective stop only toward price, never away from it."""
    return max(current, candidate) if side > 0 else min(current, candidate)


def confirmed_pivots(
    m5: pd.DataFrame, side: int, entry_spread: float, formed_from: pd.Timestamp
) -> list[tuple[pd.Timestamp, pd.Timestamp, float]]:
    """(available time, pivot bar open, buffered stop) of radius-1 M5 swing pivots formed at/after ``formed_from``.

    A BUY trails pivot lows (low <= both neighbours), a SELL pivot highs. The pivot is known when its right-hand bar
    closes; its buffer is max(entry spread, 0.10 x ATR(14) of that confirming bar).
    """
    rows: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []
    low = m5["low"].to_numpy(float)
    high = m5["high"].to_numpy(float)
    atr = m5["atr14"].to_numpy(float)
    for pivot in range(1, len(m5) - 1):
        if m5.index[pivot] < formed_from:
            continue
        if side > 0:
            price = low[pivot]
            is_pivot = price <= low[pivot - 1] and price <= low[pivot + 1]
        else:
            price = high[pivot]
            is_pivot = price >= high[pivot - 1] and price >= high[pivot + 1]
        value = atr[pivot + 1]
        if not is_pivot or not np.isfinite(value) or value <= 0:
            continue
        buffer = max(entry_spread, 0.10 * value)
        stop = price - buffer if side > 0 else price + buffer
        rows.append(
            (pd.Timestamp(m5["close_time"].iloc[pivot + 1]), pd.Timestamp(m5.index[pivot]), float(stop))
        )
    return sorted(rows)


def find_signal(event: Mapping[str, object], m1: pd.DataFrame) -> dict[str, object]:
    """Steps 1-5 up to the confirmation close: reclaim, retest, provisional stop, invalidation, continuation."""
    key = str(event["trade_key"])
    stop_time = _utc(event["stop_time_utc"], "stop_time_utc")
    side = int(event["side"])
    original_entry = float(event["entry"])
    m5 = m5_bars(m1, side)
    if m5.empty:
        return {"trade_key": key, "status": "NO_COMPLETE_M5"}
    data_end = m1.index.max() + pd.Timedelta(minutes=1)
    end = stop_time + MAX_WAIT
    # Step 2: the first completed M5 close beyond E0 strictly after the stop, within 8 hours of the stop.
    after_stop = m5.loc[(m5["close_time"] > stop_time) & (m5["close_time"] <= end)]
    reclaim_mask = after_stop["close"] > original_entry if side > 0 else after_stop["close"] < original_entry
    reclaim_rows = after_stop.loc[reclaim_mask]
    if reclaim_rows.empty:
        return {"trade_key": key, "status": "NO_RECLAIM" if data_end >= end else "PENDING_RECLAIM_HORIZON"}
    reclaim_pos = int(m5.index.get_loc(reclaim_rows.index[0]))
    seen = {"reclaim_time_utc": pd.Timestamp(m5["close_time"].iloc[reclaim_pos]).isoformat()}

    # Step 3: among the next six completed bars, the first that touches E0 and closes on the reclaimed side.
    retest_pos: int | None = None
    for pos in range(reclaim_pos + 1, min(reclaim_pos + 1 + RETEST_BARS, len(m5))):
        row = m5.iloc[pos]
        touched = row["low"] <= original_entry if side > 0 else row["high"] >= original_entry
        held = row["close"] >= original_entry if side > 0 else row["close"] <= original_entry
        if touched and held:
            retest_pos = pos
            break
    if retest_pos is None:
        complete = len(m5) >= reclaim_pos + 1 + RETEST_BARS
        return {"trade_key": key, "status": "NO_RETEST" if complete else "PENDING_RETEST_WINDOW", **seen}
    retest = m5.iloc[retest_pos]
    seen["retest_time_utc"] = pd.Timestamp(retest["close_time"]).isoformat()

    # Step 4: provisional stop from the retest extreme; B = max(original entry spread, 0.10 x M5 ATR(14)).
    atr = float(retest["atr14"])
    if not np.isfinite(atr) or atr <= 0:
        return {"trade_key": key, "status": "NO_ATR", **seen}
    source_spread = float(event["spread"])
    if not np.isfinite(source_spread) or source_spread < 0:
        raise ValueError("source spread must be finite and non-negative")
    buffer = max(source_spread, 0.10 * atr)
    provisional = float(retest["low"] - buffer if side > 0 else retest["high"] + buffer)

    # Step 5: within the next two bars, the first close beyond the retest bar's far extreme; a bar that breaches the
    # provisional stop (the confirmation bar included) cancels the event.
    confirm_pos: int | None = None
    for pos in range(retest_pos + 1, min(retest_pos + 1 + CONFIRM_BARS, len(m5))):
        row = m5.iloc[pos]
        breached = row["low"] <= provisional if side > 0 else row["high"] >= provisional
        if breached:
            return {"trade_key": key, "status": "STRUCTURE_INVALIDATED", **seen}
        if (row["close"] > retest["high"]) if side > 0 else (row["close"] < retest["low"]):
            confirm_pos = pos
            break
    if confirm_pos is None:
        complete = len(m5) >= retest_pos + 1 + CONFIRM_BARS
        status = "NO_CONTINUATION" if complete else "PENDING_CONFIRMATION_WINDOW"
        return {"trade_key": key, "status": status, **seen}
    return {
        "trade_key": key,
        "status": "SIGNAL",
        "side": side,
        "reclaim_time_utc": pd.Timestamp(m5["close_time"].iloc[reclaim_pos]),
        "retest_time_utc": pd.Timestamp(retest["close_time"]),
        "confirmation_time_utc": pd.Timestamp(m5["close_time"].iloc[confirm_pos]),
        "retest_high": float(retest["high"]),
        "retest_low": float(retest["low"]),
        "retest_atr": atr,
        "provisional_stop": provisional,
        "m5": m5,
    }


def _manage(
    side: int,
    entry: float,
    entry_time: pd.Timestamp,
    initial_stop: float,
    pivots: list[tuple[pd.Timestamp, pd.Timestamp, float]],
    chunks: Iterator[pd.DataFrame],
    bars_known_until: pd.Timestamp,
) -> dict[str, object]:
    """Steps 7-8 on ordered quotes: trail on confirmed pivots, stop first, then the 8-hour exit."""
    risk = (entry - initial_stop) * side
    deadline = entry_time + MAX_HOLD
    stop = initial_stop
    pivot_idx = 0
    mfe = mae = 0.0
    for chunk in chunks:
        times = pd.DatetimeIndex(chunk["time_utc"])
        mark = chunk["bid"].to_numpy(float) if side > 0 else chunk["ask"].to_numpy(float)
        for i in range(len(times)):
            t = times[i]
            if t > bars_known_until:
                # A pivot confirmed after the supplied bars could tighten the stop; never guess it.
                return {"status": "PENDING_M1_COVERAGE"}
            while pivot_idx < len(pivots) and pivots[pivot_idx][0] <= t:
                stop = _tighten_stop(side, stop, pivots[pivot_idx][2])
                pivot_idx += 1
            price = float(mark[i])
            r_now = (price - entry) * side / risk
            mfe, mae = max(mfe, r_now), min(mae, r_now)
            if (price <= stop) if side > 0 else (price >= stop):
                reason = "STOP" if stop == initial_stop else "TRAIL_STOP"
                return _done(reason, t, price, stop, entry, entry_time, risk, side, mfe, mae)
            if t >= deadline:
                return _done("TIME", t, price, stop, entry, entry_time, risk, side, mfe, mae)
    return {"status": "PENDING_EXIT_HORIZON"}


def _done(
    reason: str,
    t: pd.Timestamp,
    price: float,
    stop: float,
    entry: float,
    entry_time: pd.Timestamp,
    risk: float,
    side: int,
    mfe: float,
    mae: float,
) -> dict[str, object]:
    return {
        "status": "COMPLETE",
        "reason": reason,
        "exit_time_utc": pd.Timestamp(t),
        "exit": price,
        "final_stop": stop,
        "r": (price - entry) * side / risk,
        "holding_minutes": (pd.Timestamp(t) - entry_time).total_seconds() / 60.0,
        "mfe_r": mfe,
        "mae_r": mae,
    }


def _simulate(
    event: Mapping[str, object], m1: pd.DataFrame, quotes: Quotes, *, historical: bool, slippage: float = 0.0
) -> dict[str, object]:
    _validate_bars(m1, historical=historical)
    required = {
        "trade_key",
        "stop_time_utc",
        "side",
        "entry",
        "stop",
        "spread",
        "runner_stopped_before_plus1",
    }
    missing = required - set(event)
    if missing:
        raise ValueError(f"event missing fields: {sorted(missing)}")
    if slippage < 0:
        raise ValueError("slippage must be non-negative")
    key = str(event["trade_key"])
    stop_time = _utc(event["stop_time_utc"], "stop_time_utc")
    if not historical and stop_time < COLLECTION_START:
        raise ValueError("source stop predates prospective collection boundary")
    side = int(event["side"])
    if side not in (-1, 1):
        raise ValueError("side must be -1 or +1")
    if not bool(event["runner_stopped_before_plus1"]):
        return {"trade_key": key, "status": "INELIGIBLE_SOURCE"}
    original_entry, original_stop = float(event["entry"]), float(event["stop"])
    if not np.isfinite([original_entry, original_stop]).all() or (original_entry - original_stop) * side <= 0:
        raise ValueError("original entry/stop do not define positive risk in the trade direction")
    if len(m1) == 0:
        return {"trade_key": key, "status": "NO_BARS"}

    signal = find_signal(event, m1)
    if signal["status"] != "SIGNAL":
        return signal
    confirm_time = pd.Timestamp(signal["confirmation_time_utc"])
    times = {
        k: pd.Timestamp(signal[k]).isoformat()
        for k in ("reclaim_time_utc", "retest_time_utc", "confirmation_time_utc")
    }
    data_end = m1.index.max() + pd.Timedelta(minutes=1)

    # Step 5 entry: the first quote of the next M1 bar - ask for a BUY, bid for a SELL - plus optional slippage.
    window = quotes.span(confirm_time, confirm_time + ENTRY_QUOTE_WINDOW)
    window = window.loc[pd.DatetimeIndex(window["time_utc"]) < confirm_time + ENTRY_QUOTE_WINDOW]
    if window.empty:
        status = "NO_ENTRY_QUOTE" if data_end > confirm_time + ENTRY_QUOTE_WINDOW else "PENDING_ENTRY_BAR"
        return {"trade_key": key, "status": status, **times}
    first = window.iloc[0]
    entry_time = pd.Timestamp(first["time_utc"])
    entry_spread = float(first["ask"] - first["bid"])
    entry = float(first["ask"] + slippage) if side > 0 else float(first["bid"] - slippage)
    initial_stop = float(signal["provisional_stop"])
    if (entry - initial_stop) * side <= 0:
        return {"trade_key": key, "status": "ENTRY_THROUGH_STOP", **times}
    risk = (entry - initial_stop) * side

    pivots = confirmed_pivots(signal["m5"], side, entry_spread, formed_from=confirm_time)
    managed = _manage(
        side, entry, entry_time, initial_stop, pivots, quotes.iter_from(entry_time, max_days=10), data_end
    )
    base = {
        "trade_key": key,
        **times,
        "entry_time_utc": entry_time.isoformat(),
        "entry": entry,
        "entry_spread": entry_spread,
        "initial_stop": initial_stop,
        "initial_risk": risk,
        "retest_atr": float(signal["retest_atr"]),
    }
    if managed["status"] != "COMPLETE":
        return {**base, "status": managed["status"]}
    managed["exit_time_utc"] = pd.Timestamp(managed["exit_time_utc"]).isoformat()
    return {**base, **managed}


def simulate_candidate(event: Mapping[str, object], m1: pd.DataFrame, quotes: Quotes) -> dict[str, object]:
    """Evaluate a prospective source-stop event; refuses all pre-boundary data."""
    return _simulate(event, m1, quotes, historical=False)


def simulate_historical_diagnostic(
    event: Mapping[str, object],
    m1: pd.DataFrame,
    quotes: Quotes,
    *,
    exam_start: pd.Timestamp,
    earliest_data: pd.Timestamp,
    slippage: float = 0.0,
) -> dict[str, object]:
    """Isolated pre-exam replay; refuses any event or bar in or after the reserved exam."""
    exam_start = _utc(exam_start, "exam_start")
    earliest_data = _utc(earliest_data, "earliest_data")
    stop_time = _utc(event.get("stop_time_utc"), "stop_time_utc")
    if stop_time >= exam_start:
        raise ValueError("historical diagnostic refuses locked exam/post-exam events")
    if len(m1):
        if m1.index.min() < earliest_data or m1.index.max() >= exam_start:
            raise ValueError("historical bars cross the declared diagnostic boundary")
        refuse_exam(m1.index.min(), m1.index.max() + pd.Timedelta(minutes=1))
    return _simulate(event, m1, quotes, historical=True, slippage=slippage)
