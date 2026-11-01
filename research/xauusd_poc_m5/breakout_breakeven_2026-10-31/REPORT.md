# Break-even stop test after cluster breakout — Dukascopy XAUUSD M5

**Date:** 2026-10-31 (Asia/Bangkok)  
**Decision:** Moving the stop to entry after favorable movement did not repair regime transfer.

## Test

Use the confirmed two-M5-close breakout and next-M1 market entry setup. Keep the initial stop just inside the broken VA edge and target one VA width beyond it. When price first reaches +0.5R or +1.0R (bid for long, ask for short), move the stop to entry starting on the next M1 bar. If the entry stop and target can occur in the same M1 bar, use stop-first ordering. The no-move version is included as the baseline.

Same Dukascopy M1 bid/ask data and 158 covered sessions; same 110/48 chronological split. M1 OHLC ordering is unknown; no commission or additional slippage is included.

## Results

| Lookback / management | Development | Development folds | Validation |
|---|---:|---|---:|
| 6h, no BE move | 59 trades, -20.07R | -7.55 / -3.09 / -9.43R | 29 trades, -11.32R |
| 6h, move to BE at +0.5R | 59 trades, -15.24R | -8.02 / +1.54 / -8.76R | 29 trades, -7.33R |
| 6h, move to BE at +1R | 59 trades, -17.90R | -6.71 / -0.46 / -10.72R | 29 trades, -10.51R |
| 12h, no BE move | 41 trades, +20.72R | +5.81 / +2.98 / +11.93R | 21 trades, -12.54R |
| 12h, move to BE at +0.5R | 41 trades, -3.28R | -5.82 / +5.99 / -3.45R | 21 trades, -13.36R |
| 12h, move to BE at +1R | 41 trades, -4.59R | -3.53 / +3.97 / -5.02R | 21 trades, -17.56R |

The +0.5R break-even rule reduced the 6h validation loss, but all development folds did not turn positive and the total remained negative. It erased the 12h development profit and worsened validation. It therefore does not solve the breakout strategy's regime dependence.

## Files

`run_breakeven.py` generates `trade_outcomes.csv`, `summary.csv`, `development_folds.csv`, and `selection.csv`.
