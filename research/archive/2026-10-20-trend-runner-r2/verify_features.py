"""Independent feature recomputation and real-data truncation checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from r2.boundaries import DESIGN_END  # noqa: E402
from r2.data import load_design_m1, load_entries_and_outcomes  # noqa: E402
from r2.features import FEATURE_COLUMNS, build_feature_panel  # noqa: E402


def independent_panel(entries: pd.DataFrame, m1: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Recompute formulas directly without importing the production bars or feature helpers."""
    raw = m1.set_index(pd.DatetimeIndex(m1["open_time"]))

    def aggregate(rule: str) -> pd.DataFrame:
        frame = raw.resample(rule, label="left", closed="left").agg(
            high=("high", "max"), low=("low", "min"), close=("close", "last")
        )
        frame = frame.dropna().reset_index(names="start")
        frame["available"] = frame["start"] + pd.tseries.frequencies.to_offset(rule)
        return frame.loc[frame["available"] <= cutoff].reset_index(drop=True)

    h1 = aggregate("1h")
    previous_close = h1["close"].shift()
    ranges = pd.concat(
        [h1["high"] - h1["low"], (h1["high"] - previous_close).abs(), (h1["low"] - previous_close).abs()],
        axis=1,
    )
    h1["atr"] = ranges.max(axis=1).rolling(14, min_periods=14).mean()
    h4 = aggregate("4h")
    raw_daily = m1.assign(day=pd.to_datetime(m1["open_time"], utc=True).dt.floor("D"))
    daily = raw_daily.groupby("day").agg(high=("high", "max"), low=("low", "min")).reset_index()
    daily["available"] = daily["day"] + pd.Timedelta(days=1)
    daily = daily.loc[daily["available"] <= cutoff].reset_index(drop=True)

    records: list[dict[str, object]] = []
    ordered = entries.loc[entries["entry_time"] < cutoff].sort_values(["entry_time", "trade_key"])
    for row in ordered.itertuples(index=False):
        earlier_h1 = h1.loc[h1["available"] <= row.entry_time]
        earlier_h4 = h4.loc[h4["available"] <= row.entry_time]
        earlier_days = daily.loc[daily["available"] <= row.entry_time]
        current = earlier_h1.iloc[-1]
        atr = float(current["atr"])
        side = int(row.side)
        h1_flow = side * (float(current["close"]) - float(earlier_h1.iloc[-7]["close"])) / atr
        h4_flow = side * (float(earlier_h4.iloc[-1]["close"]) - float(earlier_h4.iloc[-4]["close"])) / atr
        history = earlier_h1.iloc[-121:-1]["atr"].dropna().to_numpy()
        atr_percentile = float(np.mean(history <= atr))
        recent = earlier_h1.iloc[-20:]
        levels = [float(recent["high"].max() if side == 1 else recent["low"].min())]
        if not earlier_days.empty:
            levels.append(float(earlier_days.iloc[-1]["high" if side == 1 else "low"]))
        distances = [side * (level - row.entry) for level in levels if side * (level - row.entry) > 0]
        open_space = 5.0 if not distances else float(np.clip(min(distances) / atr, 0.0, 5.0))
        prior = ordered.loc[
            (ordered["window"] == row.window)
            & (ordered["entry_time"] < row.entry_time)
            & (ordered["outcome_available"] < row.entry_time)
        ].sort_values("outcome_available").tail(20)
        prior_edge = 0.0 if len(prior) < 5 else float((prior["runner_r"] - prior["fast_r"]).mean())
        minutes = (row.entry_time - row.anchor).total_seconds() / 60.0
        records.append(
            {
                "trade_key": row.trade_key,
                "h1_flow_6_atr": h1_flow,
                "h4_flow_3_atr": h4_flow,
                "open_space_atr": open_space,
                "h1_atr_percentile_120": atr_percentile,
                "risk_h1_feature": float(row.risk_h1),
                "pullback_ratio_feature": float(row.pullback_ratio),
                "anchor_entry_minutes": float(np.clip(minutes, 0.0, 240.0)),
                "side_feature": float(side),
                "session_asia": float(row.window == "ASIA"),
                "session_london": float(row.window == "LONDON"),
                "prior_session_runner_edge": float(np.clip(prior_edge, -2.0, 2.0)),
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    entries = load_entries_and_outcomes()
    m1 = load_design_m1()
    production = build_feature_panel(entries, m1, cutoff=DESIGN_END)
    independent = independent_panel(entries, m1, DESIGN_END)
    comparison = production[["trade_key", *FEATURE_COLUMNS]].merge(
        independent, on="trade_key", suffixes=("_production", "_independent"), validate="one_to_one"
    )
    independent_errors = {
        name: float(np.max(np.abs(comparison[f"{name}_production"] - comparison[f"{name}_independent"])))
        for name in FEATURE_COLUMNS
    }
    if any(value > 1e-10 for value in independent_errors.values()):
        raise AssertionError(f"Independent recomputation mismatch: {independent_errors}")

    truncation: dict[str, dict[str, object]] = {}
    for text in ("2025-12-15T00:00:00Z", "2026-02-16T00:00:00Z", "2026-04-10T00:00:00Z"):
        cutoff = pd.Timestamp(text)
        short_m1 = load_design_m1(end=cutoff)
        short = build_feature_panel(entries, short_m1, cutoff=cutoff)
        expected = production.loc[production["entry_time"] < cutoff, ["trade_key", *FEATURE_COLUMNS]]
        merged = expected.merge(short[["trade_key", *FEATURE_COLUMNS]], on="trade_key", suffixes=("_full", "_cut"))
        maximum = max(
            float(np.max(np.abs(merged[f"{name}_full"] - merged[f"{name}_cut"])))
            for name in FEATURE_COLUMNS
        )
        if len(merged) != len(expected) or maximum > 1e-10:
            raise AssertionError(f"Truncation failure at {text}: rows={len(merged)}/{len(expected)}, max={maximum}")
        truncation[text] = {"rows": len(merged), "maximum_absolute_error": maximum}

    report = {
        "status": "PASS",
        "rows": len(production),
        "independent_maximum_absolute_error": independent_errors,
        "truncation": truncation,
        "exam_read": False,
    }
    (ROOT / "feature_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    production.to_parquet(ROOT / "feature_panel.parquet", index=False)


if __name__ == "__main__":
    main()
