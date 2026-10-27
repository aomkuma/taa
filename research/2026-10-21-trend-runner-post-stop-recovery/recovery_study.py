"""Predeclared post-stop recovery and M5-reclaim re-entry study (research only)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
JOURNAL = REPO / "research/2026-10-21-trend-runner-3y-walkforward/trade_journal.csv"
BAR_PATH = REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
SHADOW_START = pd.Timestamp("2026-10-21", tz="UTC")
POINT = 0.01
RECOVERY_HORIZON = pd.Timedelta(hours=8)
REENTRY_HORIZON = pd.Timedelta(minutes=120)


def read_bars() -> pd.DataFrame:
    bars = pd.read_parquet(
        BAR_PATH,
        columns=["open_time", "open", "high", "low", "close", "spread"],
        filters=[("open_time", ">=", pd.Timestamp("2023-09-01", tz="UTC").to_pydatetime()),
                 ("open_time", "<", EXAM_START.to_pydatetime())],
    )
    bars["open_time"] = pd.to_datetime(bars["open_time"], utc=True)
    bars = bars.sort_values("open_time").set_index("open_time", drop=True)
    if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise AssertionError("M1 timestamps must be unique and chronological.")
    if (bars.index >= EXAM_START).any() or (bars.index >= SHADOW_START).any():
        raise AssertionError("Exam or post-shadow M1 bars crossed the loader boundary.")
    return bars


def make_m5(bars: pd.DataFrame) -> pd.DataFrame:
    grouped = bars.groupby(bars.index.floor("5min"), sort=True)
    m5 = grouped.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), spread=("spread", "last"), count=("close", "size"),
    )
    m5["close_time"] = m5.index + pd.Timedelta(minutes=5)
    return m5.loc[m5["count"] == 5].copy()


def _directional(bars: pd.DataFrame, side: int) -> tuple[np.ndarray, ...]:
    offset = bars["spread"].to_numpy(float) * POINT if side < 0 else 0.0
    return tuple(bars[name].to_numpy(float) + offset for name in ("open", "high", "low", "close"))


def _first_cross(values: np.ndarray, level: float, side: int, above: bool) -> int | None:
    crossed = values >= level if (side > 0) == above else values <= level
    found = np.flatnonzero(crossed)
    return int(found[0]) if len(found) else None


def recovery_row(
    event: pd.Series,
    bars: pd.DataFrame,
    m5: pd.DataFrame,
) -> tuple[dict[str, object], dict[str, object] | None]:
    side = 1 if event["side"] == "BUY" else -1
    original_entry = float(event["entry"])
    risk = float(event["initial_risk_price"])
    stop_time = pd.Timestamp(event["runner_exit_time_utc"])
    end = min(stop_time + RECOVERY_HORIZON, EXAM_START)
    lo = int(bars.index.searchsorted(stop_time, side="left"))
    hi = int(bars.index.searchsorted(end, side="left"))
    path = bars.iloc[lo:hi]
    if path.empty:
        raise AssertionError(f"No recovery bars for {event['trade_key']}.")
    op, high, low, close = _directional(path, side)
    times = pd.DatetimeIndex(path.index)
    favorable = ((high if side > 0 else low) - original_entry) * side / risk
    adverse = ((low if side > 0 else high) - original_entry) * side / risk
    rec: dict[str, object] = {
        "trade_key": event["trade_key"], "stop_time_utc": stop_time.isoformat(),
        "year": stop_time.year, "window": event["window"], "side": event["side"],
        "initial_risk": risk, "h1_atr": float(event["h1_atr"]),
        "h1_atr_risk_ratio": float(event["risk_h1_atr"]),
        "initial_runner_r": float(event["runner_r"]),
        "recovery_horizon_minutes": RECOVERY_HORIZON.total_seconds() / 60,
        "full_8h_recovery_observed": stop_time + RECOVERY_HORIZON <= EXAM_START,
        "m5_reclaim_window_complete": stop_time + RECOVERY_HORIZON <= EXAM_START,
        "reclaim_entry_m5_minutes": np.nan,
        "reclaim_entry_m5_time_utc": "",
        "mfe_8h_from_initial_entry_r": (
            float(np.max(favorable)) if stop_time + RECOVERY_HORIZON <= EXAM_START else np.nan
        ),
        "mae_8h_from_initial_entry_r": (
            float(np.min(adverse)) if stop_time + RECOVERY_HORIZON <= EXAM_START else np.nan
        ),
    }
    for minutes in (15, 30, 60, 120, 240, 480):
        horizon_end = stop_time + pd.Timedelta(minutes=minutes)
        covered = horizon_end <= EXAM_START
        rec[f"covered_{minutes}m"] = covered
        if covered:
            mask = times < horizon_end
            hi_fav = favorable[mask]
            for target in (0, 1, 2):
                rec[f"hit_{target:+d}r_{minutes}m"] = bool(np.any(hi_fav >= target))
        else:
            for target in (0, 1, 2):
                rec[f"hit_{target:+d}r_{minutes}m"] = np.nan

    m5_after = m5.loc[(m5["close_time"] > stop_time) & (m5["close_time"] <= end)]
    m5_spread = m5_after["spread"].to_numpy(float) * POINT if side < 0 else 0.0
    m5_close_executable = m5_after["close"].to_numpy(float) + m5_spread
    signal_idx = _first_cross(m5_close_executable, original_entry, side, above=True)
    candidate: dict[str, object] | None = None
    if signal_idx is not None:
        signal_time = pd.Timestamp(m5_after["close_time"].iloc[signal_idx])
        signal_close = float(m5_close_executable[signal_idx])
        rec["reclaim_entry_m5_time_utc"] = signal_time.isoformat()
        rec["reclaim_entry_m5_minutes"] = (signal_time - stop_time).total_seconds() / 60.0
        m1_idx = int(bars.index.searchsorted(signal_time, side="left"))
        if m1_idx < len(bars) and bars.index[m1_idx] <= signal_time + pd.Timedelta(minutes=5):
            reentry_time = pd.Timestamp(bars.index[m1_idx])
            if reentry_time + REENTRY_HORIZON < EXAM_START:
                row = bars.iloc[m1_idx]
                spread = float(row["spread"]) * POINT
                entry_price = float(row["open"]) + (spread if side > 0 else 0.0)
                candidate = simulate_reentry(
                    event=event,
                    bars=bars.loc[reentry_time: reentry_time + REENTRY_HORIZON],
                    side=side,
                    entry_time=reentry_time,
                    entry_price=entry_price,
                    risk=risk,
                    stop_multiple=1.0,
                )
                wider = simulate_reentry(
                    event=event,
                    bars=bars.loc[reentry_time: reentry_time + REENTRY_HORIZON],
                    side=side,
                    entry_time=reentry_time,
                    entry_price=entry_price,
                    risk=risk,
                    stop_multiple=1.5,
                )
                candidate.update({
                    "trade_key": event["trade_key"],
                    "stop_time_utc": stop_time.isoformat(),
                    "m5_signal_time_utc": signal_time.isoformat(),
                    "entry_time_utc": reentry_time.isoformat(),
                    "entry": entry_price,
                    "m5_signal_close_executable": signal_close,
                    "signal_close_offset_from_original_r": (signal_close - original_entry) * side / risk,
                    "entry_offset_from_original_r": (entry_price - original_entry) * side / risk,
                    "initial_risk": risk,
                    "side": event["side"],
                    "year": stop_time.year,
                    "window": event["window"],
                    "h1_atr": float(event["h1_atr"]),
                    "stop_1_5x_r": wider["r"],
                    "stop_1_5x_complete": wider["complete"],
                    "stop_1_5x_exit_reason": wider["exit_reason"],
                    "stop_1_5x_hold_minutes": wider["hold_minutes"],
                    "stop_1_5x_same_bar_stop_target_ambiguous": wider.get(
                        "same_bar_stop_target_ambiguous", False
                    ),
                })
    return rec, candidate


def simulate_reentry(
    event: pd.Series,
    bars: pd.DataFrame,
    side: int,
    entry_time: pd.Timestamp,
    entry_price: float,
    risk: float,
    stop_multiple: float,
) -> dict[str, object]:
    deadline = entry_time + REENTRY_HORIZON
    path = bars.loc[bars.index < deadline]
    if path.empty or path.index[0] != entry_time:
        return {"complete": False, "exit_reason": "MISSING_ENTRY_BAR", "r": np.nan,
                "hold_minutes": np.nan, "exit_time_utc": ""}
    opened, high, low, close = _directional(path, side)
    times = pd.DatetimeIndex(path.index)
    stop = entry_price - side * risk * stop_multiple
    target = entry_price + side * 2.0 * risk
    for i, at in enumerate(times):
        if (opened[i] <= stop if side > 0 else opened[i] >= stop):
            exit_price, reason = opened[i], "STOP_GAP"
        elif (opened[i] >= target if side > 0 else opened[i] <= target):
            exit_price, reason = target, "TARGET_GAP"
        else:
            hit_stop = low[i] <= stop if side > 0 else high[i] >= stop
            hit_target = high[i] >= target if side > 0 else low[i] <= target
            if hit_stop:
                exit_price, reason = stop, "STOP_INTRABAR"
                ambiguous = bool(hit_target)
            elif hit_target:
                exit_price, reason = target, "TARGET_2R"
                ambiguous = False
            else:
                continue
        if reason in {"STOP_GAP", "TARGET_GAP"}:
            ambiguous = False
        if reason.startswith("STOP") or reason.startswith("TARGET"):
            exit_time = at if reason.endswith("GAP") else at + pd.Timedelta(minutes=1)
            result_r = float((exit_price - entry_price) * side / risk)
            after = path.iloc[i:] if reason.endswith("GAP") else path.iloc[i + 1:]
            if not after.empty:
                _, after_high, after_low, _ = _directional(after, side)
                after_fav_r = ((after_high if side > 0 else after_low) - entry_price) * side / risk
                post_exit_favorable = max(0.0, float(np.max(after_fav_r)) - result_r)
                target_after = np.flatnonzero(after_fav_r >= 2.0)
                later_target2 = bool(len(target_after))
                if later_target2:
                    target_i = int(target_after[0])
                    after_adverse_r = ((after_low if side > 0 else after_high) - entry_price) * side / risk
                    worst_before_target2 = float(np.min(after_adverse_r[:target_i + 1]))
                    minutes_to_target2_after_exit = (
                        after.index[target_i] - exit_time
                    ).total_seconds() / 60.0
                    after_start_idx = i if reason.endswith("GAP") else i + 1
                    path_to_later_target = path.iloc[:after_start_idx + target_i + 1]
                    _, full_high, full_low, _ = _directional(path_to_later_target, side)
                    full_adverse_r = ((full_low if side > 0 else full_high) - entry_price) * side / risk
                    worst_from_entry_before_later_target = float(np.min(full_adverse_r))
                else:
                    worst_before_target2 = np.nan
                    minutes_to_target2_after_exit = np.nan
                    worst_from_entry_before_later_target = np.nan
            else:
                post_exit_favorable, later_target2 = 0.0, False
                worst_before_target2, minutes_to_target2_after_exit = np.nan, np.nan
                worst_from_entry_before_later_target = np.nan
            return {"complete": True, "exit_reason": reason,
                    "r": result_r,
                    "hold_minutes": (exit_time - entry_time).total_seconds() / 60.0,
                    "exit_time_utc": exit_time.isoformat(), "same_bar_stop_target_ambiguous": ambiguous,
                    "post_exit_favorable_within_120m_r": post_exit_favorable,
                    "target2_touched_after_exit_within_120m": later_target2,
                    "worst_r_after_exit_before_later_target2": worst_before_target2,
                    "worst_r_from_entry_before_later_target2": worst_from_entry_before_later_target,
                    "minutes_after_exit_to_later_target2": minutes_to_target2_after_exit}
    if path.index[-1] + pd.Timedelta(minutes=1) < deadline - pd.Timedelta(minutes=1):
        return {"complete": False, "exit_reason": "CENSORED_DATA_GAP", "r": np.nan,
                "hold_minutes": np.nan, "exit_time_utc": ""}
    exit_time = path.index[-1] + pd.Timedelta(minutes=1)
    return {"complete": True, "exit_reason": "TIME_120M",
            "r": float((close[-1] - entry_price) * side / risk),
            "hold_minutes": (exit_time - entry_time).total_seconds() / 60.0,
            "exit_time_utc": exit_time.isoformat()}


def summarize(recovery: pd.DataFrame, reentries: pd.DataFrame) -> dict[str, object]:
    summary: dict[str, object] = {
        "source_events": int(len(recovery)),
        "m5_reclaim_eligible_events": int(recovery["m5_reclaim_window_complete"].sum()),
        "events_with_m5_reclaim": int(recovery["reclaim_entry_m5_time_utc"].ne("").sum()),
        "m5_reclaim_time_minutes": {},
        "reentry_attempts": int(len(reentries)),
        "complete_reentries": int(reentries["complete"].sum()) if len(reentries) else 0,
        "censored_reentries": int((~reentries["complete"]).sum()) if len(reentries) else 0,
        "data_boundary_check": "PASS: M1 loader filters strictly before 2026-04-18 UTC.",
        "rule": "first post-stop completed M5 close reclaims original entry in original direction; next M1 open; 1 initial-R stop, 2R target, 120-minute time exit; same-bar stop first.",
        "recovery_by_horizon": {},
        "reentry_metrics": {},
        "reentry_stop_1_5x_metrics": {},
        "reentry_by_year": [],
        "reentry_stop_1_5x_by_year": [],
        "reentry_by_window": [],
        "reentry_stop_1_5x_by_window": [],
        "reentry_by_side": [],
        "recovery_by_window": [],
        "limitations": [
            "This rule was motivated by an already inspected M1 journal; all re-entry returns are exploratory, not validation.",
            "M1 OHLC cannot recover within-minute order or exact executable fills; same-bar ambiguity resolves to stop.",
            "Events are not portfolio-independent; summed R is event-level, not a portfolio equity curve.",
            "A later favorable move after stop is descriptive and does not mean a live re-entry could capture it.",
        ],
    }
    for minutes in (15, 30, 60, 120, 240, 480):
        hit_zero = recovery[f"hit_+0r_{minutes}m"].dropna()
        hit_one = recovery[f"hit_+1r_{minutes}m"].dropna()
        hit_two = recovery[f"hit_+2r_{minutes}m"].dropna()
        summary["recovery_by_horizon"][str(minutes)] = {
            "minutes": minutes,
            "eligible_events": int(len(hit_zero)),
            "reclaim_original_entry_pct": float(100 * hit_zero.mean()),
            "reach_original_plus_1r_pct": float(100 * hit_one.mean()),
            "reach_original_plus_2r_pct": float(100 * hit_two.mean()),
        }
    reclaim_minutes = recovery.loc[recovery["reclaim_entry_m5_minutes"].notna(), "reclaim_entry_m5_minutes"]
    summary["m5_reclaim_time_minutes"] = {
        "median": float(reclaim_minutes.median()),
        "p25": float(reclaim_minutes.quantile(0.25)),
        "p75": float(reclaim_minutes.quantile(0.75)),
    }
    for window, group in recovery.groupby("window", sort=True):
        summary["recovery_by_window"].append({
            "window": str(window), "events": int(len(group)),
            "m5_reclaim_pct": float(100 * group["reclaim_entry_m5_time_utc"].ne("").mean()),
            "reach_original_plus_1r_60m_pct": float(100 * group["hit_+1r_60m"].mean()),
            "reach_original_plus_1r_120m_pct": float(100 * group["hit_+1r_120m"].mean()),
        })
    complete = reentries.loc[reentries["complete"]].copy() if len(reentries) else reentries
    if len(complete):
        x = complete["r"].to_numpy(float)
        later_target_mask = complete["target2_touched_after_exit_within_120m"].fillna(False).astype(bool)
        summary["reentry_metrics"] = {
            "n": int(len(x)), "total_r": float(x.sum()), "mean_r": float(x.mean()),
            "median_r": float(np.median(x)), "win_rate_pct": float(100 * np.mean(x > 0)),
            "max_drawdown_r_event_order": float(np.max(np.maximum.accumulate(np.r_[0.0, np.cumsum(x)]) - np.r_[0.0, np.cumsum(x)])),
            "exit_reason_counts": {str(k): int(v) for k, v in complete["exit_reason"].value_counts().items()},
            "median_hold_minutes": float(complete["hold_minutes"].median()),
            "same_bar_stop_target_ambiguous_count": int(complete["same_bar_stop_target_ambiguous"].sum()),
            "ambiguous_trade_upper_bound_r": float(
                x.sum() + 3.0 * complete["same_bar_stop_target_ambiguous"].sum()
            ),
            "median_entry_offset_from_original_r": float(complete["entry_offset_from_original_r"].median()),
            "median_entry_offset_winners_r": float(
                complete.loc[complete["r"] > 0, "entry_offset_from_original_r"].median()
            ),
            "median_entry_offset_stops_r": float(
                complete.loc[complete["exit_reason"].str.startswith("STOP"), "entry_offset_from_original_r"].median()
            ),
            "stops_later_touching_target2_pct": float(
                100 * complete.loc[complete["exit_reason"].str.startswith("STOP"),
                                   "target2_touched_after_exit_within_120m"].mean()
            ),
            "median_post_exit_favorable_after_stop_r": float(
                complete.loc[complete["exit_reason"].str.startswith("STOP"),
                             "post_exit_favorable_within_120m_r"].median()
            ),
            "later_target2_trade_count": int(
                complete.loc[complete["exit_reason"].str.startswith("STOP"),
                             "target2_touched_after_exit_within_120m"].fillna(False).sum()
            ),
            "median_worst_r_before_later_target2": float(
                complete.loc[later_target_mask,
                             "worst_r_after_exit_before_later_target2"].median()
            ),
            "later_target2_within_1_5r_stop_pct": float(
                100 * complete.loc[later_target_mask,
                                   "worst_r_from_entry_before_later_target2"].ge(-1.5).mean()
            ),
            "later_target2_within_2r_stop_pct": float(
                100 * complete.loc[later_target_mask,
                                   "worst_r_from_entry_before_later_target2"].ge(-2.0).mean()
            ),
            "median_worst_r_full_path_to_later_target2": float(
                complete.loc[later_target_mask, "worst_r_from_entry_before_later_target2"].median()
            ),
        }
        wider = complete.loc[complete["stop_1_5x_complete"]].copy()
        wx = wider["stop_1_5x_r"].to_numpy(float)
        summary["reentry_stop_1_5x_metrics"] = {
            "n": int(len(wx)), "total_r_original_risk_units": float(wx.sum()),
            "mean_r_original_risk_units": float(wx.mean()),
            "mean_r_per_1_5x_stop_risk": float(wx.mean() / 1.5),
            "win_rate_pct": float(100 * np.mean(wx > 0)),
            "median_r_original_risk_units": float(np.median(wx)),
            "exit_reason_counts": {str(k): int(v) for k, v in wider["stop_1_5x_exit_reason"].value_counts().items()},
            "same_bar_stop_target_ambiguous_count": int(
                wider.get("stop_1_5x_same_bar_stop_target_ambiguous", pd.Series(False, index=wider.index)).fillna(False).sum()
            ),
        }
        for year, group in complete.groupby("year", sort=True):
            summary["reentry_by_year"].append({
                "year": int(year), "n": int(len(group)), "total_r": float(group["r"].sum()),
                "mean_r": float(group["r"].mean()), "win_rate_pct": float(100 * group["r"].gt(0).mean()),
            })
        for year, group in wider.groupby("year", sort=True):
            summary["reentry_stop_1_5x_by_year"].append({
                "year": int(year), "n": int(len(group)), "total_r": float(group["stop_1_5x_r"].sum()),
                "mean_r": float(group["stop_1_5x_r"].mean()),
                "win_rate_pct": float(100 * group["stop_1_5x_r"].gt(0).mean()),
            })
        for window, group in wider.groupby("window", sort=True):
            summary["reentry_stop_1_5x_by_window"].append({
                "window": str(window), "n": int(len(group)), "total_r": float(group["stop_1_5x_r"].sum()),
                "mean_r": float(group["stop_1_5x_r"].mean()),
                "win_rate_pct": float(100 * group["stop_1_5x_r"].gt(0).mean()),
            })
        for field, target, label in (("window", "reentry_by_window", "window"),
                                     ("side", "reentry_by_side", "side")):
            for value, group in complete.groupby(field, sort=True):
                summary[target].append({
                    label: str(value), "n": int(len(group)), "total_r": float(group["r"].sum()),
                    "mean_r": float(group["r"].mean()), "win_rate_pct": float(100 * group["r"].gt(0).mean()),
                })
        summary["reentry_by_outcome"] = []
        for outcome, group in complete.assign(outcome=np.where(complete["r"] > 0, "WIN", "NON_WIN")).groupby("outcome"):
            summary["reentry_by_outcome"].append({
                "outcome": str(outcome), "n": int(len(group)),
                "mean_r": float(group["r"].mean()),
                "median_signal_close_offset_r": float(group["signal_close_offset_from_original_r"].median()),
                "median_entry_offset_r": float(group["entry_offset_from_original_r"].median()),
                "median_hold_minutes": float(group["hold_minutes"].median()),
            })
        ordered = complete.sort_values(["stop_time_utc", "trade_key"]).reset_index(drop=True)
        split = max(1, len(ordered) // 2)
        summary["chronological_halves"] = [
            {"half": "earlier", "n": int(len(ordered.iloc[:split])),
             "total_r": float(ordered.iloc[:split]["r"].sum()), "mean_r": float(ordered.iloc[:split]["r"].mean())},
            {"half": "later", "n": int(len(ordered.iloc[split:])),
             "total_r": float(ordered.iloc[split:]["r"].sum()), "mean_r": float(ordered.iloc[split:]["r"].mean())},
        ]
        ordered_wide = wider.sort_values(["stop_time_utc", "trade_key"]).reset_index(drop=True)
        split_wide = max(1, len(ordered_wide) // 2)
        summary["stop_1_5x_chronological_halves"] = [
            {"half": "earlier", "n": int(len(ordered_wide.iloc[:split_wide])),
             "total_r": float(ordered_wide.iloc[:split_wide]["stop_1_5x_r"].sum()),
             "mean_r": float(ordered_wide.iloc[:split_wide]["stop_1_5x_r"].mean())},
            {"half": "later", "n": int(len(ordered_wide.iloc[split_wide:])),
             "total_r": float(ordered_wide.iloc[split_wide:]["stop_1_5x_r"].sum()),
             "mean_r": float(ordered_wide.iloc[split_wide:]["stop_1_5x_r"].mean())},
        ]
    return summary


def make_report(summary: dict[str, object]) -> str:
    m = summary["reentry_metrics"]
    wide = summary["reentry_stop_1_5x_metrics"]
    horizons = summary["recovery_by_horizon"]
    years = "\n".join(
        f"| {r['year']} | {r['n']} | {r['mean_r']:+.3f}R | {r['total_r']:+.2f}R | {r['win_rate_pct']:.1f}% |"
        for r in summary["reentry_by_year"]
    )
    halves = "\n".join(
        f"| {r['half']} | {r['n']} | {r['mean_r']:+.3f}R | {r['total_r']:+.2f}R |"
        for r in summary.get("chronological_halves", [])
    )
    wide_years = "\n".join(
        f"| {r['year']} | {r['n']} | {r['mean_r']:+.3f}R | {r['total_r']:+.2f}R | {r['win_rate_pct']:.1f}% |"
        for r in summary["reentry_stop_1_5x_by_year"]
    )
    wide_halves = "\n".join(
        f"| {r['half']} | {r['n']} | {r['mean_r']:+.3f}R | {r['total_r']:+.2f}R |"
        for r in summary["stop_1_5x_chronological_halves"]
    )
    windows = "\n".join(
        f"| {r['window']} | {r['events']} | {r['m5_reclaim_pct']:.1f}% | {r['reach_original_plus_1r_60m_pct']:.1f}% |"
        for r in summary["recovery_by_window"]
    )
    return f"""# Post-stop recovery and fixed M5 re-entry study

