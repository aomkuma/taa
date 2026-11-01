# One-hour rotation time stop

**Status:** frozen before outcome calculation
**Date:** 2026-10-31 (Asia/Bangkok)

## Hypothesis

If an edge-to-POC rotation does not happen within one hour, the setup may have failed or become stale. Test a 12-completed-M5-bar time exit while keeping cluster formation, entry, stop, target, quote fills and all other rules fixed. Compare with the unchanged no-timeout baseline.

## Fixed rules

- Use the exact frozen 6h profile cluster and VAL-long / VAH-short rotation rules, including POC target and signal-wick stop, from `stable_profile_clusters_2026-10-31/PROTOCOL.md`.
- Compare holding until target/stop/session end against closing at the last available quote after 12 completed M5 bars if neither target nor stop has occurred.
- No parameter sweep. Keep one position open at a time; later signals may occur after the changed exit time.
- Same 158 sessions, 110 development, 48 validation, and three development folds. Selection requires >=20 development trades, positive net R in >=2/3 folds and positive validation net R.

## Expectation before reveal

The time stop should cut some full-stop losses but may also close eventual POC winners early. I expect a lower average loss and lower target rate; profitability is uncertain.

## Limits

Validation dates have been inspected in prior research. Quote updates are FBS broker activity, not centralized executed volume. Spread is included; commission and extra slippage are excluded.
