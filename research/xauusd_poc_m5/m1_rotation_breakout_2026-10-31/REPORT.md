# M1 tick-volume rotation / breakout comparison

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before the replay.  
**Profile:** FBS-Demo M1 tick_volume allocated by OHLC price overlap into $0.10 rows.  
**Execution:** FBS bid/ask ticks.  
**Sample:** 158 covered sessions (110 development / 48 validation).

## Results

| Variant | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz |
|---|---:|---:|---:|---:|---:|
| Rotation only | 49 | -13.05 | 25 | -15.98 | -43.18 |
| Rotation + breakout retest | 98 | -25.17 | 47 | -26.83 | -45.59 |

The breakout variant split into 22 rotation + 25 breakout trades in validation; rotations contributed -15.98R and breakouts -10.84R. The breakout addition worsened the validation total. It was negative in all three development folds as well.

## Decision

Neither variant passed selection. The results do not support either fading the edge to POC or switching to a retest breakout under these frozen rules. This is a stronger rejection of the user-aligned playbook on the FBS M1 proxy than the earlier raw-tick test.

The values still do not reproduce the OANDA indicator. TradingView documents tick volume from lower-timeframe bars for Forex/CFDs, but this study uses FBS M1 bars and a fixed $0.10 row size; M1 OHLC overlap is a proxy for price allocation. See [TradingView Volume Profile concepts](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/) and [row allocation documentation](https://tradingview.com/charting-library-docs/latest/trading_terminal/session-volume-profile/).

Historical validation has been inspected repeatedly. Bid/ask is included; commission and extra slippage are not. This rejects these variants on the available sample, not every possible Volume Profile strategy.

Artifacts: `PROTOCOL.md`, `test_rotation_breakout.py`, `summarize_trades.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `trades.csv`, `qualifying_profile_windows.csv`, `session_audit.csv`.
