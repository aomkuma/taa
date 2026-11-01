# POC edge strategy tuning protocol

**Status:** preregistered before parameter sweep
**Date:** 2026-10-31 (Asia/Bangkok)

## Scope

Tune only the VAL-long / VAH-short mean-reversion strategy. The direct POC-line entry is out of scope. Use local FBS-Demo XAUUSD quote ticks and M5 bars, prior completed session profile, $0.10 midpoint bins, 70% value area, POC target, and a stop beyond the signal/confirmation candle wick by max($0.05, one prior-session median spread). Entry/exit use ask/bid and tick replay; commission and extra slippage are unavailable and excluded.

## Fixed candidate grid

Touch zone stays max($0.05, 2 ? prior-session median spread). Test six combinations:

- Confirmation bars: 0 (current baseline) or 1 (next M5 bar must close inside the edge before entry).
- Acceptance handling: none; two consecutive closes outside the edge suspend fading it for the rest of the session; or two consecutive closes outside suspend fading until two consecutive closes back inside the edge.

This grid separates each proposed filter while also testing their combinations. No other threshold, target, bin width, stop, or direction changes.

## Time split and selection

- Use only sessions passing the existing complete-quote coverage rule.
- Sort covered sessions chronologically. First 70% is development; final 30% is later validation.
- Divide development sessions into three consecutive equal-size folds.
- A candidate is eligible only with at least 20 development trades and positive net R in at least 2 of 3 folds. Select the eligible candidate with the highest median fold mean R. If none qualify, select none. Exact ties prefer fewer trades; no manual override.
- Report every candidate on both development and validation, plus baseline. Do not tune against validation results.

## Pre-run expectation

I expect added confirmation and outside-edge handling to reduce the number of trades. Whether average R improves is uncertain; the prior short run showed that a permanent ban can also remove a later recovery. If no candidate meets the fixed selection rule, the data do not justify a tuned configuration.

## Limits

There are only about one year of tick quotes. The later validation slice overlaps dates whose baseline behavior was inspected in earlier short samples, so it is a temporal validation check but not a fully untouched blind holdout. Quote-update count is a broker-specific activity proxy, not centralized executed XAUUSD volume. The grid is small by design; repeated experimentation can still overfit.
