# TR3 forward shadow contract

This is a non-ordering research contract. It does not authorize engine, DEMO or LIVE integration.

## Cold start

Collection may begin no earlier than 2026-10-21 00:00 UTC. The locked 2026-04-18 through 2026-10-17 exam cannot be
used to fill the rolling training windows. Because the historical design sample is stale by more than 120 days,
TR3 must begin in quarantine:

1. Record new causal TR1 opportunities, the frozen 11-feature vector and hypothetical RUNNER outcome.
2. Do not score a TR3 action until a UTC month-start refit has at least 60 completed forward rows in each 60/90/120
   calendar-day component window.
3. The formal evaluation clock starts with the first eligible scored opportunity, not with warm-up collection.

## Frozen decision

Use alpha 20, target clip [-1.5, 5], training-only preprocessing, the three declared windows, score
`median - 0.5 * population_std`, strict score > +0.05 and RUNNER/SKIP only. Freeze each entry record and model hash at
decision time. Later outcomes cannot rewrite it.

## Evaluation boundary

Wait for both 60 new scored trading days and 100 new scored opportunities. Evaluate once using the exact primary
gates in `PLAN.md`, plus:

- no hash, time-boundary or outcome-availability violation;
- constant-risk results as the operational cash metric;
- explicit comparison with always RUNNER on identical new opportunities;
- bootstrap interval, best-one/best-three removal and month/session/direction concentration.

Any change to side handling, features, threshold, alpha, windows, exit or sizing creates a new named round and
restarts forward collection. Passing triggers an integration review, not automatic trading.
