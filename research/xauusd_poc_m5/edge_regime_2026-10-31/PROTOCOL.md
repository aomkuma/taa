# Six-hour price-cluster and trend-regime comparison

**Status:** preregistered before calculating variant outcomes
**Date:** 2026-10-31 (Asia/Bangkok)

## Starting point

The prior rolling six-hour profile test lost money overall and triggered both edge entries on nearly every session. Test whether requiring a stable recent price cluster or aligning edge trades with the six-hour drift improves that result.

## Fixed data and entry rules

- Use the previously calculated rolling 6h tick-update Volume Profile, built before each signal bar opens, with $0.10 bins and a 70% value area.
- VAL long / VAH short only. Touch-and-close-back-inside entry; target rolling POC; stop past the signal bar wick by the rolling spread buffer. First tick after signal close; chronological bid/ask replay; one position at a time, one trade per edge per session.
- Require the current and previous broker sessions' quote coverage to pass the existing filter. Compare variants on the same 158 covered sessions. Split the first 70% (110 sessions) from the final 30% (48 sessions); divide development into three chronological folds.

## Frozen regime rules

1. **Baseline:** take either edge setup.
2. **Price-cluster fade:** allow edge setups only if the preceding 6h has at least 24 active M5 bars in each 3h half and the high/low ranges of the two halves overlap by at least 50% of the narrower half's range.
3. **Trend pullback:** allow VAL long only when the prior 6h net move is positive and `abs(net move) / sum(abs(M5 close changes)) >= 0.35`; allow VAH short only when the move is negative and meets the same threshold.
4. **Combined regime:** if the two 3h ranges meet the cluster condition, allow either edge fade; otherwise allow only the trend-aligned pullback above.

No new indicators, optimized thresholds, trade management changes, or POC-line entries.

## Evaluation rule

A variant is only considered a candidate if it has at least 20 development trades, positive net R in at least 2 of 3 development folds, and positive net R in validation. If none meet this rule, select none and test a different pre-registered hypothesis. Validation is not used to choose parameters.

## Expectation before reveal

The balance filter should reduce the frequent countertrend fades. Trend pullbacks may help in migrating profiles. I do not assume either will be profitable; the earlier six-hour baseline was negative.

## Limits

The price-cluster gate is a measurable approximation: overlapping 3h price ranges, not a universal definition of a cluster. Tick updates are broker-specific activity rather than centralized traded XAUUSD volume. Bid/ask spread is included, but commission and extra slippage are excluded. Some dates were examined in earlier analyses, so this is not a fully untouched holdout.
