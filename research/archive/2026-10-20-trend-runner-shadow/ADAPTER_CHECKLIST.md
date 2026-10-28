# Detector adapter checklist

- [x] Freeze adapter rules and safety boundary before parity measurement.
- [x] Add append-only processed-anchor state.
- [x] Implement DST anchors and causal M1/H1 aggregation.
- [x] Implement frozen impulse/pullback/continuation detector.
- [x] Implement tick fill, spread, stop and risk filter.
- [x] Implement all 11 entry features independently.
- [x] Implement prior-session completed-outcome feature using RUNNER minus FAST.
- [x] Implement one-way scan command and immediate shadow scoring.
- [x] Add unit/causal/truncation/isolation tests.
- [x] Pass parity replay against frozen TR1 entries.
- [x] Rehearse end to end without retaining synthetic records.
- [x] Confirm delivered real database remains empty.
- [x] Write adapter operating handoff.

## Completion checkpoint

- P1 parity: 192 anchors, 138/138 entries, no mismatch.
- Eleven-feature maximum error: 2.22e-16; 12 truncation cases invariant.
- Pre-data operational scan: three PENDING_M1, zero journal writes.
