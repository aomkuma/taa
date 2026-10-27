# RETEST-CONTINUATION V1

An isolated prospective research branch for post-stop retest/continuation behavior. It cannot place orders and does not modify TR1/TR3/TR4 or the Champion shadow journal.

## Run the observer

From the repository root, after new forward outcomes have matured:

```powershell
.venv/Scripts/python.exe research/2026-10-21-trend-runner-retest-continuation/run_observer.py
```

The command reads the existing forward-shadow SQLite journal read-only, validates source stop-before-+1R classification against ordered executable ticks, reads only post-2026-10-21 M1 rows, and appends candidate events/outcomes to `candidate_journal.sqlite` in this directory. Pending data horizons remain pending. Reruns are idempotent. Optional `--source-db`, `--m1`, `--tick-root`, and `--candidate-db` arguments can point to alternate research files; do not point `--candidate-db` at the Champion database.

## Historical diagnostic (not validation)

An explicitly requested exploratory replay of the previously inspected pre-exam 632-event source cohort is stored under `historical_diagnostic/`. It uses M1 OHLC, recorded spread, and excludes slippage; it is in-sample and event-level, and cannot establish independent profitability. It is kept separate from `candidate_journal.sqlite` and from the prospective observer.

## Evidence discipline

The current forward source journal had 0 new post-boundary opportunities/outcomes when checked. Synthetic tests verify simulator behavior only. Prospective interim results require 50 completed events over at least 30 trading days; no strategy promotion is automatic.

See [PLAN.md](PLAN.md) for the frozen rule and acceptance gates, and [STATUS.md](STATUS.md) for current evidence and remaining conditions.
