"""Build a trade-complete weekly review from the frozen historical M1 journal.

All review flags are descriptive prompts, not proof that a trade was avoidable.
The script never changes strategy rules or the source trade journal.
"""
# Markdown output contains deliberately long prose and tables.
# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "trade_journal.csv"
OUTPUT = ROOT / "weekly_journal"
REQUIRED = {
    "trade_key",
    "entry_time_utc",
    "window",
    "side",
    "action",
    "action_reason",
    "runner_r",
    "fast_r",
    "runner_exit_reason",
    "fast_exit_reason",
    "runner_hold_minutes",
    "path_class",
    "h1_atr",
    "risk_h1_atr",
    "pullback_ratio",
    "open_space_atr",
    "post_exit_favorable_from_exit_r",
    "mfe_before_exit_r_including_exit_bar",
    "mae_before_exit_r_including_exit_bar",
}


def add_review_fields(source: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED - set(source.columns)
    if missing:
        raise ValueError(f"source journal missing columns: {sorted(missing)}")
    journal = source.copy()
    journal["entry_time_utc"] = pd.to_datetime(journal["entry_time_utc"], utc=True)
    if journal["trade_key"].duplicated().any():
        raise ValueError("source journal contains duplicate trade keys")
    if not journal["entry_time_utc"].is_monotonic_increasing:
        journal = journal.sort_values(["entry_time_utc", "trade_key"]).reset_index(drop=True)
    journal["week_start_utc"] = (
        journal["entry_time_utc"].dt.normalize()
        - pd.to_timedelta(journal["entry_time_utc"].dt.dayofweek, unit="D")
    ).dt.strftime("%Y-%m-%d")
    flag_conditions = [
        (journal["action"].eq("RUNNER") & journal["runner_r"].lt(0), "SELECTED_RUNNER_LOSS"),
        (journal["action"].eq("SKIP") & journal["runner_r"].gt(0), "SKIPPED_COUNTERFACTUAL_WIN"),
        (journal["path_class"].eq("STOP_BEFORE_1R"), "STOPPED_BEFORE_1R"),
        (journal["post_exit_favorable_from_exit_r"].ge(1), "POST_EXIT_FOLLOWTHROUGH_GE_1R"),
        ((journal["fast_r"] - journal["runner_r"]).ge(1), "FAST_OUTPERFORMED_RUNNER_GE_1R"),
    ]
    journal["review_flags"] = ""
    for condition, label in flag_conditions:
        journal.loc[condition, "review_flags"] = journal.loc[condition, "review_flags"].map(
            lambda current, flag=label: f"{current};{flag}" if current else flag
        )
    return journal


def weekly_summary(journal: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for week, group in journal.groupby("week_start_utc", sort=True):
        selected = group.loc[group["action"].eq("RUNNER")]
        losses = selected.loc[selected["runner_r"].lt(0)]
        wins = selected.loc[selected["runner_r"].gt(0)]
        worst = losses.nsmallest(1, "runner_r")
        best = wins.nlargest(1, "runner_r")
        worst_row = worst.iloc[0] if not worst.empty else None
        best_row = best.iloc[0] if not best.empty else None
        rows.append(
            {
                "week_start_utc": week,
                "week_end_utc": (pd.Timestamp(week) + pd.Timedelta(days=6)).strftime("%Y-%m-%d"),
                "opportunities": len(group),
                "selected_runner": len(selected),
                "selected_wins": len(wins),
                "selected_losses": len(losses),
                "selected_total_r": float(selected["runner_r"].sum()),
                "selected_mean_r": float(selected["runner_r"].mean()) if len(selected) else None,
                "selected_win_rate": float((selected["runner_r"] > 0).mean()) if len(selected) else None,
                "skipped_counterfactual_wins": int(
                    (group["action"].eq("SKIP") & group["runner_r"].gt(0)).sum()
                ),
                "stopped_before_1r": int(group["path_class"].eq("STOP_BEFORE_1R").sum()),
                "post_exit_followthrough_ge_1r": int(group["post_exit_favorable_from_exit_r"].ge(1).sum()),
                "fast_outperformed_runner_ge_1r": int(((group["fast_r"] - group["runner_r"]) >= 1).sum()),
                "worst_selected_trade_key": None if worst_row is None else worst_row["trade_key"],
                "worst_selected_r": None if worst_row is None else float(worst_row["runner_r"]),
                "worst_selected_context": None
                if worst_row is None
                else f"{worst_row['side']} {worst_row['window']} / {worst_row['runner_exit_reason']}",
                "best_selected_trade_key": None if best_row is None else best_row["trade_key"],
                "best_selected_r": None if best_row is None else float(best_row["runner_r"]),
                "best_selected_context": None
                if best_row is None
                else f"{best_row['side']} {best_row['window']} / {best_row['runner_exit_reason']}",
            }
        )
    return pd.DataFrame(rows)


def build_summary(journal: pd.DataFrame, weeks: pd.DataFrame) -> dict[str, object]:
    selected = journal.loc[journal["action"].eq("RUNNER")]
    selected_values = selected["runner_r"]
    selected_losses = selected.loc[selected["runner_r"].lt(0)]
    top_trades = selected.nlargest(5, "runner_r")
    active_weeks = weeks.loc[weeks["selected_runner"].gt(0)]
    reviewed_flags = {
        "selected_runner_losses": int((selected_values < 0).sum()),
        "skipped_counterfactual_wins": int((journal["action"].eq("SKIP") & journal["runner_r"].gt(0)).sum()),
        "stopped_before_1r": int(journal["path_class"].eq("STOP_BEFORE_1R").sum()),
        "post_exit_followthrough_ge_1r": int(journal["post_exit_favorable_from_exit_r"].ge(1).sum()),
        "fast_outperformed_runner_ge_1r": int(((journal["fast_r"] - journal["runner_r"]) >= 1).sum()),
    }
    top_weeks = weeks.nlargest(5, "selected_total_r").to_dict(orient="records")
    worst_weeks = weeks.nsmallest(5, "selected_total_r").to_dict(orient="records")
    by_side: dict[str, object] = {}
    by_window: dict[str, object] = {}
    for dimension, output in (("side", by_side), ("window", by_window)):
        for key, group in selected.groupby(dimension):
            output[str(key)] = {
                "trades": len(group),
                "total_r": float(group["runner_r"].sum()),
                "mean_r": float(group["runner_r"].mean()),
                "win_rate": float((group["runner_r"] > 0).mean()),
            }
    return {
        "source": SOURCE.name,
        "timezone": "UTC; weeks run Monday-Sunday",
        "entries": len(journal),
        "date_start_utc": journal["entry_time_utc"].min().isoformat(),
        "date_end_utc": journal["entry_time_utc"].max().isoformat(),
        "active_weeks": len(weeks),
        "weeks_with_selected_runner": len(active_weeks),
        "selected_runner_entries": len(selected),
        "selected_runner_total_r": float(selected_values.sum()),
        "selected_runner_mean_r": float(selected_values.mean()) if len(selected) else None,
        "selected_runner_win_rate": float((selected_values > 0).mean()) if len(selected) else None,
        "selected_runner_median_r": float(selected_values.median()) if len(selected) else None,
        "top5_winner_share_of_selected_total_r": float(top_trades["runner_r"].sum() / selected_values.sum())
        if len(selected) and selected_values.sum() != 0
        else None,
        "selected_total_r_ex_top5": float(selected_values.sum() - top_trades["runner_r"].sum()),
        "top_selected_trades": [
            {
                "trade_key": row.trade_key,
                "entry_time_utc": row.entry_time_utc.isoformat(),
                "side": row.side,
                "window": row.window,
                "r": float(row.runner_r),
            }
            for row in top_trades.itertuples(index=False)
        ],
        "profitable_selected_weeks": int((active_weeks["selected_total_r"] > 0).sum()),
        "losing_selected_weeks": int((active_weeks["selected_total_r"] < 0).sum()),
        "weekly_selected_total_r_median": float(active_weeks["selected_total_r"].median())
        if len(active_weeks)
        else None,
        "review_flags": reviewed_flags,
        "selected_loss_exit_reasons": {
            str(key): int(value)
            for key, value in selected_losses["runner_exit_reason"].value_counts().items()
        },
        "selected_loss_path_classes": {
            str(key): int(value) for key, value in selected_losses["path_class"].value_counts().items()
        },
        "selected_by_side": by_side,
        "selected_by_window": by_window,
        "top_weeks": top_weeks,
        "worst_weeks": worst_weeks,
        "limitations": [
            "Historical, in-sample M1 OHLC backtest journal; not a live execution journal.",
            "A review flag identifies a path worth inspecting; it does not prove the trade was avoidable or the rule was wrong.",
            "Skipped wins are counterfactual RUNNER outcomes, not realized profits or automatic selection mistakes.",
            "Trades can overlap in time; summed R by week is not an account-equity curve.",
            "No strategy or order rule is changed by this review.",
        ],
    }


def render_markdown(summary: dict[str, object], weeks: pd.DataFrame) -> str:
    flags = summary["review_flags"]
    selected_mean = (
        "n/a" if summary["selected_runner_mean_r"] is None else f"{summary['selected_runner_mean_r']:+.3f}R"
    )
    selected_win_rate = (
        "n/a" if summary["selected_runner_win_rate"] is None else f"{summary['selected_runner_win_rate']:.1%}"
    )
    selected_median = (
        "n/a"
        if summary["selected_runner_median_r"] is None
        else f"{summary['selected_runner_median_r']:+.3f}R"
    )
    weekly_median = (
        "n/a"
        if summary["weekly_selected_total_r_median"] is None
        else f"{summary['weekly_selected_total_r_median']:+.2f}R"
    )
    top5_share = summary["top5_winner_share_of_selected_total_r"]
    lines = [
        "# Historical weekly trade journal review",
        "",
        f"Source: `{summary['source']}` · {summary['date_start_utc']} to {summary['date_end_utc']} · weeks are UTC Monday-Sunday.",
        "",
        "## Whole-sample readout",
        "",
        f"- Journal coverage: **{summary['entries']:,} trades/opportunities** across **{summary['active_weeks']} active weeks**.",
        f"- Frozen selector chose **{summary['selected_runner_entries']:,} RUNNER** opportunities: **{summary['selected_runner_total_r']:+.2f}R total**, **{selected_mean} per selected trade**, win rate **{selected_win_rate}**, median **{selected_median}**.",
        f"- Weeks with at least one RUNNER selection: **{summary['profitable_selected_weeks']} positive / {summary['losing_selected_weeks']} negative**; median weekly total **{weekly_median}**.",
        f"- Top 5 winners contribute **{top5_share:.1%}** of selected total R; excluding them leaves **{summary['selected_total_r_ex_top5']:+.2f}R**."
        if top5_share is not None
        else "- Top-winner concentration is unavailable because there are no selected trades.",
        "",
        "## Repeated patterns worth reviewing",
        "",
        "- Selected losing trade exit reasons: "
        + ", ".join(f"{count} {reason}" for reason, count in summary["selected_loss_exit_reasons"].items())
        + ".",
        "- Selected losing path classes: "
        + "; ".join(f"{path}: {count}" for path, count in summary["selected_loss_path_classes"].items())
        + ". Review entry timing/confirmation before changing stop width.",
        "- Side/session differences below are descriptive and post-hoc; use them to prioritize chart review, not to add a filter on this same sample.",
        "",
        "### Selected RUNNER results by side",
        "",
        "| Side | Trades | Total R | Mean R | Win rate |",
        "|---|---:|---:|---:|---:|",
        *[
            f"| {key} | {value['trades']} | {value['total_r']:+.2f} | "
            f"{value['mean_r']:+.3f} | {value['win_rate']:.1%} |"
            for key, value in summary["selected_by_side"].items()
        ],
        "",
        "### Selected RUNNER results by session",
        "",
        "| Session | Trades | Total R | Mean R | Win rate |",
        "|---|---:|---:|---:|---:|",
        *[
            f"| {key} | {value['trades']} | {value['total_r']:+.2f} | "
            f"{value['mean_r']:+.3f} | {value['win_rate']:.1%} |"
            for key, value in summary["selected_by_window"].items()
        ],
        "",
        "## Recurring review flags",
        "",
        f"- Selected RUNNER losses: **{flags['selected_runner_losses']}**.",
        f"- SKIP opportunities with positive counterfactual RUNNER result: **{flags['skipped_counterfactual_wins']}**; review for possible missed setups, not as realized P&L.",
        f"- STOP_BEFORE_1R paths: **{flags['stopped_before_1r']}**; investigate entry timing/confirmation and whether the stop was structurally premature.",
        f"- Trades with at least +1R favorable movement after exit: **{flags['post_exit_followthrough_ge_1r']}**; review exits/re-entry separately, not as guaranteed recoverable profit.",
        f"- FAST exceeded RUNNER by at least 1R: **{flags['fast_outperformed_runner_ge_1r']}**; inspect exit-management context.",
        "",
        "These are repeatable prompts for trade-by-trade review, not labels of trader error. A candle-path backtest cannot establish intent or within-bar ordering.",
        "",
        "## Strongest selected weeks",
        "",
        "| Week (UTC) | Trades | RUNNER R | Best trade | Worst trade | Early stops | After-exit +1R |",
        "|---|---:|---:|---|---|---:|---:|",
    ]
    for row in summary["top_weeks"]:
        lines.append(_week_line(row))
    lines += [
        "",
        "## Weakest selected weeks",
        "",
        "| Week (UTC) | Trades | RUNNER R | Worst trade | Worst context | Early stops | After-exit +1R |",
        "|---|---:|---:|---|---|---:|---:|",
    ]
    for row in summary["worst_weeks"]:
        lines.append(_week_line(row, weak=True))
    lines += [
        "",
        "## Every active week",
        "",
        "| Week (UTC) | Opportunities | Selected | Selected R | Mean R | Win rate | Losses | SKIP wins | Stop <1R | Post-exit +1R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in weeks.to_dict(orient="records"):
        mean = "-" if pd.isna(row["selected_mean_r"]) else f"{row['selected_mean_r']:+.3f}"
        rate = "-" if pd.isna(row["selected_win_rate"]) else f"{row['selected_win_rate']:.1%}"
        lines.append(
            f"| {row['week_start_utc']}–{row['week_end_utc']} | {row['opportunities']} | "
            f"{row['selected_runner']} | {row['selected_total_r']:+.2f} | {mean} | {rate} | "
            f"{row['selected_losses']} | {row['skipped_counterfactual_wins']} | "
            f"{row['stopped_before_1r']} | {row['post_exit_followthrough_ge_1r']} |"
        )
    lines += [
        "",
        "## How to use this journal",
        "",
        "Open `weekly_trade_journal.csv` to inspect every individual trade and its review flags. The focused selected-trade audit for losses stopped before +1R is in `../early_stop_audit/EARLY_STOP_AUDIT.md`, the 146 exact cases are in `../early_stop_audit/stop_before_1r_trades.csv`, and the fixed post-entry checkpoint study is in `../early_stop_audit/POST_ENTRY_REVIEW.md`. For a suspected mistake, check the exact entry/exit rows and price path before proposing a rule change. Existing delayed-reentry studies are already exploratory and in-sample; do not count them as independent validation.",
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in summary["limitations"]],
        "",
    ]
    return "\n".join(lines)


def _week_line(row: dict[str, object], *, weak: bool = False) -> str:
    missing = "-"
    if weak:
        trade = (
            missing
            if pd.isna(row["worst_selected_trade_key"])
            else f"{row['worst_selected_trade_key']} ({row['worst_selected_r']:+.2f}R)"
        )
        context = missing if pd.isna(row["worst_selected_context"]) else row["worst_selected_context"]
        return (
            f"| {row['week_start_utc']} | {row['selected_runner']} | {row['selected_total_r']:+.2f}R | "
            f"{trade} | {context} | {row['stopped_before_1r']} | "
            f"{row['post_exit_followthrough_ge_1r']} |"
        )
    best = (
        missing
        if pd.isna(row["best_selected_trade_key"])
        else f"{row['best_selected_trade_key']} ({row['best_selected_r']:+.2f}R)"
    )
    worst = (
        missing
        if pd.isna(row["worst_selected_trade_key"])
        else f"{row['worst_selected_trade_key']} ({row['worst_selected_r']:+.2f}R)"
    )
    return (
        f"| {row['week_start_utc']} | {row['selected_runner']} | {row['selected_total_r']:+.2f}R | "
        f"{best} | {worst} | {row['stopped_before_1r']} | "
        f"{row['post_exit_followthrough_ge_1r']} |"
    )


def main() -> None:
    source = pd.read_csv(SOURCE)
    journal = add_review_fields(source)
    weeks = weekly_summary(journal)
    if int(weeks["opportunities"].sum()) != len(journal):
        raise AssertionError("weekly aggregation lost or duplicated journal rows")
    if int(weeks["selected_runner"].sum()) != int(journal["action"].eq("RUNNER").sum()):
        raise AssertionError("weekly aggregation lost or duplicated selected trades")
    summary = build_summary(journal, weeks)
    OUTPUT.mkdir(exist_ok=True)
    journal.to_csv(OUTPUT / "weekly_trade_journal.csv", index=False, float_format="%.6f")
    weeks.to_csv(OUTPUT / "weekly_summaries.csv", index=False, float_format="%.6f")
    (OUTPUT / "weekly_review_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUTPUT / "WEEKLY_REVIEW.md").write_text(render_markdown(summary, weeks), encoding="utf-8")
    print(f"journalled {len(journal)} trades into {len(weeks)} UTC weeks")  # noqa: T201


if __name__ == "__main__":
    main()
