# Automatic dual-outcome adapter handoff

## Delivered path

`scored journal opportunity + M1 parquet + daily quote parquet -> FAST and RUNNER simulation -> one immutable outcome`

The implementation is isolated in `shadow/outcomes.py` and `shadow/outcome_adapter.py`. It independently reproduces
the frozen FAST and SPLIT state machines and does not import historical strategy, application, broker, engine, or order
modules.

## Frozen rules

- FAST uses the initial stop, a +2R target, and a 60-minute deadline.
- RUNNER takes one third at +1R, trails two thirds on confirmed M5 structure, moves to confirmed M15 structure after
  +3R, and ends after 8 hours.
- Longs execute against bid; shorts execute against ask. Stops are checked before targets and state changes.
- Exact-time structure confirmations apply after price actions at that timestamp.
- The structure buffer is the greater of entry spread and 10% of ATR(14).
- If the market is closed at a deadline, the first later executable quote supplies the time-exit mark.

## Causal operation

Run:

`.venv/Scripts/python -m shadow.cli --db research/2026-10-20-trend-runner-shadow/shadow_journal.sqlite settle --m1 data/history/FBS-Demo/XAUUSD/M1.parquet --tick-root data/ticks/XAUUSD`

Only scored opportunities without an outcome are considered. Incomplete M1 or quote coverage remains pending and
writes nothing. A completed outcome contains both labels and is append-only; rerunning settlement is safe.

## Verification evidence

- `OUTCOME_PARITY.json`: PASS.
- 280 safe-design P1/P2 entries and 560 FAST/SPLIT outcomes checked.
- Completion, timestamp, price, reason, R, holding duration, activation, partial, graduation, and final stop all
  matched; zero mismatches.
- Exam data was not opened.
- Thirteen shadow tests pass, including partial accounting, exact-time ordering, closed-market deadline handling,
  complete-data gating, and idempotent settlement.
- Synthetic rehearsal used a temporary database. The real journal remains empty: zero opportunities and outcomes.

## Remaining operational limitation

This is a batch file adapter. It depends on M1 and daily quote parquet being refreshed outside this package. It has no
terminal connection and no order capability. Forward evidence begins only when genuinely new post-boundary files are
available.
