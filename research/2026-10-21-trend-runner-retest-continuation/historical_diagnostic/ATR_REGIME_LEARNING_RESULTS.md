# Per-trade ATR-regime learning — historical replay

**Decision: exploratory only; no strategy change.** This replay uses the 632 pre-exam source events and the frozen RETEST-CONTINUATION V1 outcomes. It reads completed M15/M30/H1 bars only as available at the original stop time; the composite is the median percentile. High-volatility state is strictly above the previously researched 80th percentile; otherwise state is normal/low.

For every source event, the policy looks back 52 weeks within the same ATR state at previously allowed, completed candidate attempts whose outcome exit precedes the current event. It needs five prior outcomes; before that it allows the frozen candidate. Once warm, it allows a state only if trailing mean R is positive. Blocked outcomes are journaled but never used to train later decisions.

## Result

| Policy | Completed attempts | Total R | Mean R | Median R | Win rate |
|---|---:|---:|---:|---:|---:|
| Frozen V1 | 108 | +28.25 | +0.262 | -0.377 | 38.9% |
| ATR-state adaptive | 64 | +25.02 | +0.391 | -0.446 | 40.6% |
| Blocked counterfactual | 44 | +3.23 | +0.073 | -0.274 | 36.4% |
| Source-stop ATR-state screen (>80th pct; not entry-time gate) | 93 | +30.96 | +0.333 | -0.348 | 39.8% |
| High-ATR blocked counterfactual | 15 | -2.72 | -0.181 | -0.588 | 33.3% |

The adaptive policy allowed 379/632 source events and selected 64/108 completed attempts; 44 blocked completed attempts sum to +3.23R. It started in warm-up for 91 events.

## Frozen candidate outcomes by ATR state

| ATR state at source-stop time | Events | Completed attempts | Total R | Mean R |
|---|---:|---:|---:|---:|
| HIGH | 65 | 15 | -2.72 | -0.181 |
| NORMAL_OR_LOW | 567 | 93 | +30.96 | +0.333 |

## Interpretation

The direct fixed-gate row in this diagnostic applies ATR state at the original source-stop time, not the later re-entry entry time; it is not an evaluation of an entry lock. A separate earlier-period holdout tests the fixed gate at actual re-entry time. The trailing-mean policy remains an in-sample research experiment. Do not promote either rule from this development replay.

Limitations: pre-exam data only; M1 OHLC event replay; recorded spread included; slippage excluded; overlapping event paths are not portfolio equity. Locked exam [2026-04-18, 2026-10-18) excluded.
