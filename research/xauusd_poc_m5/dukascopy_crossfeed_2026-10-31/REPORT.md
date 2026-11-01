# Dukascopy cross-feed test — XAUUSD M5 profile clusters

**Date:** 2026-10-31 (Asia/Bangkok)  
**Research status:** No candidate passed the predeclared consistency rule.

## Question

Does the six-hour POC/value-area edge idea survive when the source feed changes from FBS-Demo to Dukascopy? Is a six-hour lookback essential, and does a rejection close back inside the cluster help?

## Data and replay

- Dukascopy XAUUSD bid and ask M1 candles, 2025-10-01 through 2026-10-28; the export provides separate bid/ask prices and volume fields ([official exporter](https://www.dukascopy.com/api/data/get/historical-data-export)).
- 381,982 bid/ask-aligned M1 bars; profile allocation uses bid M1 volume spread uniformly over each M1 bar's $0.10 price range. This is an intrabar allocation proxy, not trade-by-trade volume at price.
- Quotes are aggregated into M5 candles. Entries and exits use the relevant bid/ask side. Because only M1 OHLC is used, if stop and target are both possible within one M1 bar, stop is assumed first. An OCO touch at both edges in the same minute is counted as ambiguous and skipped.
- To compare like-for-like with the FBS work, the same 158 FBS-covered sessions and chronological split were retained: 110 development, 48 validation. The validation period has been repeatedly inspected in related work and is not a pristine holdout.
- Tested lookbacks were 3h, 6h and 12h. A cluster is defined by overlap of the older/recent halves' 70% value areas >= 0.50, half-period POC distance <= $0.50, lookback-scaled price-path efficiency <= 0.25, and the prior M5 close inside the full-window value area.
- Baseline edge-limit strategy freezes the first qualifying cluster, places buy VAL / sell VAH limits while the cluster remains valid, targets POC, and places the stop outside the full rolling profile extreme plus spread pad. A second variant waits for an M5 sweep of a frozen VA edge and close back inside, enters at the next minute open, targets POC, and stops beyond the rejection wick plus spread pad.
- Costs beyond observed bid/ask spread (commission, queue position, latency, additional slippage) are excluded.

## Results

| Setup | Lookback | Development | Development folds | Validation | Decision |
|---|---:|---:|---|---:|---|
| Requalify every bar, edge limit, full-profile stop | 3h | 53 trades, -13.71R | -5.31, -6.68, -1.72R | 30 trades, -9.35R | Reject |
| Same | 6h | 38 trades, -9.16R | +1.04, -5.39, -4.81R | 17 trades, -2.93R | Reject |
| Same | 12h | 25 trades, -6.33R | -4.47, +0.38, -2.24R | 12 trades, +2.50R | Reject; one positive fold and only 12 validation trades |
| Requalify every bar, edge limit, tight VA stop | 3h / 6h / 12h | -60.68 / -54.98 / -66.90R | 0 positive folds | -26.39 / -19.37 / -19.60R | Reject all |
| Cluster remains active until two closes outside VA; edge limit, profile stop | 6h | 64 trades, -27.11R | -1.09, -11.54, -14.48R | 30 trades, -14.42R | Reject |
| Same lifecycle rule, edge limit, profile stop | 12h | 42 trades, -13.52R | -7.06, -1.60, -4.86R | 23 trades, -2.61R | Reject |
| Same lifecycle rule, sweep-and-reclaim entry, wick stop | 6h | 43 trades, -28.35R | -10.88, -11.15, -6.32R | 19 trades, -7.10R | Reject |
| Same lifecycle rule, sweep-and-reclaim entry, wick stop | 12h | 24 trades, +2.23R | +0.88, -2.01, +3.36R | 16 trades, -9.13R | Reject; development gain did not transfer |

The strongest validation result was 12h edge-limit with structural stop (+2.50R / 12 trades), but its development result was -6.33R and only one of three development folds was positive. The strongest development result was 12h sweep-and-reclaim (+2.23R / 24 trades), but its validation was -9.13R. The direction of performance reverses between periods. No tested lookback or entry passed the predeclared rule of at least 20 development trades, positive results in at least two development folds, and positive validation R.

Tight stops performed worst. A stop just outside VAL/VAH repeatedly lost before price reached the POC, including 100% stops for the tested 12h variant. Structural stops raised the chance of returning to POC but left the planned target smaller than the stop risk in most cases; that helped explain why win rates above 50% could still have negative R.

## Interpretation

The six-hour restriction is not supported as a factual requirement: testing 3h and 12h did not reveal a robust replacement. Relaxing the six-hour rule to 12h created isolated positive windows, but not consistent performance. The more important failure is regime transfer: a price cluster plus edge fade was insufficient to protect against continued directional movement. Waiting for an M5 rejection changed the development result at 12h but failed validation.

This is a cross-feed robustness check, not an OANDA replication. Dukascopy differs from TradingView's OANDA feed, and M1 volume allocation and OHLC fill replay cannot reproduce exact indicator levels or tick order. Therefore the results can reject this version of the idea, but cannot prove an alternative profitable strategy.

## Reproducibility

- `run_crossfeed.py`: 3h/6h/12h lookbacks, two stop variants, all outputs in this folder.
- `../cluster_lifecycle_2026-10-31/run_lifecycle.py`: lifecycle entry handling and sweep/reclaim entries at 6h/12h.
- `data/`: bid/ask M1 CSV exports for the tested period.
- Outputs: `summary.csv`, `development_folds.csv`, `selection.csv`, and `trades.csv` in each experiment folder.

