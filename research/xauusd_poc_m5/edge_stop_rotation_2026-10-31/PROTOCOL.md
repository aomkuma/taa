# Stop beyond frozen value-area edge

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

A stop at the rejection-candle wick can be hit while price remains near the frozen profile boundary. For edge-to-POC rotation, compare the original wick stop with invalidation beyond the frozen VAL/VAH edge.

## Fixed comparison

- Use the corrected FBS M1 tick-volume profile proxy and same six-hour stable-cluster formation, $0.10 rows, 70% VA, overlap >=50%, M5 coverage minimums, first qualifying cluster/session, VAL/VAH touch-reclaim entries, frozen POC target, bid/ask tick replay and one-position rule from `m1_tick_volume_profile_2026-10-31/PROTOCOL.md`.
- Wick-stop baseline: long stop = signal low - spread pad; short = signal high + spread pad.
- Edge-stop: long stop = min(signal low, frozen VAL) - spread pad; short = max(signal high, frozen VAH) + spread pad. This guarantees the stop is outside the frozen value edge and the signal wick.
- No reward/risk gate; compare only stop placement. Same 158 sessions, chronological 110/48 split, 3 development folds. Selection rule stays >=20 development trades, positive net R in >=2/3 folds, positive validation net R.

## Expectation before reveal

The edge stop may survive shallow boundary sweeps and reach POC more often, while increasing initial risk. Raw points could improve but net R may not.

## Limits

FBS-Demo, not OANDA; M1 OHLC overlap allocation approximates quote-update prices. Validation is historical and inspected. Bid/ask is included; commission and extra slippage are excluded.
