# Early-stop vs winner chart/context comparison

## Method

Compare 146 exact selected STOP_BEFORE_1R losses with 95 positive selected RUNNER trades from the same frozen 3-year journal. Pre-entry features use only the prior 15 or 60 completed M1 bars; winner/loss labels are retrospective and are not features. Charts use only complete M15 candles resampled from M1, normalize price directionally by initial risk, and show one illustrative pair for every window x side stratum. Within each stratum, the loss is the median pre-exit-MFE case; its winner is the nearest standardized match on pre-entry features. Charts are illustrative, not evidence of statistical significance.

## Pre-entry context across all trades

| Pre-entry feature (known at entry) | Early stops median (IQR) | Selected winners median (IQR) |
|---|---:|---:|
| 15m directional return / H1 ATR | +0.374 (0.325) | +0.337 (0.277) |
| 60m directional return / H1 ATR | +0.472 (0.487) | +0.470 (0.527) |
| Entry location in prior 60m range (directional, 0-1) | +0.961 (0.133) | +0.974 (0.085) |
| Directional M1 body fraction in prior 60m | +0.533 (0.067) | +0.533 (0.067) |
| Prior 60m high-low range / H1 ATR | +0.920 (0.518) | +0.915 (0.547) |

IQR is the interquartile range. Directional returns are side-adjusted and normalized by each trade's H1 ATR. Entry location 0 means the unfavorable edge and 1 the favorable edge of the prior 60-minute range; values above 1 indicate entry beyond that favorable edge. A difference is descriptive and must not be converted directly into a filter.

The cohort medians are nearly identical on all five measured pre-entry features: 15m/60m directional return, range location, candle-body agreement, and prior-range size. The simple M1 context measured here does not distinguish the groups; that weakens the case for adding a same-sample pre-entry filter based on these variables.

## Matched chart cases

| Window | Side | Cohort N: loss / win | Early stop (R, pre-exit MFE) | Winner (R, pre-exit MFE) | Chart |
|---|---|---:|---|---|---|
| ASIA | BUY | 27 / 16 | M1WF-00635 (-0.94R, +0.12R MFE) | M1WF-00365 (+0.91R, +2.38R MFE) | `matched_charts/pair_01_asia_buy.png` |
| ASIA | SELL | 12 / 4 | M1WF-00250 (-1.00R, +0.15R MFE) | M1WF-00640 (+3.63R, +6.69R MFE) | `matched_charts/pair_02_asia_sell.png` |
| LONDON | BUY | 44 / 31 | M1WF-00377 (-1.00R, +0.21R MFE) | M1WF-01061 (+0.90R, +2.47R MFE) | `matched_charts/pair_03_london_buy.png` |
| LONDON | SELL | 23 / 23 | M1WF-00583 (-1.00R, +0.17R MFE) | M1WF-00382 (+0.02R, +1.97R MFE) | `matched_charts/pair_04_london_sell.png` |
| NY0830 | BUY | 24 / 13 | M1WF-00811 (-1.00R, +0.22R MFE) | M1WF-00978 (+2.21R, +5.15R MFE) | `matched_charts/pair_05_ny0830_buy.png` |
| NY0830 | SELL | 16 / 8 | M1WF-00585 (-1.00R, +0.10R MFE) | M1WF-01273 (+1.45R, +6.24R MFE) | `matched_charts/pair_06_ny0830_sell.png` |

## Interpretation and research decision

Read the paired charts as examples, not as a causal comparison: even after matching side/session and coarse pre-entry context, the winning label is known only after the fact. The 146 early-stop paths mostly show very little favorable movement before exit; that is more consistent with failed follow-through than a trailing exit cutting off an already-large open gain. Whether a confirmation delay, pullback/retest entry, or initial-stop geometry is responsible remains unresolved.

A separate RETEST-CONTINUATION candidate already exists and studies post-stop reclaim, retest, then M5 confirmation; it has an isolated historical diagnostic and a frozen prospective observer. This chart review is not evidence to create or alter that rule. Its prior positive historical result was concentrated in a few trades, so preserve its separate prospective evidence contract rather than retuning it here. For the baseline TR3 entry, no new candidate is promoted from this chart review. Any further test must use a separately predeclared rule and an allowed, strictly later sample; preserve the locked exam boundary and the already frozen observer contract.

## Limitations

- Historical M1 OHLC backtest only; no tick-level ordering, spread/slippage sensitivity, or live executions are added here.
- The cohort label uses final RUNNER R; it is retrospective, not known at entry.
- Matching and representative chart selection are for visualization only. They do not prove that any entry modification improves performance.
- Pre-entry comparisons are exploratory/post-hoc, with five related features and no multiple-testing correction.
- No change to TR1/TR3/TR4, any order path, or the forward-shadow contract.
