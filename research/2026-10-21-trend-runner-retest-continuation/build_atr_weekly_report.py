"""Build a chronological, event-level weekly replay from ATR learning decisions."""

# ruff: noqa: E501, T201

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "historical_diagnostic"
SOURCE = DATA / "atr_regime_trade_learning.csv"


def main() -> None:
    trades = pd.read_csv(SOURCE, parse_dates=["source_stop_time_utc", "candidate_exit_time_utc"])
    trades["source_stop_time_utc"] = pd.to_datetime(trades["source_stop_time_utc"], utc=True)
    trades["candidate_exit_time_utc"] = pd.to_datetime(
        trades["candidate_exit_time_utc"], utc=True, errors="coerce"
    )
    trades["week_start_utc"] = trades["source_stop_time_utc"].dt.normalize() - pd.to_timedelta(
        trades["source_stop_time_utc"].dt.weekday, unit="D"
    )
    weeks = trades.groupby("week_start_utc", sort=True)
    lines = [
        "# ATR-adaptive strategy — week-by-week historical replay",
        "",
        "This is a chronological research journal, not live trading. Each event's ATR state is computed from completed M15/M30/H1 bars available at its decision time. The adaptive decision uses only prior allowed trades whose outcomes had already settled. A blocked trade's counterfactual result is recorded for evaluation but never updates the policy.",
        "The three policy paths are distinct: the trailing learner and source-stop screen below evaluate ATR at the original source stop; the frozen entry-time lock was tested separately on 2021-09..2023-10 and is summarized in `historical_holdout_2021_2023/HOLDOUT_RESULTS.md`.",
        "",
        "R values are candidate trade outcomes, not account equity. Weeks are UTC Monday-start; only weeks containing source events are listed. The locked exam period is excluded.",
        "",
        "## Weekly replay",
    ]
    cumulative_base = 0.0
    cumulative_adaptive = 0.0
    cumulative_fixed = 0.0
    for week_start, frame in weeks:
        completed = frame[frame["candidate_r"].notna()]
        selected = frame[frame["selected_r"].notna()]
        blocked = frame[frame["blocked_counterfactual_r"].notna()]
        fixed_selected = frame[frame["fixed_atr_selected_r"].notna()]
        fixed_blocked = frame[frame["fixed_atr_blocked_r"].notna()]
        base_r = float(completed["candidate_r"].sum())
        adaptive_r = float(selected["selected_r"].sum())
        fixed_r = float(fixed_selected["fixed_atr_selected_r"].sum())
        fixed_blocked_r = float(fixed_blocked["fixed_atr_blocked_r"].sum())
        cumulative_base += base_r
        cumulative_adaptive += adaptive_r
        cumulative_fixed += fixed_r
        lines.extend(
            [
                "",
                f"### Week of {week_start:%Y-%m-%d} UTC",
                "",
                f"Events: {len(frame)}; high-ATR: {int(frame['atr_regime'].eq('HIGH').sum())}; completed candidate trades: {len(completed)}; allowed: {len(selected)}; blocked completed: {len(blocked)}.",
                f"This week: frozen {base_r:+.3f}R; trailing adaptive {adaptive_r:+.3f}R; source-stop ATR-state screen {fixed_r:+.3f}R (blocked {fixed_blocked_r:+.3f}R). Cumulative: frozen {cumulative_base:+.3f}R; trailing adaptive {cumulative_adaptive:+.3f}R; source-stop screen {cumulative_fixed:+.3f}R.",
                "",
                "| UTC decision | Side / window | ATR state (M15/M30/H1; composite) | Prior settled same-state trades | Decision | Outcome |",
                "|---|---|---|---:|---|---|",
            ]
        )
        for row in frame.itertuples(index=False):
            prior_mean = (
                "—"
                if pd.isna(row.prior_allowed_completed_mean_r)
                else f"{row.prior_allowed_completed_mean_r:+.3f}R"
            )
            prior = f"{row.prior_allowed_completed_n}; mean {prior_mean}"
            atr = f"{row.atr_m15_pct:.2f}/{row.atr_m30_pct:.2f}/{row.atr_h1_pct:.2f}; {row.atr_composite_pct:.2f}"
            if row.status == "COMPLETE":
                outcome = f"{row.candidate_r:+.3f}R"
                if not row.allowed:
                    outcome += " (blocked counterfactual)"
            else:
                outcome = f"no entry: {row.status}"
            lines.append(
                f"| {row.source_stop_time_utc:%Y-%m-%d %H:%M} | {row.side} / {row.window} | {row.atr_regime} ({atr}) | {prior} | trailing: {row.action}; fixed: {row.fixed_atr_action} | {outcome} |"
            )
        high = frame[frame["atr_regime"].eq("HIGH")]
        normal = frame[frame["atr_regime"].ne("HIGH")]
        state_summary = []
        for label, state_frame in (("HIGH", high), ("NORMAL_OR_LOW", normal)):
            state_done = state_frame[state_frame["candidate_r"].notna()]
            if len(state_done):
                state_summary.append(
                    f"{label}: {len(state_done)} trades, {state_done['candidate_r'].sum():+.3f}R"
                )
        lines.extend(
            [
                "",
                "**Weekly market-state read:** "
                + ("; ".join(state_summary) if state_summary else "no completed trades in either state")
                + ".",
            ]
        )
    completed_all = trades[trades["candidate_r"].notna()].sort_values("source_stop_time_utc")
    fixed_all = completed_all[completed_all["fixed_atr_selected_r"].notna()]
    high_all = completed_all[completed_all["fixed_atr_blocked_r"].notna()]
    midpoint = len(completed_all) // 2
    high_first = completed_all.iloc[:midpoint].loc[
        completed_all.iloc[:midpoint]["fixed_atr_blocked_r"].notna(), "fixed_atr_blocked_r"
    ]
    high_second = completed_all.iloc[midpoint:].loc[
        completed_all.iloc[midpoint:]["fixed_atr_blocked_r"].notna(), "fixed_atr_blocked_r"
    ]
    lines += [
        "",
        "## What the sequence says",
        "",
        f"The trailing-mean ATR policy selected {int(trades['selected_r'].count())} attempts for {trades['selected_r'].sum():+.3f}R and blocked {int(trades['blocked_counterfactual_r'].count())} trades worth {trades['blocked_counterfactual_r'].sum():+.3f}R, so it is not adopted. The simpler fixed high-ATR lock selected {len(fixed_all)} attempts for {fixed_all['fixed_atr_selected_r'].sum():+.3f}R; its {len(high_all)} blocked high-ATR attempts summed to {high_all['fixed_atr_blocked_r'].sum():+.3f}R (first/second chronological halves {high_first.sum():+.3f}R / {high_second.sum():+.3f}R). This is a promising research lead, not validation: only 15 high-ATR attempts and the cutoff came from previously inspected data. The per-trade table exposes decisions and weekly cumulative paths. Do not retune against these same weeks; independent proof needs an untouched sample.",
        "",
    ]
    output = DATA / "ATR_WEEKLY_SEQUENTIAL_REPLAY.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {output} ({len(weeks)} weeks, {len(trades)} events)")


if __name__ == "__main__":
    main()
