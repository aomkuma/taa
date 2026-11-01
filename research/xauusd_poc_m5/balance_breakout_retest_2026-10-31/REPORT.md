# Balance-cluster breakout retest — Dukascopy XAUUSD M5

**Date:** 2026-10-31 (Asia/Bangkok)  
**Decision:** No candidate; both tested lookbacks were negative in validation and inconsistent across development folds.

## Hypothesis

A stable, overlapping value area may mark balance. If price then closes outside VAL/VAH on two consecutive M5 bars, a retest of the broken edge may support continuation. This switches from fading the VA edge to entering in the direction of a confirmed breakout.

## Rules

- Use the first qualifying profile cluster per session at either 6h or 12h lookback: overlapping older/recent 70% VAs >=0.50, half POCs <=$0.50 apart, lookback efficiency <=0.25, and prior close inside full-window VA.
- Freeze VAL, POC and VAH at formation.
- Wait for two consecutive M5 closes above VAH or below VAL.
- After the second close, place a passive retest limit at the broken edge: buy VAH after an upside break; sell VAL after a downside break.
- Stop at the opposite value-area edge. Target one value-area width beyond the breakout edge, producing approximately 1R before spread/gap effects.
- Replay using Dukascopy M1 bid/ask candles. Stops are checked first when both stop and target could trade in a minute; entry-minute target is not credited. One breakout attempt per session; unfilled retests are not counted as trades.

## Results

| Lookback | Development | Fold 1 / 2 / 3 | Validation |
|---|---:|---|---:|
| 6h | 52 trades, -7.39R | +0.84 / -0.38 / -7.85R | 28 trades, -3.54R |
| 12h | 38 trades, -3.93R | +5.56 / -4.40 / -5.09R | 23 trades, -7.01R |

The higher win rate did not overcome losses: 6h won 46.2% in both development and validation; 12h validation won 34.8%. The 6h and 12h versions each had only one positive development fold, and both validations were negative.

## Limits and files

The same 158 covered sessions and chronological split are reused; validation is no longer a pristine holdout. Dukascopy is a secondary source, not the OANDA feed shown in the chart. M1 OHLC cannot establish exact intraminute ordering; the adverse stop-first assumption is used. Commission and slippage beyond the recorded spread are excluded.

`run_breakout_retest.py` creates `trades.csv`, `session_audit.csv`, `summary.csv`, `development_folds.csv`, and `selection.csv`.
