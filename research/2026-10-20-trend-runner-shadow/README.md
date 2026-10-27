# TREND-RUNNER forward shadow journal

Standalone research infrastructure for collecting genuinely new TR3 evidence. It has no broker, execution or order
interface.

## Required sequence

Set `PYTHONPATH=research/2026-10-20-trend-runner-shadow` from the repository root.

For routine operation, the recommended command runs the complete causal sequence and regenerates the report:

`.venv/Scripts/python -m shadow.cli --db research/2026-10-20-trend-runner-shadow/shadow_journal.sqlite cycle --m1 data/history/FBS-Demo/XAUUSD/M1.parquet --tick-root data/ticks/XAUUSD --start 2026-10-21 --end 2026-10-22 --report-output research/2026-10-20-trend-runner-shadow/status`

`start` is inclusive and `end` is exclusive. Rerunning a range is safe. The individual commands below remain
available for diagnosis and manual event ingestion.

1. Initialize once:

   `.venv/Scripts/python -m shadow.cli --db research/2026-10-20-trend-runner-shadow/shadow_journal.sqlite init`

2. For every new causal TR1 entry, ingest its opportunity JSON in nondecreasing entry-time order:

   `.venv/Scripts/python -m shadow.cli --db ... ingest-opportunity opportunity.json`

   Or run the standalone one-way detector over a half-open local-day range:

   `.venv/Scripts/python -m shadow.cli --db ... scan --m1 data/history/FBS-Demo/XAUUSD/M1.parquet --tick-root data/ticks/XAUUSD --start 2026-10-21 --end 2026-10-22`

   `scan` processes Asia/London/New York anchors, writes any valid entry and scores it immediately. Incomplete M1 or
   missing tick files remain `PENDING` and are not finalized.

3. Immediately freeze its shadow decisions before its outcome exists:

   `.venv/Scripts/python -m shadow.cli --db ... score`

4. After both frozen paths have had enough data to complete, settle pending outcomes automatically:

   `.venv/Scripts/python -m shadow.cli --db ... settle --m1 data/history/FBS-Demo/XAUUSD/M1.parquet --tick-root data/ticks/XAUUSD`

   Settlement waits for M1 through entry + 8 hours and for the first executable quote at or after that horizon. It
   then writes FAST and RUNNER together. Reruns are idempotent. A separately reviewed producer may still ingest the
   same strict outcome event manually:

   `.venv/Scripts/python -m shadow.cli --db ... ingest-outcome outcome.json`

5. Generate status/drift output:

   `.venv/Scripts/python -m shadow.cli --db ... report --output research/2026-10-20-trend-runner-shadow/status`

   The report includes a forward-only robustness monitor for Champion concentration, chronological drawdown,
   rolling-20 expectancy, month/direction/session cuts and deterministic moving-block uncertainty. Hypothetical
   slippage stress is excluded. Challenger comparisons remain observational and cannot replace the Champion.

The CLI rejects outcomes for unscored opportunities, historical/backdated opportunities, altered duplicate payloads,
non-UTC timestamps, inconsistent risk/USD and incomplete feature vectors.

## Integration boundary

The package now includes an independent frozen TR1 file detector. It reads M1 and daily tick parquet only and writes
directly to the research journal. It does not import the historical TR1 package or application engine. External
detectors may still feed the reviewed JSON schema, but must pass an equivalent causal review.

Outcome settlement is a separate file-only adapter. It cannot run before an opportunity has been written and scored,
and it records the pair only after the full outcome horizon is available. Entry detection and feature construction
therefore cannot see the future label.

The database begins empty. Do not seed it from P1/P2 or the historical exam. During cold start all actions are null
`WARMUP`. Formal scoring begins only after a month-start snapshot finds 60 completed forward outcomes in every
60/90/120-day window.

## Policies

- `CHAMPION_R3`: frozen TR3 threshold 0.05, disagreement penalty 0.5.
- `CHALLENGER_T010`: threshold 0.10; observational only.
- `CHALLENGER_BUY_ONLY`: Champion rule with SELL forced to SKIP; observational only.

Challengers cannot replace the Champion automatically.

## Forward robustness states

- `INSUFFICIENT`: fewer than 20 completed Champion RUNNER trades.
- `COLLECTING`: enough RUNNER trades for monitoring, but the 100-opportunity/60-trading-day formal gate is incomplete.
- `ROBUST_POSITIVE`, `FRAGILE_POSITIVE` or `NOT_POSITIVE`: emitted only after formal readiness, using the frozen gates
  in `ROBUSTNESS_PLAN.md`.

These states never affect recorded actions or authorize an order.
