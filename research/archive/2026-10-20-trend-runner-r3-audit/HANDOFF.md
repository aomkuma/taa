# TR3 pre-forward profit robustness audit handoff

## Verdict

`FRAGILE_POSITIVE`

The frozen TR3 primary is profitable on safe-design P1/P2, but the evidence is not yet robust enough for promotion.
The historical exam was not opened, the Champion was not changed, and hypothetical slippage stress was excluded by
user direction.

## Reconciled observed result

- 83 executed from 210 scored opportunities.
- +17.702R total and +0.213R per executed trade.
- Profit factor 1.416; payoff ratio 3.103; win rate 31.3%.
- Maximum drawdown 13.327R and maximum losing streak 8.
- The final 42 executed trades remain below the prior equity peak, ending 6.243R below it.
- All five frozen headline fields reconcile exactly with the R3 result artifact.

## Main fragility evidence

- Removing the best trade leaves +1.277R.
- Removing the best two leaves -10.617R; removing the best three leaves -16.893R.
- The best trade equals 92.8% of net profit; the best three equal 195.4% because the remaining trades net negative.
- Rolling 20-trade mean ranges from -0.627R to +1.054R; 70.3% of windows are positive.
- Three of five months are profitable. All three sessions are positive, but only BUY is positive by direction.

## Resampling

Twenty thousand deterministic samples were run for each method.

- IID 95% mean interval: -0.267R to +0.818R; positive-total probability 76.1%.
- Circular moving-block length-5 interval: -0.279R to +0.779R; positive-total probability 77.6%.
- Moving-block simulated maximum drawdown: 14.412R median, 28.045R at the 95th percentile and 35.581R at the
  99th percentile.

The lower bounds remain below zero, so the positive expectancy is not statistically secure in this sample.

## Decision

Continue forward shadow collection with the frozen Champion and challengers. Do not add a post-result BUY filter,
retune the threshold, or promote the strategy based on this audit. The most valuable next evidence is untouched
forward data showing whether profit remains positive without dependence on a few extreme winners.

## Reproduction

- Run `.venv/Scripts/python research/2026-10-20-trend-runner-r3-audit/audit.py`.
- Run `.venv/Scripts/python -m pytest research/2026-10-20-trend-runner-r3-audit/tests -q`.
- Run `.venv/Scripts/ruff check research/2026-10-20-trend-runner-r3-audit`.
- Type-check the Canvas with
  `npx --yes --package typescript tsc --noEmit -p research/2026-10-20-trend-runner-r3-audit/tsconfig.canvas.json`.

Machine-readable evidence is in `RESULTS.json`; supporting cuts and removal paths are CSV files in this directory.
