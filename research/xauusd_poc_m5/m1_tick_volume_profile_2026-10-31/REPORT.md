# M1 tick-volume profile proxy result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, written before the M1-profile run.  
**Feed:** FBS-Demo M1 tick_volume for profile; FBS bid/ask raw ticks for execution.  
**Sample:** Same 158 covered sessions (110 development / 48 validation). M1 session-bar coverage versus expected M1 bars from M5 was 99.998% on average; minimum 99.853%, with no session below 99.5% (`m1_session_coverage_audit.csv`).

## Results

| Rule | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz | Wins (validation) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 49 | -13.05 | 25 | -15.98 | -43.18 | 7 |
| min_rr_2 | 29 | -7.48 | 7 | -7.98 | -12.46 | 0 |

Development folds:
- baseline: fold 1 -8.60R / 11 trades, fold 2 +1.53R / 19 trades, fold 3 -5.99R / 19 trades
- min_rr_2: fold 1 -5.50R / 5 trades, fold 2 +0.67R / 15 trades, fold 3 -2.65R / 9 trades

## Decision

No candidate. The baseline and 2R variant were negative in validation, and no variant met the selection rule. The 2R raw-quote-count result from `../min_reward_risk_2026-10-31/REPORT.md` (+4.77R validation) does not carry over: with M1 tick-volume distribution, the 2R variant lost -7.98R on seven validation trades with no winners. The seven-trade validation result is small, but it is enough to withdraw the earlier raw-tick candidate claim; it is not enough to establish the M1 variant as a stable failure by itself.

## Method correction and remaining mismatch

TradingView documents that Forex/CFD Volume Profile uses tick volume from lower-timeframe bars and defines tick volume as price updates; POC is the highest-activity row and the 70% value area is a configurable convention ([TradingView: Volume Profile concepts](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/)). Its charting library also distributes a lower-timeframe bar across rows in proportion to price overlap ([TradingView Charting Library: Session Volume Profile](https://tradingview.com/charting-library-docs/latest/trading_terminal/session-volume-profile/)). This run therefore uses M1 tick_volume and OHLC-range allocation rather than assigning every raw FBS quote directly to a bin.

It remains an approximation: FBS is not the OANDA feed in the screenshot, the row size is fixed at $0.10 rather than confirmed from the custom indicator settings, and M1 OHLC does not reveal each quote update price. Do not call these levels the same as the OANDA indicator. Entry fills use FBS bid/ask ticks; commission and extra slippage remain excluded.

Artifacts: `PROTOCOL.md`, `test_m1_profile.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `qualifying_profile_windows.csv`, `session_audit.csv`, `m1_session_coverage_audit.csv`, `trades.csv`.
