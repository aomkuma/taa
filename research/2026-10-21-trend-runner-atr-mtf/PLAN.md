# TREND-RUNNER MTF ATR pause-filter research

Status: exploratory, isolated research only. This package does not modify TR1/TR2/TR3, the locked exam, or any order path.

## Question

Does a multi-timeframe volatility pause gate improve the frozen TR3 primary on the same 210 scored opportunities?

## Data boundary and baseline

- Input outcomes: TR3 `predictions_primary.parquet` only (210 scored design opportunities; no historical exam rows).
- Underlying bars: XAUUSD M1 rows from 2025-10-18 through, but excluding, 2026-04-18 UTC.
- TR3 primary baseline: 83 RUNNER actions, all other actions remain SKIP.
- Paired control: always-RUNNER on the same 210 opportunities.
- Slippage remains excluded as directed. Returns are reported in R; optional constant-$10-risk conversion is exactly 10 × R.
- This is seen development evidence, not an independent test.

## Causal volatility features

- Build completed UTC M15, M30 and H1 bars from the allowed M1 source.
- Compute simple ATR(14), using the project's MT5-compatible true-range definition.
- At each opportunity, only use the latest bar with `available_at <= entry_time`.
- For each timeframe, calculate the current ATR's percentile against the preceding 120-H1-bar-equivalent count of completed ATR observations, excluding the current observation. This uses 480 prior M15, 240 prior M30 or 120 prior H1 ATR values. Missing/non-trading bars are not fabricated.
- Composite volatility score = median of the three timeframe percentiles. This requires at least two timeframes to indicate a high-volatility regime and avoids comparing raw ATR magnitudes across different bar sizes.

## Frozen stateful pause rule

At each scored opportunity in chronological order:

1. If active and composite percentile is strictly above the upper threshold, pause before deciding the current action.
2. If paused and composite percentile is at or below the lower threshold, resume before deciding the current action.
3. While paused, suppress RUNNER actions; SKIP remains SKIP.
4. Report three predeclared hysteresis pairs: primary 80/70, sensitivities 75/65 and 85/75 (upper/lower percentile).

The same gate and thresholds apply to TR3 primary and always-RUNNER controls. No threshold may replace the primary after results are inspected.

## Metrics

For baseline and each gate: executed trades, total R, mean R/trade, win rate, max drawdown R, losing streak, trades blocked, pause/resume transitions and total R after removing the best trade. Show ATR percentile and raw ATR distributions by winning/non-positive outcome as context.

## Interpretation boundary

Any apparent improvement is exploratory because thresholds and analysis are evaluated on previously seen development data. The rule is not validated and must not be integrated/promoted based on this report. No live/demo/order action is in scope.
