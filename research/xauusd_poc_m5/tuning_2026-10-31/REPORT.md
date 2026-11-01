# XAUUSD VAL/VAH tuning result

**Run date:** 2026-10-31 (Asia/Bangkok)
**Protocol:** see `PROTOCOL.md`; written before the parameter sweep
**Data:** FBS-Demo XAUUSD M5 and bid/ask ticks; 159 sessions passed coverage

## Split and selection

The chronological split used the first 111 covered sessions (2025-10-07 through 2026-07-08 UTC) for development and the final 48 sessions (2026-07-09 through 2026-10-26 UTC) for later validation. The development interval was divided into three consecutive folds. All 6 configurations had negative net R in all 3 development folds, so none met the preregistered rule (at least 20 development trades and positive net R in at least 2 folds). **No tuned configuration was selected.**

## Results by configuration

Net R sizes each trade to its initial stop risk. Price P&L uses one ounce as a reporting unit and includes bid/ask spread; commission and extra slippage are excluded.

| Configuration | Development trades | Development net R | Validation trades | Validation net R | Validation net price points/oz |
|---|---:|---:|---:|---:|---:|
| Baseline: no confirmation, no outside filter | 124 | -41.48 | 64 | +17.03 | +47.72 |
| 1-bar confirmation, no outside filter | 120 | -64.50 | 61 | +14.37 | +20.13 |
| No confirmation, permanent ban after 2 closes outside | 77 | -37.02 | 36 | -4.09 | +14.83 |
| 1-bar confirmation, permanent ban | 61 | -31.92 | 25 | +11.73 | +47.91 |
| No confirmation, re-enable after 2 closes inside | 116 | -40.97 | 64 | +9.26 | +17.39 |
| 1-bar confirmation, temporary suspension | 110 | -46.84 | 58 | +5.24 | +35.59 |

The later segment is positive for several configurations, but the same parameter choices were consistently negative across the three earlier development folds. Choosing one based on the final segment would violate the preregistered selection rule. Also, some late dates overlap prior short samples, so this is not a fully blind holdout.

## Conclusion

There is no evidence in this run for a stable parameter adjustment. The filters reduce some losing entries but also change which recoveries are captured; no tested version produced positive results consistently across development periods. Keep the rule set unselected rather than adopting a configuration based on the late segment. A genuinely forward sample with frozen rules is needed to decide whether any variant is useful.

This remains an exploratory backtest: quote-update activity is a broker-specific proxy, not centralized XAUUSD traded volume. The results do not include commission or additional slippage.

## Files

- `PROTOCOL.md`: frozen test plan and selection rule
- `tune_edges.py`: reproducible six-configuration walk-forward sweep
- `summary.csv`: development and validation totals by configuration
- `development_folds.csv`: development results by fold
- `selection.csv`, `selected_config.txt`: selection decision
- `trades_all_configs.csv`: trade log for all variants
- `daily_levels.csv`, `session_coverage.csv`: profiles and coverage
