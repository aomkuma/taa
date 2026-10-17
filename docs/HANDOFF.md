# Session handoff

Last updated: 2026-10-17 17:00 Thai (the owner's goals written down; every earlier setup stopped; Setup OWN, the
owner's own trade, starts). This file holds **state only**: rules and conventions live in `CLAUDE.md` and
`docs/CODING_STANDARDS.md`, design in `docs/PLAN.md` / `docs/PLAN_LEARNING.md`, progress in `docs/TICKETS.md` /
`docs/TICKETS_LEARNING.md`, setup results in `docs/SETUP_REVIEW.md`.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

````text
Continue TAA (C:\Users\korap\taa). Chat with me in Thai and give times in Thai time (UTC+7). Docs and code stay
in English. Follow CLAUDE.md and the memory rules. Read docs/OWNER_GOALS.md first (my goals and principles),
then docs/OWN_SETUP.md (Setup OWN, my own trade: the moments when gold runs) and docs/HANDOFF.md.

State (2026-10-17): every earlier setup (V1, F1, S1) is stopped in config.yaml; the bot starts over with Setup
OWN in the aggressive preset once it passes its gate. DEMO is paused. main is not pushed (I push myself).

Next: the plan in docs/OWN_SETUP.md - focus on the bot; backtests cover the latest six months only (we revise
setups every 3-6 months): the moments dataset for gold 2026-04-14 .. 10-14, the hypotheses H1-H4 and the
playbook selector fitted on the first three months and judged once on the last three, then the engine setup and
its backtest. Ask me when the meaning is unclear.
````

---

## Current state (2026-10-17, 17:00 Thai)

- **The owner's goals and principles:** `docs/OWNER_GOALS.md` (several were never written down before: session
  opens, ATR low, Bollinger squeeze, quick profit, the review cadence, news). Setup OWN: `docs/OWN_SETUP.md`,
  `docs/OWNER_TRADING.md` "Setup OWN".
- **Setup OWN round 1 (2026-10-17, latest six months, harness):** no playbook pays at the moments after costs;
  the context selector, OWN v1 (two pieces mined from the fit months: judged -0.155 R over 141 trades) and H5
  (the last 20 days pick the playbook: -0.013 R over 266) fail. Details and next levers: `docs/OWN_SETUP.md`
  "Results". The owner's exits: target at least 5 USD (gold 1 pip = 1 USD), scalp first, hold 2-3 hours when
  the picture is clear; largest timeframe H1. Nothing is coded in the engine yet.
- **Every earlier setup stopped** (owner, 2026-10-17): V1, F1 and lane `s1` are `enabled: false` in
  `config.yaml` (parameters kept); no setup trades until OWN passes its gate. `high_risk` (aggressive preset) stays
  on for OWN.
- **DEMO:** paused since 2026-10-16 10:51 Thai (`scripts\demo-tasks.ps1 -Resume` to restart; nothing would trade).
- **Why the change:** S1 (M1 fade) and TS (M15 structure break) pay only in gold's 2024-26 rally (five years of
  gold: SETUP_REVIEW §23-23.3; docs/OWNER_TRADING.md "Setup TS"). The owner: a setup fitting only some periods is
  normal; the system must see the present and choose.
- **Work stopped, results kept:** the out-of-sample runs (`docs/OUT_OF_SAMPLE.md`: year A 12/36; year C not run),
  the S1 spread-floor engine checks (`data/backtests/s1fix/`, four partial runs, no result), the TS session.
  The harness results for S1 over five years are the record (SETUP_REVIEW §23).
- **Unmerged branches** (worktrees under `.claude/worktrees/`): `s1-cost-floor` (`min_atr_spreads`, a fade's
  spread rule on the stop it trades) and `setup-groups` (gold / currency sub-setups `setup_harmonic_gold`,
  `setup_breakout_gold`, a `symbols` param); tests green on the branch; the owner decides whether to merge.
- **Data:** gold 2020-09 .. 2023-10 in `data/history_old/FBS-Demo/XAUUSD` (the TS session's store), 2023-08 ..
  2026-10 in `data/history`; FX majors M1 2023-09 .. 2026-10; US100/JP225/US30/US500/XAUAUD M1/M15/H1 from
  2023-08. Backups of `data/history`: `D:/taa-history-backup-2026-10-17`, `-17b`.
- **Code:** TAA-507 portfolio backtest (`app.cli backtest --portfolio`) merged. Latest migration **0043**. The
  last full pytest + vitest run was 2026-10-06: due.

## Next work

1. Setup OWN (`docs/OWN_SETUP.md`), latest six months only (fit 2026-04-14 .. 07-14, judge 07-14 .. 10-14):
   the release calendar (done), the moments dataset, H1-H4 and the selector, the engine setup, the gate.
2. The weekly market-state report and the monthly re-fit (the owner's review cadence).
3. Owner decisions pending: merge the two branches or not; the account size for the daily goal (100 or 150 USD).
4. Full pytest + vitest once (stack paused).
5. **Owner, before LIVE:** DEMO soak, the drills on the LIVE machine (TAA-1403), the go-live checklist and the
   explicit go-ahead. Never enable LIVE on the owner's behalf; the aggressive preset refuses LIVE in code.

## Local environment

- **Demo stacks** (`scripts\start-demo.cmd`, details in the script header):
  - Default: FakeMT5 PAPER engine, web `http://127.0.0.1:8000`, `data/taa_cloud.db`, `.env.demo`.
  - `-Mt5 -Demo` (the one in use): the real MT5 terminal and FBS demo account, DEMO orders
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
