# Balance-cluster breakout close entry — Dukascopy XAUUSD M5

**Date:** 2026-10-31 (Asia/Bangkok)  
**Decision:** No candidate; 12h looked strong in development but reversed in validation.

## Rule

Use the first cluster in each session from the established profile filter: older/recent 70% VA overlap >=0.50, half POC shift <=$0.50, path efficiency <=0.25, and the prior close inside value. Freeze VAL, POC and VAH. A breakout is confirmed by two consecutive M5 closes beyond one edge. Enter at the first M1 ask/bid open after the second M5 bar closes. The stop is just back inside the broken edge, buffered by twice the prior-hour median spread plus $0.10. Target is one VA width beyond the breakout edge. Skip if the next-minute open is already back inside VA or beyond target.

The comparison setup from the companion report waits for a retest of the broken edge and uses the opposite VA boundary as stop. Both use the same cluster definition, 158-session chronological split, and Dukascopy M1 bid/ask OHLC replay. Stops are processed before targets if both could occur within one minute. Extra slippage and commission are excluded.

## Results

| Lookback / entry | Development | Development folds | Validation |
|---|---:|---|---:|
| 6h market after confirmation | 59 trades, -20.07R | -7.55 / -3.09 / -9.43R | 29 trades, -11.32R |
| 12h market after confirmation | 41 trades, +20.72R | +5.81 / +2.98 / +11.93R | 21 trades, -12.54R |
| 6h breakout retest | 52 trades, -7.39R | +0.84 / -0.38 / -7.85R | 28 trades, -3.54R |
| 12h breakout retest | 38 trades, -3.93R | +5.56 / -4.40 / -5.09R | 23 trades, -7.01R |

12h market entry had 3 winners and 18 stops in validation, despite positive development in every fold. A diagnostic trend-alignment filter reduced validation loss to -9.25R across 18 trades but did not reverse it. Requiring the close to clear the broken VA edge by at least 0.10 ATR reduced validation loss to -8.87R across 18 trades, but development results fell to +17.25R and the stricter 0.25 ATR threshold turned development negative. These filters were post-hoc and are not candidates. This is strong evidence that the apparent development edge is tied to the earlier regime and does not transfer to the later block. The diagnostic script and per-trade distances are in `../breakout_strength_diagnostic_2026-10-31/`.

## Files

`run_close_entry.py` generates `trades.csv`, `session_audit.csv`, `summary.csv`, `development_folds.csv`, and `selection.csv`. Breakout-ret-test details are in `../balance_breakout_retest_2026-10-31/REPORT.md`.

