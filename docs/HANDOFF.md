# Session handoff

Last updated: 2026-10-06, later the same day (the learning-track session took over after the session that did
revisions 5–6, Phase 10, Phase 14 and Phase 13 core).
This file holds **state only**: rules and conventions live in `CLAUDE.md` and `docs/CODING_STANDARDS.md`,
design decisions in `docs/PLAN.md` (each ticket's "TAA-xxx decisions" notes), progress in `docs/TICKETS.md`.
What was built per ticket is in the git history. A separate **learning track** (Milestone 3) is designed in
`docs/PLAN_LEARNING.md` / `docs/TICKETS_LEARNING.md` (another session started it on 2026-10-06).

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md first (state, "Next work", gotchas), then docs/TICKETS.md
(progress, dependencies) and the PLAN sections the next ticket names.
Follow CLAUDE.md and docs/CODING_STANDARDS.md (§9 for the frontend; frontend/README.md for its commands).
Work on main, one ticket at a time, in the "Next work" order; another session may work on the learning track
(docs/*_LEARNING.md): commit by explicit paths only.
For PWA pages: build page tests from frontend/src/test/fixtures/api-samples.json (real API responses) and add
every new route a page reads to tests/web/test_api_samples.py and frontend/src/test/apiSamples.test.ts
(regenerate with TAA_UPDATE_API_SAMPLES=1). Run the full pytest suite and vitest one after the other, never
at the same time, and not while the local demo stack runs (the machine runs out of memory).
Check every change against real data, not only samples: the local stack on the real MT5 demo account (PAPER)
runs with scripts\start-demo.cmd -Mt5 (http://localhost:8001). After changing Python code or config.yaml,
restart that stack's web, worker and/or engine (web first when the heartbeat or a migration changed).
Commit at each ticket boundary (allowed); I push myself. LIVE stays off until I say so; subscriptions stay off.
Update docs/HANDOFF.md at the end of the session. Chat with me in Thai.
```

---

## Current state

- **Done:** Phases 0–10, 2A, 6A–6C, 8A, 12 (DEMO), **14 except the owner's part** (1401 live gate wiring, 1402
  security review, 1403 drills automated; 1404 final docs pass started) and **13** (1301 AI interface,
  1302 Anthropic provider, 1303 veto, 1304 AI page and narrative, 1305 AI on advisory). Revisions 5 (owner's profile drives
  the engine's risk) and 6 (manual trades matched to signals, TAA-1006) are done.
- **Not started / open:** Phase 11 Railway (**the only deferred work**, user decision 2026-10-06; AI is in
  scope), TAA-1403's last item (the owner repeats the drills on the LIVE machine), TAA-1404
  (final docs pass; README, runbooks and PLAN notes are current as of this session), Phase 15 (deferred).
- **Checks (2026-10-06, stack stopped):** full pytest **2791 passed, 7 skipped** (10 min); vitest 526; Playwright
  smoke 3; ruff, mypy, bandit clean; `pip-audit` and `npm audit` clean.
- **Git:** `main` only; the user pushes. Latest migration: **0041** (`entry_plan_intents`, TAA-1207).
- **The `-Mt5` stack** still runs the code from before the learning-track commits below: restart it (web
  first for the new `/learning` routes and the rebuilt PWA, then the engine for the magic registry and
  migration 0038), only with the user's go-ahead.

### Learning track, started 2026-10-06 (Milestone 3; `docs/PLAN_LEARNING.md`, `docs/TICKETS_LEARNING.md`)

- Design: 52 tickets in waves 0–9; the reasoning of the design conversation is in
  `docs/LEARNING_DISCUSSION.md`. New work stays separate from the existing process (§L0.2).
- **TAA-L901 (Wave 0, a fix for today's engine):** stable magic numbers (`app/engine/magic_registry.py`,
  migration 0038). Before, magic = base + index of the *enabled* strategies, so enabling/disabling/reordering a
  strategy with open positions re-mapped them; the loss tracker now counts the whole bot range.
- **TAA-L002:** golden harness `tests/golden/` (backtest trades, replay shadow trades, PAPER engine decisions
  and positions). Regenerate only on purpose with `TAA_UPDATE_GOLDEN=1` and review the JSON diff.
- **Wave 1 reports:** `app/learning/` (timing failure modes vs a random-walk baseline, the E[R] = p·W −
  (1 − p)·L − c split, manual-trade behavior) served on request by `GET /engines/{id}/learning/timing|
  expectancy|behavior` and the new PWA page **Learning** (Analysis group). Open in Wave 1: timing for manual
  trades (L701 item 8) and the stop history of manual positions (L808).
- Checks after these commits: unit 2351 + web 312 + golden 3 + engine integration 48 passed; vitest 535,
  lint, typecheck, build; ruff, mypy, bandit clean. The full pytest run with the stack stopped is still due.
- **TAA-L001 done** (`app.cli ticks probe`, read-only): FBS has no depth of market, `last`/`volume` are always
  0, ~58% of EURUSD ticks change neither bid nor ask (flag 96 alone; filter them), XAUUSD tick history ≥ 12
  months. Next: tick capture (TAA-L101…). Open questions Q2–Q8, Q12 in `docs/PLAN_LEARNING.md` §L18.

### TAA-1207: the bot sends split entries (2026-10-06, evening)

- The Trading profile's "Splitting an entry" now drives the bot (PLAN §A31 "TAA-1207 decisions"): the plan
  rides on the risk-profile document; `execution.entry_plans: true` in `config.yaml` (code default off).
  Owner's choice in the PWA: Scale in, 5 orders, equal weights, 0.5 × ATR, 0.01 lot per tap.
- Owner decisions: one plan = one trade for "Positions at the same time" and the per-symbol limit; heat sums
  every part including resting limits; unfilled limits live 4 h (16 × M15), and are cancelled when the
  market part closes, on any kill switch and before the Friday cut-off.
- DEMO: market part first, limits (BUY_LIMIT / SELL_LIMIT, same SL/TP, broker-side expiration +5 min) only
  after it is protected; `app/engine/plan_supervisor.py` follows them; the reconciler knows resting orders;
  SAME_PRICE parts go to break-even once one part has closed. PAPER mirrors it. FakeMT5 emulates pending
  orders. `demo-report` adds "no limit part left past its lifetime".
- **Checked on the FBS demo terminal (order_check only, 2026-10-06):** EURUSD, GBPUSD, USDJPY and XAUUSD
  accept a BUY_LIMIT with RETURN, FOK or IOC filling, with or without `ORDER_TIME_SPECIFIED`
  (`expiration_mode` 15). The engine uses RETURN + the broker expiration.
- **Critical fix found on the way (964221a):** `MT5Client.call` passed an empty `**kwargs` to the C module, and
  the real `order_check` / `order_send` then answer None with (-2, "Unnamed arguments not allowed"). **No DEMO
  order ever reached the broker before 2026-10-06 12:48 UTC**: the 5 accepted signals of the morning were
  REJECTED at `order_check`. FakeMT5 cannot show this; the opt-in contract test
  `TAA_MT5_TESTS=1 TAA_MT5_TRADING_TESTS=1 pytest -m mt5 -k order_check` (DEMO, order_check only) does.
- The `-Mt5 -Demo` stack was restarted at ~12:48 UTC with TAA-1207 and the fix (web, worker, engine; no open
  positions). The engine reports the owner's plan (cloud profile: SCALE_IN, 5 parts, 0.01 lot, 0.5 × ATR).

### What this session added (2026-10-05/06)

- **Revision 5 (PLAN §A33):** the owner's Trading profile drives the engine's risk inside the `config.yaml` cage
  (TAA-408 ceiling 3 %, TAA-710, TAA-924). Cage now 2 % / 4 % heat / 4 % daily / 8 % weekly (`.env` no longer
  overrides it). The scanner sizes the owner's lots with the profile too (without min RR).
- **Revision 6 (PLAN §A34, TAA-1006):** manual MT5 trades matched to the signals they followed (HIGH / LIKELY /
  UNMATCHED), the owner's correction, closed manual trades compared me / signal / bot in R.
- **Phase 10:** TAA-1004 recommendations (bootstrap CI, A16 rules, "Backtest this change" as a bounded job
  change), TAA-1005 analytics API and page (scopes PAPER / SHADOW / BACKTEST).
- **Phase 14:** LIVE path behind its gate (TAA-1401: flag, account-bound phrase, REAL account, gate per decision
  and before `order_send`, probation, banner, `LIVE_START` audit); `docs/SECURITY_REVIEW.md`; `db backup` /
  `db restore`; LIVE drills on FakeMT5; `docs/RUNBOOK_LIVE.md`.
- **Phase 13:** AI review (`app/ai/`): schema v1.0, Anthropic provider (`beta.messages.parse`,
  `claude-opus-5-5`, low effort, `fallbacks: "default"`), veto/advisory gate after all other checks (can only
  block), per-candle cache, daily budgets (`config.yaml` → `ai`), AI review page. `AI_PROVIDER=none` by default.
  TAA-1305 (2026-10-06): `ai_notes` (migration 0040) — the engine writes an opinion per new opportunity and
  TH/EN narratives of the ranking and recent shadow results on a background thread (`ai.advisory`, off by
  default, own budget); the PWA shows them labelled "AI opinion, not advice" (opportunity detail, Ranking,
  Analytics), the AI page shows accuracy/calibration, and alert settings have the opt-in AI filter (offered
  only once AGREE beats all opportunities, bootstrap CI). Gated by `AI_NARRATIVES`. PLAN §A8 TAA-1305 notes.
- PWA: chart follows the newest bar, strength-styled S/R zones; dashboard open opportunities and signal track
  record; live candle ≈ one heartbeat per second (per-detector pulse).

## Next work

1. **LIVE is ready to be switched on only by the owner.** What is left before real money:
   - the two-week DEMO soak (`docs/RUNBOOK_DEMO.md` §4): first started 2026-10-06 ~06:57 UTC, but no order
     reached the broker until the MT5 client fix, so it **really starts 2026-10-06 ~12:48 UTC** on the FBS demo
     account (`scripts\start-demo.cmd -Mt5 -Demo`, engine db `data/demo/engine-mt5.db`; the owner's Trading
     profile decides the risk; split entries per TAA-1207); `demo-report --days 14` from 2026-10-20 ~13:00 UTC;
   - the drills on the LIVE machine with the record table (`docs/RUNBOOK_LIVE.md` §2) — TAA-1403's last item;
   - the go-live checklist (`docs/RUNBOOK_LIVE.md` §1), then the owner's explicit go-ahead on the day.
   Never enable LIVE (`ENABLE_LIVE_TRADING`, the phrase) on the owner's behalf.
2. **AI:** built, off until a key is set. Set `AI_PROVIDER=anthropic`, `AI_API_KEY`, `AI_MODE=advisory` (entry
   reviews, records only) in `.env` on the engine machine and `ai.advisory.enabled: true` in `config.yaml`
   (opinions and narratives), then restart the engine; watch the "AI review" page and the opportunity detail.
   Costs real money: budgets `ai` (50 calls / $2 a day) and `ai.advisory` (100 calls / $3 a day).
3. **TAA-1404 final docs pass:** check README, both runbooks, CLAUDE.md and `.env.example` against reality once
   LIVE has run (or before the owner's go-live).
4. Phase 11 Railway: skipped for now; later only with the owner's Railway access and go-ahead.
5. **Learning track (Milestone 3):** in progress (see the section above and `docs/TICKETS_LEARNING.md`); it
   covers the owner's homework (scan every symbol, symbol character, tick features, adaptive selection). The
   findings below stay valid input:
   - Ranking covers the whole broker universe (549 symbols on the FBS demo). The opportunity scanner covers
     only the advisory requirements (allowlist + favourites + lists + `advisory.universe.auto_top_n: 30`) with a
     per-cycle time budget (~1–1.6 s per symbol per bar for the evidence scan).
   - Trading, candle streaming and charts cover only `ALLOWED_SYMBOLS` (EURUSD, GBPUSD, USDJPY, XAUUSD).
   - Strategy parameters are fixed in `config.yaml` (restart needed); detector parameters can come from the
     owner's theory settings (TAA-920).
6. Small open ideas: an aggregate of manual trades on the accuracy page once enough have closed; check that the
   owner's open manual trades (GBPUSD, EURUSD) show an R on Trade history when they close.

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

- **Drive C is nearly full (~5 GB free on 2026-10-06).** Asking MT5 for old ticks (`copy_ticks_range`) makes the
  terminal download whole months into `C:\MT5	aa-bot\Bases\<server>	icks` (~40–60 MB per month and
  symbol). An uncapped depth search filled the drive once; `ticks probe` is now capped with a free-disk
  guard. Keep any backfill bounded. The tick months deleted that day (before 2026-09) may read as empty until
  the terminal is restarted (its cache index still lists them).
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

- **Before LIVE:** the DEMO soak, the drills on the LIVE machine (record table in `docs/RUNBOOK_LIVE.md`), the
  go-live checklist, a separate `ENGINE_DB_URL` for LIVE, the MT5 password in Windows Credential Manager, and
  the explicit go-ahead. Only the owner sets `ENABLE_LIVE_TRADING` and the confirmation phrase.
- **AI (optional):** an Anthropic API key in `.env` (`AI_PROVIDER=anthropic`, `AI_API_KEY`), starting with
  `AI_MODE=advisory`; budgets in `config.yaml` → `ai` (default 50 calls and $2 a day).
- The current Trading profile uses 1.5 % per trade (inside the 2 % cage); lower it in the PWA if wanted.
- Phase 11 (skipped for now): Railway account access, only with an explicit go-ahead.
- Before ever enabling subscriptions: legal review (`docs/COMPLIANCE.md`; gate `SUBSCRIPTIONS_ENABLED` +
  `SUBSCRIPTIONS_LEGAL_REVIEW`).
- TAA-1501 (cloud replay jobs): revisit when users without engines are served.
- `VAPID_SUBJECT` in `.env` is a placeholder; set a real contact if wanted.
- Set the owner's account profile on `/account` so alerts carry money (one click: "My engine's MT5 account").
