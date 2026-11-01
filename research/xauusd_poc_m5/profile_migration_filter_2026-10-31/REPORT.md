# Profile-migration direction filter result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before outcome calculation.  
**Sample:** 158 covered sessions (110 development, 48 validation).

| Period | Trades | Wins | Net points/oz | Net R |
|---|---:|---:|---:|---:|
| development | 24 | 7 | +4.47 | -0.05 |
| validation | 19 | 5 | -15.04 | -2.24 |
| all | 43 | 12 | -10.57 | -2.29 |

Development folds: fold 1 -1.69R, fold 2 -8.99R, fold 3 +10.63R

## Decision

No selection. The direction filter reduced trades from 73 to 43, but validation remained negative at -2.24R. Development was near flat overall and had only one positive fold out of three. It did not pass the frozen selection rule. Profile-center migration alone did not provide a reliable way to choose a trade side.

## Limits

This uses broker-specific quote-update volume and the already inspected historical validation period. Spread is reflected in tick fills; commission and additional slippage are excluded.

## Artifacts

- `PROTOCOL.md`: hypothesis and frozen rules
- `test_migration_filter.py`: reproducible replay
- `summary.csv`, `development_folds.csv`, `selection.csv`: grouped results
- `trades.csv`: trade-level output
