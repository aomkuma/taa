# M5 close-break stop result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before the replay.  
**Profile:** FBS M1 tick_volume OHLC allocation, $0.10 rows; execution: FBS bid/ask ticks.  
**Sample:** 158 sessions, 110 development / 48 validation.

| Rule | Dev trades | Dev net R | Validation trades | Validation net R | Val points/oz | Val wins | Close stops (val) |
|---|---:|---:|---:|---:|---:|---:|---:|
| wick_stop | 49 | -13.05 | 25 | -15.98 | -43.18 | 7 | 0 |
| close_break | 49 | +13.86 | 25 | -21.67 | -57.27 | 9 | 16 |

Development fold net R:
- wick_stop: fold 1 -8.60R, fold 2 +1.53R, fold 3 -5.99R
- close_break: fold 1 -1.36R, fold 2 +10.99R, fold 3 +4.23R

## Interpretation

Close-confirmed invalidation raised the development win rate and net R, but validation dropped to -21.67R (-57.27 price points) on 25 trades. The close-break variant also realized closes after the edge break rather than a hard stop; the 16 validation close stops averaged a larger than planned loss, which overwhelms the development improvement. The two positive development folds did not generalize.

## Decision

No selection. This stop rule fails validation despite a better development result. It illustrates why stop placement must be evaluated on realized loss, not win rate alone. No live method is supported.

Limits: FBS proxy rather than OANDA; M1 OHLC profile allocation is approximate; validation was inspected repeatedly; commission and extra slippage excluded.

Artifacts: `PROTOCOL.md`, `test_close_break.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `trades.csv`, `qualifying_profile_windows.csv`.
