"""Build a chronological weekly journal from the frozen pre-exam diagnostic."""

# Generated Markdown rows and report prose are intentionally assembled as single lines.
# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "historical_diagnostic" / "diagnostic_trades.csv"
OUTPUT = ROOT / "historical_diagnostic"
EXAM_START = pd.Timestamp("2026-04-18T00:00:00Z")


def main() -> None:
    events = pd.read_csv(INPUT)
    events["source_stop_time_utc"] = pd.to_datetime(events["source_stop_time_utc"], utc=True)
    events["week_start_utc"] = events["source_stop_time_utc"].dt.normalize() - pd.to_timedelta(
        events["source_stop_time_utc"].dt.weekday, unit="D"
    )
    if (events["source_stop_time_utc"] >= EXAM_START).any():
        raise AssertionError("weekly journal crossed the locked exam boundary")

    completed = events.loc[events["status"].eq("COMPLETE")].copy()
    completed["is_win"] = completed["r"] > 0
    if len(events) != 632 or len(completed) != 108:
        raise AssertionError("weekly journal input differs from the frozen 632/108 diagnostic cohort")
    if not abs(float(completed["r"].sum()) - 28.246273828950212) < 1e-8:
        raise AssertionError("weekly journal total differs from the frozen diagnostic summary")
    weekly = events.groupby("week_start_utc", as_index=False).agg(
        source_events=("trade_key", "size"),
        completed_attempts=("r", "count"),
        no_retest=("status", lambda s: int((s == "NO_RETEST").sum())),
        structure_invalidated=("status", lambda s: int((s == "STRUCTURE_INVALIDATED").sum())),
        no_reclaim=("status", lambda s: int((s == "NO_RECLAIM").sum())),
        no_continuation=("status", lambda s: int((s == "NO_CONTINUATION").sum())),
        pending=("status", lambda s: int(s.isin(["PENDING_EXIT_HORIZON", "PENDING_RECLAIM_HORIZON"]).sum())),
    )
    result_stats = completed.groupby("week_start_utc").agg(
        total_r=("r", "sum"),
        mean_r=("r", "mean"),
        median_r=("r", "median"),
        win_rate=("is_win", "mean"),
        median_mfe_r=("mfe_r", "median"),
        median_mae_r=("mae_r", "median"),
        best_r=("r", "max"),
    )
    best_trade = completed.loc[
        completed.groupby("week_start_utc")["r"].idxmax(),
        ["week_start_utc", "trade_key"],
    ].rename(columns={"trade_key": "best_trade_key"})
    weekly = weekly.merge(result_stats, on="week_start_utc", how="left")
    weekly = weekly.merge(best_trade, on="week_start_utc", how="left")

    first_monday = events["week_start_utc"].min()
    last_monday = events["week_start_utc"].max()
    calendar = pd.DataFrame({"week_start_utc": pd.date_range(first_monday, last_monday, freq="7D", tz="UTC")})
    weekly = calendar.merge(weekly, on="week_start_utc", how="left")
    if len(weekly) != 129 or int(weekly["source_events"].sum()) != len(events):
        raise AssertionError("weekly calendar does not cover every source event")
    count_columns = [
        "source_events",
        "completed_attempts",
        "no_retest",
        "structure_invalidated",
        "no_reclaim",
        "no_continuation",
        "pending",
    ]
    weekly[count_columns] = weekly[count_columns].fillna(0).astype(int)
    weekly["win_rate"] = weekly["win_rate"].fillna(0.0)
    weekly["total_r"] = weekly["total_r"].fillna(0.0)
    weekly["cumulative_r"] = weekly["total_r"].cumsum()
    weekly["week_end_utc"] = weekly["week_start_utc"] + pd.Timedelta(days=6)
    weekly.to_csv(OUTPUT / "weekly_journal.csv", index=False, date_format="%Y-%m-%d")

    active = weekly.loc[weekly["completed_attempts"] > 0].copy()
    years = (
        completed.assign(year=completed["source_stop_time_utc"].dt.year)
        .groupby("year")
        .agg(
            attempts=("r", "size"),
            total_r=("r", "sum"),
            mean_r=("r", "mean"),
            median_r=("r", "median"),
            win_rate=("is_win", "mean"),
        )
    )
    ordered = completed.sort_values("source_stop_time_utc").reset_index(drop=True)
    midpoint = len(ordered) // 2
    halves = {
        "first_half": ordered.iloc[:midpoint],
        "second_half": ordered.iloc[midpoint:],
    }
    training_side_means = halves["first_half"].groupby("side")["r"].mean()
    selected_side = str(training_side_means.idxmax())
    later_half = halves["second_half"]
    later_selected = later_half.loc[later_half["side"].eq(selected_side)]
    later_top3 = later_selected.nlargest(3, "r")
    top3 = completed.nlargest(3, "r")

    def week_start_fmt(value: object) -> str:
        return pd.Timestamp(value).strftime("%Y-%m-%d")

    lines = [
        "# RETEST-CONTINUATION V1 — weekly historical journal",
        "",
        "**Status: descriptive, in-sample research only. No strategy rule changed.**",
        "",
        "## Coverage and result",
        "",
        f"- Source cohort: {len(events)} stopped-before-+1R opportunities across {len(weekly)} calendar weeks.",
        f"- Completed candidate attempts: {len(completed)} across {len(active)} active weeks; {len(completed) / max(len(active), 1):.2f} attempts per active week.",
        f"- Candidate outcome: {completed['r'].sum():+.2f}R total, {completed['r'].mean():+.3f}R mean, {completed['is_win'].mean():.1%} winners, {completed['r'].median():+.3f}R median.",
        f"- Top 3 attempts contributed {top3['r'].sum() / completed['r'].sum():.1%} of total R; excluding them leaves {completed['r'].sum() - top3['r'].sum():+.2f}R.",
        "- Locked exam [2026-04-18, 2026-10-18) and later observations were excluded. Recorded spread is included; slippage is excluded.",
        "",
        "## Yearly progression",
        "",
        "| Year | Attempts | Total R | Mean R | Median R | Win rate |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year, row in years.iterrows():
        lines.append(
            f"| {year} | {int(row.attempts)} | {row.total_r:+.2f} | {row.mean_r:+.3f} | {row.median_r:+.3f} | {row.win_rate:.1%} |"
        )
    lines += [
        "",
        "## Chronological halves",
        "",
        "| Half | Attempts | Total R | Mean R | Median R | Win rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, sample in halves.items():
        lines.append(
            f"| {name.replace('_', ' ')} | {len(sample)} | {sample['r'].sum():+.2f} | {sample['r'].mean():+.3f} | {sample['r'].median():+.3f} | {(sample['r'] > 0).mean():.1%} |"
        )
    lines += [
        "",
        "## Chronological direction transfer check",
        "",
        f"Choosing the side with higher mean R from only the first half selects {selected_side} (first-half means: BUY {training_side_means.get('BUY', float('nan')):+.3f}R, SELL {training_side_means.get('SELL', float('nan')):+.3f}R). Applied to the next 54 attempts, {selected_side}-only retains {len(later_selected)} trades and {later_selected['r'].sum():+.2f}R ({later_selected['r'].mean():+.3f}R/trade; {(later_selected['r'] > 0).mean():.1%} wins), versus all sides at {later_half['r'].sum():+.2f}R.",
        f"However, its top three later-half winners contribute {later_top3['r'].sum():+.2f}R; without them the selected side retains only {later_selected['r'].sum() - later_top3['r'].sum():+.2f}R. This chronological split is still already-seen development data, not independent validation; it is a lead to study, not a reason to disable SELL in the strategy.",
    ]

    lines += [
        "",
        "## Weekly extremes (weeks with completed attempts)",
        "",
        "Positive weeks:",
        "",
        "| Week starts UTC | Attempts | Total R | Best R | Best trade |",
        "|---|---:|---:|---:|---|",
    ]
    for row in active.nlargest(5, "total_r").itertuples(index=False):
        lines.append(
            f"| {week_start_fmt(row.week_start_utc)} | {row.completed_attempts} | {row.total_r:+.2f} | {row.best_r:+.2f} | {row.best_trade_key} |"
        )
    lines += [
        "",
        "Negative weeks:",
        "",
        "| Week starts UTC | Attempts | Total R | Best R | Most common event outcome |",
        "|---|---:|---:|---:|---|",
    ]
    reason_columns = ["no_retest", "structure_invalidated", "no_reclaim", "no_continuation"]
    for row in active.nsmallest(5, "total_r").itertuples(index=False):
        row_dict = row._asdict()
        reason = max(reason_columns, key=lambda col: row_dict[col])
        reason_text = (
            f"{reason.replace('_', ' ')} ({row_dict[reason]})"
            if row_dict[reason] > 0
            else "none; all other events completed or pending"
        )
        lines.append(
            f"| {week_start_fmt(row.week_start_utc)} | {row.completed_attempts} | {row.total_r:+.2f} | {row.best_r:+.2f} | {reason_text} |"
        )

    lines += [
        "",
        "## Trade-path journal findings",
        "",
        "- 632-event funnel: 108 COMPLETE, 221 NO_RETEST, 114 STRUCTURE_INVALIDATED, 114 NO_RECLAIM, 65 NO_CONTINUATION, and 10 pending horizon events.",
        "- All 108 completed attempts ultimately exited by the structural trailing stop; median trade was negative even though total R was positive.",
        "- Of 42 attempts that reached at least +1R MFE, 34 closed positive and 8 finished at or below zero. All 11 attempts that reached +3R MFE finished positive. This suggests the main weakness is the entry/continuation funnel, more than a general failure to retain a large move; the threshold cut is retrospective, not a deployable rule.",
        "- The three largest winners occurred in separate 2025 weeks. Their removal turns the full result negative, so the positive total is not a stable weekly edge.",
        "- The second chronological half gained +23.45R, but excluding its three largest winners it lost -9.61R. Improvement over time is therefore not established independently of outliers.",
        "",
        "## Learning and next research action",
        "",
        "Do not promote or retune this setup or the failed 52-week filter from these same outcomes. The first-half direction transfer chose BUY, but the next-half result falls to +0.98R after removing its three largest winners, so do not disable SELL based on this sample. The next historical question is the low completion rate (108/632): investigate one isolated entry-funnel hypothesis, preserve every skipped event, and measure it chronologically against the frozen candidate. Any positive development-sample result remains exploratory and does not replace a truly untouched validation period.",
        "",
        "Reproduce with `.venv/Scripts/python.exe research/2026-10-21-trend-runner-retest-continuation/build_weekly_journal.py`. Weekly rows for all calendar weeks, including weeks with no source events, are in `weekly_journal.csv`.",
    ]
    (OUTPUT / "WEEKLY_JOURNAL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
