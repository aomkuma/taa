"""Build an M1 OHLC path journal for the frozen pre-exam TR1/TR3 replay."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BAR_PATH = REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet"
PREDICTIONS_PATH = ROOT / "predictions_walkforward.parquet"
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
SHADOW_START = pd.Timestamp("2026-10-21", tz="UTC")
POINT = 0.01
HORIZON = pd.Timedelta(hours=8)


def read_bars() -> pd.DataFrame:
    """Load only pre-exam M1 rows; fail closed if a boundary is crossed."""
    frame = pd.read_parquet(
        BAR_PATH,
        columns=["open_time", "open", "high", "low", "close", "spread"],
        filters=[("open_time", ">=", pd.Timestamp("2023-09-01", tz="UTC").to_pydatetime()),
                 ("open_time", "<", EXAM_START.to_pydatetime())],
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame = frame.sort_values("open_time").reset_index(drop=True)
    if (frame["open_time"] >= EXAM_START).any() or (frame["open_time"] >= SHADOW_START).any():
        raise AssertionError("Exam or post-shadow bars crossed the journal data boundary.")
    return frame.set_index("open_time", drop=True)


def _first_touch(
    favorable_r: np.ndarray,
    adverse_r: np.ndarray,
    times: pd.DatetimeIndex,
    start: pd.Timestamp,
) -> tuple[str, float]:
    """First +/-1R touch using M1 bars; mark a same-bar ordering as ambiguous."""
    up = np.flatnonzero(favorable_r >= 1.0)
    down = np.flatnonzero(adverse_r <= -1.0)
    if not len(up) and not len(down):
        return "NEITHER_1R", np.nan
    up_i = int(up[0]) if len(up) else len(times) + 1
    down_i = int(down[0]) if len(down) else len(times) + 1
    if up_i == down_i:
        return "SAME_M1_BAR_AMBIGUOUS", float((times[up_i] - start).total_seconds() / 60.0)
    i = min(up_i, down_i)
    label = "+1R_FIRST" if up_i < down_i else "-1R_FIRST"
    return label, float((times[i] - start).total_seconds() / 60.0)


def _path_metrics(
    bars: pd.DataFrame,
    side: int,
    entry: float,
    risk: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return favorable/adverse R excursions and M1 executable-side timestamps."""
    offset = bars["spread"].to_numpy(float) * POINT if side == -1 else np.zeros(len(bars))
    high = bars["high"].to_numpy(float) + offset
    low = bars["low"].to_numpy(float) + offset
    if side == 1:
        favorable = (high - entry) / risk
        adverse = (low - entry) / risk
    else:
        favorable = (entry - low) / risk
        adverse = (entry - high) / risk
    return favorable, adverse, high, low


