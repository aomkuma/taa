# Minimum 2R to frozen POC result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before the corrected replay.  
**Sample:** 158 covered sessions (110 development / 48 validation).

| Rule | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz | All net R |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 44 | +2.37 | 29 | -2.90 | -26.75 | -0.53 |
| min_rr_2 | 30 | +2.09 | 12 | +4.77 | +0.27 | +6.86 |

Development-fold net R:
- Fold 1: -0.39R (8 trades)
- Fold 2: -8.45R (12 trades)
- Fold 3: +10.94R (10 trades)

## Decision

The 2R gate passed development and validation trade-count minimums, and validation finished at +4.77R on 12 trades. It did **not** meet the frozen consistency rule: only one of three development folds was positive; fold 2 lost -8.45R. The 12 validation trades also include only two winners, so the positive sum is concentrated in two outcomes. The candidate is not selected as robust.

For comparison, the unchanged frozen-edge baseline had validation -2.90R. The filter improved this one later segment but did not make development consistent. This is a watch-list hypothesis for a genuinely forward demo sample, not a proven live method.

## Limits

The validation period was inspected in prior analyses, so the +4.77R is not an independent untouched holdout. FBS tick-update volume is broker-specific; spread is included, commission and extra slippage are not.

Artifacts: `PROTOCOL.md`, `test_min_rr.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `trades.csv`.
