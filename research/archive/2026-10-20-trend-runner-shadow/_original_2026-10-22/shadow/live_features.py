"""Causal entry-time features for adapter-emitted opportunities."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .detector import Detection, aggregate, atr
from .journal import ShadowJournal
from .schema import FEATURE_COLUMNS


def _prior_session_edge(journal: ShadowJournal, window: str, entry_time: pd.Timestamp) -> float:
    opportunities = journal.opportunities()
    outcomes = journal.outcomes()
    if opportunities.empty or outcomes.empty:
        return 0.0
    history = opportunities[["trade_key", "entry_time", "window"]].merge(
        outcomes[["trade_key", "outcome_available", "fast_r", "runner_r"]],
        on="trade_key",
        validate="one_to_one",
    )
    history["entry_time"] = pd.to_datetime(history["entry_time"], utc=True)
    history["outcome_available"] = pd.to_datetime(history["outcome_available"], utc=True)
    eligible = history.loc[
        (history["window"] == window)
        & (history["entry_time"] < entry_time)
        & (history["outcome_available"] < entry_time)
    ].sort_values("outcome_available").tail(20)
    if len(eligible) < 5:
        return 0.0
    return float(np.clip((eligible["runner_r"] - eligible["fast_r"]).mean(), -2.0, 2.0))


def build_features(
    m1: pd.DataFrame,
    detection: Detection,
    fill: dict[str, object],
    journal: ShadowJournal,
) -> dict[str, float]:
    entry_time = pd.Timestamp(fill["entry_time"])
    h1 = aggregate(m1, "1h")
    h4 = aggregate(m1, "4h")
    h1["atr"] = atr(h1["high"].to_numpy(), h1["low"].to_numpy(), h1["close"].to_numpy())
    h1 = h1.loc[h1["avail"] <= entry_time]
    h4 = h4.loc[h4["avail"] <= entry_time]
    if len(h1) < 121 or len(h4) < 4:
        raise ValueError("insufficient completed history for frozen features")
    current_atr = float(h1.iloc[-1]["atr"])
    side = detection.side
    h1_flow = side * (float(h1.iloc[-1]["close"]) - float(h1.iloc[-7]["close"])) / current_atr
    h4_flow = side * (float(h4.iloc[-1]["close"]) - float(h4.iloc[-4]["close"])) / current_atr
    previous_atrs = h1.iloc[-121:-1]["atr"].dropna().to_numpy(dtype=float)
    atr_percentile = float(np.mean(previous_atrs <= current_atr))

    recent = h1.iloc[-20:]
    levels = [float(recent["high"].max() if side > 0 else recent["low"].min())]
    raw = m1.copy()
    raw["day"] = raw.index.floor("D")
    entry_day = entry_time.floor("D")
    earlier = raw.loc[raw["day"] < entry_day]
    if not earlier.empty:
        previous_day = earlier.groupby("day").agg(high=("high", "max"), low=("low", "min")).iloc[-1]
        levels.append(float(previous_day["high" if side > 0 else "low"]))
    entry = float(fill["entry"])
    distances = [side * (level - entry) for level in levels if side * (level - entry) > 0]
    open_space = 5.0 if not distances else float(np.clip(min(distances) / current_atr, 0.0, 5.0))
    minutes = (entry_time - detection.anchor).total_seconds() / 60.0
    features = {
        "h1_flow_6_atr": float(h1_flow),
        "h4_flow_3_atr": float(h4_flow),
        "open_space_atr": open_space,
        "h1_atr_percentile_120": atr_percentile,
        "risk_h1_feature": float(fill["risk_h1"]),
        "pullback_ratio_feature": detection.pullback_ratio,
        "anchor_entry_minutes": float(np.clip(minutes, 0.0, 240.0)),
        "side_feature": float(side),
        "session_asia": float(detection.window == "ASIA"),
        "session_london": float(detection.window == "LONDON"),
        "prior_session_runner_edge": _prior_session_edge(
            journal, detection.window, entry_time
        ),
    }
    if set(features) != set(FEATURE_COLUMNS):
        raise AssertionError("adapter feature vector drifted from schema")
    return features
