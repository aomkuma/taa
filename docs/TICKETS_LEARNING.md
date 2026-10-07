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
- Project rules that apply to every ticket here (see HANDOFF "Notes for the remaining tickets"):
  - a new replicated table needs a sample row in `tests/sync_data.py`
  - every new route a page reads is added to `tests/web/test_api_samples.py` and
    `frontend/src/test/apiSamples.test.ts`
  - run the full pytest and vitest suites one after the other, with the demo stack stopped
- Every ticket that adds or uses a hook (H1–H4) or changes engine behavior under a flag depends on TAA-L002
  (golden harness), even where its "Depends on" line does not repeat it.
- **Separate from the existing process:** new code goes into new modules (`app/learning`, `app/squad`, new
  detector/setup files). Existing modules are read, not rewritten, and change only at the hook points of
  PLAN_LEARNING §L0.2, with a golden test that flags-off behavior is unchanged. Check the reuse map (§L0.1)
  before starting a ticket.

**Execution order: waves** (decided by Claude on 2026-10-06 at the user's request; PLAN_LEARNING §L16). Phases
group tickets by topic. **The waves below are the order of work.** The whole track starts after Phase 14 and
the wrap-up of TICKETS.md, except Wave 0.

| Wave | Tickets | Why at this point |
|---|---|---|
| 0 — Safety fix | L901 | Fixes a latent issue of today's engine (magic = index of enabled strategies). Recommended **before LIVE go-live**, i.e. during Phase 14 / wrap-up (Q11) |
| 1 — Quick wins on existing data | L002, L701, L801, L808 (patterns that need no playbook) | Uses shadow trades, analytics and TAA-1006 data that already exist. Shows which lever (p, W, L, c) and which failure mode matter most, which steers everything after |
| 2 — Data foundation | L001, L101, L102, L103, L104, L203 | Ticks take calendar time to accumulate. Start capture early in the track so L5 has months of data later |
| 3 — Character & regime | L301, L302, L303, L304, L305, L703 | Profiles and regimes feed playbooks, timing and bots. Low risk, explainable, visible in the PWA |
| 4 — Scan everything + squad foundation | L806, L902, L903, L906 | Q10 (scan everything tradable); the bot model, shared computation and trading universe, with legacy mode golden-tested |
| 5 — Playbooks | L601, L802, L803, L804, L805, L807, L306 | The trading approach: router, range, runner + adds, transitions, selection, profile uses |
| 6 — Squad | L904, L905, L907, L908, L909 | Commander, budgets, lifecycle, squad backtest, Squad page; bots start as SHADOW |
| 7 — Timing variants & models | L702, L704, L401, L402, L403, L404, L405, L406, L705, L706 | Need enough shadow outcomes from Waves 3–6 to evaluate fairly |

**Reprioritized 2026-10-07 (docs/SETUP_REVIEW.md):** a one-year replay showed that the setups lose mainly on
entry timing and stops inside the noise (55 % of stopped breakout trades reached their target later; a pullback
entry with a wide stop moved −0.13 R to about 0 R). **L702 (with `PULLBACK_WIDE`) and L707 come first**, ahead of
the waves above; the replay supplies enough history, so L702 no longer waits for Waves 3–6.
| 8 — Tick microstructure in use | L201, L202, L501, L502, L503, L504 | Needs months of recorded ticks from Wave 2 and DEMO time |
| 9 — Governance & wrap-up | L602, L603, L604 | Drift, Learning page, runbook once models are live |

Rules: one ticket at a time; every ticket keeps the legacy path identical with flags off (PLAN_LEARNING §L0.2);
LIVE use of anything here needs Phase 14 and the user's explicit go-ahead.

## Progress

| Milestone | Phase | Tickets | Done | Status |
|---|---|---|---|---|
| M3 | Phase L0 — Feed probe & foundations | 2 | 2 | DONE |
| M3 | Phase L1 — Tick data foundation | 4 | 0 | TODO |
| M3 | Phase L2 — Microstructure features | 3 | 0 | TODO |
| M3 | Phase L3 — Symbol profile & regime | 6 | 0 | TODO |
| M3 | Phase L4 — Signal-quality model | 6 | 0 | TODO |
| M3 | Phase L5 — Tick confirmation of entries | 4 | 0 | TODO |
| M3 | Phase L6 — Adaptive selection, governance & wrap-up | 4 | 0 | TODO |
| M3 | Phase L7 — Entry timing (right direction, wrong time) | 8 | 2 | IN PROGRESS |
| M3 | Phase L8 — Regime playbooks (closing the human gaps) | 8 | 1 | IN PROGRESS |
| M3 | Phase L9 — Squad mode (team of specialist bots) | 9 | 1 | IN PROGRESS |

## Milestone 3 — Learning layer

### Phase L0 — Feed probe & foundations

#### TAA-L001 — DOM and tick-history probe (L1)

- **Status:** DONE
- **Depends on:** — (needs the user's OK to read from the real demo terminal)

- [x] `app.cli ticks probe --symbols ... [--max-weeks 8]`: read-only; `market_book_add/get/release`, a capped `copy_ticks_range` depth search (week granularity, cold-cache retries), tick rate per symbol; refuses with little free disk
- [x] report: DOM empty/static/changing, levels and sizes seen, tick-history depth per symbol, `last`/`volume` usage, flags distribution
- [x] FakeMT5 gains `market_book_*` emulation (empty and populated modes)
- [x] record the findings in PLAN_LEARNING §L1 and decide whether `book_imbalance` (L4) is enabled (2026-10-06: no book on FBS → dropped; flag-96-only ticks must be filtered)
- [x] tests (FakeMT5)

#### TAA-L002 — Hook points and golden harness (§L0.2)

- **Status:** DONE
- **Depends on:** L901

Scope (decided 2026-10-06, §L0.2 rule 9): the harness only. Each hook, and each config section, is added by
the first ticket that needs it, on top of this harness (H1 → L802, H2 → L501/L702, H3 → L804, H4 → L702;
`learning.*` config with its first user, `squad` with L902).

- [x] golden harness `tests/golden/`: backtest trades, advisory replay shadow trades, and the PAPER engine's decisions and positions on FakeMT5 + ManualClock, compared with stored JSON
- [x] regeneration only on purpose (`TAA_UPDATE_GOLDEN=1`), the JSON diff reviewed in the same change
- [x] `LAYERS` entry for `app.learning` (done with L701); `app.squad` with L902
- [x] golden green on today's code

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
- [ ] hour-of-week activity, volatility and spread profiles (168 buckets), reading `LiquidityProfile` (`app/advisory/market_sessions.py`) without changing it
- [ ] trend vs mean reversion: autocorrelation (Newey–West), variance ratio (robust z), Hurst via DFA with bootstrap CI, OU half-life, summary label
- [ ] breakout behavior (follow-through, false break, MFE/MAE in ATR)
- [ ] level respect vs random-level baseline
- [ ] session character, gaps, news sensitivity (`app/news`), correlation cluster (reuse `app/advisory/correlations.py`)
- [ ] each metric: value, CI, n, flags; `INSUFFICIENT_DATA` below `min_samples`
- [ ] tests (synthetic series with known properties: random walk, AR(1), trending drift)

#### TAA-L302 — Regime classifier (L5)

- **Status:** TODO
- **Depends on:** L301

- [ ] `app/learning/regime.py`: overlay that reads `regime_detector` output (unchanged) and adds profile-normalized inputs, efficiency ratio, `QUIET`, hysteresis
- [ ] regime added to opportunity `ctx:` features and shadow rows
- [ ] reason/status codes + i18n
- [ ] tests

#### TAA-L303 — Profile service and storage (L5, L9)

- **Status:** TODO
- **Depends on:** L302

- [ ] `SymbolProfileService`: nightly build on a worker thread, `keep_versions`; data budget: traded, watchlist and tier-1 symbols first, rotation through the catalog via `history_download.py`
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

Note 2026-10-07 (docs/SETUP_REVIEW.md §4): single context rules chosen on one half-year (+0.1 to +0.2 R) fell to
about 0 R on the other half. The model needs the richer evidence features and purged walk-forward; simple
filters are not a substitute.

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

- [ ] hook H2 `EntryPlacer` (pass-through default: place now) if L702 has not added it; golden unchanged
- [ ] `app/learning/entry_confirmation.py` behind hook H2: PENDING → CONFIRMED / CANCELLED_CHASE / CANCELLED_INVALID / CANCELLED_MARKET / EXPIRED_TIMEOUT
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

### Phase L7 — Entry timing (right direction, wrong time)

Design: PLAN_LEARNING §L19. Every variant is evaluated in shadow first; none increases money at risk or moves
the TP.

#### TAA-L701 — Timing diagnostics (L19.1, L19.2)

- **Status:** DONE
- **Depends on:** — (Wave 1; σ from ATR first, the L303 profile σ once it exists); uses existing shadow data and TAA-1006 matches

- [x] `app/learning/timing.py`: pure follow-up after a stop with its own look-ahead H, over analytics `Trade` records (read-only)
- [x] wiring: load trades and bars (M1/M5, look-ahead H) for the report, reading the TAA-1005 after-exit loader approach and `stop_too_tight` without changing them
- [x] failure-mode classification `EARLY` / `LATE` / `STALL` / `TF_MISMATCH` / `WRONG` / `OTHER` / `UNKNOWN`
- [x] i18n codes for the failure modes (th + en) with the first API/PWA use
- [x] winners' MAE quantiles (R, ATR), time-to-target quantiles, pre-entry run (chase), TF agreement
- [x] random-walk first-passage baseline (P(TP first) = b/(a+b), E[τ] = a·b/σ²) shown beside the observed values
- [x] served by `GET /engines/{id}/learning/timing`, computed on request from the replicas like TAA-1005 (a `timing_diagnostics` table only if the load needs one)
- [x] same report for matched manual trades in analytics
- [x] tests (synthetic paths with known outcomes; baseline formula against simulation)

#### TAA-L702 — Entry-mode shadow variants (L19.3)

- **Status:** IN PROGRESS
- **Depends on:** L701

- [ ] hook H4 shadow variant registry (defaults `PLAN`, `MANAGED`) and H2 for waiting entries; golden unchanged
- [ ] shadow variants `PULLBACK`, `LTF_TRIGGER`, `WIDE_STOP` (point-in-time quantiles; same TP price; sizer-based lots) through hook H4
- [x] shadow variant `PULLBACK_WIDE` (2026-10-07): the pullback limit with the `WIDE_STOP` stop measured from the signal's entry; `PULLBACK` alone is reported but expected to be worse (SETUP_REVIEW §4, §6)
- [ ] `entry_window_bars` per waiting mode (default 2, ceiling 6; `signal_expiry_bars` unchanged for `PLAN`); invalidation re-checked each trigger-TF bar (`ENTRY_SETUP_INVALID`)
- [ ] batch resolution on M1 for tier-1 opportunities within the scanner budget
- [ ] paired ΔR vs `PLAN` with bootstrap CI, fill rate, avoided losers vs missed winners, failure-mode mix before and after
- [x] replay support (REPLAY reported separately)
- [x] API `GET /engines/{id}/timing` (diagnostics + variant stats)
- [ ] tests (missed entry = 0 R; risk percent unchanged in `WIDE_STOP`; no variant moves the TP)

#### TAA-L703 — Timing detectors (L19.4)

- **Status:** TODO
- **Depends on:** L303

- [ ] new file `app/evidence/timing.py`: NR4/NR7 and a direction-neutral compression state (ATR percentile, squeeze active before breakout); `volatility.bollinger_squeeze`, `candle.inside_outside`, `sessions.*_breakout` stay as they are
- [ ] session timing (minutes to high-activity hour, dead hour) and news timing
- [ ] expected-time `ctx:` feature from L701
- [ ] `docs/INDICATORS.md` / `docs/PATTERNS.md` entries, explanation keys th + en
- [ ] tests (no lookahead; direction-neutral detectors never add directional support)

#### TAA-L704 — Learned time stop and one re-entry (L19.5)

- **Status:** TODO
- **Depends on:** L702

- [ ] shadow variant `TIME_STOP_LEARNED` (q75 time to +0.5R, bounded by min bars and the configured time stop)
- [ ] shadow variant `REENTRY_1`: HTF structure intact, within lifetime, new trigger, sized from the remaining idea budget
- [ ] re-entry = same `signal_id`, new part number (arbitration cooldown for new signals unchanged); counts toward daily loss and breakers; disabled after a daily-loss or breaker event; labelled everywhere
- [ ] `timing.reentry_enabled` gate for real re-entries (default false; Q7)
- [ ] tests (idea risk never exceeds the original budget; skip below `volume_min`)

#### TAA-L705 — Time-to-move model (L19.6)

- **Status:** TODO
- **Depends on:** L402, L701

- [ ] censored first-passage dataset (+1R vs −1R, TP vs SL)
- [ ] discrete-time hazard (logistic), LightGBM hazard, Kaplan–Meier and random-walk baselines
- [ ] integrated Brier score under purged walk-forward; registry lifecycle as L404
- [ ] alert text "similar setups reached the target in about X–Y h" (th + en), only when n ≥ `eta_min_n` and the model beats Kaplan–Meier
- [ ] holding-style filter and optional predicted q75 for `TIME_STOP_LEARNED`
- [ ] tests (censoring handled; no-signal data never beats the baseline)

#### TAA-L706 — Entry-mode policy and execution (L19.7)

- **Status:** TODO
- **Depends on:** L702, L704

- [ ] `entry_mode_policy` versions per symbol × strategy (pooled fallback); selection only by §L19.7 criteria
- [ ] PWA: timing report, variant comparison, per-strategy override (only among variants; Q8 confirmation flow)
- [ ] engine: market vs limit (`PULLBACK`, expiry = signal lifetime) vs waiting for `LTF_TRIGGER`, through the unchanged risk → mode gate → execution path
- [ ] pending limits cancelled on kill switch and breaker events
- [ ] tests (mode never changes risk; LIVE stays on `PLAN` until the further DEMO period and go-ahead)

#### TAA-L707 — Research harness (2026-10-07)

- **Status:** DONE
- **Depends on:** — (prototypes in `research/2026-10-07-setup-review/`)

The supported version of the setup review's scripts, so a hypothesis about a setup can be tested the same way
every time (by the owner, a session or the research report of L708).

- [x] `app/learning/research.py` (pure): load REPLAY/LIVE shadow trades and the stored M1/M5 bars of their horizon; re-simulate exits (target in R, break-even, partial, trail, time stop), stop multipliers with the same risk percent, retest entries with a stop from the signal's entry, re-entry after a stop
- [x] baselines on the same signals: random direction and the other direction (information and cost drag)
- [x] context splits at the signal bar (hour, stretch from EMA, bar size, ATR percentile, compression, cost share, first signal of the day, HTF alignment)
- [x] every statistic as mean R with a bootstrap CI for all / first half / second half; rules chosen on one half are reported on the other (walk-forward), never on the same data
- [x] `python -m app.cli research hypotheses --strategy NAME [--from DB] [--json]` and `research replay-family` (the per-symbol replay runner with idle priority and a memory guard)
- [x] tests (synthetic paths with known outcomes; the market re-simulation matches the shadow resolver)

#### TAA-L708 — Research report (the AI's research role)

- **Status:** TODO
- **Depends on:** L707

- [ ] a scheduled job (weekly, after the calibration rebuild) runs the L707 hypothesis set on the new LIVE and REPLAY shadow trades per strategy and stores a versioned report
- [ ] the report lists only findings that hold on both halves, with what would change (a proposal, never an applied change)
- [ ] optional TH/EN narrative of the report through the AI notes path (TAA-1305), labelled AI opinion
- [ ] PWA: the report on the Learning page; a proposal links to "Backtest this change" (TAA-1004)
- [ ] tests

### Phase L8 — Regime playbooks (closing the human gaps)

Design: PLAN_LEARNING §L20. Principle: profit cannot be predicted; every rule here must improve a lever of
E[R] = p·W − (1−p)·L − c (or n, survival, discipline), proven in shadow first. Nothing raises the idea's risk above the
per-signal budget.

#### TAA-L801 — Expectancy report (L20.0)

- **Status:** IN PROGRESS
- **Depends on:** — (Wave 1 by strategy × symbol; playbook and bot dimensions added when L802/L902 exist)

- [x] `app/learning/expectancy.py`: p, W, L, c, E[R] with bootstrap CI (reuse `bootstrap_mean_ci`) and opportunity rate per any grouping (strategy × symbol, LIVE/REPLAY, …)
- [ ] playbook and bot dimensions (with L802 / L902)
- [x] "which lever moved" vs the previous version; LIVE and REPLAY separate
- [x] `GET /engines/{id}/learning/expectancy`, computed on request (current vs previous period); a table only if needed
- [x] PWA Learning page section (hypothetical label, th + en)
- [x] tests (decomposition sums to the measured E[R])

#### TAA-L802 — Playbook router (L20.1)

- **Status:** TODO
- **Depends on:** L302, L601, L703

- [ ] hook H1 `CandidateFilter` (structural protocol, pass-through default) in the engine, backtester and replay; golden unchanged
- [ ] `app/learning/playbooks.py`: `TREND_RUNNER` / `RANGE` / `BREAKOUT` / `STAND_ASIDE` from HTF regime, compression, news, spread and costly hours
- [ ] hysteresis `switch_bars`; `playbook_state` table (replicated)
- [ ] `playbooks: [...]` declared per strategy/setup in config; router is disable-only; fit matrix allows a playbook per symbol
- [ ] reason codes `PLAYBOOK_*` + i18n; playbook shown in alerts and on the symbol page
- [ ] tests (never enables a disabled strategy; no flip-flop within `switch_bars`)

#### TAA-L803 — Range playbook (L20.2)

- **Status:** TODO
- **Depends on:** L802, L701 (entry-mode variants of L702 plug in when they exist)

- [ ] qualified-range detector (ADX, efficiency ratio, touches, width vs ATR and cost, no compression); triggers reuse `wyckoff.spring_upthrust`, `levels.sr_zone`, `smc.liquidity_sweep` and reversal candles
- [ ] `setup_range_fade` (`DEMO_UNPROVEN`): edge-zone entry after LTF rejection, stop outside noise (MAE q80), TP1 mid / TP2 opposite edge
- [ ] exit on a closed HTF bar outside the range (`RANGE_BROKEN`), learned time stop
- [ ] `setup_failed_break` (2026-10-07, §L20.2): a range-edge break, then a closed bar back inside within `failed_break_bars`; stop beyond the break's extreme plus the `WIDE_STOP` buffer; shadow first
- [ ] `docs/STRATEGIES.md` entry
- [ ] tests

#### TAA-L804 — Trend runner and risk-free adds (L20.3)

- **Status:** TODO
- **Depends on:** L802, L701 (entry-mode variants of L702 plug in when they exist)

- [ ] hook H3 `ExitPolicy` (default = the §A11 rules) in the engine and backtester; golden unchanged
- [ ] split position (part A at `tp1_r`, part B runner without fixed TP) on the `SAME_PRICE` plan; runner rules as an `ExitPolicy` (hook H3); the §A11 rules stay the default
- [ ] runner trailing: the tighter of HTF structure trail and chandelier `k × ATR`; at least break-even + costs after TP1; SL moves only favorably
- [ ] runner exits: trail, HTF CHoCH against, regime leaves `TREND`, kill switch, breaker; swap accrued and shown
- [ ] under the learning flags, position-count limits count ideas (one signal = one idea) while risk sums all parts; flags off keeps per-position counting (golden test)
- [ ] adds (opt-in, `max_adds`): only when existing stops lock in the add's risk; idea risk ≤ initial budget (property test); count toward heat; off after daily loss or breaker
- [ ] shadow variants `RUNNER`, `RUNNER_ADDS` with paired ΔR, W/L shifts and max DD
- [ ] broker position management (§A11) supports runner trailing in DEMO
- [ ] tests

#### TAA-L805 — Regime transition policies (L20.4)

- **Status:** TODO
- **Depends on:** L803, L804

- [ ] `RANGE_BROKEN`, `RANGE_TO_RUNNER` (shadow variant), `TREND_EXHAUSTION` tighten, `TREND_ENDED` exit
- [ ] no new entries in `VOLATILE` or news blackout; existing stops never widened
- [ ] reason codes + i18n
- [ ] tests (each policy on FakeMT5 scenarios)

#### TAA-L806 — Tiered scanning of all symbols (L20.5)

- **Status:** TODO
- **Depends on:** L302 (interest score uses the playbook once L802 exists)

- [ ] tier 0 indicator-only pass over all tradable symbols (549 on FBS demo) each entry-TF close; interest score; replaces the monitored-set cap of 60 for scanning (alerts keep their own requirements)
- [ ] tier 1 full pipeline for positions, watchlists and the top `tier1_max`; rotation every `rotation_bars`
- [ ] CPU budget per cycle with metrics (latency, symbols per tier, dropped) in `/health` and `doctor`
- [ ] decide and build a separate scan process (HANDOFF homework item 6) so the trading loop never waits for the scan (~7 s cycles today)
- [ ] chart data on demand for any symbol (not only `ALLOWED_SYMBOLS`)
- [ ] universe filter by spread vs cost threshold (Q10)
- [ ] tests (rotation guarantees coverage; budget overrun drops lowest interest first)

#### TAA-L807 — Selection under heat and correlation (L20.6)

- **Status:** TODO
- **Depends on:** L301 (ranks with the current win probability; the L4 model once selected)

- [ ] ranking by expected R per unit risk (cost included), then setup strength
- [ ] at most `max_per_cluster_direction` per correlation cluster and direction; same-currency exposure as one bet
- [ ] rejected signals keep shadow tracking (`HEAT_RANKED_OUT`, `CORRELATED_DUPLICATE`)
- [ ] runs after the existing `app/strategy/arbitration.py` (unchanged), through hook H1
- [ ] tests

#### TAA-L808 — Behavior report on manual trades (L20.7)

- **Status:** DONE
- **Depends on:** L701 (Wave 1; the "against the current playbook" check is added when L802 exists)

- [x] detectors: early exit of winners, stop moved away, revenge trade, overtrading, off-plan trade, comfort-zone bias
- [x] per pattern: count, share, hypothetical ΔR "as traded" vs "as planned"
- [x] engine records the stop history of manual positions (today `manual_trade_links` keeps only `sl_initial`), so `STOP_MOVED` can be judged
- [x] `GET /engines/{id}/learning/behavior`, computed on request + Learning page section
- [x] descriptive, non-judgmental th + en texts; catalogs test passes
- [x] tests

### Phase L9 — Squad mode (team of specialist bots)

Design: PLAN_LEARNING §L21. Legacy single-engine mode stays the default and must behave identically.

#### TAA-L901 — Stable magic registry (L21.8)

- **Status:** DONE
- **Depends on:** — (Wave 0)

Note: this fixes a latent issue of today's engine (magic = base + index of enabled strategies). Recommended
during Phase 14 / wrap-up, before LIVE go-live.

- [x] `magic_registry` table `(bot_id, strategy) → slots`, assigned once, never reused + migration (0038; engine-local, replicated later with L909)
- [x] first start registers `("default", strategy)` with today's values (open positions keep their mapping)
- [x] orchestrator, position manager, broker positions and exposure use the registry
- [x] unknown magic inside the bot range → stray policy, never managed by a guess
- [x] tests (enable/disable/reorder strategies with open positions keeps every mapping)

#### TAA-L902 — Bot model and legacy wrapper (L21.2)

- **Status:** TODO
- **Depends on:** L901

- [ ] `BotSpec` + `squad` config (`enabled`, `bots`, `trade_universe`, `conflict_policy`, `allocation`) with `extra="forbid"` and ceilings
- [ ] legacy mode = one implicit `default` bot from `strategies`, `timeframes`, `symbols.allowed`, `risk`
- [ ] per-bot timeframes, symbol scope, sessions (own weekend rule within its scope, e.g. crypto; news blackouts and account breakers still global), playbooks and entry/exit style
- [ ] `bot_id` on decisions, opportunities, shadow rows, intents and positions (+ migration)
- [ ] bot specs versioned and audited, reloadable without a restart; PWA edits can only lower risk (HANDOFF homework item 6)
- [ ] golden test: legacy decisions and backtest identical to before
- [ ] tests

#### TAA-L903 — Shared computation across bots (L21.2)

- **Status:** TODO
- **Depends on:** L902

- [ ] candles, indicators, evidence, regime/playbook and micro features cached per symbol × TF × bar and shared
- [ ] candle watermarks per bot × symbol × entry TF (each bar evaluated once per bot)
- [ ] CPU metrics per bot and per shared stage; scanner budget covers all bots
- [ ] tests (two bots on the same TF compute evidence once)

#### TAA-L904 — Commander (L21.4)

- **Status:** TODO
- **Depends on:** L902, L807

- [ ] `app/squad/commander.py` behind hook H1: collect every bot's candidates per cycle; deterministic ranking (expected R per unit risk, priority, `bot_id`)
- [ ] `net_direction` policy (`SQUAD_CONFLICT`, `SQUAD_OPPOSES_OPEN`); `independent` opt-in, hedging only, refused on netting accounts
- [ ] same-direction stacking within `max_bots_per_symbol` and `max_symbol_risk_percent`; cross-bot correlation clusters
- [ ] decision record keeps the full candidate list and the reason each lost
- [ ] tests (property: commander never creates or scales up; netting account never gets opposite positions)

#### TAA-L905 — Per-bot risk budgets (L21.5)

- **Status:** TODO
- **Depends on:** L904

- [ ] per-bot `risk_share`, per-trade risk, max positions, own daily stop (`BOT_DAILY_STOP`), `BOT_BUDGET_FULL`
- [ ] per-bot probation multiplier
- [ ] account cage and breakers above all bots; remote changes lower-only
- [ ] `allocation: evidence` (weekly, step-limited, floored, audited): decreases automatic, increases as proposals the owner confirms (CLI / step-up); `BOT_NO_EDGE` auto-pause with shadow kept
- [ ] tests (property: Σ bot risk ≤ cage; each bot ≤ its budget)

#### TAA-L906 — Trading universe (L21.6)

- **Status:** TODO
- **Depends on:** L902, L806

- [ ] `trade_universe: allowlist | catalog`; catalog = enabled, present, tradable, cost filter, spec checks
- [ ] bot scope ∩ trading universe; symbol overrides still apply
- [ ] `doctor` lists the effective trading universe per bot
- [ ] tests (a symbol failing min-lot or cost checks is never traded)

#### TAA-L907 — Bot lifecycle and reports (L21.7)

- **Status:** TODO
- **Depends on:** L905, L801

- [ ] statuses SHADOW / PAPER / ACTIVE / PAUSED / RETIRED; `app.cli squad list | show | promote | pause | resume | retire` (audited)
- [ ] per-bot reports: expectancy decomposition, timing failure modes, fit slice, max DD, correlation with other bots, duplicate-trade flag
- [ ] `bots` and `bot_reports` tables (replicated)
- [ ] tests

#### TAA-L908 — Squad backtest (L21.7)

- **Status:** TODO
- **Depends on:** L904, L905

- [ ] portfolio backtest running the commander over all bots
- [ ] per-bot stand-alone vs squad contribution
- [ ] cloud backtest presets accept a squad config
- [ ] tests (legacy single-bot result equals the existing golden backtest)

#### TAA-L909 — Squad page and starting roster (L21.3, L21.9)

- **Status:** TODO
- **Depends on:** L907

- [ ] API: bots, reports, commander decisions; pause/resume as step-up commands (lower-only)
- [ ] PWA Squad page: bot cards, commander decisions, controls; bot shown on alerts and opportunities
- [ ] i18n th + en (bot names, statuses, `SQUAD_*`/`BOT_*` codes); catalogs test passes
- [ ] starting roster in `config.yaml` as SHADOW bots (`trend_rider`, `range_sniper`, `breakout_hunter`, `pattern_specialist`, `session_opener`, `crypto_247`)
- [ ] `docs/STRATEGIES.md` bot section; runbook for adding a bot
- [ ] lint, typecheck, test, build green
