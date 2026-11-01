# OCO limits with audited quote-side stops

**Status:** exploratory execution audit; the historical validation block has been reused in prior experiments and is not a fresh holdout.
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis and rule

Test the user's direct boundary rule: buy a frozen six-hour VAL and sell a frozen six-hour VAH with an OCO pair. Use the FBS M1 tick-volume profile, $0.10 bins, price-range overlap allocation, 70% contiguous value area, two three-hour halves, and at least 50% overlap between the halves. Require 48 completed M5 bars total and at least 24 per half. Use one first qualifying cluster per session and at most one fill.

Place the OCO at the first qualifying profile bar open. A buy limit fills on ask <= VAL; a sell limit fills on bid >= VAH; use the executable quote as the fill, allowing price improvement. Cancel the opposite side after the first fill. Stop sits outside the frozen edge by 2 x the six-hour median spread + $0.10. Target is the frozen POC. Replay subsequent bid/ask ticks; if the executable stop quote is already crossed at the entry tick, record an immediate stop. Normalize R to the stop distance from the planned limit price, so price improvement cannot shrink the risk denominator. Orders expire after two consecutive M5 closes outside the frozen VA, after 72 profile bars, or at session end. Process a bar's quote touches before its close can invalidate orders.

Sample: 158 covered sessions; first 110 chronological sessions for development and last 48 for validation; three development folds. A candidate would need >=20 development trades, positive net R in at least two folds, and positive validation net R.

## Limits

FBS-Demo, not OANDA. M1 tick volume is broker-specific and the OHLC price-row allocation approximates TradingView's profile. This is one historical broker feed; validation is not pristine due to prior related experiments. Commission, queue position, latency and extra slippage are excluded. This is research, not a live-trading recommendation.
