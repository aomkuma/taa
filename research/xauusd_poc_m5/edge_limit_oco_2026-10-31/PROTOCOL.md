# OCO limit entries at frozen VAL / VAH

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

The user's stated rule is to buy the lower profile edge and sell the upper edge. Prior tests waited for M5 close confirmation. This test places one OCO limit pair at frozen VAL/VAH and fills on an executable quote touch, then cancels the other side after the first fill.

## Rules

- Use corrected FBS M1 tick_volume OHLC-overlap profile, $0.10 bins, 70% VA, six-hour window split into 3h halves, >=50% half-VA overlap, >=24 completed M5 bars per half, 48 total, first cluster/session, frozen levels.
- After cluster formation, submit buy limit at VAL and sell limit at VAH. Long fills when ask <= VAL, at current ask (price improvement retained); short fills when bid >= VAH, at current bid. If both sides are touched in the same tick, skip that bar as ambiguous. First fill cancels the opposite order and consumes the cluster.
- Stop is beyond the touched frozen edge by the same profile median spread pad: VAL-pad for long, VAH+pad for short. Target is frozen POC. Replay subsequent bid/ask quotes tick by tick, one trade maximum/session.
- Orders expire at two consecutive M5 closes outside the cluster, 72 profile bars, or session end. No M5 rejection confirmation and no RR filter.
- Same 158 sessions; 110 development / 48 validation / three folds; selection needs >=20 development trades, positive net R in >=2 folds and positive validation net R.

## Expectation

Limit fills improve entry price but can fill while price is moving through the edge. OCO limits may increase opportunity count; whether boundary stops survive the move is uncertain.

## Limits

FBS-Demo, not OANDA. M1 OHLC allocation approximates price-level tick volume. Bid/ask quote fills are simulated, but passive order queue position/latency is not known. Validation has been inspected; commission and extra slippage excluded.
