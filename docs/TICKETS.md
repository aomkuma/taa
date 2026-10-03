# TAA — Tickets & Checklists

Design reference: [PLAN.md](PLAN.md). Section references such as A9 or A29 point to PLAN.md.

## How to use this file

- Status values: `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED`.
- Tick a checkbox (`- [x]`) as soon as an item is complete; `python scripts/tickets.py sync` recomputes statuses
  and the progress table.
- Definition of Done: checklist complete, tests green, docs updated.
- Milestone 1 never sends broker orders. Work stops for review after Milestone 1.
- Revision 2 (2026-10-03) added Phases 2A, 6A–6C and 8A, TAA-110, and amended items marked "(rev. 2)".
- Revision 3 (2026-10-03) added TAA-2A10 (do it before TAA-2A7) and TAA-922, and amended items marked "(rev. 3)":
  Fibonacci extension levels with candle location (PLAN §A29), trading profile and entry plans (PLAN §A31).

**Execution order (Milestone 1):** 0 → 1 → 2 → 2A → 3 → 4 → 5 → 6 → 6A → 6B → 6C → 7 → 8 → 8A → 9 → 10 → 11

## Progress

| Milestone | Phase | Tickets | Done | Status |
|---|---|---|---|---|
| M1 | Phase 0 — Foundation & safety scaffolding | 9 | 9 | DONE |
| M1 | Phase 1 — MT5 read-only gateway & market data | 10 | 10 | DONE |
| M1 | Phase 2 — Indicators & features | 6 | 6 | DONE |
| M1 | Phase 2A — Technical evidence engine (rev. 2 follow-ups 5–6) | 10 | 10 | DONE |
| M1 | Phase 3 — Strategy engine | 7 | 6 | IN PROGRESS |
| M1 | Phase 4 — Risk, decision pipeline, breakers | 7 | 0 | TODO |
| M1 | Phase 5 — Backtesting | 6 | 0 | TODO |
| M1 | Phase 6 — PAPER runtime | 6 | 0 | TODO |
| M1 | Phase 6A — Symbol universe & suitability ranking (rev. 2, requirement 1) | 5 | 0 | TODO |
| M1 | Phase 6B — Watchlists, opportunities & alert windows (rev. 2, requirement 2) | 5 | 0 | TODO |
| M1 | Phase 6C — Shadow trades, accuracy & calibration (rev. 2, requirement 3) | 5 | 0 | TODO |
| M1 | Phase 7 — Cloud sync | 7 | 0 | TODO |
| M1 | Phase 8 — Web backend & worker | 10 | 0 | TODO |
| M1 | Phase 8A — Personalization, entitlements & multi-tenant readiness (rev. 2 follow-up 7) | 5 | 0 | TODO |
| M1 | Phase 9 — PWA frontend | 22 | 0 | TODO |
| M1 | Phase 10 — Trade analytics | 5 | 0 | TODO |
| M1 | Phase 11 — Railway deployment | 4 | 0 | TODO |
| M2 | Phase 12 — DEMO execution | 6 | 0 | TODO |
| M2 | Phase 13 — AI assessment (optional layer) | 5 | 0 | TODO |
| M2 | Phase 14 — LIVE readiness | 4 | 0 | TODO |

## Milestone 1 — everything that never sends a broker order

### Phase 0 — Foundation & safety scaffolding

#### TAA-001 — Plan docs in repo

- **Status:** DONE
- **Depends on:** —

- [x] `docs/PLAN.md` (Part A)
- [x] `docs/TICKETS.md` (Part B, progress table, status legend)
- [x] link both from README

#### TAA-002 — Repo bootstrap

- **Status:** DONE
- **Depends on:** 001

- [x] git init
- [x] `.gitignore` (env, data/, logs/, .venv, node_modules, *.db, dist)
- [x] `pyproject.toml` (ruff/mypy/pytest)
- [x] pinned `requirements/{base,engine,cloud,dev}.txt` + aggregate `requirements.txt` (`MetaTrader5; sys_platform=="win32"`)
- [x] package skeleton (A2.3)
- [x] README skeleton

#### TAA-003 — Configuration system

- **Status:** DONE
- **Depends on:** 002

- [x] pydantic-settings for env + `config.yaml` (precedence, unknown keys rejected)
- [x] validators, hard ceilings, percent units
- [x] `TRADING_MODE` required
- [x] `.env.example` (placeholders only) + default `config.yaml`
- [x] masked effective-config summary
- [x] tests

#### TAA-004 — Secrets & redaction

- **Status:** DONE
- **Depends on:** 003

- [x] `SecretStr` everywhere
- [x] `keyring:` indirection
- [x] RedactingFilter (exact secrets, regex, masked login)
- [x] tests proving secrets never reach logs, reprs or exceptions

#### TAA-005 — Logging

- **Status:** DONE
- **Depends on:** 004

- [x] JSON rotating file logs + console formatter
- [x] correlation ids (contextvars)
- [x] per-module levels
- [x] tests

#### TAA-006 — Core types & clock

- **Status:** DONE
- **Depends on:** 002

- [x] enums and value objects
- [x] Decimal helpers (`floor_to_step`, `normalize_to_tick`)
- [x] Clock (System, Frozen)
- [x] error hierarchy
- [x] UUIDv7 ids
- [x] tests

#### TAA-007 — Storage & audit

- **Status:** DONE
- **Depends on:** 006

- [x] SQLAlchemy 2 + Alembic (SQLite WAL with `synchronous=FULL`; Postgres-portable)
- [x] base repositories
- [x] hash-chained `audit_events` + `app.cli audit verify`
- [x] tests

#### TAA-008 — Kill switch & CLI

- **Status:** DONE
- **Depends on:** 007

- [x] `app.cli` framework
- [x] kill switch (file + DB state)
- [x] `kill --reason`, and `kill --release --reason` (local only)
- [x] audit
- [x] tests

#### TAA-009 — CI & hooks

- **Status:** DONE
- **Depends on:** 002

- [x] GitHub Actions (ruff, mypy, pytest, pip-audit, bandit, gitleaks, frontend lint/test/build, Postgres migration test)
- [x] pre-commit (ruff, gitleaks)
- [x] Dependabot

### Phase 1 — MT5 read-only gateway & market data

#### TAA-101 — Gateway protocols + FakeMT5

- **Status:** DONE
- **Depends on:** 006

- [x] market-data and account protocols (orders live in a separate ExecutionGateway, M2)
- [x] FakeMT5 emulating the MetaTrader5 API surface we use, including None results, errors and disconnects
- [x] contract tests run against both

#### TAA-102 — MT5 connection manager

- **Status:** DONE
- **Depends on:** 101, 004

