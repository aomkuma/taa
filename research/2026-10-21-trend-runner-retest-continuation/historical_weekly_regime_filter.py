"""Exploratory past-only weekly side/session filter for the frozen diagnostic."""

# Report prose is assembled as complete Markdown lines below.
# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "historical_diagnostic" / "diagnostic_trades.csv"
OUTPUT = ROOT / "historical_diagnostic"
EXAM_START = pd.Timestamp("2026-04-18T00:00:00Z")
LOOKBACK = pd.Timedelta(weeks=52)
MIN_HISTORY = 5


def replay(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    history: list[dict[str, object]] = []

    for event in events.sort_values("source_stop_time_utc").itertuples(index=False):
        decision_time = event.source_stop_time_utc
        lower_bound = decision_time - LOOKBACK
        prior = [
            trade
            for trade in history
            if trade["side"] == event.side
            and trade["window"] == event.window
            and lower_bound <= trade["exit_time_utc"] < decision_time
        ]
        prior_r = sum(float(trade["r"]) for trade in prior)
        prior_mean = prior_r / len(prior) if prior else None
        action = (
            "ALLOW_WARMUP"
            if len(prior) < MIN_HISTORY
            else ("ALLOW_POSITIVE_TRAILING" if prior_mean > 0 else "BLOCK_NONPOSITIVE_TRAILING")
        )
        is_allowed = action != "BLOCK_NONPOSITIVE_TRAILING"
        complete = event.status == "COMPLETE"
        row = {
            "trade_key": event.trade_key,
            "source_stop_time_utc": decision_time,
            "side": event.side,
            "window": event.window,
            "status": event.status,
            "action": action,
            "allowed": is_allowed,
            "prior_allowed_completed_n": len(prior),
            "prior_allowed_completed_total_r": prior_r if prior else None,
            "prior_allowed_completed_mean_r": prior_mean,
            "candidate_r": float(event.r) if complete else None,
            "selected_r": float(event.r) if complete and is_allowed else None,
            "blocked_counterfactual_r": float(event.r) if complete and not is_allowed else None,
            "candidate_exit_time_utc": event.exit_time_utc if complete else None,
        }
        rows.append(row)

        # A live adaptive policy can learn only from its own allowed, completed attempts.
        # A later event cannot use a still-open result, even if its eventual label is in the file.
        if complete and is_allowed:
            history.append(
                {
                    "side": event.side,
                    "window": event.window,
                    "r": float(event.r),
                    "exit_time_utc": event.exit_time_utc,
                }
            )

    return pd.DataFrame(rows)


def summary_line(label: str, values: pd.Series) -> str:
    values = values.dropna().astype(float)
    if values.empty:
        return f"| {label} | 0 | n/a | n/a | n/a | n/a |"
    return (
        f"| {label} | {len(values)} | {values.sum():+.2f} | {values.mean():+.3f} | "
        f"{values.median():+.3f} | {(values > 0).mean():.1%} |"
    )


def main() -> None:
    source = pd.read_csv(INPUT)
    source["source_stop_time_utc"] = pd.to_datetime(source["source_stop_time_utc"], utc=True)
    source["exit_time_utc"] = pd.to_datetime(source["exit_time_utc"], utc=True, errors="coerce")
    if (source["source_stop_time_utc"] >= EXAM_START).any():
        raise AssertionError("input crossed locked exam boundary")
    source = source.sort_values("source_stop_time_utc").reset_index(drop=True)
    decisions = replay(source)
    if len(decisions) != len(source) or decisions["trade_key"].duplicated().any():
        raise AssertionError("filter must emit exactly one decision per source event")
    if decisions["selected_r"].notna().sum() + decisions["blocked_counterfactual_r"].notna().sum() != int(
        source["status"].eq("COMPLETE").sum()
    ):
        raise AssertionError("every completed attempt must be selected or explicitly blocked")
    decisions.to_csv(
        OUTPUT / "weekly_regime_filter_decisions.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ"
    )

    completed = decisions.loc[decisions["candidate_r"].notna()].copy()
    selected = completed.loc[completed["selected_r"].notna()]
    blocked = completed.loc[completed["blocked_counterfactual_r"].notna()]
    if len(completed) != 108 or not abs(completed["candidate_r"].sum() - 28.246273828950212) < 1e-8:
        raise AssertionError("paired baseline differs from frozen diagnostic")

    weekly = decisions.copy()
    weekly["week_start_utc"] = weekly["source_stop_time_utc"].dt.normalize() - pd.to_timedelta(
        weekly["source_stop_time_utc"].dt.weekday, unit="D"
    )
    weekly_summary = (
        weekly.groupby("week_start_utc")
        .agg(
            source_events=("trade_key", "size"),
            allowed_events=("allowed", "sum"),
            candidate_attempts=("candidate_r", "count"),
            filtered_attempts=("selected_r", "count"),
            blocked_completed=("blocked_counterfactual_r", "count"),
            baseline_r=("candidate_r", "sum"),
            filtered_r=("selected_r", "sum"),
        )
        .reset_index()
    )
    weekly_summary["baseline_r"] = weekly_summary["baseline_r"].fillna(0.0)
    weekly_summary["filtered_r"] = weekly_summary["filtered_r"].fillna(0.0)
    weekly_summary["cumulative_filtered_r"] = weekly_summary["filtered_r"].cumsum()
    weekly_summary.to_csv(OUTPUT / "weekly_regime_filter_by_week.csv", index=False, date_format="%Y-%m-%d")

    # Half cuts are chronological among source events, preserving all weekly decisions.
    midpoint = len(decisions) // 2
    halves = [("first half", decisions.iloc[:midpoint]), ("second half", decisions.iloc[midpoint:])]
    lines = [
        "# Past-only weekly side/session filter — historical walk-forward",
        "",
        "**Decision: exploratory only; do not add to the strategy.** This is a causal replay on already inspected pre-exam development data, not independent validation.",
        "",
        "## Frozen rule for this replay",
        "",
        "At each source stop event, inspect only previously ALLOWED and completed candidate attempts from the same side/session cell, within the preceding 52 weeks and with their exit time before the current event. If fewer than five prior attempts exist, allow the original candidate during warm-up. Otherwise allow the cell only when its trailing mean R is positive. Blocked candidate outcomes are not fed back into the model. No same-week/future outcome is used.",
        "",
        "## Paired result",
        "",
        "| Policy | Completed attempts | Total R | Mean R | Median R | Win rate |",
        "|---|---:|---:|---:|---:|---:|",
        summary_line("Frozen candidate", completed["candidate_r"]),
        summary_line("Past-only filter", selected["selected_r"]),
        summary_line("Blocked counterfactual", blocked["blocked_counterfactual_r"]),
        "",
        f"The filter allowed {int(decisions['allowed'].sum())}/{len(decisions)} source events, selected {len(selected)}/{len(completed)} completed candidate attempts, and blocked {len(blocked)} completed counterfactual attempts ({blocked['blocked_counterfactual_r'].sum():+.2f}R). Warm-up decisions: {int(decisions['action'].eq('ALLOW_WARMUP').sum())}.",
        "",
        "## Chronological halves (all source events ordered by event time)",
        "",
        "| Half | Baseline attempts | Baseline R | Filter attempts | Filter R | Blocked completed |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, half in halves:
        base = half["candidate_r"].dropna()
        filt = half["selected_r"].dropna()
        blocked_half = half["blocked_counterfactual_r"].dropna()
        lines.append(
            f"| {name} | {len(base)} | {base.sum():+.2f} | {len(filt)} | {filt.sum():+.2f} | {len(blocked_half)} ({blocked_half.sum():+.2f}R) |"
        )
    lines += [
        "",
        "## Interpretation and next step",
        "",
        "A filter can raise mean R while lowering total R simply by taking fewer attempts; both totals and per-attempt returns matter. Because side/session groupings were suggested by this same historical journal, the replay is still vulnerable to research-selection bias even though its trade-by-trade rule is past-only. Do not tune its lookback, minimum history, or threshold on this dataset. Keep the original V1 and this filter outside the strategy; the result only decides whether the prior-only adaptive idea merits a separately frozen study.",
        "",
        "Limits: M1 OHLC diagnostic labels, recorded spread included, slippage excluded, event attempts can overlap, and locked exam [2026-04-18, 2026-10-18) excluded. `weekly_regime_filter_decisions.csv` records every source event and its causal decision; `weekly_regime_filter_by_week.csv` contains weekly paired totals.",
    ]
    (OUTPUT / "WEEKLY_REGIME_FILTER_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
