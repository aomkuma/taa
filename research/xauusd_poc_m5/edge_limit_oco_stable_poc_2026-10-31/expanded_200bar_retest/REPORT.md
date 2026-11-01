# 200-bar breakout retest with a structural stop

**Date:** 2026-11-01 (Asia/Bangkok)  
**Question:** Can a retest-and-reclaim filter remove false breakouts from the 200-bar balance-cluster setup while keeping the wider stop?

## Frozen rule

Use the same previous-200-completed-M5-bar profile and cluster filters as the [200-bar breakout test](../expanded_200bar_breakout/REPORT.md). Require two consecutive M5 closes beyond frozen VAH/VAL. Then wait up to 12 M5 bars for the first retest of the broken value edge. Enter only if that retest bar touches the edge and closes back outside value; cancel the setup if the first retest closes back inside. Entry uses the first post-close FBS quote. Stop is beyond the full 200-bar profile low/high plus spread pad; target is one VA width beyond the broken edge. The sample and chronological split are unchanged (264 sessions; 184 development / 80 validation).

## Results

| Period | Trades | Wins | Win rate | Net R | Net price PnL | PF (R) | Targets / stops |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | 9 | 5 | 55.6% | -1.53R | -$127.91/oz | 0.54 | 3 / 3 |
| Validation | 6 | 2 | 33.3% | -1.49R | -$101.39/oz | 0.38 | 2 / 2 |

Development folds returned +1.73R (4 trades), -1.24R (3), and -2.02R (2). The retest filter reduced the sample to 15 trades, but both development and validation were negative; the wide structural stop made the losing price moves large.

## Decision and limitations

**Reject this version.** Retest-and-reclaim plus a wide stop did not remove the negative expectancy. The sample is small, so this only rejects the stated rule; it does not prove every breakout filter is ineffective.

This is FBS-Demo, not OANDA. M1 tick volume allocated across candle ranges approximates the profile, and commission plus additional slippage are omitted. The historical validation block has been reused in related research.

## Reproduction

Run `python test_breakout_200bar_retest.py` from this folder's parent. Raw trades and profile audits are in `expanded_200bar_retest/`.
