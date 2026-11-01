# M1 tick-volume profile proxy aligned to TradingView methodology

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Why this revision

The earlier runs counted raw FBS quote records directly into price bins. TradingView documents that Forex/CFD Volume Profile uses tick volume (price updates) from lower-timeframe bars and distributes each lower-timeframe bar's volume across intersected price rows. This run uses FBS M1 `tick_volume` and allocates each minute's volume across $0.10 bins proportionally to the M1 OHLC range. It is closer to that method, but is still an FBS proxy and does not reproduce the user's OANDA chart or its unspecified row settings.

## Frozen rules

- At each M5 signal bar open, use completed M1 bars only from the preceding six clock hours; split into older/recent three-hour halves. Keep the same 158 covered sessions and cluster eligibility based on 48 active M5 bars overall / at least 24 M5 bars per half.
- Allocate each M1 bar's tick_volume across intersected $0.10 bins by price-range overlap; if high equals low, assign it to the containing bin. Use TradingView's documented 70% contiguous value-area procedure: start at the POC, add the larger adjacent row while it fits the remaining target, and use nearest-to-POC / above-row tie breaks. This leaves a different calculation from earlier raw-tick runs.
- Stable cluster: older/recent 3h VAs overlap >=50% of the narrower VA. Freeze the combined six-hour VAL/POC/VAH on its first qualifying M5 bar.
- Trade VAL touch/reclaim long or VAH touch/reclaim short, target frozen POC, stop past signal wick plus existing rolling FBS bid/ask spread pad. Use raw FBS bid/ask ticks for execution only.
- Compare baseline against minimum executable reward/risk >=2.0. One setup evaluation per edge/session; one open position at a time.
- Same chronological split and selection rule: >=20 development trades, positive net R in >=2/3 development folds, positive validation net R.

## Expectation before reveal

The M1 bar-based volume assignment will shift and smooth the profile relative to raw quote-price counts; the 2R candidate may change materially. I do not assume it will improve.

## Limits

FBS tick volume and spread differ from OANDA. $0.10 rows are a fixed research choice; the screenshot's custom indicator parameters are not fully specified. The validation period was inspected previously and is not blind. Commission and extra slippage are excluded.
