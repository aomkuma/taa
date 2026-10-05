# Session handoff

Last updated: 2026-10-05 (session that started the Phase 9 pages), single session on `main`. Done in this
session: TAA-903 app shell, 904 dashboard, 905 charts, 906 symbols, 907 positions & history, 908 signals &
decisions, 909 strategies. The previous session (2026-10-04) did TAA-804 … TAA-8A5. No branch holds unmerged work. This file
holds **state only**. Rules and conventions live in `CLAUDE.md` (loaded automatically by Claude Code) and
`docs/CODING_STANDARDS.md`.

---

## Prompt for the next session

The user's decision (2026-10-04): **one session at a time**, working in the main checkout. No parallel sessions,
no extra worktrees. The user uses TAA for themselves now; selling it comes later, but the multi-user foundation
is built properly in ticket order (it now is: Phase 8A is done).

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md (state, the "Next work" order), docs/TICKETS.md (progress,
dependencies) and docs/PLAN.md §A15 (PWA frontend) and §A28 (localization & advisory UI); the page tickets
name their own sections (§A14 APIs, §A26/§A27 advisory, §A30/§A31 settings, §A32 engines).
Follow CLAUDE.md and docs/CODING_STANDARDS.md (§9 for the frontend; frontend/README.md for its commands).
Done: Phases 0–8, 8A and 12 (cloud replay jobs moved to the deferred TAA-1501, Phase 15).
Partly done: Phase 9 (901–909, 915), Phase 10 (1001..1003). Not started: Phase 11 (Railway), M2 Phases 13–14.
This is the only session: work on main in C:\Users\korap\taa, one ticket at a time, in the order of the
"Next work" list in docs/HANDOFF.md. Continue with TAA-910 (backtests UI).
A local PostgreSQL 16 is available for tests: `pytest -m postgres` uses TAA_POSTGRES_URL from .env (role taa,
database taa_test); never touch other projects' databases on that server.
LIVE stays disabled until Phase 14 and an explicit go-ahead. Subscriptions stay off (SUBSCRIPTIONS_ENABLED=false).
For PWA pages: build page tests from frontend/src/test/fixtures/api-samples.json (real API responses) and add
every new route a page reads to tests/web/test_api_samples.py and frontend/src/test/apiSamples.test.ts
(regenerate with TAA_UPDATE_API_SAMPLES=1). Run the full pytest suite and vitest one after the other, never
at the same time (the machine runs out of memory).
Commit at each ticket boundary (allowed). Pushing from Claude Code fails (GitHub needs an interactive login),
so I push myself. Update docs/HANDOFF.md at the end of the session. Stop for review at the end of Milestone 1,
or at any phase boundary if I ask. Chat with me in Thai.
```

---

## Current state

- **Done:** Phase 0 (TAA-001..009), Phase 1 (TAA-101..110), Phase 2 (TAA-201..206), Phase 2A
  (TAA-2A1..2A10), Phase 3 (TAA-301..307), Phase 4 (TAA-401..407), Phase 5 (TAA-501..506) and Phase 6
  (TAA-601..606), Phase 12 (TAA-1201..1206, pulled forward: DEMO broker orders) and Phase 6A
  (TAA-6A1..6A5, symbol universe & suitability ranking) and Phase 6B (TAA-6B1..6B5, watchlists,
  opportunities & alert windows), Phase 6C (TAA-6C1..6C5, shadow trades, accuracy & calibration).
- **Design rev. 4 (2026-10-04, docs only):** PLAN §A32 covers the engine registry and per-user self-hosted engines.
  Engine keys move from the web env into an `engines` table owned by a user. The PWA Engines page issues
  `ENGINE_ID` and `ENGINE_HMAC_SECRET` (shown once), and the browser generates `CONTROL_TOTP_SECRET`, which never
  reaches the cloud. New tickets: TAA-708, 709, 811, 923. Rollout is fail-closed: one ACTIVE engine until 709, and
  `MULTI_ENGINE_ENABLED=false`.
- **Also done:** Phase 7 (TAA-701..709), Phase 8 (TAA-801..811) and Phase 8A (TAA-8A1..8A5). TAA-810's optional
  cloud replay jobs moved to TAA-1501 (Phase 15, deferred; reasons in TICKETS): replay runs locally with
  `python -m app.cli advisory replay` and its rows replicate up.
- **In progress (progress table):** Phase 9 10/23 (901–909,
  915), Phase 10 3/5 (1001..1003). Not started: Phase 11 (Railway), M2 Phases 13 (AI, optional) and 14
  (LIVE). The order of the remaining tickets: "Next work" below.
- **Checks:** 2678 passed, 7 skipped (6 real-terminal, 1 contract case defined from bar 0) after TAA-909; the
  Postgres tests run when `TAA_POSTGRES_URL` is set (they ran). The full suite takes ~7–9 min. ruff, mypy and
  bandit are clean. Frontend: `npm run lint`, `typecheck`, `test`, `build` in `frontend/` (251 tests after TAA-909). Architecture rules are enforced by `tests/unit/test_architecture.py`.
- **Design rev. 3** (committed docs, code later in its phases):
  - PLAN §A31 "Trading profile & entry plans":
    - style slider 0–100 (defensive → offensive) with five anchor presets
    - risk per signal (all entries) and portfolio heat
    - entry splitting: `SINGLE`, `SAME_PRICE` with staggered TPs, `SCALE_IN` with a shared stop
    - lot per tap (`lot_unit`); lots computed from the risk budget, never rounded up
    - M2 limits = min(profile, local `RiskConfig`)
  - The user's choices: all three split modes, lots computed from the budget, both risk budgets (per signal
    and portfolio). Item 1 was to be built now; item 2 follows the phase order.
  - Ticket items marked "(rev. 3)": TAA-401, 402, 406, 6B1, 8A4, 810, and the new TAA-922 (Phase 9).
- **Built:**
  - config (pydantic-settings + `config.yaml`, percent risk units, hard ceilings)
  - secrets (`keyring:` indirection, log redaction), JSON logging
  - SQLite/Postgres storage with Alembic (migrations 0001–0017), hash-chained audit log
  - kill switch; CLI (`config`, `db`, `audit`, `kill`, `doctor`, `backtest`, `breaker`, `demo-report`,
    `advisory rank|replay|calibrate`, `strategy list|enable`); CI config
  - cloud sync, engine side (Phase 7, PLAN §A13):
    - `app/security/hmac_auth.py`: signer/verifier (METHOD|TARGET|TS|NONCE|BODY_SHA256), skew 300 s, nonce
      store (memory; `app/sync/nonces.py` SQL, `ingest_nonces`, migration 0014), dual-secret rotation
    - `app/sync/outbox.py` + `client.py` + `runtime.py`: `outbox_events` (migration 0015), priorities,
      coalescing, gzip batches, backoff, DEAD after `max_attempts`, backlog cap, metrics in `status()["sync"]`;
      sender thread only when `sync.enabled`
    - TAA-703 ingest (PLAN §A13 "TAA-703 decisions"): `app/sync/events.py` (replicated tables as
      `ReplicaSpec`s; strict payload schemas generated from the columns; envelopes), `replication.py`
      (`after_flush` hook → outbox in the same transaction, coalesced per row; `snapshot()` once per engine DB
      and on RESYNC; installed by the engine and by the CLI when `sync.enabled`), `ingest.py`
      (`IngestService`: per-event rejection, upserts guarded by `replica_versions`, audit continuity in
      `audit_replicas`, command results via `CommandQueue.record_result`), route
      `app/web/routers/ingest.py` behind `SignedEngine` (`app/web/deps.py`); `WebSettings` gains
      `ENGINE_ID`, `ENGINE_HMAC_SECRET`, `ENGINE_HMAC_SECRET_PREVIOUS`. The sender parks events the cloud
      rejects as DEAD at once; batches are capped at 1000 events and `sync.max_batch_bytes`.
    - TAA-704 route: `GET /api/v1/engine/commands?cursor=` (`app/web/routers/engine.py`): 200 with
      `commands` + `cursor`, or 204 after 25 s; tested against the engine's own `CommandPoller`.
    - TAA-803 read APIs (PLAN §A14 "TAA-803 decisions"): `/api/v1/engines/{engine_id}/...` in
      `app/web/routers/data.py` + `app/web/readmodels.py`, `OwnedEngine` in `app/web/deps.py`; IDOR test walks
      every route (`tests/web/test_data_api.py` `ROUTES`: add new engine routes there).
    - TAA-804 SSE (PLAN §A14 "TAA-804 decisions", migration 0022): `GET /api/v1/engines/{id}/stream`
      (`app/web/routers/stream.py`, `app/web/stream.py`) over a per-engine change feed that ingest writes in
      its transaction (`app/sync/stream.py`: `stream_heads` + `stream_events`, commit-ordered `seq`, newest
      5000 kept). `ready`/`reset`/topic events/`: ping` with `id`/`end`; `Last-Event-ID` resumes; 10-minute
      streams; 4 per user. Tests shorten the timing with `ctx.streams.timing = StreamTiming(...)`.
    - TAA-805 control API (PLAN §A14 "TAA-805 decisions"): `POST|GET /api/v1/engines/{id}/commands`,
      `GET .../commands/{cid}` (`app/web/routers/control.py`); step-up, one body with per-type fields, owned
      engines only, 409 for revoked engines; `COMMAND_QUEUED`/`COMMAND_RESULT` on the `web` audit chain; command
      state on the stream (`status`/`command`). The engine control TOTP is never returned, audited or streamed.
    - TAA-811 engine management API (PLAN §A32 "TAA-811 decisions"): `GET|POST /api/v1/engines`,
      `POST .../{id}/rotate|revoke` (`app/web/routers/engines.py`); secrets once with `no-store`; OWNER role
      lists (`?scope=all`) and revokes every engine but rotates only its own; 5 new secrets per user per hour
      counted from the audit chain. `EngineErrorCode` ↔ `frontend/src/i18n/codes.ts` `ENGINE_ERRORS` with TH/EN
      texts in the new `codes` catalog (`locales/*/codes.json`).
  - cloud worker (TAA-808, PLAN §A14 "TAA-808 decisions", migration 0023): `python -m app.worker [check]`,
    `app/worker/` (`jobs.py` queue with leases and backoff retries, `schedule.py` periodic tasks claimed once
    across workers, `retention.py` housekeeping only, `service.py` loop + heartbeat + `worker_health`),
    env-only `WorkerSettings`. Handlers register by kind (Web Push 806, backtests 807).
  - heartbeats & watchdog (TAA-705 items 1–2, PLAN §A13 "TAA-705 decisions", migration 0024): engine
    `heartbeat` events with quotes and a market schedule (`app/sync/heartbeat.py`), cloud `engine_heartbeats`,
    worker task `engine_watchdog` (`app/worker/watchdog.py`) raising ENGINE_OFFLINE/ENGINE_BACK as
    `notifications` rows (`app/sync/notifications.py`) + stream events, pushed by TAA-806.
  - Web Push (TAA-806, PLAN §A14 "TAA-806 decisions", migration 0025): `scripts/generate_vapid_keys.py`,
    `app/worker/push.py` (dispatch task + `push.send` jobs, dedup 10 min, 20/h, CRITICAL exempt, push-service
    endpoint allowlist), `app/web/routers/notifications.py` (key, subscribe/unsubscribe/test, notification
    centre, preferences). The local `.env` has a generated VAPID pair (subject `mailto:owner@example.com`;
    change it if you like) and `WORKER_ENV=development` (2026-10-04, at the user's request). The PWA service
    worker's `push` handler is still to do (TAA-912/914).
  - cloud backtests (TAA-807, PLAN §A17 "TAA-807 decisions", migration 0026): presets + bounded request,
    `backtest.run` worker jobs on the engine's uploaded history, results/compare APIs under
    `/api/v1/engines/{id}/backtests`. Tests: `tests/backtest/test_cloud_backtests.py` (CLI parity with GOLDEN).
  - advisory APIs (TAA-809, PLAN §A14 "TAA-809 decisions", migration 0027): per-user preferences, watchlists,
    favourites, detector catalog, profile; per-engine ranking, opportunities with contributions, shadow
    statistics, calibration; the engine's `advisory-config` with ETag/304.
  - opportunity push (TAA-810, PLAN §A30 "TAA-810 decisions", migration 0028): worker task
    `opportunity_alerts` → OPPORTUNITY notifications with the personalizer's TH/EN push (top-3 contributions,
    rev. 3 entry plan, badge) and silent same-tag OPPORTUNITY_UPDATE replacements. Cloud replay jobs moved to
    TAA-1501 (deferred).
  - risk budget for alerts (user decision 2026-10-04, option C): `alerts.when_risk_full` PAUSE (default) or
    WARN when an opportunity would exceed the heat or position budget (PLAN §A30 TAA-810 notes).
  - tenancy (TAA-8A1, PLAN §A30 "TAA-8A1 decisions"): `Role`, `require_roles`, ADMIN without trading controls,
    PDPA export/erasure (`app/web/privacy.py`, `app/web/routers/me.py`), admin user list.
  - plans & entitlements (TAA-8A2, PLAN §A30 "TAA-8A2 decisions", migration 0029): typed keys,
    `EntitlementService.resolve`, seeded OWNER/FREE/PRO, enforcement in API, alerter and compute union.
  - account profiles & cloud sizing (TAA-8A3, PLAN §A30 "TAA-8A3 decisions", migration 0030):
    `/me/account-profile`, `SpecCalculator`, `HistoryRates`, `size_manual`; MT5 cross-check in tests.
  - multi-user personalizer (TAA-8A4, PLAN §A30 "TAA-8A4 decisions", migration 0031): market feed for
    subscribers (`app/web/feed.py`), owner-account redaction, per-user ranking/accuracy/sizing/alerts, compute
    union over engine users. Tests: `tests/web/test_market_feed.py`.
    - TAA-706 candle sync (PLAN §A13 "TAA-706 decisions", migration 0021): `candles` events of up to 1000
      closed bars into the per-engine `history_candles`; `CandleStreamer` on the engine's candle poll (per
      symbol back-off, so crypto streams at weekends); `python -m app.cli sync upload-history [--send]` and
      `scripts/download_history.py --upload`; `OutboxSender.drain()` for tools.
    - TAA-709 engine-scoped replicas (PLAN §A32 "TAA-709 decisions", migration 0020): every replicated
      table has `engine_id` (mixins `EngineKeyed`/`EngineTagged`); the engine writes `LOCAL_ENGINE` and looks
      rows up with `(LOCAL_ENGINE, key)`; the cloud sets the signer's id (never on the wire); `source_id` for
      tables without a natural key; several engines may be active. Two engines with identical local rows are
      tested in `tests/web/test_engine_scoped_replicas.py`.
    - TAA-708 engine registry (PLAN §A32 "TAA-708 decisions"): table `engines` (migration 0019),
      `app/web/engines.py` `EngineRegistry` (issue/rotate/revoke/list/import-env, secrets encrypted with HKDF
      purpose `engine-hmac-secret`, 5 s key cache, rotation hand-over, first/last seen, limits: one ACTIVE
      engine per deployment until 709, `WEB_MAX_ENGINES_PER_USER`, `MULTI_ENGINE_ENABLED=false`), `Verifier`
      reads keys through `KeyLookup`, `SignedEngine` carries `owner_user_id`. CLI `python -m app.cli web
      engine add|rotate|revoke|list|import-env` and `python -m app.cli engine new-totp`. Web tests pair an
      engine with `tests/web/conftest.py` `pair_engine()`. To pair the local engine with `python -m app.web`:
      create the owner, then `web engine import-env --owner NAME` (uses the `.env` ENGINE_* values).
    - `app/security/totp.py` + `app/sync/commands.py`: long-poll client thread, engine-loop processing,
      allowlist, expiry, single-use TOTP, results as `command_result` outbox events; `command_log`;
      `app/sync/command_queue.py` (cloud queue, `engine_commands`, migration 0016); strategy disable persisted
      in `engine_state` (`app.cli strategy enable` re-enables); FLATTEN also flattens PAPER positions
  - read-only MT5 client and gateway (explicit login, account verification, order functions blocked,
    `symbols(group)`, `ticks_range`)
  - multi-asset FakeMT5 (schedules, ticks, fixed and FBS-tiered leverage)
  - ServerClock (FBS = EET, `Europe/Athens`)
  - closed-candle service with watermarks, quality checks, quote service
  - history store (Parquet/SQL) and downloader
  - indicators (`app/indicators/`): trend, momentum, volatility, tick-volume features, and price action
    (candle anatomy, confirmed swings, structure, S/R zones, breakouts). Formulas, warm-up positions and TA-Lib
    differences are in `docs/INDICATORS.md`. Every indicator is registered in
    `tests/unit/test_indicators_contract.py` (warm-up, look-ahead and short-input checks).
  - evidence engine (`app/evidence/`, PLAN §A29):
    - framework, multi-degree zigzag, registry with prerequisite closure, look-ahead harness
    - 61 registered detectors: Fibonacci, levels, chart patterns, candlesticks, momentum, trend,
      volatility/volume, sessions, Ichimoku, structure, smart money, harmonics, Elliott
    - harmonics (TAA-2A7, `harmonics.py`): table-driven XABCD (Gartley, Bat, Butterfly, Crab, Cypher, Shark,
      AB=CD). The PRZ is the intersection of D's ratio bands; completion is the first touch of the PRZ after C
      is confirmed; quality = 1 − mean ratio error (D scored at the ideal D inside the PRZ).
    - Elliott (TAA-2A8, `elliott.py`, tier T3, `heuristic: true`): one detector `elliott.wave` with states
      `wave3`, `wave5`, `c_completion`; hard rules filter, Fibonacci guidelines score, primary + alternates per
      bar with confidence = score / max(1, Σ scores).
    - selective computation (TAA-2A9): `plan_from_config(config, only=union)`; the cloud's union only narrows
      the locally enabled set, unknown ids are logged and skipped; `ids_in_families` for family toggles.
    - (rev. 3, TAA-2A10) `fib.extension_level`: 127.2/161.8/261.8/423.6 % extensions as support/resistance
      (two-point and trend-based). Candle location sources now include it, `fib.cluster` and trendline
      bounces; breaks don't count (`prev_high_low` uses `reject` variants only). Candle records carry
      `at_levels` (the i18n keys of the levels they sat on).
    - catalog and rules in `docs/PATTERNS.md`; every detector must be documented there and pass the harness
      (`tests/unit/test_evidence_catalog.py`)
    - test helpers: `tests/evidence_harness.py` (harness, `scan_one`) and `tests/evidence_paths.py` (`path` =
      straight legs between vertices, `bars` = explicit OHLC rows)
  - strategy engine (`app/strategy/`, PLAN §A7, §A29; overview in `docs/STRATEGIES.md`):
    - models (`signal_models.py`): `Signal` (idempotency key, expiry, score, conditions → setup strength,
      evidence with relations, `confluence` points), `MarketContext`, `TimeframeState`, `StrategyContext`
    - `context_builder.py`: per-timeframe fetch + indicators, close-time alignment (`context_at` works on
      pre-analyzed frames, so backtests analyze once), S/R levels, session, per-TF analysis logs, optional
      evidence engine per timeframe; `regime_detector.py` (thresholds in `config.yaml` → `regime:`)
    - `base_strategy.py` + `registry.py` + `catalog.py`: params validated at startup (even for disabled
      entries); the plugin boundary turns a crash or a foreign signal into HOLD `STRATEGY_ERROR`;
      `StrategySet.evaluate` enriches every signal with confluence (TAA-307)
    - `arbitration.py`: duplicates → cooldown → BUY/SELL conflict → ranking; cooldown state exportable
    - `example_trend_pullback` (enabled, demo) and 8 pattern setups in `setups.py` (all `enabled: false` in
      `config.yaml`); shared entry rules in `rules.py`; every demo entry carries `DEMO_UNPROVEN`
    - confluence score (`app/evidence/confluence.py`, weights in `evidence.confluence` and docs/PATTERNS.md):
      core checklist 40 pts + noisy-OR per family capped at the family weight − 0.75 × conflicts
    - architecture rule: `app.indicators`, `app.evidence`, `app.strategy` never import broker services,
      storage, security or settings loaders
  - risk and decisions (Phase 4, PLAN §A8–§A10, §A31):
    - `app/risk/reasons.py`: every A8 reason code; `checks.py`: `Check` (value, threshold, HARD/ACCOUNT kind)
    - `position_sizer.py`: A9 steps in Decimal, broker loss cross-checked against tick value (loss rounded
      up past float noise), margin and margin-level checks; entry plans (`SINGLE` / `SAME_PRICE` /
      `SCALE_IN`, weights, `lot_unit` taps, drop-deepest-part) share the same code path; hypothesis
      properties in `tests/property/test_sizing_properties.py`
    - `exposure_manager.py`: risk to stop measured from the open price (a stop past break-even risks 0),
      heat incl. manual positions, unknown risk for positions without a stop, counts, correlation groups
      (other symbols only), per-currency direction, margin utilization, effective leverage
    - `loss_tracker.py`: broker-day/ISO-week baselines (Europe/Athens), cash flows, HWM on flow-adjusted
      equity, consecutive losses from closing bot deals, every deal booked once (tables `risk_*`, migration 0003)
    - `circuit_breaker.py` + `breaker_monitor.py`: A10 table, HEALTHY / COOLDOWN / NEXT_DAY / NEXT_WEEK /
      MANUAL resets, latching after repeated trips, MAX_DRAWDOWN reset needs acknowledgement, audited and
      notified; order-path breakers inactive in PAPER (tables `breaker_*`, migration 0004)
    - `mode_gates.py`: DEMO/LIVE gates with full truth tables (not wired to orders); `limits.py`:
      `effective_risk(local, profile)` only ever tightens
    - `app/market_data/trading_sessions.py`: windows in exchange-local timezones (DST-aware, may span
      midnight), daily breaks, Friday cutoff; `app/news/calendar.py`: manual blackouts
    - `app/engine/decision_engine.py`: all checks evaluated and persisted (`decision_records`,
      `decision_checks`, migration 0005); EXECUTION vs ADVISORY profile; one test per M1 reason code
  - backtesting (Phase 5, PLAN §A17):
    - `app/execution/fill_model.py` (next-open fills, bid/ask, SL first, gap fills) and
      `simulated_broker.py` (account, market/limit orders, seeded slippage, commission, swap with triple
      day, deals, MAE/MFE; implements `ProfitCalculator`; rates from its own traded pairs first);
      `management.py` (A11 break-even / trailing / time stop, shared with TAA-603)
    - `app/backtest/engine.py`: one loop over all symbols' entry-bar closes running the real context,
      strategies, arbiter, decision engine, sizer, loss tracker and breakers; `conversion.py`
      (`SeriesRates`, direct / inverse / one-hop cross, last close ≤ t); `metrics.py`, `report.py`
      (summary.json, trades.csv, equity.csv, limitations); `robustness.py` (walk-forward, sensitivity grid
      with stability, Monte Carlo, overfitting warnings); `runner.py` (load from `data/history`, data hash)
    - CLI: `python -m app.cli backtest --server <srv> --symbols ... --start ... --end ...`
    - non-positive prices (WTI 2020): `analyze_frame` marks bars `valid`; `context_at` flags
      `INVALID_OHLC` while a bad print is in the strategy window, so entries are rejected (`DATA_INVALID`);
      simulated margin uses |price|; documented in PLAN §A24
  - PAPER runtime (Phase 6):
    - `app/engine/orchestrator.py` (`Engine`): PAPER only (DEMO/LIVE refused); per cycle kill switch,
      reconnect, quotes → breakers → paper fills → position management; new closed bars (watermarks) →
      context (with evidence) → strategies → arbiter → decision → paper order; health interval: loss
      tracking, breaker ticks, storage/disk, marks, heartbeat; clock re-verification (idle market = no
      verdict, entries stay blocked until verified). Entry point `python -m app.main --mode paper [--fake]`.
    - `app/engine/paper.py`: `PaperExecution` (persisted book: `paper_accounts/intents/positions`,
      migration 0006; intent key = signal key + part, unique; restore at startup) and `LiveRates`;
      `SimulatedBroker.on_quote` gives tick-level fills; paper orders carry the signal's expiry, so an order
      left pending by a stop expires instead of filling late; starting balance = the real account's equity
      at the first start unless `paper.initial_balance` is set
    - `app/engine/position_manager.py`: A11 rules on every quote with stop invariants (re-attach a missing
      stop, favourable only, stops level, rate limit), strategy close signals and time-stop bars per bar
    - restart safety: arbiter cooldowns and last entries in `engine_state` (migration 0007); a real
      position with the bot's magic trips ACCOUNT_CHANGE + a CRITICAL event
    - `app/monitoring/alerts.py`: event types and severities, `EventBus` with dedupe, JSON-lines sink
      (`logs/events.jsonl`); `health_check.py`: loopback `/health` and the heartbeat file
      (`data/heartbeat.json`); `scripts/watchdog.ps1` (restarts a stale engine, not a deliberate stop) and
      `scripts/setup_windows_host.ps1` (Task Scheduler, run it yourself; `-WhatIf` first)
  - DEMO execution (Phase 12, DEMO account only; `docs/RUNBOOK_DEMO.md`):
    - `app/broker/execution.py`: `RequestBuilder` (deal / SLTP / close, filling resolver, deviation, GTC,
      magic, ≤ 25-char ASCII comment, no request without SL) and `ExecutionGateway` (refuses non-DEMO modes
      and non-DEMO accounts; `order_send` → `None` is reported as UNKNOWN); `build_trading()` in the factory
      (DEMO + `ENABLE_DEMO_TRADING` only)
    - FakeMT5 trade server (`app/broker/fake_trading.py`): validation like the real server, execution,
      SL/TP, closes, stop processing, `desk.force(retcode | None, executes=...)`, `price_override`
    - `app/engine/order_manager.py`: intent state machine (`order_intents`, migration 0008) with
      write-ahead, `order_check`, pre-send re-check, the §A12 retcode matrix (UNKNOWN → DUPLICATE_EXECUTION;
      halting codes → kill switch; SYMBOL_RESTRICTED breaker added) and the post-fill guard (slippage,
      realized risk reduce/close, SL re-attach or emergency close)
    - `app/engine/reconciler.py`: UNKNOWN / interrupted intents, protection sweep, strays
    - `app/engine/broker_positions.py`: A11 rules via SLTP within stops/freeze levels, closes, flatten
    - `app/engine/backends.py`: `PaperBackend` / `DemoBackend`; the engine checks the DEMO gate before every
      decision and send; `python -m app.main --mode demo`; CLI `breaker list|reset`, `demo-report`
  - advisory ranking (Phase 6A, PLAN §A25; `app/advisory/`):
    - `asset_classes.py` + `universe.py`: classes from currency codes, path and calc mode; `symbol_catalog`
      (migration 0009) refreshed daily from `symbols_get(group)`; exotics/OTHER opt-in; `monitored_set`
    - `market_sessions.py`: Sydney/Tokyo/London/New York/EU and US equities in exchange-local time (DST via
      zoneinfo), asset class → sessions with per-symbol overrides, `session_state` (active, ends_at,
      next_open), hour-of-week tick-volume `LiquidityProfile` from H1
    - `suitability.py`: `collect_facts` (broker calls once per symbol) and `assess` (per account, no broker
      calls; risk-sized lot from the real `PositionSizer` via `FactsCalculator`), gates G1–G6 with
      explanation keys; `explanations.py` has the TH/EN texts
    - `scoring.py` + `correlations.py`: S1–S9, Overall/Now, greedy diversified ranking (eligible first,
      deterministic); hypothesis property: more equity never lowers S1 or fails G2
    - `ranking_service.py`: structural refresh (6 h / equity ±5%), round-robin metrics (20 symbols/min,
      hourly), Now score per minute, `suitability_snapshots` (one row per symbol and hour, 90-day
      retention, migration 0010); runs inside the engine loop behind its own error boundary
      (`advisory.ranking.enabled`); `Engine.request_rescan()` is the RESCAN hook for the Phase 7 command queue
    - CLI: `python -m app.cli advisory rank [--fake] [--top N] [--lang th]` (`--fake` uses a throwaway DB)
  - opportunities (Phase 6B, PLAN §A26, §A29–§A31; `app/advisory/`):
    - `preferences.py`: watchlists, alert rules (metric, x, lifetime, sessions, user windows, rate limits,
      language), `TheoryPreferences` (presets, toggles, bounded params), `TradingProfile` (slider anchors,
      defensive rounding, overrides, ceilings, break-even + 2 pp floor), `EntryPlanPreferences`;
      `config.yaml` → `advisory.preferences` is the local fallback (`local_preferences`)
    - `confidence.py` + `stats_math.py`: subset setup strength, hierarchical Beta-binomial buckets (κ 20,
      replay cap 50, 90% interval, insufficient flag), IRLS logistic evidence model used only when
      walk-forward CV beats the buckets, Shapley attribution (exact ≤ 10 players), track records,
      `signal_features`
    - `requirements.py`: compute requirements (symbol / detector / strategy union, lifetime) from the users'
      preferences; `scanner.py`: per new entry bar, ADVISORY decisions, `opportunities` rows (migration
      0011, id = signal idempotency key), time budget per cycle; `lifecycle.py`: market windows, EXPIRED /
      INVALIDATED / FOLLOWED, restart catch-up; `statuses.py` (pure, shared with the cloud)
    - `personalize.py`: pure per-user decision (entitlements, theory subset, metric/x/N, profile limits,
      windows, rate limits) and TH/EN push payloads incl. the silent replacement; imports no broker code
    - the engine runs scanner + lifecycle every cycle behind the advisory error boundary
      (`advisory.scanner.enabled`); trading engine tests switch the scanner off
  - shadow trades, accuracy & calibration (Phase 6C, PLAN §A27, §A29; formulas in `docs/ADVISORY.md`):
    - `shadow.py` (pure): entry at the decision's quote + slippage, PLAN and MANAGED variants, closed-M1
      resolution with tick tie-breaks / SL-first `AMBIGUOUS`, entry-minute ticks or `PARTIAL_BAR`, `GAP`, 72 h
      time stop, commission + swap (rollover days), broker P/L, R, MAE/MFE, `VOID`
    - `shadow_tracker.py` (engine): opens rows for every opportunity (`shadow_trades`, migration 0012, which
      also adds the opportunity quote and `alerted_at`), copies alerted/followed, resolves per M1 cursor
      every `poll_seconds`, restart catch-up from history
    - `replay.py` + `app.cli advisory replay`: the scanner over stored history (backtest context code,
      ADVISORY profile, flat account), M1/M5 resolution, `source=REPLAY`, idempotent and deterministic;
      `--detectors` narrows the ~1 s/bar evidence cost
    - `calibration.py` + `app.cli advisory calibrate`: bucket + evidence model from CLOSED PLAN rows,
      selection needs a 0.5% relative Brier gain, out-of-sample Brier + reliability, versioned
      `calibration_tables` / `evidence_model_versions` (migration 0013, plus
      `opportunities.calibration_version`), nightly rebuild on a worker thread, hourly retry after a failure
    - attribution fix: a detector that did not fire is an observed zero; `ctx:n_families` adds imputed
      players' activity rates, so useless theories get ~0 points
    - `stats.py` (pure, for the cloud too): hit rate + Wilson CI, expectancy, PF, total hypothetical P/L,
      follow-all curve + max DD, breakdowns, in-sample threshold explorer, LIVE/REPLAY sections, theory
      scoreboard; `EdgeBook` feeds ranking S8 (REPLAY capped)
  - trade analytics (Phase 10, PLAN §A16; `app/analytics/`, pure, no I/O):
    - `trade_builder.py` (TAA-1001): one `Trade` record from backtest `ClosedTrade`s, closed PAPER positions
      (+ intents for the initial stop and planned risk) and CLOSED shadow rows (scope SHADOW, `source` and
      `variant` kept); R net of costs, MAE/MFE in R, costs in money (unknown parts None, `cost_r` a lower
      bound), `hypothetical` for backtest/paper/shadow; unusable rows go to `TradeSet.skipped` with a reason
    - `styles.py` (TAA-1002): setup, direction, holding, session, regime, volatility, weekday/hour (UTC),
      symbol, strategy, scope (+ variant/source); unknown facts tagged UNKNOWN
    - `attribution.py` (TAA-1003): ordered rules, 1–3 codes per trade, English one-line texts, evidence values,
      `analytics.attribution.<CODE>` translation keys; rules with unknown facts don't fire
    - test factories in `tests/analytics_data.py`
  - web service foundation (Phase 8, `app/web/`, PLAN §A14; branch `phase8-auth`):
    - TAA-801: `create_app(WebSettings)` (`app/web/app.py`), env-only `WebSettings` in `app/config.py`
      (`WEB_ENV` defaults to production, which requires an https `WEB_PUBLIC_ORIGIN`), `GET /api/v1/health`,
      strict CSP + security headers on every response (`security_headers.py`), 64 KiB body limit, JSON error
      shape `{"error": {"code", "message"}}` (`errors.py`), the built PWA served from `frontend/dist` with SPA
      fallback (`static.py`), `python -m app.web`
    - TAA-802: tables `users`, `sessions`, `login_throttle` (migration 0017); `app/web/auth.py`
      (`AuthService`): argon2id (`app/security/passwords.py`), mandatory TOTP with one-time steps
      (`app/security/web_totp.py`), TOTP secrets encrypted with a key derived from `WEB_SESSION_SECRET`
      (`app/security/crypto.py`, HKDF), keyed-hash session tokens, 30 min idle / 12 h absolute, CSRF token +
      Origin check, lockout per username (5) and address (20) doubling from 1 min to 1 h, 5-minute step-up,
      TOTP re-enrollment (password + step-up), audit chain `web`; routes in `app/web/routers/auth.py`,
      dependencies `CurrentSession` / `CsrfSession` / `StepUpSession` in `app/web/deps.py`; CLI
      `python -m app.cli web create-user | reset-password | reset-totp | list-users`
  - PWA frontend foundation (Phase 9, `frontend/`, PLAN §A15/§A28; commands and conventions in
    `frontend/README.md` and CODING_STANDARDS §9):
    - TAA-901: Vite 8 + React 19 + TypeScript 6.0 (strict) + Tailwind 4 + React Router + TanStack Query + zod +
      vite-plugin-pwa (app shell precache, `/api/` excluded from the navigation fallback, external
      `registerSW.js` for the CSP); ESLint (type-aware) + Prettier + Vitest; dev proxy `/api` →
      `127.0.0.1:8000` (`TAA_API_TARGET` overrides); `apiGet` validates every response with zod; only a
      placeholder home page and a not-found page so far
    - TAA-915: react-i18next (`th` default, `en`), `LanguageSwitcher` (sets `<html lang>`, remembers the choice
      in localStorage), bundled Noto Sans Thai (variable, Thai + Latin), `format.ts` / `useFormat()` (Thai
      Gregorian dates, Asia/Bangkok, locale-aware numbers/money/percent, "—" for missing values, naive
      datetimes rejected), `explain:<key>` catalogs copied from `explanations.py`, the `codes:<kind>.<CODE>`
      key scheme (keys only: untranslated codes render raw), parity tests against the backend enums
    - TAA-902 (branch `phase8-auth`): `/login` (password + TOTP, TH/EN), `RequireAuth` route guard,
      `apiPost` with `X-CSRF-Token`, session end on any 401 `unauthenticated` or when the idle/absolute
      deadline passes (absolute limit measured on the server clock via `server_time`), logout
    - TAA-903 (PLAN §A15 "TAA-903 decisions"): `src/app/shell/` (nav model `nav.ts`, sidebar + phone bottom bar
      with a "More" sheet, mode banner, engine bar with picker/health/live state, offline banner, `StaleBadge`,
      `RequireOwnEngine`, `PlaceholderPage` for pages not built yet), `src/engine/` (`useEngine`,
      `useEngineStatus`, health rule = the watchdog's 60 s on the server clock), `src/live/` (`LiveStream` SSE
      client + `LiveProvider`, `useLiveEvents(topic, …)`), themes (`src/app/theme.ts`, `dark` class). Backend:
      `/status` gains `heartbeat`; the stream route no longer refreshes the session idle timer
      (`StreamSession`), which would otherwise have kept idle tabs signed in forever.
    - TAA-904 (PLAN §A15 "TAA-904 decisions", §A13 TAA-705 note): engine heartbeats carry an `account`
      snapshot (equity, P/L, drawdown, heat, limits); dashboard in `src/pages/dashboard/` with SVG gauges and
      per-topic live refresh; `codes:` kinds `breaker`, `notificationType`, `decision` with texts.
    - TAA-905 (PLAN §A15 "TAA-905 decisions"): `/candles?zones=true` (S/R zones); `src/pages/charts/`
      (`model.ts` pure, `chartAdapter.ts` the only Lightweight Charts import, lazy route chunk), evidence
      overlays from `?decision=`/`?opportunity=`, `codes:family`. Verified in headless Edge under the real CSP
      (the library's `<style>`-injecting logo is off; our attribution link is shown instead).
    - TAA-906 (PLAN §A15 "TAA-906 decisions"): quotes with the engine's spread limit, `GET /quotes`,
      `src/pages/symbols/`, shared `src/components/Gauge.tsx`; API samples contract
      (`tests/web/test_api_samples.py` ↔ `frontend/src/test/apiSamples.test.ts`), which caught TAA-905's
      `/symbols` shape bug (fixed).
    - TAA-907 (PLAN §A15 "TAA-907 decisions"): floating P/L on paper marks, trade lifecycle on the audit
      chain (`TradeAuditSink`), `GET /trades/{ticket}`, `src/pages/trades/` (positions, history with CSV, trade
      drawer). TAA-911 should add close/flatten buttons to the positions page with its step-up dialogs.
    - TAA-908 (PLAN §A15 "TAA-908 decisions"): `/decisions?reason=` (SQLite + PostgreSQL tested), the
      decision log with check-by-check dialog in `src/pages/decisions/`, texts for all reason codes.
    - TAA-909 (PLAN §A15 "TAA-909 decisions"): `GET /strategies?days=` (`app/web/strategies.py`), heartbeats
      carry `disabled_strategies`, `src/pages/strategies/`, and the reusable `StepUpDialog`
      (`src/components/StepUpDialog.tsx`, `src/auth/stepUp.ts`): TAA-911 should use it for its controls.
    - Page tests use `src/test/engine.ts` (`owner()`, `status()`, `heartbeat()`, `renderShell(path)`) and
      `src/test/eventSource.ts` (fake EventSource).
  - local PostgreSQL 16 (Windows service `postgresql-x64-16`, localhost:5432), shared with other projects.
    TAA has its own role `taa` (LOGIN, CREATEDB) and database `taa_test`; the URL is `TAA_POSTGRES_URL` in
    `.env`. `pytest -m postgres` (4 tests: migrations + schema parity, rev. 4 backfill/downgrade, two-engine
    ingest, audit chain over JSONB) creates and drops a throwaway database per test. Other databases on that
    server (e.g. `aicentralize`) belong to other projects: never touch them.
  - a local `.env` (git-ignored) with the FBS **demo** login and random `ENGINE_ID`, `ENGINE_HMAC_SECRET` and
    `CONTROL_TOTP_SECRET`. It uses the master password with `PAPER_ALLOW_MASTER_PASSWORD=true` (the user's
    choice for the demo account). Blank env values count as unset (`env_ignore_empty`).
  - the bot terminal is a dedicated portable copy at `C:\MT5\taa-bot` (option A in `.env`); option B, the
    installed terminal, is commented out.
  - real terminal verified:
    - `doctor` reports 0 failures (warnings: master password, Algo Trading button off), and `pytest -m mt5`
      passes 6/6
    - server time is verified even on weekends through 24/7 crypto symbols (`symbols.clock_fallback_symbols`,
      default BTCUSD/ETHUSD); FBS offset +3h (EEST) confirmed
    - demo account: USD, 1:200, hedging
    - a fresh terminal may need a moment to sync a symbol before `order_calc_profit` works (XAUUSD failed once
      on the first run)
  - the demo account also carries a manual BTCUSD test position (magic 0). Per PLAN, manual positions count
    toward exposure (policy: count or halt), and Phase 6B uses them to detect FOLLOWED opportunities.
- **Git:** `main`, committed per ticket (the user allows commits at ticket boundaries; ask before pushing). A
  remote `origin` exists; `main` is ahead of `origin/main` (18 commits at the end of this session, the handoff included; the user
  pushes). Work happens on
  `main` in `C:\Users\korap\taa` (one session at a time). It is the only worktree and the only local branch:
  `phase8-auth`, `phase9-frontend` and `phase10-analytics` were merged, then deleted with their worktrees
  (2026-10-04). The `origin/dependabot/*` branches are Dependabot PRs on GitHub, untouched. Latest migration: **0032**.

## Next work

Dependency graph of the open Milestone 1 tickets (→ = unblocks):

- **Critical path:** 703 ingest → 803 read APIs → 804 SSE → 903 app shell → pages 904–913 → 914 PWA polish
- 704 long-poll route → 805 control API → 911 risk & controls page
- 707 advisory sync (needs 703, 704) → 809 advisory APIs → 810 opportunity push and pages 916–920
- 703 → 706 candle & history sync
- 808 worker → 705 heartbeat & watchdog, 806 Web Push (→ 810, 912), 807 backtest jobs (→ 910, 1004)
- 8A1 tenancy → 8A2 plans → 8A3 account profiles → 8A4 personalizer (also needs 810), 8A5; 921 needs 8A1–8A3
- 1004 recommendations (needs 807) → 1005 analytics API & pages (also needs 903)
- 922 trading profile page: unblocked
- (rev. 4, PLAN §A32) 708 engine registry → 709 engine-scoped replicas (lifts the one-engine limit); 708 → 811
  engine management API → 923 Engines page (also needs 903, 915); 803 and 805 gain owner-scoping items
- Phase 11 (Railway) after Milestone 1 features; it needs the user's Railway access.

**Order for the single session** (critical path first, otherwise the TICKETS execution order; each step's
dependencies are done by the time it is reached):

1. ~~TAA-703, 704, 707, 708, 709, 706, 803~~ (done in the previous session)
2. ~~TAA-804, 805, 811, 808, 705, 806, 807, 809, 810~~ (done; cloud replay jobs deferred to TAA-1501)
3. ~~TAA-8A1 → 8A2 → 8A3 → 8A4 → 8A5~~ (done, Phase 8A)
4. ~~TAA-903 app shell, 904 dashboard, 905 charts, 906 symbols, 907 positions & history, 908 decisions, 909 strategies~~ (done). **Next:** 910–913, 916–923, then 914 PWA polish (Phase 9). The backend for every page exists; see "Notes for the PWA" below.
5. TAA-1004 (do the preparation in "Notes from Phase 10" first), TAA-1005 (Phase 10)
6. Phase 11 Railway deployment: only with the user's Railway access and go-ahead. Then stop for the
   Milestone 1 review.

Planned details:

- A new replicated table needs a sample row in `tests/sync_data.py` (a test enforces it).
- **TAA-1004 preparation:** see "Notes from Phase 10".

## Parallel sessions (rules learned on 2026-10-04)

Not used now (one session at a time). Kept for the case the user runs sessions in parallel again.

- **One worktree per session.** Never work in the main checkout `C:\Users\korap\taa` while other sessions
  run. It only receives fast-forwards. A session that edited files there blocked two merges.
- **Merging into main:** in your worktree, `git merge main`, resolve, run the full gate (pytest, ruff format
  + check, mypy, bandit; plus the frontend four if `frontend/` changed), commit. Then in the main checkout:
  `git merge --ff-only <branch>`. It refuses instead of touching another session's files. If main moved in
  between, repeat. If the gate is slow and main keeps moving, run the fast checks (ruff, mypy, bandit, the
  tests of the changed area, `test_architecture.py`, `test_storage.py`), fast-forward, then run the full
  suite on that commit right away.
- **Hot files that conflict:**
  - `docs/TICKETS.md` progress table: take main's side, then `scripts/tickets.py sync`. It recomputes from
    the checkboxes, which merge cleanly.
  - `docs/PLAN.md` and `docs/HANDOFF.md`: edit only your own sections.
  - `app/storage/models/__init__.py`, `app/config.py`, `config.yaml`, `app/cli/__main__.py`,
    `app/web/app.py` (router registration): small additive edits only.
- **Migrations are a single chain.** The session that merges second renumbers its revision and
  `down_revision` to follow main's head. Re-run autogenerate against main's head if the models overlap.
- **Test load:** three full suites at once ran out of memory (numpy `ArrayMemoryError`) and probably caused the
  rare pandas access violations (see "Notes from Phase 7"). Stagger full runs; rerun a lone failure by itself
  before investigating.
- A fresh worktree needs its own venv or a junction to the main one (`mklink /J .venv
  C:\Users\korap\taa\.venv`). Remove a junction with `rmdir`, never a recursive delete, which would empty the
  real venv.

## Notes for the next session

- Notes for the PWA (Phase 9; the APIs the pages read, all under `/api/v1`):
  - Session: `/auth/session|login|logout|step-up|profile`; feed: `GET /me/feed` (which engine the user reads;
    `own` false = the owner's market feed, where account details are redacted).
  - Live data: `GET /engines/{id}/stream` (SSE; `ready`/`reset`, topics status, quotes, positions,
    notifications, decisions; `Last-Event-ID` resumes; PLAN §A14 "TAA-804 decisions").
  - Owner pages: status, account, positions, trades, intents, decisions, breakers, kill-switch, symbols,
    candles (with overlays and markers), config, audit/verify (TAA-803); commands (TAA-805); engines (TAA-811);
    backtests (TAA-807).
  - Advisory pages: ranking (personal on the feed), opportunities (with `probability`, `contributions`, plan,
    `my_sizing`), shadow-trades, accuracy (`?mine=true`), threshold-explorer, theory-scoreboard, calibration;
    `/advisory/preferences|watchlists|favourites|detectors` (TAA-809/8A4).
  - Me: notifications, push key/subscribe/unsubscribe/test, preferences (TAA-806); `/me/alerts`,
    `/me/entitlements`, `/me/account-profile`, `/me/export`, `/me/erase`; admin `/admin/users|plans`.
  - The service worker's `push` handler is not written yet: messages carry `title`, `body`, `tag`, `url`,
    `silent`, `renotify`, `badge` (prebuilt opportunity pushes, TAA-810). Notification types and `NoAlert` /
    plan-limit codes need `codes:` keys with TH/EN texts when their pages show them.
- Lessons from this session:
  - Don't edit the working tree while a full test run is going: the migration-parity test reads the
    migration files at run time and failed on a half-written next ticket. Stage the ticket, run, commit.
  - Long multi-line edits through a bash heredoc broke bash's quote parsing once; writing the edit as a small
    Python script in the scratchpad and running it is more robust.
  - A SQL `LIKE 'taa_t_%'` also matches `taa_test` (`_` is a wildcard): never clean up databases by pattern.
    The throwaway-database teardown in `tests/integration/test_postgres.py` now retries instead.
  - `.env` (local, git-ignored) now also has `WORKER_ENV=development` and a generated VAPID pair with
    `VAPID_SUBJECT=mailto:owner@example.com` (the user may set a real contact; it goes to the push services).

- Docstrings longer than 110 characters fail ruff (E501). Wrap them by hand, or keep the summary line short and
  put the details in a paragraph below it.
- `docs/TICKETS.md` uses CRLF line endings. `scripts/tickets.py` handles that; if you edit the file by hand,
  preserve the line endings.
- The catalog test is the slowest part of the suite (~15 s), because candlestick detectors run their location
  prerequisites.

- Decisions made in Phase 3 that the user may want to revisit:
  - Chart-pattern and breakout setups default to the **nearer** stop (pattern invalidation or 1.5 ATR),
    because the textbook stop beyond the pattern extreme gives RR < 1 with a measured-move target. Recorded
    in PLAN §A29; `stop_mode: invalidation` restores the textbook rule.
  - The 8 pattern setups ship disabled; enabling them needs the evidence engine wired into the runtime
    (Phase 6). The SMC setup also needs `max_age_bars` ≥ 30 for `smc.liquidity_sweep` and
    `structure.bos_choch`.
- Decisions made in Phase 4:
  - `SessionWindow` changed from `start_utc`/`end_utc` to `start`/`end`/`timezone` (config.yaml updated).
  - New reason codes beyond PLAN §A8's list: `CURRENCY_EXPOSURE_LIMIT`, `UNKNOWN_POSITION_RISK`,
    `FOREIGN_POSITIONS` (recorded in PLAN §A8).
  - The live gate lives in `app/risk/mode_gates.py`, not `app/security/live_gate.py`, because it reuses
    the broker-layer `verify_identity` (split out of `verify_connection`).
- Decisions made in Phase 5:
  - `backtest.leverage` added to config (simulated margin only).
  - `BaseStrategy.should_close(ctx, side)` hook; the example strategy closes when the H1 bias flips.
  - The golden backtest (`tests/backtest/test_runner_cli.py::GOLDEN`) is a regression anchor on synthetic
    data; update it only for an intended behaviour change and say why in the commit.
- Notes from Phase 12:
  - DEMO has only run on the FakeMT5 trade server. The first real demo session is the user's call: follow
    `docs/RUNBOOK_DEMO.md` (backtest on real history first, Algo Trading on, master password, `doctor`).
  - Limit (scale-in) parts of an entry plan are not sent to the broker yet; only market parts are.
  - `.env` currently has `TRADING_MODE=PAPER`; DEMO needs `TRADING_MODE=DEMO` and `ENABLE_DEMO_TRADING=true`.
- Notes from Phase 6:
  - The evidence scan costs ~1.6 s per symbol per new entry bar (61 detectors, two timeframes). Fine for
    a few symbols every 15 min; the universe scanner (6B) needs a budget or a narrower plan.
  - The PAPER engine has only been run on FakeMT5. Running it against the real terminal is the user's
    call (read-only, investor or master password per `.env`).
- Notes from Phase 6A:
  - The ranking assesses the **broker** account (equity, margin) even in PAPER mode, because it advises the
    user about their real account; the paper book only drives the bot.
  - G6 checks quote freshness only while the symbol's mapped sessions are open, so weekends don't mark
    everything stale.
  - `SymbolSpec.swap_mode` was added (default UNKNOWN for specs stored earlier); S9 understands points,
    deposit currency and disabled swaps, other modes score a neutral 50 with an `unknown_swap` flag.
  - S8 (historical edge) is neutral until Phase 6C supplies shadow outcomes (`edge_source` hook).
  - Real demo terminal (2026-10-04, read-only, user-approved): 541 enabled symbols, 384 eligible. The first
    run took 9.5 min; the greedy S7 pass was O(n³) with `DataFrame.at` and is now incremental (12 s for
    the whole universe). Refreshes are time-budgeted per engine cycle (`max_refresh_seconds`), because a cold
    terminal needs ~1 s per symbol to sync history. Open markets rank first (on Sundays: crypto).
- Notes from Phase 7:
  - The full suite crashed twice (Windows access violation in pandas groupby inside `FakeMT5._bars`, main thread,
    no other Python threads alive; once in `test_engine_restart`). It did not reproduce in 3 targeted reruns
    or the next full run (2050 passed). Possibly load from the parallel sessions; watch for it.
    - Seen twice more in the phase10-analytics session (2026-10-04), same frame
      (`pandas groupby.first` ← `FakeMT5._bars` ← `copy_rates_from_pos`): once in
      `test_engine_paper::test_a_failing_cycle_blocks_entries_but_the_loop_continues` (via
      `RankingService.refresh`), once as a stack dump mid-run. Both full reruns passed. Still only under
      parallel sessions' load; no ticket yet. Next step if it recurs: run `tests/integration` alone in a
      PowerShell loop with `-x` and `PYTHONFAULTHANDLER=1`, and try a pandas/numpy version pin.
  - Calibration shutdown now waits for a running build so no worker thread touches a closed database.
- Notes from Phase 6C:
  - Shadow results have only run on FakeMT5. On a real terminal, M1 history and `copy_ticks_range` need the
    symbol synced; failures are retried on the next poll.
  - Replay on real data needs M1 or M5 in `data/history` (download it first). Use `--detectors` to keep long
    windows affordable.
  - Win probability is read in the cloud from the calibration version stamped on each opportunity (8A4).
- Notes from Phase 6B:
  - Hard ADVISORY failures create no opportunity (their reasons stay in `decision_records`); recorded in
    PLAN §A26. The scanner uses `timeframes` from `config.yaml`; per-user holding styles do not change the
    scan timeframes yet.
  - Market windows use the longest lifetime any user wants; the personalizer applies the user's own window.
  - ACTIVE is set through `OpportunityLifecycle.mark_active` when someone is alerted (wired in 8A4).
  - Conflict policy: `TheoryPreferences.conflict_policy` unless the trading profile overrides it explicitly;
    minimum supporting families = max(theories, profile). BLOCK blocks on a conflict of quality ≥ 0.6.
  - Non-owner users get no lot in pushes until account profiles exist (8A).
- Notes from Phase 9 (frontend foundation):
  - The frontend parity tests (`frontend/src/i18n/codes.test.ts`, `explain.test.ts`) read `app/risk/reasons.py`,
    `app/strategy/signal_models.py`, `app/advisory/{suitability,statuses,lifecycle,shadow,explanations}.py` and
    `app/core/enums.py`. Changing those enums or explanation keys/placeholders needs a matching change in
    `frontend/src/i18n/` (`npm run test` in `frontend/`). The Python suite does not run them.
  - TypeScript is pinned to 6.0.x: typescript-eslint 8 does not support TypeScript 7 yet.
  - The `codes` namespace has no texts yet (the ticket asked for keys only); add TH/EN texts with the pages
    that show the codes (TAA-908 decisions, TAA-917 opportunities, TAA-919 accuracy).
  - The app icon is a placeholder SVG; maskable/Apple icons, API caching rules and the install prompt are
    TAA-914.
  - Built pages load lazily (`BUILT` in `routes.tsx`); the main chunk is ~340 kB after TAA-906.
  - Memory (16 GB machine): running vitest while the full pytest suite runs crashed Node workers (exit 134)
    and once made argon2 fail with "Memory allocation error" in user-creating fixtures. Run the two suites one
    after the other; rerun a lone `HashingError` before investigating.
  - Write page tests from `src/test/fixtures/api-samples.json` (real responses); add each new route a page
    reads to `tests/web/test_api_samples.py` and `apiSamples.test.ts`. Hand-written fakes hid a shape bug once.
  - A real-browser check of a component without the backend: build a small harness with Vite into the
    scratchpad (alias `@` → `frontend/src`), serve it with `app.web.security_headers.CONTENT_SECURITY_POLICY`
    and screenshot it with headless Edge (`msedge --headless=new --screenshot=… --enable-logging=stderr`).
  - A new page: add it to `src/app/shell/nav.ts` if missing, then replace its `PlaceholderPage` route in
    `src/app/routes.tsx`. Engine queries go under `engineKey(id)` so the stream's resync refetches them.
  - Windows is case-insensitive: `gauge.ts` next to `Gauge.tsx` broke the TypeScript build. Give logic modules
    a different name than their component.
  - The UI has only been checked through tests (jsdom), not yet in a real browser against `python -m app.web`.
- Notes from Phase 8 (web auth, branch `phase8-auth`):
  - Two TOTP modules on purpose: `app/security/web_totp.py` (web users: stateless, last step stored per user)
    and `app/security/totp.py` (engine-only `CONTROL_TOTP_SECRET`, single-use in memory, TAA-704).
  - Running locally: add `WEB_ENV=development` and a `WEB_SESSION_SECRET` (at least 32 characters) to `.env`,
    create the owner with `python -m app.cli web create-user <name>` (scan the QR, confirm a code), then
    `python -m app.web` (http://127.0.0.1:8000 serves `frontend/dist`) or `npm run dev` in `frontend/`. The
    full stack was checked end to end with curl (login, cookie, CSRF-protected logout).
  - Development cookies are `taa_session` without `Secure` (loopback http); production uses
    `__Host-taa_session` with `Secure`. Origins accepted in development: Vite 5173 and app.web 8000.
  - Engine bug, fixed on main (2026-10-04): `BreakerMonitor.observe_storage` formatted `free_gb=None` (no
    `data/` directory) and raised every cycle; now the write check alone decides and the reason says
    "unknown". Fresh worktrees no longer need `data/` for the engine tests.
  - Timing-sensitive integration tests (`test_engine_paper`, `test_scanner` time budgets) failed once under
    heavy machine load and passed on rerun.
- Notes from Phase 10 (TAA-1001..1003):
  - Fills store no entry context. Callers pass an `EntryContext` per signal id, built from the decision
    record with `context_from_decision`. The backtest keeps no decision records per trade, so TAA-1004 on
    backtests needs `BacktestEngine` to keep the selected signal's `MarketContext` (or its decision record)
    by signal id: a small change in `app/backtest/engine.py`.
  - Exit-time facts (HTF trend, ATR) and the news overlap are optional context. Until a caller supplies them,
    LOSS_REGIME_SHIFT, LOSS_VOLATILITY_SPIKE and LOSS_NEWS_PROXIMITY never fire.
  - The attribution texts are English only; the PWA needs `analytics.attribution.<CODE>` TH/EN texts in
    `frontend/src/i18n/` with TAA-1005.
- Risk-layer test helpers: `tests/risk_data.py` (`TickCalculator`, `funds`, `XAUUSD_SPEC`).
- Strategy-layer test helpers: `tests/strategy_data.py` (synthetic M15/H1 frames, `sawtooth_m15`,
  `EURUSD_SPEC`, `StubCandles`) and the builders in `tests/unit/test_strategy_models.py`.

## Open items needing the user

- Pushing to GitHub: the user asked for a push (2026-10-04), but `git push` from Claude Code fails because
  the Git credential manager needs an interactive GitHub login (`gh` is not installed). The user runs
  `git push origin main` in their own terminal.
- The flaky pandas access violation has no ticket yet: open one if it recurs (see "Notes from Phase 7").
- Before Phase 11: Railway account access for deployment (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (Thai SEC advisory licensing, PDPA, payments): the questions
  and the enable checklist are in `docs/COMPLIANCE.md`; the gate is `SUBSCRIPTIONS_ENABLED` +
  `SUBSCRIPTIONS_LEGAL_REVIEW`.
- TAA-1501 (cloud replay jobs, Phase 15 deferred backlog): revisit when users without engines are served.
- `VAPID_SUBJECT` in `.env` is a placeholder (`mailto:owner@example.com`); set a real contact if wanted.
