# Forward shadow system handoff

## Delivered

- Append-only/idempotent SQLite journal for opportunity, outcome, decision, snapshot and audit records.
- Hard collection boundary at 2026-10-21 UTC and nondecreasing opportunity ingestion.
- Frozen independent TR3 ensemble with monthly 60/90/120-day cold-start refits.
- Champion plus two observational challengers; no automatic promotion.
- Drift report using hash-verified historical feature distributions only as a reference, never training data.
- Readiness counter requiring 100 scored opportunities and 60 scored trading days.
- CLI for init, ingest, score, status, policy display and report generation.
- Empty initialized `shadow_journal.sqlite` and empty status report.
- Independent one-way M1/tick detector for frozen 0.25H, M1 pullback TR1 entries.
- Append-only anchor state, so completed NO_ENTRY/rejected/emitted anchors cannot change on rerun.
- Independent automatic FAST/RUNNER settlement from M1 and daily quote files.
- Entry spread preserved in the strict opportunity event for exact structural-stop reconstruction.
- Forward-only robustness monitor covering concentration, chronological path risk, rolling expectancy, group cuts,
  deterministic moving-block uncertainty and observational Champion/Challenger comparison.
- One-command `cycle` orchestration for scan, pending-decision scoring, outcome settlement and report generation.

## Causal safeguards

- Opportunity must be scored before its outcome can be recorded.
- Monthly snapshots and decisions are immutable; a mismatched replay fails.
- Insufficient month-start data freezes the entire month as `WARMUP`.
- Model training uses only forward entries in the window with RUNNER exits before month start.
- All timestamps must be UTC; feature vector, side/session one-hots, risk and fixed-lot USD are reconciled.
- Package imports no TR1/TR2/TR3 strategy package and no app/broker/engine/execution module.

## Verification

- Seventeen unit/integration tests pass.
- Synthetic rehearsal with 60 completed rows produced three READY January snapshots and three scored target decisions
  sharing a deterministic model hash.
- Synthetic database was temporary; `REHEARSAL.json` confirms zero real forward rows were written.
- Delivered database status: 0 opportunities, 0 outcomes, 0 decisions, 0 snapshots, not evaluation-ready.
- Full P1 parity: 192 anchors checked, 138/138 frozen entries reproduced, no extras, all 11 features matched with
  maximum error 2.22e-16, and 12 truncation cases were invariant.
- Operational 2026-10-21 scan correctly returned three `PENDING_M1` states on 2026-10-20 and wrote no record.
- Outcome parity across safe-design P1/P2: 280 entries, 560 FAST/SPLIT outcomes, 10 fields per outcome and zero
  mismatches. Exam data was not opened.
- Real-journal settlement run returned `ALREADY_SETTLED_OR_EMPTY`; the database remains at zero opportunities and
  zero outcomes.
- Empty-journal robustness state is `INSUFFICIENT`; hypothetical slippage stress is explicitly excluded.
- Real `cycle` run for the half-open 2026-10-21 day returned `PENDING_M1: 3`; it wrote zero journal rows and safely
  regenerated the empty report.

## Deliberate boundary

The system detects entries and settles hypothetical outcomes from immutable market-data files but does not connect to
a terminal or trading engine. Entry and outcome adapters remain separate: an opportunity is persisted and scored
before future quote data can be consumed. Both FAST and RUNNER labels are written together because the frozen session
feature is `RUNNER - FAST`.

## Next operational step

Begin feeding genuinely new causal opportunities in the sequence documented by `README.md`. Run `scan` after market
files arrive, then run `settle` after the 8-hour horizon has matured. Monitor the generated report; do not evaluate or
change the Champion until cold start completes and both formal sample thresholds are met.
