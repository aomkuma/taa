"""Combine the frozen candidate and past-only decisions into weekly reports."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "historical_diagnostic"
EXAM_START = pd.Timestamp("2026-04-18T00:00:00Z")


def main() -> None:
    journal = pd.read_csv(DATA / "weekly_journal.csv")
    journal["week_start_utc"] = pd.to_datetime(journal["week_start_utc"], utc=True)
    decisions = pd.read_csv(
        DATA / "weekly_regime_filter_decisions.csv",
        parse_dates=["source_stop_time_utc", "candidate_exit_time_utc"],
    )
    decisions["week_start_utc"] = (
        decisions["source_stop_time_utc"].dt.normalize()
        - pd.to_timedelta(decisions["source_stop_time_utc"].dt.weekday, unit="D")
    )
    if (decisions["source_stop_time_utc"] >= EXAM_START).any():
        raise AssertionError("weekly report crossed the locked exam boundary")

    counts = decisions.pivot_table(
        index="week_start_utc", columns="action", values="trade_key", aggfunc="count", fill_value=0
    ).reset_index()
    for name in ["ALLOW_WARMUP", "ALLOW_POSITIVE_TRAILING", "BLOCK_NONPOSITIVE_TRAILING"]:
        if name not in counts:
            counts[name] = 0
    weekly = journal.merge(counts, on="week_start_utc", how="left")
    weekly[["ALLOW_WARMUP", "ALLOW_POSITIVE_TRAILING", "BLOCK_NONPOSITIVE_TRAILING"]] = (
        weekly[["ALLOW_WARMUP", "ALLOW_POSITIVE_TRAILING", "BLOCK_NONPOSITIVE_TRAILING"]]
        .fillna(0)
        .astype(int)
    )
    filter_week = pd.read_csv(DATA / "weekly_regime_filter_by_week.csv")
    filter_week["week_start_utc"] = pd.to_datetime(filter_week["week_start_utc"], utc=True)
    weekly = weekly.merge(
        filter_week[[
            "week_start_utc", "filtered_attempts", "blocked_completed", "filtered_r", "cumulative_filtered_r"
        ]],
        on="week_start_utc",
        how="left",
        suffixes=("", "_filter"),
    )
    weekly["filtered_attempts"] = weekly["filtered_attempts"].fillna(0).astype(int)
    weekly["blocked_completed"] = weekly["blocked_completed"].fillna(0).astype(int)
    weekly["filtered_r"] = weekly["filtered_r"].fillna(0.0)
    weekly["cumulative_filtered_r"] = weekly["cumulative_filtered_r"].fillna(0.0)
    weekly["cumulative_baseline_r"] = weekly["total_r"].cumsum()
    if len(weekly) != 129 or int(weekly["source_events"].sum()) != 632:
        raise AssertionError("expected a full 129-week report over all 632 source events")

    details = decisions.copy()
    completed = details.loc[details["candidate_r"].notna()].copy()
    path_data = pd.read_csv(DATA / "diagnostic_trades.csv")
    lines = [
        "# Historical weekly walk-forward reports — RETEST-CONTINUATION V1",
        "",
        "**This is a retrospective, in-sample replay on pre-exam development data, not live trading or independent validation.** Every week is processed in chronological order. The weekly adaptive decision uses only prior allowed, completed candidate attempts in the same side/session cell over 52 weeks; it needs five prior settled attempts, otherwise the frozen V1 is allowed during warm-up. A result can update later weeks only after its exit time. No result is used to choose its own week's action.",
        "",
        f"Coverage: {len(weekly)} UTC weeks, {int(weekly['source_events'].sum())} source events, {len(completed)} completed V1 attempts. Frozen V1 total {completed['candidate_r'].sum():+.2f}R; past-only weekly filter {completed['selected_r'].sum():+.2f}R on {int(completed['selected_r'].notna().sum())} attempts. R is event-level and overlapping attempts are not portfolio equity. Recorded spread is included; slippage is excluded. Locked exam [2026-04-18, 2026-10-18) was excluded.",
        "",
        "## Week-by-week sequence",
        "",
    ]

    funnel_cols = [
        ("no_retest", "no retest"),
        ("structure_invalidated", "structure invalidated"),
        ("no_reclaim", "no reclaim"),
        ("no_continuation", "no continuation"),
        ("pending", "pending"),
    ]
    action_cols = [
        ("ALLOW_WARMUP", "warm-up allow"),
        ("ALLOW_POSITIVE_TRAILING", "positive-history allow"),
        ("BLOCK_NONPOSITIVE_TRAILING", "non-positive-history block"),
    ]
    detail_by_week = {key: group for key, group in details.groupby("week_start_utc")}

    for row in weekly.itertuples(index=False):
        start = pd.Timestamp(row.week_start_utc)
        end = start + pd.Timedelta(days=6)
        actions = [f"{label}: {int(getattr(row, col))}" for col, label in action_cols if int(getattr(row, col)) > 0]
        funnel = [f"{label} {int(getattr(row, col))}" for col, label in funnel_cols if int(getattr(row, col)) > 0]
        week_events = detail_by_week.get(start)
        if week_events is None:
            winners = losers = 0
            median_mfe = median_mae = None
            blocked_r = 0.0
        else:
            week_complete = week_events.loc[week_events["candidate_r"].notna()]
            winners = int((week_complete["candidate_r"] > 0).sum())
            losers = int((week_complete["candidate_r"] <= 0).sum())
            median_mfe = None
            median_mae = None
            selected_keys = set(week_complete["trade_key"].astype(str))
            path_rows = path_data.loc[path_data["trade_key"].astype(str).isin(selected_keys)]
            if not path_rows.empty:
                median_mfe = float(path_rows["mfe_r"].median())
                median_mae = float(path_rows["mae_r"].median())
            blocked_r = float(week_events["blocked_counterfactual_r"].sum(skipna=True))

        lines.append(f"### Week {start:%Y-%m-%d} to {end:%Y-%m-%d} UTC")
        lines.append("")
        lines.append(
            f"- Source events: {int(row.source_events)}. Funnel outcomes: {', '.join(funnel) if funnel else 'none'}; completed V1 attempts: {int(row.completed_attempts)} ({winners} positive, {losers} non-positive)."
        )
        lines.append(f"- Past-only decisions this week: {', '.join(actions) if actions else 'none'}.")
        lines.append(
            f"- Weekly result: V1 {row.total_r:+.2f}R on {int(row.completed_attempts)} attempts; adaptive {row.filtered_r:+.2f}R on {int(row.filtered_attempts)}. Cumulative: V1 {row.cumulative_baseline_r:+.2f}R; adaptive {row.cumulative_filtered_r:+.2f}R."
        )
        if int(row.blocked_completed) > 0:
            lines.append(
                f"- Filter review: blocked {int(row.blocked_completed)} completed counterfactual attempt(s), worth {blocked_r:+.2f}R in hindsight; this outcome may update later weeks only after settlement."
            )
        if int(row.completed_attempts) == 0:
            lines.append("- Weekly learning: no completed candidate result; use this week for funnel coverage only, not an expectancy update.")
        else:
            path_note = (
                f"median MFE {median_mfe:+.2f}R / median MAE {median_mae:+.2f}R"
                if median_mfe is not None and median_mae is not None
                else "path excursions unavailable"
            )
            lines.append(
                f"- Weekly learning: {winners} positive and {losers} non-positive attempts; {path_note}. The sample is small, so no threshold or strategy change is inferred from this week alone."
            )
        lines.append("")

    lines += [
        "## End-of-replay conclusion",
        "",
        "The 52-week adaptive filter finished below the frozen V1 in total R (+26.28R versus +28.25R), although it had higher mean R per selected attempt. It blocked 31 completed V1 paths worth +1.96R in hindsight, and its chronological halves had opposite implications. Therefore it is not adopted. The week-by-week log is the requested learning journal; it does not convert an in-sample result into verified future profitability.",
        "",
        "Machine-readable tables: `weekly_sequential_replay.csv` (all weeks) and `weekly_regime_filter_decisions.csv` (one decision for every source event). Reproduce with `.venv/Scripts/python.exe research/2026-10-21-trend-runner-retest-continuation/build_weekly_sequence_report.py`.",
    ]
    (DATA / "WEEKLY_SEQUENTIAL_REPLAY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    weekly.to_csv(DATA / "weekly_sequential_replay.csv", index=False, date_format="%Y-%m-%d")


if __name__ == "__main__":
    main()
