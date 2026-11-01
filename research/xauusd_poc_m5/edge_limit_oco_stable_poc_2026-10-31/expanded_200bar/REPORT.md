# Stable-POC edge rotation with a true 200-bar M5 profile

**Date:** 2026-11-01 (Asia/Bangkok)  
**Question:** Does extending the profile from six hours to the last 200 completed M5 bars improve the balance-cluster rotation setup?

## Method

At each M5 bar, built the profile from the previous 200 completed M5 bars, splitting it into older and newer 100-bar halves. M1 FBS `tick_volume` was distributed over each M1 candle's $0.10 price rows in proportion to the candle's OHLC range. This uses actual bar counts, so weekend and market-closure gaps do not shorten the profile.

A cluster required at least 50% overlap between the two halves' 70% value areas, POC displacement no more than $0.50, six-hour path efficiency no more than 0.25, and the previous M5 close inside the full profile value area. The first qualifying profile was frozen. A buy limit at VAL and sell limit at VAH were active while price remained in value, with only the first touch traded. Stop was just outside the frozen VAL/VAH by the existing spread pad; target was the frozen POC. Two consecutive M5 closes beyond value invalidated an unfilled setup; order life was capped at 72 M5 bars. Bid/ask ticks determined touch fills and exits.

The same expanded coverage was used: 264 sessions with at least 247 of the expected 274 M5 bars, split chronologically into 184 development and 80 validation sessions. A profile also needed at least 900 M1 bars for its 200-bar M5 interval.

## Results

| Period | Trades | Wins | Win rate | Net R | Targets / stops |
|---|---:|---:|---:|---:|---:|
| Development | 15 | 0 | 0% | -14.43R | 0 / 15 |
| Validation | 8 | 0 | 0% | -6.56R | 0 / 8 |

The three development folds returned -4.31R (5 trades), -6.11R (6), and -4.01R (4). There were 48 qualifying cluster windows across 30,434 profile observations, but only 23 sessions produced a trade; all 23 stopped before reaching POC.

## Decision and limitations

**Reject this version.** A 200-bar profile alone did not fix the VAL/VAH fade under the tested stable-cluster and low-efficiency gates. The sample is sparse and every entry stopped, so it is evidence against this specified rule, not every possible 200-bar profile strategy.

This remains a broker-specific FBS-Demo study. M1 tick volume allocated across candle ranges is a proxy, not OANDA's profile feed or centralized gold trade volume. Commission and extra slippage are excluded. The chronological validation block has been reused in related research and is not pristine.

## Reproduction

Run `python test_oco_limit_200bar_expanded.py` from this folder's parent. Outputs are in `expanded_200bar/`.