def build_journal(bars: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for trade in predictions.itertuples(index=False):
        start = pd.Timestamp(trade.entry_time)
        exit_time = pd.Timestamp(trade.runner_exit_time)
        horizon_end = start + HORIZON
        if start >= EXAM_START or exit_time >= EXAM_START or horizon_end > EXAM_START:
            raise AssertionError(f"Locked exam boundary violation for {trade.trade_key}.")

        lo = int(bars.index.searchsorted(start, side="left"))
        hi = int(bars.index.searchsorted(horizon_end, side="left"))
        path = bars.iloc[lo:hi]
        if path.empty or path.index[0] != start:
            raise AssertionError(f"Missing first M1 entry bar for {trade.trade_key}.")
        favorable, adverse, _, _ = _path_metrics(
            path, int(trade.side), float(trade.entry), float(trade.risk)
        )
        times = pd.DatetimeIndex(path.index)

        # At an open-gap exit the exit bar opens at exit_time and its later range is
        # post-exit. At a close exit, the exit candle is included in pre-exit path.
        pre_mask = times < exit_time
        pre_fav, pre_adv, pre_times = favorable[pre_mask], adverse[pre_mask], times[pre_mask]
        after_mask = times >= exit_time
        post_fav, post_times = favorable[after_mask], times[after_mask]
        if not len(pre_fav):
            pre_fav, pre_adv, pre_times = np.array([0.0]), np.array([0.0]), pd.DatetimeIndex([start])

        mfe_i = int(np.argmax(pre_fav))
        mae_i = int(np.argmin(pre_adv))
        first_1r, first_1r_minutes = _first_touch(pre_fav, pre_adv, pre_times, start)
        milestones: dict[str, object] = {}
        for target in (1, 2, 3):
            hit = np.flatnonzero(pre_fav >= target)
            milestones[f"first_{target}r_minutes"] = (
                float((pre_times[int(hit[0])] - start).total_seconds() / 60.0) if len(hit) else np.nan
            )

        peak_fav = np.maximum.accumulate(pre_fav)
        pullback = np.maximum(peak_fav - pre_adv, 0.0)
        runner_r = float(trade.runner_r)
        realized_exit_r = ((runner_r - 1.0 / 3.0) * 1.5
                           if bool(trade.runner_partial_taken) else runner_r)
        post_exit_best_from_entry = float(max(0.0, np.max(post_fav))) if len(post_fav) else 0.0
        post_exit_i = int(np.argmax(post_fav)) if len(post_fav) else -1
        runner_reason = str(trade.runner_reason)
        if runner_reason.startswith("STOP") and first_1r == "-1R_FIRST":
            path_class = "STOP_BEFORE_1R"
        elif runner_reason.startswith("STOP") and bool(trade.runner_partial_taken):
            path_class = "STOP_AFTER_1R_PARTIAL"
        elif runner_reason.startswith("STOP") and float(np.max(pre_fav)) >= 1.0:
            path_class = "STOP_AFTER_1R_NO_PARTIAL_AMBIGUOUS"
        elif runner_reason.startswith("STOP"):
            path_class = "STOP_BEFORE_1R_OR_AMBIGUOUS"
        elif runner_reason.startswith("TIME"):
            path_class = "TIME_EXIT"
        else:
            path_class = runner_reason
        outcome_class = "WIN" if runner_r > 1e-9 else "LOSS" if runner_r < -1e-9 else "BREAKEVEN"

        rows.append({
            "trade_key": trade.trade_key,
            "entry_time_utc": start.isoformat(),
            "window": trade.window,
            "side": "BUY" if int(trade.side) == 1 else "SELL",
            "entry": float(trade.entry),
            "initial_stop": float(trade.stop),
            "initial_risk_price": float(trade.risk),
            "h1_atr": float(trade.h1_atr),
            "risk_h1_atr": float(trade.risk_h1),
            "pullback_ratio": float(trade.pullback_ratio),
            "open_space_atr": float(trade.open_space_atr),
            "h1_atr_percentile_120": float(trade.h1_atr_percentile_120),
            "action": str(trade.action),
            "action_reason": str(trade.action_reason),
            "confidence_score": float(trade.confidence_score),
            "runner_r": runner_r,
            "outcome_class": outcome_class,
            "runner_exit_time_utc": exit_time.isoformat(),
            "runner_exit_reason": runner_reason,
            "runner_hold_minutes": float(trade.runner_holding_minutes),
            "runner_partial_taken": bool(trade.runner_partial_taken),
            "runner_graduated": bool(trade.runner_graduated),
            "runner_exit_price_r": realized_exit_r,
            "fast_r": float(trade.fast_r),
            "fast_exit_reason": str(trade.fast_reason),
            "fast_hold_minutes": float(trade.fast_holding_minutes),
            "mfe_before_exit_r_including_exit_bar": float(np.max(pre_fav)),
            "mfe_time_minutes": float((pre_times[mfe_i] - start).total_seconds() / 60.0),
            "mae_before_exit_r_including_exit_bar": float(np.min(pre_adv)),
            "mae_time_minutes": float((pre_times[mae_i] - start).total_seconds() / 60.0),
            "max_pullback_from_peak_r": float(np.max(pullback)),
            "first_1r_touch_order": first_1r,
            "first_1r_touch_minutes": first_1r_minutes,
            **milestones,
            "mfe_8h_r": float(np.max(favorable)),
            "mae_8h_r": float(np.min(adverse)),
            "post_exit_best_from_entry_r": post_exit_best_from_entry,
            "post_exit_favorable_from_exit_r": max(0.0, post_exit_best_from_entry - realized_exit_r),
            "post_exit_mfe_minutes": (
                float((post_times[post_exit_i] - exit_time).total_seconds() / 60.0)
                if post_exit_i >= 0 else np.nan
            ),
            "path_class": path_class,
        })
    return pd.DataFrame(rows)


def summarize(journal: pd.DataFrame) -> dict[str, object]:
    scored = journal.copy()
    scored["positive_r"] = scored["runner_r"] > 1e-9
    scored["executed"] = scored["action"].eq("RUNNER")

    def group(frame: pd.DataFrame, label: str) -> dict[str, object]:
        if frame.empty:
            return {"group": label, "n": 0}
        return {
            "group": label,
            "n": int(len(frame)),
            "wins": int(frame["positive_r"].sum()),
            "win_rate_pct": float(100 * frame["positive_r"].mean()),
            "runner_total_r": float(frame["runner_r"].sum()),
            "runner_mean_r": float(frame["runner_r"].mean()),
            "median_mfe_before_exit_r": float(frame["mfe_before_exit_r_including_exit_bar"].median()),
            "median_mae_before_exit_r": float(frame["mae_before_exit_r_including_exit_bar"].median()),
            "median_mfe_8h_r": float(frame["mfe_8h_r"].median()),
            "median_favorable_after_exit_r": float(frame["post_exit_favorable_from_exit_r"].median()),
            "after_exit_ge_1r_pct": float(100 * frame["post_exit_favorable_from_exit_r"].ge(1.0).mean()),
            "after_exit_ge_2r_pct": float(100 * frame["post_exit_favorable_from_exit_r"].ge(2.0).mean()),
            "after_exit_ge_3r_pct": float(100 * frame["post_exit_favorable_from_exit_r"].ge(3.0).mean()),
            "median_minutes_to_post_exit_mfe": float(frame["post_exit_mfe_minutes"].median()),
            "plus_1r_before_minus_1r_pct": float(100 * frame["first_1r_touch_order"].eq("+1R_FIRST").mean()),
            "stop_before_1r_pct": float(100 * frame["path_class"].eq("STOP_BEFORE_1R").mean()),
            "median_hold_minutes": float(frame["runner_hold_minutes"].median()),
            "median_h1_atr": float(frame["h1_atr"].median()),
            "median_pullback_ratio": float(frame["pullback_ratio"].median()),
            "median_open_space_atr": float(frame["open_space_atr"].median()),
        }

    summaries = [
        group(scored, "all opportunities"),
        group(scored.loc[scored.executed], "TR3 selected RUNNER"),
        group(scored.loc[~scored.executed], "TR3 skipped; counterfactual RUNNER"),
        group(scored.loc[scored.positive_r], "profitable counterfactual RUNNER"),
        group(scored.loc[~scored.positive_r], "non-profitable counterfactual RUNNER"),
    ]
    by_reason = [group(g, str(reason)) for reason, g in scored.groupby("runner_exit_reason", sort=True)]
    by_class = [group(g, str(path_class)) for path_class, g in scored.groupby("path_class", sort=True)]
    by_year_action = [
        group(g, f"{year} · {action}")
        for (year, action), g in scored.groupby([pd.to_datetime(scored.entry_time_utc, utc=True).dt.year, "action"], sort=True)
    ]
    return {
        "status": "DESCRIPTIVE_M1_PATH_JOURNAL_ONLY",
        "rows": len(journal),
        "entry_range_utc": [journal.entry_time_utc.min(), journal.entry_time_utc.max()],
        "exam_or_post_shadow_used": False,
        "path_definition": "Executable-side M1 OHLC: bid marks for BUY and spread-adjusted ask marks for SELL.",
        "caveat": "M1 does not reveal event order inside a candle; same-bar excursion and +1R/-1R ordering can be ambiguous. Descriptive findings do not establish causation.",
        "groups": summaries,
        "by_exit_reason": by_reason,
        "by_path_class": by_class,
        "by_year_action": by_year_action,
    }


def make_report(summary: dict[str, object]) -> str:
    g = {item["group"]: item for item in summary["groups"]}  # type: ignore[index]
    wins = g["profitable counterfactual RUNNER"]
    losses = g["non-profitable counterfactual RUNNER"]
    selected = g["TR3 selected RUNNER"]
    skipped = g["TR3 skipped; counterfactual RUNNER"]
    stop_before_1r = next(item for item in summary["by_path_class"] if item["group"] == "STOP_BEFORE_1R")
    return f"""# Trade journal: TREND-RUNNER M1 path analysis

**Scope:** {summary['rows']:,} scored entries, {summary['entry_range_utc'][0]} through {summary['entry_range_utc'][1]}. The locked exam and post-shadow data were excluded. This is a descriptive M1 OHLC reconstruction, not tick-level evidence.

## What distinguished profitable from non-profitable opportunities?

| Counterfactual RUNNER group | Trades | Win rate | Mean result | Median MFE before exit | Median MAE before exit | Median 8h MFE | Median favorable movement after exit |
|---|---:|---:|---:|---:|---:|---:|---:|
| Profitable | {wins['n']} | {wins['win_rate_pct']:.1f}% | {wins['runner_mean_r']:+.3f}R | {wins['median_mfe_before_exit_r']:.2f}R | {wins['median_mae_before_exit_r']:.2f}R | {wins['median_mfe_8h_r']:.2f}R | {wins['median_favorable_after_exit_r']:.2f}R |
| Non-profitable | {losses['n']} | {losses['win_rate_pct']:.1f}% | {losses['runner_mean_r']:+.3f}R | {losses['median_mfe_before_exit_r']:.2f}R | {losses['median_mae_before_exit_r']:.2f}R | {losses['median_mfe_8h_r']:.2f}R | {losses['median_favorable_after_exit_r']:.2f}R |

Here “before exit” includes the M1 exit candle, so its high/low ordering is not known. MFE/MAE are price excursions relative to the initial risk, not realized R. “Favorable movement after exit” is the best later executable-side mark minus the modeled exit price, normalized by initial risk and floored at zero; it is not a tradable counterfactual return.

## Concrete path findings

- Of the {losses['n']} non-profitable counterfactual RUNNER outcomes, {stop_before_1r['n']} ({100 * stop_before_1r['n'] / losses['n']:.1f}%) were stopped before a confirmed +1R touch. Their median favorable excursion before exit was only {stop_before_1r['median_mfe_before_exit_r']:.2f}R; median adverse excursion for all losses was {losses['median_mae_before_exit_r']:.2f}R. Median holding time was {losses['median_hold_minutes']:.0f} minutes.
- Profitable opportunities reached +1R before -1R on {wins['plus_1r_before_minus_1r_pct']:.1f}% of cases, versus {losses['plus_1r_before_minus_1r_pct']:.1f}% for non-profitable ones. Their median hold was {wins['median_hold_minutes']:.1f} minutes and median pre-exit MFE was {wins['median_mfe_before_exit_r']:.2f}R.
- After a non-profitable modeled exit, {losses['after_exit_ge_1r_pct']:.1f}% later moved at least 1R favorably from that exit price within the original 8-hour horizon; median favorable movement was {losses['median_favorable_after_exit_r']:.2f}R, with median time to that later best mark {losses['median_minutes_to_post_exit_mfe']:.0f} minutes. This suggests a testable timing/stop/continuation hypothesis, **not** proof that widening stops would help.
- Entry-context medians for profitable vs non-profitable cases were similar: H1 ATR {wins['median_h1_atr']:.2f} vs {losses['median_h1_atr']:.2f}; pullback ratio {wins['median_pullback_ratio']:.3f} vs {losses['median_pullback_ratio']:.3f}; open space {wins['median_open_space_atr']:.2f} vs {losses['median_open_space_atr']:.2f} ATR. These simple medians do not show a clean standalone entry filter.

## Did the selector help on these same opportunities?

- TR3 selected {selected['n']} trades, total {selected['runner_total_r']:+.2f}R, mean {selected['runner_mean_r']:+.3f}R, median pre-exit MFE {selected['median_mfe_before_exit_r']:.2f}R, median pre-exit MAE {selected['median_mae_before_exit_r']:.2f}R.
- TR3 skipped {skipped['n']} opportunities; if they had instead used the same RUNNER exit, their counterfactual result was {skipped['runner_total_r']:+.2f}R total and {skipped['runner_mean_r']:+.3f}R per opportunity. This comparison is descriptive and does not change the frozen selector.

## Exit and path breakdowns

The same summary JSON also breaks trades down by exit reason, path class and year/action. The per-trade file records exact entry/exit timestamps, reason, holding time, time-to-1R/2R/3R, MFE/MAE, pullback from peak, entry ATR/pullback/open-space context, and movement remaining after exit. This makes individual cases traceable without claiming a causal label from OHLC alone.

## Interpretation boundary

The journal can answer “what price path preceded or followed this simulated result?” It cannot by itself prove “why the market moved,” and M1 candles cannot resolve within-minute order. The strong after-stop movement is the next research lead: test delayed confirmation/re-entry or structural stop alternatives only in a separately frozen study, never by silently changing the current result. The setup/selector were chosen after later development data had been seen; use these findings to nominate hypotheses only, then freeze any candidate rule before a separate untouched forward test. No entry/exit rule, risk parameter or live path was changed.
"""


def main() -> None:
    predictions = pd.read_parquet(PREDICTIONS_PATH)
    predictions["entry_time"] = pd.to_datetime(predictions["entry_time"], utc=True)
    predictions["runner_exit_time"] = pd.to_datetime(predictions["runner_exit_time"], utc=True)
    if len(predictions) != 1231 or predictions["trade_key"].duplicated().any():
        raise AssertionError("Unexpected scored journal population.")
    bars = read_bars()
    journal = build_journal(bars, predictions)
    if len(journal) != len(predictions):
        raise AssertionError("The trade journal lost or duplicated scored entries.")
    summary = summarize(journal)
    journal.to_csv(ROOT / "trade_journal.csv", index=False, float_format="%.6f")
    (ROOT / "trade_journal_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (ROOT / "JOURNAL.md").write_text(make_report(summary), encoding="utf-8")
    print(f"journal rows: {len(journal):,}; no exam/post-shadow bars loaded")
    print(json.dumps(summary["groups"], indent=2))


if __name__ == "__main__":
    main()
