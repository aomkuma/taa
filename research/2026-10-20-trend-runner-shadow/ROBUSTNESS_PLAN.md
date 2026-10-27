# Forward robustness monitor plan

## Objective

Extend the observational shadow report so untouched forward evidence automatically shows whether Champion profit is
broadly distributed or still dependent on a few extreme winners. This monitor cannot change a decision, model,
threshold, policy, or order state.

## Frozen boundary

- Use only completed outcomes joined to immutable `CHAMPION_R3` decisions with status `SCORED`.
- Use `runner_r` only when the frozen action is `RUNNER`; `SKIP` remains zero exposure and is not counted as a trade.
- Preserve chronological entry order for path and rolling metrics.
- Do not use historical P1/P2 rows, the locked exam, or historical audit results in forward calculations.
- Do not add hypothetical slippage or transaction-cost penalties.
- Challengers remain observational and cannot replace the Champion automatically.

## Metrics

For the Champion, report:

1. Executed count, total/mean R, win rate, profit factor and payoff ratio.
2. Maximum drawdown, losing streak, longest underwater span and terminal drawdown.
3. Total R after removing the best one and best three trades.
4. Best-one and best-three contribution as a share of net profit when net profit is nonzero.
5. Rolling 20-trade current/minimum/median/maximum expectancy and fraction of positive windows.
6. Month, direction and session totals without creating a filter.
7. Once at least 20 RUNNER outcomes exist, 5,000 deterministic circular moving-block samples of length 5:
   95% mean-R interval, probability total R is positive, and maximum-drawdown percentiles.
8. Compact completed-performance summaries for Champion and both declared challengers.

## Status and gates

- `INSUFFICIENT`: fewer than 20 completed Champion RUNNER trades.
- `COLLECTING`: at least 20 trades, but fewer than 100 scored opportunities or 60 scored trading days.
- At formal evaluation readiness:
  - `ROBUST_POSITIVE` only if observed total is positive, total after removing the best three remains positive, the
    moving-block lower 95% mean is positive, and at least 70% of rolling-20 windows are positive.
  - `FRAGILE_POSITIVE` when observed total is positive but any robustness gate fails.
  - `NOT_POSITIVE` when observed total is non-positive.

These labels describe evidence only. No status authorizes trading or modifies policy state.

## Verification

- Unit-test empty, insufficient, collecting, fragile and robust calculations with synthetic arrays.
- Verify chronological ordering and deterministic bootstrap output.
- Verify report generation is observational and leaves the journal unchanged.
- Re-run the complete shadow test suite and source-isolation guard.
- Confirm the delivered real forward database remains empty.