**Decision: the exact immediate M5-reclaim + 1R-stop version failed; this does not reject every re-entry idea.** The 1.5R-stop sensitivity improved substantially but remained negative. Neither version is approved for the strategy or for trading. The wider-stop result is post-hoc exploration on the same data, not confirmation.

## Study definition

Population: {summary['source_events']} frozen walk-forward opportunities stopped before a preceding +1R touch. The locked exam and all post-shadow data were excluded. The implementation follows the written trigger: first completed M5 close back across the original entry in the original direction, then next M1 open. The primary version uses a 1-original-R stop, 2R target, and 120-minute time exit. Entry includes recorded spread; slippage is excluded. Audit found no same-M1 stop/target collisions, so the stop-first ambiguity convention did not cause the negative result. No evident timing/side/spread implementation error was found in the rule as specified; however, M1 OHLC still limits fill-order certainty.

## Re-entry result

- M5 closed back through the original entry in {summary['events_with_m5_reclaim']} / {summary['m5_reclaim_eligible_events']} eligible cases ({100 * summary['events_with_m5_reclaim'] / summary['m5_reclaim_eligible_events']:.1f}%); median wait was {summary['m5_reclaim_time_minutes']['median']:.0f} minutes (IQR {summary['m5_reclaim_time_minutes']['p25']:.0f}-{summary['m5_reclaim_time_minutes']['p75']:.0f}).
- {m['n']} re-entry attempts completed: **{m['total_r']:+.2f}R** total, **{m['mean_r']:+.3f}R per attempt**, {m['win_rate_pct']:.1f}% winners, median result {m['median_r']:+.2f}R, median holding time {m['median_hold_minutes']:.0f} minutes.
- Exits: {m['exit_reason_counts']}.
- Same-M1 stop/target ambiguous cases: **{m['same_bar_stop_target_ambiguous_count']}**. Thus conservative collision handling did not explain this loss.

