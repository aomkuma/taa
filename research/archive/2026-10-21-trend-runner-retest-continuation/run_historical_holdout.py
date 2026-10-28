"""Evaluate the frozen ATR entry gate on pre-development XAUUSD history."""

# ruff: noqa: E501, T201

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUTPUT = HERE / "historical_holdout_2021_2023"
M1_PATH = REPO / "data/history_old/FBS-Demo/XAUUSD/M1.parquet"
HOLDOUT_START = pd.Timestamp("2021-09-01T00:00:00Z")
HOLDOUT_END = pd.Timestamp("2023-10-03T00:00:00Z")
GATE = 0.80
POINT = 0.01
BOOTSTRAP_SEED = 20261021
BOOTSTRAP_REPS = 20_000
SUPERSEDED = (
    "Superseded 2026-10-22 (DEBUG_2026-10-22.md): this replay took its TR1 source trades from the "
    "3-year walk-forward's M1-OHLC approximation and managed V1 on M1 bars. Use pipeline.py (tick "
    "fills, tick SPLIT source) one week at a time; the original is kept in _original_2026-10-22/."
)

TR1_DIR = REPO / "research/2026-10-20-trend-runner"
ATR_DIR = REPO / "research/2026-10-21-trend-runner-atr-mtf"
WF_DIR = REPO / "research/2026-10-21-trend-runner-3y-walkforward"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TR1_DIR))
sys.path.insert(0, str(ATR_DIR))
sys.path.insert(0, str(WF_DIR))

import walkforward  # noqa: E402
from candidate import simulate_historical_diagnostic  # noqa: E402
from frozen_round import require_frozen_manifest  # noqa: E402
from run_atr_backtest import attach_last_completed, m30_bars, volatility_frame  # noqa: E402
from tr1.bars import aggregate  # noqa: E402


