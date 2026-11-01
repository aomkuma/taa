# Minimum 2R distance to frozen POC

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

Some edge rejections have too little room to the frozen POC relative to the signal-wick stop. Accept a setup only when the attainable entry-to-POC distance is at least twice the planned entry-to-stop distance. This avoids taking geometrically poor rotations before outcomes are known.

## Fixed rules

- Same frozen cluster formation, immediate M5 touch/reclaim, frozen POC target, signal-wick stop, tick replay, and one position/session / one setup evaluation per edge as in `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Compare the unchanged immediate-entry baseline against the same setup with a minimum reward/risk ratio of 2.0, computed from the first executable quote after the signal: long uses ask-entry and bid stop/target; short uses bid-entry and ask stop/target.
- When the first setup at an edge fails the ratio gate, mark that edge evaluated for the session and do not try it again.
- Same 158 sessions; 110 development / 48 validation; three folds. Candidate requires >=20 development trades, positive net R in >=2/3 folds, and positive validation net R.

## Expectation before reveal

The gate should reduce trades and improve potential reward relative to planned risk, but it cannot improve entry direction by itself. I expect fewer losses per trade but an uncertain total and validation result.

## Limits

The historical validation period was inspected in prior experiments. Profile activity is the FBS quote-update proxy; bid/ask is included, while commission and extra slippage are excluded.
