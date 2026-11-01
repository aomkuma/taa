# Stable-POC cluster with expanded FBS coverage

**Date:** 2026-11-01 (Asia/Bangkok)  
**Question:** Does requiring a stationary POC make VAL/VAH rotation more robust when the session-coverage gate is widened?

## Frozen rule

Replayed the existing stable-POC limit strategy on the expanded 264-session FBS sample. It requires an overlapping six-hour value area, POC displacement between the older and newer three-hour profiles no more than $0.50, six-hour price path efficiency no more than 0.25, and price inside value before order activation. The first qualifying daily cluster is frozen. Buy limit at VAL / sell limit at VAH; first touch only. Target is POC; stop is beyond the full six-hour profile extreme with the existing spread pad. Two consecutive M5 closes beyond value invalidate an unfilled order. Execution uses FBS bid/ask ticks.

## Results

| Period | Trades | Win rate | Net R | PF (R) | Targets / stops |
|---|---:|---:|---:|---:|---:|
| Development (184 sessions) | 50 | 10.0% | -24.35R | 0.45 | 4 / 45 |
| Validation (80 sessions) | 32 | 12.5% | +1.50R | 1.05 | 4 / 28 |

Development folds returned -9.74R, -3.20R, and -11.41R. Validation's small positive result was accompanied by a negative -$0.51/oz aggregate price PnL and a point-based profit factor below 1. Most trades stopped; the R result depends on sizing each setup by its different planned stop distance.

## Decision and limitations

**Do not select this as a candidate.** The rule fails every development fold and the validation gain is marginal, with only four targets among 32 trades. This fits a regime-specific or fragile outcome better than a stable edge. The earlier 158-session study also had negative development despite positive late validation; widening coverage does not resolve that inconsistency.

The input remains FBS-Demo M1 tick volume allocated over candle ranges plus FBS bid/ask quote execution, not the screenshot's OANDA data or centralized gold trade volume. Commissions and extra slippage are omitted, and the validation segment has been reused in prior exploration.

## Reproduction

Run `python test_oco_limit_expanded.py` from this folder's parent. Outputs are in `expanded_coverage/`.
