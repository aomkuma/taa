# One-bar edge rejection confirmation result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before the run.  
**Sample:** 158 covered sessions; 110 development, 48 validation.

| Entry rule | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz | All net R |
|---|---:|---:|---:|---:|---:|---:|
| immediate | 44 | +2.37 | 29 | -2.90 | -26.75 | -0.53 |
| nextbar_confirmation | 21 | +0.66 | 4 | -2.36 | -17.32 | -1.70 |

Next-bar confirmation development folds: fold 1 +0.76R (4 trades), fold 2 -1.50R (6 trades), fold 3 +1.40R (11 trades)

## Decision

The confirmation raised development win rate to 61.9% on 21 trades and netted +0.66R, but validation had only four trades and lost -2.36R. It fails the frozen rule because validation net R is negative; the four-trade validation count is also too small to support adoption. Across all 25 trades the result was -1.70R.

The higher win rate did not make it a winner. The strategy remains unselected.

Limits: historical validation is partly inspected; quote-update activity is FBS-specific; spread is included but commission and extra slippage are not.

Artifacts: `PROTOCOL.md`, `test_confirmation.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `trades.csv`.
