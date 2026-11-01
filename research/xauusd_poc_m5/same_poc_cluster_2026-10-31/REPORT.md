# Exact POC-stability cluster result

**Date:** 2026-10-31 (Asia/Bangkok)  
**Protocol:** `PROTOCOL.md`, frozen before the run.  
**Profile:** FBS M1 tick_volume, $0.10 rows; execution FBS bid/ask ticks.  
**Sample:** 158 sessions, 110 development / 48 validation.

| Rule | Dev trades | Dev net R | Validation trades | Validation net R | Validation wins |
|---|---:|---:|---:|---:|---:|
| baseline | 10 | -6.84 | 4 | -4.09 | 0 |
| min_rr_2 | 4 | -4.20 | 2 | -2.05 | 0 |

The stricter same-POC rule reduced qualifying sessions to 22/158 and yielded only 14 baseline trades overall (4 validation). Baseline had -4.09R in validation and no winners there. The >=2R subset had two validation trades, both losses (-2.05R). Development baseline was negative in folds 2 and 3; no variant met selection.

## Decision

This test shows exact POC agreement makes the cluster detector more selective, but the eligible trades remain too sparse and negative to support adoption. The condition does not resolve the rotation failure.

This remains an FBS approximation, not the OANDA indicator. Quote-based fills include spread but omit commission and extra slippage. Validation dates were repeatedly inspected.

Artifacts: `PROTOCOL.md`, `test_same_poc.py`, `summary.csv`, `development_folds.csv`, `selection.csv`, `qualifying_profile_windows.csv`, `session_audit.csv`, `trades.csv`.
