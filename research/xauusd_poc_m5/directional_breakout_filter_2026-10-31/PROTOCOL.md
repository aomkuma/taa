# Directional regime gate for a frozen-cluster breakout retest

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

A two-close acceptance outside a frozen value edge followed by a retest may still fail in a non-directional market. Permit the breakout-retest entry only if the completed six-hour M5 path efficiency is >=0.35 and the six-hour net close direction matches the breakout direction. This applies a directional regime condition to breakout retests, not to rotation fades.

## Fixed rules

- Use the exact stable half-profile cluster, frozen VA boundaries, two consecutive closes outside, retest within six M5 bars, breakout target at one frozen VA width, wick stop, quote replay, one position and session handling from `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Compare the unchanged breakout-retest version against the single regime-gated version. Gate is measured at the retest signal using only completed M5 bars in the preceding six-hour window (no more than 72 bars): `abs(last close - first close) / sum(abs(close-to-close change)) >= 0.35`, and the net close change sign must equal breakout direction.
- Same 158 covered sessions; 110 development / 48 validation; three development folds. Candidate requires >=20 development trades, positive net R in >=2/3 folds and positive validation net R.

## Expectation before reveal

The regime gate should remove some false breakouts in chop but may enter too late or remove valid early turns. I expect fewer trades and uncertain returns.

## Limits

The historical validation period is partly inspected. This is an exploratory conditional test. FBS quote updates are a broker proxy; spread is included but commission and extra slippage are excluded.
