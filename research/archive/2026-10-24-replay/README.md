# The AI trader's replays - start here

The AI trader is the engine's own path with the AI as the author of the signal: the watcher wakes it on a
closed M1 bar, it answers one step, the brakes veto or halve it, and what survives goes through every check
like any other signal (`docs/TRADING_FLOW.md`, PLAN §A37). This folder holds its replays: the record, the
journals, the faults found, and the scripts that produce them.

## Where everything is

| What | File | Keep it current |
|---|---|---|
| **Every day the AI has ever traded, with its code version** | `RECORD.md` | one row per day per code version; rows are added, never rewritten |
| **The current run, day by day, with the measurer's own reading** | `rerun_2026-10-28/JOURNAL.md` | one section per day, written before the next day runs |
| The generated report of each day | `rerun_2026-10-28/day_<date>.md` | written by `day.py` in the same change as the run |
| Every fault found, with its fix and status | `ISSUES.md` | a new row the day it is found; the status is corrected when the code is verified, not when it is written |
| Day 3's four code versions (2026-07-08) | `day3_variants/` | the reports recovered on 2026-10-28 |
| What each `except` in `app/ai/` swallows | `SWALLOWED.md` | re-checked when a handler is added |
| The state before a run was wiped | `data/replay/ai/backup_*/` (gitignored) | one folder per wipe, never deleted without reading it |

## How a day is run

```powershell
.venv\Scripts\python research/2026-10-24-replay/rollback.py 2026-07-06   # undo that day and later first
.venv\Scripts\python research/2026-10-24-replay/day.py 2026-07-06 > research\2026-10-24-replay\<run>\day_2026-07-06.md
.venv\Scripts\python research/2026-10-24-replay/day.py 2026-07-06 --report   # re-report without replaying
```

Rules that cost us something when they were broken (`docs/CODING_STANDARDS.md` section 11,
`docs/TRADER_ROUTINE.md`):

- **One day at a time**, each reported to the owner before the next runs. Not a batch.
- **The report goes to a file in this folder**, under the name a reader looks for, in the same change as the
  run. `data/` is gitignored: a report left there exists on one machine only, and on 2026-10-26/27 that lost
  a third of the whole record.
- **Never an empty file where a report belongs.** It answers the reader's question wrongly.
- **`app/` is not edited while a run is in flight.** Each day is a new process and would pick the edit up,
  and days on different code versions are not a record of one system.
- **Days run in order.** State, the journal the AI reads and both account balances carry from day to day, and
  `day.py` refuses a day that sits before the watcher's last call.
- **A day's report has four parts** (`docs/TRADER_ROUTINE.md`): the decisions the measurer disagrees with,
  every trade in detail, the profit and loss, and the day's close with one lesson.

## What a day report must answer before it is called done

- Which commit produced it, and what the store and the answers cache held when it started.
- Every wake: why it was woken, what it read, what it decided, what stopped it.
- For each disagreement: the measurer's own call from the point-in-time readings, stated before what followed.
- Whether any rule cited by the AI had its reading in the prompt at all. On 2026-07-06 three did not, and the
  day took no trade in a 74 USD range (ISSUES 37-39).

## The scripts

| Script | What it does |
|---|---|
| `day.py <date>` | replays one Thai day through the engine and prints the report |
| `rollback.py <date>` | undoes that day and later in the store, the day folders and the ledger |
| `premarket.py`, `plan_day.py` | the morning plan's inputs and a preview of it |
| `live_watch.py` | one line per new decision, plan or trade while a run goes |
| `audit_stops.py`, `audit_trades.py`, `audit_sim.py` | re-derive stops, trades and fills independently of the app |
| `plant_bugs_*.py` | plant deliberate bugs; every one must make a test fail, and the output is committed |
| `rederive_stops.py`, `parity.py` | an independent re-derivation, to the cent, of what the app computed |
