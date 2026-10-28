# TREND-RUNNER forward shadow system plan

Written before creating the journal or running a shadow score.

## Scope

Build a standalone, non-ordering forward journal for the frozen TR3 champion. It accepts causal opportunity events,
stores immutable outcomes, performs cold-start monthly refits, records Champion and Challenger decisions, and emits
drift/performance reports. It must never import or call broker, execution, engine, DEMO or LIVE code.

## Safety boundary

- Earliest accepted opportunity: 2026-10-21 00:00 UTC.
- The locked 2026-04-18 through 2026-10-17 exam cannot be ingested as forward evidence.
- Historical R2 features may be read only to establish drift reference distributions, never as model training rows.
- During cold start every policy state is `WARMUP`; there is no hypothetical trade action until all 60/90/120-day
  windows contain 60 completed forward outcomes at a UTC month start.
- All records are append-only/idempotent. A same-key payload mismatch is an error, never an update.

## Components

1. SQLite research journal inside this folder, with opportunities, outcomes, decisions, model snapshots and audit log.
2. Strict JSON opportunity/outcome schemas with UTC, feature, stop/risk and hash validation.
3. Independent frozen TR3 ensemble implementation.
4. Champion: threshold 0.05, disagreement penalty 0.5, both sides.
5. Shadow-only challengers declared before forward evidence:
   - `CHALLENGER_T010`: threshold 0.10, penalty 0.5;
   - `CHALLENGER_BUY_ONLY`: Champion rule but forces SELL to SKIP.
6. Drift report covering feature shifts, action rate, rolling 20/40 outcomes, drawdown, concentration, model counts and
   forward-evaluation readiness.
7. CLI for init, ingest, score, status and report. No command can place an order.

## Verification

- Test schema rejection, idempotency, immutability and timestamps.
- Test cold-start quarantine and all-window minimum counts.
- Test current/future outcomes cannot influence an entry decision.
- Test deterministic model/payload hashes and replay.
- Test Champion/Challenger separation and import guard.
- Run a synthetic end-to-end rehearsal only; do not seed real forward evidence.

## Deliverable boundary

The delivered database is empty and ready for events. The system is infrastructure, not validation. Formal evaluation
requires 60 scored trading days and 100 scored opportunities after warm-up, as defined by TR3.
