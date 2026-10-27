# Session handoff

Last updated: 2026-10-27 21:30 Thai. Read the **last section first** - it is the current state (the AI trader
replays, the three bots, the open breaker question). The sections before it are the record of earlier days and
are kept for their detail, not as the present picture. This file holds **state only**:

| What | Where |
|---|---|
| Rules and conventions | `CLAUDE.md`, `docs/CODING_STANDARDS.md` |
| Design | `docs/PLAN.md`, `docs/PLAN_LEARNING.md` |
| Progress | `docs/TICKETS.md`, `docs/TICKETS_LEARNING.md` |
| Setup OWN | `docs/OWN_SETUP.md` (state), `docs/OWN_SETUP_ROUNDS.md` (rounds 1-17) |
| The research of 2026-10-18 onward | `research/2026-10-18-moments/agents/` (`CHECKLIST.md`, `TEAM.md`, `precursors/notes.md`) |
| The owner's own trades and readings | `docs/OWNER_TRADING.md` |
| Stopped setups | `docs/archive/` |

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

````text
Continue TAA (C:\Users\korap\taa). Chat with me in Thai and give times in Thai time (UTC+7), always taken from
`date -u` (never write a time ahead of the clock). Docs and code stay in English. Follow CLAUDE.md and the
memory rules.

Read first, in order:
1. docs/OWNER_GOALS.md
2. docs/HANDOFF.md
3. research/2026-10-18-moments/agents/CHECKLIST.md (every method tried, with its verdict and lesson)
4. research/2026-10-18-moments/agents/TEAM.md (the roles)
5. the tail of research/2026-10-18-moments/agents/precursors/notes.md

Your role: the researcher, measurer and coordinator. You research the opportunities and probabilities, and turn
them into designs and prompts for the developer agents. You measure everything they deliver:
- re-run their tests;
- plant your own bugs;
- re-derive trades from the raw ticks;
- check results against my reading of the real candles, not only against unit tests.
You also commit per step by explicit paths (never push), keep CHECKLIST.md current, and read the exam
(2026-04-18 .. 2026-10-17) yourself, once per frozen rule. No agent ever loads the exam.

The goal is fixed: at least +0.15 R a trade after costs (spread only; slippage is a parameter defaulting to 0) in
both learning parts (P1 2025-10-18 .. 2026-01-15, P2 2026-01-16 .. 2026-04-17), about 2-3 trades a day, in my
windows (Asia 07-09 Thai, London 13-14 Thai, the NY open up to + 4 h). The method is flexible.
- A loss never stops the work: tick it FAIL with its lesson and add the next method.
- Before discarding a method, try the opposite side, a wider stop and a nearer target.
- If a method pays, find the market states where it pays, and cut its weight in the others.
- Answer only from real candles; never make up numbers. No coin / "50-50" verdicts.

State (2026-10-20 12:40 Thai):
- PLAN-1 (Asia B2 + the London 13:00 ORB + the NY 08:30 straddle, one position at a time, about 2.3 trades a
  day) is frozen for the one exam read. Spread only: +0.252 / +0.140 R; weighted by the D1 state +0.341 /
  +0.191.
- The four agents stopped on the weekly API limit (reset 2026-10-21 15:00 Thai). Start them again as new agents
  from their briefs (*_PROMPT.md + their own DEV_LOG / AUDIT / PROPOSALS), one task each as listed in
  HANDOFF "Next work".
- DEMO is paused (resume only on my word); LIVE stays off.
````

---

## Update 2026-10-20 18:27 Thai (read this before "Current state" below, which is the 12:40 picture)

- **Measured and committed today:** the auditor's closed-bars downloader (eeca5a9); auditor rounds 2-3 (win = pnl > 0,
  `plib.load_learning()`, plan1 audited PASS); dev2 V3-1 (4a10c58); the strategist rows 39 / 45 (rows 42-45);
  dev1's PLAN-1 runner (915e8fe).
- **The PLAN-1 exam read (row 46, done once):** unweighted +0.129 R on 330 trades (2.54 a weekday), +344.87 USD at
  0.01 lot, DD 108.12. NY straddle +0.285, Asia B2 +0.105, London ORB +0.023. The state weights lowered it. PARTIAL.
