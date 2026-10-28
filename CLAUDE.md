# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Read first

- **`docs/START_HERE.md`** - what this repository is now, what we are doing, and the one number everything
  is judged against.
- **`docs/HOUSE_RULES.md`** - how to work here. Every rule in it was paid for with a real mistake.
- **`eye/METHOD.md`**, **`eye/TRIED.md`**, **`eye/LESSONS.md`** - the live work: trading gold by eye, what
  has been tried and whether it worked, and what the ledger supports.

Everything built before 2026-10-28 is stopped and archived: `docs/archive/README.md` and
`research/archive/`. It is a record so the same ground is not covered twice, **not a starting point.**

## The project

TAA was an automated trading platform for an FBS account through MetaTrader 5, built on Windows beside the
terminal. On 2026-10-28 the owner stopped and archived all of it - every setup, all the research, the
knowledge base and the working method - keeping the raw data and the indicator primitives, to be put
together again.

So the code still builds and its tests pass, but **no strategy is enabled in `config.yaml`, in any lane.**
A started engine sends no order. DEMO and the hourly observer are disabled in Task Scheduler. LIVE stays
off and needs Phase 14 and an explicit word.

## Commands (Windows, from the repo root, always the venv)

```powershell
.venv\Scripts\python -m pip install -r requirements.txt -r requirements/dev.txt   # setup
.venv\Scripts\python -m pytest -q                              # all tests (about 15 minutes)
.venv\Scripts\python -m pytest tests/unit/test_broker.py -q    # one file
.venv\Scripts\ruff format app tests scripts; .venv\Scripts\ruff check app tests scripts
.venv\Scripts\mypy app; .venv\Scripts\bandit -q -r app -c pyproject.toml
.venv\Scripts\python -m app.cli doctor --fake                  # diagnostics against FakeMT5
.venv\Scripts\python -m app.cli backtest --server FBS-Demo --symbols XAUUSD --start 2026-01-01 --end 2026-06-30
```

The eye work:

```powershell
.venv\Scripts\python eye/sheets.py moments          # the hundred clock-sampled moments
.venv\Scripts\python eye/walk.py <id> <bars>        # sit at a moment and advance; H1 three weeks + M5 33 hours
.venv\Scripts\python eye/score.py [summary]         # score the ledger's unscored rows, or the running totals
```

**Nothing is committed without `ruff`, `mypy`, `bandit` and the tests green**, and nothing is pushed,
deployed, started on DEMO or LIVE, or pointed at the owner's accounts without asking first. Committing per
step by explicit paths is fine without asking.

## Working with the owner

- Chat in **Thai**. Documents, code and comments in **English**. Times to the owner in **Thai time**, read
  with PowerShell `Get-Date` (Git Bash `date` is wrong on this machine).
- **Record every trade and every decision when it happens**, in the file that holds them - never only in
  conversation.
- Report what the measurement says, including when it contradicts what was said before. A conclusion drawn
  from a handful of samples has been wrong three times out of three here.
- The owner's goal is fixed: **at least +0.15 R a trade after costs**. The method is theirs to direct.

## Architecture, while the code exists

`core` → `config`/`security` → `storage` → `broker` → `market_data` → `indicators`/`evidence` → `strategy`
→ `risk`/`engine` → `execution`; `sync` → `web`/`worker`. Enforced by `tests/unit/test_architecture.py`:
MetaTrader5 only inside `app/broker`, order functions only there, no wall-clock reads outside
`app/core/clock.py`, strategies pure. A new package must be added to that test's `LAYERS` table.

Decisions use **closed bars only**; MT5 epochs are broker server time and convert through `ServerClock`;
everything internal is timezone-aware UTC. Secrets and safety flags come from the environment, parameters
from `config.yaml`. Conventions in `docs/archive/CODING_STANDARDS.md`.
