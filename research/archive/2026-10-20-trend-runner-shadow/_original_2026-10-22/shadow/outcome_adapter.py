"""File-only settlement of hypothetical FAST and RUNNER shadow outcomes."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .adapter import load_m1
from .journal import ShadowJournal
from .outcomes import StructureContext, build_structure_context, run_exit, structure_events
from .schema import Outcome


def load_outcome_ticks(root: Path, start: pd.Timestamp, deadline: pd.Timestamp) -> pd.DataFrame | None:
    frames: list[pd.DataFrame] = []
    found_deadline = False
    # A Friday/holiday deadline can be reached only by the next market quote.
    for day in pd.date_range(start.floor("D"), deadline.floor("D") + pd.Timedelta(days=14), freq="D"):
        path = root / f"{day.date().isoformat()}.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True)
        frame = frame.loc[frame["time_utc"] >= start]
        if frame.empty:
            continue
        frames.append(frame)
        if (frame["time_utc"] >= deadline).any():
            found_deadline = True
            break
    if not frames or not found_deadline:
        return None
    ticks = pd.concat(frames, ignore_index=True).sort_values("time_utc").reset_index(drop=True)
    end = int(pd.DatetimeIndex(ticks["time_utc"]).searchsorted(deadline, side="left"))
    ticks = ticks.iloc[: end + 1].reset_index(drop=True)
    return ticks


def calculate_outcome(
    opportunity: dict[str, object],
    ticks: pd.DataFrame,
    context: StructureContext,
) -> Outcome:
    entry_time = pd.Timestamp(opportunity["entry_time"])
    runner_end = entry_time + pd.Timedelta(hours=8)
    events = structure_events(
        context,
        side=int(opportunity["side"]),
        entry_time=entry_time,
        entry_spread=float(opportunity["spread"]),
        end_time=runner_end,
    )
    arguments = (
        ticks,
        int(opportunity["side"]),
        float(opportunity["entry"]),
        float(opportunity["stop"]),
        entry_time,
        events,
    )
    fast = run_exit("FAST", *arguments)
    runner = run_exit("RUNNER", *arguments)
    if not fast.complete or not runner.complete or fast.exit_time is None or runner.exit_time is None:
        raise ValueError("both hypothetical paths must be complete")
    risk = float(opportunity["risk"])
    return Outcome.from_dict(
        {
            "trade_key": str(opportunity["trade_key"]),
            "fast_exit_time": fast.exit_time.isoformat(),
            "runner_exit_time": runner.exit_time.isoformat(),
            "fast_r": fast.r,
            "runner_r": runner.r,
            "fast_usd_fixed_001": fast.r * risk,
            "runner_usd_fixed_001": runner.r * risk,
        }
    )


def settle(journal: ShadowJournal, *, m1_path: Path, tick_root: Path) -> dict[str, int]:
    opportunities = journal.opportunities()
    outcomes = journal.outcomes()
    existing = set() if outcomes.empty else set(outcomes["trade_key"])
    if opportunities.empty:
        return {"ALREADY_SETTLED_OR_EMPTY": 0}
    pending = opportunities.loc[~opportunities["trade_key"].isin(existing)]
    if pending.empty:
        return {"ALREADY_SETTLED_OR_EMPTY": 0}
    decisions = journal.decisions()
    decided = set() if decisions.empty else set(decisions["trade_key"])
    ready = pending.loc[pending["trade_key"].isin(decided)].copy()
    counts: dict[str, int] = {}
    undecided_count = len(pending) - len(ready)
    if undecided_count:
        counts["PENDING_DECISION"] = int(undecided_count)
    if ready.empty:
        return counts
    ready["entry_time"] = pd.to_datetime(ready["entry_time"], utc=True)
    earliest = ready["entry_time"].min() - pd.Timedelta(days=30)
    latest = ready["entry_time"].max() + pd.Timedelta(hours=8, minutes=1)
    m1 = load_m1(m1_path, earliest, latest)
    m1_end = None if m1.empty else m1.index.max() + pd.Timedelta(minutes=1)
    context = build_structure_context(m1)
    for opportunity in ready.sort_values("entry_time").to_dict(orient="records"):
        entry_time = pd.Timestamp(opportunity["entry_time"])
        deadline = entry_time + pd.Timedelta(hours=8)
        if m1_end is None or m1_end < deadline:
            status = "PENDING_M1"
        else:
            ticks = load_outcome_ticks(tick_root, entry_time, deadline)
            if ticks is None:
                status = "PENDING_TICKS"
            else:
                journal.record_outcome(calculate_outcome(opportunity, ticks, context))
                status = "SETTLED"
        counts[status] = counts.get(status, 0) + 1
    return counts
