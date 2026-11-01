# Locked cluster rotation and breakout test

**Status:** preregistered before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

The rolling profile's edges follow price. A cluster may be more useful when its boundaries are frozen after price balances and invalidated when the market accepts beyond them. Test edge rotations inside the frozen cluster and a breakout retest after invalidation.

## Cluster formation and lifecycle

- Use the rolling six-hour tick-update profile computed before each M5 bar opens (same $0.10 bins, 70% VA, spread estimate as the existing study).
- A cluster qualifies when the previous 6h contains at least 24 active M5 bars in each 3h half and the high/low ranges of those halves overlap by at least 50% of the narrower range.
- On the first qualifying bar while no cluster is active, freeze that profile's VAL, POC, VAH, touch zone, and stop buffer. Keep it for at most 72 M5 bars.
- Inside the frozen cluster: VAL touch and close back above is a long toward frozen POC; VAH touch and close below is a short toward frozen POC. Stop beyond the signal bar wick plus the frozen spread buffer. At most one trade per edge per cluster.
- Two consecutive M5 closes above frozen VAH or below frozen VAL invalidate mean reversion. For the breakout version only, wait for a retest within the next six M5 bars: the bar must touch the broken edge zone and close on the breakout side. Enter after its close, stop beyond its wick plus buffer, target one frozen VA width beyond the broken edge. At most one breakout trade per cluster.
- Reset cluster state at each broker session. After a cluster expires or invalidates, allow a new cluster only after six bars of cooldown and a fresh qualification. One open trade at a time; skip bars that qualify at both edges.

## Variants

1. **Locked rotation:** cluster edge mean reversion only; after two closes outside, invalidate and stand aside.
2. **Locked rotation + breakout retest:** same rotation trades; after two closes outside, take the single retest breakout described above.

Compare with the existing rolling 6h profile baseline on the same 158 sessions. Split chronologically 70/30 and report first 3 development folds. No parameter sweep.

## Selection rule

A candidate must have at least 20 development trades, positive net R in at least 2 of 3 development folds, and positive net R in validation. Otherwise select none and move to a distinct hypothesis. Validation is not used to tune parameters.

## Expectation before reveal

Freezing edges should reduce repeated signals caused by moving boundaries. Breakout retests may capture days that no longer rotate through the cluster. Profitability remains uncertain.

## Limits

Cluster formation is approximated by overlapping 3h price ranges, not a universal definition. Tick updates are broker-specific activity rather than centralized trade volume. Bid/ask spread is included; commission and additional slippage are excluded. Some dates are not a fully blind holdout because earlier baseline studies examined them.
