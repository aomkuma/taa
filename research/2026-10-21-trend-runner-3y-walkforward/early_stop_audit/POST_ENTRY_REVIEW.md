# Historical post-entry cohort review

Source: `trade_journal.csv`; selected RUNNER entries 2023-11-01 06:10:00+00:00 through 2026-04-17 12:46:00+00:00. M1 OHLC only; the locked exam beginning 2026-04-18 was excluded.

## Plan and checklist

- [x] Compare the 146 exact pre-+1R stop losses, 95 selected winners, and all other selected outcomes.
- [x] Measure only completed post-entry M1 bars through the earlier of the checkpoint or the modeled exit.
- [x] Keep still-open survivor counts separate from positions already exited before each checkpoint.
- [x] Exclude slippage; use recorded spread for the SELL executable-side M1 estimates.
- [x] Evaluate one break-even 15-minute gate once as an exploratory diagnostic; do not sweep thresholds or change a strategy rule.

## Fixed-checkpoint results

Metrics below are computed only among trades still open at that checkpoint. Exited counts show how the survivor set shrinks. R excursions use initial risk; +0.5R/+1R touch rates are descriptive only.

| Cohort | Minute | Cohort N | Exited | Still open | Close R median [IQR] | MFE R median | MAE R median | +0.5R / +1R touch | M5 structure median (coverage) |
|---|---:|---:|---:|---:|---|---:|---:|---|---|
| EARLY_STOP_LOSS | 5 | 146 | 54 | 92 | -0.285 [-0.546, -0.032] | +0.153 | -0.589 | 20.7% / 0.0% | n/a |
| EARLY_STOP_LOSS | 15 | 146 | 113 | 33 | -0.450 [-0.614, -0.180] | +0.391 | -0.786 | 24.2% / 0.0% | 0.0 (33) |
| EARLY_STOP_LOSS | 30 | 146 | 140 | 6 | -0.377 [-0.742, -0.160] | +0.559 | -0.929 | 50.0% / 0.0% | 0.5 (6) |
| EARLY_STOP_LOSS | 60 | 146 | 146 | 0 | n/a | n/a | n/a | n/a | n/a |
| OTHER_SELECTED_OUTCOME | 5 | 72 | 0 | 72 | +0.109 [-0.210, +0.563] | +0.522 | -0.313 | 52.8% / 19.4% | n/a |
| OTHER_SELECTED_OUTCOME | 15 | 72 | 9 | 63 | +0.361 [-0.114, +0.905] | +0.985 | -0.602 | 82.5% / 49.2% | 1.0 (63) |
| OTHER_SELECTED_OUTCOME | 30 | 72 | 34 | 38 | +0.423 [-0.075, +1.364] | +1.404 | -0.643 | 97.4% / 68.4% | 2.0 (38) |
| OTHER_SELECTED_OUTCOME | 60 | 72 | 66 | 6 | +1.332 [+0.584, +1.913] | +3.679 | -0.557 | 100.0% / 83.3% | 4.0 (6) |
| SELECTED_WIN | 5 | 95 | 0 | 95 | +0.190 [-0.164, +0.620] | +0.521 | -0.355 | 50.5% / 25.3% | n/a |
| SELECTED_WIN | 15 | 95 | 0 | 95 | +1.014 [+0.345, +1.508] | +1.413 | -0.439 | 86.3% / 65.3% | 1.0 (94) |
| SELECTED_WIN | 30 | 95 | 3 | 92 | +1.343 [+0.835, +2.264] | +2.231 | -0.509 | 96.7% / 88.0% | 2.0 (92) |
| SELECTED_WIN | 60 | 95 | 25 | 70 | +2.508 [+1.444, +3.796] | +3.662 | -0.495 | 100.0% / 100.0% | 5.0 (70) |

## Interpretation

Compare early-stop and winner paths only at a checkpoint where both still have survivors. Any increase in separation at later checkpoints is conditional on having lasted that long, so it cannot be interpreted as an unconditional entry signal. MFE/MAE and threshold touches use M1 OHLC; intraminute ordering and executable stop fills cannot be reconstructed from these bars.

## Exploratory 15-minute close assessment

Among positions still open at each fixed checkpoint, use directional close R only as a retrospective ranking of positive final R, not a tradable or validated predictor. This cohort is in-sample; the outcome label is known only later.

