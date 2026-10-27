"""Independently replay every saved P1 opportunity from bars and raw quotes.

This verifier deliberately does not import ``tr1.opportunity`` or ``tr1.simulation``.
It repeats the rule in a second implementation so a shared helper cannot make the
producer and checker agree on the same mistake.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from tr1.boundaries import P1
from tr1.data import TickStore, load_m1

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
TICK_ROOT = REPO / "data" / "ticks" / "XAUUSD"
TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15}
DEADLINE_MINUTES = {"ASIA": 120, "LONDON": 120, "NY0830": 240}


class VerificationError(AssertionError):
    """An independently reconstructed value differs from the saved study."""


@dataclass(frozen=True)
class IndependentCandidate:
    reference: float
    h1_atr: float
    side: int
    impulse_decision: pd.Timestamp
    pivot_time: pd.Timestamp
    pivot_price: float
    pivot_available: pd.Timestamp
    impulse_span: float
    pullback_depth: float
    pullback_ratio: float
    continuation_level: float
    decision_time: pd.Timestamp
    entry_atr: float


def aggregate_independently(m1: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Build clock bars without using the production aggregation helper."""
    if minutes == 1:
        result = m1[["open", "high", "low", "close"]].copy()
    else:
        key = m1.index.floor(f"{minutes}min")
        grouped = m1.assign(_key=key).groupby("_key", sort=True)
        result = grouped.agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")
        )
    result["avail"] = result.index + pd.Timedelta(minutes=minutes)
    return result


def atr_independently(bars: pd.DataFrame, length: int = 14) -> np.ndarray:
    """Repeat MT5 ATR from its definition rather than importing the implementation."""
    high = bars["high"].to_numpy(float)
    low = bars["low"].to_numpy(float)
    close = bars["close"].to_numpy(float)
    result = np.full(len(bars), np.nan)
    tr = np.full(len(bars), np.nan)
    for index in range(1, len(bars)):
        tr[index] = max(high[index], close[index - 1]) - min(low[index], close[index - 1])
        if index >= length:
            result[index] = float(np.mean(tr[index - length + 1 : index + 1]))
    return result


def pivot_indices(bars: pd.DataFrame, kind: str) -> np.ndarray:
    """Return independently detected radius-one pivots in confirmation order."""
    values = bars["low" if kind == "low" else "high"].to_numpy(float)
    if kind == "low":
        mask = (values[1:-1] <= values[:-2]) & (values[1:-1] <= values[2:])
    else:
        mask = (values[1:-1] >= values[:-2]) & (values[1:-1] >= values[2:])
    return np.flatnonzero(mask) + 1


def reconstruct_candidate(
    row: pd.Series,
    m1: pd.DataFrame,
    h1: pd.DataFrame,
    h1_atr: np.ndarray,
    bars: pd.DataFrame,
    bar_atr: np.ndarray,
    pivots: dict[str, np.ndarray],
) -> IndependentCandidate:
    """Re-run impulse, first-valid-pullback and continuation selection."""
    anchor = pd.Timestamp(row["anchor"])
    first = int(m1.index.searchsorted(anchor, side="left"))
    if first >= len(m1) or m1.index[first] > anchor + pd.Timedelta(minutes=5):
        raise VerificationError("saved row has no usable anchor bar")
    reference = float(m1.iloc[first]["open"])
    available = pd.DatetimeIndex(h1["avail"])
    h1_index = int(available.searchsorted(anchor, side="right")) - 1
    h_value = float(h1_atr[h1_index])
    distance = float(row["threshold"]) * h_value
    impulse_index: int | None = None
    side = 0
    end = int(m1.index.searchsorted(anchor + pd.Timedelta(minutes=60), side="left"))
    for index in range(first, end):
        close = float(m1.iloc[index]["close"])
        up = close >= reference + distance
        down = close <= reference - distance
        if up != down:
            impulse_index = index
            side = 1 if up else -1
            break
    if impulse_index is None:
        raise VerificationError("saved row has no independently detected impulse")
    impulse_decision = pd.Timestamp(m1.index[impulse_index]) + pd.Timedelta(minutes=1)
    deadline = anchor + pd.Timedelta(minutes=DEADLINE_MINUTES[str(row["window"])])
    kind = "low" if side > 0 else "high"
    anchor_bar = int(bars.index.searchsorted(anchor, side="left"))
    kind_pivots = pivots[kind]
    kind_times = bars.index.take(kind_pivots)
    first_pivot = int(kind_times.searchsorted(impulse_decision, side="left"))
    for pivot in kind_pivots[first_pivot:]:
        pivot_time = pd.Timestamp(bars.index[pivot])
        pivot_available = pd.Timestamp(bars.iloc[pivot + 1]["avail"])
        if pivot_available > deadline:
            break
        if side > 0:
            extreme = float(bars["high"].iloc[anchor_bar : pivot + 1].max())
            pivot_price = float(bars.iloc[pivot]["low"])
            span = extreme - reference
            depth = extreme - pivot_price
            crossed = pivot_price <= reference
            continuation = float(bars["high"].iloc[pivot - 1 : pivot + 2].max())
        else:
            extreme = float(bars["low"].iloc[anchor_bar : pivot + 1].min())
            pivot_price = float(bars.iloc[pivot]["high"])
            span = reference - extreme
            depth = pivot_price - extreme
            crossed = pivot_price >= reference
            continuation = float(bars["low"].iloc[pivot - 1 : pivot + 2].min())
        ratio = depth / span if span > 0 else np.nan
        if crossed or not np.isfinite(ratio) or not 0.20 <= ratio <= 0.65:
            continue
        start = max(pivot + 2, int(bars.index.searchsorted(pivot_available, side="left")))
        for current in range(start, len(bars)):
            decision_time = pd.Timestamp(bars.iloc[current]["avail"])
            if decision_time > deadline:
                break
            close = float(bars.iloc[current]["close"])
            continued = close > continuation if side > 0 else close < continuation
            if not continued:
                continue
            return IndependentCandidate(
                reference,
                h_value,
                side,
                impulse_decision,
                pivot_time,
                pivot_price,
                pivot_available,
                span,
                depth,
                float(ratio),
                continuation,
                decision_time,
                float(bar_atr[current]),
            )
    raise VerificationError("saved row has no independently detected pullback entry")


