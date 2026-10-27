# Forward robustness monitor handoff

## Delivered

The shadow status report now evaluates the distribution quality of completed forward `CHAMPION_R3` RUNNER trades.
It is read-only with respect to decisions and policy state. It cannot place an order or promote a challenger.

Metrics include total/mean R, win rate, profit factor, payoff ratio, chronological drawdown and underwater duration,
best-one/best-three removal, tail concentration, rolling-20 expectancy, month/direction/session cuts, and a
deterministic 5,000-sample circular moving-block bootstrap. Hypothetical slippage/cost stress is excluded by user
direction; frozen outcome R is used unchanged.

## Status lifecycle

- Fewer than 20 completed Champion RUNNER trades: `INSUFFICIENT`.
- At least 20, but before 100 scored opportunities and 60 scored trading days: `COLLECTING`.
- After formal readiness: `ROBUST_POSITIVE`, `FRAGILE_POSITIVE`, or `NOT_POSITIVE` under the frozen gates in
  `ROBUSTNESS_PLAN.md`.

Policy comparison reports completed selected count, total/mean R and drawdown for Champion and both predeclared
challengers. It is observational only.

## Verification

- Status-transition tests cover insufficient, collecting, robust-positive, fragile-positive and non-positive paths.
- Moving-block output is deterministic and group cuts reconcile to completed rows.
- Complete shadow suite: 16 tests passed.
- Static checks passed.
- Real forward report remains empty and correctly reports `INSUFFICIENT`; no synthetic or historical row was written.
