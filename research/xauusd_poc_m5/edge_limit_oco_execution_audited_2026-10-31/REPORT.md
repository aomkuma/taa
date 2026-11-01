# Audited OCO limits at frozen VAL / VAH

## Result

The direct ?buy VAL / sell VAH? OCO rule did not show an edge on this FBS-Demo sample.

- Development: 110 trades, 2 targets, net **-65.57R**; folds: -26.17R, -11.37R, -28.04R.
- Validation: 48 trades, 1 target, net **-27.33R**.
- 69/158 entries (48 development, 21 validation) filled when the quote on the protective-stop side had already crossed the stop in the same tick. These are recorded as immediate stops, not discarded.

## Protocol and audit

See `PROTOCOL.md`. Profile: six-hour M1 tick-volume OHLC-overlap allocation, $0.10 rows, 70% value area; one first qualifying cluster per session. Orders are buy limit at frozen VAL and sell limit at frozen VAH, with the opposite canceled after the first fill. Stop is at least 2 x median spread + $0.10 outside the edge; target is frozen POC. Quote-side stop/target fills use bid/ask ticks. R uses planned limit-to-stop distance. A bar's fills are processed before two-close invalidation at that bar's close.

## Interpretation

Most fills were edge penetrations that kept going through the protective stop, rather than reversals to POC. The direct boundary-touch rule therefore fails on this data. This is an FBS proxy, not the OANDA feed in the screenshot; costs beyond spread and passive-order queue priority are excluded. Historical validation is not pristine after related experiments.
