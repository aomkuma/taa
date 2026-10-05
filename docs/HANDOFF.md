# Session handoff

Last updated: 2026-10-05. Single session on `main`. This file holds **state only**: rules and conventions live
in `CLAUDE.md` and `docs/CODING_STANDARDS.md`, design decisions in `docs/PLAN.md` (each ticket's "TAA-xxx
decisions" notes), progress in `docs/TICKETS.md`. What was built per ticket is in the git history.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md (state, "Next work"), docs/TICKETS.md (progress,
dependencies) and docs/PLAN.md §A15 (PWA frontend) and §A28 (localization & advisory UI); the page tickets
name their own sections (§A14 APIs, §A26/§A27 advisory, §A30/§A31 settings, §A32 engines).
Follow CLAUDE.md and docs/CODING_STANDARDS.md (§9 for the frontend; frontend/README.md for its commands).
This is the only session: work on main, one ticket at a time, in the "Next work" order. Continue with
TAA-913 (system & settings).
For PWA pages: build page tests from frontend/src/test/fixtures/api-samples.json (real API responses) and add
every new route a page reads to tests/web/test_api_samples.py and frontend/src/test/apiSamples.test.ts
(regenerate with TAA_UPDATE_API_SAMPLES=1). Run the full pytest suite and vitest one after the other, never
at the same time, and not while the local demo stack runs (the machine runs out of memory).
Commit at each ticket boundary (allowed); I push myself. LIVE stays disabled; subscriptions stay off.
Update docs/HANDOFF.md at the end of the session. Chat with me in Thai.
```

---

## Current state

- **Done:** Phases 0–8, 2A, 6A–6C, 8A and 12 (DEMO orders, pulled forward). Phase 9: 901–912 and 915.
  Phase 10: 1001–1003.
- **Not started:** Phase 11 (Railway), M2 Phases 13 (AI, optional) and 14 (LIVE), Phase 15 (deferred
  backlog: TAA-1501 cloud replay jobs).
- **Checks** (last full runs): pytest 2683 passed, 7 skipped (~7–9 min; the Postgres tests run when
  `TAA_POSTGRES_URL` is set); ruff, mypy, bandit clean; frontend lint, typecheck, build clean, vitest 334.
- **Git:** `main` only (the user pushes; `git push` from Claude Code
  fails on the interactive GitHub login). Latest migration: **0032**.
- **2026-10-05 extras** (outside the tickets, at the user's request): `start-demo.ps1 -Mt5`, the searchable
  symbol picker on the charts page, `sync.chart_timeframes` (every chart timeframe streamed) and the
  service-worker "new version" banner.

## Next work

1. Phase 9 pages: **TAA-913** system & settings, 916–923 (ranking, opportunities,
   watchlists, accuracy, theories, account/plan/admin, trading profile, engines), then **914** PWA polish.
   The backend for every page exists (API list below).
2. Phase 10: TAA-1004 recommendations (preparation below), then TAA-1005 analytics API & pages.
3. Phase 11 Railway deployment: only with the user's Railway access and go-ahead. Then stop for the
   Milestone 1 review.

### Notes for the remaining tickets

- **APIs the pages read** (all under `/api/v1`):
  - Session `/auth/session|login|logout|step-up|profile`; `GET /me/feed` (`own` false = the owner's market
    feed, account details redacted).
  - Live data: `GET /engines/{id}/stream` (SSE; topics status, quotes, positions, notifications, decisions).
  - Owner: status, account, positions, trades, intents, decisions, breakers, kill-switch, symbols, candles,
    config, audit/verify, commands, engines, backtests.
  - Advisory: ranking, opportunities (`probability`, `contributions`, plan, `my_sizing`), shadow-trades,
    accuracy (`?mine=true`), threshold-explorer, theory-scoreboard, calibration;
    `/advisory/preferences|watchlists|favourites|detectors`.
  - Me: notifications, push key/subscribe/unsubscribe/test, preferences; `/me/alerts`, `/me/entitlements`,
    `/me/account-profile`, `/me/export`, `/me/erase`; admin `/admin/users|plans`.
- **TAA-917:** opportunity pushes link to `/opportunities/{id}` (app/worker/push.py) and the notification centre
  to `/charts?opportunity=`: add the `/opportunities/:id` route. TAA-917 / 919: add TH/EN texts for the
  `codes:` they show (opportunity statuses, accuracy codes).
- **TAA-914:** the app icon is a placeholder SVG; maskable/Apple icons, API caching rules (network-first,
  `/api/` never answered with `index.html`) and the install prompt are still to do.
- **TAA-1004 preparation:** fills store no entry context; callers pass an `EntryContext` per signal id
  (`context_from_decision`). For backtests, `BacktestEngine` must keep the selected signal's `MarketContext`
  (or decision record) by signal id: a small change in `app/backtest/engine.py`. Until exit-time facts and
  news overlap are supplied, LOSS_REGIME_SHIFT, LOSS_VOLATILITY_SPIKE and LOSS_NEWS_PROXIMITY never fire.
- **TAA-1005:** `analytics.attribution.<CODE>` needs TH/EN texts in `frontend/src/i18n/`; reuse
  `createSeriesChart` (`src/pages/charts/chartAdapter.ts`) for equity/drawdown.
- A new replicated table needs a sample row in `tests/sync_data.py` (a test enforces it).

## Local environment

- **Demo stack** (`scripts\start-demo.cmd`, details in the script header): web + worker + PAPER engine, each in
  its own window.
  - Default: FakeMT5 engine, web `http://127.0.0.1:8000`, `data/taa_cloud.db`, engine `fake demo` in
    `.env.demo`. It shares `data/heartbeat.json` and the kill-switch file with a real engine.
  - `-Mt5` (the user's preferred way to look at the app): PAPER on the real MT5 terminal (FBS demo account),
    web `http://localhost:8001` with its own database `data/demo/cloud-mt5.db`, engine `mt5 demo (paper)` in
    `.env.demo-mt5`, health port 8766. Both stacks can run at once.
  - Web user `aomkuma` (OWNER) in both databases; `app.cli web reset-password` resets it.
- **MT5:** a dedicated portable terminal at `C:\MT5\taa-bot`. `doctor` passes (warning: Algo Trading off).
  Demo account: USD, 1:200, hedging, with a manual BTCUSD position (magic 0) that counts toward exposure but is
  not shown in the PWA (PAPER pages show only the bot's paper book). `.env` has `TRADING_MODE=PAPER`; DEMO
  orders need `TRADING_MODE=DEMO` + `ENABLE_DEMO_TRADING=true` and `docs/RUNBOOK_DEMO.md` (DEMO has only run
  on the FakeMT5 trade server so far; limit parts of entry plans are not sent yet).
- **PostgreSQL 16** (service `postgresql-x64-16`, shared with other projects): role `taa`, database
  `taa_test`, URL `TAA_POSTGRES_URL` in `.env`. Never touch other projects' databases; never clean up
  databases by `LIKE` pattern (`_` is a wildcard).

## Gotchas

- **Memory (16 GB):** full pytest + vitest at once, or either next to the demo stack, crashes workers (vitest
  exit 134, numpy `ArrayMemoryError`, pandas access violations, argon2 `HashingError`). Run them one after the
  other; with the stack up use `npx vitest run --maxWorkers=2`; rerun a lone failure before investigating.
- Web Push is untested with a real push service so far: turn it on in the browser on the `-Mt5` stack
  (`.env` has the VAPID pair; `VAPID_SUBJECT` is a placeholder) and send a test from the Notifications page.
- The service worker is `frontend/src/sw/sw.ts` (`injectManifest`, own `tsconfig.sw.json`).
- After a frontend rebuild the open PWA keeps the old version until the "new version" banner's Reload (or
  all tabs are closed).
- Don't edit the working tree during a full test run (the migration-parity test reads migration files).
- Frontend:
  - Passing the typed i18next `t` as a parameter fails with TS2589: put the text in a small component that
    calls `useTranslation()` itself.
  - `z.looseObject` types keys as `string`; use `z.object` where the page indexes translation keys by field.
  - Windows is case-insensitive: don't name a module `gauge.ts` next to `Gauge.tsx`. A file exporting a
    component may only export components (react-refresh lint).
  - A new page: add it to `src/app/shell/nav.ts`, replace its `PlaceholderPage` route in
    `src/app/routes.tsx`; engine queries go under `engineKey(id)`.
  - A new strategy parameter or strategy needs TH/EN texts (`strategies.param.<name>` in `common.json`,
    `codes:strategyName` / `codes:strategy`); parity tests read the Python models.
  - Parity tests read backend enums and `app/advisory/explanations.py`; TypeScript stays on 6.0.x
    (typescript-eslint 8).
  - API samples must be stable: pin wall-clock stamps and random ids in `tests/web/test_api_samples.py`.
- Python: docstrings over 110 characters fail ruff E501. `docs/TICKETS.md` uses CRLF (`scripts/tickets.py`
  handles it). Long edits are safer as a small Python script than as a bash heredoc.

## Decisions the user may want to revisit

- Chart-pattern and breakout setups default to the **nearer** stop (`stop_mode: invalidation` restores the
  textbook stop); the 8 pattern setups ship disabled (PLAN §A29).
- Hard ADVISORY failures create no opportunity; per-user holding styles don't change the scan timeframes yet
  (PLAN §A26).

## Open items needing the user

- Before Phase 11: Railway account access (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (`docs/COMPLIANCE.md`; gate `SUBSCRIPTIONS_ENABLED` +
  `SUBSCRIPTIONS_LEGAL_REVIEW`).
- TAA-1501 (cloud replay jobs): revisit when users without engines are served.
- `VAPID_SUBJECT` in `.env` is a placeholder; set a real contact if wanted.