- [x] explicit `initialize(path, login, password, server, timeout, portable)`
- [x] post-connect verification per mode (login, server, trade_mode, trade_allowed, terminal flags, hedging margin mode)
- [x] lock-serialized calls
- [x] reconnect with backoff
- [x] `ReadOnlyMT5Gateway`
- [x] PAPER investor-password enforcement

#### TAA-103 — Account & terminal services

- **Status:** DONE
- **Depends on:** 102

- [x] snapshots
- [x] stop-out and margin-call levels
- [x] account-change baseline
- [x] tests

#### TAA-104 — Symbol service

- **Status:** DONE
- **Depends on:** 102

- [x] discovery + `symbol_select`
- [x] SymbolSpec validation (R13 fields, Bid chart mode)
- [x] filling resolver (R6)
- [x] trade-mode direction rules
- [x] clear "unavailable" errors

#### TAA-105 — ServerClock

- **Status:** DONE
- **Depends on:** 006, 102

- [x] zoneinfo + tzdata offsets
- [x] live-tick verification (ticks advancing)
- [x] drift detection
- [x] server↔UTC conversion with DST folds
- [x] tests around EU DST weekends

#### TAA-106 — Candle service

- **Status:** DONE
- **Depends on:** 105

- [x] closed-bar selection with grace
- [x] UTC + server timestamps
- [x] persisted dedup watermark
- [x] quality checks (OHLC, session-aware gaps, stale, maxbars)
- [x] per-TF enable and warm-up sizing
- [x] FakeMT5 tests

#### TAA-107 — Quote service

- **Status:** DONE
- **Depends on:** 104

- [x] fresh tick
- [x] spread in points
- [x] tick age
- [x] rolling median spread
- [x] invalid-price detection

#### TAA-108 — History download & store

- **Status:** DONE
- **Depends on:** 106

- [x] `scripts/download_history.py` (chunked `copy_rates_range` → Parquet + spec snapshot)
- [x] HistoryStore (Parquet, SQL)
- [x] tests

#### TAA-109 — `doctor` command

- **Status:** DONE
- **Depends on:** 102–107

- [x] terminal path and build
- [x] algo-trading and API flags
- [x] account verification
- [x] server offset
- [x] symbols and specs
- [x] maxbars
- [x] `order_calc_profit` sign check
- [x] readable report

#### TAA-110 — (rev. 2) Leverage tiers & symbol catalog access

- **Status:** DONE
- **Depends on:** 103, 104

- [x] remove leverage from the critical account identity (FBS equity tiers, R24); a leverage change becomes a WARNING event plus margin re-check, never ACCOUNT_CHANGE or a refused reconnect
- [x] `symbols(group)` gateway method using `symbols_get` (R22)
- [x] FakeMT5 multi-asset symbols (AUDUSD, EURGBP, XAGUSD, US30, USOIL, BTCUSD, a stock) with realistic paths/calc modes + `copy_ticks_range`
- [x] tests

### Phase 2 — Indicators & features

#### TAA-201 — Trend indicators

- **Status:** DONE
- **Depends on:** 006

- [x] SMA, EMA, MACD, ADX/±DI
- [x] formulas documented
- [x] reference tests

#### TAA-202 — Momentum indicators

- **Status:** DONE
- **Depends on:** 201

- [x] RSI, Stochastic, CCI
- [x] tests

#### TAA-203 — Volatility indicators

- **Status:** DONE
- **Depends on:** 201

- [x] ATR, Bollinger, historical volatility, ATR percentile
- [x] tests

#### TAA-204 — Volume features

- **Status:** DONE
- **Depends on:** 201

- [x] tick-volume ratio features
- [x] tests

#### TAA-205 — Price action

- **Status:** DONE
- **Depends on:** 203

- [x] candle anatomy
- [x] confirmed swings (k-bar lag)
- [x] HH/HL/LH/LL
- [x] S/R zones
- [x] breakout and false breakout
- [x] tests

#### TAA-206 — Indicator verification

- **Status:** DONE
- **Depends on:** 201–205

- [x] TA-Lib cross-check (optional, skipped if absent)
- [x] look-ahead mutation tests
- [x] warm-up NaN tests
- [x] `docs/INDICATORS.md`

### Phase 2A — Technical evidence engine (rev. 2 follow-ups 5–6)

#### TAA-2A1 — Evidence framework

- **Status:** DONE
- **Depends on:** 205

- [x] `Evidence` model (family, direction, quality, key levels, invalidation, targets, tier, i18n key)
- [x] detector registry with config enable/params
- [x] shared multi-degree zigzag/pivot engine (ATR-scaled, confirmation lag)
- [x] immutable snapshots
- [x] look-ahead harness run against every detector
- [x] `docs/PATTERNS.md` skeleton

#### TAA-2A2 — Fibonacci & levels

- **Status:** DONE
- **Depends on:** 2A1

- [x] retracements of the last impulse
- [x] golden-zone pullback + rejection
- [x] extensions (targets)
- [x] fib cluster confluence
- [x] round numbers
- [x] classic/Fibonacci/Camarilla pivots
- [x] previous day/week high/low
- [x] golden + near-miss tests

#### TAA-2A3 — Chart patterns

- **Status:** DONE
- **Depends on:** 2A1

- [x] extrema-rule detectors (R29) with tolerances: M/W double top/bottom
- [x] triple top/bottom
- [x] H&S (+inverse)
- [x] triangles
- [x] wedges
- [x] rectangles
- [x] flags/pennants
- [x] cup & handle
- [x] breakout confirmation
- [x] measured moves
- [x] quality (symmetry, fit error, tick-volume confirmation)
- [x] golden + near-miss tests

#### TAA-2A4 — Candlestick patterns

- **Status:** DONE
- **Depends on:** 2A1

- [x] engulfing
- [x] hammer/pin bar
- [x] shooting star
- [x] doji family
- [x] inside/outside bar
- [x] morning/evening star
- [x] three soldiers/crows
- [x] harami
- [x] tweezer
- [x] marubozu
- [x] location weighting (S/R/fib)
- [x] TA-Lib cross-check in tests

#### TAA-2A5 — Momentum, volatility, volume, sessions

- **Status:** DONE
- **Depends on:** 2A1

- [x] RSI/MACD/Stochastic regular + hidden divergences
- [x] overbought/oversold
- [x] crosses
- [x] CCI extremes
- [x] MA alignment
- [x] Bollinger squeeze/breakout
- [x] Keltner
- [x] Donchian
- [x] ATR expansion
- [x] tick-volume spike/climax
- [x] session VWAP
- [x] Asian-range and London/NY breakouts
- [x] tests

#### TAA-2A6 — Ichimoku, structure & smart money

- **Status:** DONE
- **Depends on:** 2A1

