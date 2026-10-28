# One-way causal detector adapter plan

Written before adapter implementation or parity measurement.

## Objective

Extend the existing non-ordering shadow system with a one-way batch adapter:

`M1 parquet + daily tick parquet -> frozen TR1 entry -> frozen 11 features -> journal -> immediate shadow score`

The adapter reads files only. It has no broker, terminal, engine, execution or order interface.

## Frozen detector

- XAUUSD only; threshold 0.25H; M1 first pullback/continuation only.
- Asia, London and New York 08:30 local anchors with the frozen DST-aware clocks.
- First impulse close within 60 minutes; pullback ratio [0.20, 0.65].
- Radius-1 pivot becomes available only after its right-hand M1 bar closes.
- Asia/London deadline 120 minutes; New York deadline 240 minutes.
- Market fill is the first tick at/after the continuation decision, within five minutes, on the adverse quote.
- Stop buffer is max(spread, 0.10 M1 ATR); accept risk/H1 in [0.05, 0.50].
- At most one entry per window anchor.

## Causality and state

- A scan is accepted only from 2026-10-21 UTC onward in operational mode.
- An anchor is finalized only when M1 reaches its full deadline and required tick data exists.
- Completed anchors are append-only in the same SQLite journal; reruns are idempotent.
- Entry features use bars with availability no later than fill time.
- Prior-session edge uses only journal outcomes completed before fill.
- Opportunity is written and scored before any outcome is permitted.
- No outcome simulation is added here; the existing strict outcome event remains a separate later input.

## Verification before delivery

1. Hand tests for clocks, impulse, pivot availability, fill, risk and future-bar invariance.
2. Parity replay against frozen pre-exam TR1 entries using a test-only boundary bypass in memory, never journal ingest.
3. Truncation replay: later M1/ticks cannot change a finalized earlier detection.
4. Empty/current operational scan must not fabricate an event before the collection boundary/data are complete.
5. Import guard proving no execution-capable module is reachable.

The adapter is complete when parity and synthetic end-to-end tests pass and the real shadow database remains empty.
