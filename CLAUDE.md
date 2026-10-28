# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Read first

- **`docs/HANDOFF.md`** - **start here in a new session**: where the work stands, the current numbers,
  where the next day resumes, and what is still open.
- **`docs/START_HERE.md`** - what this repository is now, what we are doing, and the one number everything
  is judged against.
- **`docs/HOUSE_RULES.md`** - how to work here. Every rule in it was paid for with a real mistake.
- **`eye/METHOD.md`**, **`eye/TRIED.md`**, **`eye/LESSONS.md`** - the live work: trading gold by eye, what
  has been tried and whether it worked, and what the ledger supports.

Everything built before 2026-10-28 is stopped and archived: `docs/archive/README.md` and
`research/archive/`. It is a record so the same ground is not covered twice, **not a starting point.**

**Everything in an archive folder is old data and never decides the present** (owner, 2026-10-28) -
`docs/archive/`, `research/archive/`, and any folder named `archive`. Its numbers, verdicts, rules,
setups and lessons were measured under a method that was stopped; they are not evidence for or against
anything done now, not a default to fall back on, and not quoted as a reason. Read it only to avoid
covering the same ground twice, and say so when you do. A decision about the present rests on what
the present work has measured, or on the owner's word.

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
.venv\Scripts\python eye/walk.py "2026-04-01 07:00" 12   # a real day, advanced 12 M5 bars: _a = H1 + M15, _b = M5; ZigZag, MACD, RSI
.venv\Scripts\python eye/walk.py <id> <bars>            # the same, at one of the retired sampled moments
.venv\Scripts\python eye/score.py [summary]             # score the ledger's unscored rows, or the running totals
.venv\Scripts\python eye/rules.py                       # which of the nine rules held, and where they fought
```

The method is **real trading days, one at a time** (`eye/METHOD.md` 2c): a date taken whole, the owner's
three windows walked in order - Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai - and every
window written into `eye/sessions.csv` whether it produced a trade or not. `eye/sheets.py` and
`moments.csv` are the retired clock-sampling design, kept because the control trades came from it.

The principle the trading holds to is **the owner's: price structure + divergence + counting the peaks**
(`eye/METHOD.md` 2e), dictated by the owner on 2026-10-28 and written there in full - do not ask it again.
Anything new about it is the owner's to state: ask, and write the answer in their terms; never fill it in
from your own reading of the charts (METHOD 2d was exactly that, and is on hold). An example the owner
gives is a principle to generalise, never a rule with its numbers.

**Nothing is committed without `ruff`, `mypy`, `bandit` and the tests green**, and nothing is pushed,
deployed, started on DEMO or LIVE, or pointed at the owner's accounts without asking first. Committing per
step by explicit paths is fine without asking.

## My own working rules (owner, 2026-10-28: keep these here)

- **When I say something is recorded, name the file and say what it holds.** "Recorded" on its own tells
  the owner nothing about where to look.
- **Write it where it belongs the moment it happens** - every trade, every wait, every lesson - and never
  only in the conversation. A day reported in chat and left out of the journal has happened twice.
- **Do not conclude from a handful.** Three times in one session I stated a conclusion from two to six
  samples and the next measurement reversed it. Say the sample size and what the number rests on.
- **Write the expectation before the reveal.** Every time that was skipped, the explanation arrived after
  the number and fitted it too well.
- **An abnormal count stops the report** until it is explained - a zero, an empty file, a rate that will
  not move.
- **When I am wrong, correct the record, not just the sentence.** The file that carries the wrong number
  is the thing that misleads the next session.
- **Report what the measurement says even when it contradicts me**, and say which part is measured and
  which part is my reading.
- **The archive is old data.** Nothing in `docs/archive/`, `research/archive/` or any `archive` folder
  decides the present - not a number, a verdict, a rule or a lesson (owner, 2026-10-28).
- **Ask before:** git push, any deploy, starting DEMO or LIVE, anything touching the owner's accounts, and
  any change to risk. Committing per step by explicit paths is fine without asking.

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
