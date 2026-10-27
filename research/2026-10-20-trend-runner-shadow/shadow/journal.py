"""Append-only SQLite journal. It has no order or broker capability."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .schema import Opportunity, Outcome, canonical_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
  trade_key TEXT PRIMARY KEY, entry_time TEXT NOT NULL, window TEXT NOT NULL, side INTEGER NOT NULL,
  event_hash TEXT NOT NULL, payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (
  trade_key TEXT PRIMARY KEY REFERENCES opportunities(trade_key), exit_time TEXT NOT NULL,
  event_hash TEXT NOT NULL, payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  policy TEXT NOT NULL, trade_key TEXT NOT NULL REFERENCES opportunities(trade_key), status TEXT NOT NULL,
  action TEXT, reason TEXT NOT NULL, model_month TEXT NOT NULL, model_hash TEXT,
  predictions_json TEXT NOT NULL, decision_hash TEXT NOT NULL, recorded_at TEXT NOT NULL,
  PRIMARY KEY (policy, trade_key)
);
CREATE TABLE IF NOT EXISTS model_snapshots (
  model_month TEXT NOT NULL, window_days INTEGER NOT NULL, model_hash TEXT NOT NULL,
  train_count INTEGER NOT NULL, payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
  PRIMARY KEY (model_month, window_days)
);
CREATE TABLE IF NOT EXISTS audit_log (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, entity_key TEXT NOT NULL,
  event_hash TEXT NOT NULL, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adapter_anchors (
  anchor_id TEXT PRIMARY KEY, anchor_time TEXT NOT NULL, window TEXT NOT NULL, status TEXT NOT NULL,
  input_hash TEXT NOT NULL, details_json TEXT NOT NULL, recorded_at TEXT NOT NULL
);
"""


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


class ShadowJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def _append(
        self,
        table: str,
        key_column: str,
        key: str,
        payload: dict[str, object],
        extras: dict[str, object],
    ) -> bool:
        if table not in {"opportunities", "outcomes"} or key_column != "trade_key":
            raise ValueError("unsupported journal table")
        event_hash = canonical_hash(payload)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self.connect() as connection:
            existing = connection.execute(
                f"SELECT event_hash FROM {table} WHERE {key_column} = ?",  # noqa: S608
                (key,),
            ).fetchone()
            if existing:
                if existing[0] != event_hash:
                    raise ValueError(f"immutable {table} payload mismatch for {key}")
                return False
            columns = [key_column, *extras, "event_hash", "payload_json", "recorded_at"]
            values = [key, *extras.values(), event_hash, payload_json, now_utc()]
            placeholders = ",".join("?" for _ in columns)
            connection.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",  # noqa: S608
                values,
            )
            connection.execute(
                "INSERT INTO audit_log(event_type,entity_key,event_hash,recorded_at) VALUES (?,?,?,?)",
                (f"append_{table}", key, event_hash, now_utc()),
            )
        return True

    def record_opportunity(self, opportunity: Opportunity) -> bool:
        existing = self.opportunity(opportunity.trade_key)
        if existing is None:
            with self.connect() as connection:
                latest = connection.execute("SELECT MAX(entry_time) FROM opportunities").fetchone()[0]
            if latest is not None and opportunity.entry_time < pd.Timestamp(latest):
                raise ValueError("opportunities must be ingested in nondecreasing entry-time order")
        return self._append(
            "opportunities",
            "trade_key",
            opportunity.trade_key,
            opportunity.payload(),
            {
                "entry_time": opportunity.entry_time.isoformat(),
                "window": opportunity.window,
                "side": opportunity.side,
            },
        )

    def record_outcome(self, outcome: Outcome) -> bool:
        opportunity = self.opportunity(outcome.trade_key)
        if opportunity is None:
            raise ValueError(f"unknown trade_key: {outcome.trade_key}")
        with self.connect() as connection:
            decision_count = connection.execute(
                "SELECT COUNT(*) FROM decisions WHERE trade_key = ?", (outcome.trade_key,)
            ).fetchone()[0]
        if decision_count == 0:
            raise ValueError("score the opportunity before recording its outcome")
        entry_time = pd.Timestamp(opportunity["entry_time"])
        if outcome.fast_exit_time <= entry_time or outcome.runner_exit_time <= entry_time:
            raise ValueError("both outcomes must complete after entry")
        risk = float(opportunity["risk"])
        expected_runner_usd = outcome.runner_r * risk
        expected_fast_usd = outcome.fast_r * risk
        if not math.isclose(
            outcome.runner_usd_fixed_001, expected_runner_usd, rel_tol=1e-8, abs_tol=1e-8
        ):
            raise ValueError("runner_usd_fixed_001 must equal runner_r * initial risk")
        if not math.isclose(
            outcome.fast_usd_fixed_001, expected_fast_usd, rel_tol=1e-8, abs_tol=1e-8
        ):
            raise ValueError("fast_usd_fixed_001 must equal fast_r * initial risk")
        return self._append(
            "outcomes",
            "trade_key",
            outcome.trade_key,
            outcome.payload(),
            {"exit_time": outcome.outcome_available.isoformat()},
        )

    def opportunity(self, trade_key: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM opportunities WHERE trade_key = ?", (trade_key,)
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def opportunities(self) -> pd.DataFrame:
        return self._payload_frame("opportunities")

    def outcomes(self) -> pd.DataFrame:
        return self._payload_frame("outcomes")

    def decisions(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM decisions ORDER BY model_month, trade_key, policy", connection
            )

    def snapshots(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM model_snapshots ORDER BY model_month, window_days", connection
            )

    def snapshot(self, month: str, window_days: int) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM model_snapshots WHERE model_month=? AND window_days=?",
                (month, window_days),
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def _payload_frame(self, table: str) -> pd.DataFrame:
        if table not in {"opportunities", "outcomes"}:
            raise ValueError("unsupported journal table")
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT payload_json FROM {table} ORDER BY rowid"  # noqa: S608
            ).fetchall()
        return pd.DataFrame([json.loads(row[0]) for row in rows])

    def record_snapshot(self, month: str, window_days: int, payload: dict[str, object]) -> str:
        model_hash = canonical_hash(payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT model_hash FROM model_snapshots WHERE model_month=? AND window_days=?",
                (month, window_days),
            ).fetchone()
            if existing:
                if existing[0] != model_hash:
                    raise ValueError(f"immutable model snapshot mismatch for {month}/{window_days}")
                return model_hash
            connection.execute(
                "INSERT INTO model_snapshots VALUES (?,?,?,?,?,?)",
                (month, window_days, model_hash, int(payload["train_count"]), encoded, now_utc()),
            )
        return model_hash

    def record_decision(self, payload: dict[str, object]) -> bool:
        decision_hash = canonical_hash(payload)
        key = (str(payload["policy"]), str(payload["trade_key"]))
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT decision_hash FROM decisions WHERE policy=? AND trade_key=?", key
            ).fetchone()
            if existing:
                if existing[0] != decision_hash:
                    raise ValueError(f"immutable decision mismatch for {key}")
                return False
            connection.execute(
                "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    payload["policy"], payload["trade_key"], payload["status"], payload["action"],
                    payload["reason"], payload["model_month"], payload["model_hash"],
                    json.dumps(payload["predictions"], sort_keys=True, separators=(",", ":")),
                    decision_hash, now_utc(),
                ),
            )
        return True

    def adapter_anchor(self, anchor_id: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT anchor_time,window,status,input_hash,details_json FROM adapter_anchors "
                "WHERE anchor_id=?",
                (anchor_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "anchor_time": row[0],
            "window": row[1],
            "status": row[2],
            "input_hash": row[3],
            "details": json.loads(row[4]),
        }

    def record_adapter_anchor(
        self,
        *,
        anchor_id: str,
        anchor_time: str,
        window: str,
        status: str,
        input_hash: str,
        details: dict[str, object],
    ) -> bool:
        payload = {
            "anchor_time": anchor_time,
            "window": window,
            "status": status,
            "input_hash": input_hash,
            "details": details,
        }
        event_hash = canonical_hash(payload)
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT input_hash,status,details_json FROM adapter_anchors WHERE anchor_id=?",
                (anchor_id,),
            ).fetchone()
            if existing:
                existing_payload = {
                    "anchor_time": anchor_time,
                    "window": window,
                    "status": existing[1],
                    "input_hash": existing[0],
                    "details": json.loads(existing[2]),
                }
                if canonical_hash(existing_payload) != event_hash:
                    raise ValueError(f"immutable adapter anchor mismatch for {anchor_id}")
                return False
            connection.execute(
                "INSERT INTO adapter_anchors VALUES (?,?,?,?,?,?,?)",
                (
                    anchor_id,
                    anchor_time,
                    window,
                    status,
                    input_hash,
                    json.dumps(details, sort_keys=True),
                    now_utc(),
                ),
            )
            connection.execute(
                "INSERT INTO audit_log(event_type,entity_key,event_hash,recorded_at) VALUES (?,?,?,?)",
                ("append_adapter_anchor", anchor_id, event_hash, now_utc()),
            )
        return True

    def adapter_anchors(self) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM adapter_anchors ORDER BY anchor_time, window", connection
            )
