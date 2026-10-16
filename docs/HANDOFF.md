# Session handoff

Last updated: 2026-10-16 10:30 Thai (S1 on DEMO as an M1 lane, V1 + room gate on DEMO, no SL_TOO_FAR, breakouts with the
trend measured and not kept, the owner's custom-setup notes). This file holds **state only**: rules and
conventions live in `CLAUDE.md` and `docs/CODING_STANDARDS.md`, design in `docs/PLAN.md` / `docs/PLAN_LEARNING.md`,
progress in `docs/TICKETS.md` / `docs/TICKETS_LEARNING.md`, setup results in `docs/SETUP_REVIEW.md`.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

````text
Continue TAA (C:\Users\korap\taa). Chat with me in Thai and give times in Thai time (UTC+7). Docs and code stay
in English. Follow CLAUDE.md and the memory rules. Report results as tables; report progress while backtests
run. Ask me when the meaning is unclear; don't guess. Read docs/HANDOFF.md ("Current state", "Next work" and
"Gotchas") first.

State at the hand-over (2026-10-16, about 10:30 Thai time):
- The DEMO stack RUNS (resumed 10:10 Thai, no open positions, equity 1,066.21). Remind me to pause it
  (scripts\demo-tasks.ps1 -Pause) before the computer sleeps.
- Two backtests were running in the old session and may have stopped with it: data/backtests/inv/
  s1resume_2026-03 (S1 with entry_on: resume) and s1fx_2026-08 (S1 on the 7 FX majors). If a log has no
  "expectancy" line, rerun it with the commands in docs/HANDOFF.md "Current state". Report both as tables,
  cross-checked against trades.csv, and decide per the ladder.
- main has many commits from 2026-10-15/16, NOT pushed (I push myself).

Tasks, in this order:
1. The two backtests above (results, ladder decision, SETUP_REVIEW / STRATEGIES glance table).
2. My custom setup (docs/OWNER_TRADING.md): I tell my trades (idea, prices, stop/target, management); you map
   them to the bot's measurements, restate the rule for me to confirm, then build and backtest it. Never touch my
   real account; its history only from a report I export.
3. Chart read CR-4 (docs/CHART_READ.md): trend 17/20 by proxy (in-sample), levels 5/20 - work on the levels,
   then a fresh blind 20-chart check by a sub agent.
Before any rule changes trading: a SETUP_REVIEW section, and config.yaml changed only for what passed - ask me
first (the DEMO bot reads config.yaml on restart).
````

---

## Current state (2026-10-16, 10:30 Thai)

### Trading on DEMO (running; resumed 2026-10-16 10:10 Thai)

- **Stack:** `-Mt5 -Demo` from Task Scheduler (`scripts\demo-tasks.ps1 -Pause / -Resume`). Demo account
  ~1,066 USD, no open positions. Last restart 13:28 Thai with the code of 2026-10-15 and a fresh PWA build.
- **Setups trading** (all in the aggressive preset, 7.5 % a trade, fades half):
  - harmonic V1 + `h4_room_2` (`structure_tf: H4, room_min_r: 2`; SETUP_REVIEW §18; on since 11:14 Thai);
  - breakout F1 (fades of counter-trend breaks with the H4 and H1 trend; §16);
  - **S1**, the M1 gold scalp, as **lane `s1`** (`setup_breakout_scalp`; PLAN §A7 entry lanes; §17; on since
    12:11 Thai). The lane reproduced S1's March backtest trade for trade.
- **Decision engine:** no `SL_TOO_FAR` any more (owner): a far stop gets a smaller lot, the loss at the stop
  stays within the risk per trade. A strategy's own `max_sl_atr` still applies (V1/F1/S1 unchanged; with it off,
  V1 and F1 trade identically in March - the owner has not decided whether to remove it).
- `config.yaml` (committed, owner): `high_risk:` on, lane `s1`, V1 room gate, S1 in `high_risk.setups`.

### Setup round

