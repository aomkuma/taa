# Stable profile-cluster test result

**Run date:** 2026-10-31 (Asia/Bangkok)
**Protocol:** `PROTOCOL.md`, recorded before this run
**Sample:** same 158 covered sessions, 110 development and 48 validation.

## Result

| Variant | Dev trades | Dev net R | Validation trades | Validation net R | Validation points/oz | All trades | All points/oz |
|---|---:|---:|---:|---:|---:|---:|---:|
| Frozen cluster rotation to POC | 44 | +2.37 | 29 | -2.90 | -26.75 | 73 | +2.27 |
| Frozen rotation plus breakout retest | 95 | -11.82 | 52 | -5.76 | -0.68 | 147 | +25.50 |

Neither variant met the preregistered rule. Rotation was nearly flat by price points over the full sample but lost in validation and had positive net R in only one of three development folds. Adding breakouts raised the number of trades and points, but net R remained negative in both development and validation.

The profile half-VA overlap detector created a frozen cluster in every covered session, so it did not filter out entire days. It did reduce actual rotation trades to 73 across the full sample. The cluster definition is more selective than high/low overlap, but the trades still do not show repeatable positive risk-adjusted returns.

## Interpretation

This is not a winning method yet. The POC target is close enough to produce a near-flat raw point result in-sample, but validation losses and negative net R do not support selecting it. The breakout addition does not solve the risk-adjusted performance issue.

Volume Profile's POC is the highest-activity price row and its VA is a specified share of profile activity; TradingView notes Forex/CFD profiles may rely on tick-volume price updates ([reference](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/)). This local FBS quote-update profile remains broker-specific, not centralized XAUUSD volume.

## Next check

Compare the two natural rotation exits?frozen POC versus the opposite frozen VA edge?without changing entries or stops. This is a separate target-sensitivity test, not a selected rule.

## Files

- `PROTOCOL.md`: frozen cluster logic and entry/exit rules
- `test_stable_profile.py`: profile construction and replay
- `summary.csv`, `development_folds.csv`, `selection.csv`: results
- `trades.csv`: accepted trades
- `qualifying_profile_windows.csv`: qualifying half-profile overlap states
- `cluster_starts.csv`, `session_cluster_counts.csv`: cluster audit
