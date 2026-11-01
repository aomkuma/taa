# M1 tick-volume profile: rotation versus breakout retest

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

At a recent stable profile cluster, fade a value edge only while price remains accepted inside value. After two M5 closes outside a frozen edge, switch to a breakout retest instead of continuing to fade. Compare this adaptive playbook with rotation-only.

## Profile construction

Use the M1 tick_volume OHLC-overlap proxy in `m1_tick_volume_profile_2026-10-31/PROTOCOL.md`: $0.10 rows, six-hour window split into two three-hour halves, contiguous 70% value area, and >=50% overlap of the narrower half VA. Require 48 completed M5 bars in the full profile and 24 per half. Freeze the first qualifying profile each session.

## Trade rules

- Both variants: while in rotation state, buy frozen VAL touch/reclaim toward frozen POC; sell frozen VAH touch/reject toward frozen POC. Use signal wick plus existing spread pad, first quote after M5 close, one position at a time, one entry per edge.
- Rotation-only: two consecutive closes outside either edge terminate that cluster; no breakout trade.
- Adaptive variant: after two consecutive closes outside, disable further rotations and wait at most six M5 bars. An upward break retest is a touch of VAH zone that closes above VAH; enter long, stop past retest wick, target VAH + frozen VA width. Mirror for downward break / VAL retest, target VAL - frozen VA width. One breakout attempt; no new cluster that session.
- Replay FBS bid/ask ticks. No extra RR gate.

## Evaluation

Same 158 covered sessions, 110 development / 48 validation and three chronological development folds. Require >=20 development trades, positive net R in at least two folds, and positive validation net R. No parameter search.

## Expectation

The regime switch may avoid fading accepted breakouts but could enter late and take losses on failed retests. I expect fewer trades than rotation plus breakout from the raw-tick profile; profitability is uncertain.

## Limits

This is FBS-Demo M1 tick_volume, not OANDA. M1 OHLC overlap is an approximation to each update's traded price, $0.10 rows are a chosen sensitivity, and the later validation block is previously inspected. Spread is replayed; commission and extra slippage are excluded.
