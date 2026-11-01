# Frozen cluster target comparison

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md` recorded before this counterfactual run.  
**Sample:** 158 covered sessions; 110 development, 48 validation.

## Results

| Exit target | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz | All net R |
|---|---:|---:|---:|---:|---:|---:|
| Frozen POC | 44 | +2.37 | 29 | -2.90 | -26.75 | -0.53 |
| Opposite VA edge | 43 | -18.52 | 30 | -8.63 | -42.81 | -27.15 |

Development-fold net R:
- Opposite VA edge: fold 1 -1.64R, fold 2 -12.78R, fold 3 -4.10R
- Frozen POC: fold 1 -2.35R, fold 2 -7.87R, fold 3 +12.58R

## Decision

Neither target passed the prespecified rule (at least 20 development trades, positive net R in at least two of three folds, and positive validation net R). The opposite-edge target had a much lower win rate and more negative R. The frozen POC remains the less poor target, but its validation net R was negative, so it is not selected.

The POC rows replicate the earlier frozen-cluster rotation result. Changing only the target does not repair the entry logic. The next investigation should focus on when to trade the edge and on direction/regime, rather than widening the target.

## Limits

This is broker-specific FBS tick-update activity, not centralized XAUUSD volume. Bid/ask is included in replay; commission and extra slippage are excluded. The historical validation segment has been inspected in earlier work and is not a blind holdout.

## Artifacts

- `PROTOCOL.md`: frozen comparison and selection rule
- `test_targets.py`: reproducible two-target replay
- `summary.csv`, `development_folds.csv`, `selection.csv`: aggregate results
- `trades.csv`: individual trades
- `selected_variant.txt`: decision
