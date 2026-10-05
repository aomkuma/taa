# Session handoff

Last updated: 2026-10-05 (fourth session that day: revision 5). Single session on `main`. This file holds
**state only**: rules and conventions live in `CLAUDE.md` and `docs/CODING_STANDARDS.md`, design decisions in
`docs/PLAN.md` (each ticket's "TAA-xxx decisions" notes), progress in `docs/TICKETS.md`. What was built per
ticket is in the git history.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md first (state, "Next work", gotchas), then docs/TICKETS.md
(progress, dependencies) and the PLAN sections the next ticket names (Phase 10: PLAN §A15 Recommendations and
Analytics, §A27 for shadow statistics).
Follow CLAUDE.md and docs/CODING_STANDARDS.md (§9 for the frontend; frontend/README.md for its commands).
This is the only session: work on main, one ticket at a time, in the "Next work" order. Start with the open
item at the top of "Next work" (heartbeat rate check), then TAA-1004 (recommendations).
For PWA pages: build page tests from frontend/src/test/fixtures/api-samples.json (real API responses) and add
every new route a page reads to tests/web/test_api_samples.py and frontend/src/test/apiSamples.test.ts
(regenerate with TAA_UPDATE_API_SAMPLES=1). Run the full pytest suite and vitest one after the other, never
at the same time, and not while the local demo stack runs (the machine runs out of memory).
Check every change against real data, not only samples: the local stack on the real MT5 demo account (PAPER)
runs with scripts\start-demo.cmd -Mt5 (http://localhost:8001). After changing Python code or config.yaml,
restart that stack's web, worker and/or engine (a running process refuses new config keys); after a frontend
build I press Reload on the "new version" banner.
Commit at each ticket boundary (allowed); I push myself. LIVE stays disabled; subscriptions stay off.
Update docs/HANDOFF.md at the end of the session. Chat with me in Thai.
```

---

## Current state

- **Done:** Phases 0–8, 2A, 6A–6C, 8A, **9 (complete: 901–923)** and 12 (DEMO orders, pulled forward).
  Phase 10: 1001–1003.
- **Not started:** Phase 10 TAA-1004/1005, Phase 11 (Railway), M2 Phases 13 (AI, optional) and 14 (LIVE),
  Phase 15 (deferred backlog: TAA-1501 cloud replay jobs).
- **Checks:**
  - Last **full** pytest: 2699 passed, 7 skipped (earlier on 2026-10-05; ~10 min). Since then, run next to the
    demo stack: tests/unit + tests/integration + tests/backtest 2405 passed (after the DATA_GAPS fix), tests/web
    350 (one sample regenerated since). **Run the full suite once with the stack stopped.**
  - ruff, mypy, bandit clean. Frontend: lint, typecheck (app, node, sw, e2e), build clean; vitest 502;
    Playwright smoke 3 (`npm run build && npm run e2e`).
- **Git:** `main` only; the user pushes (`git push` from Claude Code fails on the interactive GitHub login).
  Latest migration: **0036** (`manual_trade_overrides`).

### What this session (2026-10-05, third) added

Tickets, each with a "decisions" note in PLAN:

- **TAA-918** watchlists page + alert settings card on Notifications (PLAN §A28).
- **TAA-919** signal accuracy page; `GET /accuracy` carries the owner's `currency`; `codes:shadowFlag`.
- **TAA-920** theories & conditions page; detector names TH/EN (`codes:evidence.<id>`, `evidenceName()`);
  **the engine owner's bounded detector parameters now reach the scan** (`AdvisoryConfig.params`, the user's
  decision; merged over `config.yaml`, invalid ones skipped).
- **TAA-921** "My account & plan" (`/account`) and "Users & plans" (`/admin`, OWNER/ADMIN only);
  `GET /admin/users` carries `plan`; new `GET /admin/users/{id}/entitlements`.
- **TAA-922** trading profile page; new `POST /engines/{id}/entry-plan/preview` (sizes a draft plan with the
  alerts' own sizer).
- **TAA-923** engines page (add wizard, browser-made control TOTP with QR via `uqr`, rotate, revoke).
- **TAA-914** PWA polish: PNG/maskable/Apple icons (`npm run icons`), caching rules, install prompt, gzip for
  the static app (not `/api/`), Playwright smoke tests (installed Chrome, `@playwright/test` 1.63).

Fixes and changes found on real data (at the user's request):

- **Manual MT5 positions** were invisible but blocked every paper entry: the heartbeat now carries
  `foreign_positions` (risk to stop, counted or not) and `effective_leverage`; Positions page and dashboard
  list them; dashboard has an effective-leverage gauge.
- **Two accounts, now named:** the dashboard showed the bot's simulated PAPER book ($989.67) while the ranking
  showed the real MT5 account ($1,105.05). In PAPER the heartbeat now also carries `broker_account`, and the
  dashboard shows both with explanations. The numbers differ by design.
- **DATA_GAPS** refused most stock signals and XAUUSD: closed hours counted as missing bars and the configured
  `daily_breaks_utc` never reached the check. `app/market_data/quality.py` now learns each symbol's closed
  time-of-day slots from its own bars and counts only bars missing in normally traded hours.
- **Live candle speed:** `sync.heartbeat_seconds: 1` and `flush_interval_seconds: 1` (were 10 / 2), and the
  scanner pulses the heartbeat between symbols (an engine cycle takes ~7 s, mostly the evidence scan, and the
  heartbeat used to go out once per cycle). See "Next work" item 1.

## Next work

**Focus (user decision 2026-10-06):** skip Phase 11 (Railway) for now. Work toward LIVE auto-trading, Phase
14: TAA-1401 live gate wiring (6 conditions + account-bound phrase, probation, banner) → 1402 security review →
1403 go-live checklist & drills → 1404 final docs. Do this together with wrap-up work: the loose ends below,
the dashboard additions (§A28), and a full pytest + vitest run with the stack stopped. Phase 13 (AI) is optional
and comes after. Turning LIVE on still needs Phase 14 done and the user's explicit go-ahead at that moment.

1. **TAA-1006 is done** (rev. 6, 2026-10-06): manual trades are linked to signals on the engine, the owner
   corrects a link on Positions, and closed manual trades show me / signal / bot in R on Trade history. When
   the owner's two open manual trades (GBPUSD, EURUSD) close, check that they appear there with an R. Open
   idea: an aggregate of manual trades on the accuracy page once there are enough of them.
2. **Done on 2026-10-05/06 and checked on the real stack:** revision 5 (owner's profile inside the
   `config.yaml` cage, now 2 % / 4 % heat / 4 % daily / 8 % weekly; `.env` no longer overrides
   `MAX_RISK_PER_TRADE` / `MAX_DAILY_LOSS_PERCENT`), live candle ≈ one heartbeat per second (per-detector
   pulse), chart range fix and strength-styled S/R zones. Probation is LIVE-only by design (TAA-1401).
   Restarting the stack from Claude Code works when the user has approved it in the conversation.
3. **Phase 10 is done** (TAA-1004 recommendations, TAA-1005 analytics API & page, 2026-10-06).
4. Dashboard additions of PLAN §A28 still open: active opportunities and the accuracy summary (the top-5
   ranking widget is done).
5. Phase 11 Railway deployment: **skipped for now** (user decision 2026-10-06). Later, only with the user's
   Railway access and go-ahead.
6. **Homework from the user (2026-10-05), after all remaining tickets:** the system's purpose is to sweep
   **every** tradable symbol (hundreds) for opportunities, not 4. Make it as flexible as possible, including
   future strategies, and let AI take part in learning and adapting the trading playbook to current
   conditions. Findings so far (check again before designing):
   - Ranking covers the whole broker universe (549 symbols on the FBS demo). The opportunity scanner covers
     only the advisory requirements: allowlist + favourites + lists + `advisory.universe.auto_top_n: 30`
     (affordable symbols only), with a per-cycle time budget (~1–1.6 s per symbol per bar for the evidence
     scan), which also makes the engine cycle slow (~7 s).
   - Affordability is judged on the engine owner's account; with subscribers on the feed the scanner would
     need their accounts too.
   - Trading, candle streaming, chart data and forming bars cover only the traded symbols:
     `ALLOWED_SYMBOLS` in `.env` overrides `symbols.allowed` in `config.yaml` (EURUSD, GBPUSD, USDJPY,
     XAUUSD). Charts of other symbols have no bars.
   - Strategies and their parameters are fixed in `config.yaml` (`extra="forbid"`; a running process must be
     restarted after a config change). Detector parameters can now come from the owner's theory settings
     (TAA-920), strategy parameters cannot.
   - Learning today: calibration from shadow outcomes (PLAN §A27) and analytics (Phase 10); AI is the
     optional M2 Phase 13 (assessment/veto). Neither adapts strategies.
   - To design: scanning cost at hundreds of symbols (budget, priorities, sharding, probably a separate scan
     process), chart data on demand for any symbol, strategies and parameters changeable without a restart
     (from the PWA, versioned and audited), and an AI loop that proposes changes from outcomes and backtests
     them before anything goes live (never auto-applied, PLAN §A15 Recommendations).

### Why the real stack shows little data (explained to the user on 2026-10-05)

- **No paper trades yet:** every EXECUTION decision was refused with `MAX_TOTAL_OPEN_RISK` and
  `LEVERAGE_LIMIT` because of a manual 1.0-lot EURUSD trade on a ~$1,000 account (15% heat, 113x). That trade
  has since been closed (effective leverage 0 at the end of the session). The user may still choose
  `risk.foreign_positions_policy` or a separate bot account (see "Decisions the user may want to revisit").
- **No alerts yet:** the alert metric is win probability ≥ 55%, but the calibration version was built before
  any shadow trade closed (0 outcomes), so every opportunity reads "insufficient data". It rebuilds daily
  (after `advisory.calibration.nightly_hour_utc`); switching the metric to setup strength in the alert
  settings gives alerts meanwhile. Offered to the user, not changed.
- **No sizing money in alerts:** the owner's account profile is not set (`/account` → save "My engine's MT5
  account").

### Notes for the remaining tickets

- **APIs the pages read** (all under `/api/v1`):
  - Session `/auth/session|login|logout|step-up|profile`; `GET /me/feed` (`own` false = the owner's market
    feed, account details redacted).
  - Live data: `GET /engines/{id}/stream` (SSE; topics status, quotes, positions, notifications, decisions);
    the status topic carries every heartbeat (now ~1/s).
  - Owner: status, account, positions, trades, intents, decisions, breakers, kill-switch, symbols, candles,
    config, audit/verify, commands, engines, backtests.
  - Advisory: ranking, opportunities, shadow-trades, accuracy (`?mine=true`), threshold-explorer,
    theory-scoreboard, calibration, entry-plan/preview; `/advisory/preferences|watchlists|favourites|
    detectors`.
  - Me: notifications, push, preferences; `/me/alerts|entitlements|account-profile|export|erase`; admin
    `/admin/users|plans`, `/admin/users/{id}/entitlements|plan|overrides/{key}`.
- The preferences document has one schema and query (`src/pages/watchlists/schemas.ts`, `hooks.ts`):
  `usePreferences`, `useFavourites`, `useSaveSections` (re-reads, then PUTs the whole document).
- Engine-wide account data for pages: `useEngineStatus().data.heartbeat.account` (paper book, limits,
  `foreign_positions`, `broker_account`, `effective_leverage`).
- Routes with a detail param: `DETAIL_PARAM` in `src/app/routes.tsx` (`/opportunities/:opportunityId`).
  Only `analytics` is still a `PlaceholderPage`; the shell tests use `/analytics` as their widget-free page,
  so move them when TAA-1005 builds it.
- **TAA-1004 preparation:** fills store no entry context; callers pass an `EntryContext` per signal id
  (`context_from_decision`). For backtests, `BacktestEngine` must keep the selected signal's `MarketContext`
  (or decision record) by signal id: a small change in `app/backtest/engine.py`. Until exit-time facts and
  news overlap are supplied, LOSS_REGIME_SHIFT, LOSS_VOLATILITY_SPIKE and LOSS_NEWS_PROXIMITY never fire.
- **TAA-1005:** `analytics.attribution.<CODE>` needs TH/EN texts in `frontend/src/i18n/`; reuse
  `SeriesChart` (`src/pages/backtests/SeriesChart.tsx`) for equity/drawdown, as the accuracy page does.
- A new replicated table needs a sample row in `tests/sync_data.py` (a test enforces it).

## Local environment

- **Demo stack** (`scripts\start-demo.cmd`, details in the script header): web + worker + PAPER engine, each in
  its own window.
  - Default: FakeMT5 engine, web `http://127.0.0.1:8000`, `data/taa_cloud.db`, engine `fake demo` in
    `.env.demo`. It shares `data/heartbeat.json` and the kill-switch file with a real engine.
  - `-Mt5` (the user's preferred way to look at the app): PAPER on the real MT5 terminal (FBS demo account),
    web `http://localhost:8001` with its own database `data/demo/cloud-mt5.db`, engine `mt5 demo (paper)` in
    `.env.demo-mt5`, health `http://127.0.0.1:8766/health`. Both stacks can run at once. It was running at the
    end of this session (web and engine restarted with the latest code).
  - Web user `aomkuma` (OWNER) in both databases; `app.cli web reset-password` resets it.
- **MT5:** a dedicated portable terminal at `C:\MT5\taa-bot`. `doctor` passes (warning: Algo Trading off).
  Demo account: USD, 1:200, hedging, ~$1,105 equity; the user also trades it by hand (manual positions are now
  shown in the PWA). `.env` has `TRADING_MODE=PAPER`; DEMO orders need `TRADING_MODE=DEMO` +
  `ENABLE_DEMO_TRADING=true` and `docs/RUNBOOK_DEMO.md` (DEMO has only run on the FakeMT5 trade server so far;
  limit parts of entry plans are not sent yet).
- **PostgreSQL 16** (service `postgresql-x64-16`, shared with other projects): role `taa`, database
  `taa_test`, URL `TAA_POSTGRES_URL` in `.env`. Never touch other projects' databases; never clean up
  databases by `LIKE` pattern (`_` is a wildcard).
- **Browsers:** Google Chrome and Edge are installed; Playwright drives Chrome (`channel: 'chrome'`), and
  `npx lighthouse@12` works with `CHROME_PATH` set to Chrome (retry once on `NO_NAVSTART`).

## Gotchas

- **Memory (16 GB):** full pytest + vitest at once, or either next to the demo stack, crashes workers (vitest
  exit 134, numpy `ArrayMemoryError`, pandas access violations, argon2 `HashingError`). Run them one after the
  other; with the stack up use `npx vitest run --maxWorkers=2`; rerun a lone failure before investigating.
- **Heartbeat schema is strict** (`extra="forbid"`): when the engine's heartbeat gains a field, restart the
  **web** first, then the engine, or the cloud refuses the heartbeats.
- Changing `config.yaml` values that `/engines/{id}/config` shows changes the `engines/ENGINE/config` API
  sample: regenerate with `TAA_UPDATE_API_SAMPLES=1`.
- Web Push is untested with a real push service so far: turn it on in the browser on the `-Mt5` stack
  (`.env` has the VAPID pair; `VAPID_SUBJECT` is a placeholder) and send a test from the Notifications page.
- The service worker is `frontend/src/sw/sw.ts` (`injectManifest`, own `tsconfig.sw.json`); it caches only
  the app shell and never `/api/`.
- After a frontend rebuild the open PWA keeps the old version until the "new version" banner's Reload (or
  all tabs are closed).
- Don't edit Python or migration files during a full pytest run (the migration-parity test reads them);
  frontend edits are fine.
- Restarting the `-Mt5` stack from Claude Code: stop the `python.exe` processes whose command line has
  `app.web|app.worker|app.main` (and their `start-demo.ps1 -Role ...` PowerShell windows), start the roles
  with `start-demo.ps1 -Role web|worker -Mt5`, wait for `http://localhost:8001/api/v1/health`, then
  `-Role engine` (health on port 8766). A Python-only change in the engine needs only the engine restarted.
- In Engine tests, `run(max_cycles=n)` ends with `shutdown()`, which disconnects MT5: read the heartbeat
  during the run (or call `_health()` after `start()`), not after it.
- `Path.write_text` without `newline="\n"` writes CRLF on Windows; the repo is LF (`.gitattributes`).
- i18next: a `count` parameter triggers plural lookups (`_one`/`_other`); name it `n` for plain numbers.
  Detector ids contain dots, so `codes:evidence.<id>` is nested JSON (`fib` → `retracement`).
- Real data beats samples: on 2026-10-05 the `-Mt5` stack showed FBS metals as OTHER, a manual position
  blocking every entry, stocks blocked by DATA_GAPS and two different account equities; no test had covered
  any of them.
- Frontend:
  - Passing the typed i18next `t` as a parameter fails with TS2589: put the text in a small component that
    calls `useTranslation()` itself.
  - `z.looseObject` types keys as `string`; use `z.object` where the page indexes translation keys by field.
  - Windows is case-insensitive: don't name a module `gauge.ts` next to `Gauge.tsx`. A file exporting a
    component may only export components (react-refresh lint): keep helpers in `*Model.ts` files.
  - A new page: add it to `src/app/shell/nav.ts`, replace its `PlaceholderPage` route in
    `src/app/routes.tsx`; engine queries go under `engineKey(id)`. Nav items can be `admin` (OWNER/ADMIN).
  - Secrets (engine keys, TOTP) never go through TanStack mutations or queries (their caches keep results):
    call `apiPost` directly and keep the result in component state.
  - Template literals in `new RegExp(...)` drop backslashes: use `String.raw`.
  - A new strategy parameter or strategy needs TH/EN texts (`strategies.param.<name>` in `common.json`,
    `codes:strategyName` / `codes:strategy`); parity tests read the Python models.
  - Parity tests read backend enums and `app/advisory/explanations.py`; TypeScript stays on 6.0.x
    (typescript-eslint 8).
  - API samples must be stable: pin wall-clock stamps and random ids in `tests/web/test_api_samples.py`
    (engine ids → `ENGINE`, user ids → `USER` / `USER_<NAME>`).
  - Large page tests (theories, profile, engines) set `vi.setConfig({ testTimeout: 20_000 })`: typing is slow
    when the suite runs in parallel.
- Python: docstrings over 110 characters fail ruff E501. `docs/TICKETS.md` uses CRLF (`scripts/tickets.py`
  handles it). Long edits are safer as a small Python script than as a bash heredoc (heredocs expand `\n`).

## Decisions the user may want to revisit

- **Manual trades on the bot's account** count toward the bot's limits (`risk.foreign_positions_policy:
  count`), measured against the paper book's equity in PAPER. With a large manual trade the bot opens nothing.
  Options: separate the bot's account from manual trading, or change the policy.
- **Alert metric** is win probability (needs closed shadow outcomes for calibration); setup strength works from
  day one.
- Chart-pattern and breakout setups default to the **nearer** stop (`stop_mode: invalidation` restores the
  textbook stop). All 9 strategies are enabled in `config.yaml` (unproven; PAPER).
- Hard ADVISORY failures create no opportunity; per-user holding styles don't change the scan timeframes yet
  (PLAN §A26).
- Forex exotics stay opt-in (wide spreads); OTHER is on.
- The DATA_GAPS check learns closed hours from the last ~400 bars: around a DST change a stock's shifted hour
  can count as missing for a few days; holidays (a whole missing day) still count as gaps.

## Open items needing the user

- Before Phase 11: Railway account access (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (`docs/COMPLIANCE.md`; gate `SUBSCRIPTIONS_ENABLED` +
  `SUBSCRIPTIONS_LEGAL_REVIEW`).
- TAA-1501 (cloud replay jobs): revisit when users without engines are served.
- `VAPID_SUBJECT` in `.env` is a placeholder; set a real contact if wanted.
- Set the owner's account profile on `/account` so alerts carry money (one click: "My engine's MT5 account").
