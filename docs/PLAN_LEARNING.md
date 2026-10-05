# TAA — Learning Layer: Symbol Character, Tick Microstructure & Signal Quality (Design)

> Separate design track, started 2026-10-06. It extends [PLAN.md](PLAN.md) and does not replace any part of it.
> Work items live in [TICKETS_LEARNING.md](TICKETS_LEARNING.md). Section numbers here are `L0`–`L18`; references
> such as §A27 point to PLAN.md. No profitability claims anywhere: every model here can only estimate, filter
> or explain. Capital protection, fail-closed behavior and auditability still come first.

## L0. Context & goals

**Request (2026-10-06):** can the system learn

1. the **character of each symbol**: how it typically moves, when, and how far;
2. **more precise entry timing from ticks**;
3. **where price is likely to go next from ticks**, buying/selling pressure, and similar market microstructure.

**Goals.**

- G1. A versioned, explainable **symbol profile** per server × symbol that describes its behavior: volatility and
  spread by hour of week, trend vs mean-reversion tendency, breakout behavior, regime, news sensitivity and
  correlation cluster.
- G2. A **tick data foundation**: record, store and summarize the tick stream the broker sends, because history
  depth at the broker is short and data is the bottleneck for everything else.
- G3. **Microstructure features** (tick intensity, tick imbalance, spread state, quote stalls, jumps). They are
  labelled as proxies and computed without lookahead.
- G4. A **signal-quality (meta-label) model** that estimates P(TP before SL) for signals the existing strategies
  produce. It competes with the current bucket and logistic models (§A27) and wins only out of sample.
- G5. **Tick confirmation** of entries: a closed-bar signal may wait a short time for micro conditions, or be
  cancelled. Its value is proven by an A/B shadow comparison before it is enabled.
- G6. A **learning loop with governance**: scheduled retraining, model lifecycle, drift detection and automatic
  demotion, with every step audited.

**Non-goals (explicit).**

- No high-frequency or latency-arbitrage trading. A retail Windows + MT5 + home-network path has hundreds of ms
  of latency, and spread plus commission dominate any micro edge.
- No price-direction model that trades on its own. Learning components **rank, filter, delay or explain** signals
  from the existing strategy layer; they never create a trade.
- No deep learning and no reinforcement learning in this track. They need far more data than one retail account
  produces, overfit easily, and cannot meet the explainability requirement of §A29. This can be revisited
  after L4 has a proven baseline (L18, Q4).
- No online learning inside the trading loop. Training always runs off the loop, and a model is promoted only
  through the explicit lifecycle (L9).
- The LLM provider (Phase 13 in TICKETS.md) is not part of prediction here. Its role is narrative only (L12).

## L1. Data reality: what FBS × MT5 actually provides

| Data | What it really is | Consequence |
|---|---|---|
| `copy_ticks_*` (`time_msc`, `bid`, `ask`, `last`, `volume`, `flags`) | The broker's quote stream, already filtered or aggregated by FBS. For FX/CFD, `last` and `volume` are usually 0. | Microstructure means **quote dynamics**, not trades. |
| Bar `tick_volume` | The number of quote updates in the bar | An activity proxy, not traded volume |
| Bar `real_volume` | 0 for FX/CFD on FBS | Unusable |
| `market_book_*` (DOM) | **Unverified.** FBS advertises DOM in its MT5 offering, but for OTC FX a retail DOM shows the broker's own quote ladder (indicative sizes), not a market-wide book | Probe it first (TAA-L001). Book features stay optional, behind the probe result, and the design must work without them |
| Tick history depth | `copy_ticks_range` returns only what the broker's server keeps. The depth varies by symbol and server and is not documented | Probe the depth (TAA-L001) and **record ticks ourselves** from day one (L3) |
| Time | `time_msc` in broker server wall-clock (EET/EEST) | Convert only through `ServerClock` (as in PLAN §A5) |

**Real buy/sell pressure is not observable.** Every "pressure" feature here is a proxy, named and explained as
one in code, UI text and docs. The broker's quote stream may differ from other venues, so tick-based findings
are valid for **this broker's feed only**. Profiles and models are always keyed by server.

### L1.1 Research notes that shape the design

- **Order-flow imbalance works on very short horizons.** On exchange limit-order books, OFI (Cont, Kukanov &
  Stoikov, "The Price Impact of Order Book Events", 2014; generalized in arXiv:2112.02947) has a near-linear
  relation with **contemporaneous** and very short-horizon price changes. The predictive window is seconds up
  to about a minute. Our count-based quote OFI (no sizes, broker feed) is a weaker proxy than that. Its
  realistic use is therefore **timing and filtering an entry within minutes** (L7), not forecasting the next
  hours.