- [x] Ichimoku (cloud, TK cross, Kumo breakout, Chikou)
- [x] Dow structure, BOS/CHoCH
- [x] trendlines/channels
- [x] liquidity sweep
- [x] fair value gap
- [x] order block
- [x] supply/demand zone
- [x] Wyckoff spring/upthrust
- [x] tests

#### TAA-2A7 — Harmonic patterns

- **Status:** DONE
- **Depends on:** 2A1, 2A2

- [x] table-driven XABCD (Gartley, Bat, Butterfly, Crab, Cypher, Shark, AB=CD) per R30
- [x] tolerance config
- [x] PRZ computation
- [x] completion detection
- [x] quality = ratio error
- [x] golden tests per pattern

#### TAA-2A8 — Elliott Wave (heuristic tier)

- **Status:** DONE
- **Depends on:** 2A1, 2A2

- [x] impulse/correction candidates from multi-degree zigzag
- [x] 3 hard rules (R31)
- [x] Fibonacci guideline scoring
- [x] primary + alternate counts with confidence
- [x] states (possible wave 3 / wave 5 / C completion)
- [x] snapshot immutability across recounts
- [x] "heuristic" labelling
- [x] golden 5-wave tests

#### TAA-2A9 — (rev. 2) Selective computation

- **Status:** DONE
- **Depends on:** 2A1–2A8

- [x] compute only the required detector set (union from config / `advisory-config`)
- [x] dependency graph auto-enables prerequisites (zigzag, Fibonacci, ...)
- [x] per-detector timing and call counters
- [x] test: disabled detectors are never executed

#### TAA-2A10 — (rev. 3) Fibonacci extension levels & candle location

- **Status:** DONE
- **Depends on:** 2A2, 2A4

- [x] `fib.extension_level`: 127.2/161.8/261.8/423.6 % as support/resistance, two-point (A + r·AB) and trend-based (C + r·AB), in force until the next same-direction extreme is confirmed
- [x] candle location sources: + `fib.extension_level`, `fib.cluster`, `structure.trendline` (bounce variants only)
- [x] `at_levels` detail naming the levels a candle pattern sat on
- [x] golden + near-miss tests (incl. shooting star at the 161.8 % extension)
- [x] `docs/PATTERNS.md`

### Phase 3 — Strategy engine

#### TAA-301 — Signal & context models

- **Status:** DONE
- **Depends on:** 006

- [x] Signal (spec §9 + ids, expiry, score)
- [x] MarketContext
- [x] StrategyContext
- [x] serialization tests
- [x] (rev. 2) `conditions` checklist (name, passed, weight, detail) + `setup_strength` 0–100 on every signal
- [x] (rev. 2) `evidence` list (supports/conflicts) on every signal

#### TAA-302 — Context builder & regime detector

- **Status:** DONE
- **Depends on:** 106, 201–205

- [x] per-TF retrieval
- [x] close-time alignment
- [x] per-TF analysis logs
- [x] regime and volatility states
- [x] look-ahead tests

#### TAA-303 — Strategy framework

- **Status:** DONE
- **Depends on:** 301

- [x] BaseStrategy
- [x] registry from config (enable/disable, params)
- [x] isolation (no broker or credential access)

#### TAA-304 — Signal arbitration

- **Status:** DONE
- **Depends on:** 303

- [x] conflict resolver
- [x] ranking
- [x] cooldown
- [x] one signal per strategy/symbol/bar
- [x] tests

#### TAA-305 — Example strategy

- **Status:** DONE
- **Depends on:** 302–304

- [x] `example_trend_pullback` (A7)
- [x] reason codes and explanations
- [x] synthetic-scenario tests
- [x] "demo only" docs

#### TAA-306 — (rev. 2) Pattern-based strategies

- **Status:** TODO
- **Depends on:** 2A2–2A8, 303

- [ ] setup generators per §A29 (M/W & H&S neckline breaks
- [ ] triangle/wedge/rectangle/flag breakouts
- [ ] Fibonacci pullback continuation
- [ ] harmonic PRZ reversal
- [ ] Elliott wave-3/5 entries
- [ ] SMC sweep+CHoCH+FVG
- [ ] Donchian/session breakouts
- [ ] candlestick reversal at confluence)
- [ ] explicit entry/SL/TP rules + min RR
- [ ] per-strategy enable
- [ ] demo/unproven labels
- [ ] synthetic-scenario tests

#### TAA-307 — (rev. 2) Confluence enrichment

- **Status:** DONE
- **Depends on:** 2A1, 301

- [x] attach all active evidence (all enabled TFs incl. HTF) to every signal
- [x] supports/conflicts classification
- [x] family-capped noisy-OR confluence score → setup strength
- [x] conflict penalty
- [x] double-counting control tests

### Phase 4 — Risk, decision pipeline, breakers

#### TAA-401 — Position sizer

- **Status:** TODO
- **Depends on:** 104

- [ ] A9 steps
- [ ] Decimal math
- [ ] property tests (never above budget, step-aligned, never below min, inconsistent specs rejected)
- [ ] (rev. 3) entry-plan sizing (PLAN §A31): `SAME_PRICE` / `SCALE_IN`, weights, `lot_unit` (taps), budget with every part filled, drop-deepest-part rule
- [ ] (rev. 3) property tests for entry plans (never above budget with all parts filled, unit-aligned, never rounded up)

#### TAA-402 — Exposure manager

- **Status:** TODO
- **Depends on:** 401

- [ ] open risk
- [ ] per-symbol limits
- [ ] correlation groups
- [ ] currency direction
- [ ] margin utilization
- [ ] effective leverage
- [ ] (rev. 3) portfolio heat incl. manual positions; unknown-risk flag for positions without a stop
- [ ] tests

#### TAA-403 — Loss tracker

- **Status:** TODO
- **Depends on:** 007

- [ ] broker-day and week baselines
- [ ] HWM
- [ ] cash-flow adjustments
- [ ] consecutive losses
- [ ] persistence across restarts
- [ ] tests

#### TAA-404 — Circuit breakers

- **Status:** TODO
- **Depends on:** 403

- [ ] framework (scope, latching, half-open, cooldowns)
- [ ] A10 breakers (M1 subset active)
- [ ] persistence
- [ ] events and notifications
- [ ] tests

#### TAA-405 — Decision engine

- **Status:** TODO
- **Depends on:** 401–404, 305

- [ ] A8 checks and reason codes
- [ ] DecisionRecord persistence
- [ ] a test per reason code
- [ ] (rev. 2) ADVISORY profile: hard failures vs account-rule warnings; universe check replaces the allowlist check

#### TAA-406 — Mode gates

- **Status:** TODO
- **Depends on:** 003, 102

