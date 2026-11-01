# Rolling six-hour M5 Volume Profile edge test

**Status:** protocol written before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Interpretation

A local price cluster is represented by a rolling six-hour Volume Profile. For each candidate M5 signal bar, calculate the profile from quote ticks in the preceding six clock hours, ending before that signal bar opens. The window can contain at most 72 completed M5 bars; a market-closure gap can make it contain fewer bars.

## Frozen rules

- Quote price is bid/ask midpoint. Assign each quote update to the nearest $0.10 price bin; counts are broker-specific activity, not centralized executed volume.
- POC is the bin with the greatest quote-update count. VAL/VAH enclose a contiguous range around POC containing at least 70% of quote updates, expanding toward the adjacent bin with more activity; ties expand lower first.
- Calculate rolling VAL/POC/VAH only from data before the candidate M5 bar opens (no current-bar profile lookahead).
- Touch zone is max($0.05, twice the median of per-M5-bar median spreads in the profile window). Buy VAL after an M5 touch and close above VAL; sell VAH after a touch and close below VAH.
- Entry is the first tick after the signal M5 bar closes (ask long, bid short). Target is the signal's rolling POC. Stop is beyond the signal bar's wick by max($0.05, the same rolling median spread).
- One position at a time; one VAL long and one VAH short at most per broker session. Skip simultaneous two-edge signals and invalid stop/target geometry.
- Replay quote ticks in time order. Require complete quote coverage for the current and previous broker sessions. Split valid sessions chronologically 70/30 and report both portions. No parameter sweep.

## Expectation before reveal

A recent six-hour profile should better reflect a local balance than a long 200-bar profile or the prior-day profile. I expect fewer late signals from stale levels; profitability is uncertain, especially after a sharp trend. This test does not add a separate trend or balance filter: the rolling value area itself defines the local activity cluster.

## Limits

FBS-Demo tick updates are not market-wide trade volume. The spread estimate is the median of bar-level median spreads, an approximation to the six-hour quote spread. Commission and extra slippage are excluded. This is an exploratory backtest, not a live-trading recommendation.
