# Strict stable-center cluster test

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

The 50% half-profile VA-overlap gate passed almost every session, so it did not isolate a distinct balance. A stricter, structure-based cluster definition is that the older and recent three-hour profiles have the same POC row, in addition to overlapping value areas. Test whether freezing and trading only such a stable center changes results.

## Fixed rules

- Use FBS M1 tick_volume allocated by M1 OHLC price overlap into fixed $0.10 rows, six-hour window, 70% contiguous value area, and completed data only, per `m1_tick_volume_profile_2026-10-31/PROTOCOL.md`.
- Require 48 completed M5 bars in the six-hour window, >=24 M5 bars in each half, >=50% overlap of the narrower half VA, and identical older/recent-half POC price row. Freeze the combined six-hour levels at the first qualifying bar, maximum one cluster per session.
- Compare edge rotation to frozen POC against the same entry with executable >=2R target distance gate. Keep VAL/VAH touch/reclaim, wick stop, bid/ask replay, one evaluation per edge/session, one open position.
- Same 158 sessions; chronological 110 development / 48 validation / three development folds; candidate gate unchanged (>=20 dev trades, >=2 positive folds, positive validation R).

## Expectation

Exact POC agreement should reduce session clusters materially and focus the strategy on a persistent activity center. It may leave too few opportunities; no profit improvement is assumed.

## Limits

This is an FBS proxy, not OANDA. The value area row size is fixed at $0.10 and M1 OHLC allocation approximates update prices. Historical validation is partly inspected; bid/ask is included, commission and extra slippage excluded.
