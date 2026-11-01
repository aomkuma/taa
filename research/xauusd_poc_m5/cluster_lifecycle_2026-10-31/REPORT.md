# Cluster lifecycle and rejection-entry test

This follow-up changes the meaning of an active cluster. Once a cluster is detected, its VA and POC remain frozen until two consecutive M5 closes outside the frozen VA or the lookback-duration expiry. The edge order is allowed to remain active during that lifecycle. The rejection variant enters only after an M5 bar sweeps an edge and closes back inside the frozen VA, then uses the next M1 open and the signal wick for its stop.

## Results

| Lookback / setup | Development | Development folds | Validation |
|---|---:|---|---:|
| 6h edge limit, profile-extreme stop | 64 trades, -27.11R | -1.09, -11.54, -14.48R | 30 trades, -14.42R |
| 6h sweep/reclaim, wick stop | 43 trades, -28.35R | -10.88, -11.15, -6.32R | 19 trades, -7.10R |
| 12h edge limit, profile-extreme stop | 42 trades, -13.52R | -7.06, -1.60, -4.86R | 23 trades, -2.61R |
| 12h sweep/reclaim, wick stop | 24 trades, +2.23R | +0.88, -2.01, +3.36R | 16 trades, -9.13R |

No setup passes the existing rule (>=20 development trades, >=2 positive development folds, and positive validation net R). The 12h sweep/reclaim setup is a development-only signal that fails validation sharply; it is not selected.

## Execution assumptions and files

Uses Dukascopy M1 bid/ask OHLCV and the same 158 covered sessions as the FBS study. Orders/targets/stops are replayed from M1 OHLC with adverse ordering when stop and target can both occur within a minute. Commission, queue position, latency and extra slippage are not included. The independent cross-feed report is in `../dukascopy_crossfeed_2026-10-31/REPORT.md`.

`run_lifecycle.py` generates `trades.csv`, `session_audit.csv`, `summary.csv`, `development_folds.csv`, and `selection.csv`.
