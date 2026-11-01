# Prior-session value-area cluster filter

**Status:** preregistered before calculating outcomes
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

VAL-long / VAH-short mean reversion may work better when the market has accepted overlapping value ranges in consecutive sessions (a price cluster) than when value is migrating. Test this as one filter; no parameter sweep.

## Operational definition

For session N, use completed active sessions N-1 and N-2 only. A cluster exists if their 70% Value Areas overlap by at least 50% of the narrower area's width:

`overlap = max(0, min(VAH1, VAH2) - max(VAL1, VAL2))`

`cluster_ratio = overlap / min(VAH1 - VAL1, VAH2 - VAL2)`

Trade in session N only when `cluster_ratio >= 0.50`. The profiles use midpoint quote-update counts in $0.10 bins. Require complete tick coverage for N, N-1 and N-2; compare filtered and unfiltered versions on exactly the same eligible sessions.

## Entry and risk rules

- Buy VAL after an M5 touch of the edge zone and close back above VAL; sell VAH after touch and close back below VAH.
- Edge zone remains max($0.05, 2 ? prior-session median spread). Target is the prior-session POC.
- Stop remains beyond the signal-bar wick by max($0.05, one prior-session median spread).
- First quote after signal close is the entry (ask long, bid short); replay quotes chronologically. One open trade at a time; at most one entry per edge per session.
- No direct POC-line trades, added confirmation bars, trend filter, or other tuning.

## Evaluation

Use all sessions passing the shared three-session completeness requirement, sorted chronologically. Report baseline and cluster-filtered outcomes on the identical dates, separately for first 70% and final 30%. This is a single hypothesis comparison, not a parameter search. No configuration will be selected based only on the final segment.

## Expectation before reveal

I expect the cluster filter to reduce trade count. It may improve mean R by excluding value migration, but the direction and size of any effect are uncertain.

## Limits

The filtered sample may be small. The validation period is historical and not fully blind because earlier work inspected parts of the same data. Quote-update count is broker-specific activity, not centralized executed XAUUSD volume. P&L includes spread via bid/ask fills but excludes commission and extra slippage.