def read_m1() -> pd.DataFrame:
    frame = pd.read_parquet(
        M1_PATH,
        columns=["open_time", "open", "high", "low", "close", "spread", "tick_volume"],
        filters=[
            ("open_time", ">=", HOLDOUT_START.to_pydatetime()),
            ("open_time", "<", HOLDOUT_END.to_pydatetime()),
        ],
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame = frame.sort_values("open_time").set_index("open_time")
    if frame.empty or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise AssertionError("Holdout M1 bars must be nonempty, unique, and chronological")
    if frame.index.min() < HOLDOUT_START or frame.index.max() >= HOLDOUT_END:
        raise AssertionError("Holdout M1 loader crossed its half-open date boundary")
    return frame


def source_stopped_before_1r(
    m1: pd.DataFrame, entry_time: pd.Timestamp, exit_time: pd.Timestamp, side: int, entry: float, risk: float
) -> bool:
    raise RuntimeError(
        "bug B8: eligibility from M1 bars touching -1R misses trailed stops and same-bar order; "
        "use source_ticks.stopped_before_plus1 on the tick SPLIT result"
    )
    path = m1.loc[entry_time:]
    path = path.loc[path.index < exit_time]
    if path.empty or risk <= 0:
        return False
    spread = path["spread"].to_numpy(float) * POINT if side == -1 else np.zeros(len(path))
    high = path["high"].to_numpy(float) + spread
    low = path["low"].to_numpy(float) + spread
    favorable = (high - entry) * side / risk if side > 0 else (entry - low) / risk
    adverse = (low - entry) * side / risk if side > 0 else (entry - high) / risk
    plus = np.flatnonzero(favorable >= 1.0)
    minus = np.flatnonzero(adverse <= -1.0)
    if not len(minus):
        return False
    if not len(plus):
        return True
    return int(minus[0]) < int(plus[0])


def bootstrap_mean_by_day(values: pd.DataFrame, value_col: str, seed: int) -> list[float]:
    nonempty = values.loc[values[value_col].notna()]
    groups = [g[value_col].to_numpy(float) for _, g in nonempty.groupby("entry_day", sort=True)]
    if not groups:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    n = len(groups)
    means = np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        sampled = rng.integers(0, n, size=n)
        draw = np.concatenate([groups[j] for j in sampled])
        means[i] = draw.mean()
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def bootstrap_paired_delta_by_day(values: pd.DataFrame) -> list[float]:
    groups = [g["delta_r"].to_numpy(float) for _, g in values.groupby("entry_day", sort=True)]
    if not groups:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(BOOTSTRAP_SEED + 1)
    n = len(groups)
    means = np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        sampled = rng.integers(0, n, size=n)
        means[i] = np.concatenate([groups[j] for j in sampled]).mean()
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def main() -> None:
    raise SystemExit(SUPERSEDED)
    require_frozen_manifest()
    # Reuse the frozen TR1 entry and M1 SPLIT/RUNNER simulator on this earlier data segment.
    walkforward.BAR_PATH = M1_PATH
    walkforward.WARMUP_START = HOLDOUT_START
    walkforward.DATA_END = HOLDOUT_END
    walkforward.EXAM_START = HOLDOUT_END
    walkforward.SHADOW_START = HOLDOUT_END

    m1 = read_m1()
    entries = walkforward.generate_entries(m1)
    source_entries_generated = len(entries)
    outcomes = walkforward.add_outcomes(m1, entries)
    complete = outcomes.loc[outcomes["complete"].eq(True)].copy()
    if complete.empty or complete["trade_key"].duplicated().any():
        raise AssertionError("No unique, fully settled frozen-TR1 source outcomes")

    eligible_rows: list[dict[str, object]] = []
    for row in complete.itertuples(index=False):
        if not str(row.runner_reason).startswith("STOP"):
            continue
        entry_time = pd.Timestamp(row.entry_time)
        exit_time = pd.Timestamp(row.runner_exit_time)
        side = int(row.side)
        if not source_stopped_before_1r(m1, entry_time, exit_time, side, float(row.entry), float(row.risk)):
            continue
        stop_time = exit_time
        # Reserve four calendar days for the trigger/hold plus the first executable
        # quote after the 8h deadline in case the market closes across it.
        if stop_time + pd.Timedelta(days=4) >= HOLDOUT_END:
            continue
        original_spread = float(row.spread)
        warm_start = max(HOLDOUT_START, stop_time - pd.Timedelta(hours=3))
        path = m1.loc[warm_start : stop_time + pd.Timedelta(days=4)]
        event = {
            "trade_key": f"OLD-{row.trade_key}",
            "stop_time_utc": stop_time,
            "side": side,
            "entry": float(row.entry),
            "stop": float(row.stop),
            "spread": original_spread,
            "runner_stopped_before_plus1": True,
        }
        candidate = simulate_historical_diagnostic(
            event, path, exam_start=HOLDOUT_END, earliest_data=HOLDOUT_START
        )
        eligible_rows.append(
            {
                "trade_key": event["trade_key"],
                "source_entry_time_utc": entry_time,
                "source_stop_time_utc": stop_time,
                "window": row.window,
                "side": "BUY" if side > 0 else "SELL",
                "source_risk": float(row.risk),
                "source_runner_r": float(row.runner_r),
                **candidate,
            }
        )

    events = pd.DataFrame(eligible_rows).sort_values("source_stop_time_utc").reset_index(drop=True)
    if events.empty:
        raise RuntimeError("The earlier holdout generated no eligible stopped-before-1R source events")
    events["entry_time_utc"] = pd.to_datetime(events["entry_time_utc"], utc=True, errors="coerce")
    events["source_stop_time_utc"] = pd.to_datetime(events["source_stop_time_utc"], utc=True)
    events["decision_time"] = events["entry_time_utc"].fillna(events["source_stop_time_utc"])

    bars_by_tf = {
        "m15": (aggregate(m1, "15min"), 15),
        "m30": (m30_bars(m1), 30),
        "h1": (aggregate(m1, "1h"), 60),
    }
    features = events.copy()
    for name, (bars, minutes) in bars_by_tf.items():
        features = attach_last_completed(features, volatility_frame(bars, minutes, name), name)
        features.rename(
            columns={
                f"atr_pct_{name}": f"atr_{name}_pct",
                f"available_{name}": f"atr_{name}_available_at",
            },
            inplace=True,
        )
    pct_cols = [f"atr_{name}_pct" for name in ("m15", "m30", "h1")]
    availability_cols = [f"atr_{name}_available_at" for name in ("m15", "m30", "h1")]
    features["atr_composite_pct"] = features[pct_cols].median(axis=1)
    features["atr_gate_status"] = np.where(
        features["atr_composite_pct"].notna() & (features["atr_composite_pct"] > GATE),
        "BLOCK_HIGH_ATR",
        np.where(features["atr_composite_pct"].notna(), "ALLOW_ATR", "ATR_UNAVAILABLE"),
    )
    for column in availability_cols:
        if (features[column] > features["decision_time"]).any():
            raise AssertionError(f"Future completed bar attached in {column}")

    features["candidate_r"] = pd.to_numeric(features["r"], errors="coerce")
    features["baseline_r"] = features["candidate_r"].where(features["status"].eq("COMPLETE"))
    features["gate_r"] = features["candidate_r"].where(
        features["status"].eq("COMPLETE") & features["atr_gate_status"].eq("ALLOW_ATR")
    )
    features["blocked_r"] = features["candidate_r"].where(
        features["status"].eq("COMPLETE") & features["atr_gate_status"].eq("BLOCK_HIGH_ATR")
    )
    scored = features.loc[features["baseline_r"].notna()].copy().sort_values("entry_time_utc")
    scored["entry_day"] = scored["entry_time_utc"].dt.floor("D")
    scored["paired_gate_r"] = scored["gate_r"].fillna(0.0)
    scored["delta_r"] = scored["paired_gate_r"] - scored["baseline_r"]
    midpoint = len(scored) // 2
    halves = {"first_half": scored.iloc[:midpoint], "second_half": scored.iloc[midpoint:]}

    base = scored["baseline_r"]
    gated = scored["gate_r"].dropna()
    blocked = scored["blocked_r"].dropna()
    gate_mean_ci = bootstrap_mean_by_day(
        scored.loc[scored["gate_r"].notna()].assign(entry_day=lambda f: f["entry_time_utc"].dt.floor("D")),
        "gate_r",
        BOOTSTRAP_SEED,
    )
    delta_ci = bootstrap_paired_delta_by_day(scored)
    distinct_days = int(scored["entry_day"].nunique())
    selected_days = int(scored.loc[scored["gate_r"].notna(), "entry_day"].nunique())
    volume_pass = (
        len(scored) >= 100 and distinct_days >= 60 and int(gated.count()) >= 100 and selected_days >= 60
    )
    half_means = {
        name: {
            "baseline_n": int(frame["baseline_r"].notna().sum()),
            "baseline_mean_r": float(frame["baseline_r"].mean()),
            "gate_n": int(frame["gate_r"].notna().sum()),
            "gate_mean_r": float(frame["gate_r"].mean()) if frame["gate_r"].notna().any() else None,
        }
        for name, frame in halves.items()
    }
    pass_checks = {
        "minimum_100_baseline_and_gate_attempts_with_60_days_each": volume_pass,
        "fixed_gate_mean_positive_in_both_halves": all(
            item["gate_mean_r"] is not None and item["gate_mean_r"] > 0 for item in half_means.values()
        ),
        "fixed_gate_day_block_95ci_lower_above_zero": gate_mean_ci[0] > 0,
        "paired_increment_day_block_95ci_lower_above_zero": delta_ci[0] > 0,
    }
    status_counts = {str(key): int(value) for key, value in features["status"].value_counts().items()}
    result = {
        "study": "Fixed high-ATR lock on earlier pre-development XAUUSD M1 holdout",
        "holdout_start": HOLDOUT_START.isoformat(),
        "holdout_end_exclusive": HOLDOUT_END.isoformat(),
        "development_period_used_for_gate_selection": "2023-10-30 through 2026-04-16",
        "holdout_data_caveat": "This earlier period was used by other XAUUSD research in the workspace; it was not referenced by this candidate's development scripts, but is not globally virgin market data.",
        "atr_rule": {
            "atr_period": 14,
            "timeframes": ["M15", "M30", "H1"],
            "percentile_lookback": "preceding 120 hours of ATR values, current ATR excluded from reference window",
            "composite": "median of the three causal completed-timeframe percentiles",
            "block_when": "composite percentile strictly greater than 0.80 at actual re-entry entry time",
            "missing_atr": "not gate-eligible; recorded separately",
        },
        "source_rule": "frozen TR1 M1 opportunity + SPLIT/RUNNER M1 OHLC simulator; event eligibility is runner STOP with first adverse -1R before favorable +1R, independent of TR3 action",
        "source_events_generated": source_entries_generated,
        "eligible_source_events": len(features),
        "candidate_attempts": len(scored),
        "candidate_distinct_entry_days": distinct_days,
        "gate_attempts": int(gated.count()),
        "gate_distinct_entry_days": selected_days,
        "blocked_attempts": int(blocked.count()),
        "blocked_counterfactual_total_r": float(blocked.sum()),
        "atr_unavailable_attempts": int(scored["atr_gate_status"].eq("ATR_UNAVAILABLE").sum()),
        "candidate_status_counts": status_counts,
        "censored_candidate_paths_excluded": status_counts.get("PENDING_EXIT_HORIZON", 0),
        "baseline": {
            "n": len(base),
            "total_r": float(base.sum()),
            "mean_r": float(base.mean()),
            "median_r": float(base.median()),
            "win_rate": float((base > 0).mean()),
        },
        "fixed_gate": {
            "n": int(gated.count()),
            "total_r": float(gated.sum()),
            "mean_r": float(gated.mean()) if gated.count() else None,
            "median_r": float(gated.median()) if gated.count() else None,
            "win_rate": float((gated > 0).mean()) if gated.count() else None,
            "day_block_95ci_mean_r": gate_mean_ci,
        },
        "paired_gate_minus_baseline_per_candidate_attempt_day_block_95ci": delta_ci,
        "chronological_halves": half_means,
        "formal_volume_gate": volume_pass,
        "pass_checks": pass_checks,
        "decision": "PASS_RESEARCH_GATE" if all(pass_checks.values()) else "NOT_PASS_RESEARCH_GATE",
        "costs": "M1 recorded spread included; slippage excluded; overlapping event paths are not portfolio equity",
        "locked_exam_read": False,
        "forward_shadow_read": False,
    }
    OUTPUT.mkdir(exist_ok=True)
    features.to_csv(OUTPUT / "holdout_trade_journal.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    (OUTPUT / "holdout_summary.json").write_text(
        json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        "# Fixed ATR lock — earlier historical holdout",
        "",
        f"**Decision: {result['decision']}**. The reserved 2026 exam interval was not opened. This test uses separate earlier XAUUSD M1 bars from 2021-09-01 through 2023-10-02, before this candidate's development cohort. These bars were used by other gold research in the workspace, so this is candidate-specific holdout history, not globally virgin data.",
        "",
        "## Frozen rule",
        "",
        "Block a RETEST-CONTINUATION entry only when the median percentile of causal ATR(14) on completed M15/M30/H1 bars is strictly above 80%. Each percentile ranks current ATR against the preceding 120 hours of ATR values, excluding current ATR. Evaluate at the actual re-entry entry timestamp; allow at or below 80%. No trailing outcome learning or parameter changes are used in this holdout.",
        "",
        "## Holdout result",
        "",
        "The earlier +30.96R source-stop ATR screen from the development journal measures volatility at the original stop, not at re-entry. It is therefore a different filter and must not be presented as the result of this actual-entry gate.",
        "",
        f"Source events generated: {result['source_events_generated']}; eligible stopped-before-1R events: {result['eligible_source_events']}; completed candidate attempts: {result['candidate_attempts']} across {distinct_days} entry days; censored candidate paths excluded: {result['censored_candidate_paths_excluded']}.",
        f"V1 baseline: {base.sum():+.3f}R / {len(base)} attempts; mean {base.mean():+.3f}R; win rate {(base > 0).mean():.1%}.",
        f"Fixed ATR lock: {gated.sum():+.3f}R / {len(gated)} attempts; mean {gated.mean():+.3f}R; win rate {(gated > 0).mean():.1%}; day-block 95% CI for mean [{gate_mean_ci[0]:+.3f}, {gate_mean_ci[1]:+.3f}]R.",
        f"Blocked completed counterfactuals: {len(blocked)} attempts, {blocked.sum():+.3f}R. Paired gate-minus-baseline mean delta per candidate attempt day-block 95% CI [{delta_ci[0]:+.3f}, {delta_ci[1]:+.3f}]R.",
        "",
        "## Predeclared checks",
        "",
    ]
    lines.extend(
        f"- {name.replace('_', ' ')}: {'PASS' if value else 'FAIL'}" for name, value in pass_checks.items()
    )
    lines += [
        "",
        "Chronological halves (split by completed candidate attempts):",
        "",
    ]
    for name, values in half_means.items():
        lines.append(f"- {name}: {values['gate_n']} gate trades; mean {values['gate_mean_r']}")
    lines += [
        "",
        "Limitations: this is an M1 OHLC approximation, not tick replay. The period was not referenced by this candidate's development code but was used by other XAUUSD research in the workspace. Candidate outcomes are event-level, may overlap, include recorded spread, and omit slippage. Any positive result remains historical evidence and requires portfolio/concurrency and operational-parity review before promotion.",
        "",
    ]
    (OUTPUT / "HOLDOUT_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
