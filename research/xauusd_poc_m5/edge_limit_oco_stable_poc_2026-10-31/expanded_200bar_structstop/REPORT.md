# 200-bar breakout with a structural profile stop

**Date:** 2026-11-01 (Asia/Bangkok)  
**Question:** Does allowing the stop to sit beyond the full 200-bar profile reduce false-breakout stopouts enough to justify the wider risk?

## Method

This is the same 200-completed-M5-bar balance-cluster breakout as the [edge-stop version](../expanded_200bar_breakout/REPORT.md): two M5 closes beyond the frozen value area, entry at the first post-confirmation FBS quote, and target one VA width beyond the broken edge. Only the stop changed: long stops sit below the full 200-bar profile low and short stops above its high, plus the same spread pad. The 264-session chronological split and all profile filters were unchanged.

## Results

| Period | Trades | Wins | Win rate | Net R | Net price PnL | PF (R) | Targets / stops |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | 20 | 12 | 60.0% | -1.51R | -$80.96/oz | 0.70 | 9 / 4 |
| Validation | 18 | 10 | 55.6% | +0.02R | -$58.04/oz | 1.01 | 8 / 3 |

There were 17 target exits among 38 trades, compared with 7 targets with the stop just inside the broken edge. Wider protection reduced stop exits but raised loss size substantially. Development folds were +2.47R, -0.94R, and -3.03R; only one was positive.

## Decision and limitations

**Reject.** The nearly flat validation R result does not transfer to development, the aggregate price PnL is negative in both periods, and the final development fold is materially negative. This stop adjustment alone does not establish a false-breakout filter or a tradable edge.

The study uses FBS-Demo M1 tick volume distributed over candle ranges and FBS bid/ask ticks, not OANDA's profile feed. Commission and extra slippage are excluded; the historical validation block was reused in prior work.

## Reproduction

Run `python test_breakout_200bar_structstop.py` from this folder's parent. Raw trades and profile audits are in `expanded_200bar_structstop/`.
