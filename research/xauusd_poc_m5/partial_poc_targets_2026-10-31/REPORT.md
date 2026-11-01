# Partial POC targets on cluster-edge entries — Dukascopy XAUUSD M5

**Date:** 2026-10-31 (Asia/Bangkok)  
**Decision:** Taking profit before POC reduced some validation losses, but no target fraction passed the consistency rule.

## Test

Keep the cluster lifecycle limit entries, fill prices, and stop beyond the full frozen profile extreme fixed. Re-simulate exits at 50%, 70%, 78%, 88%, or 100% of the distance from the actual fill price to frozen POC. Quote-side stop/target conditions use Dukascopy M1 bid/ask OHLC, with the stop first if both could trade in one M1 bar; target is not credited on the entry minute. The 100% target reproduces the POC target baseline.

This isolates exit placement for the same 6h and 12h entries. It does not permit a second entry after an earlier exit in the session. The same previously inspected 158-session sample and split are used; spread is included, extra slippage/commission excluded.

## Results

| Lookback / target | Development | Fold 1 / 2 / 3 | Validation |
|---|---:|---|---:|
| 6h, 78% to POC | 64 trades, -24.71R | -2.16 / -10.12 / -12.44R | 30 trades, -9.58R |
| 6h, 88% to POC | 64 trades, -26.91R | -1.67 / -11.82 / -13.42R | 30 trades, -13.51R |
| 12h, 50% to POC | 42 trades, -7.70R | -3.42 / -1.04 / -3.24R | 23 trades, -1.96R |
| 12h, 70% to POC | 42 trades, -11.38R | -3.66 / -1.75 / -5.97R | 23 trades, -1.80R |
| 12h, 78% to POC | 42 trades, -14.63R | -6.66 / -2.29 / -5.67R | 23 trades, -3.07R |
| 12h, 88% to POC | 42 trades, -13.40R | -6.12 / -1.98 / -5.30R | 23 trades, -3.50R |
| 12h, 100% / POC | 42 trades, -13.52R | -7.06 / -1.60 / -4.86R | 23 trades, -2.61R |

The 12h 70% target had the least negative validation result (-1.80R) among these 12h fractions, but it remained negative in all three development folds. The 78%/88% levels requested as a possibility did not improve the result: both validation and development remained negative. A nearer target increased hit rate but paid too little against the wide structural stop.

## Files

`run_targets.py` produces `trade_outcomes.csv`, `summary.csv`, `development_folds.csv`, and `selection.csv`.
