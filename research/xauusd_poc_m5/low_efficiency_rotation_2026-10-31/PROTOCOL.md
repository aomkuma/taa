# Trade rotations only in a low-efficiency six-hour regime

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

VAL/VAH-to-POC rotation should work only when the recent six-hour path is non-directional. Gate each edge signal using six-hour close-to-close efficiency: absolute net close change divided by the sum of absolute close changes across completed M5 bars. Permit a rotation only at efficiency <=0.25.

## Fixed rules

- Same frozen profile cluster formation, touch/reclaim entry, signal-wick stop, frozen POC target, spread-aware tick replay, one position at a time and one entry per edge/session as `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Efficiency uses only completed M5 bars ending before the signal bar opens, within the same maximum six-hour profile window. It is recalculated at each signal. Zero total path is assigned efficiency 0.
- Compare ungated rotation with the single <=0.25 gate. No parameter sweep.
- Same 158 covered sessions, 110 development / 48 validation, three folds. Candidate needs >=20 development trades, positive net R in at least two folds, and positive validation net R.

## Expectation before reveal

Low efficiency should identify rotation and reduce trend-day fades, but can also exclude good reversals or admit noisy churn. I expect fewer entries and uncertain returns.

## Limits

The threshold is a conventional low-directionality cutoff but has not been tuned on this sample. Validation dates have been seen in prior analyses and are not blind. FBS tick updates proxy activity; bid/ask is included but commission and extra slippage are excluded.
