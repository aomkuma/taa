"""Frozen RETEST-CONTINUATION V1 simulator; prospective research only."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

COLLECTION_START = pd.Timestamp("2026-10-21T00:00:00Z")
POINT = 0.01
MAX_WAIT = pd.Timedelta(hours=8)
MAX_HOLD = pd.Timedelta(hours=8)
PRICE_COLUMNS = ("open", "high", "low", "close", "spread")


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


def _m5_bars(m1: pd.DataFrame, side: int) -> pd.DataFrame:
    """Aggregate complete M5 candles on the relevant executable side."""
    offset = m1["spread"] * POINT if side < 0 else 0.0
    executable = pd.DataFrame(index=m1.index)
    for col in ("open", "high", "low", "close"):
        executable[col] = m1[col] + offset
    grouped = executable.groupby(executable.index.floor("5min"), sort=True)
    m5 = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        count=("close", "size"),
    )
    m5["close_time"] = m5.index + pd.Timedelta(minutes=5)
    m5 = m5.loc[m5["count"].eq(5)].copy()
    previous_close = m5["close"].shift(1)
    true_range = pd.concat(
        [m5["high"] - m5["low"], (m5["high"] - previous_close).abs(), (m5["low"] - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    m5["atr14"] = true_range.rolling(14, min_periods=14).mean()
    return m5


def _stop_touched(side: int, bar: pd.Series, stop: float) -> tuple[bool, float, str]:
    """Return (touched, fill, reason) using executable OHLC and adverse gap fills."""
    if side > 0:
        if float(bar["open"]) <= stop:
            return True, float(bar["open"]), "STOP_GAP"
        if float(bar["low"]) <= stop:
            return True, stop, "STOP"
    else:
        ask_open = float(bar["open"]) + float(bar["spread"]) * POINT
        ask_high = float(bar["high"]) + float(bar["spread"]) * POINT
        if ask_open >= stop:
            return True, ask_open, "STOP_GAP"
        if ask_high >= stop:
            return True, stop, "STOP"
    return False, np.nan, ""


def _tighten_stop(side: int, current: float, candidate: float) -> float:
    """Move a protective stop only toward price, never away from it."""
    return max(current, candidate) if side > 0 else min(current, candidate)


def _confirmed_pivots(
    m5: pd.DataFrame, side: int, entry_spread: float
) -> list[tuple[pd.Timestamp, pd.Timestamp, float]]:
    """(available time, pivot time, buffered stop) for radius-1 structure."""
    rows: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []
    for pivot in range(1, len(m5) - 1):
        price = float(m5["low"].iloc[pivot] if side > 0 else m5["high"].iloc[pivot])
        left = float(m5["low"].iloc[pivot - 1] if side > 0 else m5["high"].iloc[pivot - 1])
        right = float(m5["low"].iloc[pivot + 1] if side > 0 else m5["high"].iloc[pivot + 1])
        is_pivot = price <= left and price <= right if side > 0 else price >= left and price >= right
        atr = float(m5["atr14"].iloc[pivot + 1])
        if not is_pivot or not np.isfinite(atr) or atr <= 0:
            continue
        buffer = max(entry_spread, 0.10 * atr)
        stop = price - buffer if side > 0 else price + buffer
        avail = pd.Timestamp(m5["close_time"].iloc[pivot + 1])
        rows.append((avail, pd.Timestamp(m5.index[pivot]), float(stop)))
    return sorted(rows)


def _simulate(event: Mapping[str, object], m1: pd.DataFrame, *, historical: bool) -> dict[str, object]:
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
    stop_time = _utc(event["stop_time_utc"], "stop_time_utc")
    if not historical and stop_time < COLLECTION_START:
        raise ValueError("source stop predates prospective collection boundary")
    side = int(event["side"])
    if side not in (-1, 1):
        raise ValueError("side must be -1 or +1")
    if not bool(event["runner_stopped_before_plus1"]):
        return {"trade_key": str(event["trade_key"]), "status": "INELIGIBLE_SOURCE"}
    original_entry, original_stop = float(event["entry"]), float(event["stop"])
    if not np.isfinite([original_entry, original_stop]).all() or (original_entry - original_stop) * side <= 0:
        raise ValueError("original entry/stop do not define positive risk in the trade direction")
    if len(m1) == 0:
        return {"trade_key": str(event["trade_key"]), "status": "NO_BARS"}

    m5 = _m5_bars(m1, side)
    if m5.empty:
        return {"trade_key": str(event["trade_key"]), "status": "NO_COMPLETE_M5"}
    end = stop_time + MAX_WAIT
    after_stop = m5.loc[(m5["close_time"] > stop_time) & (m5["close_time"] <= end)]
    reclaim_mask = after_stop["close"] > original_entry if side > 0 else after_stop["close"] < original_entry
    reclaim_rows = after_stop.loc[reclaim_mask]
    if reclaim_rows.empty:
        status = "NO_RECLAIM" if m1.index.max() >= end else "PENDING_RECLAIM_HORIZON"
        return {"trade_key": str(event["trade_key"]), "status": status}
    reclaim_pos = m5.index.get_loc(reclaim_rows.index[0])
    reclaim_time = pd.Timestamp(m5["close_time"].iloc[reclaim_pos])

    retest_pos: int | None = None
    retest = None
    for pos in range(reclaim_pos + 1, min(reclaim_pos + 7, len(m5))):
        row = m5.iloc[pos]
        touched = float(row["low"]) <= original_entry if side > 0 else float(row["high"]) >= original_entry
        held = float(row["close"]) >= original_entry if side > 0 else float(row["close"]) <= original_entry
        if touched and held and row["close_time"] <= end:
            retest_pos, retest = pos, row
            break
    if retest is None or retest_pos is None:
        sixth_bar = reclaim_pos + 6
        if sixth_bar < len(m5) and pd.Timestamp(m5["close_time"].iloc[sixth_bar]) <= end:
            window_end = pd.Timestamp(m5["close_time"].iloc[sixth_bar])
        else:
            window_end = end
        status = "NO_RETEST" if m1.index.max() >= window_end else "PENDING_RETEST_WINDOW"
        return {"trade_key": str(event["trade_key"]), "status": status}
    atr = float(retest["atr14"])
    if not np.isfinite(atr) or atr <= 0:
        return {"trade_key": str(event["trade_key"]), "status": "NO_ATR"}
    source_spread = float(event["spread"])
    if not np.isfinite(source_spread) or source_spread < 0:
        raise ValueError("source spread must be finite and non-negative")
    buffer = max(source_spread, 0.10 * atr)
    initial_stop = float(retest["low"] - buffer if side > 0 else retest["high"] + buffer)

    confirm_pos: int | None = None
    for pos in range(retest_pos + 1, min(retest_pos + 3, len(m5))):
        row = m5.iloc[pos]
        between = m5.iloc[retest_pos + 1 : pos + 1]
        breached = any(_m5_stop_breached(r, side, initial_stop) for _, r in between.iterrows())
        close_break = (
            float(row["close"]) > float(retest["high"])
            if side > 0
            else float(row["close"]) < float(retest["low"])
        )
        if breached:
            return {"trade_key": str(event["trade_key"]), "status": "STRUCTURE_INVALIDATED"}
        if close_break:
            confirm_pos = pos
            break
    if confirm_pos is None:
        confirmation_end = m5["close_time"].iloc[min(retest_pos + 2, len(m5) - 1)]
        available = len(m5) > retest_pos + 2 and m1.index.max() >= confirmation_end
        status = "NO_CONTINUATION" if available else "PENDING_CONFIRMATION_WINDOW"
        return {"trade_key": str(event["trade_key"]), "status": status}
    confirm_time = pd.Timestamp(m5["close_time"].iloc[confirm_pos])
    if confirm_time > end:
        return {"trade_key": str(event["trade_key"]), "status": "EXPIRED"}
    entry_loc = int(m1.index.searchsorted(confirm_time, side="left"))
    if entry_loc >= len(m1):
        return {"trade_key": str(event["trade_key"]), "status": "PENDING_ENTRY_BAR"}
    entry_time = pd.Timestamp(m1.index[entry_loc])
    if entry_time < confirm_time or entry_time > confirm_time + pd.Timedelta(minutes=1):
        return {"trade_key": str(event["trade_key"]), "status": "PENDING_ENTRY_BAR"}
    entry_bar = m1.iloc[entry_loc]
    spread = float(entry_bar["spread"]) * POINT
    entry = float(entry_bar["open"] + spread if side > 0 else entry_bar["open"])
    if (entry - initial_stop) * side <= 0:
        return {"trade_key": str(event["trade_key"]), "status": "ENTRY_THROUGH_STOP"}
    risk = (entry - initial_stop) * side
    deadline = entry_time + MAX_HOLD
    deadline_loc = int(m1.index.searchsorted(deadline, side="left"))
    if deadline_loc >= len(m1):
        return {
            "trade_key": str(event["trade_key"]),
            "status": "PENDING_EXIT_HORIZON",
            "entry_time_utc": entry_time.isoformat(),
            "entry": entry,
            "initial_stop": initial_stop,
            "initial_risk": risk,
            "reclaim_time_utc": reclaim_time.isoformat(),
            "retest_time_utc": pd.Timestamp(retest["close_time"]).isoformat(),
            "confirmation_time_utc": confirm_time.isoformat(),
        }
    path = m1.iloc[entry_loc : deadline_loc + 1]

    pivots = _confirmed_pivots(m5, side, spread)
    pivot_idx = 0
    active_stop = initial_stop
    mfe = 0.0
    mae = 0.0
    for at, bar in path.iterrows():
        while pivot_idx < len(pivots) and pivots[pivot_idx][0] <= at:
            avail, pivot_time, candidate_stop = pivots[pivot_idx]
            pivot_idx += 1
            if pivot_time < entry_time or avail <= confirm_time:
                continue
            active_stop = _tighten_stop(side, active_stop, candidate_stop)
        touched, fill, reason = _stop_touched(side, bar, active_stop)
        long_high, long_low = float(bar["high"]), float(bar["low"])
        if side < 0:
            long_high += float(bar["spread"]) * POINT
            long_low += float(bar["spread"]) * POINT
        favorable = long_high if side > 0 else long_low
        adverse = long_low if side > 0 else long_high
        mfe = max(mfe, (favorable - entry) * side / risk)
        mae = min(mae, (adverse - entry) * side / risk)
        if touched:
            return {
                "trade_key": str(event["trade_key"]),
                "status": "COMPLETE",
                "reason": reason,
                "entry_time_utc": entry_time.isoformat(),
                "exit_time_utc": at.isoformat(),
                "reclaim_time_utc": reclaim_time.isoformat(),
                "retest_time_utc": pd.Timestamp(retest["close_time"]).isoformat(),
                "confirmation_time_utc": confirm_time.isoformat(),
                "entry": entry,
                "exit": fill,
                "initial_stop": initial_stop,
                "final_stop": active_stop,
                "initial_risk": risk,
                "r": (fill - entry) * side / risk,
                "holding_minutes": (at - entry_time).total_seconds() / 60,
                "mfe_r": mfe,
                "mae_r": mae,
            }
    # First M1 open at/after the 8-hour deadline; path contains that bar.
    at = pd.Timestamp(path.index[-1])
    bar = path.iloc[-1]
    quote = float(bar["open"] if side > 0 else bar["open"] + float(bar["spread"]) * POINT)
    return {
        "trade_key": str(event["trade_key"]),
        "status": "COMPLETE",
        "reason": "TIME",
        "entry_time_utc": entry_time.isoformat(),
        "exit_time_utc": at.isoformat(),
        "reclaim_time_utc": reclaim_time.isoformat(),
        "retest_time_utc": pd.Timestamp(retest["close_time"]).isoformat(),
        "confirmation_time_utc": confirm_time.isoformat(),
        "entry": entry,
        "exit": quote,
        "initial_stop": initial_stop,
        "final_stop": active_stop,
        "initial_risk": risk,
        "r": (quote - entry) * side / risk,
        "holding_minutes": (at - entry_time).total_seconds() / 60,
        "mfe_r": mfe,
        "mae_r": mae,
    }


def simulate_candidate(event: Mapping[str, object], m1: pd.DataFrame) -> dict[str, object]:
    """Evaluate a prospective source-stop event; refuses all pre-boundary data."""
    return _simulate(event, m1, historical=False)


def simulate_historical_diagnostic(
    event: Mapping[str, object],
    m1: pd.DataFrame,
    *,
    exam_start: pd.Timestamp,
    earliest_data: pd.Timestamp,
) -> dict[str, object]:
    """Explicitly isolated replay for pre-exam diagnostic research only."""
    exam_start = _utc(exam_start, "exam_start")
    earliest_data = _utc(earliest_data, "earliest_data")
    stop_time = _utc(event.get("stop_time_utc"), "stop_time_utc")
    if stop_time >= exam_start:
        raise ValueError("historical diagnostic refuses locked exam/post-exam events")
    if len(m1) and (m1.index.min() < earliest_data or m1.index.max() >= exam_start):
        raise ValueError("historical bars cross the declared diagnostic boundary")
    return _simulate(event, m1, historical=True)


def _m5_stop_breached(bar: pd.Series, side: int, stop: float) -> bool:
    return float(bar["low"]) <= stop if side > 0 else float(bar["high"]) >= stop
