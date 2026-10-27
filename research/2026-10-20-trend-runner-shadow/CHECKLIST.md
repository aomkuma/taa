# Forward shadow system checklist

- [x] Write plan before creating journal state.
- [x] Freeze collection boundary and policies.
- [x] Implement strict schemas and append-only journal.
- [x] Implement cold-start Champion/Challenger scoring.
- [x] Implement deterministic model and event hashes.
- [x] Implement drift/performance/readiness report.
- [x] Implement non-ordering CLI.
- [x] Add isolation, causality, idempotency and replay tests.
- [x] Run synthetic end-to-end rehearsal.
- [x] Initialize an empty forward database.
- [x] Confirm no engine/config/broker files changed.
- [x] Write operating guide and handoff.

## Completion checkpoint

- Seventeen tests and the synthetic 60-row cold-start rehearsal pass.
- Empty real journal and report initialized; no forward evidence was fabricated.
- Mode is hard-coded and reported as `SHADOW_ONLY_NO_ORDER_CAPABILITY`.
