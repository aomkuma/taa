# Stable six-hour volume cluster test

**Status:** preregistered before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

The prior 3h high/low overlap filter was too permissive. A local price cluster should show overlap in the **volume-profile value areas** of the older and newer halves of the six-hour window. Freeze the combined six-hour profile once that state appears, so levels do not drift while trading.

## Formation and profile

- Use only tick midpoint updates in the six-hour interval before each candidate M5 bar opens; maximum 72 M5 bars.
- Split this lookback into older and newer three-hour halves. Require at least 24 active M5 bars in each half with quote activity.
- Compute separate $0.10-bin quote-count profiles for each half and for the combined six hours, using the established contiguous 70% value-area algorithm.
- A cluster forms when the two half-window VA ranges overlap by at least 50% of the narrower VA width. Freeze combined-window VAL, POC, VAH, zone and spread buffer at the first qualifying bar in each broker session. At most one cluster can form per session; expiry is after 72 M5 bars.

## Trade variants

- **Rotation:** inside the frozen cluster, buy a VAL rejection and target frozen POC; sell a VAH rejection and target frozen POC. Stop beyond signal-bar wick by the frozen spread buffer. One trade per edge per cluster.
- **Rotation + breakout:** same rotations. After two consecutive M5 closes beyond a frozen edge, disable further rotations. A retest must touch the broken boundary zone and close on the breakout side within six M5 bars. Enter after that close, stop beyond the retest wick by buffer, and target one frozen VA width beyond the broken edge. One breakout trade per cluster.

Require complete current and previous session quote coverage; same 158 sessions and chronological 70/30 split as previous work. One position at a time. Skip bars that qualify at both edges. Bid/ask tick replay; no commission or extra slippage. No parameter search.

## Selection rule

A candidate needs at least 20 development trades, positive net R in at least 2 of 3 chronological development folds, and positive net R in validation. Otherwise select none.

## Expectation before reveal

Volume-based half-profile overlap should identify fewer, more stable clusters than raw price-range overlap. Freezing their edges should reduce repeated signals. Whether the rotation or breakout phase is profitable remains uncertain.

## Limits

Quote-update counts are a broker-specific activity proxy, not centralized executed XAUUSD volume. This is a historical and partly previously inspected dataset, not a fully blind holdout. Results exclude commission and extra slippage.