| Stop-event year | Attempts | Mean R/attempt | Total R | Win rate |
|---|---:|---:|---:|---:|
{years}

| Chronological half | Attempts | Mean R/attempt | Total R |
|---|---:|---:|---:|
{halves}

The 1R-stop candidate is negative in both chronological halves and all calendar-year cuts; the 2026 cut is partial. This establishes failure of this exact rule on this sample, not failure of the entire setup family.

## Stop-width audit: a possible fix, not a pass

Of the {m['exit_reason_counts'].get('STOP_INTRABAR', 0) + m['exit_reason_counts'].get('STOP_GAP', 0)} baseline stop-outs, **{m['later_target2_trade_count']} ({m['stops_later_touching_target2_pct']:.1f}%)** later touched +2R from the re-entry within the remaining observation horizon. Across those later-target paths, median worst adverse excursion was {m['median_worst_r_full_path_to_later_target2']:.2f}R; {m['later_target2_within_1_5r_stop_pct']:.1f}% stayed within 1.5R adverse and {m['later_target2_within_2r_stop_pct']:.1f}% within 2R. This suggests stop width may contribute, but is not proof that a wider stop is the right remedy.

An exploratory sensitivity widened only the stop to 1.5 original-R while keeping the target at +2 original-R, the trigger, entry, and time exit unchanged. This changes the payoff ratio to 2R reward / 1.5R risk. It improved mean return from {m['mean_r']:+.3f} to **{wide['mean_r_original_risk_units']:+.3f} original-risk-R per attempt** ({wide['mean_r_per_1_5x_stop_risk']:+.3f} per 1.5R actually risked), and win rate from {m['win_rate_pct']:.1f}% to {wide['win_rate_pct']:.1f}%, but still lost **{wide['total_r_original_risk_units']:+.2f} original-risk-R total**. This is a useful clue, not a profitable or validated variant.

