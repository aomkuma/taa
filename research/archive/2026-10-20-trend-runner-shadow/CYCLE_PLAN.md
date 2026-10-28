# Daily shadow cycle plan

## Objective

Provide one safe command that advances the complete file-only forward workflow:

`scan entries -> freeze decisions -> settle matured outcomes -> write status/robustness report`

The command must remain idempotent and have no broker, terminal, engine, execution, or order capability.

## Contract

- Accept the same half-open day range as `scan`, plus M1 path, daily tick root and report-output directory.
- Run entry scanning first. Valid entries are already scored immediately by the entry adapter.
- Run settlement second across every scored opportunity still missing an outcome.
- Generate the observational report last, even when all market data is pending.
- Return one JSON object containing scan counts, settlement counts and the final report.
- Preserve all existing collection-boundary, immutability, causality and full-horizon checks.
- A rerun over the same range must not create a duplicate opportunity, decision, outcome or anchor.
- Do not add hypothetical slippage/cost stress.

## Failure behavior

- Missing or incomplete future M1/ticks remains `PENDING_*` and writes no fabricated market event.
- A real validation/immutability error fails the cycle; it is never converted into pending.
- Report files may be regenerated because they are derived observational artifacts, not journal evidence.

## Verification

- Test the whole cycle against an empty temporary journal and unavailable forward data.
- Confirm all three 2026-10-21 session anchors remain `PENDING_M1` before their data exists.
- Confirm a second run remains empty/idempotent.
- Pass the complete shadow suite and static checks.
- Run the command against the delivered real journal and confirm it remains free of synthetic/historical rows.

