# TR4 MTF ATR pause-gate forward research

Status: **SPECIFIED, NOT BACKTESTED OR VALIDATED**. This is an isolated research variant; it does not edit TR1, TR2, TR3, the existing shadow journal, or any order path.

## Purpose

Evaluate whether a frozen multi-timeframe ATR pause gate adds value to the frozen TR3 RUNNER/SKIP decisions on genuinely new forward observations. The exploratory 2026-10-21 backtest used seen development data and is not independent evidence.

## Frozen candidate rule

- Parent actions and RUNNER outcomes are the frozen TR3 Champion outputs, unchanged.
- Build completed UTC M15, M30 and H1 bars from causal M1 data; calculate the project's MT5-compatible simple ATR(14).
- At each opportunity decision time, attach the latest completed bar per timeframe with `available_at <= decision_time`.
- For each timeframe, rank current ATR against the prior 120 H1-bar-equivalent ATR observations (480 M15, 240 M30, 120 H1), excluding the current observation. Do not fabricate missing bars.
- Composite volatility = median of the three causal ATR percentiles. Values are fractions in [0, 1].
- Start unpaused. Pause before the current opportunity when the composite is strictly above 0.80. While paused, resume before the current opportunity when composite is at or below 0.70. Suppress only parent `RUNNER` actions while paused; retain parent `SKIP` actions.
- No threshold tuning, absolute ATR band, side filter, sizing change, exit change, or slippage adjustment is in this round. Slippage is excluded as directed.

## Evaluation boundary

- No historical exam or previously seen P1/P2/TR3/ATR outcomes may be used as TR4 validation.
- Forward collection boundary: 2026-10-21 00:00 UTC. Use the isolated TR3 shadow journal as the frozen parent-event source, read-only; TR4 has no broker/order capability.
- Do not score a parent TR3 action until the frozen TR3 cold-start contract permits it. Keep TR4's gate state and decisions in a separate append-only artifact.
- Formal comparison requires at least 100 new scored opportunities and 60 new scored trading days, after valid cold start. Compare TR4 to TR3 on the identical opportunities and RUNNER outcome labels.
- Report trade count, total/mean R, constant-$10-risk cash (`10 * R`), win rate, max drawdown, losing streak, best-one/best-three removal, pause transitions, and month/session/direction concentration. Include uncertainty and data-boundary/causality audits.
- Evaluate once. Any rule change creates a new named round and starts a new forward collection window.

## Decision rule

TR4 remains observational and research-only regardless of interim results. A positive sample is not proof of future profitability. No integration decision before the complete frozen sample and audit; a passing review only permits a separate integration review.
