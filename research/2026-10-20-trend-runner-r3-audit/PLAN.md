# TR3 pre-forward profit robustness audit plan

## Objective

Measure how fragile the frozen TR3 primary profit is before forward collection begins. This audit is diagnostic only:
it must not change the Champion, choose a new threshold, or inspect the historical exam.

## Frozen input

- `../2026-10-20-trend-runner-r3/predictions_primary.parquet`
- Primary action is unchanged: use rows already marked `RUNNER`; `SKIP` remains zero exposure.
- Safe-design P1/P2 rows only. Do not regenerate predictions or refit a model.
- Record the source SHA-256 before calculation.

## Predeclared measurements

1. Reconcile executed count, total R, mean R, fixed-0.01 USD and constant-$10-risk USD with frozen R3.
2. Remove the best 1 through 5 trades without replacement and report the remaining total.
3. Measure gross profit, gross loss, profit factor, payoff ratio and win rate.
4. Measure chronological maximum drawdown, losing streak, longest underwater span and unresolved terminal drawdown.
5. Measure rolling 20-executed-trade expectancy: minimum, median, maximum and fraction positive.
6. Report month, direction and session dependence without introducing a new filter.
7. Run 20,000 deterministic IID bootstrap samples and 20,000 circular moving-block samples of length 5.
8. For each bootstrap method report the 95% mean-R interval, probability total R is positive and simulated maximum
    drawdown percentiles.

Additional hypothetical slippage/cost stress is explicitly excluded at the user's direction. The frozen R values
remain unchanged and already use the original tick-side execution and spread rules.

## Interpretation gates

- `ROBUST`: moving-block lower 95% mean is positive, remains profitable after removing the best three trades, and at
  least 70% of rolling 20-trade windows are positive.
- `FRAGILE_POSITIVE`: observed total is positive, but one or more robustness gates fail.
- `NOT_POSITIVE`: observed total is non-positive.

These labels describe evidence strength, not permission to trade.

## Deliverables

- Reproducible audit script.
- Machine-readable results and supporting CSV files.
- Concise written handoff.
- Standalone Canvas summary for inspection beside the chat.

