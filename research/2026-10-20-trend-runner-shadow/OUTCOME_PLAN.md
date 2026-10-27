# Automatic dual-outcome adapter plan

## Objective

Complete the forward shadow loop without adding any broker or order capability. For every frozen,
already-scored opportunity, reconstruct the two hypothetical outcomes needed by the journal:

- `FAST`: original stop, `+2R` target, maximum hold 60 minutes.
- `RUNNER`: the frozen `SPLIT` family: take one third at `+1R`, trail the remaining two thirds on
  confirmed M5 structure, graduate to confirmed M15 structure after `+3R`, maximum hold 8 hours.

The adapter writes one immutable outcome only when both paths have completed.

## Frozen semantics

1. Use executable quote side: bid for a long, ask for a short.
2. Stop checks precede target/partial/graduation checks at each quote.
3. A structure event available strictly before a quote affects that quote. An event available at the
   exact quote timestamp is applied after the price actions at that timestamp.
4. A confirmed radius-1 pivot is eligible only when both pivot time and confirmation availability are
   at or after entry and availability is no later than the 8-hour horizon.
5. Structure buffer is `max(entry spread, 0.10 * ATR(14))` at the confirmation bar.
6. M5 trailing applies until graduation. M15 events apply only at or after the graduation timestamp.
7. The execution path includes the first quote at or after each time deadline.
8. R is based on the original risk. RUNNER R after a partial is
   `1/3 + 2/3 * remaining_leg_R`.

## Data and causality boundaries

- Opportunity payload must preserve entry spread; it is an input to the frozen structure-stop rule.
- Process only opportunities present in the append-only journal and missing an outcome.
- Require M1 history through the 8-hour horizon and an execution quote at or after that horizon before
  attempting settlement. This intentionally delays settlement instead of making an early-data guess.
- Read tick files only from entry forward until the first quote at or after the 8-hour horizon.
- Do not read, import, or call broker, engine, execution, TR1, R2, or R3 runtime code.
- Do not write partial outcomes, retries, or synthetic evidence into the real forward database.

## Implementation sequence

1. Extend the strict opportunity schema with non-negative finite `spread`.
2. Implement an independent frozen FAST/SPLIT simulator and causal structure-event builder inside
   `shadow/`.
3. Implement a file-only settlement adapter for pending journal opportunities.
4. Expose settlement through a `settle` CLI command.
5. Add unit and synthetic end-to-end tests for ordering, partial accounting, data readiness, and
   append-only behavior.
6. Verify exact parity against frozen P1 and P2 entries/results without opening exam data.
7. Update operating documentation and run the real journal settlement command; an empty or
   not-yet-mature journal must remain unchanged.

## Acceptance gates

- All shadow tests pass.
- Source isolation test continues to pass.
- FAST and SPLIT match every frozen P1/P2 reference row on completion state, exit time, exit price,
  reason, R, holding time, activation flags, graduation, and final stop.
- A second settlement run is idempotent.
- The real forward journal contains no synthetic or historical opportunity/outcome rows.

