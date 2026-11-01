# POC-stable balance cluster rotation

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

VA overlap alone passed nearly every session, so it did not isolate a balanced cluster. A balance should also keep its center of activity from migrating. Add a POC stability test: older- and recent-half POCs must differ by no more than 10% of the narrower half-profile VA width. Then trade both frozen cluster edges back toward the frozen six-hour POC.

## Fixed rules

- Same ticks, $0.10 bins, 70% VA, 6h lookback split into two 3h halves, minimum 24 active M5 bars per half, >=50% overlap of the narrower half-profile VA, cluster freeze and maximum one cluster/session as in `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Additional cluster gate: `abs(recent_half_POC - older_half_POC) <= 0.10 * min(older_half_VA_width, recent_half_VA_width)`.
- At frozen cluster VAL, enter long on touch/reclaim; at VAH, enter short on touch/reclaim. Stop remains beyond signal-bar wick by the same spread pad. Target is frozen POC. One position at a time and one entry per edge per cluster.
- Same 158 sessions; chronological 110 development / 48 validation and three development folds. Selection requires >=20 development trades, positive net R in >=2/3 development folds, and positive validation net R.

## Expectation before reveal

The stricter center-stability gate should reduce eligible clusters and trades. It may avoid periods where the value area overlaps but its activity center is shifting. I do not expect the gate alone to guarantee an edge.

## Limits

Validation dates have appeared in prior research and are not blind. FBS quote updates are a broker activity proxy, not centralized executed volume. Bid/ask is included; commission and extra slippage are excluded.
