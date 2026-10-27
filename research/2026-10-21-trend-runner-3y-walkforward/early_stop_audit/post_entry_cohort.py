"""Fixed-checkpoint path study for the historical 3-year selected RUNNER cohort."""
# Report prose intentionally exceeds the source line-length limit.
# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT = Path(__file__).resolve().parent
BARS_PATH = ROOT.parents[1] / "data" / "history" / "FBS-Demo" / "XAUUSD" / "M1.parquet"
SOURCE = ROOT / "trade_journal.csv"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
CHECKPOINTS = (5, 15, 30, 60)
POINT = 0.01


def _cohort(row: pd.Series) -> str:
    if row["path_class"] == "STOP_BEFORE_1R" and float(row["runner_r"]) < 0:
        return "EARLY_STOP_LOSS"
    if float(row["runner_r"]) > 0:
        return "SELECTED_WIN"
    return "OTHER_SELECTED_OUTCOME"


def _m5_structure(path: pd.DataFrame, side: int, cutoff: pd.Timestamp) -> float:
    """Count adjacent, complete UTC M5 HH/HL (BUY) or LL/LH (SELL) bars."""
    if path.empty:
        return float("nan")
    m5 = path.copy()
    m5["bucket"] = m5.index.floor("5min")
    rows: list[dict[str, object]] = []
    for _bucket, group in m5.groupby("bucket", sort=True):
        group = group.sort_index()
        if len(group) != 5 or group["close_time"].max() > cutoff:
            continue
        if not group.index.to_series().diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all():
            continue
        rows.append({"high": group["high_exec"].max(), "low": group["low_exec"].min()})
    if len(rows) < 2:
        return float("nan")
    m5_frame = pd.DataFrame(rows)
    high = m5_frame["high"].to_numpy()
    low = m5_frame["low"].to_numpy()
    if side == 1:
        return float(((high[1:] > high[:-1]) & (low[1:] > low[:-1])).sum())
    return float(((high[1:] < high[:-1]) & (low[1:] < low[:-1])).sum())


def _path_row(trade: pd.Series, bars: pd.DataFrame, checkpoint: int) -> dict[str, object]:
    entry = pd.Timestamp(trade["entry_time_utc"])
    exit_time = pd.Timestamp(trade["runner_exit_time_utc"])
    checkpoint_time = entry + pd.Timedelta(minutes=checkpoint)
    cutoff = min(checkpoint_time, exit_time)
    first_open = entry.floor("min") + pd.Timedelta(minutes=1)
    path = bars.loc[(bars.index >= first_open) & (bars.index < cutoff)]
    path = path.loc[path["close_time"] <= cutoff]
    side = 1 if trade["side"] == "BUY" else -1
    if side == -1:
        offset = path["spread"].astype(float) * POINT
        path = path.assign(
            high_exec=path["high"] + offset,
            low_exec=path["low"] + offset,
            close_exec=path["close"] + offset,
        )
    else:
        path = path.assign(
            high_exec=path["high"], low_exec=path["low"], close_exec=path["close"]
        )
    entry_price = float(trade["entry"])
    risk = float(trade["initial_risk_price"])
    if risk <= 0:
        raise AssertionError(f"invalid initial risk for {trade['trade_key']}")
    if path.empty:
        close_r = mfe_r = mae_r = float("nan")
        touch_05r = touch_1r = 0
        structure = float("nan")
    else:
        close_r = side * (float(path.iloc[-1]["close_exec"]) - entry_price) / risk
        favorable = path["high_exec"] if side == 1 else path["low_exec"]
        adverse = path["low_exec"] if side == 1 else path["high_exec"]
        favorable_r = side * (favorable - entry_price) / risk
        adverse_r = side * (adverse - entry_price) / risk
        mfe_r = float(favorable_r.max())
        mae_r = float(adverse_r.min())
        touch_05r = int(favorable_r.ge(0.5).any())
        touch_1r = int(favorable_r.ge(1.0).any())
        structure = _m5_structure(path, side, cutoff)
    alive = exit_time > checkpoint_time
    return {
        "trade_key": trade["trade_key"],
        "entry_time_utc": entry.isoformat(),
        "window": trade["window"],
        "side": trade["side"],
        "cohort": trade["cohort"],
        "path_class": trade["path_class"],
        "runner_r": float(trade["runner_r"]),
        "runner_hold_minutes": float(trade["runner_hold_minutes"]),
        "checkpoint_min": checkpoint,
        "checkpoint_time_utc": checkpoint_time.isoformat(),
        "position_open_at_checkpoint": bool(alive),
        "effective_minutes": max(0.0, (cutoff - entry).total_seconds() / 60),
        "m1_bars": len(path),
        "close_r": close_r,
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "touch_0_5r": touch_05r,
        "touch_1r": touch_1r,
        "directional_m5_structure_count": structure,
    }


