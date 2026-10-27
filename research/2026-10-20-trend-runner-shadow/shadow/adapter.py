"""One-way file adapter from frozen market data to the shadow journal."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .clocks import DEADLINE_MINUTES, SESSIONS, anchor
from .detector import detect, fill_and_risk
from .journal import ShadowJournal
from .live_features import build_features
from .schema import COLLECTION_START, Opportunity
from .service import score_opportunity


def load_m1(path: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frame = pd.read_parquet(
        path,
        filters=[("open_time", ">=", start.to_pydatetime()), ("open_time", "<", end.to_pydatetime())],
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame = frame.sort_values("open_time").set_index("open_time")
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("M1 timestamps must be unique and increasing")
    return frame


def load_ticks(root: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    days = pd.date_range(start.floor("D"), end.floor("D"), freq="D")
    files = [root / f"{day.date().isoformat()}.parquet" for day in days]
    if any(not path.exists() for path in files):
        return None
    frames = [
        pd.read_parquet(
            path,
            filters=[("time_utc", ">=", start.to_pydatetime()), ("time_utc", "<=", end.to_pydatetime())],
        )
        for path in files
    ]
    result = pd.concat(frames, ignore_index=True)
    if not result.empty:
        result["time_utc"] = pd.to_datetime(result["time_utc"], utc=True)
        # Equal-time quotes keep file order (bug S2, 2026-10-22).
        result = result.sort_values("time_utc", kind="stable").reset_index(drop=True)
    return result


def frame_hash(*frames: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes())
    return digest.hexdigest()


def _jsonable_detection(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def process_anchor(
    journal: ShadowJournal,
    m1: pd.DataFrame,
    tick_root: Path,
    at: pd.Timestamp,
    window: str,
    *,
    operational: bool = True,
) -> str:
    if operational and at < COLLECTION_START:
        raise ValueError("operational adapter cannot scan before collection boundary")
    anchor_id = f"{at.isoformat()}|{window}"
    if journal.adapter_anchor(anchor_id) is not None:
        return "ALREADY_PROCESSED"
    deadline = at + pd.Timedelta(minutes=DEADLINE_MINUTES[window])
    relevant = m1.loc[(m1.index >= at - pd.Timedelta(days=30)) & (m1.index < deadline)]
    detection = detect(m1, at, window)
    if detection is None:
        journal.record_adapter_anchor(
            anchor_id=anchor_id,
            anchor_time=at.isoformat(),
            window=window,
            status="NO_ENTRY",
            input_hash=frame_hash(relevant),
            details={},
        )
        return "NO_ENTRY"
    tick_end = detection.decision_time + pd.Timedelta(minutes=5)
    ticks = load_ticks(tick_root, detection.decision_time, tick_end)
    if ticks is None:
        return "PENDING_TICKS"
    fill = fill_and_risk(detection, ticks)
    details = {key: _jsonable_detection(value) for key, value in asdict(detection).items()}
    if fill is None:
        journal.record_adapter_anchor(
            anchor_id=anchor_id,
            anchor_time=at.isoformat(),
            window=window,
            status="NO_FILL_OR_RISK_REJECT",
            input_hash=frame_hash(relevant, ticks),
            details=details,
        )
        return "NO_FILL_OR_RISK_REJECT"
    trade_key = f"TR1-{at.strftime('%Y%m%dT%H%M%SZ')}-{window}"
    opportunity = Opportunity.from_dict(
        {
            "trade_key": trade_key,
            "entry_time": pd.Timestamp(fill["entry_time"]).isoformat(),
            "anchor": at.isoformat(),
            "window": window,
            "side": detection.side,
            "entry": fill["entry"],
            "spread": fill["spread"],
            "stop": fill["stop"],
            "risk": fill["risk"],
            "features": build_features(m1, detection, fill, journal),
        }
    )
    journal.record_opportunity(opportunity)
    score_opportunity(journal, trade_key)
    details.update({key: _jsonable_detection(value) for key, value in fill.items()})
    details["trade_key"] = trade_key
    journal.record_adapter_anchor(
        anchor_id=anchor_id,
        anchor_time=at.isoformat(),
        window=window,
        status="EMITTED_AND_SCORED",
        input_hash=frame_hash(relevant, ticks),
        details=details,
    )
    return "EMITTED_AND_SCORED"


def scan(
    journal: ShadowJournal,
    *,
    m1_path: Path,
    tick_root: Path,
    start_day: str,
    end_day: str,
) -> dict[str, int]:
    start = pd.Timestamp(start_day)
    end = pd.Timestamp(end_day)
    if start.tzinfo is not None or end.tzinfo is not None or end <= start:
        raise ValueError("scan days must be naive YYYY-MM-DD with end > start")
    if start.tz_localize("UTC") < COLLECTION_START:
        raise ValueError("scan starts before forward collection boundary")
    m1 = load_m1(
        m1_path,
        (start - pd.Timedelta(days=30)).tz_localize("UTC"),
        (end + pd.Timedelta(days=1)).tz_localize("UTC"),
    )
    counts: dict[str, int] = {}
    local_days = pd.date_range(start, end - pd.Timedelta(days=1), freq="D")
    scheduled = sorted(
        (anchor(day, window), window) for day in local_days if day.dayofweek < 5 for window in SESSIONS
    )
    for at, window in scheduled:
        try:
            status = process_anchor(journal, m1, tick_root, at, window)
        except ValueError as error:
            if "full anchor deadline" not in str(error):
                raise
            status = "PENDING_M1"
        counts[status] = counts.get(status, 0) + 1
    return counts
