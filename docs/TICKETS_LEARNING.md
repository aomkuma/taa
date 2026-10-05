# TAA — Learning Layer Tickets & Checklists

Design reference: [PLAN_LEARNING.md](PLAN_LEARNING.md). Section references such as L5 point to that file, and
references such as §A27 point to [PLAN.md](PLAN.md). The main tickets live in [TICKETS.md](TICKETS.md).

## How to use this file

- The status values and Definition of Done are the same as in TICKETS.md: tests, ruff (format + check), mypy and
  bandit are green, and docs are updated. Frontend items also need lint, typecheck, test and build.
- Tick items with the `--file` option:
  `python scripts/tickets.py --file docs/TICKETS_LEARNING.md tick TAA-L101 1 2`, then
  `python scripts/tickets.py --file docs/TICKETS_LEARNING.md sync`.
- Every ticket keeps the safety invariants of PLAN_LEARNING §L10: learning can only veto, delay or explain, never
  create a trade or increase size.
- New reason codes, statuses and explanation keys go into `frontend/src/i18n/` (th + en) in the same change.
- No profitability claims in any text.

**Execution order:** L0 → L1 → L2 → L3 → L4 → L5 → L6. The track starts only after Phase 14 and the wrap-up of
TICKETS.md are finished (user decision 2026-10-06: no early start, not even for tick capture; PLAN_LEARNING
§L16, Q1).

## Progress

| Milestone | Phase | Tickets | Done | Status |
|---|---|---|---|---|
| M3 | Phase L0 — Feed probe | 1 | 0 | TODO |
| M3 | Phase L1 — Tick data foundation | 4 | 0 | TODO |
| M3 | Phase L2 — Microstructure features | 3 | 0 | TODO |
| M3 | Phase L3 — Symbol profile & regime | 6 | 0 | TODO |
| M3 | Phase L4 — Signal-quality model | 6 | 0 | TODO |
| M3 | Phase L5 — Tick confirmation of entries | 4 | 0 | TODO |
| M3 | Phase L6 — Adaptive selection, governance & wrap-up | 4 | 0 | TODO |

## Milestone 3 — Learning layer

### Phase L0 — Feed probe

#### TAA-L001 — DOM and tick-history probe (L1)

