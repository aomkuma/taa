"""Append-only store for isolated prospective RETEST-CONTINUATION observations."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from candidate import COLLECTION_START

FINAL_STATUSES = {
    "COMPLETE", "INELIGIBLE_SOURCE", "NO_RECLAIM", "NO_RETEST", "NO_CONTINUATION",
    "STRUCTURE_INVALIDATED", "NO_ATR", "ENTRY_THROUGH_STOP", "EXPIRED",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS source_events (
  trade_key TEXT PRIMARY KEY, event_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_results (
  trade_key TEXT PRIMARY KEY REFERENCES source_events(trade_key), result_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
  trade_key TEXT NOT NULL, payload_hash TEXT NOT NULL, recorded_at TEXT NOT NULL
);
"""


def _hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CandidateJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript(SCHEMA)

    def record_source_event(self, event: dict[str, object]) -> bool:
        required = {
            "trade_key", "stop_time_utc", "side", "entry", "stop", "spread",
            "runner_stopped_before_plus1",
        }
        if set(event) != required:
            raise ValueError(f"source event fields must be exactly {sorted(required)}")
        stop_time = pd.Timestamp(event["stop_time_utc"])
        if stop_time.tzinfo is None or str(stop_time.tz) != "UTC":
            raise ValueError("stop_time_utc must be timezone-aware UTC")
        if stop_time < COLLECTION_START:
            raise ValueError("source event predates collection boundary")
        side = int(event["side"])
        entry, stop, spread = (float(event[name]) for name in ("entry", "stop", "spread"))
        if side not in (-1, 1) or not all(math.isfinite(v) for v in (entry, stop, spread)):
            raise ValueError("invalid side, entry, stop, or spread")
        if spread < 0 or (entry - stop) * side <= 0:
            raise ValueError("source event must have non-negative spread and positive directional risk")
        if not isinstance(event["runner_stopped_before_plus1"], bool):
            raise ValueError("runner_stopped_before_plus1 must be boolean")
        key = str(event["trade_key"]).strip()
        if not key or len(key) > 128:
            raise ValueError("trade_key must contain 1-128 characters")
        payload = dict(event)
        payload["trade_key"] = key
        payload["stop_time_utc"] = stop_time.isoformat()
        payload.update({"side": side, "entry": entry, "stop": stop, "spread": spread})
        event_hash = _hash(payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with sqlite3.connect(self.path) as db:
            existing = db.execute(
                "SELECT event_hash FROM source_events WHERE trade_key=?", (key,)
            ).fetchone()
            if existing:
                if existing[0] != event_hash:
                    raise ValueError(f"immutable source event mismatch for {key}")
                return False
            db.execute(
                "INSERT INTO source_events VALUES (?,?,?,?)", (key, event_hash, encoded, _now())
            )
            db.execute(
                "INSERT INTO audit_log(event_type,trade_key,payload_hash,recorded_at) VALUES (?,?,?,?)",
                ("append_source_event", key, event_hash, _now()),
            )
        return True

    def record_result(self, trade_key: str, result: dict[str, object]) -> bool:
        if str(result.get("trade_key", "")) != trade_key:
            raise ValueError("result trade_key does not match source event")
        if result.get("status") not in FINAL_STATUSES:
            raise ValueError("only terminal candidate outcomes may be journaled")
        result_hash = _hash(result)
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            if db.execute("SELECT 1 FROM source_events WHERE trade_key=?", (trade_key,)).fetchone() is None:
                raise ValueError(f"unknown source event: {trade_key}")
            existing = db.execute(
                "SELECT result_hash FROM candidate_results WHERE trade_key=?", (trade_key,)
            ).fetchone()
            if existing:
                if existing[0] != result_hash:
                    raise ValueError(f"immutable candidate result mismatch for {trade_key}")
                return False
            db.execute(
                "INSERT INTO candidate_results VALUES (?,?,?,?)",
                (trade_key, result_hash, encoded, _now()),
            )
            db.execute(
                "INSERT INTO audit_log(event_type,trade_key,payload_hash,recorded_at) VALUES (?,?,?,?)",
                ("append_candidate_result", trade_key, result_hash, _now()),
            )
        return True

    def counts(self) -> dict[str, int]:
        with sqlite3.connect(self.path) as db:
            events = int(db.execute("SELECT COUNT(*) FROM source_events").fetchone()[0])
            results = int(db.execute("SELECT COUNT(*) FROM candidate_results").fetchone()[0])
        return {"source_events": events, "terminal_results": results}