- [ ] live and demo gate evaluation + full truth-table tests (not wired to orders in M1)
- [ ] (rev. 3) M2 limits = min(trading profile, local `RiskConfig`); a cloud profile never raises a local limit (test)

#### TAA-407 — Sessions & news

- **Status:** TODO
- **Depends on:** 006

- [ ] per-symbol session windows
- [ ] NewsCalendar interface + manual blackout windows
- [ ] tests
- [ ] (rev. 2) windows defined in exchange-local timezones (shared with TAA-6A2)

### Phase 5 — Backtesting

#### TAA-501 — SimulatedBroker

- **Status:** TODO
- **Depends on:** 401

- [ ] fill model (next open, bid/ask via spread)
- [ ] seeded slippage
- [ ] commission and swap
- [ ] pessimistic intrabar SL/TP
- [ ] gap fills
- [ ] tests

#### TAA-502 — Backtest engine

- **Status:** TODO
- **Depends on:** 405, 501

- [ ] event loop
- [ ] shared strategy, decision, risk and position-manager code
- [ ] multi-symbol
- [ ] progress events

#### TAA-503 — Currency conversion

- **Status:** TODO
- **Depends on:** 108

- [ ] conversion series for P/L outside the account currency
- [ ] tests

#### TAA-504 — Metrics & reports

- **Status:** TODO
- **Depends on:** 502

- [ ] A17 metrics
- [ ] JSON summary
- [ ] trades CSV
- [ ] equity and DD series

#### TAA-505 — Robustness tools

- **Status:** TODO
- **Depends on:** 504

- [ ] walk-forward
- [ ] sensitivity grid
- [ ] Monte Carlo
- [ ] overfitting warnings

#### TAA-506 — CLI & reproducibility

- **Status:** TODO
- **Depends on:** 504

- [ ] `app.cli backtest`
- [ ] seed, config and data hashes
- [ ] determinism and golden tests

### Phase 6 — PAPER runtime

#### TAA-601 — Orchestrator

- **Status:** TODO
- **Depends on:** 405, 106

- [ ] main loop + scheduler (monitor 1–2 s, health 5 s, candle checks, decisions)
- [ ] mode wiring (PAPER only in M1)
- [ ] graceful shutdown

#### TAA-602 — Paper execution

- **Status:** TODO
- **Depends on:** 501, 601

- [ ] SimulatedBroker on live ticks
- [ ] paper intents and positions persisted
- [ ] idempotency keys

#### TAA-603 — Position manager

- **Status:** TODO
- **Depends on:** 602

- [ ] break-even
- [ ] ATR trailing
- [ ] time stop
- [ ] close signals
- [ ] SL invariants
- [ ] MAE/MFE tracking
- [ ] tests

#### TAA-604 — Restart safety

- **Status:** TODO
- **Depends on:** 601

- [ ] startup reconciliation
- [ ] watermark and breaker restore
- [ ] test: no duplicate signals after a restart

#### TAA-605 — Engine health

- **Status:** TODO
- **Depends on:** 601

- [ ] localhost `/health`
- [ ] heartbeat file
- [ ] `scripts/watchdog.ps1`
- [ ] Task Scheduler setup script

#### TAA-606 — Notification events

- **Status:** TODO
- **Depends on:** 404

- [ ] event model + severities for every alert type
- [ ] local log sink

### Phase 6A — Symbol universe & suitability ranking (rev. 2, requirement 1)

#### TAA-6A1 — Asset classes & universe

- **Status:** TODO
- **Depends on:** 110

- [ ] classification by `trade_calc_mode` + `path` + currency codes (FOREX_MAJOR/MINOR/EXOTIC, METAL, INDEX, ENERGY, CRYPTO, STOCK, OTHER)
- [ ] include/exclude patterns and per-class switches (all on, exotics opt-in)
- [ ] `symbol_catalog` table with daily refresh
- [ ] monitored set = favourites ∪ lists ∪ auto top-N ∪ allowlist, capped at 60
- [ ] tests

#### TAA-6A2 — Market sessions & liquidity

- **Status:** TODO
- **Depends on:** 407, 6A1

- [ ] sessions in exchange-local timezones (Sydney, Tokyo, London, New York, US equities, crypto 24/7)
- [ ] asset-class → session mapping + per-symbol overrides
- [ ] hour-of-week tick-volume liquidity profile from H1 history
- [ ] `session_state(symbol, now)` with current session, ends_at and next_open
- [ ] tests across mismatched US/EU DST weeks

#### TAA-6A3 — Suitability metrics & gates

- **Status:** TODO
- **Depends on:** 401, 203, 6A1

- [ ] typical SL from ATR
- [ ] min-lot risk + required equity
- [ ] risk-sized lot via PositionSizer
- [ ] margin via `calc_margin` with a hike buffer
- [ ] effective leverage (1%-move method)
- [ ] cost ratio
- [ ] stops-level feasibility
- [ ] gates G1–G6 with explanation keys
- [ ] tests incl. small-account XAUUSD exclusion

#### TAA-6A4 — Scores & ranking

- **Status:** TODO
- **Depends on:** 6A2, 6A3

- [ ] soft scores S1–S9 with configurable weights
- [ ] Overall vs Now scores
- [ ] H1 return correlations vs open exposure
- [ ] historical-edge component (neutral when data is insufficient)
- [ ] deterministic ordering
- [ ] property tests (monotonic in equity)

#### TAA-6A5 — Ranking service

- **Status:** TODO
- **Depends on:** 6A4, 601

- [ ] scheduler (structural 6 h / equity ±5%, dynamic hourly round-robin, Now score per minute)
- [ ] `suitability_snapshots` + 90-day retention
- [ ] RESCAN hook
- [ ] metrics/logs
- [ ] `app.cli advisory rank` table output
- [ ] FakeMT5 multi-asset integration test

### Phase 6B — Watchlists, opportunities & alert windows (rev. 2, requirement 2)

#### TAA-6B1 — Advisory preferences (shared models)

- **Status:** TODO
- **Depends on:** 003

- [ ] watchlists (FAVOURITES, CUSTOM, AUTO_TOP_N)
- [ ] alert metric WIN_PROBABILITY or SETUP_STRENGTH
- [ ] global x + per-list override
- [ ] signal lifetime bars
- [ ] market-session rule
- [ ] user time windows (user timezone)
- [ ] rate limits and per-symbol cooldown
- [ ] expiry-update push
- [ ] language
- [ ] (rev. 2) `TheoryPreferences`: family/detector toggles, bounded parameter overrides, pattern-strategy toggles, minimum supporting theories, conflict policy, presets
- [ ] (rev. 3) `TradingProfile` (PLAN §A31): style slider 0–100 with five anchor presets and interpolation, per-field overrides, hard ceilings, break-even/EV floor on thresholds
- [ ] (rev. 3) `EntryPlan` preferences: `lot_unit`, mode (`SINGLE`/`SAME_PRICE`/`SCALE_IN`), parts, weights, spacing, partial-TP R levels
- [ ] validation shared by cloud and engine
- [ ] `config.yaml` fallback for local runs
- [ ] tests

