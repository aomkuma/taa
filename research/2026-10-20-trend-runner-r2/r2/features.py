"""Causal feature panel for the fixed TR1 opportunity population."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .bars import add_atr, clock_bars, completed_trading_days, last_available_index

FEATURE_COLUMNS = [
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
]


def _price_features(
    entry: pd.Series,
    h1: pd.DataFrame,
    h4: pd.DataFrame,
    daily: pd.DataFrame,
) -> dict[str, float]:
    timestamp = pd.Timestamp(entry["entry_time"])
    side = int(entry["side"])
    h1_index = last_available_index(h1["available_at"], timestamp)
    h4_index = last_available_index(h4["available_at"], timestamp)
    day_index = last_available_index(daily["available_at"], timestamp)
    if h1_index is None:
        raise ValueError(f"No completed H1 bar for {entry['trade_key']}")

    atr = float(h1.iloc[h1_index]["atr"])
    h1_flow = np.nan
    if h1_index >= 6 and np.isfinite(atr) and atr > 0:
        h1_flow = side * (float(h1.iloc[h1_index]["close"]) - float(h1.iloc[h1_index - 6]["close"])) / atr
    h4_flow = np.nan
    if h4_index is not None and h4_index >= 3 and np.isfinite(atr) and atr > 0:
        h4_flow = side * (float(h4.iloc[h4_index]["close"]) - float(h4.iloc[h4_index - 3]["close"])) / atr

    previous_atrs = h1.iloc[max(0, h1_index - 120) : h1_index]["atr"].dropna().to_numpy(dtype=float)
    atr_percentile = np.nan
    if len(previous_atrs) >= 20 and np.isfinite(atr):
        atr_percentile = float(np.mean(previous_atrs <= atr))

    recent = h1.iloc[max(0, h1_index - 19) : h1_index + 1]
    level_values: list[float] = []
    if not recent.empty:
        level_values.append(float(recent["high"].max() if side == 1 else recent["low"].min()))
    if day_index is not None:
        level_values.append(float(daily.iloc[day_index]["high" if side == 1 else "low"]))
    entry_price = float(entry["entry"])
    positive_distances = [
        side * (level - entry_price) for level in level_values if side * (level - entry_price) > 0
    ]
    if not np.isfinite(atr) or atr <= 0:
        open_space = np.nan
    elif positive_distances:
        open_space = float(np.clip(min(positive_distances) / atr, 0.0, 5.0))
    else:
        open_space = 5.0

    return {
        "h1_flow_6_atr": float(h1_flow),
        "h4_flow_3_atr": float(h4_flow),
        "open_space_atr": float(open_space),
        "h1_atr_percentile_120": float(atr_percentile),
    }


def add_prior_session_edge(panel: pd.DataFrame) -> pd.DataFrame:
    """Use only prior same-session outcomes fully available at this entry."""
    result = panel.copy()
    values: list[float] = []
    for row in result.itertuples(index=False):
        eligible = result.loc[
            (result["window"] == row.window)
            & (result["entry_time"] < row.entry_time)
            & (result["outcome_available"] < row.entry_time)
        ].sort_values("outcome_available")
        eligible = eligible.tail(20)
        edge = 0.0 if len(eligible) < 5 else float((eligible["runner_r"] - eligible["fast_r"]).mean())
        values.append(float(np.clip(edge, -2.0, 2.0)))
    result["prior_session_runner_edge"] = values
    return result


def build_feature_panel(entries: pd.DataFrame, m1: pd.DataFrame, *, cutoff: pd.Timestamp) -> pd.DataFrame:
    h1 = add_atr(clock_bars(m1, "1h", cutoff=cutoff))
    h4 = clock_bars(m1, "4h", cutoff=cutoff)
    daily = completed_trading_days(m1, cutoff=cutoff)
    rows: list[dict[str, float]] = []
    for _, entry in entries.iterrows():
        if pd.Timestamp(entry["entry_time"]) >= pd.Timestamp(cutoff):
            continue
        features = _price_features(entry, h1, h4, daily)
        minutes = (pd.Timestamp(entry["entry_time"]) - pd.Timestamp(entry["anchor"])).total_seconds() / 60.0
        features.update(
            {
                "trade_key": entry["trade_key"],
                "risk_h1_feature": float(entry["risk_h1"]),
                "pullback_ratio_feature": float(entry["pullback_ratio"]),
                "anchor_entry_minutes": float(np.clip(minutes, 0.0, 240.0)),
                "side_feature": float(entry["side"]),
                "session_asia": float(entry["window"] == "ASIA"),
                "session_london": float(entry["window"] == "LONDON"),
            }
        )
        rows.append(features)
    feature_frame = pd.DataFrame(rows)
    result = entries.merge(feature_frame, on="trade_key", how="inner", validate="one_to_one")
    result = result.sort_values(["entry_time", "trade_key"]).reset_index(drop=True)
    return add_prior_session_edge(result)
