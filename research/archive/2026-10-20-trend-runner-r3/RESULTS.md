# TR3 design-only result

Status: **FORWARD SHADOW CANDIDATE**. NOT PROMOTED; all evidence is seen development data.

The historical exam was not used. P1/P2/TR2 are all seen development evidence.

## Primary robust ensemble

- Actions: {'SKIP': 127, 'RUNNER': 83}.
- 83 executed from 210 scored opportunities.
- 17.702R total; 0.213R per executed trade.
- Bootstrap 95% mean interval [-0.270, 0.827].
- Drawdown 13.327R; losing streak 8.
- Without best one 1.277R; without best three -16.893R.
- Constant $10 risk: $177.02; fixed 0.01 lot audit: $16.27.

## Same-row always RUNNER baseline

- 19.195R total; 0.091R/trade; drawdown 20.241R.

TR3 retained 92.2% of the baseline total R while executing 39.5% of its opportunities. Mean R per executed trade
rose by 134%, and drawdown fell by 34.2%. Constant-risk sizing converts the primary result to +$177.02 at $10
initial risk per trade. The fixed 0.01-lot result was also positive at +$16.27.

## Robustness cautions

- The bootstrap mean interval still crosses zero, so statistical uncertainty remains high.
- Removing the best trade leaves +1.277R, but removing the best three leaves -16.893R.
- December and January supplied most profit; February and March were negative.
- BUY made +20.776R while SELL lost -3.074R. This is reported, not converted into a post-result side filter.
- Several component coefficients still changed sign. The ensemble reduces decision instability but does not prove
  the underlying relationships are stationary.

All four predeclared neighbouring diagnostics were positive, with 66-96 trades, +14.859R to +27.254R and
+0.225R to +0.300R per trade. This is useful local robustness evidence, but no diagnostic replaces the primary.

## Development gates

- PASS: at_least_100_scored
- PASS: at_least_60_executed
- PASS: mean_r_at_least_0_15
- PASS: mean_r_above_always_runner
- PASS: retain_half_baseline_total_r
- PASS: non_negative_without_best
- PASS: drawdown_at_least_10pct_lower
- PASS: edge_outside_best_month
- PASS: edge_outside_best_session
- PASS: causal_and_mutation_checks

## Group cuts

### month

  month  trades   total_r    mean_r
2025-12      25 12.428978  0.497159
2026-01      20  9.043131  0.452157
2026-02       6 -3.291190 -0.548532
2026-03      19 -3.412750 -0.179618
2026-04      13  2.933414  0.225647

### week

    week  trades   total_r    mean_r
2025-W49       6 -3.401792 -0.566965
2025-W50       9 11.964614  1.329402
2025-W51       4 -2.444920 -0.611230
2025-W52       4  0.309186  0.077297
2026-W01       3  4.983284  1.661095
2026-W02       5  1.945344  0.389069
2026-W03       4 -0.021094 -0.005273
2026-W04       6 10.610029  1.768338
2026-W05       4 -2.472544 -0.618136
2026-W06       4 -2.746487 -0.686622
2026-W08       1  0.372215  0.372215
2026-W09       1 -0.916918 -0.916918
2026-W10       1 -0.334749 -0.334749
2026-W11       2 -0.008819 -0.004410
2026-W12       6 -5.410433 -0.901739
2026-W13       8  2.642360  0.330295
2026-W14       4 -2.593855 -0.648464
2026-W15       4 -1.388944 -0.347236
2026-W16       7  6.615105  0.945015

### session

window  trades  total_r   mean_r
  ASIA      26 8.566238 0.329471
LONDON      27 5.975607 0.221319
NY0830      30 3.159737 0.105325

### direction

direction  trades   total_r    mean_r
      BUY      53 20.775697  0.391994
     SELL      30 -3.074114 -0.102470

## Boundary

No result here is independent validation. Diagnostics cannot replace the frozen primary. A candidate must be evaluated on genuinely new forward observations before any integration decision.
