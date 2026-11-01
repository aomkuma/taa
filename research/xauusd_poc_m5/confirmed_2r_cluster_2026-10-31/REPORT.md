# Next-bar confirmation plus 2R gate result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before the run.  
**Sample:** 158 covered sessions; 110 development / 48 validation.

## Result

| Rule | Dev trades | Dev net R | Validation trades | Validation net R |
|---|---:|---:|---:|---:|
| baseline | 44 | +2.37 | 29 | -2.90 |
| confirmed_2r | 4 | -0.66 | 0 | +0.00 |

The conjunction produced only 4 development trades and zero validation trades. The zero is explained by the strict two-stage rule: no validation setup both broke the rejection candle on the next bar and offered 2R to the frozen POC before its one-per-edge limit. This is too sparse to assess and fails the minimum sample rule outright.

## Decision

Rejected. Combining the two filters did not yield a testable frequency, let alone a confirmed edge. The four development trades do not support a conclusion.

The historical validation was previously inspected and is not blind. The local profile uses FBS quote-update activity, not centralized XAUUSD volume; spread is included, commission and extra slippage are excluded.

Artifacts: `PROTOCOL.md`, `test_confirmed_2r.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `trades.csv`.
