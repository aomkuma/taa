# Automatic dual-outcome adapter checklist

## Freeze and schema

- [x] Write plan before implementation.
- [x] Add entry spread to the strict opportunity payload and documentation.
- [x] Update every synthetic/test opportunity fixture.
- [x] Preserve append-only and forward-boundary validation.

## Simulator

- [x] Implement independent FAST and RUNNER/SPLIT state machines.
- [x] Preserve executable-side quote semantics and check ordering.
- [x] Implement confirmed M5/M15 pivot events with ATR/spread buffer.
- [x] Preserve exact-time event ordering and M5-to-M15 graduation.
- [x] Reject crossed, unordered, pre-entry, or incomplete paths.

## Settlement adapter

- [x] Select only scored opportunities with no outcome.
- [x] Require complete M1 and tick coverage through entry + 8 hours.
- [x] Stop tick loading after the first quote at/after the horizon.
- [x] Write both FAST and RUNNER outcomes atomically through the journal.
- [x] Return explicit settled/pending/idempotent counts.
- [x] Add CLI command without any order capability.

## Verification

- [x] Add focused simulator and adapter tests.
- [x] Pass the complete shadow test suite.
- [x] Match frozen P1 FAST/SPLIT outcomes exactly.
- [x] Match frozen P2 FAST/SPLIT outcomes exactly.
- [x] Generate a machine-readable parity artifact.
- [x] Run synthetic rehearsal without retaining its database.
- [x] Run settlement against the real forward journal.
- [x] Confirm the real journal contains no synthetic/historical rows.

## Documentation and handoff

- [x] Update README, event schema, and handoff.
- [x] Record commands, results, limitations, and the next safe action.
