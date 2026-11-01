# M5 close-through-value invalidation

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

An intrabar wick through VAL/VAH may be a liquidity sweep rather than acceptance. Test exiting a rotation only when a completed M5 bar closes outside the frozen value area. This matches the user's instruction to stop when the edge breaks, with a close-confirmed definition.

## Fixed comparison

- Use the FBS M1 tick-volume OHLC-overlap profile ($0.10 rows), six-hour window, frozen stable VA cluster and all eligibility rules from `m1_tick_volume_profile_2026-10-31/PROTOCOL.md`.
- Same M5 edge touch/reclaim entry, frozen POC target, one edge attempt/session, and one-position rule.
- Wick-stop baseline: stop at signal wick plus spread pad.
- Close-break variant: planned risk boundary is VAL - spread pad for long / VAH + spread pad for short; ignore intrabar excursions, but exit at first executable quote after a completed M5 close beyond VAL (long) or VAH (short). Target remains checked tick-by-tick, so a target reached before the invalidating close wins. If neither happens, flatten at session end.
- Compare on the same 158 sessions, chronological 110/48 split and three folds. Selection rule unchanged.

## Expectation

Close confirmation should tolerate transient sweeps but can increase realized loss beyond planned risk. I expect fewer stop exits; net R may worsen if breakouts continue.

## Limits

FBS-Demo M1 proxy, not OANDA. M1 OHLC overlap approximates volume-at-price. Historical validation has been inspected; spread is included, commission and extra slippage excluded.
