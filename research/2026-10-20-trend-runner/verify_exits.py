"""Independent raw-quote replay of every P1 exit-family result."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from tr1.boundaries import P1
from tr1.data import TickStore, load_m1
from verify_opportunities import aggregate_independently, atr_independently, pivot_indices

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BAR_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
TICK_ROOT = REPO / "data" / "ticks" / "XAUUSD"


class VerificationError(AssertionError):
    """Independent exit reconstruction differs from the saved producer result."""


def read_path(store: TickStore, start: pd.Timestamp, deadline: pd.Timestamp) -> pd.DataFrame:
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
        last = int(pd.DatetimeIndex(ticks["time_utc"]).searchsorted(deadline, side="left"))
        ticks = ticks.iloc[: last + 1]
    return ticks.reset_index(drop=True)


def independent_events(
    bars: pd.DataFrame,
    atrs: np.ndarray,
    pivots: dict[str, np.ndarray],
    timeframe: str,
    side: int,
    entry_time: pd.Timestamp,
    spread: float,
    end: pd.Timestamp,
) -> list[dict[str, object]]:
    kind = "low" if side > 0 else "high"
    events: list[dict[str, object]] = []
    for pivot in pivots[kind]:
        pivot_time = pd.Timestamp(bars.index[pivot])
        available = pd.Timestamp(bars.iloc[pivot + 1]["avail"])
        if pivot_time < entry_time or available < entry_time:
            continue
        if available > end:
            break
        value = float(atrs[pivot + 1])
        if not np.isfinite(value) or value <= 0:
            continue
        price = float(bars.iloc[pivot]["low" if side > 0 else "high"])
        buffer = max(spread, 0.10 * value)
        events.append(
            {
                "avail": available,
                "timeframe": timeframe,
                "pivot_time": pivot_time,
                "stop": price - buffer if side > 0 else price + buffer,
            }
        )
    return events


def tighter(side: int, current: float, candidate: float) -> float:
    return max(current, candidate) if side > 0 else min(current, candidate)


def is_stop(side: int, price: float, stop: float) -> bool:
    return price <= stop if side > 0 else price >= stop


def event_applies(
    event: dict[str, object],
    graduated: bool,
    graduation_time: pd.Timestamp | None,
    runner_end: pd.Timestamp,
) -> bool:
    available = pd.Timestamp(event["avail"])
    if available > runner_end:
        return False
    if not graduated:
        return event["timeframe"] == "M5"
    return event["timeframe"] == "M15" and graduation_time is not None and available >= graduation_time


def independent_exit(
    family: str,
    ticks: pd.DataFrame,
    side: int,
    entry: float,
    initial_stop: float,
    entry_time: pd.Timestamp,
    events: list[dict[str, object]],
) -> dict[str, object]:
    times = pd.DatetimeIndex(ticks["time_utc"])
    prices = ticks["bid"].to_numpy(float) if side > 0 else ticks["ask"].to_numpy(float)
    risk = (entry - initial_stop) * side
    fast_end = entry_time + pd.Timedelta(minutes=60)
    runner_end = entry_time + pd.Timedelta(hours=8)
    target_1 = entry + side * risk
    target_2 = entry + side * 2 * risk
    target_3 = entry + side * 3 * risk
    events = sorted(events, key=lambda event: (event["avail"], event["timeframe"], event["pivot_time"]))
    pointer = 0
    stop = initial_stop
    partial = False
    runner = family in {"SWING", "SPLIT"}
    graduated = False
    graduation_time: pd.Timestamp | None = None
    reached_1_time: pd.Timestamp | None = None
    known_m5: list[dict[str, object]] = []

    def finish(reason: str, time: pd.Timestamp | None, price: float) -> dict[str, object]:
        complete = reason != "CENSORED"
        raw_r = (price - entry) * side / risk if np.isfinite(price) else np.nan
        result_r = 1 / 3 + 2 / 3 * raw_r if partial and complete else raw_r
        return {
            "complete": complete,
            "exit_time": time if time is not None else pd.NaT,
            "exit_price": price,
            "reason": reason,
            "r": result_r,
            "holding_minutes": ((time - entry_time).total_seconds() / 60 if time is not None else np.nan),
            "runner_activated": runner,
            "partial_taken": partial,
            "graduated": graduated,
            "final_stop": stop,
        }

    for tick_index, time in enumerate(times):
        price = float(prices[tick_index])
        while pointer < len(events) and pd.Timestamp(events[pointer]["avail"]) < time:
            event = events[pointer]
            pointer += 1
            if event["timeframe"] == "M5":
                known_m5.append(event)
            if runner and event_applies(event, graduated, graduation_time, runner_end):
                stop = tighter(side, stop, float(event["stop"]))
        same: list[dict[str, object]] = []
        while pointer < len(events) and pd.Timestamp(events[pointer]["avail"]) == time:
            same.append(events[pointer])
            pointer += 1
        if is_stop(side, price, stop):
            return finish("STOP", time, price)
        if family in {"FAST", "STATE"} and not runner:
            at_target = price >= target_2 if side > 0 else price <= target_2
            if at_target:
                return finish("TARGET", time, target_2)
        if family == "SPLIT" and not partial:
            at_partial = price >= target_1 if side > 0 else price <= target_1
            if at_partial:
                partial = True
        if family == "STATE" and not runner:
            known_m5.extend(event for event in same if event["timeframe"] == "M5")
            if time <= fast_end:
                at_1 = price >= target_1 if side > 0 else price <= target_1
                if at_1 and reached_1_time is None:
                    reached_1_time = time
                qualifying = [
                    event
                    for event in known_m5
                    if pd.Timestamp(event["avail"]) <= fast_end
                    and tighter(side, initial_stop, float(event["stop"])) != initial_stop
                ]
                if reached_1_time is not None and qualifying:
                    runner = True
                    for event in qualifying:
                        stop = tighter(side, stop, float(event["stop"]))
                    if is_stop(side, price, stop):
                        return finish("STOP", time, price)
            if not runner and time >= fast_end:
                return finish("TIME", time, price)
        if family == "FAST" and time >= fast_end:
            return finish("TIME", time, price)
        if runner and not graduated:
            at_3 = price >= target_3 if side > 0 else price <= target_3
            if at_3:
                graduated = True
                graduation_time = time
        for event in same:
            if runner and event_applies(event, graduated, graduation_time, runner_end):
                stop = tighter(side, stop, float(event["stop"]))
        if is_stop(side, price, stop):
            return finish("STOP", time, price)
        if runner and time >= runner_end:
            return finish("TIME", time, price)
    return finish("CENSORED", times[-1] if len(times) else None, float(prices[-1]) if len(prices) else np.nan)


def equal(actual: object, expected: object) -> bool:
    if pd.isna(actual) and pd.isna(expected):
        return True
    if isinstance(actual, (float, np.floating)) or isinstance(expected, (float, np.floating)):
        return bool(np.isclose(float(actual), float(expected), rtol=1e-9, atol=1e-9))
    return bool(actual == expected)


def main() -> None:
    saved = pd.read_parquet(HERE / "exit_results_p1.parquet")
    opportunities = pd.read_parquet(HERE / "opportunities_p1.parquet")
    selected = (
        opportunities.loc[(opportunities["threshold"] == 0.25) & (opportunities["timeframe"] == "M1")]
        .sort_values("entry_time")
        .reset_index(drop=True)
    )
    m1 = load_m1(BAR_PATH, P1, warmup_start=pd.Timestamp("2025-09-01", tz="UTC"))
    bars = {"M5": aggregate_independently(m1, 5), "M15": aggregate_independently(m1, 15)}
    atrs = {name: atr_independently(frame) for name, frame in bars.items()}
    pivots = {
        name: {kind: pivot_indices(frame, kind) for kind in ("low", "high")} for name, frame in bars.items()
    }
    store = TickStore(TICK_ROOT, P1, cache_days=4)
    fields = [
        "complete",
        "exit_time",
        "exit_price",
        "reason",
        "r",
        "holding_minutes",
        "runner_activated",
        "partial_taken",
        "graduated",
        "final_stop",
    ]
    checks = 0
    for entry_id, opportunity in selected.iterrows():
        entry_time = pd.Timestamp(opportunity["entry_time"])
        end = entry_time + pd.Timedelta(hours=8)
        path = read_path(store, entry_time, end)
        events: list[dict[str, object]] = []
        for timeframe in ("M5", "M15"):
            events.extend(
                independent_events(
                    bars[timeframe],
                    atrs[timeframe],
                    pivots[timeframe],
                    timeframe,
                    int(opportunity["side"]),
                    entry_time,
                    float(opportunity["spread"]),
                    min(end, P1.end),
                )
            )
        for family in ("FAST", "SWING", "SPLIT", "STATE"):
            expected = saved.loc[(saved["entry_id"] == entry_id) & (saved["family"] == family)].iloc[0]
            actual = independent_exit(
                family,
                path,
                int(opportunity["side"]),
                float(opportunity["entry"]),
                float(opportunity["stop"]),
                entry_time,
                events,
            )
            for field in fields:
                if not equal(actual[field], expected[field]):
                    raise VerificationError(
                        f"entry {entry_id} {family} {field}: reconstructed {actual[field]!r}, "
                        f"saved {expected[field]!r}"
                    )
                checks += 1
    if any(day >= P1.end for day in store.opened):
        raise VerificationError("independent verifier opened a tick day beyond P1")
    report = "\n".join(
        [
            "TR1 independent exit replay - P1 only",
            f"entries replayed: {len(selected)}",
            f"exit-family rows replayed: {len(saved)}",
            f"field checks: {checks}",
            f"physical tick files opened: {len(store.opened)}",
            f"latest tick day opened: {max(store.opened).date() if store.opened else None}",
            "result: PASS",
            "Producer exit/structure modules were not imported.",
            "No P2 or exam data was opened.",
            "",
        ]
    )
    (HERE / "out_verify_exits_p1.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report)  # noqa: T201


if __name__ == "__main__":
    main()
