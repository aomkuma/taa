# OCO in stationary value clusters

## Corrected result

The cluster is activated only at the first bar where all conditions are simultaneously true: base six-hour VA overlap, prior M5 close inside VA, efficiency <=0.25, and older/recent-half POCs within $0.50. Levels are frozen at that point.

- Development: 32 trades, 2 targets, net **-22.44R**; folds: -14.52R, -4.15R, -3.77R.
- Validation: 22 trades, 4 targets, net **+10.95R**; PF on points 1.46 and PF on planned-risk R 1.58.
- The validation winners cluster in June development and October validation; all targets in validation came in October 2026. This concentration and negative development folds indicate regime dependence, not a robust candidate.

The positive validation block is insufficient evidence because it is only 22 trades, fails development consistency, and has been inspected in this related research. Execution and data limits are in `PROTOCOL.md`.

## Superseded diagnostic

`premature_activation_diagnostic/` preserves the first implementation, which froze levels before the POC-stability condition occurred. Its 1 development / 5 validation fills (+4.98R validation) are invalid for inference and explicitly superseded.