#### TAA-6B2 — Setup strength & explainable win probability

- **Status:** TODO
- **Depends on:** 301, 307, 6C3 (tables may start empty)

- [ ] setup strength from the condition checklist + confluence score (TAA-307)
- [ ] hierarchical Beta-binomial bucket model (strategy × symbol/asset class × strength bucket × RR band) with 90% CI and n
- [ ] (rev. 2) L2 logistic evidence model (numpy IRLS) used only when it beats the bucket model in walk-forward CV
- [ ] Shapley contributions summing to p − base rate
- [ ] per-evidence standalone hit rate, n, CI and lift
- [ ] computation over any theory subset (disabled detectors neutrally imputed)
- [ ] random baseline 1/(1+RR), break-even (1+c)/(1+RR), EV in R
- [ ] "insufficient data" state
- [ ] tests

#### TAA-6B3 — Market opportunity scanner

- **Status:** TODO
- **Depends on:** 405, 601, 6A5, 6B2, 2A9

- [ ] per new entry-TF bar for the monitored-symbol union
- [ ] strategies (incl. TAA-306) + ADVISORY decision profile
- [ ] only the required detector/strategy union is computed
- [ ] owner-account lot, risk and reward money
- [ ] idempotent market opportunity records for every candidate with evidence snapshot + model features
- [ ] per-cycle time budget
- [ ] **no user alerting here** (personalizer, TAA-8A4)
- [ ] tests

#### TAA-6B4 — Market windows & lifecycle

- **Status:** TODO
- **Depends on:** 6B3

- [ ] market `valid_until` = earliest of signal lifetime / session end / news blackout, with the reason stored
- [ ] invalidation (price drift, SL touched before entry, spread spike, opposite signal)
- [ ] market statuses CANDIDATE/ACTIVE/EXPIRED/INVALIDATED
- [ ] owner FOLLOWED detection from account positions (magic 0)
- [ ] restart catch-up
- [ ] tests with a manual clock

#### TAA-6B5 — Personalization library

- **Status:** TODO
- **Depends on:** 6B1, 6B2, 6B4

- [ ] pure `personalize.py`: for an opportunity × user → entitlements filter
- [ ] theory-subset scoring
- [ ] metric/x/minimum-supporting-theories decision
- [ ] user-window end (earliest with the market window) + badge state
- [ ] rate limit/dedup decision
- [ ] TH/EN notification payload with top-3 contributions, `tag = opportunity_id`, silent replacement on expiry/invalidation, app-badge count
- [ ] tests (the worker wires it up in TAA-8A4)

### Phase 6C — Shadow trades, accuracy & calibration (rev. 2, requirement 3)

#### TAA-6C1 — Shadow trade tracker

- **Status:** TODO
- **Depends on:** 6B3, 501, 603

- [ ] created for every candidate (alerted flag)
- [ ] entry at signal ask/bid with recorded spread + configured slippage
- [ ] lot and equity snapshot
- [ ] PLAN and MANAGED variants
- [ ] resolution on M1 bars with tick tie-breaks (`copy_ticks_range`) and a pessimistic fallback
- [ ] time stop
- [ ] gap handling
- [ ] commission + swap estimate
- [ ] P/L via `calc_profit` + R + MAE/MFE
- [ ] persistence + restart catch-up
- [ ] tests

#### TAA-6C2 — Historical replay

- **Status:** TODO
- **Depends on:** 502, 6C1

- [ ] replay the scanner over N months per symbol using backtest components
- [ ] M5/M1 resolution
- [ ] `source=REPLAY`
- [ ] `app.cli advisory replay`
- [ ] determinism test

#### TAA-6C3 — Calibration & evidence-model builder

- **Status:** TODO
- **Depends on:** 6C1

- [ ] bucket tables from LIVE + REPLAY (replay as a capped prior)
- [ ] empirical-Bayes pooling
- [ ] versioned `calibration_tables`
- [ ] Brier score + reliability data
- [ ] (rev. 2) evidence-model training per strategy family × asset class (replay down-weighted) with walk-forward CV and model selection
- [ ] versioned `evidence_model_versions`
- [ ] nightly and on-demand rebuild
- [ ] tests: synthetic known-p outcomes are recovered, synthetic informative/uninformative detectors get the right sign/≈0 weight

#### TAA-6C4 — Accuracy statistics & theory scoreboard

- **Status:** TODO
- **Depends on:** 6C1

- [ ] hit rate with Wilson CI
- [ ] expectancy (R, money)
- [ ] PF
- [ ] total hypothetical P/L at historical lot sizes
- [ ] follow-all equity curve + max DD
- [ ] breakdowns (symbol, strategy, asset class, session, bucket, watchlist, alerted/followed)
- [ ] threshold explorer (in-sample warning)
- [ ] live/replay separation
- [ ] (rev. 2) **theory scoreboard** per detector/family × asset class × TF (hit rate, expectancy, lift, n)
- [ ] tests

#### TAA-6C5 — Advisory integration & docs

- **Status:** TODO
- **Depends on:** 6C3, 6C4, 6A4

- [ ] accuracy feeds ranking S8 and win probability
- [ ] shadow trades accepted by the analytics trade builder (scope SHADOW)
- [ ] `docs/ADVISORY.md` (formulas, definitions, baselines, assumptions, caveats)

### Phase 7 — Cloud sync

#### TAA-701 — Outbox

- **Status:** TODO
- **Depends on:** 007

- [ ] UUIDv7 event schema
- [ ] priorities
- [ ] batching + gzip
- [ ] backoff
- [ ] quote coalescing
- [ ] backlog metrics
- [ ] tests

#### TAA-702 — HMAC auth library

- **Status:** TODO
- **Depends on:** 004

- [ ] sign and verify (timestamp, nonce, body hash)
- [ ] nonce store
- [ ] dual-secret rotation
- [ ] forgery, replay and skew tests

#### TAA-703 — Ingest API

- **Status:** TODO
- **Depends on:** 702, 801

- [ ] endpoint
- [ ] schema validation
- [ ] idempotent upserts
- [ ] audit-chain continuity check
- [ ] tests

#### TAA-704 — Command channel

- **Status:** TODO
- **Depends on:** 702, 008

- [ ] long-poll endpoint
- [ ] allowlist
- [ ] expiry
- [ ] single-use TOTP verified on the engine
- [ ] results posted back
- [ ] tests