- **Status:** TODO
- **Depends on:** — (needs the user's OK to read from the real demo terminal)

- [ ] `app.cli ticks probe --symbols ...`: read-only; `market_book_add/get/release`, `copy_ticks_range` depth search (binary search for the oldest available day), tick rate per symbol
- [ ] report: DOM empty/static/changing, levels and sizes seen, tick-history depth per symbol, `last`/`volume` usage, flags distribution
- [ ] FakeMT5 gains `market_book_*` emulation (empty and populated modes)
- [ ] record the findings in PLAN_LEARNING §L1 and decide whether `book_imbalance` (L4) is enabled
- [ ] tests (FakeMT5)

### Phase L1 — Tick data foundation

#### TAA-L101 — Tick store (L3)

- **Status:** TODO
- **Depends on:** L001

- [ ] `app/market_data/tick_store.py`: Parquet per server/symbol/UTC day (zstd), schema of §L3
- [ ] coverage index (captured intervals) with merge and gap queries
- [ ] quality checks on write (non-positive, crossed, out-of-order, jumps flagged, duplicate bursts) → `TickQualityReport`
- [ ] retention by days and size cap (oldest first)
- [ ] `LAYERS` entry + architecture test
- [ ] tests (round trip, idempotent merge, gaps, retention)

#### TAA-L102 — Tick recorder (L3)

- **Status:** TODO
- **Depends on:** L101

- [ ] `app/market_data/tick_recorder.py`: own thread, shared gateway rate limit, `ManualClock`-testable
- [ ] universe: positions → watchlists → ranking top-N, cap `max_symbols`, refresh every 15 min
- [ ] incremental pull with persisted watermark (`tick_watermarks`: last ms + ordinal) and 2 s overlap dedup
- [ ] pauses on disconnect, re-verification and closed sessions; backfill on start (`backfill_days`)
- [ ] server time → UTC through `ServerClock` only
- [ ] config `learning.ticks` (`extra="forbid"`, ceilings) + migration
- [ ] wired into `app.main` behind `learning.enabled` and `learning.ticks.enabled`
- [ ] tests (FakeMT5 tick generation, restart without duplicates or holes, disconnect)

#### TAA-L103 — Micro-bars (L3)

- **Status:** TODO
- **Depends on:** L102

- [ ] `app/market_data/micro_bars.py`: per-M1 summary columns of §L3, built only for closed, covered minutes
- [ ] Parquet `data/micro/<server>/<symbol>/<YYYY-MM>.parquet`, idempotent rebuild from raw ticks
- [ ] `micro_bar_daily` table (replicated) + migration + outbox mapping
- [ ] tests (golden values, partial coverage, rebuild equality)

#### TAA-L104 — Tick CLI and health (L3)

- **Status:** TODO
- **Depends on:** L103

- [ ] `app.cli ticks status | backfill | verify --day | prune`
- [ ] `doctor` section: recorder running, lag per symbol, disk use, last quality report
- [ ] `/health` field for the recorder
- [ ] tests

### Phase L2 — Microstructure features

#### TAA-L201 — Feature library (L4)

- **Status:** TODO
- **Depends on:** L103

- [ ] `app/indicators/microstructure.py` (pure): `tick_intensity_z`, `tick_imbalance`, `ofi_l1`, `velocity_atr`, `spread_ratio`, `spread_widening`, `quote_stall`, `jump_flag`, `run_persistence`, `range_position`, `efficiency_ratio`
- [ ] `book_imbalance` only if TAA-L001 enabled it
- [ ] `None` on insufficient coverage, never interpolated
- [ ] bar-level approximations tagged `approx=True`
- [ ] docs: `docs/INDICATORS.md` section "Tick-flow (quote) indicators", stating they are proxies
- [ ] tests (hand-computed fixtures per feature)

#### TAA-L202 — No-lookahead harness (L4)

- **Status:** TODO
- **Depends on:** L201

- [ ] property test: random truncation points give identical values at `t`
- [ ] tick replay source for backtests (`TickReplay`) over recorded days, with the gateway's `ticks_range` semantics
- [ ] backtest flag `--micro` only over recorded coverage; fails closed outside it
- [ ] tests

#### TAA-L203 — FakeMT5 realistic ticks

- **Status:** TODO
- **Depends on:** L102

- [ ] seeded tick generator: intensity by hour of week, spread regimes, rollover spikes, stalls and jumps
- [ ] scenarios for the tests of L3–L5 (trending, ranging, news spike)
- [ ] tests

### Phase L3 — Symbol profile & regime

#### TAA-L301 — Profile metrics library (L5)

- **Status:** TODO
- **Depends on:** L201

- [ ] `app/learning/` package + `LAYERS` entry + "no execution imports" architecture test
- [ ] hour-of-week activity, volatility and spread profiles (168 buckets)
- [ ] trend vs mean reversion: autocorrelation (Newey–West), variance ratio (robust z), Hurst via DFA with bootstrap CI, OU half-life, summary label
- [ ] breakout behavior (follow-through, false break, MFE/MAE in ATR)
- [ ] level respect vs random-level baseline
- [ ] session character, gaps, news sensitivity (`app/news`), correlation cluster
- [ ] each metric: value, CI, n, flags; `INSUFFICIENT_DATA` below `min_samples`
- [ ] tests (synthetic series with known properties: random walk, AR(1), trending drift)

#### TAA-L302 — Regime classifier (L5)

- **Status:** TODO
- **Depends on:** L301

- [ ] `app/learning/regime.py`: rule-based `QUIET`/`RANGE`/`TREND`/`VOLATILE`/`UNKNOWN` with profile-normalized inputs
- [ ] regime added to opportunity `ctx:` features and shadow rows
- [ ] reason/status codes + i18n
- [ ] tests

#### TAA-L303 — Profile service and storage (L5, L9)

- **Status:** TODO
- **Depends on:** L302

- [ ] `SymbolProfileService`: nightly build on a worker thread, `keep_versions`
- [ ] stability check 30 vs 90 days → `SHIFTING`
- [ ] `symbol_profiles` table + migration + outbox mapping
- [ ] `app.cli learning profile build | show SYMBOL`
- [ ] config `learning.profile` + `learning.regime`
- [ ] tests (version naming, reproducibility, failure keeps previous version)

#### TAA-L304 — Profile API (L11)

- **Status:** TODO
- **Depends on:** L303

- [ ] `GET /engines/{id}/symbols/{symbol}/profile` (latest + history), owned engines only
- [ ] zod schemas on the frontend
- [ ] tests

#### TAA-L305 — Character tab in the PWA (L11)

- **Status:** TODO
- **Depends on:** L304

- [ ] symbol page → Character tab: hour-of-week heat maps, trend/mean-reversion with CI, breakout, sessions, news sensitivity, regime now, stability flags
- [ ] explanation keys `explain:learning.*` (th + en), parity tests
- [ ] "insufficient data" and "behavior changing" states
- [ ] lint, typecheck, test, build green

#### TAA-L306 — Profile uses in advisory and strategy (L5)

- **Status:** TODO
- **Depends on:** L303

- [ ] ranking factor: costly hours and spread stress (§A25), behind config
- [ ] alert windows exclude costly hours and news blackouts per symbol (§A26), opt-in
- [ ] volatility-aware SL/TP suggestion; sizing unchanged in risk percent; cage ceilings respected
- [ ] profile gates (disable only, audited, reason code `PROFILE_GATE`)
- [ ] tests (gates never enable; size risk percent unchanged)

### Phase L4 — Signal-quality model

#### TAA-L401 — Dataset builder (L6)

- **Status:** TODO
- **Depends on:** L303

- [ ] `app/learning/dataset.py`: CLOSED PLAN shadow rows (LIVE, REPLAY flagged) + profile, regime and micro features at signal time + `has_ticks`
- [ ] label intervals (signal time → exit time) kept for purging
- [ ] feature schema with hash; training data hash
- [ ] point-in-time joins only (profile version valid at signal time)
- [ ] tests (no future profile leaks into a row)

#### TAA-L402 — Purged walk-forward evaluator (L6)

- **Status:** TODO
- **Depends on:** L401

- [ ] `app/learning/evaluation.py`: purged walk-forward with embargo = max trade lifetime
- [ ] Brier, log loss, reliability bins; economic metric (θ from training folds, expectancy in R OOS) with paired bootstrap CI
- [ ] configuration count recorded; deflated penalty reported
- [ ] live and replay reported separately
- [ ] tests (leakage test: a deliberately leaky feature must not survive purging)

#### TAA-L403 — Gradient-boosted candidate (L6)

- **Status:** TODO
- **Depends on:** L402

- [ ] `lightgbm` pinned in `requirements/engine.txt` (after the user's OK, Q3)
- [ ] `GbtModel`: shallow trees, monotone constraints, fixed small grid (≤ `max_configs`), seeded
- [ ] isotonic/Platt calibration on OOS predictions
- [ ] text-format save/load (`model_to_string` / `Booster(model_str=...)`), no pickle
- [ ] Shapley attribution through the existing machinery with a `predict_proba` callable
- [ ] logistic model extended with profile features
- [ ] tests (reproducible model text, schema-hash mismatch → unavailable)

#### TAA-L404 — Model registry and lifecycle (L9)

- **Status:** TODO
- **Depends on:** L403

- [ ] `ml_model_versions` + `model_predictions` tables + migrations + outbox (metadata only)
- [ ] lifecycle CANDIDATE → SHADOW → ACTIVE → RETIRED / REJECTED, status history
- [ ] `app.cli learning train | list | show ID | promote ID --reason | demote ID --reason`, audited
- [ ] weekly training schedule on a worker thread, thread cap
- [ ] retention (20 per scope + every former ACTIVE)
- [ ] tests

#### TAA-L405 — Integration into the win probability (L6)

- **Status:** TODO
- **Depends on:** L404

- [ ] `GbtModel` as a candidate in `build_win_probability`; selection only by the L6 rules
- [ ] SHADOW predictions recorded per opportunity, shown separately as "under evaluation"
- [ ] opportunity stores the model version used
- [ ] explanation keys for new feature families (th + en)
- [ ] tests (a no-signal dataset never selects GBT)

#### TAA-L406 — Engine filter mode (L6, L10)

- **Status:** TODO
- **Depends on:** L405

- [ ] `filter_mode` off/advisory/filter; the filter can only skip entries (reason `MODEL_FILTER`)
- [ ] `on_unavailable` baseline/block (forced to block in LIVE)
- [ ] decision record holds model version, feature hash and p
- [ ] filtered signals keep shadow tracking
- [ ] tests (never increases size, never bypasses risk/mode gate/breakers/kill switch)

### Phase L5 — Tick confirmation of entries

#### TAA-L501 — Confirmation state machine (L7)

- **Status:** TODO
- **Depends on:** L201, L202

- [ ] `app/engine/entry_confirmation.py`: PENDING → CONFIRMED / CANCELLED_CHASE / CANCELLED_INVALID / CANCELLED_MARKET / EXPIRED_TIMEOUT
- [ ] `pending_entries` table; pending rows expire after restart (fail closed)
- [ ] risk re-check at confirmation time; one evaluation per bar preserved
- [ ] `on_no_ticks` immediate/cancel (forced to cancel in LIVE); config `learning.confirmation` with ceilings
- [ ] reason codes `MICRO_*` + i18n
- [ ] tests (ManualClock + FakeMT5 scenarios from L203)

#### TAA-L502 — CONFIRMED shadow variant and A/B statistics (L7)

- **Status:** TODO
- **Depends on:** L501

- [ ] shadow variant `CONFIRMED` (same opportunity; a cancelled one counts as 0 R)
- [ ] paired ΔR with bootstrap CI, hit rate, expectancy, max DD, cancellations by reason, avoided losers vs missed winners
- [ ] `GET /engines/{id}/confirmation/stats`
- [ ] tests

#### TAA-L503 — Latency measurement (L7)

- **Status:** TODO
- **Depends on:** L501

- [ ] timestamps: decision, confirmation, `order_send` start/end, deal fill
- [ ] p50/p95 latency and slippage vs confirmation price per symbol; flag above `max_latency_ms`
- [ ] `demo-report` section
- [ ] tests

#### TAA-L504 — Enable in DEMO (L13)

- **Status:** TODO
- **Depends on:** L502, L503

- [ ] acceptance check per §L13 (≥ 200 opportunities, paired ΔR CI > 0), numbers recorded in HANDOFF
- [ ] DEMO run with confirmation on; runbook section in `docs/RUNBOOK_DEMO.md`
- [ ] LIVE stays off until the further DEMO period, Phase 14 and the user's go-ahead

### Phase L6 — Adaptive selection, governance & wrap-up

#### TAA-L601 — Strategy × symbol × regime fit matrix (L8)

- **Status:** TODO
- **Depends on:** L302

- [ ] `app/learning/fit_matrix.py`: expectancy in R with empirical-Bayes pooling, LIVE and REPLAY separate
- [ ] `fit_matrix` table (replicated) + nightly build
- [ ] opt-in gate: disable when the upper 90% bound < 0 and n ≥ `min_n`; auto re-enable; reason `FIT_GATE_NEGATIVE`; audited
- [ ] gated cells keep shadow tracking
- [ ] tests (gate never enables a strategy config.yaml disabled)

#### TAA-L602 — Drift monitoring and auto-demotion (L9)

- **Status:** TODO
- **Depends on:** L404

- [ ] PSI per feature vs training; rolling Brier vs bucket baseline
- [ ] automatic demotion ACTIVE → SHADOW, `MODEL_DRIFT` notification (pushed), audit entry, fallback to previous selection
- [ ] hourly job; config `learning.drift`
- [ ] tests

#### TAA-L603 — Learning page in the PWA (L11)

- **Status:** TODO
- **Depends on:** L405, L502, L601

- [ ] models: status, metrics, reliability diagram, drift, status history
- [ ] fit-matrix heat map (labelled hypothetical, n and CI)
- [ ] confirmation A/B results
- [ ] `learning` entitlement (owner only; subscriptions stay off)
- [ ] i18n th + en, catalogs test (no profitability language)
- [ ] lint, typecheck, test, build green

#### TAA-L604 — Documentation and runbook (all)

- **Status:** TODO
- **Depends on:** L601, L602, L603

- [ ] PLAN_LEARNING updated with the decisions taken in each ticket
- [ ] runbook: enable, promote, demote, disk housekeeping, what to do on `MODEL_DRIFT`
- [ ] README and HANDOFF links
- [ ] CLAUDE.md commands section updated with the new CLI commands
