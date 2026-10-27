# Early-stop trade audit

Source: `trade_journal.csv`. 146 of 313 selected RUNNER trades were stopped before +1R.
Historical M1 OHLC only; no strategy rules changed.

## Comparison

| Group | N | Mean R | Median R | Median pre-exit MFE R | Median H1 ATR | Median risk/H1 ATR | Post-exit >=1R | Post-exit >=2R |
|---|---|---|---|---|---|---|---|---|
| STOP_BEFORE_1R_LOSS | 146 | -0.994 | -1.000 | 0.183 | 9.213 | 0.279 | 109/146 (74.7%) | 99/146 (67.8%) |
| OTHER_SELECTED_LOSS | 72 | -0.358 | -0.333 | 1.404 | 10.122 | 0.284 | 52/72 (72.2%) | 46/72 (63.9%) |
| SELECTED_WIN | 95 | 2.234 | 0.989 | 4.438 | 11.631 | 0.285 | 90/95 (94.7%) | 82/95 (86.3%) |

Post-exit >=1R/2R means the later path moved that far from original entry after exit. This is hindsight, not a recoverable-trade rate.

## Progress made before stop

| Pre-exit MFE bucket | Trades |
|---|---|
| <0.25R | 89 |
| 0.25-<0.5R | 26 |
| 0.5-<1R | 31 |

A large share with very small pre-exit MFE points more toward weak/failed follow-through than exits cutting off substantial progress. It does not establish whether entry timing or stop placement was at fault.

## Early-stop losses by side

| side | trades | mean_runner_r | median_runner_r | median_h1_atr | median_mfe_before_exit_r | post_exit_ge_1r_count |
|---|---|---|---|---|---|---|
| BUY | 95 | -0.992 | -1.000 | 9.724 | 0.198 | 71 |
| SELL | 51 | -0.997 | -1.000 | 7.599 | 0.147 | 38 |

## Early-stop losses by session

| window | trades | mean_runner_r | median_runner_r | median_h1_atr | median_mfe_before_exit_r | post_exit_ge_1r_count |
|---|---|---|---|---|---|---|
| ASIA | 39 | -0.988 | -1.000 | 10.837 | 0.119 | 30 |
| LONDON | 67 | -0.995 | -1.000 | 6.938 | 0.212 | 53 |
| NY0830 | 40 | -0.997 | -1.000 | 12.213 | 0.186 | 26 |

## Reading and next test

The exact STOP_BEFORE_1R group is separated from 54 STOP_AFTER_1R_PARTIAL losses and 18 STOP_BEFORE_1R_OR_AMBIGUOUS losses. The matched chart and pre-entry context comparison is in `CHART_CONTEXT_REVIEW.md`. Session/side results are exploratory and post-hoc; any candidate needs a predeclared rule and an allowed chronologically later holdout before promotion.

## Limitations

- Descriptive, post-hoc analysis of a frozen historical sample; not independent validation.
- M1 OHLC cannot establish exact intrabar price ordering; ambiguous paths are separate.
- Post-exit favorable movement is hindsight and does not prove the stop was avoidable.
- No strategy, entry, exit, or risk rule is changed by this audit.