| Minute | Period | Survivors | Positive final R | Spearman(close R, final R) | AUC(close R for positive final R) |
|---:|---|---:|---:|---:|---:|
| 5 | ALL | 259 | 95 | 0.397 | 0.671 |
| 15 | ALL | 191 | 95 | 0.620 | 0.779 |
| 30 | ALL | 136 | 92 | 0.594 | 0.770 |
| 60 | ALL | 76 | 70 | 0.478 | 0.702 |
| 5 | 2023 | 12 | 3 | 0.490 | 0.852 |
| 5 | 2024 | 55 | 24 | 0.390 | 0.620 |
| 5 | 2025 | 138 | 41 | 0.328 | 0.634 |
| 5 | 2026 | 54 | 27 | 0.419 | 0.691 |
| 15 | 2023 | 9 | 3 | 0.454 | 0.556 |
| 15 | 2024 | 40 | 24 | 0.599 | 0.781 |
| 15 | 2025 | 99 | 41 | 0.611 | 0.771 |
| 15 | 2026 | 43 | 27 | 0.658 | 0.852 |
| 30 | 2023 | 5 | 3 | 0.300 | 0.500 |
| 30 | 2024 | 30 | 24 | 0.580 | 0.889 |
| 30 | 2025 | 69 | 40 | 0.641 | 0.792 |
| 30 | 2026 | 32 | 25 | 0.458 | 0.606 |
| 60 | 2023 | 4 | 3 | 0.000 | 0.667 |
| 60 | 2025 | 34 | 30 | 0.382 | 0.683 |
| 60 | 2026 | 20 | 19 | 0.665 | 0.632 |

One illustrative break-even gate (not deployed) is shown below: at +15 minutes, if a position is still open, has not touched +1R, and its directional close is at or below 0R, replace the baseline future result with that 15-minute close. This natural threshold was evaluated once, not optimized or swept, but the idea is prompted by historical analysis and remains post-hoc/in-sample evidence.

| Cohort | Trades | Gate exits | Of exits, baseline winners | Baseline total R | Gate total R | Net delta R | Delta on baseline non-winners | Delta on baseline winners | Baseline / gate win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ALL | 313 | 54 | 11 | +41.36 | +43.46 | +2.10 | +15.77 | -13.67 | 30.4% / 26.8% |
| YEAR_2023 | 14 | 4 | 1 | -6.25 | -5.60 | +0.65 | +1.63 | -0.98 | 21.4% / 14.3% |
| YEAR_2024 | 66 | 9 | 2 | +19.47 | +18.81 | -0.65 | +2.68 | -3.34 | 36.4% / 33.3% |
| YEAR_2025 | 168 | 28 | 5 | +0.17 | +2.08 | +1.91 | +8.35 | -6.43 | 24.4% / 21.4% |
| YEAR_2026 | 65 | 13 | 3 | +27.98 | +28.16 | +0.19 | +3.10 | -2.92 | 41.5% / 36.9% |
| WINDOW_ASIA | 84 | 19 | 2 | -4.13 | +1.19 | +5.32 | +7.01 | -1.69 | 23.8% / 21.4% |
| WINDOW_LONDON | 153 | 29 | 9 | +48.24 | +44.42 | -3.82 | +8.16 | -11.98 | 35.3% / 29.4% |
| WINDOW_NY0830 | 76 | 6 | 0 | -2.75 | -2.15 | +0.60 | +0.60 | +0.00 | 27.6% / 27.6% |
| SIDE_BUY | 192 | 41 | 9 | +45.93 | +50.32 | +4.39 | +13.16 | -8.77 | 31.2% / 26.6% |
| SIDE_SELL | 121 | 13 | 2 | -4.57 | -6.86 | -2.29 | +2.61 | -4.89 | 28.9% / 27.3% |

The 11 eventual winners stopped by the gate all went on to touch +1R from entry between minutes 22 and 47 (median 36 minutes). The largest was M1WF-01044: close -0.278R at minute 15, then +3.885R final; its first +1R touch was at minute 27. This shows why the short checkpoint would cut some genuine delayed continuations.
The five largest baseline winners were not changed by the gate. Removing those same five still leaves -21.48R baseline versus -19.38R under the gate, so the small aggregate increase does not remove the strategy's dependence on a handful of outliers.

The gate recovers R by closing non-winners early, but its total delta is the net of loss reduction on baseline non-winners and lost return on eventual winners. The aggregate and its year/session/side cuts are all same-sample results; the small net uplift masks worse results in 2024, London, and SELL. This is not a validated strategy improvement; do not change production or isolated candidate rules from it.

No new entry/exit rule is recommended from this report. The descriptive results may guide chart review, but any candidate must be separately frozen and tested without retuning on these same observations. The existing RETEST-CONTINUATION prospective observer remains isolated and unchanged.

Reproducibility: `post_entry_cohort.py`. M1 bars loaded: 862,895; range 2023-11-01 06:09:00+00:00 to 2026-04-17 13:46:00+00:00 UTC. Spread is applied to SELL OHLC as `spread * 0.01`; slippage is excluded.
