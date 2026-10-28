# TR3 post-entry path diagnostics

**Status: completed exploratory analysis; no strategy change recommended.** This is not an independent backtest or a promotion result.

## Data and method

- Input: frozen TR3 primary predictions and XAUUSD FBS-Demo M1 bars.
- Population: 83 frozen `RUNNER` selections; 26 eventually positive (`runner_r > 0`) and 57 non-positive; P1 33 / P2 50.
- Entry range: 2025-12-01 00:55 UTC through 2026-04-17 01:10 UTC. All are seen P1/P2 development observations. Historical exam data was not read.
- Checkpoints: 15, 30, 60, 120 minutes after entry. Metrics stop at the earlier of checkpoint or frozen runner exit. Only complete M1 bars strictly after the entry minute are used. A separate `still_open_at_checkpoint` flag prevents confusing short completed trades with live positions.
- `close_r`, OHLC MFE/MAE and target touches are directional and divided by initial risk. M5 structure is a count of adjacent completed UTC M5 bars making both directional HH+HL (BUY) or LL+LH (SELL).

## Findings

| Checkpoint | Still open: positive / non-positive | Median close R (positive / non-positive) | Median MFE R (positive / non-positive) | Median MAE R (positive / non-positive) | Directional M5 structure count (positive / non-positive) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 15m | 26 / 27 | +0.859 / -0.144 | 1.264 / 0.627 | -0.436 / -0.568 | 1 / 1 |
| 30m | 23 / 12 | +1.267 / +0.475 | 1.926 / 1.779 | -0.463 / -0.699 | 2 / 2 |
| 60m | 16 / 3 | +2.509 / +1.385 | 4.089 / 6.185 | -0.357 / -0.655 | 5 / 3 |
| 120m | 9 / 0 | +4.555 / n/a | 6.247 / n/a | -0.408 / n/a | 12 / n/a |

The “still open” rows are survivorship-selected, especially at 60 and 120 minutes (only 19 and 9 positions remain open). The 60-minute non-positive MFE is based on just three trades; it is not a stable comparison. Seventeen of the 26 positive trades had already exited by 120 minutes, so a live-position-only comparison at that point excludes many eventual winners.

At 15 minutes the eventual winners had a higher median close R in both periods: P1 +0.859 versus +0.048 among non-positive trades still open; P2 +0.690 versus -0.347. The direction of this early close-return difference is consistent across P1/P2, but the samples are small and it is a retrospective split by final result, not a validated predictor. Early structure counts do not separate the cohorts: median directional M5 HH/HL (BUY) or LL/LH (SELL) counts are equal at 15 and 30 minutes. At 30 minutes, non-positive trades still open often showed favorable movement too: two-thirds touched +1R, and 5/12 touched +3R, versus 17/23 and 5/23 among eventual winners. That is a warning against using one threshold or early excursion as a standalone selector.

### Supplemental rank check (exploratory, computed after the initial report)

Among only the 53 trades still open at 15 minutes with a complete M1 close, the association between 15-minute directional close R and final RUNNER R was Spearman 0.582 overall (P1 0.465, P2 0.643). As a retrospective ranking of eventual positive versus non-positive outcomes in this same conditional group, the AUC was 0.771 (26 positive, 27 non-positive; ties receive half credit). This is a useful reason to investigate the feature, not evidence of a deployable signal: it is an in-sample, outcome-labeled analysis of a small survivor subset, with no confidence interval or untouched validation.

## Interpretation

The clearest descriptive feature is that eventual winners tended to have better directional closing performance early, while many non-positive trades closed quickly. However, the 30-minute overlap and the lack of an early M5-structure difference mean this does **not** establish a reliable continuation rule. The runner's hold time itself also selects the later surviving population. Do not add a 15-minute gate, 1R/3R rule, or HH/HL filter to TR1/TR3/TR4 from these results.

## Limitations and reproducibility

- P1/P2 are already-seen development data and the target outcome defines the retrospective cohorts; no unseen exam or forward evidence is claimed.
- M1 OHLC highs/lows approximate excursion and touches. They do not establish tick ordering inside a candle or executable prices, and the final incomplete candle before exit is excluded.
- Very fast exits can have no complete post-entry M1 bar; medians use rows with available path values, so coverage counts must be read with each group size.
- Checkpoint survivor groups shrink to 3 non-positive rows at 60 minutes and zero at 120 minutes.
- Slippage remains excluded, consistent with the user's instruction.

Re-run with `.venv/Scripts/python.exe research/2026-10-21-trend-runner-path-diagnostics/analyze_paths.py`. `trade_paths.csv` contains one row per selected trade/checkpoint; `summary.csv` pools P1/P2 by outcome and checkpoint/survivor status; `summary_by_split.csv` retains the period splits.

## Decision

Research only. Keep all strategy definitions frozen. The next valid step for any proposed path-based rule is a new, predeclared forward shadow sample under the existing TR3 evaluation contract, followed by a one-time evaluation; do not use the locked historical exam.
