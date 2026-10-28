"""Run the frozen TR1 round through one common P1/P2 code path; exam is unsupported."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from tr1.bars import aggregate, atr, confirmed_fractals, minute_bars
from tr1.boundaries import DataBoundaryError, Period, PeriodName, period_for
from tr1.data import TickStore, load_m1
from tr1.exits import ExitFamily, run_exit
from tr1.opportunity import find_first_pullback, find_impulse, initial_stop
from tr1.simulation import market_fill
from tr1.structure import structure_events
from tr1.windows import Window, anchor

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
TICK_ROOT = REPO / "data" / "ticks" / "XAUUSD"
MANIFEST = HERE / "freeze_manifest.json"
THRESHOLD = 0.25
TIMEFRAME = "M1"
DEADLINES = {Window.ASIA: 120, Window.LONDON: 120, Window.NY0830: 240}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_frozen_manifest() -> None:
    """Refuse validation unless every frozen source/rule file still has its recorded hash."""
    if not MANIFEST.exists():
        raise DataBoundaryError("P2 remains locked because freeze_manifest.json does not exist")
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))["sha256"]
    mismatches = []
    for relative, expected in records.items():
        path = HERE / relative
        actual = sha256(path) if path.exists() else "MISSING"
        if actual != expected:
            mismatches.append(f"{relative}: expected {expected}, got {actual}")
    if mismatches:
        raise DataBoundaryError("frozen hash mismatch; P2 was not opened:\n" + "\n".join(mismatches))


def atr_values(bars: pd.DataFrame) -> np.ndarray:
    return atr(
        bars["high"].to_numpy(float),
        bars["low"].to_numpy(float),
        bars["close"].to_numpy(float),
        14,
    )


def h1_at(h1: pd.DataFrame, values: np.ndarray, moment: pd.Timestamp) -> float:
    index = int(pd.DatetimeIndex(h1["avail"]).searchsorted(moment, side="right")) - 1
    return float(values[index]) if index >= 0 else np.nan


def study_days(period: Period) -> list[str]:
    days = pd.date_range(period.start.normalize(), period.end - pd.Timedelta(days=1), freq="1D")
    return [day.date().isoformat() for day in days if day.dayofweek < 5]


def execution_path(
    store: TickStore,
    start: pd.Timestamp,
    deadline: pd.Timestamp,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    day = start.normalize()
    found = False
    while day < store.period.end:
        if (store.root / f"{day.date().isoformat()}.parquet").exists():
            frame = store.day(day)
            frame = frame.loc[frame["time_utc"] >= start] if day == start.normalize() else frame
            if len(frame):
                frames.append(frame)
                if (frame["time_utc"] >= deadline).any():
                    found = True
                    break
        day += pd.Timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=["time_utc", "bid", "ask"])
    ticks = pd.concat(frames, ignore_index=True)
    if found:
        end = int(pd.DatetimeIndex(ticks["time_utc"]).searchsorted(deadline, side="left"))
        ticks = ticks.iloc[: end + 1]
    return ticks.reset_index(drop=True)


def generate_entries(period: Period, m1: pd.DataFrame, store: TickStore) -> pd.DataFrame:
    bars = minute_bars(m1)
    entry_atr = atr_values(bars)
    pivots = confirmed_fractals(bars, radius=1)
    h1 = aggregate(m1, "1h")
    h1_values = atr_values(h1)
    rows: list[dict[str, object]] = []
    for day in study_days(period):
        for window, deadline in DEADLINES.items():
            at = anchor(day, window)
            if not period.contains(at):
                continue
            h_value = h1_at(h1, h1_values, at)
            impulse = find_impulse(m1, at, h_value, THRESHOLD)
            if impulse is None:
                continue
            candidate, _ = find_first_pullback(
                bars,
                impulse,
                window=window.value,
                timeframe=TIMEFRAME,
                deadline_minutes=deadline,
                entry_atr_values=entry_atr,
                pivots=pivots,
            )
            if candidate is None:
                continue
            fill_end = min(candidate.decision_time + pd.Timedelta(minutes=5), period.end)
            fill_ticks = store.span(candidate.decision_time, fill_end)
            fill = market_fill(fill_ticks, impulse.side, candidate.decision_time)
            if fill is None:
                continue
            spread = float(fill_ticks.iloc[fill.index]["ask"] - fill_ticks.iloc[fill.index]["bid"])
            stop, risk = initial_stop(candidate, fill, spread)
            risk_h = risk / impulse.h1_atr
            if not 0.05 <= risk_h <= 0.50:
                continue
            rows.append(
                {
                    "window": window.value,
                    "anchor": at,
                    "reference": impulse.reference,
                    "h1_atr": impulse.h1_atr,
                    "side": impulse.side,
                    "impulse_decision": impulse.decision,
                    "pivot_time": candidate.pivot_time,
                    "pivot_price": candidate.pivot_price,
                    "pivot_available": candidate.pivot_available,
                    "pullback_ratio": candidate.pullback_ratio,
                    "decision_time": candidate.decision_time,
                    "entry_atr": candidate.entry_atr,
                    "entry_time": fill.time,
                    "entry": fill.price,
                    "spread": spread,
                    "stop": stop,
                    "risk": risk,
                    "risk_h1": risk_h,
                }
            )
    return pd.DataFrame(rows).sort_values("entry_time").reset_index(drop=True)


def generate_exits(
    period: Period,
    m1: pd.DataFrame,
    store: TickStore,
    entries: pd.DataFrame,
) -> pd.DataFrame:
    bars = {"M5": aggregate(m1, "5min"), "M15": aggregate(m1, "15min")}
    atrs = {name: atr_values(frame) for name, frame in bars.items()}
    pivots = {name: confirmed_fractals(frame, radius=1) for name, frame in bars.items()}
    rows: list[dict[str, object]] = []
    for entry_id, entry_row in entries.iterrows():
        entry_time = pd.Timestamp(entry_row["entry_time"])
        runner_end = entry_time + pd.Timedelta(hours=8)
        path = execution_path(store, entry_time, runner_end)
        events = []
        for timeframe in ("M5", "M15"):
            events.extend(
                structure_events(
                    bars[timeframe],
                    pivots[timeframe],
                    atrs[timeframe],
                    timeframe=timeframe,
                    side=int(entry_row["side"]),
                    entry_time=entry_time,
                    entry_spread=float(entry_row["spread"]),
                    end_time=min(runner_end, period.end),
                )
            )
        for family in ExitFamily:
            result = run_exit(
                family,
                path,
                int(entry_row["side"]),
                float(entry_row["entry"]),
                float(entry_row["stop"]),
                entry_time,
                events,
            )
            record = {
                "entry_id": entry_id,
                "window": entry_row["window"],
                "anchor": entry_row["anchor"],
                "entry_time": entry_time,
                "side": int(entry_row["side"]),
                "entry": float(entry_row["entry"]),
                "initial_stop": float(entry_row["stop"]),
                "initial_risk": float(entry_row["risk"]),
                **asdict(result),
            }
            record["family"] = result.family.value
            record["reason"] = result.reason.value
            record["usd_001"] = result.r * float(entry_row["risk"]) if result.complete else np.nan
            rows.append(record)
    return pd.DataFrame(rows).sort_values(["entry_time", "family"]).reset_index(drop=True)


def p1_reference_superseded() -> bool:
    """True when the manifest marks the stored P1 artifacts as superseded (re-freeze of 2026-10-22).

    The stored P1 parquet files were produced by the code before bug B1 was fixed, so they are no reference.
    """
    if not MANIFEST.exists():
        return False
    return bool(json.loads(MANIFEST.read_text(encoding="utf-8")).get("p1_reference_superseded"))


def verify_p1_parity(entries: pd.DataFrame, exits: pd.DataFrame) -> None:
    if p1_reference_superseded():
        print("P1 parity skipped: the stored P1 artifacts predate the 2026-10-22 bug fixes")  # noqa: T201
        return
    opportunities = pd.read_parquet(HERE / "opportunities_p1.parquet")
    reference_entries = (
        opportunities.loc[
            (opportunities["threshold"] == THRESHOLD) & (opportunities["timeframe"] == TIMEFRAME)
        ]
        .sort_values("entry_time")
        .reset_index(drop=True)
    )
    columns = list(entries.columns)
    assert_frame_equal(entries, reference_entries[columns], check_dtype=False, rtol=1e-12, atol=1e-12)
    reference_exits = pd.read_parquet(HERE / "exit_results_p1.parquet")
    assert_frame_equal(exits, reference_exits, check_dtype=False, rtol=1e-12, atol=1e-12)


def render_report(period: Period, entries: pd.DataFrame, exits: pd.DataFrame, store: TickStore) -> str:
    lines = [
        f"TR1 frozen round - {period.name.value}",
        f"entries: {len(entries)}; exit rows: {len(exits)}",
        f"physical tick files opened: {len(store.opened)}; latest: "
        f"{max(store.opened).date() if store.opened else None}",
        "family complete mean_R total_R USD_001 win",
    ]
    for family in ExitFamily:
        frame = exits.loc[(exits["family"] == family.value) & exits["complete"]]
        lines.append(
            f"{family.value:5} {len(frame):3d} {frame['r'].mean():+.3f} {frame['r'].sum():+.2f} "
            f"{frame['usd_001'].sum():+.2f} {(frame['r'] > 0).mean():.3f}"
        )
    if period.name is PeriodName.P1 and not p1_reference_superseded():
        lines.append("P1 common-runner parity with opportunity/exit study: PASS")
    lines.append("Exam data is unsupported and was not opened.")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["P1", "P2"], required=True)
    parser.add_argument("--allow-validation", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    name = PeriodName(args.period)
    if name is PeriodName.P2:
        if not args.allow_validation:
            raise DataBoundaryError("P2 requires the explicit --allow-validation switch")
        require_frozen_manifest()
    period = period_for(name, allow_validation=args.allow_validation, allow_exam=False)
    warmup = period.start - pd.Timedelta(days=50)
    m1 = load_m1(BAR_PATH, period, warmup_start=warmup)
    store = TickStore(TICK_ROOT, period, cache_days=4)
    entries = generate_entries(period, m1, store)
    exits = generate_exits(period, m1, store, entries)
    if name is PeriodName.P1:
        verify_p1_parity(entries, exits)
    suffix = name.value.lower()
    entries.to_parquet(HERE / f"frozen_entries_{suffix}.parquet", index=False)
    exits.to_parquet(HERE / f"frozen_results_{suffix}.parquet", index=False)
    report = render_report(period, entries, exits, store)
    (HERE / f"out_frozen_{suffix}.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
