# One-hour rotation time-stop result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, recorded before the run.  
**Sample:** 158 covered sessions (110 development, 48 validation).

The 12-bar time exit did not alter any trade: all entries still reached target, stop, or the session boundary before the cutoff. The two variants are identical, so the hypothesis had no eligible trades to affect.

| Period | Trades | Net points/oz | Net R |
|---|---:|---:|---:|
| development | 88 | +58.04 | +4.73 |
| validation | 58 | -53.50 | -5.79 |
| all | 146 | +4.54 | -1.06 |

Selection: no candidate. The baseline failed validation at -2.90R and only one development fold was positive. The 60-minute exit changed zero exit records, therefore it provides no improvement.

This confirms that the tested rotation trades generally resolve before one hour (or reach the session boundary). A time stop that long is redundant for this setup; the entry/stop logic remains the main issue.

Limits: same-data historical validation, broker-specific tick-update activity, and no commission/additional-slippage model.

Artifacts: `PROTOCOL.md`, `test_time_stop.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `trades.csv`.
