# OCO only after prior M5 close is inside value

## Result

The gate reduced executions but did not produce positive expectancy.

- Development: 68 trades, 2 targets, net **-49.56R**; folds: -19.03R, -6.55R, -23.98R.
- Validation: 31 trades, 3 targets, net **-13.93R**.
- Immediate stop-at-fill cases: 2 in development, 0 in validation.

The prior completed M5 close was required to be inside the frozen VA before the current bar's OCO touch could fill. It was known at bar open, so there is no same-bar look-ahead. The rest of the audited OCO method is in `../edge_limit_oco_execution_audited_2026-10-31/PROTOCOL.md`. The filter helps versus the audited unrestricted OCO in validation, but loses in development and all folds.
