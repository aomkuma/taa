# Session handoff

Last updated: 2026-10-14 (breakout F1 and harmonic V1 on DEMO in the aggressive preset, M1 gold scalping S1,
the chart read plan). This file holds **state only**: rules and conventions live in `CLAUDE.md` and
`docs/CODING_STANDARDS.md`, design in `docs/PLAN.md` / `docs/PLAN_LEARNING.md`, progress in `docs/TICKETS.md` /
`docs/TICKETS_LEARNING.md`, setup results in `docs/SETUP_REVIEW.md`. The dated session logs of 2026-10-05 ..
10-11 were removed on 2026-10-14 (see git history; their findings are in SETUP_REVIEW §8-§15 and the plans).

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

````text
Continue two tasks on TAA (C:\Users\korap\taa). Chat with me in Thai and give times in Thai time (UTC+7).
Docs and code stay in English. Follow CLAUDE.md and the memory rules. Report results as tables, and report
progress every few minutes while backtests run. Ask me when the meaning is unclear; don't guess.
Read docs/HANDOFF.md ("Current state" and "Gotchas") first.

## State at the hand-over (2026-10-14, about 17:30 Thai time)

- main has 4 new commits, NOT pushed (I push myself):
  - 33629a6: M1 scalping params atr_bars / skip_window_ny
  - 038608b: docs/CHART_READ.md, the chart read plan (TAA-L813)
  - e1d2635: aggressive preset for small accounts (minimum lot up to 15 % risk, leverage cap 200)
  - da2569b: merge of the aggressive preset (PLAN §A36, TAA-1212)
  - plus this HANDOFF rewrite
- Uncommitted: config.yaml has the `high_risk:` block switched ON. .env has ENABLE_HIGH_RISK_PROFILE and
  HIGH_RISK_CONFIRMATION (not in git). Ask me before committing the config.yaml change.