def independent_path(
    ticks: pd.DataFrame,
    side: int,
    entry: float,
    stop: float,
    start: pd.Timestamp,
    intended_end: pd.Timestamp,
) -> dict[str, object]:
    """Recalculate opportunity labels from ordered raw quotes."""
    risk = (entry - stop) * side
    times = pd.DatetimeIndex(ticks["time_utc"])
    mark = ticks["bid"].to_numpy(float) if side > 0 else ticks["ask"].to_numpy(float)
    current_r = (mark - entry) * side / risk
    stop_mask = mark <= stop if side > 0 else mark >= stop
    stop_hits = np.flatnonzero(stop_mask)
    horizon_hits = np.flatnonzero(times >= intended_end)
    stop_index = int(stop_hits[0]) if len(stop_hits) else len(times)
    horizon_index = int(horizon_hits[0]) if len(horizon_hits) else len(times)
    stopped = stop_index <= horizon_index and stop_index < len(times)
    if stopped:
        observed_end = stop_index + 1
        progress_end = stop_index
    elif horizon_index < len(times):
        observed_end = progress_end = horizon_index + 1
    else:
        observed_end = progress_end = len(times)
    observed = current_r[:observed_end]
    progress = current_r[:progress_end]
    result: dict[str, object] = {
        "stopped": stopped,
        "stop_time": times[stop_index] if stopped else pd.NaT,
        "mfe_r": max(0.0, float(np.max(observed))) if len(observed) else 0.0,
        "mae_r": min(0.0, float(np.min(observed))) if len(observed) else 0.0,
        "complete_8h": stopped or horizon_index < len(times),
    }
    running_peak = np.maximum.accumulate(progress) if len(progress) else np.empty(0)
    for milestone in (1, 2, 3, 5):
        matches = np.flatnonzero(progress >= milestone)
        index = int(matches[0]) if len(matches) else None
        suffix = f"{milestone}r"
        result[f"reached_{suffix}"] = index is not None
        result[f"time_{suffix}_min"] = (
            (times[index] - start).total_seconds() / 60.0 if index is not None else np.nan
        )
        adverse_end = index + 1 if index is not None else observed_end
        result[f"mae_before_{suffix}"] = (
            min(0.0, float(np.min(current_r[:adverse_end]))) if adverse_end else 0.0
        )
        if milestone in (1, 2):
            result[f"giveback_after_{suffix}"] = (
                float(np.max(running_peak[index:] - progress[index:])) if index is not None else np.nan
            )
    progress_times = times[:progress_end]
    for minute in (60, 120, 240, 480):
        matches = np.flatnonzero(progress_times >= start + pd.Timedelta(minutes=minute))
        result[f"r_{minute}"] = float(progress[int(matches[0])]) if len(matches) else np.nan
    return result


def equal(actual: object, expected: object, *, tolerance: float = 1e-9) -> bool:
    """Compare scalar numeric, timestamp and missing values."""
    if pd.isna(actual) and pd.isna(expected):
        return True
    if isinstance(actual, (float, np.floating)) or isinstance(expected, (float, np.floating)):
        return bool(np.isclose(float(actual), float(expected), rtol=tolerance, atol=tolerance))
    return bool(actual == expected)


