"""Strict forward event schemas and canonical hashing."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

COLLECTION_START = pd.Timestamp("2026-10-21T00:00:00Z")
FEATURE_COLUMNS = (
    "h1_flow_6_atr",
    "h4_flow_3_atr",
    "open_space_atr",
    "h1_atr_percentile_120",
    "risk_h1_feature",
    "pullback_ratio_feature",
    "anchor_entry_minutes",
    "side_feature",
    "session_asia",
    "session_london",
    "prior_session_runner_edge",
)
WINDOWS = {"ASIA", "LONDON", "NY0830"}


def utc(value: object, *, field: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None or str(timestamp.tz) != "UTC":
        raise ValueError(f"{field} must be timezone-aware UTC")
    return timestamp


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _finite(value: object, *, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


@dataclass(frozen=True)
class Opportunity:
    trade_key: str
    entry_time: pd.Timestamp
    anchor: pd.Timestamp
    window: str
    side: int
    entry: float
    spread: float
    stop: float
    risk: float
    features: dict[str, float]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Opportunity:
        required = {
            "trade_key",
            "entry_time",
            "anchor",
            "window",
            "side",
            "entry",
            "spread",
            "stop",
            "risk",
            "features",
        }
        if set(raw) != required:
            raise ValueError(f"opportunity fields must be exactly {sorted(required)}")
        entry_time = utc(raw["entry_time"], field="entry_time")
        anchor = utc(raw["anchor"], field="anchor")
        if entry_time < COLLECTION_START:
            raise ValueError("opportunity predates forward collection boundary")
        if anchor > entry_time:
            raise ValueError("anchor cannot follow entry")
        window = str(raw["window"])
        if window not in WINDOWS:
            raise ValueError(f"unsupported session: {window}")
        side = int(raw["side"])
        if side not in (-1, 1):
            raise ValueError("side must be -1 or +1")
        entry = _finite(raw["entry"], field="entry")
        spread = _finite(raw["spread"], field="spread")
        if spread < 0:
            raise ValueError("spread must be non-negative")
        stop = _finite(raw["stop"], field="stop")
        risk = _finite(raw["risk"], field="risk")
        if risk <= 0 or not math.isclose((entry - stop) * side, risk, rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError("risk must equal side * (entry - stop) and be positive")
        raw_features = raw["features"]
        if not isinstance(raw_features, dict) or set(raw_features) != set(FEATURE_COLUMNS):
            raise ValueError("features must contain exactly the frozen 11 columns")
        features = {name: _finite(raw_features[name], field=name) for name in FEATURE_COLUMNS}
        if features["side_feature"] != side:
            raise ValueError("side_feature must equal side")
        if features["session_asia"] != float(window == "ASIA"):
            raise ValueError("session_asia does not match window")
        if features["session_london"] != float(window == "LONDON"):
            raise ValueError("session_london does not match window")
        key = str(raw["trade_key"]).strip()
        if not key or len(key) > 128:
            raise ValueError("trade_key must contain 1-128 characters")
        return cls(key, entry_time, anchor, window, side, entry, spread, stop, risk, features)

    def payload(self) -> dict[str, Any]:
        return {
            "trade_key": self.trade_key,
            "entry_time": self.entry_time.isoformat(),
            "anchor": self.anchor.isoformat(),
            "window": self.window,
            "side": self.side,
            "entry": self.entry,
            "spread": self.spread,
            "stop": self.stop,
            "risk": self.risk,
            "features": self.features,
        }


@dataclass(frozen=True)
class Outcome:
    trade_key: str
    fast_exit_time: pd.Timestamp
    runner_exit_time: pd.Timestamp
    fast_r: float
    runner_r: float
    fast_usd_fixed_001: float
    runner_usd_fixed_001: float

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Outcome:
        required = {
            "trade_key",
            "fast_exit_time",
            "runner_exit_time",
            "fast_r",
            "runner_r",
            "fast_usd_fixed_001",
            "runner_usd_fixed_001",
        }
        if set(raw) != required:
            raise ValueError(f"outcome fields must be exactly {sorted(required)}")
        key = str(raw["trade_key"]).strip()
        return cls(
            key,
            utc(raw["fast_exit_time"], field="fast_exit_time"),
            utc(raw["runner_exit_time"], field="runner_exit_time"),
            _finite(raw["fast_r"], field="fast_r"),
            _finite(raw["runner_r"], field="runner_r"),
            _finite(raw["fast_usd_fixed_001"], field="fast_usd_fixed_001"),
            _finite(raw["runner_usd_fixed_001"], field="runner_usd_fixed_001"),
        )

    @property
    def outcome_available(self) -> pd.Timestamp:
        return max(self.fast_exit_time, self.runner_exit_time)

    def payload(self) -> dict[str, Any]:
        return {
            "trade_key": self.trade_key,
            "fast_exit_time": self.fast_exit_time.isoformat(),
            "runner_exit_time": self.runner_exit_time.isoformat(),
            "outcome_available": self.outcome_available.isoformat(),
            "fast_r": self.fast_r,
            "runner_r": self.runner_r,
            "fast_usd_fixed_001": self.fast_usd_fixed_001,
            "runner_usd_fixed_001": self.runner_usd_fixed_001,
        }
