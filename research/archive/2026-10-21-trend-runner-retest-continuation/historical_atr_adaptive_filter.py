"""Per-event, past-only ATR-regime adaptation for the frozen historical candidate."""

# ruff: noqa: E501

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DATA = ROOT / "historical_diagnostic"
M1_PATH = REPO / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
EXAM_START = pd.Timestamp("2026-04-18T00:00:00Z")
DATA_START = pd.Timestamp("2023-09-01T00:00:00Z")
LOOKBACK = pd.Timedelta(weeks=52)
MIN_HISTORY = 5
HIGH_ATR = 0.80

TR1_DIR = REPO / "research" / "2026-10-20-trend-runner"
ATR_DIR = REPO / "research" / "2026-10-21-trend-runner-atr-mtf"
sys.path.insert(0, str(TR1_DIR))
sys.path.insert(0, str(ATR_DIR))
from run_atr_backtest import attach_last_completed, m30_bars, volatility_frame  # noqa: E402
from tr1.bars import aggregate  # noqa: E402


def load_m1() -> pd.DataFrame:
    frame = pd.read_parquet(
        M1_PATH,
        columns=["open_time", "open", "high", "low", "close", "tick_volume", "spread"],
        filters=[
            ("open_time", ">=", DATA_START.to_pydatetime()),
            ("open_time", "<", EXAM_START.to_pydatetime()),
        ],
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame = frame.drop_duplicates("open_time", keep="last").sort_values("open_time").set_index("open_time")
    if frame.empty or frame.index.max() >= EXAM_START or frame.index.min() < DATA_START:
        raise AssertionError("M1 loader returned no data or crossed a declared date boundary")
    return frame


def attach_atr(events: pd.DataFrame, m1: pd.DataFrame) -> pd.DataFrame:
    bars_by_tf = {
        "m15": (aggregate(m1, "15min"), 15),
        "m30": (m30_bars(m1), 30),
        "h1": (aggregate(m1, "1h"), 60),
    }
    features = events.copy()
    features["decision_time"] = features["source_stop_time_utc"]
    for name, (bars, minutes) in bars_by_tf.items():
        volatility = volatility_frame(bars, minutes, name)
        features = attach_last_completed(features, volatility, name)
    availability_columns = [f"available_{name}" for name in ("m15", "m30", "h1")]
    pct_columns = [f"atr_pct_{name}" for name in ("m15", "m30", "h1")]
    if features[pct_columns].isna().any().any() or features[availability_columns].isna().any().any():
        missing = int(features[pct_columns].isna().any(axis=1).sum())
        raise AssertionError(f"causal MTF ATR percentile missing for {missing} source events")
    for name in ("m15", "m30", "h1"):
        if (features[f"available_{name}"] > features["decision_time"]).any():
            raise AssertionError(f"future {name} ATR bar attached to an event")
        features.rename(
            columns={
                f"atr_pct_{name}": f"atr_{name}_pct",
                f"available_{name}": f"atr_{name}_available_at",
            },
            inplace=True,
        )
    features["atr_composite_pct"] = features[[f"atr_{name}_pct" for name in ("m15", "m30", "h1")]].median(
        axis=1
    )
    features["atr_regime"] = np.where(features["atr_composite_pct"] > HIGH_ATR, "HIGH", "NORMAL_OR_LOW")
    return features.sort_values("decision_time").reset_index(drop=True)


def replay(events: pd.DataFrame) -> pd.DataFrame:
    history: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for event in events.itertuples(index=False):
        decision_time = event.decision_time
        lower_bound = decision_time - LOOKBACK
        prior = [
            item
            for item in history
            if item["atr_regime"] == event.atr_regime and lower_bound <= item["exit_time_utc"] < decision_time
        ]
        prior_total = sum(float(item["r"]) for item in prior)
        prior_mean = prior_total / len(prior) if prior else None
        if len(prior) < MIN_HISTORY:
            action = "ALLOW_WARMUP"
        elif prior_mean > 0:
            action = "ALLOW_POSITIVE_TRAILING"
        else:
            action = "BLOCK_NONPOSITIVE_TRAILING"
        allowed = action != "BLOCK_NONPOSITIVE_TRAILING"
        candidate_r = float(event.r) if event.status == "COMPLETE" else np.nan
        selected_r = candidate_r if allowed else np.nan
        blocked_r = candidate_r if not allowed else np.nan
        fixed_atr_allowed = event.atr_regime != "HIGH"
        decisions.append(
            {
                "trade_key": event.trade_key,
                "source_stop_time_utc": decision_time,
                "side": event.side,
                "window": event.window,
                "status": event.status,
                "atr_m15_pct": float(event.atr_m15_pct),
                "atr_m15_available_at": event.atr_m15_available_at,
                "atr_m30_pct": float(event.atr_m30_pct),
                "atr_m30_available_at": event.atr_m30_available_at,
                "atr_h1_pct": float(event.atr_h1_pct),
                "atr_h1_available_at": event.atr_h1_available_at,
                "atr_composite_pct": float(event.atr_composite_pct),
                "atr_regime": event.atr_regime,
                "fixed_atr_action": "ALLOW_NORMAL_OR_LOW" if fixed_atr_allowed else "BLOCK_HIGH_ATR",
                "fixed_atr_selected_r": candidate_r if fixed_atr_allowed else np.nan,
                "fixed_atr_blocked_r": candidate_r if not fixed_atr_allowed else np.nan,
                "action": action,
                "allowed": allowed,
                "prior_allowed_completed_n": len(prior),
                "prior_allowed_completed_total_r": prior_total if prior else np.nan,
                "prior_allowed_completed_mean_r": prior_mean,
                "candidate_r": candidate_r,
                "selected_r": selected_r,
                "blocked_counterfactual_r": blocked_r,
                "candidate_exit_time_utc": event.exit_time_utc,
            }
        )
        if event.status == "COMPLETE" and allowed:
            history.append(
                {
                    "atr_regime": event.atr_regime,
                    "r": float(event.r),
                    "exit_time_utc": event.exit_time_utc,
                }
            )
    return pd.DataFrame(decisions)


def main() -> None:
    source = pd.read_csv(DATA / "diagnostic_trades.csv")
    source["source_stop_time_utc"] = pd.to_datetime(source["source_stop_time_utc"], utc=True)
    source["exit_time_utc"] = pd.to_datetime(source["exit_time_utc"], utc=True, errors="coerce")
    if (source["source_stop_time_utc"] >= EXAM_START).any():
        raise AssertionError("historical candidate cohort crossed locked exam boundary")
    source = source.sort_values("source_stop_time_utc").reset_index(drop=True)
    features = attach_atr(source, load_m1())
    decisions = replay(features)
    completed = decisions.loc[decisions["candidate_r"].notna()]
    selected = completed.loc[completed["selected_r"].notna()]
    blocked = completed.loc[completed["blocked_counterfactual_r"].notna()]
    fixed_selected = completed.loc[completed["fixed_atr_selected_r"].notna()]
    fixed_blocked = completed.loc[completed["fixed_atr_blocked_r"].notna()]
    if len(decisions) != 632 or len(completed) != 108:
        raise AssertionError("unexpected source cohort size")
    if not abs(float(completed["candidate_r"].sum()) - 28.246273828950212) < 1e-8:
        raise AssertionError("ATR replay baseline differs from frozen diagnostic")
    if (decisions["atr_m15_available_at"] > decisions["source_stop_time_utc"]).any():
        raise AssertionError("M15 ATR availability violates causality")
    if (decisions["atr_m30_available_at"] > decisions["source_stop_time_utc"]).any():
        raise AssertionError("M30 ATR availability violates causality")
    if (decisions["atr_h1_available_at"] > decisions["source_stop_time_utc"]).any():
        raise AssertionError("H1 ATR availability violates causality")
    for row_idx, row in enumerate(decisions.itertuples(index=False)):
        if row.status == "COMPLETE":
            state = "WIN" if row.candidate_r > 0 else "NONPOSITIVE"
            outcome_note = f"{state} {row.candidate_r:+.3f}R"
        else:
            outcome_note = f"NO ENTRY ({row.status})"
        # This journal note is immutable descriptive learning; blocked counterfactual labels are never fed back.
        decisions.at[row_idx, "learning_note"] = (
            f"{outcome_note}; regime={row.atr_regime}; next-event training update only if allowed and settled"
        )
    decisions.to_csv(DATA / "atr_regime_trade_learning.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")

    decisions["week_start_utc"] = decisions["source_stop_time_utc"].dt.normalize() - pd.to_timedelta(
        decisions["source_stop_time_utc"].dt.weekday, unit="D"
    )
    weekly = (
        decisions.groupby("week_start_utc")
        .agg(
            source_events=("trade_key", "size"),
            high_atr_events=("atr_regime", lambda s: int((s == "HIGH").sum())),
            completed_attempts=("candidate_r", "count"),
            filtered_attempts=("selected_r", "count"),
            blocked_completed=("blocked_counterfactual_r", "count"),
            fixed_atr_attempts=("fixed_atr_selected_r", "count"),
            high_atr_blocked=("fixed_atr_blocked_r", "count"),
            baseline_r=("candidate_r", "sum"),
            filtered_r=("selected_r", "sum"),
            fixed_atr_r=("fixed_atr_selected_r", "sum"),
            warmup_events=("action", lambda s: int((s == "ALLOW_WARMUP").sum())),
            blocked_events=("action", lambda s: int((s == "BLOCK_NONPOSITIVE_TRAILING").sum())),
        )
        .reset_index()
    )
    weekly[["baseline_r", "filtered_r", "fixed_atr_r"]] = weekly[
        ["baseline_r", "filtered_r", "fixed_atr_r"]
    ].fillna(0.0)
    weekly["cumulative_baseline_r"] = weekly["baseline_r"].cumsum()
    weekly["cumulative_filtered_r"] = weekly["filtered_r"].cumsum()
    weekly["cumulative_fixed_atr_r"] = weekly["fixed_atr_r"].cumsum()
    weekly.to_csv(DATA / "atr_regime_weekly_results.csv", index=False, date_format="%Y-%m-%d")

    regime_summary = (
        decisions.groupby("atr_regime")
        .agg(
            events=("trade_key", "size"),
            attempts=("candidate_r", "count"),
            total_r=("candidate_r", "sum"),
            mean_r=("candidate_r", "mean"),
        )
        .fillna(0.0)
    )
    report = [
        "# Per-trade ATR-regime learning — historical replay",
        "",
        "**Decision: exploratory only; no strategy change.** This replay uses the 632 pre-exam source events and the frozen RETEST-CONTINUATION V1 outcomes. It reads completed M15/M30/H1 bars only as available at the original stop time; the composite is the median percentile. High-volatility state is strictly above the previously researched 80th percentile; otherwise state is normal/low.",
        "",
        "For every source event, the policy looks back 52 weeks within the same ATR state at previously allowed, completed candidate attempts whose outcome exit precedes the current event. It needs five prior outcomes; before that it allows the frozen candidate. Once warm, it allows a state only if trailing mean R is positive. Blocked outcomes are journaled but never used to train later decisions.",
        "",
        "## Result",
        "",
        "| Policy | Completed attempts | Total R | Mean R | Median R | Win rate |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Frozen V1 | {len(completed)} | {completed['candidate_r'].sum():+.2f} | {completed['candidate_r'].mean():+.3f} | {completed['candidate_r'].median():+.3f} | {(completed['candidate_r'] > 0).mean():.1%} |",
        f"| ATR-state adaptive | {len(selected)} | {selected['selected_r'].sum():+.2f} | {selected['selected_r'].mean():+.3f} | {selected['selected_r'].median():+.3f} | {(selected['selected_r'] > 0).mean():.1%} |",
        f"| Blocked counterfactual | {len(blocked)} | {blocked['blocked_counterfactual_r'].sum():+.2f} | {blocked['blocked_counterfactual_r'].mean():+.3f} | {blocked['blocked_counterfactual_r'].median():+.3f} | {(blocked['blocked_counterfactual_r'] > 0).mean():.1%} |",
        f"| Source-stop ATR-state screen (>80th pct; not entry-time gate) | {len(fixed_selected)} | {fixed_selected['fixed_atr_selected_r'].sum():+.2f} | {fixed_selected['fixed_atr_selected_r'].mean():+.3f} | {fixed_selected['fixed_atr_selected_r'].median():+.3f} | {(fixed_selected['fixed_atr_selected_r'] > 0).mean():.1%} |",
        f"| High-ATR blocked counterfactual | {len(fixed_blocked)} | {fixed_blocked['fixed_atr_blocked_r'].sum():+.2f} | {fixed_blocked['fixed_atr_blocked_r'].mean():+.3f} | {fixed_blocked['fixed_atr_blocked_r'].median():+.3f} | {(fixed_blocked['fixed_atr_blocked_r'] > 0).mean():.1%} |",
        "",
        f"The adaptive policy allowed {int(decisions['allowed'].sum())}/632 source events and selected {len(selected)}/108 completed attempts; {len(blocked)} blocked completed attempts sum to {blocked['blocked_counterfactual_r'].sum():+.2f}R. It started in warm-up for {int(decisions['action'].eq('ALLOW_WARMUP').sum())} events.",
        "",
        "## Frozen candidate outcomes by ATR state",
        "",
        "| ATR state at source-stop time | Events | Completed attempts | Total R | Mean R |",
        "|---|---:|---:|---:|---:|",
    ]
    for state, row in regime_summary.iterrows():
        report.append(
            f"| {state} | {int(row.events)} | {int(row.attempts)} | {row.total_r:+.2f} | {row.mean_r:+.3f} |"
        )
    report += [
        "",
        "## Interpretation",
        "",
        "The direct fixed-gate row in this diagnostic applies ATR state at the original source-stop time, not the later re-entry entry time; it is not an evaluation of an entry lock. A separate earlier-period holdout tests the fixed gate at actual re-entry time. The trailing-mean policy remains an in-sample research experiment. Do not promote either rule from this development replay.",
        "",
        "Limitations: pre-exam data only; M1 OHLC event replay; recorded spread included; slippage excluded; overlapping event paths are not portfolio equity. Locked exam [2026-04-18, 2026-10-18) excluded.",
    ]
    (DATA / "ATR_REGIME_LEARNING_RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    summary = {
        "source_events": len(decisions),
        "completed_attempts": len(completed),
        "baseline_total_r": float(completed["candidate_r"].sum()),
        "adaptive_attempts": len(selected),
        "adaptive_total_r": float(selected["selected_r"].sum()),
        "fixed_atr_lock_attempts": len(fixed_selected),
        "fixed_atr_lock_total_r": float(fixed_selected["fixed_atr_selected_r"].sum()),
        "high_atr_blocked_attempts": len(fixed_blocked),
        "high_atr_blocked_counterfactual_total_r": float(fixed_blocked["fixed_atr_blocked_r"].sum()),
        "blocked_attempts": len(blocked),
        "blocked_counterfactual_total_r": float(blocked["blocked_counterfactual_r"].sum()),
        "atr_regime_counts": decisions["atr_regime"].value_counts().to_dict(),
        "max_atr_available_after_decision": False,
        "exam_read": False,
    }
    (DATA / "atr_regime_learning_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
