# Next-bar confirmation plus minimum 2R to frozen POC

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

A touch/reclaim needs M5 follow-through, and a valid rejection should still have enough room to its frozen POC. Combine the next-bar range-break confirmation with a minimum attainable reward/risk of 2.0.

## Fixed rules

- Use the same frozen 6h/3h profile cluster, >=50% half-profile VA overlap, >=24 bars per half, first cluster per session, frozen VAL/POC/VAH, and one position/session as the stable cluster protocol.
- Signal bar must touch/reclaim VAL/VAH. The next M5 close must exceed the rejection bar high for a long or fall below its low for a short. Enter at first executable quote after confirmation close. Stop beyond the more extreme wick of the signal and confirmation bars by the original spread pad; target frozen POC.
- Require attainable entry-to-POC distance / entry-to-stop risk >=2.0 using executable ask/bid. Evaluate only the first confirmed setup at each edge per session; if it fails the RR gate, do not retry that edge.
- Compare against unchanged immediate touch/reclaim baseline on same 158 sessions, 110 development / 48 validation, three development folds. Selection requires >=20 development trades, positive net R in >=2/3 folds and positive validation net R.

## Expectation before reveal

The conjunction will likely reduce trade count sharply. It may improve entry quality and payoff geometry but can also enter too late or exclude winners. I expect the sample-size rule may fail.

## Limits

This is an exploratory combination after individual tests, so selection risk is higher. Historical validation has been inspected previously; it is not a blind holdout. FBS quote updates are broker-specific activity, bid/ask is included, but commission and extra slippage are excluded.
