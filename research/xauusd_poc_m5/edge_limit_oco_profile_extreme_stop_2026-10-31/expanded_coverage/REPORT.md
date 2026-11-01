# Expanded-coverage VAL/VAH limit test

**Date:** 2026-11-01 (Asia/Bangkok)  
**Question:** Does the familiar buy-at-lower-value / sell-at-upper-value rotation perform differently when the broader FBS session coverage is used?

## Frozen rule

Replayed the existing six-hour profile OCO setup without changing its entry, target, or stop logic. The profile uses $0.10 rows and FBS M1 tick volume allocated across candle ranges. A balance cluster requires at least 50% overlap between the older and newer three-hour 70% value areas. Once a cluster is active, place a buy limit at VAL and a sell limit at VAH; the first touched side is the only trade for that session. Target is the cluster POC. The stop is beyond the full six-hour profile low/high, padded by at least $0.10 or twice the observed six-hour median spread plus $0.10. Invalidate the order after two M5 closes beyond value; order lifetime is capped at 72 M5 bars. Fills and exits use FBS bid/ask quote ticks.

The sample contains 264 sessions with at least 247 of the expected 274 M5 bars, split chronologically into 184 development and 80 validation sessions. This removes the old previous-session coverage dependency. The four trades closed at session end used quotes less than one second before the segment close.

## Results

| Period | Trades | Win rate | Net R | PF (R) | Targets / stops |
|---|---:|---:|---:|---:|---:|
| Development | 182 | 41.2% | -7.04R | 0.91 | 75 / 107 |
| Validation | 80 | 37.5% | -12.01R | 0.69 | 30 / 50 |

Development folds: -10.62R, -1.06R, +4.64R. Only the last fold was profitable. Across both periods there were 262 trades; two selected sessions formed clusters but did not produce a valid fill.

## Decision and limitations

**Reject this rule.** Widening the sample did not rescue rotation into the POC: both development and validation were negative, with validation materially worse. This weakens the simple interpretation that buying the lower edge and selling the upper edge is sufficient. It does not prove that all POC methods fail, or that this FBS proxy matches the user's TradingView OANDA profile.

FBS M1 tick volume with uniform OHLC-range allocation is a broker-specific approximation, not centralized XAUUSD traded volume or the exact OANDA indicator feed. FBS bid/ask ticks drive fills, but commissions and additional slippage are omitted. The validation period has also been reused in related research and is not a pristine holdout.

## Reproduction

Run `python test_oco_limit_expanded.py` from this folder's parent. Outputs are saved in `expanded_coverage/`.
