# TR2 design-only result

Status: **RESEARCH ONLY - NOT READY**. NOT PROMOTED; historical exam remains locked.

P1 and P2 are already-seen design evidence. The locked 2026-04-18 through 2026-10-17 exam was not read.

## Primary result

- Scored 210 opportunities; executed 142.
- Actions: {'RUNNER': 73, 'FAST': 69, 'SKIP': 68}.
- Total 6.686R / $-79.32 at 0.01 lot.
- Mean 0.047R per executed trade; bootstrap 95% interval [-0.272, 0.432].
- Max drawdown 17.060R; maximum losing streak 8.
- After removing best one: -9.738R; best three: -27.908R.

## Same-row baselines

- Always FAST: 3.353R, 0.016R/trade, DD 17.304R.
- Always RUNNER: 19.195R, 0.091R/trade, DD 20.241R.

The adaptive primary beat always FAST in total R but did not beat always RUNNER. Within the primary, the 73 RUNNER
choices made +21.617R while the 69 FAST choices lost -14.931R. This is not evidence that the selector is reliably
identifying the better exit.

## Fixed-lot sizing audit

The positive R and negative USD results are consistent, not a join error. Every selected row satisfies
`USD = R * initial price risk` exactly (maximum error 0). R normalizes each trade by its stop distance, whereas a
fixed 0.01 lot does not. Losing trades had mean initial price risk 7.798 versus 6.959 for winners, producing -$79.32
despite +6.686R. A risk-sized implementation would be needed for R and cash performance to align, but none was
enabled or tested here.

## Sensitivity and stability

The predeclared 60-day sensitivity was strongest at +22.963R and +0.166R/trade, but it also had 18.778R drawdown.
It cannot replace the frozen 90-day primary after observing results. The other sensitivity totals were +11.260R
(alpha 5), +5.229R (alpha 20) and +4.921R (120 days).

Several standardized coefficients changed sign across only five monthly refits. FAST pullback ratio and both model
intercepts changed sign twice; RUNNER H1 flow also changed sign twice. This supports keeping TR2 in research rather
than treating the current action mapping as stable.

## Prototype gates

- PASS: at_least_100_scored
- PASS: at_least_60_executed
- FAIL: mean_r_at_least_0_15
- FAIL: non_negative_without_best_trade
- PASS: drawdown_no_worse_than_always_runner
- FAIL: edge_not_entirely_one_month
- FAIL: edge_not_entirely_one_session
- PASS: causal_and_mutation_checks

## Group cuts

### month

entry_month  trades   total_r    mean_r
    2025-12      31  2.327880  0.075093
    2026-01      32  8.484999  0.265156
    2026-02      30 -3.100857 -0.103362
    2026-03      25 -4.476544 -0.179062
    2026-04      24  3.450286  0.143762

### session

window  trades   total_r    mean_r
  ASIA      51  6.889193  0.135082
LONDON      50  0.782043  0.015641
NY0830      41 -0.985473 -0.024036

### direction

direction  trades    total_r    mean_r
      BUY      72  17.664137  0.245335
     SELL      70 -10.978374 -0.156834

### action

action  trades    total_r    mean_r
  FAST      69 -14.931053 -0.216392
RUNNER      73  21.616817  0.296121

## Interpretation boundary

This is an adaptive prototype measured on seen design data, not independent validation. Even a PASS cannot authorize live or demo orders. Forward shadow collection must last at least 60 new trading days or 100 new opportunities without opening the locked historical exam.
