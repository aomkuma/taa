"""Exploratory causal M15-M30-H1 ATR pause-gate backtest for frozen TR3 rows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TR1_DIR = ROOT / "research" / "2026-10-20-trend-runner"
sys.path.insert(0, str(TR1_DIR))

from tr1.bars import aggregate, atr  # noqa: E402
from tr1.boundaries import Period, PeriodName  # noqa: E402
from tr1.data import load_m1  # noqa: E402


OUT = Path(__file__).resolve().parent
PREDICTIONS = ROOT / "research" / "2026-10-20-trend-runner-r3" / "predictions_primary.parquet"
M1_PATH = ROOT / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
DESIGN_PERIOD = Period(
    PeriodName.P1,
    pd.Timestamp("2025-10-18 00:00:00", tz="UTC"),
    pd.Timestamp("2026-04-18 00:00:00", tz="UTC"),
)
LOOKBACK_HOURS = 120
RULES = [(80, 70, "PRIMARY_80_70"), (75, 65, "SENSITIVITY_75_65"), (85, 75, "SENSITIVITY_85_75")]


def m30_bars(m1: pd.DataFrame) -> pd.DataFrame:
    """Aggregate M1 to UTC M30 bars with the same clock-end availability convention."""
    key = m1.index.floor("30min")
    grouped = m1.assign(_key=key, _source_time=m1.index).groupby("_key", sort=True)
    bars = pd.DataFrame(
        {
            "open": grouped["open"].first(),
            "high": grouped["high"].max(),
            "low": grouped["low"].min(),
            "close": grouped["close"].last(),
            "tick_volume": grouped["tick_volume"].sum(),
            "spread": grouped["spread"].last(),
            "last": grouped["_source_time"].max(),
        }
    )
    bars.index.name = "open_time"
    bars["close_time"] = bars.index + pd.Timedelta(minutes=30)
    bars["avail"] = bars["close_time"]
    return bars


def volatility_frame(bars: pd.DataFrame, minutes_per_bar: int, name: str) -> pd.DataFrame:
    values = atr(
        bars["high"].to_numpy(float),
        bars["low"].to_numpy(float),
        bars["close"].to_numpy(float),
        14,
    )
    # Compare each current ATR with the preceding 120 hours of ATRs, excluding current.
    lookback = LOOKBACK_HOURS * 60 // minutes_per_bar
    series = pd.Series(values, index=bars["avail"])

    def rank_current(window: np.ndarray) -> float:
        prior, current = window[:-1], window[-1]
        return float(np.mean(prior <= current))

    percentile = series.rolling(lookback + 1, min_periods=lookback + 1).apply(rank_current, raw=True)
    result = pd.DataFrame(
        {
            f"atr_{name}": values,
            f"atr_pct_{name}": percentile.to_numpy(float),
        },
        index=bars["avail"],
    )
    result.index.name = "available_at"
    return result.reset_index()


def attach_last_completed(frame: pd.DataFrame, features: pd.DataFrame, name: str) -> pd.DataFrame:
    renamed = features.rename(columns={"available_at": f"available_{name}"})
    left = frame.sort_values("decision_time").copy()
    right = renamed.sort_values(f"available_{name}")
    left["decision_time"] = pd.to_datetime(left["decision_time"], utc=True).astype("datetime64[ns, UTC]")
    right[f"available_{name}"] = pd.to_datetime(
        right[f"available_{name}"], utc=True
    ).astype("datetime64[ns, UTC]")
    joined = pd.merge_asof(
        left,
        right,
        left_on="decision_time",
        right_on=f"available_{name}",
        direction="backward",
        allow_exact_matches=True,
    )
    if (joined[f"available_{name}"] > joined["decision_time"]).any():
        raise AssertionError(f"future {name} bar attached to an opportunity")
    return joined


def metrics(returns: pd.Series) -> dict[str, float | int]:
    r = returns.astype(float).reset_index(drop=True)
    if r.empty:
        return {
            "trades": 0,
            "total_r": 0.0,
            "mean_r": float("nan"),
            "win_rate": float("nan"),
            "max_drawdown_r": 0.0,
            "max_losing_streak": 0,
            "total_without_best": 0.0,
            "total_without_best_three": 0.0,
        }
    cumulative = r.cumsum()
    drawdown = cumulative.cummax().clip(lower=0) - cumulative
    streak = 0
    max_streak = 0
    for value in r:
        streak = streak + 1 if value <= 0 else 0
        max_streak = max(max_streak, streak)
    total = float(r.sum())
    return {
        "trades": int(len(r)),
        "total_r": total,
        "mean_r": float(r.mean()),
        "win_rate": float((r > 0).mean()),
        "max_drawdown_r": float(drawdown.max()),
        "max_losing_streak": int(max_streak),
        "total_without_best": float(total - r.max()),
        "total_without_best_three": float(total - r.nlargest(min(3, len(r))).sum()),
    }


def apply_pause_gate(
    data: pd.DataFrame,
    *,
    upper: float,
    lower: float,
    action_col: str,
    return_col: str,
) -> tuple[pd.Series, dict[str, int]]:
    paused = False
    keep: list[bool] = []
    pause_transitions = 0
    resume_transitions = 0
    paused_opportunities = 0
    for row in data.itertuples(index=False):
        score = float(row.atr_composite_pct)
        if not paused and score > upper:
            paused = True
            pause_transitions += 1
        elif paused and score <= lower:
            paused = False
            resume_transitions += 1
        enabled = not paused
        paused_opportunities += int(not enabled)
        action = getattr(row, action_col)
        keep.append(enabled and action)
    selected = data.loc[np.asarray(keep, dtype=bool), return_col]
    return selected, {
        "pause_transitions": pause_transitions,
        "resume_transitions": resume_transitions,
        "paused_opportunities": paused_opportunities,
    }


def summarize_atr_groups(
    data: pd.DataFrame,
    mask: pd.Series,
    label: str,
    return_col: str,
) -> list[dict[str, object]]:
    subset = data.loc[mask].copy()
    if subset.empty:
        return []
    subset["outcome"] = np.where(subset[return_col] > 0, "WIN", "NON_POSITIVE")
    rows: list[dict[str, object]] = []
    for outcome, group in subset.groupby("outcome", sort=True):
        row: dict[str, object] = {"population": label, "outcome": outcome, "trades": int(len(group))}
        for tf in ("m15", "m30", "h1"):
            for suffix, value in (
                ("atr_median", group[f"atr_{tf}"].median()),
                ("atr_q25", group[f"atr_{tf}"].quantile(0.25)),
                ("atr_q75", group[f"atr_{tf}"].quantile(0.75)),
                ("pct_median", group[f"atr_pct_{tf}"].median()),
            ):
                row[f"{tf}_{suffix}"] = float(value)
        row["composite_pct_median"] = float(group["atr_composite_pct"].median())
        rows.append(row)
    return rows


def main() -> None:
    predictions = pd.read_parquet(PREDICTIONS)
    if len(predictions) != 210 or set(predictions["action"]) - {"RUNNER", "SKIP"}:
        raise AssertionError("unexpected TR3 primary rows/actions")
    predictions["entry_time"] = pd.to_datetime(predictions["entry_time"], utc=True)
    exam_start = pd.Timestamp("2026-04-18 00:00:00", tz="UTC")
    if predictions["entry_time"].max() >= exam_start:
        raise AssertionError("TR3 input crosses the locked exam boundary")

    m1 = load_m1(M1_PATH, DESIGN_PERIOD)
    if m1.index.max() >= exam_start:
        raise AssertionError("M1 loader returned a row at/after the locked exam boundary")

    bars_by_tf = {
        "m15": (aggregate(m1, "15min"), 15),
        "m30": (m30_bars(m1), 30),
        "h1": (aggregate(m1, "1h"), 60),
    }
    data = predictions.copy()
    for name, (bars, minutes) in bars_by_tf.items():
        features = volatility_frame(bars, minutes, name)
        data = attach_last_completed(data, features, name)
    feature_cols = [f"atr_pct_{tf}" for tf in ("m15", "m30", "h1")]
    if data[feature_cols].isna().any().any():
        raise AssertionError("missing causal MTF ATR percentile for one or more scored opportunities")
    data["atr_composite_pct"] = data[feature_cols].median(axis=1)
    data = data.sort_values("decision_time").reset_index(drop=True)

    run_rows = data["action"].eq("RUNNER")
    output_rows: list[dict[str, object]] = []
    output_rows.append({"rule": "UNFILTERED_TR3_PRIMARY", "control": "TR3_PRIMARY", **metrics(data.loc[run_rows, "selected_r"]), "blocked": 0, "pause_transitions": 0, "resume_transitions": 0, "paused_opportunities": 0})
    output_rows.append({"rule": "UNFILTERED_ALWAYS_RUNNER", "control": "ALWAYS_RUNNER", **metrics(data["runner_r"]), "blocked": 0, "pause_transitions": 0, "resume_transitions": 0, "paused_opportunities": 0})
    period_rows: list[dict[str, object]] = []
    for control, base_indices, return_col in (
        ("TR3_PRIMARY", data.index[run_rows], "selected_r"),
        ("ALWAYS_RUNNER", data.index, "runner_r"),
    ):
        selected_data = data.loc[base_indices]
        for source_period, group in selected_data.groupby("source_period", sort=True):
            period_rows.append(
                {
                    "rule": "UNFILTERED",
                    "control": control,
                    "source_period": source_period,
                    **metrics(group[return_col]),
                }
            )

    for upper_pct, lower_pct, rule_name in RULES:
        upper, lower = upper_pct / 100.0, lower_pct / 100.0
        for control, action_col, return_col in (
            ("TR3_PRIMARY", "is_runner", "selected_r"),
            ("ALWAYS_RUNNER", "is_always", "runner_r"),
        ):
            data[action_col] = data["action"].eq("RUNNER") if control == "TR3_PRIMARY" else True
            selected, transitions = apply_pause_gate(
                data,
                upper=upper,
                lower=lower,
                action_col=action_col,
                return_col=return_col,
            )
            base_n = int(run_rows.sum()) if control == "TR3_PRIMARY" else len(data)
            result = {
                "rule": rule_name,
                "control": control,
                **metrics(selected),
                "blocked": base_n - len(selected),
                **transitions,
            }
            output_rows.append(result)
            selected_indices = selected.index
            selected_data = data.loc[selected_indices]
            for source_period, group in selected_data.groupby("source_period", sort=True):
                period_rows.append(
                    {
                        "rule": rule_name,
                        "control": control,
                        "source_period": source_period,
                        **metrics(group[return_col]),
                    }
                )

    summary = pd.DataFrame(output_rows)
    summary.to_csv(OUT / "backtest_summary.csv", index=False, float_format="%.8f")
    pd.DataFrame(period_rows).to_csv(OUT / "period_breakdown.csv", index=False, float_format="%.8f")
    data.to_parquet(OUT / "opportunities_with_mtf_atr.parquet", index=False)
    atr_groups = summarize_atr_groups(data, run_rows, "TR3_PRIMARY_EXECUTED", "selected_r")
    atr_groups += summarize_atr_groups(
        data,
        pd.Series(True, index=data.index),
        "ALL_210_ALWAYS_RUNNER_OUTCOMES",
        "runner_r",
    )
    (OUT / "atr_by_outcome.json").write_text(json.dumps(atr_groups, indent=2), encoding="utf-8")

    metadata = {
        "status": "EXPLORATORY_SEEN_DEVELOPMENT_DATA_NOT_VALIDATED",
        "exam_read": False,
        "design_opportunities": int(len(data)),
        "date_start": str(data["entry_time"].min()),
        "date_end": str(data["entry_time"].max()),
        "executed_tr3_baseline": int(run_rows.sum()),
        "m1_rows_loaded": int(len(m1)),
        "last_m1_open_time": str(m1.index.max()),
        "m1_exclusive_end": str(exam_start),
        "slippage_included": False,
        "atr_length": 14,
        "percentile_lookback_h1_bar_equivalent": LOOKBACK_HOURS,
        "percentile_lookbacks_bars": {"M15": 480, "M30": 240, "H1": 120},
        "composite": "median(M15, M30, H1 ATR percentiles)",
        "pause_resume_pairs_upper_lower_pct": [[upper, lower] for upper, lower, _ in RULES],
        "pause_state_updated_at": "each scored opportunity decision_time only",
        "pnl_usd_constant_risk_10": "total_r * 10",
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nBy source period:")
    print(pd.DataFrame(period_rows).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nATR by outcome (selected fields):")
    for row in atr_groups:
        print(
            row["population"], row["outcome"], "n=", row["trades"],
            "M15 ATR median/IQR=", round(row["m15_atr_median"], 3),
            round(row["m15_atr_q25"], 3), round(row["m15_atr_q75"], 3),
            "M30=", round(row["m30_atr_median"], 3),
            "H1=", round(row["h1_atr_median"], 3),
            "composite pct=", round(row["composite_pct_median"], 3),
        )
    print("\nSaved outputs to", OUT)


if __name__ == "__main__":
    main()
