# ATR stop width sensitivity — Dukascopy XAUUSD M5 clusters

**Date:** 2026-10-31 (Asia/Bangkok)  
**Decision:** No tested stop width produced a positive fold or validation result.

## Test

The entry time, side, fill and POC target were held fixed from the lifecycle edge-limit replay. Only the protective stop moved. Tested distances beyond VAL/VAH were the greater of a six-hour median-spread buffer and k × M5 ATR(14), where k = 0.00, 0.10, 0.20, 0.30, 0.50, 0.75, or 1.00. These were compared with the original stop beyond the full profile extreme. Stop/target fills were replayed on Dukascopy bid/ask M1 OHLC; if both could occur in a minute, the stop was taken first. A stop hit on the entry minute was counted immediately. Targets remained at frozen POC.

This isolates stop placement on the same passive entries; it does not test whether different exits would permit additional trades later in the same session. As in the parent run, the sample is 158 common covered sessions (110 development / 48 validation), and the validation block has been inspected in related research. Costs beyond bid/ask spread are excluded.

## Results

| Lookback / stop | Development | Fold 1 / 2 / 3 | Validation |
|---|---:|---|---:|
| 6h, 1.00 ATR | 64 trades, -41.08R | -4.28 / -10.87 / -25.92R | 30 trades, -20.02R |
| 6h, profile extreme | 64 trades, -27.11R | -1.09 / -11.54 / -14.48R | 30 trades, -14.42R |
| 12h, 1.00 ATR | 42 trades, -28.57R | -11.65 / -6.55 / -10.37R | 23 trades, -17.93R |
| 12h, 0.75 ATR | 42 trades, -28.68R | -13.10 / -7.39 / -8.19R | 23 trades, -17.31R |
| 12h, profile extreme | 42 trades, -13.52R | -7.06 / -1.60 / -4.86R | 23 trades, -2.61R |

Every ATR stop tested had negative results in all three development folds and negative validation. Wider stops reduced losses relative to very tight stops, but the full-profile stop remained the least negative. It still failed every fold and validation.

## Data-quality note

An initial calculation was discarded because Pandas 3 returned parsed trade times at microsecond resolution while quote timestamps were nanoseconds. The replay now explicitly converts trade timestamps to nanoseconds and aligns them to the correct M1 bid/ask rows. The reported outputs were generated after that correction.

## Files

- `run_atr_stops.py`
- `trade_outcomes.csv`
- `summary.csv`
- `development_folds.csv`
- `selection.csv`
