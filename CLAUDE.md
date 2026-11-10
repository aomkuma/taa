# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Read first

- **`docs/HANDOFF.md`** - **start here in a new session**: where the work stands, the current numbers,
  where the next day resumes, and what is still open.
- **`docs/START_HERE.md`** - what this repository is now, what we are doing, and the one number everything
  is judged against.
- **`docs/HOUSE_RULES.md`** - how to work here. Every rule in it was paid for with a real mistake.
- **`eye/BOT_RULES.md`** - the Fibonacci bot's rules in force (build from this); **`eye/BOT_RESEARCH.md`** -
  every research run on it with its result (`eye/research/<variant>/` holds each run's ledger and log).
- **`eye/ZONE_RULES.md`** (the run-zone setup) and **`eye/ZONE_LIVE.md`** (its runner for LIVE) - the work now
  (HANDOFF section 1).
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

So the old code still builds and its tests pass, but **no strategy is enabled in `config.yaml`, in any lane.**
A started engine sends no order. **The one thing that sends orders is the run-zone runner** (`app/zone`,
`python -m app.cli zone run`; `eye/ZONE_LIVE.md`), released 2026-11-10 - its state is in HANDOFF. DEMO and the hourly observer are disabled in Task Scheduler. The LIVE gate
in `.env` is open (set on the owner's word, 2026-11-04, for the zone runner - HANDOFF); nothing is started on LIVE
without the owner's explicit word.

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
.venv\Scripts\python eye/money.py                       # the record in money: 200 USD, 0.01 lot (args: balance lot)
.venv\Scripts\python eye/bot_config.py seed --market XAUUSD --set default --by <who>   # once: the bot's parameters (data/bot_config.db)
.venv\Scripts\python eye/bot2e.py --from 2026-04-06 --to 2026-04-07 [--set default]   # the bot, bar by bar (eye/BOT_RULES.md)
.venv\Scripts\python eye/score.py bot_ledger.csv; .venv\Scripts\python eye/money.py --ledger bot_ledger.csv
```

The run-zone setup (`eye/ZONE_RULES.md`, `eye/ZONE_LIVE.md`):

```powershell
.venv\Scripts\python eye/zone_bot.py [--start 2023-10-01] [--end ...]        # the simulation on stored bars (FBS-Demo)
.venv\Scripts\python eye/zone_paper.py [--update] [--since "2026-11-10 12:00"] # paper beside LIVE (FBS-Real bars)
.venv\Scripts\python -m app.cli zone status                                  # the runner: account, setup, orders
.venv\Scripts\python -m app.cli zone run --market XAUUSD --set default       # SENDS ORDERS in the mode of .env - the owner's word only
.venv\Scripts\python -m app.cli zone stop [--now]                            # stop it (Ctrl+C in its window = stop)
```

The method is **real trading days, one at a time** (`eye/METHOD.md` 2c): a date taken whole, the owner's
three windows walked in order - Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai - and every
window written into `eye/sessions.csv` whether it produced a trade or not. `eye/sheets.py` and
`moments.csv` are the retired clock-sampling design, kept because the control trades came from it.

The principle the trading holds to is **the owner's: price structure + divergence + counting the peaks**
(`eye/METHOD.md` 2e), dictated by the owner on 2026-10-28 and written there in full - do not ask it again.
Anything new about it is the owner's to state: ask, and write the answer in their terms; never fill it in
from your own reading of the charts (METHOD 2d was exactly that, and is on hold). An example the owner
gives is a principle to generalise, never a rule with its numbers. **The owner's pattern words are not
the textbook's: in the owner's usage an M is a buy (it forms coming down into a support) and a W a sell** -
read them the owner's way, and never fill in a side or a trend reading the owner did not give. On 2026-10-29 the
owner added **their Fibonacci** (METHOD 2e, "The owner's Fibonacci"). **A question the owner asks, or a chart the owner shows as an
example, is supporting information, never a rule; the documents record only the rules and what to do.**

**Nothing is committed without `ruff`, `mypy`, `bandit` and the tests green**, and nothing is pushed,
deployed, started on DEMO or LIVE, pointed at the owner's accounts, or changed in risk without asking first.
Committing per step by explicit paths is fine without asking.

## How the system is developed (the owner, 2026-10-29) - every change, in this order

1. **Discuss** with the owner, and **conclude** - what was decided, in the owner's words where they are
   the owner's.
2. **Record** it in the documents (rules and what to do only - no questions, no history): METHOD 2e for the
   owner's rules, the bot's spec for its rules (`eye/BOT_RULES.md`; the zone bot `eye/ZONE_RULES.md`, its runner
   `eye/ZONE_LIVE.md`), `docs/HANDOFF.md` for the state; how a rule came to be goes in the commit message.
3. **An agent reviews the documents** (Codex, read-only) - ambiguities, contradictions with the owner's
   rules, attributions, acceptance cases checked against the stored bars. Fix the documents; review again
   until a review finds nothing.
4. **Another agent writes the code** (a developer agent: **complex work - the zone runner, a fix
   across the runner - is written by Opus**, never handed to Sonnet because Opus is busy or at its limit - wait for Opus
   and say so; Sonnet only for small, separate pieces such as new files or tests; the owner 2026-11-03, again
   2026-11-08) from the reviewed spec only - no bot or research
   run, gates green (ruff, mypy, the bot's tests).
5. **Another agent reviews the code** against the spec (Codex, read-only). **Every fix after a review goes
   back to review** until a review finds nothing.
6. **Run the tests**: the full suite, then commit by explicit paths. Tests green means **the code does what
   the spec says** - never "passed" (the owner, 2026-10-30). The full suite runs **once, at the end of the whole
   job** - never between pieces; while building, only the targeted test files, one at a time (the owner,
   2026-11-01 / 11-02, told twice; routine engineering choices are mine, not questions for the owner).
7. **Check the reading against the market** (the owner, 2026-10-30: *"passing is the bot reading the chart as
   close to the market as possible"*): every reading a change touches (the H1 state, the M5 trend, the leg...) is
   run on its own, **without trading**, on the stored bars of **several months**, drawn over the candles (the
   side it allows, its edges and pivots), and judged by eye - Claude first, then the owner. A reading that
   is wrong in any month goes back to step 1. **Passed** is the owner's word on these drawings.
8. Only then, with the owner's word, a **trading run** - and its trades drawn (`eye/draw_trades.py`) and
   judged by eye against the rules before any number is believed.

**Every result is recorded the moment it is measured** - `eye/BOT_RESEARCH.md` for measurements and drawings,
`docs/HANDOFF.md` for the state - and committed; a result reported in chat only is not recorded (the owner,
2026-10-30). Claude coordinates, checks every agent's result itself, and never skips a step because a change
looks small.

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
  not move, a round, repeated or impossible value; look before reporting, never invent an explanation.
- **When I am wrong, correct the record, not just the sentence.** The file that carries the wrong number
  is the thing that misleads the next session.
- **Report what the measurement says even when it contradicts me**, and say which part is measured and
  which part is my reading.
- **Fix the root, not the symptom** (owner, 2026-11-03). After every review, group the findings by the question
  they ask; two of the same kind in different places -> stop patching, write the one rule in the spec, build it as
  one function used everywhere, and tell the owner. Passing findings on one at a time cost a whole day on the zone runner.
- **Check a spec before review; every finding is fixed** (owner, 2026-11-03: *"the small ones should all be cleared,
  and the spec should not miss so often"*). Before a spec or a spec fix goes to review, check each rule against the
  reference code it must agree with (for the zone runner: `simulate_setup`'s in-bar order, `tests/zone_replay.py`)
  and walk its edge cases (equal times, boundaries `>` / `>=`, restart, partial fills) myself. **A release waits only
  for the severe findings** (the owner, 2026-11-09: *"get the first release out; leave the non-severe defects for
  now"*): a review with no P1 is clean enough to release; its P2 / P3 findings are recorded in HANDOFF as known
  defects and fixed after the release.
- **Documents hold only what is used** (owner, 2026-11-04: *"documents should hold only what is used, not every
  history"*). A spec states the rules in force; HANDOFF the current state and what to do next. Review rounds, counts and
  how a rule came to be stay in `git log` and the commit messages, never in the document. **Before adding to a
  document** (this file included), read it whole and check the addition against it (owner, 2026-11-07): already
  there -> merge into the existing line; agreeing with it -> fine; contradicting it -> settle which holds (the later
  word of the owner; else ask) and fix the other line in the same change.
- **Think the plan through myself** (owner, 2026-11-07: *"be sharper - I should not have to keep reminding you"*).
  Before announcing next steps, check them: the order (the review before the tests; a run whose result a coming
  review may throw away goes last - **the replay and the full suite only after a code review has found nothing**,
  never beside an open review or fix "to save time"; the owner, 2026-11-07 and twice 2026-11-09: *"all the code
  fixed and all the review done - only then run the tests"* - every finding of every part, the normal case and the
  safety net alike, fixed and reviewed clean first; the owner had to say it four times - **never propose, ask about
  or prepare a way round this order**), what can run side
  by side (a read-only review beside a long run whose result it cannot throw away), the scope (only the month and
  frame that will trade), and any stalled agent or stale process - at once, unasked.
- **An instruction the owner gives goes here at once**, not only into memory (owner, 2026-11-07: *"you still had to be
  told"*). Memory is this machine's only and its files are read only when recalled; CLAUDE.md is read whole every
  session.

## The owner's standing instructions (each was given after a real mistake)

- **Numbers** (2026-10-15, 10-19): cross-check every number a second way (a net against the sum of its trades, a count
  against the summary; recompute a metric a second way and re-derive sample trades from the ticks).
- **Answer from the real candles** (2026-10-19): never make up a number or data; every claim about price comes with its
  candles (dates, Thai times) drawn, every number from a run with its script and output file named.
- **Pooled numbers are not believed** (2026-11-01): for any new form of the owner's method, draw single trades first
  (losers first, one image at a time) and ask what the owner sees; in every simulation assert a stop exit has R < 0.
- **Costs are the spread only** (2026-10-20): a buy fills at the ask, a sell at the bid; slippage is a parameter at 0.
- **Gold pip = 1.00 USD of price** (2026-10-17); at 0.01 lot about 1 USD. The owner's targets: at least 5 pips; the
  largest timeframe H1.
- **The risk per trade is the owner's choice** (2026-10-17): never list it as a concern; judge setups by R per trade,
  consistency and drawdown in R.
- **Direction rates are ~50 % by nature** (2026-10-29/30): never report one as a finding; find which conditions put a
  signal on the winning side, and judge by R per trade.
- **Audit the core readings first** (2026-10-29): when results are thin or odd, measure the side and the levels the bot
  reads against the market's own movement before tuning anything.
- **Before designing**, list the owner's standing instructions the design touches and what each forces it to be.
- **Ask, don't guess** (2026-10-09): restate my reading in one line and ask when the owner's meaning is unclear,
  especially a trading idea. **General concepts** (a range, ZigZag) I research from outside sources first (2026-10-30);
  only the owner's own reading is theirs to state.
- **Skip means skip** (2026-10-11): a topic the owner parks stays out of reports and questions until they raise it.
- **Codes get a Thai name** in every Thai message, the first time each appears (2026-10-21).
- **Agents** (2026-10-30): Claude coordinates and checks every result itself; the developer agent (step 4) builds
  piece by piece; Codex reviews read-only with **`-m gpt-6.1-sol`** (2026-11-01; `codex.exe exec -m gpt-6.1-sol --sandbox
  read-only -`, prompt on stdin). Before reporting what an agent is doing, read the process command lines
  (`Get-CimInstance Win32_Process`) and the mtimes of its files - agents stop silently after a freeze or a shutdown
  (2026-11-03). Never run a mutation check on a file an agent is editing or reviewing.
- **"Not available" needs evidence**: check services, ports, PATH and the sibling projects before saying a tool is
  missing.

## Working with the owner

- Chat in **Thai**. Documents, code and comments in **English**. Times to the owner in **Thai time**, read
  with PowerShell `Get-Date` (Git Bash `date` is wrong on this machine).
- The owner's goal is fixed: **at least +0.15 R a trade after costs**. The method is theirs to direct.

## Architecture, while the code exists

`core` → `config`/`security` → `storage` → `broker` → `market_data` → `indicators`/`evidence` → `strategy`
→ `risk`/`engine` → `execution`; `sync` → `web`/`worker`. Enforced by `tests/unit/test_architecture.py`:
MetaTrader5 only inside `app/broker`, order functions only there, no wall-clock reads outside
`app/core/clock.py`, strategies pure. A new package must be added to that test's `LAYERS` table.

Decisions use **closed bars only**; MT5 epochs are broker server time and convert through `ServerClock`;
everything internal is timezone-aware UTC. Secrets and safety flags come from the environment, parameters
from `config.yaml` - except the eye bot's `Params`, read from `data/bot_config.db` (owner, 2026-10-31;
`eye/BOT_RULES.md`, Parameters). Conventions in `docs/archive/CODING_STANDARDS.md`.
