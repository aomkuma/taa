# TR2 handoff

## Outcome

TR2 is an isolated adaptive exit-selection research setup over the 280 frozen TR1 P1+P2 entries. It did not modify
TR1, PLAN-1, Setup OWN, engine configuration, DEMO, LIVE or database state. The locked historical exam was not read.

Primary 90-day/alpha-10 monthly walk-forward scored 210 opportunities and executed 142: 69 FAST, 73 RUNNER and 68
SKIP. It made +6.686R (0.047R/executed trade), but -$79.32 at fixed 0.01 lot. Always FAST made +3.353R and always
RUNNER +19.195R on the same 210 rows. Primary drawdown was 17.060R. Removing its best trade changes the total to
-9.738R. Status is `RESEARCH ONLY - NOT READY`.

The cash discrepancy is verified: stored USD equals R times initial price risk exactly. Fixed lot exposed more cash
risk on wide-stop losses. It is not an outcome-join error.

The 60-day sensitivity reached +0.166R/trade, but it is a predeclared diagnostic and cannot replace the failed
primary after inspection. Coefficients also show multiple sign changes over five refits.

## Audit state

- 11 unit/causal tests pass.
- Independent recomputation matches all 11 features on all 280 rows with maximum absolute error 0.
- Real-data truncation at 2025-12-15, 2026-02-16 and 2026-04-10 matches 93, 188 and 265 earlier rows exactly.
- Nine planted leakage/refit/preprocessing/action mutants are caught.
- Immutable R1 files are verified against `provenance.json` on every load.
- No exam, order-routing or engine path is imported by `r2`.

## Key artifacts

- `HYPOTHESIS.md`: frozen definitions and gates.
- `RESULTS.md` / `RESULTS.json`: result and gate decision.
- `feature_panel.parquet`: causal 280-row design panel.
- `predictions_primary.parquet`: first frozen primary measurement.
- `decisions_primary.parquet`: predictions plus explicit action reasons.
- `coefficients_primary.parquet` and `coefficient_stability.csv`: monthly models and stability audit.
- `sensitivities.csv`: only the four predeclared neighbours.
- `feature_verification.json`, `mutation_report.json`, `sizing_audit.json`: verification evidence.
- `SHADOW_SPEC.md`: future-only collection contract; not integrated.

## Reproduction

From the repository root, set `PYTHONPATH=research/2026-10-20-trend-runner-r2`, then run the tests,
`verify_features.py`, `mutation_checks.py`, and `audit_results.py`. `run_research.py` is the measurement command;
the primary result above is already recorded and should not be re-selected or replaced by a sensitivity.

## Next valid step

Do not tune this round further on P1/P2 and do not open the locked exam. If development continues, implement a
non-ordering shadow journal that conforms to `SHADOW_SPEC.md`, starting no earlier than 2026-10-21 UTC, and wait for
both 60 new trading days and 100 new opportunities before one evaluation.
