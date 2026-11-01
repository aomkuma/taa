# One-bar rejection confirmation at a frozen profile edge

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

A touch-and-close-back inside VAL/VAH can still be a weak rejection. Require the next M5 bar to close beyond the rejection bar's high (long) or low (short) before entering. This tests whether follow-through confirmation improves the frozen-cluster edge rotation.

## Fixed rules

- Use the exact 6h rolling profiles, two 3h halves, >=50% half-profile VA overlap, >=24 active bars per half, freeze-at-first-qualifying cluster, VAL-long/VAH-short, frozen POC target, one position and one trade per edge/session from `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Compare immediate touch/reclaim entry against next-bar close confirmation: long requires next close > prior rejection bar high; short requires next close < prior rejection bar low. Entry uses the first quote after that close. Stop is beyond the more extreme wick of the rejection and confirmation bars by the original spread pad. Target remains frozen POC.
- Same 158 sessions, 110 development / 48 validation, three folds. Candidate requires >=20 development trades, positive net R in >=2/3 folds, and positive validation net R.

## Expectation before reveal

Confirmation should remove some weak rejections but enter later and worsen the price. I expect fewer trades; whether the better follow-through compensates for the worse entry is uncertain.

## Limits

Validation is historical and previously inspected. The profile counts FBS quote updates, not centralized executed XAUUSD volume. Bid/ask is replayed; commission and extra slippage are excluded.
