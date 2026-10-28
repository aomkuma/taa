"""Exploratory pre-exam OHLC replay; never writes to the prospective journal."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from candidate import simulate_historical_diagnostic

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE_JOURNAL = REPO / "research/2026-10-21-trend-runner-3y-walkforward/trade_journal.csv"
RECOVERY_EVENTS = REPO / "research/2026-10-21-trend-runner-post-stop-recovery/recovery_events.csv"
M1_PATH = REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet"
OUTPUT = ROOT / "historical_diagnostic"
DATA_START = pd.Timestamp("2023-09-01", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
POINT = 0.01
SUPERSEDED = (
    "Superseded 2026-10-22 (DEBUG_2026-10-22.md): this replay took its TR1 source trades from the "
    "3-year walk-forward's M1-OHLC approximation and managed V1 on M1 bars. Use pipeline.py (tick "
    "fills, tick SPLIT source) one week at a time; the original is kept in _original_2026-10-22/."
)


def load_bars() -> pd.DataFrame:
    bars = pd.read_parquet(
        M1_PATH,
        columns=["open_time", "open", "high", "low", "close", "spread"],
        filters=[
            ("open_time", ">=", DATA_START.to_pydatetime()),
            ("open_time", "<", EXAM_START.to_pydatetime()),
        ],
    )
    bars["open_time"] = pd.to_datetime(bars["open_time"], utc=True)
    bars = bars.sort_values("open_time").set_index("open_time")
    if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise AssertionError("M1 rows must be unique and chronological")
    if bars.index.min() < DATA_START or bars.index.max() >= EXAM_START:
        raise AssertionError("historical loader crossed its declared boundary")
    return bars


def main() -> None:
    raise SystemExit(SUPERSEDED)
    OUTPUT.mkdir(exist_ok=True)
    source = pd.read_csv(SOURCE_JOURNAL)
    recoveries = pd.read_csv(RECOVERY_EVENTS)
    source = source.loc[source["path_class"].eq("STOP_BEFORE_1R")].copy()
    source = source.loc[pd.to_datetime(source["runner_exit_time_utc"], utc=True) < EXAM_START]
    cohort = recoveries[["trade_key", "stop_time_utc"]].merge(
        source, on="trade_key", validate="one_to_one", suffixes=("_recovery", "_source")
    )
    if len(cohort) != 632:
        raise AssertionError(f"expected frozen 632-event cohort; found {len(cohort)}")
    if not (
        pd.to_datetime(cohort["stop_time_utc"], utc=True)
        == pd.to_datetime(cohort["runner_exit_time_utc"], utc=True)
    ).all():
        raise AssertionError("recovery and source journal stop times disagree")

    bars = load_bars()
    outcomes: list[dict[str, object]] = []
    for row in cohort.itertuples(index=False):
        stop_time = pd.Timestamp(row.stop_time_utc)
        source_entry_time = pd.Timestamp(row.entry_time_utc)
        if source_entry_time not in bars.index:
            raise AssertionError(f"missing original-entry M1 spread for {row.trade_key}")
        event = {
            "trade_key": row.trade_key,
            "stop_time_utc": stop_time,
            "side": 1 if row.side == "BUY" else -1,
            "entry": float(row.entry),
            "stop": float(row.initial_stop),
            # Historical M1 stores spread in points; candidate rule expects price units.
            "spread": float(bars.loc[source_entry_time, "spread"]) * POINT,
            "runner_stopped_before_plus1": True,
        }
        # A short pre-event warmup is needed for completed M5 ATR and pivots.
        start = max(DATA_START, stop_time - pd.Timedelta(hours=3))
        # The frozen rule can wait 8h, then needs at most 2 M5 bars to confirm,
        # followed by an 8h hold. Keep all available pre-exam rows for this event.
        path = bars.loc[start : min(stop_time + pd.Timedelta(hours=16, minutes=15), EXAM_START)]
        result = simulate_historical_diagnostic(event, path, exam_start=EXAM_START, earliest_data=DATA_START)
        outcomes.append(
            {
                "trade_key": row.trade_key,
                "source_stop_time_utc": stop_time.isoformat(),
                "year": stop_time.year,
                "window": row.window,
                "side": row.side,
                "source_entry": float(row.entry),
                "source_risk": float(row.initial_risk_price),
                "source_runner_r": float(row.runner_r),
                **result,
            }
        )

    frame = pd.DataFrame(outcomes).sort_values(["source_stop_time_utc", "trade_key"])
    frame.to_csv(OUTPUT / "diagnostic_trades.csv", index=False)
    complete = frame.loc[frame["status"].eq("COMPLETE")].copy()
    if len(complete):
        complete["cumulative_R"] = complete["r"].cumsum()
        complete["event_sequence_drawdown_R"] = complete["cumulative_R"] - complete["cumulative_R"].cummax()
    top_winners = complete.nlargest(3, "r")
    summary: dict[str, object] = {
        "study": "RETEST-CONTINUATION V1 historical diagnostic",
        "cohort_events": len(frame),
        "completed_attempts": len(complete),
        "event_status_counts": {str(k): int(v) for k, v in frame["status"].value_counts().items()},
        "net_total_R": float(complete["r"].sum()) if len(complete) else None,
        "mean_R_per_completed_attempt": float(complete["r"].mean()) if len(complete) else None,
        "win_rate": float((complete["r"] > 0).mean()) if len(complete) else None,
        "median_holding_minutes": float(complete["holding_minutes"].median()) if len(complete) else None,
        "mean_MFE_R": float(complete["mfe_r"].mean()) if len(complete) else None,
        "mean_MAE_R": float(complete["mae_r"].mean()) if len(complete) else None,
        "median_R": float(complete["r"].median()) if len(complete) else None,
        "best_R": float(complete["r"].max()) if len(complete) else None,
        "worst_R": float(complete["r"].min()) if len(complete) else None,
        "event_sequence_max_drawdown_R": float(-complete["event_sequence_drawdown_R"].min())
        if len(complete)
        else None,
        "top3_winner_share_of_total_R": float(top_winners["r"].sum() / complete["r"].sum())
        if len(complete) and complete["r"].sum() != 0
        else None,
        "total_R_ex_top3": float(complete["r"].sum() - top_winners["r"].sum()),
        "top_winners": [
            {
                "trade_key": row.trade_key,
                "date": str(row.source_stop_time_utc)[:10],
                "side": row.side,
                "window": row.window,
                "r": float(row.r),
            }
            for row in top_winners.itertuples(index=False)
        ],
        "exit_reason_counts": {str(k): int(v) for k, v in complete["reason"].value_counts().items()},
        "by_year": {},
        "chronological_halves": {},
        "by_side": {},
        "by_window": {},
        "limitations": [
            "Exploratory, in-sample diagnostic: the 632 source events were previously inspected "
            "and informed this hypothesis.",
            "M1 OHLC approximation, not tick replay; recorded spread included and slippage excluded.",
            "Candidate attempts are event-level and may overlap; summed R is not a portfolio equity result.",
            "Locked exam interval [2026-04-18, 2026-10-18) and all later data were excluded.",
            "This result cannot independently confirm future profitability or promote the setup.",
        ],
    }
    for year, group in complete.groupby("year"):
        summary["by_year"][str(year)] = {
            "attempts": len(group),
            "total_R": float(group["r"].sum()),
            "mean_R": float(group["r"].mean()),
            "win_rate": float((group["r"] > 0).mean()),
        }
    split = len(complete) // 2
    for label, group in (("first_half", complete.iloc[:split]), ("second_half", complete.iloc[split:])):
        if len(group):
            summary["chronological_halves"][label] = {
                "attempts": len(group),
                "total_R": float(group["r"].sum()),
                "mean_R": float(group["r"].mean()),
                "win_rate": float((group["r"] > 0).mean()),
            }
    for dimension in ("side", "window"):
        for key, group in complete.groupby(dimension):
            summary[f"by_{dimension}"][str(key)] = {
                "attempts": len(group),
                "total_R": float(group["r"].sum()),
                "mean_R": float(group["r"].mean()),
                "win_rate": float((group["r"] > 0).mean()),
            }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    render_report(summary)
    print(json.dumps(summary, indent=2))  # noqa: T201


def render_report(s: dict[str, object]) -> None:
    rows = [
        "# RETEST-CONTINUATION V1 — Historical Diagnostic",
        "",
        "**Decision: diagnostic only; do not add to the strategy or claim verified profitability.**",
        "",
        "## Result",
        "",
        f"- Frozen source-stop cohort: **{s['cohort_events']}** events.",
        f"- Completed candidate attempts: **{s['completed_attempts']}**.",
        (
            f"- Event-level total: **{s['net_total_R']:.3f}R**; "
            f"mean: **{s['mean_R_per_completed_attempt']:.3f}R/attempt**; "
            f"win rate: **{s['win_rate']:.1%}**."
        )
        if s["completed_attempts"]
        else "- No completed candidate attempts.",
        (
            f"- Median holding time: **{s['median_holding_minutes']:.1f} minutes**; "
            f"average MFE **{s['mean_MFE_R']:.2f}R**, average MAE **{s['mean_MAE_R']:.2f}R**."
        )
        if s["completed_attempts"]
        else "",
        (
            f"- Median trade **{s['median_R']:.3f}R**; best **{s['best_R']:.3f}R**; "
            f"worst **{s['worst_R']:.3f}R**."
        ),
        (
            f"- Event-order drawdown **{s['event_sequence_max_drawdown_R']:.3f}R** "
            "(overlapping attempts; not portfolio drawdown)."
        ),
        (
            f"- Top 3 winners contribute **{s['top3_winner_share_of_total_R']:.1%}** of total R; "
            f"excluding them leaves **{s['total_R_ex_top3']:.3f}R**."
        ),
        "",
        "## Coverage by outcome/status",
        "",
        "| Status | Events |",
        "|---|---:|",
    ]
    rows.extend(f"| {k} | {v} |" for k, v in s["event_status_counts"].items())
    rows += [
        "",
        "## Annual completed attempts",
        "",
        "| Year | Attempts | Total R | Mean R | Win rate |",
        "|---:|---:|---:|---:|---:|",
    ]
    for year, v in s["by_year"].items():
        rows.append(
            f"| {year} | {v['attempts']} | {v['total_R']:.3f} | {v['mean_R']:.3f} | {v['win_rate']:.1%} |"
        )
    rows += [
        "",
        "## Chronological halves",
        "",
        "| Half | Attempts | Total R | Mean R | Win rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, v in s["chronological_halves"].items():
        rows.append(
            f"| {label} | {v['attempts']} | {v['total_R']:.3f} | {v['mean_R']:.3f} | {v['win_rate']:.1%} |"
        )
    for dimension, title in (("by_side", "Side"), ("by_window", "Window")):
        rows += [
            "",
            f"## Completed attempts by {title.lower()}",
            "",
            f"| {title} | Attempts | Total R | Mean R | Win rate |",
            "|---|---:|---:|---:|---:|",
        ]
        for label, v in s[dimension].items():
            rows.append(
                f"| {label} | {v['attempts']} | {v['total_R']:.3f} | "
                f"{v['mean_R']:.3f} | {v['win_rate']:.1%} |"
            )
    rows += ["", "## Largest winners", "", "| Trade | Date | Side | Window | R |", "|---|---|---|---|---:|"]
    rows.extend(
        f"| {v['trade_key']} | {v['date']} | {v['side']} | {v['window']} | {v['r']:.3f} |"
        for v in s["top_winners"]
    )
    rows += ["", "## Exit reasons", "", "| Reason | Trades |", "|---|---:|"]
    rows.extend(f"| {k} | {v} |" for k, v in s["exit_reason_counts"].items())
    rows += ["", "## Interpretation and limitations", ""]
    rows.extend(f"- {item}" for item in s["limitations"])
    rows += [
        "",
        "Trade-level records are in `diagnostic_trades.csv`; machine-readable summary is in `summary.json`.",
        "",
    ]
    (OUTPUT / "DIAGNOSTIC_RESULTS.md").write_text("\n".join(rows), encoding="utf-8")


if __name__ == "__main__":
    main()
