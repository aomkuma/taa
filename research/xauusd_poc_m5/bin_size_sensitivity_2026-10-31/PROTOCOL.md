# Profile row-size robustness check

**Status:** frozen before the additional row-size runs
**Date:** 2026-10-31 (Asia/Bangkok)

## Question

The method-corrected FBS M1 profile used $0.10 rows, but the user's custom OANDA indicator row size is unknown. Does the current profile-edge strategy's result depend on this arbitrary row width?

## Fixed comparison

- Keep the M1 tick-volume OHLC overlap allocation, 70% contiguous VA, six-hour lookback, 3h halves, >=50% VA overlap, first cluster/session, VAL/VAH rejection, frozen POC target, wick stop, bid/ask execution, and min executable RR=2 unchanged from `m1_tick_volume_profile_2026-10-31/PROTOCOL.md`.
- Compare row widths $0.01 (FBS symbol tick size), $0.10 (existing run), and $0.50. These are a sensitivity check, not a parameter search; do not select the best width from this sample.
- Same 158 sessions, chronological 110 development / 48 validation, and three development folds.

## Expectation

Smaller rows should create a noisier and more broker-dependent profile; larger rows should smooth the distribution and move POC/VA levels. I expect results to vary, and no width is presumed profitable.

## Limits

This remains FBS-Demo, not OANDA. The $0.50 width is a coarse robustness case, not a claim about the screenshot's settings. The later validation period has been repeatedly inspected and cannot establish a new winner.