| Setup | State | Result |
|---|---|---|
| harmonic V1 + room | trading | year +0.226 R/trade (173), DD 9.5 R; 2nd-half CI below 0 (§18) |
| breakout F1 | trading | year +0.159 (99) (§16) |
| S1 (M1 gold scalp) | trading (lane s1) | year +0.277 (76), DD 6.2 R; 1st-half CI below 0 (§17) |
| S1 + `entry_on: resume` (Elder's third screen) | March run (78 % at hand-over, equity +27.80) | baseline March +0.397 (10) |
| S1 on the 7 FX majors | August run (24 % at hand-over, no trades yet) | FX M1 history starts 2026-07-08 (no March) |
| F1 + `entry_on: resume` | not kept | March +0.157 (5) against +0.248 (12) |
| F1 on the 21 crosses | not kept | March −0.373 (16) |
| box breakout with the trend (`setup_breakout_box`) | not kept, code stays (lane only, off) | 8 symbols M5 −0.24 (199); Asia-only gold +0.46..+1.07 on ~10/yr (owner has not chosen) |
| trend following H4/D1, momentum burst scalps | not kept | `research/2026-10-15-day-trade/BREAKOUT_NOTES.md` |

- **Chart read (TAA-L813):** CR-1, 2, 3, 5 done. The PWA chart draws `ChartReadParams.for_display()` (minor
  levels, spent at 4 crossings, the read "now" with breaks); rules keep the defaults. **CR-4 not passed:** trend
  17/20 against Claude's key (in-sample; 14/20 against the blind agent alone), levels 5/20.
- **The owner's custom setup:** `docs/OWNER_TRADING.md` - trade 1 (range buys, +81.52 USD, averaging down took
  ~60 % of the 150 USD account under water), trade 2 (head-and-shoulders right-shoulder sells, plan +100 / −40
  USD: **stopped at 4173 on 16 Oct 03:00, about −44.34 USD** after +40 open at the neckline; exact fills to
  confirm from the owner's MT5 table). Day: about +37 USD.
- **Rerun commands** (if the logs above did not finish; one at a time is fine, each takes 1-3 hours):
  ```
  CONFIG_FILE=data/research/config_s1_resume.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 ALLOWED_SYMBOLS=XAUUSD PYTHONUNBUFFERED=1   .venv/Scripts/python -m app.cli backtest --server FBS-Demo --symbols XAUUSD --start 2026-03-01 --end 2026-04-01   --strategies setup_breakout --out data/backtests/inv/s1resume_2026-03 --progress > data/backtests/inv/s1resume_2026-03.log 2>&1

  CONFIG_FILE=data/research/config_s1_fx.yaml ENABLE_HIGH_RISK_PROFILE=false MAX_ACCOUNT_DRAWDOWN_PERCENT=50 ALLOWED_SYMBOLS=EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD PYTHONUNBUFFERED=1   .venv/Scripts/python -m app.cli backtest --server FBS-Demo --symbols EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD   --start 2026-08-01 --end 2026-09-01 --strategies setup_breakout --out data/backtests/inv/s1fx_2026-08 --progress > data/backtests/inv/s1fx_2026-08.log 2>&1
  ```
  Baselines: S1 March `data/backtests/inv/scalp_s1_2026-03` (10 trades, +0.397). Judge by R per trade (a gold
  trade at the minimum lot risks ~3x a currency trade, so net can disagree).
- **PWA:** the Symbols page shows the trend per setup group (M15 setups: H4 + H1; M1 scalp: H1 + M15) from
  `GET /engines/{id}/trends`.

### Code and checks

- **Git:** `main`; the owner pushes. All of 2026-10-15 is committed and not pushed. Latest migration **0043**.
- **Checks:** targeted tests, ruff, mypy, bandit, `npm run typecheck` and the affected vitest files ran for every
  change. The last full pytest + vitest run was 2026-10-06: **due now**, with the stack paused.

## Next work

1. Finish the two running backtests (prompt, task 1).
2. The owner's custom setup (prompt, task 2): confirm the range-trading and head-and-shoulders rules; test the
   hypotheses in `docs/OWNER_TRADING.md` (planned scale-in vs averaging down, risk per trade, break-even stop,
   early manual exit) with a harness first (`research/2026-10-15-day-trade/box_harness.py` shows the method:
   reproduce the engine's March trades exactly, then grid with walk-forward), then the backtest ladder.
3. Chart read CR-4 (prompt, task 3), then CR-6 / CR-7.
4. Full pytest + vitest with the stack paused.
5. Owner decisions pending: remove V1/F1's own `max_sl_atr` (no effect in March); the box breakout Asia-only
   option (needs lane-level sessions); S1's FX expansion after the August result.
6. Older follow-ups: the aggressive preset (scanner sizing, cloud backtests, margin-level vs utilization), a
   backtester spread floor, the PWA "Pause" button, TAA-L702 open items, TAA-L803.
7. **Owner, before LIVE:** DEMO soak, the drills on the LIVE machine (TAA-1403), the go-live checklist and the
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
- **The box breakout** (`setup_breakout_box`) is off; Asia-only gold was the one positive cell (~10 trades a
  year). **V1/F1's own `max_sl_atr`** stays until the owner decides (no effect in March).
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
