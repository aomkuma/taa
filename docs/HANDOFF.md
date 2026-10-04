# Session handoff

Last updated: 2026-10-04, after Phase 6C (TAA-6C1..6C5; one 6C5 item waits for the phase10-analytics merge) and
the Phase 9 frontend foundation (TAA-901 scaffold, TAA-915 i18n, built in a parallel worktree and merged). This file holds **state
only**. Rules and conventions live in `CLAUDE.md` (loaded automatically by Claude Code) and
`docs/CODING_STANDARDS.md`.

---

## Prompt for the next session

Paste this into a new Claude Code session opened in `C:\Users\korap\taa`:

```text
Continue the TAA project. Read docs/HANDOFF.md (state), docs/TICKETS.md (progress + execution order) and the
relevant sections of docs/PLAN.md (§A27 shadow trades & calibration, §A26 opportunities, §A29 evidence model).
Follow CLAUDE.md and docs/CODING_STANDARDS.md.
Phases 0, 1, 2, 2A, 3, 4, 5, 6, 6A, 6B and 12 (DEMO execution, pulled forward on the user's request) are
DONE. Phase 6C is done except the SHADOW-scope item of TAA-6C5, which is built on branch phase10-analytics.
Phase 9 has its foundation (TAA-901, TAA-915 done; frontend/). Check open branches/worktrees (git worktree list)
before starting a ticket another session may own. Next: 7 -> 8 -> 8A -> the rest of 9 -> 10 -> 11.
LIVE stays disabled until Phase 14 and an explicit go-ahead.
Commit at each ticket boundary (allowed); ask before pushing. Stop for review at the end of Milestone 1, or at
any phase boundary if I ask.
```

---

## Current state

- **Done:** Phase 0 (TAA-001..009), Phase 1 (TAA-101..110), Phase 2 (TAA-201..206), Phase 2A
  (TAA-2A1..2A10), Phase 3 (TAA-301..307), Phase 4 (TAA-401..407), Phase 5 (TAA-501..506) and Phase 6
  (TAA-601..606), Phase 12 (TAA-1201..1206, pulled forward: DEMO broker orders) and Phase 6A
  (TAA-6A1..6A5, symbol universe & suitability ranking) and Phase 6B (TAA-6B1..6B5, watchlists,
  opportunities & alert windows).
- **In progress:** Phase 6C (all done except TAA-6C5 item 2, "shadow trades in the analytics trade builder",
  which lives on branch `phase10-analytics` as part of TAA-1001: tick it when that branch is merged), Phase 9
  (TAA-901 and TAA-915 done; the remaining pages need the Phase 8 API), Phase 10 on `phase10-analytics`, and
  Phase 8 in a separate session (worktree `taa-auth`, branch `phase8-auth`). The main session owns Phase 7
  only; tickets that need Phase 8 pieces (703 needs 801, 705 needs 808) wait for that branch.
- **Checks:** 1983 tests pass, 8 skipped (real-terminal, Postgres, one contract case defined from bar 0); the
  suite takes ~5.5 min, with backtest and engine tests the slow part. ruff,
  mypy and bandit are clean. Architecture rules are enforced by `tests/unit/test_architecture.py`.
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
  - SQLite/Postgres storage with Alembic (migrations 0001–0013), hash-chained audit log
  - kill switch; CLI (`config`, `db`, `audit`, `kill`, `doctor`, `backtest`, `breaker`, `demo-report`,
    `advisory rank|replay|calibrate`); CI config
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
  remote `origin` exists; `main` is ahead of `origin/main` (push only when the user asks). Other worktrees:
  `phase10-analytics` (TAA-1001..1003, `C:\Users\korap\taa-phase10`) and `phase8-auth` (Phase 8,
  `C:\Users\korap\taa-auth`). Branch `phase9-frontend` (TAA-901, TAA-915, docs) is merged into `main`; its worktree
  `C:\Users\korap\taa-phase9` can be removed with `git worktree remove ..\taa-phase9`.
- **Next step:** Phase 7 (cloud sync) in this session: TAA-701, 702 and 704 first; 703/705/706/707 after the
  Phase 8 branch lands (801, 808). Migration numbers can collide with the Phase 8 branch: renumber the later
  one's `down_revision` at merge time.

## Notes for the next session

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
    TAA-914. FastAPI does not serve `frontend/dist` yet (Phase 8).
- Risk-layer test helpers: `tests/risk_data.py` (`TickCalculator`, `funds`, `XAUUSD_SPEC`).
- Strategy-layer test helpers: `tests/strategy_data.py` (synthetic M15/H1 frames, `sawtooth_m15`,
  `EURUSD_SPEC`, `StubCandles`) and the builders in `tests/unit/test_strategy_models.py`.

## Open items needing the user

- Whether and when to push to GitHub (no remote configured).
- Before Phase 11: Railway account access for deployment (only with explicit go-ahead).
- Before ever enabling subscriptions: legal review (Thai SEC advisory licensing, PDPA). See PLAN §A30.