- **SW-20, the own-result switch (row 47):** FAIL on 2021-09 .. 2023-10; it lowers PLAN-1 in every period.
- **NS-1 (row 48):** the 08:30-NY straddle on release days only: +0.164 R pooled on 2021-09 .. 2025-10 (M1), positive
  4 / 4 years, other days about 0 - but M1 flatters release days by +0.193 R against the ticks. **OPEN: needs old ticks
  (08:25-09:05 NY, about 186 days) from MT5; asked the owner for the go-ahead** (it fills the terminal's Bases on D:).
- **The owner (2026-10-20):** windows and present-only rules "flexible within reason"; the measurer defines the counts
  (top test = a visit to the box's top quarter after leaving it by >= S); every TF's structure is read with its own
  swing size on the M1 path (primary), the candle reading secondary. Trade 4 corrected in `docs/OWNER_TRADING.md`
  (box 1 = the entry, stop 4180; box 2 = the base on the 50 %, stop above 4160; target Fibo 23.6 about 4102).
- **Agents:** dev2 V3-2 (stopped mid-build, resume with SendMessage after 22:00 Thai or restart from `DEV2_PROMPT.md` +
  the end of `dev2/DEV_LOG.md`); the strategist idle; the auditor idle; dev1 paused by the owner.
- **Credits:** the owner noticed the limit came fast; four agents in parallel cost about 1 M tokens an hour - run at
  most two at once.

## Current state (2026-10-20 12:40 Thai)

### Setup OWN research: the team (`research/2026-10-18-moments/agents/TEAM.md`)

The main session is the researcher / measurer / coordinator. Four background agents each write only in their own
folder, and everything is relayed through the main session.

| Agent | Folder | Brief | Last state |
|---|---|---|---|
| The first developer | `dev/` | `DEV_PROMPT.md` | Task D done and measured (CHECKLIST rows 40-41). Assigned next: row 38, the PLAN-1 runner `dev/plan1.py` - not started |
| The second developer | `dev2/` | `DEV2_PROMPT.md` | V3-1: the trade-size swings found 15 / 15 of the owner's turns on 2026-10-19, plus the 17:20 range break and the 14:30 fake break. **Not reported, not measured, not audited** |
| The auditor | `audit2/` | `AUDIT_PROMPT.md` | Four faults fixed and committed (f9163e0): the download, the ZigZag start-up, the midnight cut, the drawdown from 0. No learning-part R changed. Item 3 (the downloader stores closed bars only) is **uncommitted** in `app/market_data/history_download.py` + `tests/unit/test_history_download.py`, plus `audit2/out_closed_before.txt` and `out_win_*.txt`: the main session must review it first (tests, ruff, mypy, bandit) |
| The strategist | `strategist/` | `STRATEGIST_PROMPT.md` | `PROPOSALS.md`. Assigned next: row 39, the transformations of the FAIL rows and the state weights per piece - not started |

All four failed on 2026-10-20 at about 12:35 Thai on the weekly API limit (reset **2026-10-21 15:00 Thai**). Their
task ids are gone with this session: start them again with the Agent tool, each with its brief and its own log.

### Results (the checklist, `agents/CHECKLIST.md`, 41 rows)

The PARTIAL leads (P1 / P2 R; costs as noted in the row):

| # | Method | P1 R | P2 R |
|---|---|---|---|
| 21 | B2 at the owner's H1 levels, Asia 07-09 Thai | +0.074 | +0.182 |
| 22 / 40 | London 13:00-Thai ORB | +0.206 | +0.120 |
| 40 | London 13:00-Thai ORB, H1-level + season variant (16 trades a part) | +0.306 | +0.604 |
| 23 | The reclaim of a common level (19 / 22 trades) | +0.312 | +0.310 |
| 24 | The NY 08:30 straddle, 30 min | +0.459 | +0.114 |
| 36-37 | **PLAN-1**, the daily plan (spread only) | +0.252 | +0.140 |
| 36-37 | **PLAN-1** weighted by the D1 state (spread only) | +0.341 | +0.191 |

Everything else is FAIL, each with its lesson: LV3, V2, the probability model, the level break, B2 all-day,
break-and-retest, D2, and others.

- **PLAN-1** is frozen in CHECKLIST.md, with two declared weight variants. The exam has not been read yet.
- **The market state** (`precursors/regime.py`, the D1 20-day efficiency, P1 terciles 0.116 / 0.264):
  - the range pieces (Asia B2, the London ORB) pay in sideways / mixed states and lose in a trend;
  - the NY straddle pays in a trend.
- **Costs: the spread only** (owner, 2026-10-20). Rows marked "0.07 slip" still include the old entry slippage
  (about +0.01 R at the plan level).

### The owner's framework (2026-10-19 / 20; memory + `DEV2_PROMPT.md` "V3 design")

- **Side:** the D1 side from the H1 -> D1 structure.
- **Trend:** M15-H1.
- **Entry TF:** M1 / M5 / M15, chosen by the volatility so the move fits the TP / SL.
- **The entry:** a chart pattern at a level, at least on M1. Exit on the TF you entered on.
- **Windows:** opens run 30-60 min; NY up to + 4 h, often choppy for the first 1-2 h.
- **Trade 4** (the owner's live sell at 4169 on 2026-10-19) is in `docs/OWNER_TRADING.md`. It is the V3 acceptance
  case.

### The bot and the account

- **DEMO paused** since 2026-10-19 (no open positions). F1 CONF-72 v2 + S2 stay in `config.yaml` (lanes `own`,
  `news`) but trade only when the owner resumes the stack. LIVE is refused until Phase 14 and the owner's go-ahead.
- **Data:**
  - gold M1 (`data/history`) runs to 2026-10-19 22:40 Thai: MT5 was reopened read-only on 2026-10-19 for the live
    day;
  - gold ticks (`data/ticks/XAUUSD`, from 2025-10-01) run to 2026-10-16;
  - the older stores are as listed under "Local environment".
- **Code:** the last full pytest was 2026-10-18 (3,392 passed). Since then only research files and the auditor's
  `history_download.py` fixes have changed. Latest migration **0043**.

## Next work

1. **Review and commit the auditor's item-3 change** (the closed-bars-only downloader):
   - run the targeted tests, ruff, mypy and bandit;
   - commit by explicit paths.
2. **After 2026-10-21 15:00 Thai, restart the agents:**
   - **dev1, row 38: `dev/plan1.py`, the PLAN-1 runner.**
     - Costs are the spread only; slippage is a parameter defaulting to 0.
     - With slippage 0.07 it must reproduce `precursors/out_combo.txt` and `out_regime.txt`.
     - It has an exam switch that only the measurer uses.
   - **dev2: finish V3-1 and report.**
     - The swings, the structure per TF (D1 / H4 / H1 included) and the side / trend columns.
     - The 2026-10-19 acceptance, with written definitions for dev1's cross-check.
     - Then V3-2 per the "V3 design".
   - **The strategist, row 39:**
     - the transformations of the FAIL rows (the opposite side, the stop x 1.5 / x 2, a nearer target);
     - the state weights per piece, chosen on P1 and checked on P2 and the older years.
   - **The auditor:**
     - item 1 (wf.weekly win = pnl > 0);
     - item 4 (`plib.load_learning()`);
     - then audit dev2's `swings.py`.
3. **The PLAN-1 exam read** (once, by the main session) when `plan1.py` is measured. Report both declared weight
   variants, week by week, with the worst loss, the streak and the drawdown in USD.
4. **The owner's answers (2026-10-20):** London = the 15-minute ORB at 13:00-13:14 Thai; the real account's gold
   spread is 20-30 points; NY 08:30 is one of the windows.
5. **Engine work, only after a rule passes:** port the passing pieces into `app/strategy/`.
   - The bot's `app/indicators` are textbook formulas, not MT5's: align them first (`foundation.py`).
   - Run the full pytest / vitest once with the stack paused.
6. **Older items, still open:**
   - merge the `s1-cost-floor` / `setup-groups` branches or not;
   - `demo-track` once DEMO runs again;
   - **owner, before LIVE:** the DEMO soak, the drills (TAA-1403), the go-live checklist and the explicit go-ahead.

### Background (kept short; details in `docs/OWN_SETUP_ROUNDS.md` and `docs/archive/`)

- **Every setup before Setup OWN stopped** on 2026-10-17 (V1, F1, S1, TS; `enabled: false`, parameters kept).
- **The unmerged worktree branches** under `.claude/worktrees/`, both green on their branch; the owner decides:
  - `s1-cost-floor`;
  - `setup-groups`.
- **Weapon 4, RUN-A and the AI chart reader:** research only, stopped (see `docs/OWN_SETUP_ROUNDS.md`).

## Local environment

- **Demo stacks** (`scripts\start-demo.cmd`, details in the script header):
  - Default: FakeMT5 PAPER engine, web `http://127.0.0.1:8000`, `data/taa_cloud.db`, `.env.demo`.
  - `-Mt5 -Demo` (paused since 2026-10-19; resume only on the owner's word): the real MT5 terminal and FBS demo account, DEMO orders
    (`TRADING_MODE=DEMO`, `ENABLE_DEMO_TRADING=true` set for that process only; `.env` keeps PAPER), web
    `http://localhost:8001` with `data/demo/cloud-mt5.db`, engine db `data/demo/engine-mt5.db`, health
    `http://127.0.0.1:8766/health`, config generated at every start from `config.yaml` into
    `data/demo/config.demo-mt5.yaml`.
  - Web user `aomkuma` (OWNER) in both databases; `app.cli web reset-password` resets it.
- **MT5:** a dedicated portable terminal at `C:\MT5\taa-bot` (its `Bases` is a junction to D:). The owner also
  trades the demo account by hand (manual positions show in the PWA).
  - **Spreads on the owner's account:** gold ~30 points, currencies ~10.
  - **The owner's real account** (never connected): 150 USD at 1:2000 (2026-10-15). Its history only from a
    report the owner exports (MT5 History, Report).
- **History:** `data/history/FBS-Demo/<symbol>/{M1,M5,M15,M30,H1,H4,D1}.parquet`: M5/M15/H1 2025-10 .. 2026-10
  for 29 symbols (28 FX pairs + gold); H4/D1 from 2024-04; gold M1 the whole year, FX M1 only from 2026-07-08.
- **Research:** configs `data/research/config_*.yaml` (not in git); backtest outputs `data/backtests/inv/`;
  scripts `research/2026-10-11-pre-run/`, `research/2026-10-14-chart-read/`, `research/2026-10-15-day-trade/`.
- **PostgreSQL 16** (service `postgresql-x64-16`, shared with other projects): role `taa`, database
  `taa_test`, URL `TAA_POSTGRES_URL` in `.env`. Never touch other projects' databases; never clean up
  databases by `LIKE` pattern (`_` is a wildcard).
- **Browsers:** Chrome and Edge; Playwright drives Chrome (`channel: 'chrome'`).

## Gotchas

- **Backtests:**
  - `CONFIG_FILE` picks the config; `--lane NAME` backtests one lane of it alone.
  - `MAX_ACCOUNT_DRAWDOWN_PERCENT=50` in the command's environment (`.env` sets 10).
  - `ALLOWED_SYMBOLS` for symbols outside `symbols.allowed`; without it: SYMBOL_NOT_ALLOWED.
  - `PYTHONUNBUFFERED=1` to see progress.
  - `--symbols` is comma-separated.
  - A bar touching both levels counts as the stop.
  - `--preset aggressive --risk R --balance B` for the aggressive preset (local CLI only).
  - A worktree has no `data/` or `.env`: pass `--data C:/Users/korap/taa/data/history` and copy `.env`.
- **Memory (16 GB, commit limit ~17.8 GB):**
  - At most 3-4 backtests at once; heavy replays two at a time at idle priority.
  - Never run full test suites next to the stack: on 2026-10-07 that crashed the engine (SQLite
    `disk I/O error`).
  - Run vitest files one at a time when the machine is busy (workers die with exit 3221226505).
  - `npm run build` with the stack paused.
- **Laptop sleep** drops the MT5 IPC link; three UNHANDLED_EXCEPTION trips in a day **latch** the breaker
  (manual `breaker reset` with `ENGINE_DB_URL=sqlite:///data/demo/engine-mt5.db`, owner's approval). Pause the
  stack before closing the laptop.
- **`.env` overrides `config.yaml`:** `ALLOWED_SYMBOLS` overrides `symbols.allowed`.
- **Tests that read the repo's `config.yaml`** (doctor, scanner, strategies API, catalog tests, the API samples)
  break when it changes: rerun them after every config edit.
  - Regenerate the samples with `TAA_UPDATE_API_SAMPLES=1 pytest tests/web/test_api_samples.py`.
  - A new strategy parameter changes the samples too.
- **Heartbeat schema is strict** (`extra="forbid"`): when the engine's heartbeat gains a field, restart the
  **web** first, then the engine. `demo-tasks.ps1 -Resume` starts web first.
- **After a frontend rebuild** the open PWA keeps the old version until the "new version" banner's Reload (or a
  hard refresh, or all tabs closed).
- **`ReasonCode` enum lines must stay on one line:** the frontend parity parser reads them, so keep their
  comments short.
- **Windows file writes:**
  - Bash heredocs/printf eat backslashes in Windows paths: write such files with the Write tool or a small
    Python script.
  - `Path.write_text` without `newline="\n"` writes CRLF (the repo is LF).
  - `scripts/tickets.py` may write CRLF: convert back.
- Research loaders select columns, not ORM entities: scratch replay databases keep their old schema.
- **Research before engine runs** (2026-10-15): a harness that reproduces the engine's backtest trade for trade
  (`box_harness.py` checks parity first) measures a year in minutes; run read-only research with
  `PYTHONDONTWRITEBYTECODE=1`. The venv has no plotting library; the system `python` has Pillow.
- **Cloud history lags:** the DEMO cloud database gets M15/H1 bars late (an hour or more); check the last bar's
  time before reading "now" from it.
- **Net vs R:** a gold trade at the minimum lot can risk ~3x a currency trade, so net and R can disagree
  (F1 resume March: +0.157 R, net −80); judge by R.
- Asking MT5 for old ticks (`copy_ticks_range`) downloads whole months into the terminal's `Bases`; keep any
  backfill bounded (`ticks probe` has a free-disk guard).
- Don't edit Python or migration files during a full pytest run (the migration-parity test reads them).
- In Engine tests, `run(max_cycles=n)` ends with `shutdown()`: read the heartbeat during the run.
- **Frontend:**
  - Passing the typed i18next `t` as a parameter fails with TS2589: put the text in a small component that
    calls `useTranslation()` itself.
  - `z.looseObject` types keys as `string`: use `z.object` where the page indexes translation keys by field.
  - Windows is case-insensitive: don't name a module `gauge.ts` next to `Gauge.tsx`. A file exporting a
    component exports only components: keep helpers in `*Model.ts` files.
  - A new page: add it to `src/app/shell/nav.ts` and `src/app/routes.tsx`; engine queries go under
    `engineKey(id)`.
  - Secrets (engine keys, TOTP) never go through TanStack mutations or queries: call `apiPost` directly.
  - Template literals in `new RegExp(...)` drop backslashes: use `String.raw`.
  - A new strategy parameter or reason code needs TH/EN texts (`strategies.param.<name>` in `common.json`,
    `codes:*`).
  - i18next: a `count` parameter triggers plural lookups; name it `n` for plain numbers.
  - API samples must be stable: pin wall-clock stamps and random ids in `tests/web/test_api_samples.py`.
- Python: docstrings over 110 characters fail ruff E501. Long edits are safer as a small Python script.

## Decisions the user may want to revisit

- **The aggressive preset at 7.5 %:** 5 % has a much lower chance of the 60 % stop (ruin table, PLAN §A36).
- **The box breakout** (`setup_breakout_box`) is off and parked for a fresh analysis; Asia-only gold was the one
  positive cell (~10 trades a year).
- **Manual trades on the bot's account** count toward the bot's limits (`risk.foreign_positions_policy:
  count`). With a large manual trade the bot opens nothing.
- **Alert metric** is win probability (needs closed shadow outcomes for calibration); setup strength works from
  day one.
- `execution.entry_plans: false`: the engine sends one order per signal whatever the PWA's split-entry choice
  says (SETUP_REVIEW: scale-in with a 0.5 ATR spacing put parts into the noise, TAA-1209).

## Open items needing the user

- **Before LIVE:**
  - the DEMO soak and the drills on the LIVE machine (record table in `docs/RUNBOOK_LIVE.md`);
  - the go-live checklist, a separate `ENGINE_DB_URL` for LIVE, and the MT5 password in Windows Credential
    Manager;
  - the explicit go-ahead. Only the owner sets `ENABLE_LIVE_TRADING` and the confirmation phrase.
- Remove the merged worktree `.claude/worktrees/agent-a8b3410ffe49fb0d1` (it holds a copied `.env`).
- **AI (optional):** an Anthropic API key in `.env` (`AI_PROVIDER=anthropic`, `AI_API_KEY`), starting with
  `AI_MODE=advisory`.
- Phase 11 (Railway) only with an explicit go-ahead; subscriptions only after legal review
  (`docs/COMPLIANCE.md`).
- `VAPID_SUBJECT` in `.env` is a placeholder; the owner's account profile on `/account` lets alerts carry money.

## Update 2026-10-22 07:45 Thai: PLAN-1 on DEMO

- **Running since 2026-10-22 00:43 UTC (07:43 Thai)**: lane plan1 (setup_plan1_orb, setup_plan1_b2, setup_plan1_b2m5,
  setup_plan1_ny) on the FBS demo account (balance 1,066.21 USD), DEMO mode, the owner's AGGRESSIVE 7.5 % profile
  (from the cache). F1 / S2 off. Frozen rules + the D1 ATR(20) >= 60 regime switch (journal/PLAN1_JOURNAL.md,
  CHECKLIST 61-63).
- **It runs from a separate worktree `C:\Users\korap\taa-demo` at 857fd20** (main keeps changing under the agents).
  `.venv`, `data` and `logs` are junctions to the main repo; `.env` / `.env.demo-mt5` are copies. Worktree-only edits
  (uncommitted): `config.yaml` high_risk.setups + the 4 plan1 strategies, max_consecutive_losses 12, probation_trades 0,
  max_account_drawdown_percent 40; `.env` MAX_ACCOUNT_DRAWDOWN_PERCENT=40.
- Started with `scripts\start-demo.ps1 -Role engine -Mt5 -Demo` in its own window (web / worker on :8001 from the same
  worktree). The Task Scheduler tasks still point at the main repo and stay paused (`data/demo/paused.json`): do not
  `-Resume` them while the worktree runs. Health: http://127.0.0.1:8766/health.

---

## Update 2026-10-27 11:30 Thai: the AI trader replays, and three bots split by market

State only; the reasoning is in the memory rules and `app/strategy/kb.yaml`.

### What changed since 2026-10-22

- **DEMO is paused** (owner, 2026-10-23). The `taa-demo` worktree is not running. Past ticks are replayed
  instead, day by day as a journal.
- **The AI trader is built and runs through the engine's own path** (TAA-1804 .. 1807, `app/ai/`,
  `app/engine/ai_trader.py`, `app/engine/ai_replay.py`): the watcher wakes the AI on closed M1 bars, the AI
  answers one step decision, the brakes (`app/ai/trader.py`) veto or halve it, the `ai_trader` strategy turns
  it into an order, and the order goes through the decision engine like any signal. One code path for the
  replay and for PAPER / DEMO (PLAN §A37).
- **The answerer is now the Codex CLI with `gpt-6-luna`** (owner, 2026-10-26), for the replays and for the
  engine: `AI_PROVIDER=codex`, `AI_MODEL=gpt-6-luna`, `AI_MODE=advisory`, no API key. The Claude CLI path is
  still there (`ClaudeCLIProvider`); `--ai-cli` picks by the executable's name.
- **The replay journal of 06-09 Jul 2026** is in `research/2026-10-24-replay/` (`ledger.csv`, `day_*.md`,
  `ISSUES.md` 1-38). Accounts 300 and 100 USD. Days 1-3: +0.21 R, -2.43 R, -1.82 R; the 300 account 300 ->
  247.64. Day 4 was stopped part-way. The side was right on nearly every trade; the losses came from entering
  into a push still running toward the stop, which is now a code gate (`run_share` 1.2 over 60 minutes).
- **Rules added to the code from the owner's corrections** (each with hand-worked tests and planted bugs; 48
  of 48 caught): the stop past the liquidate zone is bounded (`app/strategy/liquidity.py`), C4 moves a short
  stop out or vetoes, C6 counts M5 closes back across the trade's own level, C9 blocks a side after its
  take-profit, and **no entry on the first touch** - an armed order waits for a signal at the level, read on
  M5 structure or an M15-H1 candle (`app/strategy/confirm.py`).

### The three bots (research, 2026-10-26/27)

`research/2026-10-26-three-bots/` - the owner's design: three bots, one account, each trading its own setup at
the same time; at most two can be in the market, since the two trend bots are each other's opposite.

| bot | what it trades | 12 months to 2026-10-23 |
|---|---|---|
| DOWN | an H1 down leg, price back 38-79 %, a quiet M5 box, an M5 close out of it | 38 trades, +0.280 R |
| RANGE | a flat H4 box (ZigZag on H4), an M5 close out of the box | 41 trades, +0.488 R |
| UP | the mirror of DOWN | 23 trades, +0.133 R |
| all three | one account, per-bot exits | 102 trades, **+0.331 R**, worst drawdown -9.4 R |

Known weaknesses, measured: dropping the best 5 trades of 102 leaves +0.092 R; the parameters were chosen on
the same 12 months; 8.5 trades a month against the goal of a trade most days. **And the engine's own breakers
(`max_drawdown` 10 %, `max_consecutive_losses` 4) trip during the year** - the research harness has no
breakers, so +0.331 R is not reachable as the account is configured today. Not yet resolved.

`DEV_SPEC.md` in that folder is the spec a developer session (Codex) is porting into `app/strategy/` as
`trend_box_down`, `trend_box_up` and `range_break` (ticket TAA-1810), with a parity script against the
research harness. Research checks the result independently before it counts as done.

### Open items needing the user

- The breakers stop the three-bot system inside the measured year. Lower the risk per trade, change the
  system so it loses less in a row, or raise the breaker limits - the last one is the owner's call.
- DEMO stays paused until the owner says otherwise. LIVE still needs Phase 14 and an explicit go-ahead.

---

## The current state, 2026-10-27 21:30 Thai (read this first)

### The engine is LIVE on the DEMO account

`TRADING_MODE=DEMO`, `ENABLE_DEMO_TRADING=true`, account 106732769 FBS-Demo, started 20:59. The owner's
decision that evening: *"go to DEMO, on the real trade account, so we know whether it works."* Seven
strategies load: the four PLAN-1 setups and the three new bots. `ENABLE_LIVE_TRADING` stays false.

- **Risk**: AGGRESSIVE 7.5 % a trade, open risk 15 %, **max 2 positions**, daily loss 15 %, min RR 0.8.
- **The loss breakers are deactivated** (the owner, 2026-10-27: *"every trade already has its stop loss;
  those systems are for human traders"*). What is left is each trade's stop and the kill switch
  (`python -m app.cli kill --reason "..."`).
- **Stop the engine with care**: a forced kill leaves the MT5 Python pipe stuck for about a minute
  ("IPC send failed"); wait and re-run `doctor` before starting again.

### Four things had to be fixed before the PWA could drive it

The owner had set Aggressive 7.5 % in the PWA long ago and the engine never saw it. Four layers:
`sync.enabled` was false; `CLOUD_BASE_URL` was empty; `ENGINE_ID` did not match the registered engine;
and the web had been started with the system Python, so it could not decrypt the rotated engine secret.
All four are fixed. `sync.enabled` stays **false in `config.yaml`** (a fresh checkout and CI must not
need `CLOUD_*`); this machine turns it on with **`SYNC_ENABLED=true` in `.env`** - a new env override.

The trading profile is also **mirrored** in `advisory.preferences.trading_profile` so the engine has the
right numbers even when the pull fails. Those two must be changed together until the pairing is trusted.

### TOTP is off on this machine

`WEB_REQUIRE_TOTP=false` (the owner: *"I am the only user"*). `WebSettings` refuses it when
`WEB_ENV=production`. The sign-in page and the step-up dialog both read `GET /api/v1/auth/options` and
hide the code field when the server says it is not needed; control actions still need the deliberate
step-up confirmation, just without a code.

### The three bots and the H4 gate

`trend_box_down`, `trend_box_up`, `range_break` are enabled in the `three_bots` lane with
`require_edge_side: true`. **The engine has not been restarted since the gate was switched on**, so the
running process is still trading without it. Before restarting, finish the engine-verified backtest.

The rule (`research/2026-10-26-three-bots/RULES_LOCKED.md`, set 2): the H4 lean must be on the trade's
side. +0.102 -> +0.210 R a trade on 2023-09..2026-10, +0.214 fitted / +0.207 never seen.

### What is open

- The engine-verified backtest of the gate (the research number is not to be quoted until it agrees).
- `on_bar` still asks a strategy from another lane to close, using the main lane's context
  (`REVIEW_FINDINGS.md`); harmless for these three bots, recorded not fixed.
- The outbox parks signed events as `AUDIT_CONFLICT: seq N` - the cloud holds a chain from a 5 Oct run.
  Heartbeats and quotes reach the PWA; decisions and trades do not. Clearing the cloud's old chain is a
  deletion, so it waits for the owner.
- **P26, the morning plan, is still only a note.** The engine traded the evening of 27 Oct without one.
  It must become a gate - no new entry for a day until that day's plan is recorded - not a reminder.
- `edge_side.py`'s final `isfinite` guard is reachable: a finite ATR of 1e-320 can overflow the division to infinity, and a test now covers it.
