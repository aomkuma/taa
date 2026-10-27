"""Three-year M1-only chronological replay of frozen TR1 + TR3 (research only)."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TR1 = REPO / "research/2026-10-20-trend-runner"
R2 = REPO / "research/2026-10-20-trend-runner-r2"
R3 = REPO / "research/2026-10-20-trend-runner-r3"
for source in (TR1, R2, R3):
    sys.path.insert(0, str(source))

from tr1.bars import aggregate, atr, confirmed_fractals, minute_bars  # noqa: E402
from tr1.opportunity import find_first_pullback, find_impulse, initial_stop  # noqa: E402
from tr1.structure import structure_events  # noqa: E402
from tr1.windows import Window, anchor  # noqa: E402
from r2.features import build_feature_panel  # noqa: E402
from r3.data import FEATURE_COLUMNS  # noqa: E402
from r3.model import monthly_walk_forward  # noqa: E402

BAR_PATH = REPO / "data/history/FBS-Demo/XAUUSD/M1.parquet"
SPEC_PATH = REPO / "data/history/FBS-Demo/XAUUSD/spec.json"
REQUESTED_START = pd.Timestamp("2023-10-21", tz="UTC")
WARMUP_START = pd.Timestamp("2023-09-01", tz="UTC")
EXAM_START = pd.Timestamp("2026-04-18", tz="UTC")
EXAM_END = pd.Timestamp("2026-10-18", tz="UTC")
SHADOW_START = pd.Timestamp("2026-10-21", tz="UTC")
DATA_END = EXAM_START
THRESHOLD = 0.25
DEADLINES = {"ASIA": 120, "LONDON": 120, "NY0830": 240}
WINDOWS = (Window.ASIA, Window.LONDON, Window.NY0830)
POINT = 0.01
RETIRED = (
    "Retired 2026-10-22 (retest-continuation/DEBUG_2026-10-22.md, bugs B5/B6): this replay fills "
    "TR1 entries at the M1 open + the M1 spread column and runs the exits on M1 OHLC, while the "
    "frozen TR1 rule fills on the first raw quote and exits on ordered bid/ask ticks. Use TR1's "
    "tick path (frozen_round.generate_entries/generate_exits or the retest-continuation "
    "pipeline.py) one week at a time. The original is kept in _original_2026-10-22/."
)


@dataclass(frozen=True)
class BarExit:
    family: str
    complete: bool
    exit_time: pd.Timestamp | None
    exit_price: float
    reason: str
    r: float
    holding_minutes: float
    partial_taken: bool
    graduated: bool


def read_m1() -> pd.DataFrame:
    frame = pd.read_parquet(
        BAR_PATH,
        columns=["open_time", "close_time", "open", "high", "low", "close", "spread", "tick_volume"],
        filters=[("open_time", ">=", WARMUP_START.to_pydatetime()), ("open_time", "<", DATA_END.to_pydatetime())],
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    frame["close_time"] = pd.to_datetime(frame["close_time"], utc=True)
    frame = frame.sort_values("open_time").reset_index(drop=True)
    if frame["open_time"].duplicated().any() or not frame["open_time"].is_monotonic_increasing:
        raise AssertionError("M1 open times must be unique and increasing.")
    if (frame["open_time"] >= EXAM_START).any() or (frame["close_time"] > EXAM_START).any():
        raise AssertionError("Locked historical exam data crossed the loader boundary.")
    if (frame["open_time"] >= SHADOW_START).any():
        raise AssertionError("Forward shadow data crossed into this historical replay.")
    return frame.set_index("open_time", drop=True)


def atr_values(frame: pd.DataFrame) -> np.ndarray:
    return atr(frame["high"].to_numpy(float), frame["low"].to_numpy(float), frame["close"].to_numpy(float), 14)


def h1_at(h1: pd.DataFrame, values: np.ndarray, moment: pd.Timestamp) -> float:
    i = int(pd.DatetimeIndex(h1["avail"]).searchsorted(moment, side="right")) - 1
    return float(values[i]) if i >= 0 else np.nan


def m1_fill(m1: pd.DataFrame, active_at: pd.Timestamp, side: int) -> tuple[pd.Timestamp, float, float] | None:
    """Approximate first post-signal quote with next available M1 open and recorded spread."""
    raise RuntimeError(RETIRED)
    i = int(m1.index.searchsorted(active_at, side="left"))
    if i >= len(m1) or m1.index[i] > active_at + pd.Timedelta(minutes=5):
        return None
    row = m1.iloc[i]
    spread = float(row["spread"]) * POINT
    # MT5 chart mode is BID: buy at ask, sell at bid.
    price = float(row["open"]) + (spread if side == 1 else 0.0)
    return pd.Timestamp(m1.index[i]), price, spread


def generate_entries(m1: pd.DataFrame) -> pd.DataFrame:
    m1bars = minute_bars(m1)
    m1atr = atr_values(m1bars)
    m1pivots = confirmed_fractals(m1bars, radius=1)
    h1 = aggregate(m1, "1h")
    h1atr = atr_values(h1)
    start_day = WARMUP_START.tz_convert("Asia/Bangkok").tz_localize(None).normalize()
    final_day = (DATA_END - pd.Timedelta(days=1)).tz_convert("Asia/Bangkok").tz_localize(None).normalize()
    rows: list[dict[str, object]] = []
    for day in pd.date_range(start_day, final_day, freq="D"):
        if day.dayofweek >= 5:
            continue
        for window in WINDOWS:
            at = anchor(day, window)
            if not (m1.index.min() <= at < DATA_END):
                continue
            h = h1_at(h1, h1atr, at)
            impulse = find_impulse(m1, at, h, THRESHOLD)
            if impulse is None:
                continue
            deadline = at + pd.Timedelta(minutes=DEADLINES[window.value])
            lo = int(pd.DatetimeIndex(m1pivots["avail"]).searchsorted(impulse.decision, side="left"))
            hi = int(pd.DatetimeIndex(m1pivots["avail"]).searchsorted(deadline, side="right"))
            local_pivots = m1pivots.iloc[lo:hi]
            candidate, _ = find_first_pullback(
                m1bars,
                impulse,
                window=window.value,
                timeframe="M1",
                deadline_minutes=DEADLINES[window.value],
                entry_atr_values=m1atr,
                pivots=local_pivots,
            )
            if candidate is None:
                continue
            fill = m1_fill(m1, candidate.decision_time, impulse.side)
            if fill is None:
                continue
            entry_time, entry_price, spread = fill
            # Entire maximum runner horizon must end before the locked exam begins.
            if entry_time < WARMUP_START or entry_time + pd.Timedelta(hours=8) >= EXAM_START:
                continue
            class FillProxy:
                price = entry_price
            stop, risk = initial_stop(candidate, FillProxy(), spread)
            risk_h = risk / impulse.h1_atr
            if not (0.05 <= risk_h <= 0.50):
                continue
            rows.append({
                "window": window.value,
                "anchor": at,
                "reference": impulse.reference,
                "h1_atr": impulse.h1_atr,
                "side": impulse.side,
                "impulse_decision": impulse.decision,
                "pivot_time": candidate.pivot_time,
                "pivot_price": candidate.pivot_price,
                "pivot_available": candidate.pivot_available,
                "pullback_ratio": candidate.pullback_ratio,
                "decision_time": candidate.decision_time,
                "entry_atr": candidate.entry_atr,
                "entry_time": entry_time,
                "entry": entry_price,
                "spread": spread,
                "stop": stop,
                "risk": risk,
                "risk_h1": risk_h,
            })
    entries = pd.DataFrame(rows).sort_values("entry_time").reset_index(drop=True)
    if entries.empty:
        raise RuntimeError("No M1 opportunities generated; do not continue to model fitting.")
    entries.insert(0, "entry_id", np.arange(len(entries), dtype=int))
    entries.insert(0, "trade_key", [f"M1WF-{i:05d}" for i in range(len(entries))])
    return entries


def directional_ohlc(row: pd.Series, side: int) -> tuple[float, float, float, float]:
    """Return executable-side OHLC marks: bid for BUY; ask proxy for SELL."""
    offset = float(row["spread"]) * POINT if side == -1 else 0.0
    return tuple(float(row[name]) + offset for name in ("open", "high", "low", "close"))


def simulate_m1_exit(
    m1: pd.DataFrame,
    entry: pd.Series,
    family: str,
    events: list,
) -> BarExit:
    """Conservative M1 OHLC replay. A same-bar adverse stop beats favorable milestones."""
    raise RuntimeError(RETIRED)
    side = int(entry["side"])
    price = float(entry["entry"])
    initial_stop = float(entry["stop"])
    risk = float(entry["risk"])
    start = pd.Timestamp(entry["entry_time"])
    if risk <= 0:
        raise AssertionError("Non-positive initial risk.")
    is_runner = family == "SPLIT"
    stop = initial_stop
    partial = False
    graduated = False
    graduation_time: pd.Timestamp | None = None
    event_index = 0
    deadline = start + (pd.Timedelta(hours=8) if is_runner else pd.Timedelta(minutes=60))
    target1 = price + side * risk
    target2 = price + side * 2.0 * risk
    target3 = price + side * 3.0 * risk
    lo = int(m1.index.searchsorted(start, side="left"))
    hi = int(m1.index.searchsorted(start + pd.Timedelta(days=3), side="left"))
    path = m1.iloc[lo:hi]

    def tighter(current: float, candidate: float) -> float:
        return max(current, candidate) if side == 1 else min(current, candidate)

    def event_applies(event) -> bool:
        if not is_runner:
            return False
        event_time = pd.Timestamp(event.avail)
        if event_time > start + pd.Timedelta(hours=8):
            return False
        if not graduated:
            return event.timeframe == "M5"
        return event.timeframe == "M15" and graduation_time is not None and event_time >= graduation_time

    def finish(when: pd.Timestamp, exit_price: float, reason: str) -> BarExit:
        raw_r = (exit_price - price) * side / risk
        value = (1.0 / 3.0 + (2.0 / 3.0) * raw_r) if is_runner and partial else raw_r
        return BarExit(family, True, when, float(exit_price), reason, float(value),
                       (when - start).total_seconds() / 60.0, partial, graduated)

    for open_time, bar in path.iterrows():
        open_time = pd.Timestamp(open_time)
        close_time = open_time + pd.Timedelta(minutes=1)
        # Apply structure confirmations that occurred during a data gap before the next quote.
        while event_index < len(events) and pd.Timestamp(events[event_index].avail) < open_time:
            event = events[event_index]
            event_index += 1
            if event_applies(event):
                stop = tighter(stop, float(event.stop))

        o, h, l, c = directional_ohlc(bar, side)
        if (o <= stop if side == 1 else o >= stop):
            return finish(open_time, o, "STOP_GAP")
        if open_time >= deadline:
            return finish(open_time, o, "TIME_OPEN")

        adverse = l if side == 1 else h
        favorable = h if side == 1 else l
        if (adverse <= stop if side == 1 else adverse >= stop):
            # The exact touch is used for an intrabar stop; an opening gap used the worse open above.
            return finish(close_time, stop, "STOP_INTRABAR")

        if family == "FAST":
            hit = favorable >= target2 if side == 1 else favorable <= target2
            if hit:
                return finish(close_time, target2, "TARGET_2R")
        else:
            hit1 = favorable >= target1 if side == 1 else favorable <= target1
            if hit1:
                partial = True
            hit3 = favorable >= target3 if side == 1 else favorable <= target3
            if hit3 and not graduated:
                graduated = True
                # OHLC cannot time the first 3R touch; use the candle close so the M15
                # graduation trail cannot be activated earlier than information allows.
                graduation_time = close_time

        # Confirmations at a clock close take effect after that candle's price action.
        while event_index < len(events) and pd.Timestamp(events[event_index].avail) <= close_time:
            event = events[event_index]
            event_index += 1
            if event_applies(event):
                stop = tighter(stop, float(event.stop))
        if (c <= stop if side == 1 else c >= stop):
            return finish(close_time, c, "STOP_AT_CLOSE")
        if close_time >= deadline:
            return finish(close_time, c, "TIME_CLOSE")

    return BarExit(family, False, None, np.nan, "CENSORED", np.nan, np.nan, partial, graduated)


def add_outcomes(m1: pd.DataFrame, entries: pd.DataFrame) -> pd.DataFrame:
    m5, m15 = aggregate(m1, "5min"), aggregate(m1, "15min")
    m5atr, m15atr = atr_values(m5), atr_values(m15)
    m5pivots, m15pivots = confirmed_fractals(m5, radius=1), confirmed_fractals(m15, radius=1)
    records: list[dict[str, object]] = []
    for _, row in entries.iterrows():
        start = pd.Timestamp(row["entry_time"])
        end = start + pd.Timedelta(hours=8)
        m5lo = int(pd.DatetimeIndex(m5pivots["avail"]).searchsorted(start, side="left"))
        m5hi = int(pd.DatetimeIndex(m5pivots["avail"]).searchsorted(end, side="right"))
        m15lo = int(pd.DatetimeIndex(m15pivots["avail"]).searchsorted(start, side="left"))
        m15hi = int(pd.DatetimeIndex(m15pivots["avail"]).searchsorted(end, side="right"))
        local_m5pivots = m5pivots.iloc[m5lo:m5hi]
        local_m15pivots = m15pivots.iloc[m15lo:m15hi]
        events = structure_events(m5, local_m5pivots, m5atr, timeframe="M5", side=int(row["side"]),
                                  entry_time=start, entry_spread=float(row["spread"]), end_time=end)
        events.extend(structure_events(m15, local_m15pivots, m15atr, timeframe="M15", side=int(row["side"]),
                                       entry_time=start, entry_spread=float(row["spread"]), end_time=end))
        events.sort(key=lambda event: (event.avail, event.timeframe, event.pivot_time))
        fast = simulate_m1_exit(m1, row, "FAST", events)
        runner = simulate_m1_exit(m1, row, "SPLIT", events)
        if not fast.complete or not runner.complete:
            records.append({"trade_key": row["trade_key"], "complete": False})
            continue
        records.append({
            "trade_key": row["trade_key"],
            "complete": True,
            "fast_r": fast.r,
            "runner_r": runner.r,
            "fast_usd": fast.r * float(row["risk"]),
            "runner_usd": runner.r * float(row["risk"]),
            "fast_exit_time": fast.exit_time,
            "runner_exit_time": runner.exit_time,
            "outcome_available": max(fast.exit_time, runner.exit_time),
            "fast_reason": fast.reason,
            "runner_reason": runner.reason,
            "fast_holding_minutes": fast.holding_minutes,
            "runner_holding_minutes": runner.holding_minutes,
            "runner_partial_taken": runner.partial_taken,
            "runner_graduated": runner.graduated,
        })
    result = entries.merge(pd.DataFrame(records), on="trade_key", how="left", validate="one_to_one")
    return result.reset_index(drop=True)


def max_drawdown(values: np.ndarray) -> float:
    equity = np.r_[0.0, np.cumsum(values)]
    return float(np.max(np.maximum.accumulate(equity) - equity))


def bootstrap_interval(values: np.ndarray, seed: int = 20261021) -> list[float]:
    if not len(values):
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(10_000, len(values)), replace=True).mean(axis=1)
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def metrics(values: pd.Series, scored: int) -> dict[str, object]:
    x = values.to_numpy(float)
    return {
        "n": int(len(x)), "scored": int(scored), "total_r": float(x.sum()),
        "mean_r": float(x.mean()) if len(x) else np.nan,
        "median_r": float(np.median(x)) if len(x) else np.nan,
        "win_rate": float(np.mean(x > 0)) if len(x) else np.nan,
        "max_drawdown_r": max_drawdown(x), "bootstrap_95_mean_r_iid": bootstrap_interval(x),
        "without_best_one_r": float(np.sort(x)[::-1][1:].sum()) if len(x) > 1 else 0.0,
        "without_best_three_r": float(np.sort(x)[::-1][3:].sum()) if len(x) > 3 else 0.0,
        "worst_r": float(x.min()) if len(x) else np.nan,
    }


def main() -> None:
    raise SystemExit(RETIRED)
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))["spec"]
    if int(spec["digits"]) != 2 or float(spec["point"]) != POINT:
        raise AssertionError("Unexpected XAUUSD point specification.")
    m1 = read_m1()
    print(f"loaded M1 bars: {len(m1):,}; {m1.index.min()} through {m1.index.max()}", flush=True)
    entries = generate_entries(m1)
    print(f"generated frozen-rule entries (including warm-up): {len(entries):,}", flush=True)
    entries.to_parquet(ROOT / "entries_stage.parquet", index=False)
    all_outcomes = add_outcomes(m1, entries)
    print(f"simulated outcomes: {len(all_outcomes):,}", flush=True)
    all_outcomes.to_parquet(ROOT / "outcomes_stage.parquet", index=False)
    censored_count = int((~all_outcomes["complete"].eq(True)).sum())
    outcomes = all_outcomes.loc[
        all_outcomes["complete"].eq(True) & (all_outcomes["outcome_available"] < EXAM_START)
    ].reset_index(drop=True)
    if outcomes.empty:
        raise RuntimeError("No complete pre-exam outcomes; stop before feature/model work.")
    feature_panel = build_feature_panel(outcomes, m1.reset_index(), cutoff=EXAM_START)
    print(f"built causal feature panel: {len(feature_panel):,}", flush=True)
    if len(feature_panel) != len(outcomes) or feature_panel["trade_key"].duplicated().any():
        raise AssertionError("Feature generation dropped or duplicated an entry.")
    if (feature_panel[FEATURE_COLUMNS].isna().all(axis=1)).any():
        raise AssertionError("A row has no usable model features.")
    predictions, coefficients = monthly_walk_forward(feature_panel)
    if predictions.empty:
        raise RuntimeError("The frozen 60/90/120-day model never warmed up; no result to report.")
    predictions = predictions.loc[predictions["entry_time"] >= REQUESTED_START].copy()
    if predictions.empty:
        raise RuntimeError("No scored rows in the requested three-year evaluation interval.")
    predictions = predictions.sort_values(["entry_time", "trade_key"]).reset_index(drop=True)
    print(f"scored post-warm-up rows: {len(predictions):,}", flush=True)
    predictions["year"] = predictions["entry_time"].dt.year
    predictions["quarter"] = predictions["entry_time"].dt.to_period("Q").astype(str)
    executed = predictions.loc[predictions["action"] == "RUNNER"]
    baseline = predictions["runner_r"]
    selected = predictions["selected_r"]
    result = {
        "status": "HISTORICAL_M1_WALK_FORWARD_RESEARCH_ONLY",
        "exam_used": False,
        "requested_start": REQUESTED_START.isoformat(),
        "warmup_start": WARMUP_START.isoformat(),
        "last_allowed_outcome_before": EXAM_START.isoformat(),
        "locked_exam_excluded": [EXAM_START.isoformat(), EXAM_END.isoformat()],
        "forward_shadow_excluded_from": SHADOW_START.isoformat(),
        "m1_first": m1.index.min().isoformat(), "m1_last_before_exam": m1.index.max().isoformat(),
        "warmup_and_eval_entry_count": int(len(outcomes)),
        "evaluation_entry_count": int((outcomes["entry_time"] >= REQUESTED_START).sum()),
        "censored_entry_count": censored_count,
        "scored_count": int(len(predictions)),
        "scored_first": predictions["entry_time"].min().isoformat(),
        "scored_last": predictions["entry_time"].max().isoformat(),
        "refit_months": sorted(predictions["refit_month"].unique().tolist()),
        "action_counts": {str(k): int(v) for k, v in predictions["action"].value_counts().items()},
        "always_runner": metrics(baseline, len(predictions)),
        "tr3_selected": metrics(selected, len(predictions)),
        "runner_selected_only": metrics(executed["runner_r"], len(predictions)),
        "m1_approximation": True,
        "execution_cost": "recorded M1 spread; zero slippage",
        "iid_bootstrap_warning": "Trade-level IID interval ignores temporal clustering; diagnostic only.",
        "limitations": [
            "M1 OHLC cannot reconstruct tick ordering or exact executable stop/target fills.",
            "Same-bar stop-vs-favorable ambiguity is resolved against the trade.",
            "The frozen TR3 model form was selected after later development data were seen; this is not independent validation.",
        ],
    }
    entries.to_parquet(ROOT / "entries_m1_approx.parquet", index=False)
    outcomes.to_parquet(ROOT / "outcomes_m1_approx.parquet", index=False)
    feature_panel.to_parquet(ROOT / "feature_panel_m1_approx.parquet", index=False)
    predictions.to_parquet(ROOT / "predictions_walkforward.parquet", index=False)
    coefficients.to_csv(ROOT / "coefficients.csv", index=False)
    predictions.groupby(["year", "action"], observed=True).agg(
        opportunities=("trade_key", "size"), selected_r=("selected_r", "sum"),
        always_runner_r=("runner_r", "sum"), mean_selected_r=("selected_r", "mean"),
    ).reset_index().to_csv(ROOT / "year_action.csv", index=False, float_format="%.6f")
    predictions.groupby(["quarter", "action"], observed=True).agg(
        opportunities=("trade_key", "size"), selected_r=("selected_r", "sum"),
        always_runner_r=("runner_r", "sum"), mean_selected_r=("selected_r", "mean"),
    ).reset_index().to_csv(ROOT / "quarter_action.csv", index=False, float_format="%.6f")
    predictions.to_csv(ROOT / "predictions_walkforward.csv", index=False, float_format="%.8f")
    (ROOT / "RESULTS.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