def require_equal(row_number: int, name: str, actual: object, expected: object) -> None:
    if not equal(actual, expected):
        raise VerificationError(f"row {row_number} {name}: reconstructed {actual!r}, saved {expected!r}")


def main() -> None:
    saved = pd.read_parquet(HERE / "opportunities_p1.parquet")
    m1 = load_m1(BAR_PATH, P1, warmup_start=pd.Timestamp("2025-09-01", tz="UTC"))
    bars_by_tf = {name: aggregate_independently(m1, minutes) for name, minutes in TF_MINUTES.items()}
    atr_by_tf = {name: atr_independently(bars) for name, bars in bars_by_tf.items()}
    pivots_by_tf = {
        name: {kind: pivot_indices(bars, kind) for kind in ("low", "high")}
        for name, bars in bars_by_tf.items()
    }
    h1 = aggregate_independently(m1, 60)
    h1_atr = atr_independently(h1)
    store = TickStore(TICK_ROOT, P1, cache_days=2)
    path_fields = [
        "stopped",
        "stop_time",
        "mfe_r",
        "mae_r",
        "reached_1r",
        "reached_2r",
        "reached_3r",
        "reached_5r",
        "time_1r_min",
        "time_2r_min",
        "time_3r_min",
        "time_5r_min",
        "mae_before_1r",
        "mae_before_2r",
        "mae_before_3r",
        "mae_before_5r",
        "giveback_after_1r",
        "giveback_after_2r",
        "r_60",
        "r_120",
        "r_240",
        "r_480",
        "complete_8h",
    ]
    candidate_checks = 0
    quote_checks = 0
    path_checks = 0
    for row_number, row in saved.iterrows():
        timeframe = str(row["timeframe"])
        candidate = reconstruct_candidate(
            row,
            m1,
            h1,
            h1_atr,
            bars_by_tf[timeframe],
            atr_by_tf[timeframe],
            pivots_by_tf[timeframe],
        )
        for field in IndependentCandidate.__dataclass_fields__:
            require_equal(row_number, field, getattr(candidate, field), row[field])
            candidate_checks += 1
        decision = pd.Timestamp(row["decision_time"])
        fill_ticks = store.span(decision, min(decision + pd.Timedelta(minutes=5), P1.end))
        if fill_ticks.empty:
            raise VerificationError(f"row {row_number} has no independent fill")
        fill_tick = fill_ticks.iloc[0]
        entry = float(fill_tick["ask"] if int(row["side"]) > 0 else fill_tick["bid"])
        spread = float(fill_tick["ask"] - fill_tick["bid"])
        buffer = max(spread, 0.10 * candidate.entry_atr)
        stop = candidate.pivot_price - buffer if candidate.side > 0 else candidate.pivot_price + buffer
        risk = (entry - stop) * candidate.side
        derived = {
            "entry_time": pd.Timestamp(fill_tick["time_utc"]),
            "entry": entry,
            "spread": spread,
            "stop": stop,
            "risk": risk,
            "risk_h1": risk / candidate.h1_atr,
            "pullback_depth_h1": candidate.pullback_depth / candidate.h1_atr,
            "pullback_duration_min": (candidate.pivot_available - candidate.impulse_decision).total_seconds()
            / 60.0,
        }
        for field, actual in derived.items():
            require_equal(row_number, field, actual, row[field])
            quote_checks += 1
        entry_time = pd.Timestamp(row["entry_time"])
        intended_end = entry_time + pd.Timedelta(hours=8)
        path = store.span(entry_time, min(intended_end + pd.Timedelta(minutes=5), P1.end))
        labels = independent_path(path, candidate.side, entry, stop, entry_time, intended_end)
        for field in path_fields:
            require_equal(row_number, field, labels[field], row[field])
            path_checks += 1
    if any(day >= P1.end for day in store.opened):
        raise VerificationError("independent verifier opened a tick day beyond P1")
    report = "\n".join(
        [
            "TR1 independent opportunity replay - P1 only",
            f"rows replayed: {len(saved)}",
            f"candidate field checks: {candidate_checks}",
            f"entry/stop field checks: {quote_checks}",
            f"raw-tick path field checks: {path_checks}",
            f"physical tick files opened: {len(store.opened)}",
            f"latest tick day opened: {max(store.opened).date() if store.opened else None}",
            "result: PASS",
            "Producer opportunity/simulation modules were not imported.",
            "No P2 or exam data was opened.",
            "",
        ]
    )
    (HERE / "out_verify_opportunities_p1.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
