"""Read-only adapter from the forward shadow outcome journal to the isolated study."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from candidate import COLLECTION_START, simulate_candidate
from journal import FINAL_STATUSES, CandidateJournal

DEFAULT_WARMUP = pd.Timedelta(hours=3)


def classify_source_event(
    opportunity: dict[str, object], outcome: dict[str, object], ticks: pd.DataFrame
) -> dict[str, object]:
    """Prove whether a completed source RUNNER stopped before its first +1R touch.

    The source outcome has no exit-reason field. We therefore require an exit before
    the frozen eight-hour timeout and inspect ordered executable ticks through the
    recorded exit quote. No final-R shortcut is used.
    """
    entry_time = pd.Timestamp(opportunity["entry_time"])
    stop_time = pd.Timestamp(outcome["runner_exit_time"])
    if entry_time.tzinfo is None or str(entry_time.tz) != "UTC":
        raise ValueError("source entry_time must be UTC")
    if stop_time.tzinfo is None or str(stop_time.tz) != "UTC":
        raise ValueError("source runner_exit_time must be UTC")
    if entry_time < COLLECTION_START:
        raise ValueError("source opportunity predates prospective boundary")
    if stop_time <= entry_time:
        raise ValueError("source RUNNER exit must follow entry")
    side = int(opportunity["side"])
    entry, stop, risk = (float(opportunity[name]) for name in ("entry", "stop", "risk"))
    if (
        side not in (-1, 1) or (entry - stop) * side <= 0 or risk <= 0
        or not math.isclose((entry - stop) * side, risk, rel_tol=1e-8, abs_tol=1e-8)
    ):
        raise ValueError("invalid source side/entry/stop/risk")
    deadline = entry_time + pd.Timedelta(hours=8)
    if stop_time >= deadline:
        stopped_before_plus1 = False  # timeout, not a stop-out
    else:
        if not {"time_utc", "bid", "ask"}.issubset(ticks.columns):
            raise ValueError("ticks need time_utc, bid, and ask")
        times = pd.DatetimeIndex(pd.to_datetime(ticks["time_utc"]))
        if times.tz is None or str(times.tz) != "UTC":
            raise ValueError("source tick timestamps must be timezone-aware UTC")
        if times.has_duplicates or not times.is_monotonic_increasing:
            raise ValueError("source ticks must be unique and increasing")
        if ticks.empty or times[0] > entry_time or times[-1] != stop_time:
            raise ValueError("ticks must cover entry and include the exact recorded RUNNER exit quote")
        if (ticks["ask"].to_numpy(float) < ticks["bid"].to_numpy(float)).any():
            raise ValueError("source ticks contain crossed bid/ask")
        mark = ticks["bid"].to_numpy(float) if side > 0 else ticks["ask"].to_numpy(float)
        in_trade = (times >= entry_time) & (times <= stop_time)
        hit_plus1 = (((mark[in_trade] - entry) * side) >= risk).any()
        stopped_before_plus1 = not bool(hit_plus1)

    return {
        "trade_key": str(opportunity["trade_key"]),
        "stop_time_utc": stop_time.isoformat(),
        "side": side,
        "entry": entry,
        "stop": stop,
        "spread": float(opportunity["spread"]),
        "runner_stopped_before_plus1": bool(stopped_before_plus1),
    }


def _source_rows(db_path: Path) -> list[tuple[dict[str, object], dict[str, object]]]:
    normalized_path = str(db_path.resolve()).replace("\\", "/")
    uri = f"file:{quote(normalized_path, safe='/:')}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        rows = db.execute(
            """SELECT o.payload_json, r.payload_json
               FROM opportunities AS o JOIN outcomes AS r USING(trade_key)
               WHERE o.entry_time >= ? ORDER BY o.entry_time, o.trade_key""",
            (COLLECTION_START.isoformat(),),
        ).fetchall()
    return [(json.loads(opportunity), json.loads(outcome)) for opportunity, outcome in rows]


def _load_ticks(tick_root: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    frames: list[pd.DataFrame] = []
    for day in pd.date_range(start.floor("D"), end.floor("D"), freq="D"):
        path = tick_root / f"{day.date().isoformat()}.parquet"
        if not path.exists():
            return None
        frame = pd.read_parquet(
            path,
            columns=["time_utc", "bid", "ask"],
            filters=[("time_utc", ">=", start.to_pydatetime()), ("time_utc", "<=", end.to_pydatetime())],
        )
        frames.append(frame)
    if not frames:
        return None
    ticks = pd.concat(frames, ignore_index=True)
    ticks["time_utc"] = pd.to_datetime(ticks["time_utc"], utc=True)
    ticks = ticks.sort_values("time_utc").reset_index(drop=True)
    return ticks if not ticks.empty else None


def _load_candidate_m1(
    m1_path: Path, stop_time: pd.Timestamp, *, warmup: pd.Timedelta = DEFAULT_WARMUP
) -> pd.DataFrame:
    start = max(COLLECTION_START, stop_time - warmup)
    # Up to 16h after original stop plus 14 days to reach the first executable quote
    # after a weekend/holiday timeout. This remains strictly post-boundary.
    end = min(
        stop_time + pd.Timedelta(hours=16, days=14, minutes=1),
        pd.Timestamp.now(tz="UTC").floor("min"),
    )
    if end <= start:
        return pd.DataFrame(columns=["open", "high", "low", "close", "spread"],
                            index=pd.DatetimeIndex([], tz="UTC", name="open_time"))
    bars = pd.read_parquet(
        m1_path,
        columns=["open_time", "open", "high", "low", "close", "spread"],
        filters=[("open_time", ">=", start.to_pydatetime()), ("open_time", "<", end.to_pydatetime())],
    )
    bars["open_time"] = pd.to_datetime(bars["open_time"], utc=True)
    return bars.sort_values("open_time").set_index("open_time")


def process_forward_source(
    source_db: Path,
    *,
    m1_path: Path,
    tick_root: Path,
    journal: CandidateJournal,
) -> dict[str, int]:
    """Read matured source rows and append only isolated candidate records.

    The source DB is opened read-only. Existing Champion rows, decisions, and order
    paths are never changed. Incomplete tick/M1 horizons are left pending.
    """
    counts: dict[str, int] = {}
    for opportunity, outcome in _source_rows(source_db):
        entry_time = pd.Timestamp(opportunity["entry_time"])
        stop_time = pd.Timestamp(outcome["runner_exit_time"])
        if entry_time < COLLECTION_START:
            raise ValueError("read-only source query returned a pre-boundary opportunity")
        if stop_time >= pd.Timestamp.now(tz="UTC"):
            counts["PENDING_SOURCE_OUTCOME"] = counts.get("PENDING_SOURCE_OUTCOME", 0) + 1
            continue
        ticks = _load_ticks(tick_root, entry_time, stop_time)
        if (
            ticks is None or ticks.empty
            or pd.Timestamp(ticks["time_utc"].iloc[0]) != entry_time
            or pd.Timestamp(ticks["time_utc"].iloc[-1]) != stop_time
        ):
            counts["PENDING_SOURCE_TICKS"] = counts.get("PENDING_SOURCE_TICKS", 0) + 1
            continue
        event = classify_source_event(opportunity, outcome, ticks)
        bars = _load_candidate_m1(m1_path, stop_time)
        if len(bars) and bars.index.min() < COLLECTION_START:
            raise AssertionError("candidate M1 loader crossed the prospective boundary")
        journal.record_source_event(event)
        result = simulate_candidate(event, bars)
        if result["status"] in FINAL_STATUSES:
            journal.record_result(str(event["trade_key"]), result)
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
    return counts
