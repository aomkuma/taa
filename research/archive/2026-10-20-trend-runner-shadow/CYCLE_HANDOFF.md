# Daily shadow cycle handoff

## Delivered

The `cycle` CLI command advances the complete file-only workflow in causal order:

1. Scan the requested half-open day range for frozen entries.
2. Freeze decisions for any manually ingested opportunity still pending a decision.
3. Settle every scored opportunity whose full dual-outcome data is mature.
4. Regenerate status, drift, performance, robustness and policy-comparison reports.

It has no broker, terminal, engine, execution or order capability. Existing schema boundaries, immutable hashes and
data-completeness gates remain authoritative.

## Operation

From the repository root with the shadow package on `PYTHONPATH`, run:

`.venv/Scripts/python -m shadow.cli --db research/2026-10-20-trend-runner-shadow/shadow_journal.sqlite cycle --m1 data/history/FBS-Demo/XAUUSD/M1.parquet --tick-root data/ticks/XAUUSD --start YYYY-MM-DD --end YYYY-MM-DD --report-output research/2026-10-20-trend-runner-shadow/status`

The start day is inclusive and end day exclusive. Pending market data is reported without finalizing an anchor or
fabricating an event. Reruns are idempotent.

## Verification

- Synthetic unavailable-data cycle and immediate rerun both returned three `PENDING_M1` anchors and zero writes.
- Complete shadow suite: 17 tests passed.
- Static checks passed.
- The real cycle for 2026-10-21 returned `PENDING_M1: 3`, zero decisions/outcomes and an `INSUFFICIENT` robustness
  state. The real journal remains empty.