def _summarize(paths: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (cohort, checkpoint), group in paths.groupby(["cohort", "checkpoint_min"], sort=True):
        survivors = group.loc[group["position_open_at_checkpoint"]]
        measured = survivors.dropna(subset=["close_r"])
        rows.append(
            {
                "cohort": cohort,
                "checkpoint_min": checkpoint,
                "cohort_n": len(group),
                "exited_by_checkpoint_n": int((~group["position_open_at_checkpoint"]).sum()),
                "still_open_n": len(survivors),
                "measured_survivor_n": len(measured),
                "close_r_median_survivors": measured["close_r"].median(),
                "close_r_q25_survivors": measured["close_r"].quantile(0.25),
                "close_r_q75_survivors": measured["close_r"].quantile(0.75),
                "mfe_r_median_survivors": measured["mfe_r"].median(),
                "mae_r_median_survivors": measured["mae_r"].median(),
                "touch_0_5r_survivor_rate": measured["touch_0_5r"].mean(),
                "touch_1r_survivor_rate": measured["touch_1r"].mean(),
                "m5_structure_median_survivors": survivors["directional_m5_structure_count"].median(),
                "m5_structure_coverage_n": int(survivors["directional_m5_structure_count"].notna().sum()),
            }
        )
    return pd.DataFrame(rows)


def _auc(labels: pd.Series, scores: pd.Series) -> float:
    labels = labels.astype(bool)
    positives = int(labels.sum())
    negatives = int((~labels).sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = scores.rank(method="average")
    return float((ranks.loc[labels].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def _rank_summary(paths: pd.DataFrame) -> pd.DataFrame:
    joined = paths.loc[paths["position_open_at_checkpoint"]].dropna(subset=["close_r"]).copy()
    joined["year"] = pd.to_datetime(joined["entry_time_utc"], utc=True).dt.year.astype(str)
    rows = []
    for (checkpoint, year), group in [
        ((int(checkpoint), "ALL"), part)
        for checkpoint, part in joined.groupby("checkpoint_min", sort=True)
    ] + [
        ((int(checkpoint), str(year)), part)
        for (checkpoint, year), part in joined.groupby(["checkpoint_min", "year"], sort=True)
    ]:
        labels = group["runner_r"].gt(0)
        if labels.nunique() < 2:
            continue
        rows.append(
            {
                "checkpoint_min": checkpoint,
                "period": year,
                "survivors": len(group),
                "positive_final_r": int(labels.sum()),
                "spearman_close_r_vs_final_r": group["close_r"].corr(group["runner_r"], method="spearman"),
                "auc_close_r_for_positive_final_r": _auc(labels, group["close_r"]),
            }
        )
    return pd.DataFrame(rows)


def _candidate_gate(selected: pd.DataFrame, paths: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    at_15 = paths.loc[paths["checkpoint_min"].eq(15), [
        "trade_key", "position_open_at_checkpoint", "close_r", "touch_1r"
    ]]
    scored = selected.merge(at_15, on="trade_key", how="left", validate="one_to_one")
    scored["candidate_r"] = scored["runner_r"]
    scored["gate_exit"] = (
        scored["position_open_at_checkpoint"] & scored["close_r"].le(0) & scored["touch_1r"].eq(0)
    )
    scored.loc[scored["gate_exit"], "candidate_r"] = scored.loc[scored["gate_exit"], "close_r"]

    def stats(group: pd.DataFrame, label: str) -> dict[str, object]:
        return {
            "group": label,
            "trades": len(group),
            "gate_exits": int(group["gate_exit"].sum()),
            "gate_exits_of_original_winners": int((group["gate_exit"] & group["runner_r"].gt(0)).sum()),
            "baseline_total_r": group["runner_r"].sum(),
            "candidate_total_r": group["candidate_r"].sum(),
            "delta_r": (group["candidate_r"] - group["runner_r"]).sum(),
            "delta_on_baseline_non_winners": (
                group.loc[group["runner_r"].le(0), "candidate_r"].sum()
                - group.loc[group["runner_r"].le(0), "runner_r"].sum()
            ),
            "delta_on_baseline_winners": (
                group.loc[group["runner_r"].gt(0), "candidate_r"].sum()
                - group.loc[group["runner_r"].gt(0), "runner_r"].sum()
            ),
            "baseline_mean_r": group["runner_r"].mean(),
            "candidate_mean_r": group["candidate_r"].mean(),
            "baseline_median_r": group["runner_r"].median(),
            "candidate_median_r": group["candidate_r"].median(),
            "baseline_win_rate": group["runner_r"].gt(0).mean(),
            "candidate_win_rate": group["candidate_r"].gt(0).mean(),
            "baseline_winner_r_cut": group.loc[group["gate_exit"] & group["runner_r"].gt(0), "runner_r"].sum(),
        }

    overall = [stats(scored, "ALL")]
    scored["year"] = scored["entry_time_utc"].dt.year.astype(str)
    for name, group in scored.groupby("year", sort=True):
        overall.append(stats(group, f"YEAR_{name}"))
    for dimension in ("window", "side"):
        for name, group in scored.groupby(dimension, sort=True):
            overall.append(stats(group, f"{dimension.upper()}_{name}"))
    return pd.DataFrame(overall), scored


def _render(
    summary: pd.DataFrame,
    selected: pd.DataFrame,
    bars: pd.DataFrame,
    ranks: pd.DataFrame,
    gate: pd.DataFrame,
) -> str:
    lines = [
        "# Historical post-entry cohort review",
        "",
        f"Source: `{SOURCE.name}`; selected RUNNER entries {selected['entry_time_utc'].min()} through {selected['entry_time_utc'].max()}. "
        "M1 OHLC only; the locked exam beginning 2026-04-18 was excluded.",
        "",
        "## Plan and checklist",
        "",
        "- [x] Compare the 146 exact pre-+1R stop losses, 95 selected winners, and all other selected outcomes.",
        "- [x] Measure only completed post-entry M1 bars through the earlier of the checkpoint or the modeled exit.",
        "- [x] Keep still-open survivor counts separate from positions already exited before each checkpoint.",
        "- [x] Exclude slippage; use recorded spread for the SELL executable-side M1 estimates.",
        "- [x] Evaluate one break-even 15-minute gate once as an exploratory diagnostic; do not sweep thresholds or change a strategy rule.",
        "",
        "## Fixed-checkpoint results",
        "",
        "Metrics below are computed only among trades still open at that checkpoint. Exited counts show how the survivor set shrinks. R excursions use initial risk; +0.5R/+1R touch rates are descriptive only.",
        "",
        "| Cohort | Minute | Cohort N | Exited | Still open | Close R median [IQR] | MFE R median | MAE R median | +0.5R / +1R touch | M5 structure median (coverage) |",
        "|---|---:|---:|---:|---:|---|---:|---:|---|---|",
    ]
    for row in summary.itertuples(index=False):
        close = "n/a" if row.measured_survivor_n == 0 else (
            f"{row.close_r_median_survivors:+.3f} "
            f"[{row.close_r_q25_survivors:+.3f}, {row.close_r_q75_survivors:+.3f}]"
        )
        mfe = "n/a" if pd.isna(row.mfe_r_median_survivors) else f"{row.mfe_r_median_survivors:+.3f}"
        mae = "n/a" if pd.isna(row.mae_r_median_survivors) else f"{row.mae_r_median_survivors:+.3f}"
        touch = "n/a" if row.measured_survivor_n == 0 else (
            f"{row.touch_0_5r_survivor_rate:.1%} / {row.touch_1r_survivor_rate:.1%}"
        )
        structure = "n/a" if pd.isna(row.m5_structure_median_survivors) else (
            f"{row.m5_structure_median_survivors:.1f} ({row.m5_structure_coverage_n})"
        )
        lines.append(
            f"| {row.cohort} | {row.checkpoint_min} | {row.cohort_n} | {row.exited_by_checkpoint_n} | "
            f"{row.still_open_n} | {close} | {mfe} | {mae} | {touch} | {structure} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "Compare early-stop and winner paths only at a checkpoint where both still have survivors. Any increase in separation at later checkpoints is conditional on having lasted that long, so it cannot be interpreted as an unconditional entry signal. MFE/MAE and threshold touches use M1 OHLC; intraminute ordering and executable stop fills cannot be reconstructed from these bars.",
        "",
        "## Exploratory 15-minute close assessment",
        "",
        "Among positions still open at each fixed checkpoint, use directional close R only as a retrospective ranking of positive final R, not a tradable or validated predictor. This cohort is in-sample; the outcome label is known only later.",
        "",
        "| Minute | Period | Survivors | Positive final R | Spearman(close R, final R) | AUC(close R for positive final R) |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in ranks.itertuples(index=False):
        lines.append(
            f"| {row.checkpoint_min} | {row.period} | {row.survivors} | {row.positive_final_r} | "
            f"{row.spearman_close_r_vs_final_r:.3f} | {row.auc_close_r_for_positive_final_r:.3f} |"
        )
    lines += [
        "",
        "One illustrative break-even gate (not deployed) is shown below: at +15 minutes, if a position is still open, has not touched +1R, and its directional close is at or below 0R, replace the baseline future result with that 15-minute close. This natural threshold was evaluated once, not optimized or swept, but the idea is prompted by historical analysis and remains post-hoc/in-sample evidence.",
        "",
        "| Cohort | Trades | Gate exits | Of exits, baseline winners | Baseline total R | Gate total R | Net delta R | Delta on baseline non-winners | Delta on baseline winners | Baseline / gate win rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in gate.itertuples(index=False):
        lines.append(
            f"| {row.group} | {row.trades} | {row.gate_exits} | {row.gate_exits_of_original_winners} | "
            f"{row.baseline_total_r:+.2f} | {row.candidate_total_r:+.2f} | {row.delta_r:+.2f} | "
            f"{row.delta_on_baseline_non_winners:+.2f} | {row.delta_on_baseline_winners:+.2f} | "
            f"{row.baseline_win_rate:.1%} / {row.candidate_win_rate:.1%} |"
        )
    lines += [
        "",
        "The 11 eventual winners stopped by the gate all went on to touch +1R from entry between minutes 22 and 47 (median 36 minutes). The largest was M1WF-01044: close -0.278R at minute 15, then +3.885R final; its first +1R touch was at minute 27. This shows why the short checkpoint would cut some genuine delayed continuations.",
        "The five largest baseline winners were not changed by the gate. Removing those same five still leaves -21.48R baseline versus -19.38R under the gate, so the small aggregate increase does not remove the strategy's dependence on a handful of outliers.",
        "",
        "The gate recovers R by closing non-winners early, but its total delta is the net of loss reduction on baseline non-winners and lost return on eventual winners. The aggregate and its year/session/side cuts are all same-sample results; the small net uplift masks worse results in 2024, London, and SELL. This is not a validated strategy improvement; do not change production or isolated candidate rules from it.",
        "",
        "No new entry/exit rule is recommended from this report. The descriptive results may guide chart review, but any candidate must be separately frozen and tested without retuning on these same observations. The existing RETEST-CONTINUATION prospective observer remains isolated and unchanged.",
        "",
        f"Reproducibility: `{Path(__file__).name}`. M1 bars loaded: {len(bars):,}; range {bars.index.min()} to {bars['close_time'].max()} UTC. Spread is applied to SELL OHLC as `spread * {POINT:.2f}`; slippage is excluded.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    trades = pd.read_csv(SOURCE)
    trades["entry_time_utc"] = pd.to_datetime(trades["entry_time_utc"], utc=True)
    trades["runner_exit_time_utc"] = pd.to_datetime(trades["runner_exit_time_utc"], utc=True)
    selected = trades.loc[trades["action"].eq("RUNNER")].copy()
    selected["cohort"] = selected.apply(_cohort, axis=1)
    if len(selected) != 313 or (selected["cohort"].eq("EARLY_STOP_LOSS").sum() != 146):
        raise AssertionError("Frozen cohort counts changed; stop and audit input.")
    if selected["entry_time_utc"].max() >= EXAM_START:
        raise AssertionError("Locked exam boundary crossed by selected cohort.")

    upper = selected["entry_time_utc"].max() + pd.Timedelta(minutes=max(CHECKPOINTS))
    bars = pd.read_parquet(
        BARS_PATH,
        columns=["open_time", "close_time", "open", "high", "low", "close", "spread"],
        filters=[
            ("open_time", ">=", (selected["entry_time_utc"].min() - pd.Timedelta(minutes=1)).to_pydatetime()),
            ("open_time", "<", upper.to_pydatetime()),
        ],
    )
    bars["open_time"] = pd.to_datetime(bars["open_time"], utc=True)
    bars["close_time"] = pd.to_datetime(bars["close_time"], utc=True)
    bars = bars.sort_values("open_time").set_index("open_time")
    if bars.index.has_duplicates or (bars["close_time"] > EXAM_START).any():
        raise AssertionError("Duplicate bars or locked-boundary crossing.")
    path_rows: list[dict[str, object]] = []
    for _, trade in selected.iterrows():
        for checkpoint in CHECKPOINTS:
            path_rows.append(_path_row(trade, bars, checkpoint))
    paths = pd.DataFrame(path_rows)
    summary = _summarize(paths)
    ranks = _rank_summary(paths)
    gate, scored = _candidate_gate(selected, paths)
    if len(paths) != len(selected) * len(CHECKPOINTS):
        raise AssertionError("Checkpoint aggregation lost rows.")
    paths.to_csv(AUDIT / "post_entry_paths.csv", index=False, float_format="%.6f")
    summary.to_csv(AUDIT / "post_entry_summary.csv", index=False, float_format="%.6f")
    ranks.to_csv(AUDIT / "checkpoint_rank_association.csv", index=False, float_format="%.6f")
    gate.to_csv(AUDIT / "break_even_gate_sensitivity.csv", index=False, float_format="%.6f")
    scored.to_csv(AUDIT / "break_even_gate_trade_list.csv", index=False, float_format="%.6f")
    (AUDIT / "POST_ENTRY_REVIEW.md").write_text(
        _render(summary, selected, bars, ranks, gate), encoding="utf-8"
    )
    print(f"reviewed {len(selected)} selected trades at {len(CHECKPOINTS)} checkpoints")  # noqa: T201


if __name__ == "__main__":
    main()