#### TAA-705 — Heartbeat & watchdog

- **Status:** TODO
- **Depends on:** 701, 808

- [ ] engine heartbeats
- [ ] worker ENGINE_OFFLINE/BACK detection (market-hours aware)
- [ ] push

#### TAA-706 — Candle & history sync

- **Status:** TODO
- **Depends on:** 108, 703

- [ ] bulk history upload
- [ ] streaming closed candles
- [ ] tests

#### TAA-707 — (rev. 2) Advisory sync

- **Status:** TODO
- **Depends on:** 701–704, 6B1

- [ ] new event types (`symbol_catalog`, `suitability_snapshot`, `opportunity`, `shadow_trade`, `calibration_version`)
- [ ] advisory-config pull client (ETag/version, local cache, fallback)
- [ ] RESCAN_SUITABILITY command
- [ ] tests

### Phase 8 — Web backend & worker

#### TAA-801 — FastAPI skeleton

- **Status:** TODO
- **Depends on:** 007

- [ ] app factory
- [ ] settings
- [ ] DB
- [ ] health
- [ ] security headers and CSP
- [ ] static PWA serving
- [ ] error handling

#### TAA-802 — Authentication

- **Status:** TODO
- **Depends on:** 801

- [ ] argon2id users
- [ ] TOTP enrollment
- [ ] server-side sessions
- [ ] CSRF
- [ ] rate limit and lockout
- [ ] step-up
- [ ] `app.cli web create-user`
- [ ] tests

#### TAA-803 — Read APIs

- **Status:** TODO
- **Depends on:** 703

- [ ] A14 endpoint set
- [ ] candle overlays and markers
- [ ] pagination and filters
- [ ] masked config
- [ ] tests

#### TAA-804 — SSE stream

- **Status:** TODO
- **Depends on:** 803

- [ ] topics
- [ ] 15 s heartbeats
- [ ] reconnect-safe cursors

#### TAA-805 — Control API

- **Status:** TODO
- **Depends on:** 704, 802

- [ ] kill switch, strategy disable, close/flatten (TOTP) → command queue
- [ ] audit
- [ ] tests

#### TAA-806 — Web Push

- **Status:** TODO
- **Depends on:** 802, 808

- [ ] VAPID key script
- [ ] subscribe, unsubscribe and test
- [ ] per-type preferences
- [ ] sender with dedup and rate limit
- [ ] tests

#### TAA-807 — Backtest jobs

- **Status:** TODO
- **Depends on:** 506, 808

- [ ] creation from validated presets
- [ ] queue
- [ ] worker execution
- [ ] results and compare APIs

#### TAA-808 — Worker service

- **Status:** TODO
- **Depends on:** 801

- [ ] job loop
- [ ] retention
- [ ] push retries
- [ ] scheduling
- [ ] health

#### TAA-809 — (rev. 2) Advisory APIs

- **Status:** TODO
- **Depends on:** 803, 707

- [ ] ranking (list, detail, history)
- [ ] opportunities (filters, detail with shadow results)
- [ ] watchlists CRUD + favourites toggle
- [ ] preferences
- [ ] (rev. 2) theory preferences + detector catalog + theory scoreboard
- [ ] opportunity evidence + contributions
- [ ] shadow trades
- [ ] accuracy
- [ ] calibration
- [ ] threshold explorer
- [ ] engine `advisory-config` endpoint (compute requirements)
- [ ] users locale/timezone
- [ ] tests

#### TAA-810 — (rev. 2) Opportunity push

- **Status:** TODO
- **Depends on:** 806, 809

- [ ] TH/EN templates incl. top-3 evidence contributions
- [ ] (rev. 3) entry plan in push and in-app: orders (market/limit, lot, price, taps), SL, TPs, risk money per order and total, heat after
- [ ] same-tag silent replacement on expiry/invalidation
- [ ] app-badge count
- [ ] per-user quiet windows and rate limits
- [ ] cloud replay jobs in the worker (optional)
- [ ] tests

### Phase 8A — Personalization, entitlements & multi-tenant readiness (rev. 2 follow-up 7)

#### TAA-8A1 — Users, roles & tenancy

- **Status:** TODO
- **Depends on:** 802

- [ ] roles OWNER / SUBSCRIBER / ADMIN
- [ ] `user_id` scoping through one authorization dependency
- [ ] owner-only guards on trading data and control endpoints
- [ ] PDPA-ready data export/delete
- [ ] cross-tenant (IDOR) tests

#### TAA-8A2 — Plans & entitlements

- **Status:** TODO
- **Depends on:** 8A1

- [ ] `plans`, `subscriptions`, `entitlement_overrides`, `usage_counters` tables
- [ ] typed `Feature`/`Limit` keys
- [ ] `EntitlementService.resolve`
- [ ] OWNER plan seeded (unlimited) + inactive FREE/PRO templates
- [ ] enforcement in API, personalizer, worker quotas and the engine compute union
- [ ] tests

#### TAA-8A3 — Account profiles & cloud sizing

- **Status:** TODO
- **Depends on:** 8A1, 401

- [ ] `account_profiles` (LINKED_ENGINE for the owner, MANUAL for others)
- [ ] spec-based ProfitCalculator in the cloud (replicated specs + conversion quotes)
- [ ] cross-check against MT5 sizing on owner data
- [ ] tests

#### TAA-8A4 — Personalizer service

- **Status:** TODO
- **Depends on:** 6B5, 8A2, 8A3, 810

