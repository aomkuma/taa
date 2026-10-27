"""Exploratory post-entry path diagnostics for the frozen TR3 RUNNER cohort."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREDICTIONS = REPO / "research/2026-10-20-trend-runner-r3/predictions_primary.parquet"
BARS = REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet"
CHECKPOINTS = (15, 30, 60, 120)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions = pd.read_parquet(PREDICTIONS)
    if len(predictions) != 210 or set(predictions["action"].unique()) != {"RUNNER", "SKIP"}:
        raise AssertionError("TR3 primary input no longer matches the frozen 210-row cohort.")
    selected = predictions.loc[predictions["action"].eq("RUNNER")].copy()
    if len(selected) != 83 or not selected["source_period"].isin(["P1", "P2"]).all():
        raise AssertionError("Unexpected selected rows or source period; stop and audit the boundary.")
    if selected["entry_time"].max() >= pd.Timestamp("2026-04-18", tz="UTC"):
        raise AssertionError("A selected entry reaches the locked exam boundary.")

    # Read only the input columns needed and only timestamps that could contribute to the
    # predeclared 120-minute paths. There is no reason to ingest post-boundary market data.
    lower = selected["entry_time"].min().floor("min")
    upper = (selected["entry_time"].max() + pd.Timedelta(minutes=120)).ceil("min")
    bars = pd.read_parquet(
        BARS,
        columns=["open_time", "close_time", "open", "high", "low", "close"],
        filters=[("open_time", ">=", lower.to_pydatetime()), ("open_time", "<", upper.to_pydatetime())],
    )
    bars = bars.sort_values("open_time").reset_index(drop=True)
    if bars["open_time"].duplicated().any():
        raise AssertionError("Duplicate M1 open_time in diagnostic window.")
    return selected, bars


def direction_values(row: pd.Series, bars: pd.DataFrame) -> tuple[float, float, float, int, int, float]:
    """Return close R, MFE R, MAE R, +1R/+3R touch flags, and M5 HH/HL count."""
    side = int(row["side"])
    entry = float(row["entry"])
    risk = float(row["risk"])
    if side not in (-1, 1) or risk <= 0:
        raise AssertionError("Invalid frozen side/risk value.")
    # `bars` here is already bounded to bars fully completed by the checkpoint and after
    # the first whole-minute boundary following entry.
    if bars.empty:
        return (float("nan"), float("nan"), float("nan"), 0, 0, float("nan"))
    close_r = side * (float(bars.iloc[-1]["close"]) - entry) / risk
    favourable_extreme = bars["high"] if side == 1 else bars["low"]
    adverse_extreme = bars["low"] if side == 1 else bars["high"]
    mfe_r = (side * (favourable_extreme - entry) / risk).max()
    mae_r = (side * (adverse_extreme - entry) / risk).min()
    touch_1r = int((side * (favourable_extreme - entry) >= risk).any())
    touch_3r = int((side * (favourable_extreme - entry) >= 3 * risk).any())

    # Count adjacent full, UTC-aligned M5 comparisons that continue in the trade direction.
    m5 = bars.copy()
    m5["bucket"] = m5["open_time"].dt.floor("5min")
    m5 = m5.groupby("bucket", as_index=False).agg(
        n=("open_time", "size"),
        last_close_time=("close_time", "max"),
        high=("high", "max"),
        low=("low", "min"),
    )
    m5 = m5.loc[(m5["n"] == 5) & (m5["last_close_time"] <= bars["close_time"].max())]
    if len(m5) < 2:
        structure = float("nan")
    else:
        h, l = m5["high"].to_numpy(), m5["low"].to_numpy()
        # BUY counts HH and HL comparisons; SELL counts LL and LH comparisons.
        structure = float(((h[1:] > h[:-1]) & (l[1:] > l[:-1])).sum())
        if side == -1:
            structure = float(((h[1:] < h[:-1]) & (l[1:] < l[:-1])).sum())
    return float(close_r), float(mfe_r), float(mae_r), touch_1r, touch_3r, structure


def main() -> None:
    selected, m1 = load_inputs()
    rows: list[dict[str, object]] = []
    path_rows: list[dict[str, object]] = []
    for _, trade in selected.iterrows():
        # Exclude the M1 candle containing the sub-minute entry timestamp, as it may include
        # pre-entry prices. Start with the next whole M1 candle.
        first_open = trade["entry_time"].floor("min") + pd.Timedelta(minutes=1)
        for checkpoint in CHECKPOINTS:
            checkpoint_time = trade["entry_time"] + pd.Timedelta(minutes=checkpoint)
            cutoff = min(checkpoint_time, trade["runner_exit_time"])
            path = m1.loc[
                (m1["open_time"] >= first_open)
                & (m1["close_time"] <= cutoff)
                & (m1["open_time"] >= trade["entry_time"].floor("min"))
            ]
            # Restrict further to a per-trade local window, not merely to the loaded union.
            path = path.loc[path["open_time"] < cutoff]
            close_r, mfe_r, mae_r, touch_1r, touch_3r, structure = direction_values(trade, path)
            path_rows.append({
                "trade_key": trade["trade_key"],
                "source_period": trade["source_period"],
                "outcome": "positive" if trade["runner_r"] > 0 else "non_positive",
                "runner_r": float(trade["runner_r"]),
                "checkpoint_min": checkpoint,
                "position_open_at_checkpoint": bool(trade["runner_exit_time"] > checkpoint_time),
                "effective_minutes": max(0.0, (cutoff - trade["entry_time"]).total_seconds() / 60),
                "m1_bars": int(len(path)),
                "close_r": close_r,
                "mfe_r": mfe_r,
                "mae_r": mae_r,
                "giveback_r": mfe_r - close_r if pd.notna(mfe_r) and pd.notna(close_r) else float("nan"),
                "touch_1r": touch_1r,
                "touch_3r": touch_3r,
                "directional_m5_hh_hl_or_ll_lh": structure,
            })

    paths = pd.DataFrame(path_rows)
    paths.to_csv(ROOT / "trade_paths.csv", index=False, float_format="%.6f")
    for (period, outcome, checkpoint, still_open), group in paths.groupby(
        ["source_period", "outcome", "checkpoint_min", "position_open_at_checkpoint"], sort=True
    ):
        valid = group.dropna(subset=["close_r"])
        rows.append({
            "source_period": period,
            "outcome": outcome,
            "checkpoint_min": checkpoint,
            "still_open_at_checkpoint": still_open,
            "n": int(len(group)),
            "coverage_n": int(len(valid)),
            "close_r_median": valid["close_r"].median(),
            "close_r_q25": valid["close_r"].quantile(.25),
            "close_r_q75": valid["close_r"].quantile(.75),
            "mfe_r_median": group["mfe_r"].median(),
            "mae_r_median": group["mae_r"].median(),
            "giveback_r_median": group["giveback_r"].median(),
            "touch_1r_rate": group["touch_1r"].mean(),
            "touch_3r_rate": group["touch_3r"].mean(),
            "m5_structure_count_median": group["directional_m5_hh_hl_or_ll_lh"].median(),
            "m5_structure_coverage_n": int(group["directional_m5_hh_hl_or_ll_lh"].notna().sum()),
            "m1_bars_median": group["m1_bars"].median(),
            "effective_minutes_median": group["effective_minutes"].median(),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(ROOT / "summary_by_split.csv", index=False, float_format="%.6f")
    pooled_rows: list[dict[str, object]] = []
    for (outcome, checkpoint, still_open), group in paths.groupby(
        ["outcome", "checkpoint_min", "position_open_at_checkpoint"], sort=True
    ):
        valid = group.dropna(subset=["close_r"])
        pooled_rows.append({
            "outcome": outcome,
            "checkpoint_min": checkpoint,
            "still_open_at_checkpoint": still_open,
            "n": int(len(group)),
            "coverage_n": int(len(valid)),
            "close_r_median": valid["close_r"].median(),
            "close_r_q25": valid["close_r"].quantile(.25),
            "close_r_q75": valid["close_r"].quantile(.75),
            "mfe_r_median": group["mfe_r"].median(),
            "mae_r_median": group["mae_r"].median(),
            "giveback_r_median": group["giveback_r"].median(),
            "touch_1r_rate": group["touch_1r"].mean(),
            "touch_3r_rate": group["touch_3r"].mean(),
            "m5_structure_count_median": group["directional_m5_hh_hl_or_ll_lh"].median(),
            "m5_structure_coverage_n": int(group["directional_m5_hh_hl_or_ll_lh"].notna().sum()),
            "m1_bars_median": group["m1_bars"].median(),
            "effective_minutes_median": group["effective_minutes"].median(),
        })
    pooled_summary = pd.DataFrame(pooled_rows)
    pooled_summary.to_csv(ROOT / "summary.csv", index=False, float_format="%.6f")
    print(f"selected={len(selected)} positive={(selected.runner_r > 0).sum()} non_positive={(selected.runner_r <= 0).sum()}")
    print(f"P1={int((selected.source_period == 'P1').sum())} P2={int((selected.source_period == 'P2').sum())}")
    durations = (selected["runner_exit_time"] - selected["entry_time"]).dt.total_seconds() / 60
    print(f"entry_range={selected.entry_time.min()}..{selected.entry_time.max()}")
    print("still_open_counts=" + ", ".join(f"{m}m:{int((durations > m).sum())}" for m in CHECKPOINTS))
    print(f"M1_rows={len(m1)} M1_range={m1.open_time.min()}..{m1.close_time.max()}")
    print(pooled_summary.to_string(index=False))


if __name__ == "__main__":
    main()
