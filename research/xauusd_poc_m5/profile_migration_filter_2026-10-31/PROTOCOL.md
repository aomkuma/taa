# Profile-migration direction filter

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

A stable overlapping value area can still have directional migration inside it. Fading both edges may therefore trade against the developing direction. Test whether allowing only VAL longs when the recent-half POC is above the older-half POC, and only VAH shorts when it is below, improves frozen-cluster rotation.

## Fixed rules

- Use the exact 6h rolling tick-update profiles, 3h older/recent halves, >=50% VA overlap, >=24 active M5 bars per half, cluster freeze, touch/reclaim entry, wick stop, frozen POC target, quote replay, and one-position/session rules from `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Direction is determined at cluster formation from recent-half POC minus older-half POC. Positive permits VAL-long only; negative permits VAH-short only; equal POCs permit no trades. Do not update the direction after formation.
- Compare against the unfiltered frozen rotation on the same sessions. No parameter sweep.
- Selection requires >=20 development trades, positive net R in >=2/3 development folds, and positive validation net R.

## Expectation before reveal

The filter should lower trade count and may reduce losses from fading a migrating profile, but it can exclude valid reversals. I expect uncertain results; the filter is not assumed profitable.

## Limits

The same-data validation segment was inspected in prior experiments and is not blind. FBS quote updates are broker-specific activity, not centralized traded volume. Bid/ask is included; commission and extra slippage are excluded.