- The DEMO stack (scripts\demo-tasks.ps1 -Pause / -Resume; web http://localhost:8001, engine health
  http://127.0.0.1:8766/health) runs harmonic V1 + breakout F1 in **Aggressive 7.5 %** on the demo account
  (~1,005 USD).
  - Don't change anything that touches the account without asking.
  - Pause the stack before any heavy run (npm run build, full pytest/vitest): it crashed the engine before.
  - Remind me to pause it before I close the laptop.
- The old worktree .claude/worktrees/agent-a8b3410ffe49fb0d1 (branch worktree-agent-a8b3410ffe49fb0d1) is
  merged; it holds a copied .env. Ask me before removing it.

## Rules that apply (CLAUDE.md + memory)

- Backtest ladder: March 2026 (03-01..04-01), then August 2026 (08-01..09-01), then the full year.
- A variant whose first run is negative is dropped. Keep only profitable ones, or the least-losing one.
- Goal per setup: >= +0.15 R/trade net (±0.05 tolerance), 90 % CI lower bound > 0 in both halves (split
  2026-04-09), max DD <= 15 R. The >= 300 trades/yr target is portfolio-wide.
- One setup at a time. A losing setup gets its conditions changed, never dropped.
- Theory 30-40 %, measured price behaviour the rest. A signal alone is not enough: trend, S/R and structure.
- In a phase that doesn't suit a setup, it trades only its surest signals (fewer trades, not none).
- Targeted tests + ruff/mypy per change; the full pytest + vitest suite only at the end of the setup round.
- Changing a reason code or i18n key means updating frontend/src/i18n in the same change (run vitest files one
  at a time: the pool crashes under memory pressure).
- Commits: by explicit paths, one commit per finished piece is OK. Never push.
- Machine: 16 GB. At most 3-4 backtests at once, and never next to full tests (MemoryError / paging file).

## Task 1 — M1 gold scalping S1: next rung of the ladder

- Config: data/research/config_scalp_s1.yaml (not in git).
  - Entry M1, context [M15, M30, H1, H4, D1], cooldown 60 bars, 1 position per symbol, slippage 7 points
    (approximates my gold spread of ~30 points).
  - setup_breakout params: screen_h4/h1 "with" on tide H1 / wave M15, fade_counter_trend, no trend entries,
    atr_bars 60, stop 2.0 x ATR(60) (the fade's stop is ~1 ATR, its target ~2 ATR), rr_target 0.5, min_rr 0.5,
    max_sl_atr 4, skip_window_ny 08:00-12:00, friday_cutoff 16:00, time stop 60 bars, no break-even/trailing.
- March 2026 result: 10 trades, win 50 %, PF 1.68, **+0.40 R/trade**, net +168 on 10,000, DD 0.65 %.
  (data/backtests/inv/scalp_s1_2026-03). It passes, but 10 trades a month is very few for scalping.
- Next: run **August 2026** with the same config:
  ```
  CONFIG_FILE=data/research/config_scalp_s1.yaml ALLOWED_SYMBOLS=XAUUSD MAX_ACCOUNT_DRAWDOWN_PERCENT=50 PYTHONUNBUFFERED=1 \
  .venv/Scripts/python -m app.cli backtest --server FBS-Demo --symbols XAUUSD --start 2026-08-01 --end 2026-09-01 \
  --strategies setup_breakout --out data/backtests/inv/scalp_s1_2026-08 --progress > data/backtests/inv/scalp_s1_2026-08.log 2>&1
  ```
  - One month of M1 gold takes about 1 hour.
  - The progress line's equity can lag; trust the final summary (summary.json has signals/rejections).
- If August holds: run the full year (2025-10..2026-09), monthly runs are OK. Judge both halves and the CI.
- If it fails, or to raise the trade count: analyse the trades (worst 3, by NY hour, by stop/target) and the
  rejections.
  - Then change the conditions, guided by research/2026-10-11-pre-run/m1_scalp_study.py
    (data/backtests/inv/m1_scalp_study_1y.txt). Only gold is viable on cost; counter-break fades inside an
    H1+M15 trend had the edge; NY 08:00-12:00 loses.
  - Each variant goes through March first.
- Report as a table and keep going until it meets the goal or the levers run out (then say so and ask).

## Task 2 — Chart read (docs/CHART_READ.md, ticket TAA-L813), starting with breakout F1

Read docs/CHART_READ.md fully first. Decisions made (owner, 2026-10-14):
- swings = the **MT5 standard ZigZag (Depth 12, Deviation 5, Backstep 3)**, ported with no repainting: a pivot
  is used only once the opposite pivot has registered, from backstep bars after that;
- the bot samples the 20 eye-check charts itself (8 symbols, M15/H1/H4, every phase, random within each
  group, never by result); the check passes at 16/20 agreements;
- **breakout F1 first**, then harmonic V1.

Measured so far (§2, research/2026-10-14-chart-read/*.py):
- The map state calls a trend on 17-19 % of H1/H4 bars vs ~60 % for the swings.
- The fractal k=3 labels are ~3x noisier.
- A trend read alone does not predict the next 24 bars (~50 %).
- The trade splits are NOT robust: they flipped between 3xATR and MT5 12/5/3. With MT5, F1 is +0.40 R in the
  mixed phase on H1 and H4 (n 21 / 29) and −0.12 R when H4 is against (n 25). So rules are chosen on the
  first half only and judged on the second half + hold-out symbols (AUDUSD, XAUUSD), never off the full year.

Steps, in this order (tick docs/TICKETS_LEARNING.md via `scripts/tickets.py --file docs/TICKETS_LEARNING.md`
as items finish):
1. **CR-1:** app/indicators/chart_read.py (pure, indicators layer) with:
   - the MT5 ZigZag port (start from research/2026-10-14-chart-read/mt5_zigzag.py);
   - structure (UP/DOWN/CONTRACTING/BROADENING/FLAT/NONE, invalidation, broken, age);
   - levels with roles (SUPPORT/RESISTANCE/FLIPPED/SPENT, retests);
   - trendline, position (retrace vs the previous leg; retrace_major vs the next-higher TF's read);
   - events (BREAK_HOLD / SWEEP_RECLAIM / RETEST);
   - scenario text;
   - the `context_map.chart_read` config (extra="forbid");
   - tests: the prefix property on random cut points, synthetic paths for each case, serialization, and the
     architecture layer table.
   - Check the port against MT5: the Python MetaTrader5 package cannot run indicators, so write a small MQL5
     script that exports ZigZag(12,5,3) buffer values to CSV for a few hundred bars per timeframe. Give it to
     me to run in the terminal, then compare (ties and equal highs are the likely differences).
2. **CR-2:** MapBook + market document (optional key: old digests stay valid) + ctx features
   (sw_trend, sw_phase, sw_age, sw_broken, inv_r, lvl_with_atr, lvl_against_r, lvl_flipped, tl_atr, retrace,
   retrace_major, ev_*). Backtest runtime may grow 10 % at most.
3. **CR-5 (F1 only):** setup params, off by default, each a Condition with TH/EN labels:
   screen_source map|swings, structure_tf + structure_gate, mixed_rule any|surest|skip, level_gate, room_min_r,
   stop_mode structure. API samples regenerated (TAA_UPDATE_API_SAMPLES=1).
4. **CR-3 for F1:**
   - Replay F1's year with the features (trades: data/backtests/inv/setup_breakout_f1_2025-10 .. _2026-09).
   - Choose at most 3 rules on the first half and write them down before judging them on the second half and
     the hold-out symbols.
5. **CR-6 for F1:** the ladder (March → August → year) for the surviving variants.
   - F1 baseline config: config.yaml setup_breakout params {screen_h4: with, screen_h1: with,
     fade_counter_trend: true, trend_entries: false, friday_cutoff_utc: "16:00"}, risk.fade
     {min_risk_reward: 0.2, max_sl_atr_multiple: 12}; research config data/research/config_bo_f1.yaml.
   - Monthly results: data/backtests/inv/breakout_f1_months.md.
   - The baseline must be matched or beaten.
6. **CR-4 (can run next to 3-5):** the PWA overlay (pivots + labels, levels by role, trendline, invalidation,
   scenarios; zod; TH/EN) and the 20-chart eye check with me.

Before any rule changes trading: a SETUP_REVIEW section with the results, and config.yaml changed only for
what passed (ask me first, because the DEMO bot reads config.yaml on restart).

## Also open (don't start unless I ask)

- Aggressive on DEMO: watch it; the drawdown kill at 60 % needs a manual reset (RUNBOOK_DEMO §6).
- The full pytest + vitest suite at the end of the setup round, with the DEMO stack paused.
````

---

## Current state (2026-10-14, evening)

### Trading on DEMO

- **Stack:** `-Mt5 -Demo` from Windows Task Scheduler (`scripts\demo-tasks.ps1`; desktop "TAA Pause" /
  "TAA Resume"). Restarted 10:22 UTC with the merged code and a fresh PWA build. Demo account ~1,005 USD, no
  open positions at the restart. Pause it before the laptop sleeps (see Gotchas).
- **Setups trading:** harmonic V1 (`{phase_gate: h4_against_or_range, max_rr: 3.0}`, no break-even;
  SETUP_REVIEW §15.3) and breakout F1 (fades of counter-trend breaks with the H4 and H1 trend, `risk.fade`
  RR floor 0.2 / SL cap 12 ATR; §16). The other seven setups are off; the inverted copies were removed from the
  code (INVERTED_SETUPS.md keeps the history).
- **Aggressive preset ON (owner, 2026-10-14):**
  - Switched on by `high_risk:` in `config.yaml` (uncommitted), `ENABLE_HIGH_RISK_PROFILE` +
    `HIGH_RISK_CONFIRMATION` in `.env`, and the owner's PWA choice.
  - The engine applies 7.5 % a trade (fades 3.75 %), 15 % open risk, 2 positions, 15 % daily loss, 35 % weekly,
    the drawdown kill at 60 % (latched; RUNBOOK_DEMO §6), the minimum lot up to 15 % risk, and the leverage cap
    200.
  - Switch off: Standard in the PWA.
- **Backtest of the preset, March 2026, 1:2000** (scratchpad runs, not kept):

  | Account | Trades | Net | R/trade | DD |
  |---|---|---|---|---|
  | 50 USD | 24 | −3 % | +0.02 | 41 % |
  | 100 USD | 25 | −1 % | +0.02 | 36 % |

  Harmonic lost in March; gold rarely fits 15 % at 50 USD. Ruin table: PLAN §A36 (7.5 % → P(kill) 54 %; 5 % → 9 %).

### Setup round (CLAUDE.md "Setup work")

| Setup | State | Result (year unless noted) |
|---|---|---|
| harmonic V1 | passes, trading | +0.211 R/trade, 181/yr, halves +0.24 / +0.18 (§15.3) |
| breakout F1 | passes, trading | +0.159 R/trade, 99/yr, halves +0.16 / +0.16 (§16) |
| M1 gold scalping S1 (breakout fade on M1, screens H1/M15) | March passed | +0.40 R, 10 trades; next: August (prompt, task 1) |
| the other seven setups | waiting | one at a time, after the current work |

- **Chart read (TAA-L813, docs/CHART_READ.md):** a planned major change, nothing built; next session task 2.
- **Confluence direction (TAA-L812, docs/CONFLUENCE_DIRECTION.md):** waits for the chart read.

### Code and checks

- **Git:** `main`; the owner pushes. Not pushed: 33629a6, 038608b, e1d2635, da2569b and this HANDOFF commit.
  Latest migration **0043**.
- **Checks:**
  - Since the last full run (2026-10-06: pytest 2791 passed, vitest 526) every change ran targeted tests only,
    plus ruff, mypy, bandit and the frontend typecheck.
  - The full pytest + vitest suite is due at the end of the setup round, with the stack paused.

## Next work

1. M1 gold scalping S1: August 2026, then the year (prompt, task 1).
2. Chart read CR-1 → CR-6 for breakout F1, then harmonic V1 (prompt, task 2).
3. The remaining seven setups, one at a time (owner picks the order).
4. Aggressive preset follow-ups:
   - whether the advisory scanner sizes with the preset (now always STANDARD);
   - cloud backtest jobs for the preset (refused now);
   - the margin-level vs utilization mismatch: `max_margin_utilization_percent` 30 lets the lot grow until the
     margin level is ~333 %, below `min_margin_level_percent` 500, so a trade is rejected instead of cut
     further; it matters at 1:100, not at 1:2000.
5. Optional: a backtester spread floor (gold 30, currencies 10 points), so backtests use the owner's real costs.
6. Full pytest + vitest with the stack paused; PWA "Pause" button; TAA-L702 open items; TAA-L803.
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
  - **The owner's real account** (not connected): 50-100 USD at 1:2000.
- **History:** `data/history/FBS-Demo/<symbol>/{M1,M5,M15,M30,H1,H4,D1}.parquet`, 2025-10 .. 2026-09, for the
  8 symbols; gold M1 covers the whole year.
- **Research:** configs `data/research/config_*.yaml` (not in git); backtest outputs `data/backtests/inv/`;
  scripts `research/2026-10-11-pre-run/`, `research/2026-10-14-chart-read/`.
- **PostgreSQL 16** (service `postgresql-x64-16`, shared with other projects): role `taa`, database
  `taa_test`, URL `TAA_POSTGRES_URL` in `.env`. Never touch other projects' databases; never clean up
  databases by `LIKE` pattern (`_` is a wildcard).
- **Browsers:** Chrome and Edge; Playwright drives Chrome (`channel: 'chrome'`).

## Gotchas

- **Backtests:**
  - `CONFIG_FILE` picks the config.
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
- Commit (or not) the `high_risk:` block in `config.yaml`.
- Remove the merged worktree `.claude/worktrees/agent-a8b3410ffe49fb0d1` (it holds a copied `.env`).
- **AI (optional):** an Anthropic API key in `.env` (`AI_PROVIDER=anthropic`, `AI_API_KEY`), starting with
  `AI_MODE=advisory`.
- Phase 11 (Railway) only with an explicit go-ahead; subscriptions only after legal review
  (`docs/COMPLIANCE.md`).
- `VAPID_SUBJECT` in `.env` is a placeholder; the owner's account profile on `/account` lets alerts carry money.