| 1.5R-stop cut | Attempts | Mean original-risk R | Total original-risk R | Win rate |
|---|---:|---:|---:|---:|
{wide_years}

| Chronological half | Attempts | Mean original-risk R | Total original-risk R |
|---|---:|---:|---:|
{wide_halves}

The wider-stop sensitivity remains mixed across years and negative in both chronological halves. Because it was selected after seeing the baseline losses, these cuts are diagnostic only and must not be used to claim a robust edge.

## How often did the original direction recover?

These are event-path percentages from the original entry price after the initial stop, not re-entry returns. Touching a level uses M1 OHLC and does not prove a tradable fill.

| Minutes after stop | Events with full horizon | Reclaimed original entry | Touched original +1R | Touched original +2R |
|---:|---:|---:|---:|---:|
| 15 | {horizons['15']['eligible_events']} | {horizons['15']['reclaim_original_entry_pct']:.1f}% | {horizons['15']['reach_original_plus_1r_pct']:.1f}% | {horizons['15']['reach_original_plus_2r_pct']:.1f}% |
| 30 | {horizons['30']['eligible_events']} | {horizons['30']['reclaim_original_entry_pct']:.1f}% | {horizons['30']['reach_original_plus_1r_pct']:.1f}% | {horizons['30']['reach_original_plus_2r_pct']:.1f}% |
| 60 | {horizons['60']['eligible_events']} | {horizons['60']['reclaim_original_entry_pct']:.1f}% | {horizons['60']['reach_original_plus_1r_pct']:.1f}% | {horizons['60']['reach_original_plus_2r_pct']:.1f}% |
| 120 | {horizons['120']['eligible_events']} | {horizons['120']['reclaim_original_entry_pct']:.1f}% | {horizons['120']['reach_original_plus_1r_pct']:.1f}% | {horizons['120']['reach_original_plus_2r_pct']:.1f}% |
| 240 | {horizons['240']['eligible_events']} | {horizons['240']['reclaim_original_entry_pct']:.1f}% | {horizons['240']['reach_original_plus_1r_pct']:.1f}% | {horizons['240']['reach_original_plus_2r_pct']:.1f}% |
| 480 | {horizons['480']['eligible_events']} | {horizons['480']['reclaim_original_entry_pct']:.1f}% | {horizons['480']['reach_original_plus_1r_pct']:.1f}% | {horizons['480']['reach_original_plus_2r_pct']:.1f}% |

