# TR3 handoff

## What changed

TR3 is a new isolated RUNNER-or-SKIP research setup. It responds to TR2's weaknesses by removing the losing FAST
choice, increasing ridge regularization, and combining 60/90/120-day predictions with an explicit disagreement
penalty. TR1, TR2 and all engine/config/order paths remain untouched.

## Result

The frozen primary scored 210 seen opportunities and selected 83 RUNNER trades:

- +17.702R total and +0.213R per executed trade;
- +$177.02 at constant $10 initial risk; +$16.27 at fixed 0.01 lot;
- 13.327R drawdown versus 20.241R for always RUNNER;
- retained 92.2% of always-RUNNER total R with 39.5% of the trades;
- +1.277R after removing the best trade, but -16.893R after removing the best three.

All ten predeclared development gates passed. Status is `FORWARD SHADOW CANDIDATE`, never promoted or independently
validated. The mean bootstrap interval is [-0.270R, +0.827R], February/March were negative, SELL was negative and
several coefficients changed sign. These are material warnings.

The four declared diagnostics were all profitable; none may replace the primary.

## Verification

- Immutable R2 feature/result artifacts are hash-verified on every load.
- The input feature panel already passed independent recomputation and three real-data truncation checks.
- Seven TR3 unit/causal/invariance tests pass.
- Eight mutation/proof checks pass.
- Current/future outcomes cannot change an earlier monthly decision.
- Actions are constrained to RUNNER/SKIP and normalized USD is exactly `10 * R`.
- No historical exam row is in the input panel; maximum entry time is 2026-04-17.

## Artifacts

- `PLAN.md`, `HYPOTHESIS.md`: pre-measurement frozen definitions.
- `RESULTS.md`, `RESULTS.json`: primary result and gates.
- `predictions_primary.parquet`: component predictions, score, reason and action.
- `coefficients_primary.parquet`, `coefficient_stability.csv`: all monthly component models.
- `diagnostics.csv`: only the four predeclared neighbours.
- `cut_*.csv`, `action_frequency.csv`: concentration and action audits.
- `mutation_report.json`: causal/model mutant evidence.
- `FORWARD_SHADOW.md`: future cold-start and evaluation contract.

## Next valid action

Do not tune R3 further on P1/P2 and do not use the historical exam. Begin a non-ordering cold-start journal with new
data. Since the old design sample is stale, wait until all three rolling components have 60 completed forward rows,
then collect both 60 scored trading days and 100 scored opportunities before the one-time forward evaluation.