- **FX order flow explains prices but is not ours to see.** Evans & Lyons ("Order Flow and Exchange Rate
  Dynamics", JPE 2002) explain 40–80% of daily FX changes with signed **interdealer** order flow, and that
  explanation is mostly contemporaneous. Retail MT5 quotes carry no trade sign or size, so this result cannot be
  reproduced with our data. It is cited here to keep expectations honest.
- **Meta-labeling and purged CV.** López de Prado (*Advances in Financial Machine Learning*, 2018, ch. 3 and 7)
  describes the triple-barrier method and meta-labeling. Its purged k-fold with embargo prevents leakage from
  overlapping label horizons. L6 follows it.
- **Random-walk tests.** Lo & MacKinlay (1988) give the variance-ratio test with a heteroskedasticity-robust
  statistic. Detrended fluctuation analysis is a more robust Hurst estimate than R/S on short, noisy series.
  Both are reported with uncertainty (L5).
- **Jumps.** The ratio of realized variance to bipower variation (Barndorff-Nielsen & Shephard, 2004) separates
  continuous volatility from jumps (L4 `jump_flag`).
- **Model storage.** LightGBM serializes boosters to its own text format (`Booster.model_to_string()` and
  `Booster(model_str=...)`), so models can live in the database without pickle (L6, L10).

## L2. Architecture & placement

```
MT5 terminal ──copy_ticks_range──▶ TickRecorder (engine, own thread)
                                       │ raw ticks
                                       ▼
                       TickStore (Parquet, local only)
                                       │
                         MicroBarBuilder (per M1 summary) ──▶ micro-bar Parquet (long retention)
                                       │
          ┌────────────────────────────┼─────────────────────────────┐
          ▼                            ▼                             ▼
  microstructure features     SymbolProfileService            DatasetBuilder
  (pure, app/indicators)      (nightly, app/learning)         (shadow + replay labels)
          │                            │                             │
          ▼                            ▼                             ▼
  EntryConfirmation (engine)   symbol_profiles (versioned) ──▶ ModelTrainer (off-loop)
          │                            │                             │
          ▼                            ▼                             ▼
  decision pipeline ◀── filter/delay only ── ModelRegistry (CANDIDATE → SHADOW → ACTIVE)
          │
          ▼
  risk → mode gate → execution (unchanged)
```

**New modules and layers** (`tests/unit/test_architecture.py` `LAYERS` gets the new entries in the same change):

| Module | Layer | Notes |
|---|---|---|
| `app/market_data/tick_store.py` | 4 (market_data) | Parquet tick store and coverage index |
| `app/market_data/tick_recorder.py` | 4 | Incremental capture through `MarketDataGateway.ticks_range` |
| `app/market_data/micro_bars.py` | 4 | Raw ticks → per-minute summaries |
| `app/indicators/microstructure.py` | 5 (indicators) | Pure functions, no I/O, no clock |
| `app/learning/` (new package) | 9 (with advisory/analytics) | profile, regime, dataset, models, registry, drift, fit matrix |
| `app/engine/entry_confirmation.py` | 10 (engine) | Confirmation state machine inside the decision path |

**Rules.**

- `app/learning` never imports `app.execution`, the order functions or `MetaTrader5`. It gets data through
  stores and the read-only gateway only. A new architecture test enforces this.
- No direct wall-clock reads. Everything takes a `Clock`, and tests use `ManualClock`.
- **Compute once, personalize per user** (PLAN §A30) still holds: the engine computes profiles, features and
  model outputs, and the cloud only replicates and personalizes them (for example, a user's own filter
  threshold).
- Raw ticks **never leave the engine machine** because of their size. Micro-bars, profiles, model metadata and
  per-opportunity model outputs replicate through the existing outbox (PLAN §A13).

## L3. Tick capture & storage

**TickRecorder.**

- **Universe:** symbols with open positions, plus every watchlist symbol and symbols in the top-N of the ranking,
  capped at `learning.ticks.max_symbols` (default 20). If the cap is hit, positions come first, then
  watchlists, then ranking order. The universe is recomputed every 15 minutes.
- **Incremental pull:** every `poll_seconds` (default 5 s) per symbol, `copy_ticks_range(from = last
  time_msc - overlap, to = now)` with `COPY_TICKS_ALL`. A per-symbol watermark (`last time_msc` plus a
  count of ticks seen at that millisecond) is persisted in SQLite, so restarts neither duplicate nor skip ticks.
- **Deduplication:** key = (`time_msc`, ordinal within the same ms, `bid`, `ask`, `flags`), with an overlap
  window of 2 s to absorb late ticks.
- **Threading:** it runs on its own thread with a rate limit shared with the gateway (it must never starve the
  trading loop's calls). It pauses while the terminal is disconnected or during account re-verification.
- **Backfill:** at start, and for any new universe symbol, it pulls as far back as the broker serves (bounded by
  `backfill_days`, default 30). Whatever the broker returns is recorded with its real coverage.
- **Market closed:** it skips symbols whose session is closed (`trading_sessions.py`), and records nothing rather
  than recording stale repeats.

**TickStore.**

- **Layout:** `data/ticks/<server>/<symbol>/<YYYY-MM-DD>.parquet` (UTC date) with columns `time_utc_ms` (int64),
  `bid`, `ask`, `last`, `volume`, `flags` (uint16) and `ordinal` (uint16). It uses zstd compression.
- **Coverage index:** `data/ticks/<server>/<symbol>/coverage.json` holds continuous intervals that were actually
  captured. A gap (terminal offline, engine stopped) is an explicit hole, and features over a hole are `None`,
  never interpolated.
- **Quality checks on write:** non-positive prices, crossed quotes (`bid > ask`), out-of-order time, jumps beyond
  `k × rolling median |Δmid|` (flagged, not dropped), and duplicate bursts. Counts go to `TickQualityReport`.
- **Retention:** raw ticks for `raw_retention_days` (default 120), plus a size cap (`max_gb`, default 20) that
  deletes the oldest days first. Micro-bars are kept indefinitely (they are small).
- **Size estimate:** EURUSD on FBS gives about 50–150k ticks a day, which is about 1–3 MB a day compressed. Twenty
  symbols over 120 days fit in a few GB.

**Micro-bars** (`micro_bars.py`): per symbol × M1, aligned to the same UTC minute grid as candles. Columns:

- `n_ticks`, `n_bid_changes`, `n_ask_changes`
- `upticks`, `downticks` (mid changes by sign)
- `spread_mean`, `spread_max`, `spread_p95` (points)
- `mid_open`, `mid_close`, `mid_high`, `mid_low`
- `rv` (sum of squared log mid returns), `bpv` (bipower variation)
- `max_gap_ms` (longest inter-tick gap), `first_tick_ms`, `last_tick_ms`
- `coverage` (share of the minute inside captured intervals)

A micro-bar is built only when its minute is closed and fully covered (otherwise `coverage < 1` and features skip
it). Micro-bars live in `data/micro/<server>/<symbol>/<YYYY-MM>.parquet`, and their engine-side summary also
replicates as `micro_bar_daily` aggregates for the PWA.

**CLI:** `app.cli ticks status | backfill --symbols ... | verify --day ... | prune`.

## L4. Microstructure features (pure, lookahead-free)

`app/indicators/microstructure.py`. Every function takes ticks or micro-bars **ending at or before** a decision
time `t` and returns a value or `None` when coverage is insufficient. Windows `W` are in minutes or ticks and set
in config.

| Feature | Definition | Reads as (proxy) |
|---|---|---|
| `tick_intensity_z` | `n_ticks` over W, z-scored against the symbol's same hour-of-week profile (L5) | Unusual activity |
| `tick_imbalance` | (upticks − downticks) / (upticks + downticks) over W | Direction of quote pressure |
| `ofi_l1` | Σ over ticks of `1{bid↑} − 1{bid↓} + 1{ask↑} − 1{ask↓}`, a count-based adaptation of order-flow imbalance (Cont, Kukanov & Stoikov) without sizes, normalized by tick count | Which side of the quote is moving |
| `velocity_atr` | (mid_t − mid_{t−W}) / ATR(entry TF) per minute | Speed of the move relative to normal |
| `spread_ratio` | Current spread / the profile's median spread for this hour of week | Liquidity stress |
| `spread_widening` | `spread_ratio > k` sustained for ≥ s seconds | Avoid entering |
| `quote_stall` | `now − last_tick > max(3 × typical gap, 10 s)` while the session is open | Feed problem or illiquidity |
| `jump_flag` | rv / bpv over W above a threshold (Barndorff-Nielsen & Shephard ratio) | Discontinuous move (news, spike) |
| `run_persistence` | Mean run length of same-sign mid changes over W vs a shuffled baseline | Micro-trend vs noise |
| `range_position` | (mid − low_W) / (high_W − low_W) | Chasing guard |
| `efficiency_ratio` | \|net Δmid\| / Σ\|Δmid\| over W (Kaufman) | Trending vs choppy quotes |
| `book_imbalance` (optional) | (Σ bid size − Σ ask size) / total over the top k levels of `market_book_get` | The broker ladder's lean. Enabled only if TAA-L001 shows a non-empty, changing book |

**Rules.**

- **No lookahead:** a property test feeds the same tick sequence truncated at random points and checks that every
  feature at `t` is identical whether or not later ticks exist.
- **Server time:** ticks are converted once at capture (`ServerClock`), and features see UTC only.
- **Naming:** UI and docs call these "quote-flow" or "tick-flow" indicators, never "order flow" or "volume", and
  the explanation key says they come from the broker's quotes.
- **Bar-level fallback:** for history without ticks, a few features have coarse approximations from M1 candles
  (`tick_volume` instead of `n_ticks`, bar spread instead of the spread profile). These are tagged `approx=True`
  and never mixed with tick-based values in one training set without a flag feature.

## L5. Symbol profile ("character")

`app/learning/profile.py`, `SymbolProfileService`. It is computed nightly per server × symbol from candles
(M1…D1), micro-bars when available, shadow and replay outcomes, and the news calendar (`app/news`).

**Windows:** the primary window is the last 90 days, plus a 30-day window for the stability check. A metric
needs `min_samples` (per metric) or it is `None` with reason `INSUFFICIENT_DATA`.

**Metrics.**

1. **Activity and volatility by hour of week** (168 buckets, server-time aware through UTC):
   - median and p90 of the M5 true range in points and as a share of ATR(D1)
   - median `tick_volume` (and `n_ticks` from micro-bars)
   - share of days with a range above 1.5× the median
2. **Spread profile by hour of week:** the median and p95 spread, plus rollover spikes (the 23:55–00:10 server
   window), and hours where `p95 spread / median true range` exceeds a cost threshold (marked "costly hours").
3. **Trend vs mean reversion** on M5, M15, H1 and H4:
   - lag-1 and lag-k autocorrelation of log returns (Newey–West SE)
   - Lo–MacKinlay variance ratio VR(q) for q ∈ {2, 4, 8, 16}, with a heteroskedasticity-robust z
   - Hurst exponent via DFA, reported with a bootstrap CI (single-number Hurst estimates are noisy, so the CI
     is shown)
   - Ornstein–Uhlenbeck half-life of deviations from a moving mean (H1)
   - Summary label: `TRENDING` / `MEAN_REVERTING` / `RANDOM_WALK_LIKE`, set only when the CI excludes the
     random-walk value; otherwise `RANDOM_WALK_LIKE`
4. **Breakout behavior**, for N-bar high/low breaks with N ∈ {20, 55} on M15 and H1:
   - follow-through rate: price reaches +1 ATR beyond the break before returning inside the range
   - false-break rate
   - median MFE and MAE in ATR over the next 24 bars
5. **Level respect:** the touch-then-reverse rate at evidence levels (`app/evidence/levels.py`, Fibonacci),
   compared with the rate at random price levels of the same distance. Only the difference is reported, because
   the raw rate is meaningless alone.
6. **Session character:** the Asia range as a share of the daily range, the London-open breakout rate of the Asia
   range, and New York continuation vs reversal.
7. **Gaps:** weekend gap size distribution and gap-fill rate within 24 h.
8. **News sensitivity:** the absolute 30-minute move after high-impact events for the symbol's currencies,
   divided by the same hour's baseline. Where it applies, the result gives "news blackout" suggestions.
9. **Correlation cluster:** rolling 60-day correlation of H1 returns with the other universe symbols, and
   hierarchical clustering into groups (reused from `app/advisory/correlations.py`).
10. **Strategy fit:** a link to the L8 fit matrix row for this symbol.

**Regime classifier** (`app/learning/regime.py`). It is rule-based first, for explainability, using
profile-normalized inputs on the entry TF:

| Regime | Rule (defaults) |
|---|---|
| `QUIET` | ATR(14) / profile median ATR < 0.7 and efficiency ratio < 0.3 |
| `RANGE` | 0.7–1.3 ATR ratio and efficiency ratio < 0.3 |
| `TREND` | Efficiency ratio ≥ 0.4 and ADX ≥ 25 |
| `VOLATILE` | ATR ratio > 1.6 or a `jump_flag` within the last 2 h |
| `UNKNOWN` | Insufficient data |

A Gaussian HMM is an optional later experiment (Q5). It is promoted only if it improves the L8 fit matrix out of
sample.

**Stability:** each metric stores the 90-day value, the 30-day value and a bootstrap CI. If the 30-day value lies
outside the 90-day CI, the metric is flagged `SHIFTING` and the UI says that the symbol's behavior is changing.

**Storage:** table `symbol_profiles` (server, symbol, version, computed_at, window_start, window_end,
data_hash, code_version, metrics JSON with value, CI, n and flags per metric, and regime_now). The newest
`keep_versions` (default 30) are kept. It replicates to the cloud.

**Uses.**

- (advisory) A **Character** tab on the PWA symbol page, with an explanation key per metric.
- (advisory) The ranking (§A25) gets an optional factor: costly hours and spread stress reduce suitability for
  the user's windows.
- (advisory) Alert windows (§A26) can exclude costly hours and news-blackout periods per symbol.
- (strategy, opt-in) A **volatility-aware SL/TP suggestion:** the stop distance is scaled by the hour-of-week
  volatility ratio. The risk sizer still sizes from the actual stop, so risk percent is unchanged, and the cage
  ceilings of §A9/§A33 apply.
- (engine, opt-in) **Profile gates**, for example disabling a mean-reversion strategy on a symbol labelled
  `TRENDING` with a CI excluding a random walk. Gates can only disable, never enable.

## L6. Signal-quality model (meta-labeling)

The idea follows López de Prado's meta-labeling: the existing strategies decide **side and plan**; the model only
estimates **how likely this particular signal is to work**, so it can rank, filter or explain it.

**Labels.**

- Primary: CLOSED `PLAN` shadow trades, with the existing definition (win = TP first; a time stop or stop-out
  is a loss; VOID skipped; §A27). LIVE and REPLAY sources are kept and flagged.
- Additional: **triple-barrier labels** produced by replay over long history for every entry signal (TP barrier,
  SL barrier and time barrier = the strategy's time stop). These are the same as PLAN shadow results by
  construction, so the replay path (`replay.py`) is reused rather than re-implemented.
- Optional secondary target: `r_net` (realized R after costs), for the economic evaluation only.

**Features** (all known at signal time):

- the existing `ev:` and `ctx:` features (§A29)
- profile features: regime, hour-of-week volatility ratio, spread ratio, trend/mean-reversion label, breakout
  follow-through rate, news proximity
- micro features at signal time (L4) when tick coverage exists, plus `has_ticks` as an explicit feature
- plan features: RR, stop distance / ATR, entry distance from signal price

**Model candidates**, all inside the existing `WinProbability` selection (`app/advisory/confidence.py`):

1. `BucketModel` (existing baseline)
2. `LogisticModel` (existing evidence model, extended with the profile features)
3. **Gradient-boosted trees** (`GbtModel`, LightGBM): shallow trees (depth ≤ 4, ≤ 200 rounds, strong L2,
   `min_data_in_leaf` ≥ 50), monotone constraints where a direction is known (for example, RR), and a small
   fixed hyperparameter grid (≤ 8 configurations; the number tried is recorded).

**Why LightGBM:** it handles nonlinear interactions on small tabular data and missing values natively, and models
serialize to a **text format** (`model_to_string`) that is stored in the database and loaded without pickle
(bandit-clean, no code execution on load). It is a new pinned dependency in `requirements/engine.txt` only.

**Validation** (`app/learning/evaluation.py`):

- **Purged walk-forward** with embargo: folds ordered by signal time; training rows whose label interval overlaps
  the test fold are purged; an embargo equal to the maximum trade lifetime (default 72 h) follows each test
  fold.
- **Probability metrics:** out-of-sample Brier score and log loss vs the current selected model. The new model
  wins only if it beats it on **both**, by the relative `min_brier_improvement` margin, as §A27 already
  requires.
- **Economic metric:** expectancy in R after costs of "take signals with p ≥ θ", where θ is chosen on the
  training folds and evaluated on the test folds. The model must not reduce OOS expectancy vs taking all
  signals, with a bootstrap 90% CI of the paired difference reported.
- **Minimum data:** ≥ 300 OOS-resolved trades in the scope (strategy × asset class, pooled fallback);
  otherwise the candidate is not eligible.
- **Overfitting guards:** the configuration count is recorded, the deflated Sharpe-style penalty is reported for
  the economic metric, live and replay results are reported separately, and an in-sample threshold explorer is
  marked in-sample.
- **Calibration:** isotonic regression fitted on OOS predictions of the training span (Platt scaling when n is
  small). The reliability diagram is stored with the version.

**Explanation:** Shapley values in probability space over the active features, reusing the existing attribution
machinery with a `predict_proba` callable. The UI explains the % exactly as it does today; new feature families
get explanation keys (`explain:learning.*`). If the GBT model is selected, explanations stay faithful because the
same Shapley procedure runs on its predictions.

## L7. Tick confirmation of entries

`app/engine/entry_confirmation.py`. The closed-bar signal rule (PLAN §A5) is unchanged. Confirmation can only
**delay or cancel** an entry, never create one or move its plan.

**State machine** per accepted entry decision (after risk checks, before the mode gate and execution):

```
PENDING ──(all conditions met)──▶ CONFIRMED ──▶ normal execution path (mode gate, ExecutionGateway)
   │
   ├─(spread_widening)──────────▶ keeps waiting (counts toward timeout)
   ├─(price moved > m × ATR from signal price in the plan direction)──▶ CANCELLED_CHASE
   ├─(price moved beyond the planned SL side)──────────────────────────▶ CANCELLED_INVALID
   ├─(quote_stall or jump_flag)────────────────────────────────────────▶ CANCELLED_MARKET
   └─(timeout T, default 3 min)────────────────────────────────────────▶ EXPIRED_TIMEOUT
```

**Confirm conditions** (all configurable):

- `tick_imbalance` over the last 60 s aligned with the side ≥ `min_imbalance` (default 0.1)
- `spread_ratio ≤ max_spread_ratio` (default 1.5)
- no `quote_stall` or `jump_flag`
- `range_position` not at the extreme against the entry (chasing guard)

**Safety and persistence.**

- Pending confirmations persist in a `pending_entries` table. **After a restart they expire** (fail closed) and
  are never resumed.
- The candle watermark still guarantees one evaluation per bar. A cancelled entry is final for that bar.
- Risk is re-checked at confirmation time against the then-current equity, exposure, breakers and kill switch.
  If anything changed, the normal risk path decides again.
- Every transition has a reason code (`MICRO_CONFIRMED`, `MICRO_CHASE`, `MICRO_INVALID`, `MICRO_MARKET`,
  `MICRO_TIMEOUT`) that is added to the backend enums and `frontend/src/i18n/` in the same change.
- Without tick coverage, confirmation either passes straight through (`on_no_ticks: immediate`) or cancels
  (`on_no_ticks: cancel`). The default is `immediate` in PAPER/DEMO and `cancel` in LIVE.

**A/B evaluation before enabling.** Shadow trades get a new variant `CONFIRMED` beside `PLAN` and `MANAGED`. It
uses the same opportunity, but the entry happens at confirmation time and price, or there is no trade if it was
cancelled. Statistics compare `PLAN` vs `CONFIRMED` on the same opportunities:

- paired difference in `r_net` per opportunity (a cancelled trade counts as 0 R), with a bootstrap 90% CI
- hit rate, expectancy and max drawdown of each, plus the share cancelled by reason
- an "avoided losers" vs "missed winners" breakdown

The confirmation is enabled for DEMO only when the paired difference CI lies above 0 over ≥ 200 opportunities,
and for LIVE only after a further DEMO period with the same result (L13).

**Latency measurement** (DEMO): record decision time, confirmation time, `order_send` start/end and the fill time
from the deal. Report the p50/p95 latency and the slippage vs the confirmation price. If the p95 latency exceeds
`max_latency_ms` (default 1500), confirmation results are flagged as unreliable.

## L8. Adaptive strategy selection (strategy × symbol × regime fit)

`app/learning/fit_matrix.py`. For each strategy × symbol × regime cell, compute expectancy in R after costs from
CLOSED PLAN shadow trades (LIVE and REPLAY separately). Cells shrink toward strategy × asset class × regime, then
strategy × regime, with the same empirical-Bayes pooling as `BucketModel`, so small cells do not swing.

- **Display:** a heat map on the PWA (hypothetical, labelled as such) with n and a credible interval per cell.
- **Gate (opt-in, config `learning.fit_gate`):** disable a strategy on a symbol in the current regime when the
  upper 90% credible bound of expectancy is below 0 and n ≥ `min_n` (default 40). It can only disable, never
  enable a strategy that config.yaml disabled. Gate changes are audited and shown with reason
  `FIT_GATE_NEGATIVE`.
- **Re-enable:** automatically when the bound recovers, since shadow trades keep accumulating for gated cells
  (they are still evaluated, just not traded).

## L9. Learning loop & model governance

**Schedule** (engine, worker thread, never in the trading loop):

| Job | When | Output |
|---|---|---|
| Micro-bar build | Every minute, for closed minutes | micro-bars |
| Profiles + regime | Nightly after `nightly_hour_utc` | `symbol_profiles` version |
| Fit matrix | Nightly after calibration | `fit_matrix` version |
| Dataset + model training | Weekly (`retrain_weekday`), or `app.cli learning train` | `ml_model_versions` CANDIDATE |
| Drift monitor | Hourly | drift metrics, possible demotion |

**Model lifecycle** (`ml_model_versions`: id, kind, scope, feature schema hash, training data hash, code
version, seed, hyperparameters, configurations tried, metrics JSON, reliability JSON, model text, status,
created_at, status history):

```
CANDIDATE ──(passes L6 validation)──▶ SHADOW ──(promote, CLI + reason, audited)──▶ ACTIVE ──▶ RETIRED
    │                                    │                                           │
    └─(fails)──▶ REJECTED                └─(fails live shadow check)──▶ REJECTED     └─(drift)──▶ SHADOW
```

- **SHADOW:** predictions are recorded per opportunity (`model_predictions`) but used nowhere. The minimum
  shadow period is `min_shadow_days` (14) **and** `min_shadow_trades` (100 resolved), and the live Brier must not
  be worse than the active model's by more than the margin.
- **ACTIVE:** at most one per scope. Promotion runs through
  `app.cli learning promote ID --reason "..."` only (a local CLI, like breaker reset), and it is written to the
  audit chain.
- **Drift:** population stability index (PSI) per feature vs training, plus rolling OOS Brier over the last N
  resolved trades vs the bucket baseline. If PSI > 0.25 on a top-5 feature, or the rolling Brier is worse than
  baseline by the margin over ≥ 50 trades, the model is **automatically demoted to SHADOW**. The demotion emits
  a `MODEL_DRIFT` notification and an audit entry, and the system falls back to the previous selection logic.
- **Reproducibility:** retraining with the same data hash, seed and code version must give an identical model
  text (tested).
- **Retention:** the newest 20 versions per scope plus every version that was ever ACTIVE.

## L10. Safety invariants (enforced by tests)

1. Learning components can only **veto, delay or explain**. They never create a signal, never increase size,
   never widen a stop beyond the plan's risk, and never bypass risk checks, breakers, the kill switch or the
   mode gates.
2. Position size always comes from the risk sizer (§A9/§A33). The volatility-aware stop suggestion changes the
   stop distance only, so risk percent stays the same.
3. **Unavailability:** when the active model or profile cannot be loaded or computed, behavior follows
   `on_unavailable`:
   - `baseline`: use the previous selection logic and no filter (default PAPER/DEMO)
   - `block`: skip new entries for the affected scope (default LIVE)

   Existing positions are never affected.
4. No pickle and no `eval` anywhere in `app/learning`. Models load from a text format and validate against the
   feature schema hash; a mismatch means "unavailable".
5. Each prediction used in a decision records the model version, feature values hash and output in the decision
   record (audit).
6. `app/learning` is read-only towards the broker (architecture test), and training is CPU-bounded: a nice level
   or thread cap (`max_train_threads`, default 2) protects the trading loop.

## L11. Cloud, API & PWA

- **Replicated tables** (engine-scoped like the rest, TAA-709): `symbol_profiles`, `micro_bar_daily`,
  `fit_matrix`, `ml_model_versions` (metadata and metrics only; the model text stays local),
  `model_predictions` (per opportunity), `pending_entries` outcomes.
- **API** (owned engines only, as in the other read APIs):
  - `GET /engines/{id}/symbols/{symbol}/profile` (latest and history)
  - `GET /engines/{id}/fit-matrix`
  - `GET /engines/{id}/models` and `.../models/{mid}` (metrics, reliability, status history)
  - `GET /engines/{id}/confirmation/stats` (A/B results)
- **PWA:**
  - Symbol page → **Character** tab: hour-of-week heat maps (volatility, spread, activity), the trend/mean-reversion
    summary with CI, breakout behavior, session character, news sensitivity, regime now, and stability flags.
  - **Learning** page: models (status, metrics, reliability diagram, drift), fit-matrix heat map, confirmation
    A/B results.
  - Opportunity detail: the model's % and explanation are shown through the existing explainable % UI. When a
    SHADOW model exists, its % is shown separately and labelled "under evaluation".
- **i18n:** every new code, status and explanation key goes into `frontend/src/i18n/` (th + en) in the same change.
  The catalogs test still rejects profitability language. Results are labelled "hypothetical" where they come
  from shadow trades.
- **Entitlements:** a `learning` feature flag in the plans structure (§A30), enabled for the owner and off
  elsewhere behind `SUBSCRIPTIONS_ENABLED=false`.

## L12. Role of the LLM (link to Phase 13)

The LLM (TAA-1301…1305) is used only for **narrative**: turning a profile or a model explanation into a short
TH/EN paragraph. Its input is the structured profile or explanation JSON, never raw prices for prediction. Its
output is labelled as AI narrative. It is not a feature of any model in this track, and its accuracy is not
claimed.

## L13. Evaluation protocol & acceptance criteria

| Component | May be shown in the PWA when | May influence DEMO trading when | May influence LIVE when |
|---|---|---|---|
| Symbol profile | Its metrics have n ≥ min_samples | Profile gate: the stability flag is not `SHIFTING` and the user opts in | Same + Phase 14 complete + explicit user go-ahead |
| Fit-matrix gate | Always (labelled hypothetical) | n ≥ 40 per gated cell, opt-in | Same + ≥ 4 weeks of DEMO with the gate on |
| Meta-label model | A SHADOW version exists | ACTIVE: L6 validation passed + shadow period passed | ACTIVE for ≥ 4 weeks in DEMO with no drift demotion |
| Tick confirmation | ≥ 50 A/B opportunities | Paired ΔR CI > 0 over ≥ 200 opportunities | Same result repeated over a further DEMO period, p95 latency within limit |

Every acceptance decision is recorded in `docs/HANDOFF.md` with the numbers. Reaching a criterion means
"allowed to be tried", not "expected to be profitable".

## L14. Configuration sketch (`config.yaml`, `extra="forbid"`)

```yaml
learning:
  enabled: false                 # master switch; everything below is inert when false
  ticks:
    enabled: true
    max_symbols: 20
    poll_seconds: 5
    backfill_days: 30
    raw_retention_days: 120
    max_gb: 20
  profile:
    window_days: 90
    stability_days: 30
    keep_versions: 30
    gates_enabled: false
  regime:
    method: rules                # rules | hmm (experimental)
  model:
    enabled: false
    candidates: [bucket, logistic, gbt]
    retrain_weekday: 6           # Sunday, market closed
    max_configs: 8
    min_oos_trades: 300
    min_shadow_days: 14
    min_shadow_trades: 100
    filter_mode: off             # off | advisory | filter
    filter_threshold: null       # chosen per scope from training folds when null
    on_unavailable: baseline     # baseline | block (forced to block in LIVE)
    max_train_threads: 2
  fit_gate:
    enabled: false
    min_n: 40
  confirmation:
    enabled: false
    timeout_seconds: 180
    min_imbalance: 0.1
    max_spread_ratio: 1.5
    chase_atr: 0.3
    on_no_ticks: immediate       # immediate | cancel (forced to cancel in LIVE)
    max_latency_ms: 1500
  drift:
    psi_threshold: 0.25
    rolling_trades: 50
```

Hard ceilings in code: `confirmation.timeout_seconds ≤ 600`, `max_symbols ≤ 60`, and `filter_mode` cannot be
`filter` while `model.enabled` is false.

## L15. Data model (new tables)

| Table | Scope | Key columns |
|---|---|---|
| `tick_watermarks` | engine | server, symbol, last_time_ms, ordinal |
| `tick_coverage` | engine | server, symbol, start, end, captured, quality counts |
| `micro_bar_daily` | replicated | server, symbol, date, n_ticks, spread stats, coverage |
| `symbol_profiles` | replicated | server, symbol, version, metrics JSON, regime_now, data_hash |
| `fit_matrix` | replicated | version, strategy, symbol, regime, n, expectancy, CI, gated |
| `ml_model_versions` | replicated (without model text) | id, kind, scope, status, metrics, schema hash |
| `model_predictions` | replicated | opportunity_id, model_id, p, explanation hash, used |
| `pending_entries` | engine (+ outcome replicated) | decision_id, state, reason, timestamps, prices |

Types stay portable (`UTCDateTime`, `JSONType`) and use one Alembic history, as PLAN §A18 requires.

## L16. Delivery phases & order

| Phase | Content | Why this order |
|---|---|---|
| L0 | Feed probe: DOM contents and tick-history depth on the real terminal | Settles the open facts of L1 before building on them |
| L1 | Tick data foundation (recorder, store, micro-bars, CLI) | Data takes calendar time to accumulate, so start earliest |
| L2 | Microstructure feature library + no-lookahead harness | Needed by L3–L5 |
| L3 | Symbol profile, regime, Character tab | Useful immediately, low risk, explainable |
| L4 | Meta-label model, evaluation, registry | Needs enough shadow/replay outcomes |
| L5 | Tick confirmation + A/B shadow variant + latency | Needs L1 data + L2 features + DEMO time |
| L6 | Fit matrix, drift, Learning page, runbook | Closes the loop |

**Placement against the main plan:** after Phase 14 and the wrap-up (the 2026-10-06 decision). **Exception:**
TAA-L001 (probe) and TAA-L101–L102 (tick capture) are small, read-only and independent. With the user's
agreement they may run earlier, so ticks start accumulating while other work continues.

## L17. Risks & limitations

- **Feed specificity:** FBS's quote stream is filtered. Tick features describe this feed, not the interbank
  market, and may change when FBS changes its feed or server.
- **Non-stationarity:** markets change. The 30-day stability check and drift demotion reduce, but do not remove,
  the risk of a profile or model that no longer fits.
- **Small samples:** one account produces few trades. Most cells stay `INSUFFICIENT_DATA` for a long time, and
  pooling plus replay priors help but bias toward the pooled average.
- **Replay vs live:** replay has no ticks and resolves SL/TP ties pessimistically. Models trained mostly on replay
  may differ live, so live and replay are always reported separately.
- **Selection bias:** gated or filtered signals still need shadow tracking, otherwise the system would never see
  their outcomes and could not recover. L8 and L6 keep shadow evaluation for everything.
- **Latency:** confirmation benefits may disappear at real execution latency. This is why there is a DEMO latency
  measurement before LIVE.
- **Compute:** profiles and training are CPU-heavy on the engine machine. Thread caps and off-hours scheduling
  (weekends) apply.
- **Storage:** raw ticks grow quickly; retention and the size cap are enforced.

## L18. Open questions for the user

1. Q1: May TAA-L001 (feed probe, read-only on the real demo terminal) and TAA-L101–L102 (tick recording) start
   before Phase 14 is finished, so data accumulates early?
2. Q2: Which symbols get ticks recorded first (default: watchlists + open positions, max 20)?
3. Q3: Is a new dependency (`lightgbm`, engine only) acceptable, or should L4 stay numpy-only (logistic + simple
   trees)?
4. Q4: Should deep learning or RL be revisited after L4 has ≥ 6 months of live shadow data?
5. Q5: Should the HMM regime experiment be in scope, or rules only?
6. Q6: Should the profile-based SL/TP suggestion be applied automatically in DEMO, or shown only?