By original entry window, the M5-reclaim rate and 60-minute +1R rate were:

| Window | Stop events | M5 reclaim | Original +1R within 60m |
|---|---:|---:|---:|
{windows}

## Next development decision

Do not add the tested immediate-reclaim versions to the strategy: 1R stop failed, while 1.5R stop improved but remained negative. Do not conclude that all re-entry or trend-following logic is unusable: later continuation after the stop was common enough to justify one carefully isolated follow-up hypothesis. The next research branch should test whether waiting for a retest/continuation after the M5 reclaim and placing a stop beyond local structure avoids premature stop-outs. Specify and freeze one rule before measuring it; use untouched forward-shadow observations for confirmation. Keep the current strategy frozen and separate; no repeated tuning on this inspected historical sample.

## Limits

M1 OHLC cannot recover exact intra-minute order or executable stop/target fills. The M5 re-entry idea was prompted by already observed trade-journal outcomes, so this replay is not independent validation. Events may overlap; total R is event-level and not a portfolio equity curve. Tick-level price sequence is unavailable across most of the tested period.
"""


def main() -> None:
    journal = pd.read_csv(JOURNAL)
    cohort = journal.loc[journal["path_class"].eq("STOP_BEFORE_1R")].copy()
    if len(cohort) != 632 or cohort["trade_key"].duplicated().any():
        raise AssertionError("The predeclared stopped-before-1R cohort changed unexpectedly.")
    if pd.to_datetime(cohort["runner_exit_time_utc"], utc=True).max() >= EXAM_START:
        raise AssertionError("Source event crossed the historical exam boundary.")
    bars = read_bars()
    m5 = make_m5(bars)
    recoveries: list[dict[str, object]] = []
    candidate_trades: list[dict[str, object]] = []
    for _, event in cohort.iterrows():
        recovery, candidate = recovery_row(event, bars, m5)
        recoveries.append(recovery)
        if candidate is not None:
            candidate_trades.append(candidate)
    recovery_frame = pd.DataFrame(recoveries)
    reentry_frame = pd.DataFrame(candidate_trades)
    summary = summarize(recovery_frame, reentry_frame)
    recovery_frame.to_csv(ROOT / "recovery_events.csv", index=False, float_format="%.6f")
    reentry_frame.to_csv(ROOT / "reentry_trades.csv", index=False, float_format="%.6f")
    (ROOT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (ROOT / "RESULTS.md").write_text(make_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
