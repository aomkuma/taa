# Fixed ATR lock — earlier historical holdout

**Decision: NOT_PASS_RESEARCH_GATE**. The reserved 2026 exam interval was not opened. This test uses separate earlier XAUUSD M1 bars from 2021-09-01 through 2023-10-02, before this candidate's development cohort. These bars were used by other gold research in the workspace, so this is candidate-specific holdout history, not globally virgin data.

## Frozen rule

Block a RETEST-CONTINUATION entry only when the median percentile of causal ATR(14) on completed M15/M30/H1 bars is strictly above 80%. Each percentile ranks current ATR against the preceding 120 hours of ATR values, excluding current ATR. Evaluate at the actual re-entry entry timestamp; allow at or below 80%. No trailing outcome learning or parameter changes are used in this holdout.

## Holdout result

The earlier +30.96R source-stop ATR screen from the development journal measures volatility at the original stop, not at re-entry. It is therefore a different filter and must not be presented as the result of this actual-entry gate.

Source events generated: 887; eligible stopped-before-1R events: 474; completed candidate attempts: 94 across 85 entry days; censored candidate paths excluded: 0.
V1 baseline: +2.193R / 94 attempts; mean +0.023R; win rate 36.2%.
Fixed ATR lock: +2.325R / 91 attempts; mean +0.026R; win rate 36.3%; day-block 95% CI for mean [-0.245, +0.402]R.
Blocked completed counterfactuals: 3 attempts, -0.132R. Paired gate-minus-baseline mean delta per candidate attempt day-block 95% CI [-0.036, +0.033]R.

## Predeclared checks

- minimum 100 baseline and gate attempts with 60 days each: FAIL
- fixed gate mean positive in both halves: FAIL
- fixed gate day block 95ci lower above zero: FAIL
- paired increment day block 95ci lower above zero: FAIL

Chronological halves (split by completed candidate attempts):

- first_half: 45 gate trades; mean 0.10219128913367076
- second_half: 46 gate trades; mean -0.04942324482551213

Limitations: this is an M1 OHLC approximation, not tick replay. The period was not referenced by this candidate's development code but was used by other XAUUSD research in the workspace. Candidate outcomes are event-level, may overlap, include recorded spread, and omit slippage. Any positive result remains historical evidence and requires portfolio/concurrency and operational-parity review before promotion.
