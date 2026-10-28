# TREND-RUNNER M15–H1 ATR pause-gate backtest

Status: exploratory only; not independently validated and not promoted.

## Method

- 210 scored TR3 opportunities, 2025-12-01 through 2026-04-17. The locked historical exam was not read.
- M15, M30 and H1 simple ATR(14), with the project's MT5-compatible true range, were computed from M1 bars ending before 2026-04-18 UTC.
- ATRs were normalized to their own trailing percentile versus the preceding 120-H1-bar-equivalent count (480 M15, 240 M30, 120 H1 observations), excluding the current bar. Missing/non-trading bars were not fabricated. The composite was the median of these three percentiles.
- The feature was sampled as of each M1 `decision_time`, not fill time. All attached bars had `available_at <= decision_time`.
- Pause/resume gates were applied before the current opportunity action: pause above the upper percentile and resume at/below the lower percentile. Pairs: 80/70 primary, 75/65 and 85/75 sensitivities.
- Compared both the frozen TR3 RUNNER/SKIP actions and always-RUNNER on the identical rows. Slippage excluded. Constant $10-risk conversion is $10 × total R.

## Primary result: TR3 actions

| Rule | Trades | Total R | Mean R/trade | Max DD (R) | $ at constant $10 risk | Trades blocked | Total after best 3 removed (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Unfiltered TR3 | 83 | +17.702 | +0.213 | 13.327 | +177.02 | 0 | -16.893 |
| Pause 80/resume 70 | 69 | +20.671 | +0.300 | 6.837 | +206.71 | 14 | -13.923 |
| Pause 75/resume 65 | 66 | +19.197 | +0.291 | 6.853 | +191.97 | 17 | -15.397 |
| Pause 85/resume 75 | 75 | +17.133 | +0.228 | 8.743 | +171.33 | 8 | -17.461 |

The primary 80/70 gate added +2.970R over unfiltered TR3 and reduced observed drawdown by 48.7%, but the result remained negative after removing the three best trades.

## Paired always-RUNNER control

| Rule | Trades | Total R | Mean R/trade | Max DD (R) | Blocked from 210 |
|---|---:|---:|---:|---:|---:|
| Unfiltered always-RUNNER | 210 | +19.195 | +0.091 | 20.241 | 0 |
| Pause 80/resume 70 | 173 | +22.288 | +0.129 | 16.607 | 37 |
| Pause 75/resume 65 | 163 | +25.687 | +0.158 | 18.466 | 47 |
| Pause 85/resume 75 | 187 | +18.938 | +0.101 | 18.597 | 23 |

The 75/65 sensitivity had the highest always-RUNNER total, but it is not selected as a replacement: it was evaluated on the same seen data, and every sensitivity must be treated as exploratory.

## Time-split check (all seen development data)

| Source split | Unfiltered TR3: trades / total R | 80/70 TR3: trades / total R |
|---|---:|---:|
| P1 | 33 / +13.777R | 29 / +8.799R |
| P2 | 50 / +3.925R | 40 / +11.873R |

The filter lowered P1 profit while raising P2 profit. Both splits are already-seen design data, so this is not independent validation.

## ATR at the selected TR3 entries

Values are ATR price units for XAUUSD; ranges in brackets are Q25–Q75.

| Outcome | Trades | M15 ATR(14) | M30 ATR(14) | H1 ATR(14) | Median composite percentile |
|---|---:|---:|---:|---:|---:|
| Win (R > 0) | 26 | 8.12 [6.43–11.38] | 12.56 [10.59–17.35] | 18.90 [15.38–25.51] | 33.5% |
| Non-positive (R ≤ 0) | 57 | 7.32 [5.60–13.61] | 10.61 [8.34–19.26] | 16.34 [12.94–29.83] | 27.5% |

Winner medians are modestly higher, but all three ATR ranges overlap substantially; this does not identify a standalone profitable ATR band.

## Decision

This backtest shows that the predeclared 80/70 MTF pause gate improved the observed TR3 total and drawdown on this sample. It does not establish that high ATR causes losses or that the gate will generalize: the sample has 83 primary trades, the best-three-removal result remains negative, the P1/P2 effect differs, and the data were already used during strategy development. Keep the gate as a research-only variant; do not integrate it or tune further against these outcomes.

Reproduction: `.venv/Scripts/python.exe research/2026-10-21-trend-runner-atr-mtf/run_atr_backtest.py`.
