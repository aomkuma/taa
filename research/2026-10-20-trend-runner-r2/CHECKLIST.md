# TREND-RUNNER Round 2 - execution checklist

Started: 2026-10-20 20:02 Thai time.

Legend: `[ ]` not started, `[~]` active, `[x]` complete, `[!]` failed/not permitted.

## 0. Isolation and governance

- [x] Create a new TR2 directory and write the plan before measurement.
- [x] Declare P1+P2 as seen design evidence, not new validation.
- [x] Keep the 2026-04-18 through 2026-10-17 exam locked.
- [x] Keep TR1 round 1 and all other setup/engine/config files read-only.
- [x] Record and verify hashes of immutable TR1 inputs.
- [x] Add automated import/path guards against exam and other setup-specific code.

## 1. Causal feature foundation

- [x] Write the frozen TR2 hypothesis before computing selector results.
- [x] Load M1 only through the P2 end with UTC checks.
- [x] Build completed H1/H4 bars independently inside TR2.
- [x] Implement H1/H4 flow, open-space and ATR-percentile features.
- [x] Join features to all 280 frozen entries without changing the entry population.
- [x] Implement shifted prior-session runner edge.
- [x] Add hand-worked no-look-ahead tests for every feature.
- [x] Add multiple real-data truncation checks.
- [x] Independently recompute the feature panel.

## 2. Adaptive selector

- [x] Implement monthly 90-day ridge refits with minimum 60 rows.
- [x] Fit scalers/imputation on training rows only.
- [x] Clip training targets and standardized features exactly as declared.
- [x] Choose RUNNER/FAST/SKIP from frozen thresholds.
- [x] Save monthly coefficients, predictions and action reasons.
- [x] Prove appending current/future outcomes cannot change an earlier decision.
- [x] Plant material leakage/refit/action bugs and catch all.

## 3. Design-only walk-forward

- [x] Run the primary selector once on the seen P1+P2 design span.
- [x] Compare against always FAST and always RUNNER on identical scored rows.
- [x] Run only the four predeclared neighbouring sensitivities.
- [x] Report R, USD, intervals, drawdown, streak and best-trade removals.
- [x] Report week, month, session, direction, action count and frequency.
- [x] Inspect monthly coefficients/action changes for instability.
- [!] Mark prototype FAIL against readiness gates; research only, not ready.

## 4. Forward boundary

- [x] Write the shadow feature/action schema without enabling orders.
- [x] Specify the future validation start, minimum duration and sample.
- [x] Confirm no exam file or tick day was opened.
- [x] Do not modify engine, DEMO, LIVE or portfolio integration.
- [x] Write a self-contained handoff.

## Checkpoints

### 2026-10-20 20:02 Thai - plan created

- TR1 round 1 remains immutable and failed only its strict promotion gate, not profitability.
- TR2 will test a causal adaptive selector over already-seen P1+P2 data.
- No selector result or exam data had been read when this plan was written.

### 2026-10-20 - TR2 completed

- Primary: 210 scored, 142 executed, +6.686R, +0.047R/trade, -$79.32 fixed 0.01 lot.
- Failed mean-R, best-trade-removal and concentration gates; always RUNNER was stronger on identical rows.
- Independent feature/truncation verification and all nine mutation checks passed.
- Status: research only, not ready; future shadow specification written but not connected to orders.
