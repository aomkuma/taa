# RETEST-CONTINUATION V1 — Historical Diagnostic

**Decision: diagnostic only; do not add to the strategy or claim verified profitability.**

## Result

- Frozen source-stop cohort: **632** events.
- Completed candidate attempts: **108**.
- Event-level total: **28.246R**; mean: **0.262R/attempt**; win rate: **38.9%**.
- Median holding time: **40.5 minutes**; average MFE **1.47R**, average MAE **-0.70R**.
- Median trade **-0.377R**; best **13.360R**; worst **-1.000R**.
- Event-order drawdown **6.967R** (overlapping attempts; not portfolio drawdown).
- Top 3 winners contribute **117.0%** of total R; excluding them leaves **-4.810R**.

## Coverage by outcome/status

| Status | Events |
|---|---:|
| NO_RETEST | 221 |
| STRUCTURE_INVALIDATED | 114 |
| NO_RECLAIM | 114 |
| COMPLETE | 108 |
| NO_CONTINUATION | 65 |
| PENDING_EXIT_HORIZON | 6 |
| PENDING_RECLAIM_HORIZON | 4 |

## Annual completed attempts

| Year | Attempts | Total R | Mean R | Win rate |
|---:|---:|---:|---:|---:|
| 2023 | 6 | -0.806 | -0.134 | 33.3% |
| 2024 | 42 | 3.394 | 0.081 | 40.5% |
| 2025 | 46 | 25.886 | 0.563 | 41.3% |
| 2026 | 14 | -0.227 | -0.016 | 28.6% |

## Chronological halves

| Half | Attempts | Total R | Mean R | Win rate |
|---|---:|---:|---:|---:|
| first_half | 54 | 4.798 | 0.089 | 40.7% |
| second_half | 54 | 23.448 | 0.434 | 37.0% |

## Completed attempts by side

| Side | Attempts | Total R | Mean R | Win rate |
|---|---:|---:|---:|---:|
| BUY | 55 | 43.670 | 0.794 | 49.1% |
| SELL | 53 | -15.424 | -0.291 | 28.3% |

## Completed attempts by window

| Window | Attempts | Total R | Mean R | Win rate |
|---|---:|---:|---:|---:|
| ASIA | 45 | 7.148 | 0.159 | 37.8% |
| LONDON | 45 | 23.397 | 0.520 | 42.2% |
| NY0830 | 18 | -2.299 | -0.128 | 33.3% |

## Largest winners

| Trade | Date | Side | Window | R |
|---|---|---|---|---:|
| M1WF-00813 | 2025-06-02 | BUY | ASIA | 13.360 |
| M1WF-00773 | 2025-05-05 | BUY | LONDON | 10.077 |
| M1WF-00986 | 2025-09-23 | BUY | LONDON | 9.619 |

### Raw-bar trigger audit for the three largest winners

All timestamps below are UTC. Each listed M5 candle consisted of 5 M1 bars. Reclaim and continuation closes satisfy the frozen BUY rule; each retest touched E0 and closed above it; the confirmation candle's low stayed above the initial structural stop. Entry was at the next M1 open with recorded spread added.

| Trade | Reclaim close vs. E0 | Retest low / close | Confirm close | Next M1 entry / initial stop | Hold | Result |
|---|---:|---:|---:|---:|---:|---:|
| M1WF-00773 | 3263.97 > 3263.59 | 3262.99 / 3264.23 | 3266.97 | 3267.15 / 3262.63 | 221 min | +10.077R |
| M1WF-00813 | 3314.63 > 3314.52 | 3313.53 / 3314.81 | 3315.92 | 3316.09 / 3313.33 | 164 min | +13.360R |
| M1WF-00986 | 3758.82 > 3757.35 | 3757.21 / 3757.36 | 3759.17 | 3759.35 / 3756.96 | 119 min | +9.619R |

The candle sequence and next-open fills are consistent with the frozen rule in these examples; this spot-check does not establish that every replay fill or every trade is correct.

## Exit reasons

| Reason | Trades |
|---|---:|
| STOP | 108 |

## Interpretation and limitations

- Exploratory, in-sample diagnostic: the 632 source events were previously inspected and informed this hypothesis.
- M1 OHLC approximation, not tick replay; recorded spread included and slippage excluded.
- Candidate attempts are event-level and may overlap; summed R is not a portfolio equity result.
- Locked exam interval [2026-04-18, 2026-10-18) and all later data were excluded.
- This result cannot independently confirm future profitability or promote the setup.

Trade-level records are in `diagnostic_trades.csv`; machine-readable summary is in `summary.json`.
