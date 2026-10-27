# TR3 execution checklist

Legend: `[ ]` pending, `[~]` active, `[x]` complete, `[!]` failed gate.

## Governance

- [x] Create an isolated TR3 directory.
- [x] Write the plan before computing any R3 result.
- [x] Declare P1/P2/TR2 as seen development evidence.
- [x] Keep the historical exam locked.
- [x] Record and verify immutable input hashes.
- [x] Prove the package does not import TR1/TR2 strategy code or app/engine code.

## Model

- [x] Freeze the exact hypothesis before measurement.
- [x] Implement 60/90/120-day causal ridge components.
- [x] Implement median/disagreement score and majority-positive rule.
- [x] Remove FAST as an available action.
- [x] Save component predictions, reasons and monthly coefficients.
- [x] Add hand-worked preprocessing/action tests.
- [x] Prove current/future outcomes cannot change an earlier decision.
- [x] Catch material boundary, target, scaling, completion and ensemble mutants.

## Measurement

- [x] Run the primary exactly once on the seen panel.
- [x] Compare with always RUNNER on identical scored rows.
- [x] Run only four predeclared diagnostics.
- [x] Report robustness, concentration, action frequency and sizing.
- [x] Evaluate every development-readiness gate; all passed.

## Handoff

- [x] Confirm no engine/config/order path changed.
- [x] Write forward-only shadow contract.
- [x] Write self-contained results and handoff.

## Checkpoint

### Plan freeze

- R3 is a simpler RUNNER-or-SKIP ensemble intended to reduce TR2 coefficient and exit-choice instability.
- No R3 model output or performance result existed when this checkpoint was written.

### Completion

- Primary: 83/210 RUNNER actions, +17.702R, +0.213R/trade, 13.327R drawdown.
- Retained 92.2% of always-RUNNER total with 39.5% of its trades; all frozen development gates passed.
- Status is forward shadow candidate only. Bootstrap/concentration/coefficient warnings remain material.