- [ ] worker job: market opportunities × active users via `personalize.py`
- [ ] user alert records + statuses (user-window expiry badge)
- [ ] TH/EN push + in-app
- [ ] per-user suitability ranking
- [ ] per-user accuracy views (snapshotted selection; P/L = R × the user's risk money)
- [ ] publishes compute requirements (symbol/detector/strategy unions) to `advisory-config`
- [ ] (rev. 3) applies the user's `TradingProfile`: thresholds, N, conflict policy, entry plan sizing, portfolio heat
- [ ] single-user equivalence test

#### TAA-8A5 — Billing-ready scaffolding (disabled)

- **Status:** TODO
- **Depends on:** 8A2

- [ ] `BillingProvider` interface (Stripe candidate, R33)
- [ ] signed-webhook design + stub
- [ ] `SUBSCRIPTIONS_ENABLED=false` compliance gate (routes unreachable, tested)
- [ ] `docs/COMPLIANCE.md` (Thai SEC advisory licensing questions, PDPA duties)

### Phase 9 — PWA frontend

#### TAA-901 — Frontend scaffold

- **Status:** TODO
- **Depends on:** —

- [ ] Vite + React + TS + Tailwind + Router + TanStack Query + zod + vite-plugin-pwa
- [ ] ESLint, Prettier, Vitest
- [ ] dev proxy

#### TAA-902 — Auth UI

- **Status:** TODO
- **Depends on:** 802, 901

- [ ] login + TOTP
- [ ] session-expiry handling
- [ ] CSRF-aware API client

#### TAA-903 — App shell

- **Status:** TODO
- **Depends on:** 902, 804

- [ ] responsive navigation
- [ ] dark and light themes
- [ ] mode banner
- [ ] offline and stale indicators
- [ ] SSE client

#### TAA-904 — Dashboard

- **Status:** TODO
- **Depends on:** 903

- [ ] A15 dashboard widgets
- [ ] live updates

#### TAA-905 — Charts

- **Status:** TODO
- **Depends on:** 903

- [ ] Lightweight Charts candles
- [ ] overlays
- [ ] indicator panes
- [ ] markers
- [ ] SL/TP lines
- [ ] S/R zones
- [ ] attribution
- [ ] (rev. 2) evidence overlays: fib levels, necklines, triangle/wedge/channel lines, XABCD, Elliott labels, FVG/order-block boxes, toggled per theory

#### TAA-906 — Symbols

- **Status:** TODO
- **Depends on:** 903

- [ ] spec table
- [ ] live quote and spread
- [ ] context
- [ ] state

#### TAA-907 — Positions & History

- **Status:** TODO
- **Depends on:** 903

- [ ] open positions and intents
- [ ] closed trades
- [ ] trade drawer timeline
- [ ] CSV export

#### TAA-908 — Signals & Decisions

- **Status:** TODO
- **Depends on:** 903

- [ ] decision log
- [ ] check-by-check view
- [ ] reason-code filters

#### TAA-909 — Strategies

- **Status:** TODO
- **Depends on:** 903

- [ ] status
- [ ] parameters
- [ ] per-strategy performance
- [ ] disable action

#### TAA-910 — Backtests UI

- **Status:** TODO
- **Depends on:** 807, 903

- [ ] list
- [ ] detail
- [ ] compare
- [ ] new run

#### TAA-911 — Risk & Controls

- **Status:** TODO
- **Depends on:** 805, 903

- [ ] limits
- [ ] breakers
- [ ] kill switch
- [ ] command history
- [ ] TOTP step-up dialogs

#### TAA-912 — Notifications

- **Status:** TODO
- **Depends on:** 806, 903

- [ ] notification center
- [ ] push enable flow (with iOS guidance)
- [ ] preferences
- [ ] test push

#### TAA-913 — System & Settings

- **Status:** TODO
- **Depends on:** 903

- [ ] health and sync
- [ ] audit verification
- [ ] masked config
- [ ] security settings

#### TAA-914 — PWA polish

- **Status:** TODO
- **Depends on:** 904–913

- [ ] manifest and icons (maskable, Apple)
- [ ] service-worker caching rules
- [ ] install prompt
- [ ] Lighthouse PWA and a11y
- [ ] Playwright smoke tests

#### TAA-915 — (rev. 2) i18n foundation

- **Status:** TODO
- **Depends on:** 901

- [ ] react-i18next (`th` default, `en`)
- [ ] language switcher
- [ ] self-hosted Noto Sans Thai
- [ ] `th-TH-u-ca-gregory` dates with Asia/Bangkok display tz (Buddhist era optional)
- [ ] translation keys for reason codes and explanations
- [ ] locale-aware numbers/currency

#### TAA-916 — (rev. 2) Symbol Ranking page

- **Status:** TODO
- **Depends on:** 809, 915

- [ ] account header
- [ ] Now/Overall sortable table
- [ ] asset-class filter
- [ ] gate chips + "needs equity ≥ $Z"
- [ ] ★ favourites
- [ ] score detail drawer
- [ ] dashboard top-5 widget

#### TAA-917 — (rev. 2) Opportunities page

- **Status:** TODO
- **Depends on:** 809, 810, 915

- [ ] live cards (both metrics, baseline, break-even, EV, lot/risk/reward money, entry/SL/TP)
- [ ] countdown
- [ ] status badges incl. "หมดเวลาที่เหมาะสมแล้ว / suitable time has passed" + reason
- [ ] chart link
- [ ] SW app-badge updates
- [ ] notification deep links
- [ ] (rev. 2) "where the % comes from" panel: base rate → per-theory contribution bars (supporting and conflicting), each theory's track record, number of supporting theories, "show on chart" per evidence

#### TAA-918 — (rev. 2) Watchlists & alert settings

- **Status:** TODO
- **Depends on:** 809, 915

- [ ] favourites and custom lists
- [ ] per-list alerts and x override
- [ ] auto top-N
- [ ] metric choice
- [ ] x slider
- [ ] user time windows editor
- [ ] session rule
- [ ] rate limits
- [ ] expiry updates
- [ ] language

#### TAA-919 — (rev. 2) Signal Accuracy page

- **Status:** TODO
- **Depends on:** 809, 915

- [ ] KPIs
- [ ] follow-all equity curve
- [ ] calibration chart with CIs
- [ ] strength buckets vs hit rate
- [ ] breakdowns
- [ ] outcome history with hypothetical P/L
- [ ] live/replay toggle
- [ ] threshold explorer (in-sample banner)
- [ ] theory scoreboard tab

#### TAA-920 — (rev. 2) Theories & Conditions settings

- **Status:** TODO
- **Depends on:** 809, 8A2, 915

- [ ] family cards with toggles + expandable per-detector toggles
- [ ] tier badges
- [ ] TH/EN explanations + diagrams
- [ ] scoreboard stats per asset class
- [ ] presets
- [ ] minimum supporting theories
- [ ] conflict policy
- [ ] pattern-strategy toggles
- [ ] bounded advanced parameters + reset
- [ ] plan-lock display
- [ ] applies from the next bar

#### TAA-921 — (rev. 2) Account profile, plan & admin pages

- **Status:** TODO
- **Depends on:** 8A1–8A3, 915

- [ ] account profile (linked MT5 values / manual form)
- [ ] plan & usage (billing hidden while disabled)
- [ ] owner admin: users, plan assignment, overrides

#### TAA-922 — (rev. 3) Trading profile page

- **Status:** TODO
- **Depends on:** 6B1, 915

- [ ] "บุคลิกการเทรด / Trading profile" page: style slider with the resulting numbers shown live
- [ ] per-field overrides with "custom" badges and reset
- [ ] entry-plan editor with an example lot breakdown (orders, taps, risk money)
- [ ] warnings for offensive settings and back-loaded scale-in

### Phase 10 — Trade analytics

#### TAA-1001 — Trade builder

- **Status:** TODO
- **Depends on:** 603, 502

- [ ] trades from paper and backtest fills (demo and live later)
- [ ] costs
- [ ] exit reasons
- [ ] MAE/MFE
- [ ] tests
- [ ] (rev. 2) shadow trades as scope SHADOW

#### TAA-1002 — Style tagging

- **Status:** TODO
- **Depends on:** 1001

- [ ] A16 tag set
- [ ] tests

#### TAA-1003 — P/L attribution

- **Status:** TODO
- **Depends on:** 1001

- [ ] rule set
- [ ] text templates
- [ ] evidence values
- [ ] a test per rule

#### TAA-1004 — Recommendations

- **Status:** TODO
- **Depends on:** 1002, 1003, 807

- [ ] stats (bootstrap CI, minimum samples)
- [ ] A16 rules
- [ ] "Backtest this change" job
- [ ] tests

#### TAA-1005 — Analytics API & pages

- **Status:** TODO
- **Depends on:** 1004, 903

- [ ] endpoints
- [ ] Analytics and Recommendations pages
- [ ] scope selector

### Phase 11 — Railway deployment

#### TAA-1101 — Dockerfiles (Railway builds only)

- **Status:** TODO
- **Depends on:** 801, 901

- [ ] web (Node build stage → python:3.11-slim, non-root)
- [ ] worker
- [ ] minimal images
- [ ] healthcheck

#### TAA-1102 — Railway IaC

- **Status:** TODO
- **Depends on:** 1101

- [ ] `.railway/railway.ts`: web, worker, postgres
- [ ] Singapore region
- [ ] variables (sealed secrets)
- [ ] healthcheck
- [ ] pre-deploy migrations
- [ ] restart policy
- [ ] watch paths
- [ ] clean `railway config plan`

#### TAA-1103 — Operations docs

- **Status:** TODO
- **Depends on:** all M1

- [ ] `DEPLOY_RAILWAY.md`
- [ ] `WINDOWS_HOST.md`
- [ ] `RUNBOOK.md`
- [ ] `SECURITY.md` (rotation, incidents)
- [ ] complete README

#### TAA-1104 — First deployment (**only with your go-ahead**)

- **Status:** TODO
- **Depends on:** 1102, 1103

- [ ] deploy
- [ ] create admin via `railway ssh`
- [ ] pair the engine (HMAC)
- [ ] smoke tests: login, ingest, SSE, push, engine-offline alert

> **Milestone 1 review checkpoint:** a paper-trading run visible in the PWA, plus backtests and analytics. Also (rev. 2): symbol ranking, opportunity alerts with per-theory explanations and expiry badges, your theory settings, shadow-trade accuracy and the theory scoreboard. Your feedback comes before any order-sending code.

## Milestone 2 — after review

### Phase 12 — DEMO execution

#### TAA-1201 — ExecutionGateway

- **Status:** TODO
- **Depends on:** 102

- [ ] `order_check` and `order_send` wrapper
- [ ] request builder (filling, deviation, GTC, magic, comment ≤ 25 chars)
- [ ] FakeMT5 tests

#### TAA-1202 — Order lifecycle

- **Status:** TODO
- **Depends on:** 1201, 405

- [ ] intent state machine
- [ ] write-ahead
- [ ] pre-send re-check
- [ ] idempotency

#### TAA-1203 — Retcode handling

- **Status:** TODO
- **Depends on:** 1202

- [ ] A12 matrix
- [ ] ORDER_FAILURES and DUPLICATE_EXECUTION breakers
- [ ] a test per retcode

#### TAA-1204 — Reconciler & post-fill guard

- **Status:** TODO
- **Depends on:** 1203

- [ ] UNKNOWN resolution (widened history windows)
- [ ] slippage and realized-risk checks
- [ ] unprotected-position guard

#### TAA-1205 — Broker position management

- **Status:** TODO
- **Depends on:** 603, 1201

- [ ] SL/TP modify (stops and freeze levels)
- [ ] close
- [ ] flatten
- [ ] rate limits

#### TAA-1206 — DEMO mode

- **Status:** TODO
- **Depends on:** 1201–1205

- [ ] account must be DEMO
- [ ] `ENABLE_DEMO_TRADING`
- [ ] 2-week demo soak runbook and report

### Phase 13 — AI assessment (optional layer)

#### TAA-1301 — AI interface

- **Status:** TODO
- **Depends on:** 301

- [ ] AIProvider protocol
- [ ] NullProvider
- [ ] strict Pydantic schema v1.0
- [ ] parser and validator
- [ ] tests

#### TAA-1302 — Anthropic provider

- **Status:** TODO
- **Depends on:** 1301

- [ ] structured outputs (`output_config.format` / `messages.parse`)
- [ ] `AI_MODEL` (default `claude-opus-5-5`), low effort
- [ ] short timeout + 1 retry
- [ ] refusal or max_tokens → HOLD
- [ ] `fallbacks: "default"` on by default
- [ ] usage and cost logging
- [ ] mocked-client tests

#### TAA-1303 — Veto integration

- **Status:** TODO
- **Depends on:** 1302, 405

- [ ] modes off/advisory/veto
- [ ] per-candle cache
- [ ] daily call and cost budgets
- [ ] timestamp and schema checks
- [ ] AI never increases size

#### TAA-1304 — AI in PWA

- **Status:** TODO
- **Depends on:** 1303, 1005

- [ ] assessments page
- [ ] agreement stats
- [ ] cost tracking
- [ ] optional labelled AI narrative in analytics

#### TAA-1305 — (rev. 2) AI on advisory

- **Status:** TODO
- **Depends on:** 1303, 6C4, 8A2

- [ ] TH/EN AI narrative for ranking and opportunities (descriptive only)
- [ ] AI opinion recorded per opportunity
- [ ] AI accuracy and calibration measured from shadow outcomes
- [ ] opt-in AI alert filter, offered only when it beats the baseline
- [ ] AI as an optional entitlement-gated feature

### Phase 14 — LIVE readiness

#### TAA-1401 — Live gate wiring

- **Status:** TODO
- **Depends on:** 406, 1206

- [ ] 6 conditions + account-bound phrase
- [ ] probation multiplier
- [ ] warning banner
- [ ] tests

#### TAA-1402 — Security review

- **Status:** TODO
- **Depends on:** Phases 12–13

- [ ] threat-model re-check
- [ ] dependency audits
- [ ] web security checklist (OWASP ASVS L2-lite)
- [ ] secrets scan

#### TAA-1403 — Go-live checklist & drills

- **Status:** TODO
- **Depends on:** 1401

- [ ] kill switch
- [ ] breaker reset
- [ ] credential rotation
- [ ] restore from backup
- [ ] engine-offline response

#### TAA-1404 — Final documentation pass

- **Status:** TODO
- **Depends on:** all

- [ ] README, runbooks and docs reflect reality

