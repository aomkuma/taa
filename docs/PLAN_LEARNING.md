# TAA — Learning Layer: Symbol Character, Tick Microstructure & Signal Quality (Design)

> Separate design track, started 2026-10-06. It extends [PLAN.md](PLAN.md) and does not replace any part of it.
> Work items live in [TICKETS_LEARNING.md](TICKETS_LEARNING.md). The reasoning behind this design (the
> conversation of 2026-10-06) is kept in [LEARNING_DISCUSSION.md](LEARNING_DISCUSSION.md).
>
> **Numbering:** sections run `L0`–`L8`, `L19`–`L21`, then `L9`–`L18`. **Section numbers and ticket phases
> are different things:** "§L8" or a bare "L8" in running text is a section (the fit matrix), while
> "Phase L8" in TICKETS_LEARNING.md is a ticket group (playbooks). Tickets are `TAA-Lxyy`. References such as
> §A27 point to PLAN.md. No profitability claims anywhere: every model here can only estimate, filter
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

### L0.1 What already exists: reuse map (checked against PLAN.md, PATTERNS.md, HANDOFF.md and the code, 2026-10-06)

This track builds **on top of** the existing system and does not rebuild it. It reads existing outputs and plugs
in through the hook points of §L0.2. Before a ticket starts, re-check this table. Every ticket names the module
it reads.

| Planned here | Already exists | What is new |
|---|---|---|
| Hour-of-week activity (L5) | `LiquidityProfile` (median tick volume per hour of week from H1) and `hour_of_week` in `app/advisory/market_sessions.py`; ranking S4 "Liquidity now" | Add volatility and spread per hour of week, CIs and stability; share the profile with strategies, not only the ranking |
| Spread profile (L5) | Median and current spread in the ranking (S2, G4); `QuoteService` rolling median spread | Per hour of week, p95, rollover spikes, "costly hours" |
| Regime (L5 regime, L20.1) | `app/strategy/regime_detector.py` (TRENDING / RANGING / VOLATILE / UNCLEAR, ADX + ATR percentile); ranking S6 regime fit; style tag `regime` | A learning overlay (`app/learning/regime.py`) that reads the detector's output and adds profile-normalized inputs, efficiency ratio, `QUIET` and hysteresis. The existing detector and enum stay unchanged (§L0.2) |
| Correlation clusters (L5, L20.6) | `app/advisory/correlations.py` (rolling H1 return correlations, `max_correlation`); ranking S7; `risk.correlation_groups` | Clustering, plus cross-bot and same-currency dedup at selection time |
| Compression and breakout detectors (L19.4) | `volatility.bollinger_squeeze` (squeeze then breakout), `candle.inside_outside` (inside bar), `volatility.donchian`, `volatility.keltner`, `volatility.atr_expansion`, `sessions.asian_breakout`, `sessions.open_breakout`, `levels.sr_breakout` | Only NR4/NR7 and a **direction-neutral compression state** (ATR percentile, squeeze active *before* the breakout) as timing context; session/news timing context |
| Range triggers (L20.2) | `wyckoff.spring_upthrust` (range + false break), `levels.sr_zone` rejection, `chart.rectangle`, `smc.liquidity_sweep`, reversal candles | The qualified-range object and `setup_range_fade` that **uses these detectors as triggers** |
| Trend structure (L20.3/L20.4) | `structure.bos_choch`, `structure.dow`, `structure.trendline`, `trend.ma_alignment`, `momentum.divergence` | Runner trailing and exhaustion/transition policies that read them |
| Trailing and break-even (L20.3) | §A11 position management: break-even at +1R, ATR trailing after +1.5R, CLOSE when the H1 bias flips; §A31 `EntryPlan` `SAME_PRICE` staggered TPs and `SCALE_IN` | A runner part without a fixed TP, structure/chandelier trail, budget-capped adds |
| Timing diagnostics (L19.2) | Analytics recommendations (`app/analytics/recommendations.py`): `stop_too_tight` (SL exit followed by TP within N bars; TAA-1005 reads 20 bars after each SL exit), `earlier_break_even` (losers with MFE ≥ 1R), `cost_drag`; attribution codes `LOSS_IMMEDIATE_ADVERSE`, `LOSS_GAVE_BACK_PROFIT`, `COUNTER_TREND_ENTRY`, `LOSS_REGIME_SHIFT` | Classifying every trade into failure modes, the MAE profile of winners, time-to-target, entry efficiency and the random-walk baseline, in `app/learning/timing.py`. It imports the existing follow-up loader and attribution read-only |
| Expectancy report (L20.0) | Segment expectancy with a seeded bootstrap CI (`restrict_segments`, `bootstrap_mean_ci`), style tags, `app/advisory/stats.py` | The p/W/L/c decomposition per playbook/bot, and "which lever moved" |
| Win probability and explanations (L6) | `BucketModel`, `LogisticModel`, walk-forward selection, Shapley attribution (`app/advisory/confidence.py`, `calibration.py`) | The GBT candidate, purged CV with embargo, the economic metric, the model lifecycle |
| Tick data (L3, L4) | `copy_ticks_range` in the gateway (used by shadow resolution); `volume.tick_spike` from bar tick volume | Continuous capture, storage, micro-bars, quote-flow features |
| Manual-trade behavior (L20.7) | TAA-1006 matching of manual trades to signals; Trade history "me / signal / bot" in R | Behavior patterns (early exit, stop moved, revenge, overtrading, off-plan) |
| Scanning all symbols (L20.5) | Catalog and ranking over the whole broker universe (549 symbols on FBS demo); scanner on the monitored set (allowlist ∪ favourites ∪ lists ∪ auto top-30, cap 60, affordable only), with a per-cycle budget; evidence ≈ 1–1.6 s per symbol per bar; an engine cycle ≈ 7 s | Tiered scanning, rotation, and probably a **separate scan process** (HANDOFF homework item 6) so the trading loop never waits |
| Trading many symbols (L21.6) | Trading, candle streaming, charts and forming bars cover only `ALLOWED_SYMBOLS` (`.env` overrides `symbols.allowed`) | `trade_universe: catalog`, and chart data on demand for any symbol |
| Strategy flexibility (L21) | Strategies fixed in `config.yaml` (restart needed); detector parameters can come from the owner's theory settings (TAA-920) | Bot specs versioned and audited, changeable without a restart (remote edits can only lower risk) |
| AI proposing changes (L9) | Recommendations with "Backtest this change" (never auto-applied); calibration rebuilt nightly | The model lifecycle and drift demotion; proposals stay "backtest first, never auto-apply" |

### L0.2 Separation from the existing process (user decision 2026-10-06)

New work is **built separately** from the existing trading, advisory and analytics process. "Reuse" in L0.1
means *reading* what exists, not rewriting it.

**Rules.**

1. **New code lives in new modules:**
   - `app/learning/` (layer 9): profiles, regime overlay, timing, expectancy, models, playbooks, behavior
   - `app/squad/` (layer 10, beside `app.engine`): bots, commander, allocation
   - `app/market_data/tick_*.py` and `micro_bars.py` (layer 4)
   - `app/indicators/microstructure.py` (layer 5)

   New evidence detectors and setups are new files registered through the existing plugin registries
   (`app/evidence/registry.py`, `app/strategy/catalog.py`). They do not edit existing detectors or setups.
2. **Existing modules are read, not rewritten.** For example:
   - The learning regime (`app/learning/regime.py`) takes `regime_detector` output plus profile inputs and
     produces its own overlay. `regime_detector.py` and the `Regime` enum stay as they are.
   - Timing diagnostics import the analytics loaders and attribution read-only.
   - The profile reads `LiquidityProfile` and correlations.
3. **The only changes to existing code are hook points**, each a small protocol defined in the lower layer and
   injected by the orchestrator, with a pass-through default:

   | Hook | Defined in | Default (= today) | Implemented by |
   |---|---|---|---|
   | H1 `CandidateFilter`: after strategy evaluation and arbitration, before the decision engine | `app/engine` | Pass everything through | Router (L20.1), model filter (L6), commander (L21) |
   | H2 `EntryPlacer`: how an accepted entry is placed | `app/engine` | Market order now | Confirmation (L7), pullback limit / LTF trigger (L19.7) |
   | H3 `ExitPolicy`: position management rules | `app/engine` | The §A11 rules | Runner, transitions (L20.3–L20.4), learned time stop |
   | H4 Shadow variant registry | `app/advisory/shadow.py` | `PLAN`, `MANAGED` | `CONFIRMED`, `PULLBACK`, `RUNNER`, … |
   | H5 Context enrichment (extra `ctx:` features) | `app/advisory/confidence.py` | None | Profile, regime, timing, micro features |
   | H6 Magic registry | `app/engine` | — (replaces the index mapping; a fix, see TAA-L901) | — |
   | H7 Orchestrator wiring behind `learning.enabled` / `squad.enabled` | `app/engine/orchestrator.py` | Off | — |
   | H8 New replicated tables (migrations, outbox mapping) | `app/storage`, `app/sync` | — | Each ticket |

   Each hook ships with a **golden test**: with the new flags off, decisions, sizes, shadow rows and backtest
   results equal the pre-hook results.
4. **The architecture test keeps it honest:** `app.learning` and `app.squad` get `LAYERS` entries. Lower layers
   never import them; they only see the hook protocols.
5. **Turning it off is always possible:** `learning.enabled: false` and `squad.enabled: false` return the
   engine to today's process. This also holds after the track is complete.
6. **Hook protocols are structural** (`typing.Protocol`). `app.learning` (layer 9) implements them **without
   importing** `app.engine` (layer 10); the orchestrator wires the implementations and mypy checks them
   there. `app.squad` (layer 10) may import `app.engine` directly.
7. **One code path for live, shadow, replay and backtest:** the backtester (§A17) and advisory replay (§A27)
   call the same hooks (H1–H4) as the engine, so a rule is evaluated identically everywhere. A hook that
   cannot run in backtest (for example, tick confirmation without recorded ticks) fails closed there, as
   §L4 describes.
8. **Existing reviewers keep their place:** the optional AI review of entries (Phase 13,
   `DecisionEngine.reviewer`) runs inside the decision engine, after H1, and is not affected by this track.
9. **Built once, by its first user:** each hook is added by the ticket that first needs it, on top of the
   golden harness of TAA-L002 (`tests/golden/`: backtest trades, replay shadow trades, PAPER engine decisions
   and positions; regenerated only on purpose with `TAA_UPDATE_GOLDEN=1`, diff reviewed).

## L1. Data reality: what FBS × MT5 actually provides

| Data | What it really is | Consequence |
|---|---|---|
| `copy_ticks_*` (`time_msc`, `bid`, `ask`, `last`, `volume`, `flags`) | The broker's quote stream. **Measured:** `last` and `volume` are 0 on 100% of ticks for all five probed symbols. FX/metals/indices ticks carry flag 96 (BUY+SELL) plus 2/4 for a bid/ask change; **about 58% of EURUSD ticks change neither bid nor ask** (flag 96 alone). Rates in the Asian session: EURUSD ~86/min, GBPUSD ~95, XAUUSD ~166, US30 ~38, BTCUSD ~40 | Microstructure means **quote dynamics**, not trades. Tick counts and imbalance must use only ticks with a bid or ask change (flags 2/4), or quote activity is overstated |
| Bar `tick_volume` | The number of quote updates in the bar | An activity proxy, not traded volume |
| Bar `real_volume` | 0 for FX/CFD on FBS | Unusable |
| `market_book_*` (DOM) | **Measured 2026-10-06 (TAA-L001): unavailable.** `market_book_add` is refused for EURUSD, GBPUSD, XAUUSD, US30 and BTCUSD on FBS-Demo | `book_imbalance` (L4) stays off. No feature depends on a book |
| Tick history depth | **Measured 2026-10-06:** XAUUSD served back to at least 2025-10 (≥ 12 months); EURUSD/GBPUSD ≥ 62 days in a capped search. Every month touched is downloaded whole into the terminal's `Bases/<server>/ticks` (~40–60 MB per month for XAUUSD/BTCUSD), and a month missing from the cache can come back empty on the first query | A 30–90-day backfill is feasible; deeper history costs disk. Still **record ticks ourselves** (L3), with the size cap |
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
- **Volatility compression (L19.4).** The idea that contraction is followed by expansion (Crabel's NR4/NR7 and
  inside days; the Bollinger-inside-Keltner squeeze) rests on volatility clustering. Every source agrees that
  compression is **direction-neutral**: it says a larger move is more likely soon, not which way. The direction
  must come from elsewhere.
- **First passage (L19.2, L19.6).** For a driftless random walk with barriers +a and −b, P(+a first) = b/(a+b)
  and the expected exit time is a·b/σ². The first-passage hazard is non-monotone: it rises, peaks near the most
  likely crossing time and then flattens. This gives a principled **null model** for "how often noise alone
  hits this stop" and "how long a move should take". It also motivates a hazard model with censoring rather
  than a plain classifier for timing.
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
  EntryConfirmation (hook H2)  symbol_profiles (versioned) ──▶ ModelTrainer (off-loop)
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
| `app/learning/` (new package) | 9 (with advisory/analytics) | profile, regime overlay, timing, expectancy, dataset, models, registry, drift, fit matrix, playbooks, behavior, entry confirmation (state machine, wired through H2) |
| `app/squad/` (new package) | 10 (beside `app.engine`) | bots, commander (H1), allocation, magic registry use |
| `app/evidence/timing.py` | 5 (evidence) | New direction-neutral timing detectors (§L19.4), registered in the existing registry |
| `app/strategy/setups_range.py` | 6 (strategy) | `setup_range_fade` (§L20.2), registered in the existing catalog |
| Hook protocols H1–H3 | in `app/engine` (structural) | §L0.2; defaults reproduce today's behavior |

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
| ~~`book_imbalance`~~ | — | Dropped: TAA-L001 found no depth of market on FBS (2026-10-06) |

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

**Data budget:** profiles need M5…D1 history (M1 for the hour-of-week ranges). For the whole catalog
(hundreds of symbols) this means download time and disk space. Profiles are built for traded, watchlist and
tier-1 symbols first and rotate through the rest, through the existing history download (`app/market_data/
history_download.py`) with a per-night budget.

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

**Regime overlay** (`app/learning/regime.py`). It reads the output of `app/strategy/regime_detector.py`, which
stays unchanged (§L0.2), and adds profile-normalized inputs on the entry TF. It is rule-based first, for
explainability:

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

`app/learning/entry_confirmation.py`, wired through hook H2 (§L0.2). The closed-bar signal rule (PLAN §A5) is
unchanged. Confirmation can only
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

## L19. Entry timing: right direction, wrong time (added 2026-10-06)

Section numbers run L0–L8, then L19–L21, then L9–L18. L19 sits here because it builds on L5–L8 and feeds L9.

**Problem (user, 2026-10-06):** traders often read the direction correctly and still lose, because the move
comes later than their position can survive. This section treats timing as a **separate, measurable problem**
next to direction.

### L19.1 Failure modes

| Code | Mode | What happens | Typical cause |
|---|---|---|---|
| `EARLY` | Too early | SL hit first, then price reaches the original TP | Stop inside the symbol's normal noise for that hour; entry before any trigger |
| `LATE` | Too late (chase) | Entry after the move ran; a normal pullback hits the SL | No wait for a pullback; the effective RR is worse than planned |
| `STALL` | Not yet | Price goes sideways until the time stop, a manual close or swap costs | Entry in a quiet session or in the wrong regime |
| `TF_MISMATCH` | Wrong timeframe | The HTF direction is right, but the entry TF is still against it | Direction and timing judged on the same TF |
| `WRONG` | Wrong direction | The TP is never reached within the look-ahead | Not a timing problem |

### L19.2 Timing diagnostics (`app/learning/timing.py`)

The diagnostics live in `app/learning/timing.py`. They read the analytics recommendations
(`stop_too_tight`, `earlier_break_even`), the attribution codes and the after-exit bar loader, and change none of
them (§L0.1, §L0.2). They run on CLOSED shadow trades (PLAN
variant) and on matched manual trades (TAA-1006). They need only
the candles that are already stored, no ticks. For every trade, the path is followed **after the exit** for a
look-ahead `H` (default = the strategy's time stop, 72 h) using M1/M5 bars:

- **`vindicated_stop`:** the SL was hit, and later, within H, price reached the original TP before going a
  further 1R beyond the SL. A trade is classified `EARLY` when this is true.
- **MAE profile of winners:** the distribution of how far winners went against the entry, in R and in ATR, before
  reaching the TP. Its quantiles define the natural "breathing room" of a symbol × strategy.
- **Time to target:** the distribution of bars from entry to TP (winners) and to +0.5R / +1R (all trades).
- **Pre-entry run (chase):** how far price ran in the trade's direction over the `pre_bars` (10) entry-TF bars
  before the entry, in ATR. A stopped-out trade after a run of ≥ `late_run_atr` (1.5) ATR is `LATE`. (TAA-L701
  decision: this replaced an "entry efficiency within the next N bars" measure, which looks at bars after the
  entry and mixes chasing with ordinary adverse moves.)
- **TF agreement:** `TF_MISMATCH` when the HTF trend was on the trade's side at entry **and** at the exit, while
  the entry TF closed on the far side of its `pre_trend_bars` (50) mean against the trade. A pullback entry also
  sits against its short-term move by design, so the 50-bar mean is used rather than the last few bars.
- **Precedence** for a stopped-out loser: `EARLY` → `LATE` → `TF_MISMATCH` → `WRONG` (not vindicated) →
  `UNKNOWN`. Time stops and flat manual/signal closes are `STALL`; other losing exits are `OTHER`.
- **Random-walk baseline (first passage):** for a driftless walk with volatility σ (from ATR at entry in Wave 1,
  and from the §L5 hour-of-week profile once it exists) and barriers +a (TP) and −b (SL), P(TP first) = b / (a + b), and the expected exit time is a·b / σ².
  The diagnostics report the observed vindicated-stop rate and time to target **next to** this baseline. Only
  the difference counts as evidence: a stop that a pure random walk would hit 60% of the time is a stop-placement
  problem, not bad luck.

**Outputs** (TAA-L701/L801/L808 decision: computed on request in the cloud from the replicas, like the analytics of
TAA-1005, through `GET /engines/{id}/learning/timing|expectancy|behavior` and the PWA **Learning** page; the
cloud follow-up uses 24 h of stored bars per trade and at most the 200 most recent trades; no table until the load
needs one): per symbol × strategy × session, the share of each failure mode with
a Wilson CI, the MAE quantiles of winners, the time-to-target quantiles, the baseline comparison, and n. Manual
trades get the same report in the analytics page ("your losses that were right too early").

### L19.3 Entry-mode variants (shadow A/B)

Each opportunity is simulated under several entry modes at once, as extra shadow variants beside `PLAN`,
`MANAGED` and `CONFIRMED` (L7). They always use the same plan direction, the same risk budget and the same TP
**price**:

| Variant | Entry rule | Main trade-off |
|---|---|---|
| `PLAN` (existing) | At the signal, at market | Baseline |
| `PULLBACK` | A limit at the learned pullback depth: the winners' MAE quantile q (default q50) of this symbol × strategy, at least 0.2 ATR; expires at the signal lifetime | Misses trades that never pull back |
| `LTF_TRIGGER` | Waits for a lower-TF trigger in the plan direction: a break of the last swing on the trigger TF (entry TF ÷ 3–4, e.g. M15 → M5 or M1); expires at the signal lifetime | Worse price, fewer whipsaws |
| `CONFIRMED` (L7) | Tick confirmation | Minute-level only; needs ticks |
| `WIDE_STOP` | `PLAN` entry with the SL at max(structure stop, winners' MAE q80 + spread), and the lot recomputed so risk percent is unchanged | Smaller lot; fewer `EARLY` stop-outs |

**Rules.**

- The SL stays at the plan's structure level unless the variant says otherwise. A better entry therefore raises
  the effective RR, and a variant may not move the TP.
- Sizing always goes through the risk sizer. No variant increases money at risk.
- Learned depths and quantiles come from profile/diagnostics versions **valid at signal time** (point in time).
- **Entry window vs signal expiry:** today a trading signal expires after `strategies.signal_expiry_bars`
  (1 entry bar), while advisory windows default to 2 bars. Waiting modes (`PULLBACK`, `LTF_TRIGGER`,
  `CONFIRMED`) get their own `entry_window_bars` per mode (default 2, ceiling 6). The existing expiry stays
  unchanged for `PLAN`. While waiting, the setup's invalidation is re-checked on every closed trigger-TF bar,
  and an invalidated setup cancels the pending entry (`ENTRY_SETUP_INVALID`).
- **Compute budget:** variants are resolved in batch on M1 bars for tier-1 opportunities only (§L20.5), with
  the same per-cycle budget as the scanner, so more variants never slow the trading loop.
- Statistics: the paired ΔR per opportunity against `PLAN` (a missed entry = 0 R) with a bootstrap 90% CI, the
  fill rate, avoided losers vs missed winners, and the failure-mode mix before and after.

### L19.4 Timing features and detectors

Squeeze breakouts, inside bars, Donchian, opening-range and Asian-range breakouts already exist as detectors
(L0.1) and stay unchanged. New are the **direction-neutral timing states**, shown as timing evidence and never
as direction, in a new file `app/evidence/timing.py`:

- **Volatility compression:** the ATR percentile over the last 100 bars < 20; Bollinger Bands inside Keltner
  Channels (squeeze); NR4/NR7 and inside bars (Crabel). Compression says that **an expansion is more likely
  soon** and is direction-neutral. The direction must come from the HTF and the strategy.
- **Session timing:** minutes until the next high-activity hour from the L5 profile (London or New York open);
  "dead hour" when the profile's activity is in the bottom quartile.
- **News timing:** minutes to the next high-impact event for the symbol's currencies (`app/news`).
- **Expected-time context:** time to target q50/q75 for this symbol × strategy (from L19.2), as a `ctx:` feature.

### L19.5 Learned time stop and one re-entry (shadow first)

- **Variant `TIME_STOP_LEARNED`:** exit at market when the trade has not reached +0.5R by the time-to-+0.5R q75 of
  its symbol × strategy (min 4 bars, max the configured time stop). The idea is to cut `STALL` trades at a small
  loss instead of a full SL.
- **Variant `REENTRY_1`:** after a SL hit, **one** re-entry with the same plan is allowed only when all of these
  hold:
  - the HTF structure is intact (the invalidation level of the setup was not broken)
  - the signal lifetime has not expired, and a new `LTF_TRIGGER` or `CONFIRMED` entry appears
  - **the total risk of the idea, including the first loss, stays within the original per-signal budget**. The
    re-entry is sized from what is left of the budget, and is skipped when it is below `volume_min`.

  A re-entry belongs to the **same signal and idea** (same `signal_id`, a new part number). It is not a new
  signal, so the arbitration cooldown (`strategies.cooldown_bars`) for new signals stays unchanged.
  Re-entries are labelled as such everywhere, count toward the daily loss limit and the breakers, and are
  disabled after a daily loss or breaker event. The point is to rescue the `EARLY` mode without becoming revenge
  trading.

### L19.6 Time-to-move model (extends L6)

L6 estimates P(TP before SL). Timing needs a **when** as well:

- **Target:** the first passage of +1R vs −1R (and of TP vs SL), with the exit time as a duration. Trades still
  open at the look-ahead end are censored, not dropped.
- **Models:**
  1. a discrete-time hazard model: logistic regression on (trade, bar-since-entry) rows, with time features
     plus the L6 features
  2. a LightGBM version under the same validation
  3. baseline: the empirical Kaplan–Meier curve per symbol × strategy and the random-walk first-passage curve

  The same purged walk-forward, calibration and lifecycle as L6 and L9 apply.
- **Output in alerts:** "similar setups reached the target in roughly 4–12 h (middle half) in the past" with n.
  It is explicitly historical and hypothetical, not a promise. It is shown only when n ≥ `min_n` and the
  model beats the Kaplan–Meier baseline out of sample (integrated Brier score).
- **Uses:**
  - the user sets realistic expectations and avoids premature manual closes
  - `TIME_STOP_LEARNED` can use the predicted q75 instead of the group q75
  - holding style (§A31 scalp/day/swing) filters signals whose expected time does not fit

### L19.7 Selection and enabling

- A variant can become the **default entry mode** for a symbol × strategy only when its paired ΔR CI against
  `PLAN` lies above 0 with n ≥ 200 opportunities in live shadow. Replay results are reported separately and do
  not count toward this threshold.
- The selection is per symbol × strategy (pooled to asset class when small) and stored in a versioned
  `entry_mode_policy`. It is shown in the PWA with the evidence. The user can override it per strategy; the
  override can only choose among variants, it cannot change risk.
- In DEMO and LIVE, the chosen mode only changes **how** the entry is placed (market vs limit vs waiting for a
  trigger). Risk checks, the mode gate and execution are unchanged. A limit order placed by `PULLBACK` gets the
  signal lifetime as its expiry and is cancelled on kill switch or breaker events like any pending order.
- `REENTRY_1` and `TIME_STOP_LEARNED` follow the same rule, and they also stay off in LIVE until a further DEMO
  period confirms them (L13).

## L20. Regime playbooks: closing the human gaps (added 2026-10-06)

**Purpose (user, 2026-10-06):** the system exists to close the weaknesses of a human trader:

- emotions (fear, greed, FOMO, revenge trading)
- a bias toward one style (trend or sideways)
- comfort with only a few assets

It should take every qualifying opportunity with sniper entries, ride a trend when the larger picture trends,
and trade ranges when the market is sideways. **Profit cannot be predicted. The goal is to make each trade's
expected value as favorable as the evidence allows, and to measure it honestly.**

### L20.0 Guiding principle: the expectancy decomposition

Per trade, in R after costs: **E[R] = p · W − (1 − p) · L − c**. The **growth of the account** also depends on how
many independent opportunities are taken (n), and on surviving drawdowns. Every component of this track maps to
one lever, and progress is judged on these process metrics (with CIs), never on single-trade outcomes:

| Lever | Meaning | Components |
|---|---|---|
| p ↑ | Take better signals | L4 signal quality, L8 fit matrix, L20.1 playbook router |
| W ↑ | Let winners run when the trend allows | L20.3 trend runner, L20.4 transitions |
| L ↓ | Lose less on the losers: fewer full stop-outs, stops outside noise | L19 timing, L7 confirmation, learned time stop |
| c ↓ | Pay less in spread, commission and swap | L3 spread profile (costly hours), L4 `spread_ratio` |
| n ↑ | More independent opportunities | L20.5 tiered scanning of all symbols, L20.2 range playbook |
| Survival | Never risk ruin | §A9/§A33 sizing and ceilings, breakers, heat, L20.6 correlation-aware selection |
| Discipline | The plan is followed | L20.7 behavior report on manual trades |

**Expectancy report** (`app/learning/expectancy.py`): per playbook × symbol × strategy, from CLOSED shadow
trades (LIVE and REPLAY separate), it shows p, W, L, c, the resulting E[R] with a bootstrap CI, the
opportunity rate, and which lever moved since the previous version. It is labelled hypothetical, and it is the
first screen to read when deciding what to change.

### L20.1 Playbook router

`app/learning/playbooks.py`. The HTF regime chooses the playbook, and the entry TF executes it:

| Playbook | HTF condition (defaults, profile-normalized where possible) | Allowed strategy families |
|---|---|---|
| `TREND_RUNNER` | Regime `TREND` (`regime_detector` TRENDING and L3 `TREND`), HTF trend direction set | Pullback, continuation, breakout in the trend direction |
| `RANGE` | Regime `RANGE` with a qualified range (L20.2) | Range fade |
| `BREAKOUT` | Compression active (L19.4) and the range edge broken on a closed HTF bar | Breakout, retest |
| `STAND_ASIDE` | `VOLATILE`, `UNCLEAR`, `QUIET` with costly hours, news blackout, spread stress or insufficient data | None |

**Rules.**

- **Hysteresis:** a regime change takes effect only after it has held for `switch_bars` (default 2) closed HTF bars,
  so the router does not flip on noise.
- Each strategy and setup declares its playbooks (`playbooks: [...]` in config). The router **only disables**
  strategies that do not fit the current playbook; it never enables one that config.yaml disabled.
- The L8 fit matrix decides per symbol whether a playbook is allowed there. A playbook without a credible edge
  on a symbol is not used on it, so the system does not trade a style where it shows no edge.
- Decisions carry reason codes (`PLAYBOOK_TREND`, `PLAYBOOK_RANGE`, `PLAYBOOK_BREAKOUT`, `PLAYBOOK_STAND_ASIDE`,
  `PLAYBOOK_MISMATCH`) shown in alerts and the PWA.

### L20.2 Range playbook

The existing setups are mostly breakout, pullback and reversal. A dedicated range fade is added
(`setup_range_fade`, starting with `DEMO_UNPROVEN` like the other setups).

- **Qualified range** (HTF):
  - ADX below `range_adx` and efficiency ratio < 0.3 over the range
  - at least 2 touches at each edge
  - a width of at least `min_width_atr` (default 2) HTF ATR, and the distance from the edge to the middle at least
    4× the round-trip cost
  - no active compression (L19.4: a squeeze inside a range means a breakout is likely, so the playbook becomes
    `BREAKOUT` watch)
- **Entry:** inside the outer `edge_zone` (default 20%) of the range, after an LTF rejection trigger (reversal
  candle, failed break, `tick_imbalance` turning; L19.3 `LTF_TRIGGER`).
- **Stop:** beyond the edge by max(`stop_buffer_atr`, the winners' MAE q80 from L19.2), so it sits outside the
  normal noise.
- **Targets:** TP1 at the middle of the range, TP2 at the opposite edge zone (`SAME_PRICE` split, §A31).
- **Exits:** a closed HTF bar outside the range → exit at market (`RANGE_BROKEN`), and a short time stop
  (learned, L19.5).

### L20.3 Trend runner and risk-free adds

- **Entry:** a pullback in the HTF trend direction with sniper timing (L19 `PULLBACK` or `LTF_TRIGGER`, L7
  confirmation).
- **Split position** (separate positions, `SAME_PRICE` mode of §A31):
  - part A (default 50%) takes profit at `runner_tp1_r` (default 1.5R)
  - part B is the **runner**, with no fixed TP
- **Runner trailing:** the stop trails behind the more conservative (closer to price) of:
  - the last confirmed HTF swing low/high minus a buffer (structure trail)
  - a chandelier stop of `k × ATR(HTF)` from the extreme since entry (default k = 3)

  After TP1 the stop is at least at break-even plus costs. The SL only moves in the favorable direction (§A11
  invariant).
- **Runner exit:** the trailing stop, an HTF change of character against the trend (`structure.bos_choch`), the
  regime leaving `TREND` for `switch_bars`, the kill switch or a breaker. Swap is accrued and shown, because
  runners hold longer.
- **Risk-free adds (pyramiding), opt-in:** at most `max_adds` (default 2) adds in the trend direction, each on a
  fresh pullback trigger. An add is allowed only when the stops of the existing parts already lock in at least
  the add's risk. The **total open risk of the idea never exceeds the initial per-signal budget**
  (property-tested). Adds count toward portfolio heat, and they are disabled after a daily-loss or breaker
  event.
- **Position limits:** the parts of one idea (part A, the runner, adds, a re-entry) are separate broker
  positions. Today's `max_positions_per_symbol: 1` and `max_open_positions` count positions, so they would
  block the second part. Under the learning flags, these limits count **ideas** (one signal = one idea),
  while risk always counts the sum of all parts. The cage values do not change, and with the flags off the
  existing per-position counting stays (golden test).
- **Evaluation:** shadow variants `RUNNER` and `RUNNER_ADDS` beside `PLAN` and `MANAGED`, with the paired ΔR,
  W and L shifts (L20.0) and max drawdown compared. A runner usually lowers the hit rate and raises W, and the
  report shows both.

### L20.4 Regime transitions and open positions

All transition policies are defined in advance per playbook and evaluated in shadow. Nothing changes on the
fly from a model:

| Open trade | Transition | Policy |
|---|---|---|
| Range fade | The range breaks against the trade | Exit (`RANGE_BROKEN`) |
| Range fade | The range breaks in the trade's direction | Variant `RANGE_TO_RUNNER`: part B converts to the runner rules (L20.3) instead of exiting at the opposite edge. Shadow first |
| Trend runner | Exhaustion: a failed higher high/lower low, momentum divergence, or the regime going to `RANGE` | Tighten the trail to the nearest LTF swing (`TREND_EXHAUSTION`) |
| Trend runner | HTF change of character against it | Exit (`TREND_ENDED`) |
| Any | `VOLATILE` or news blackout begins | No new entries; existing stops are kept, never widened |

### L20.5 Tiered scanning of all symbols

To take opportunities across the whole FBS universe (hundreds of symbols) without running the full evidence
engine (about 1 s per bar per symbol) everywhere:

- **Tier 0, every entry-TF close, all tradable symbols.** It runs indicators only: session open, spread ok vs the
  profile, ATR state, regime, compression, distance to range edges and HTF swing levels. Cost: milliseconds per
  symbol.
- **Tier 1, the full evidence and strategy pipeline,** for:
  - symbols with open positions, plus watchlist symbols
  - the top `tier1_max` (default 30) of a tier-0 interest score (playbook not `STAND_ASIDE`, price near an
    actionable zone, compression, fit-matrix edge)
- **Rotation:** every tradable symbol gets a tier-1 pass at least every `rotation_bars` bars, so a tier-0 blind
  spot cannot hide one forever.
- **Budget:** a CPU time budget per cycle with metrics (scan latency, symbols per tier, skipped). If the budget is
  exceeded, the lowest-interest symbols are dropped from tier 1 and counted.

### L20.6 Opportunity selection under heat and correlation

When more signals qualify than the heat and position limits allow (for example, broad USD weakness):

- **Rank** by expected R per unit of risk from the selected model (L4/L20.0, cost included), then by setup
  strength.
- **Deduplicate correlated exposure:** at most `max_per_cluster_direction` (default 1) per correlation cluster
  (L5) and direction, where exposure in the same currency counts as the same bet.
- Rejected signals keep shadow tracking with reason `HEAT_RANKED_OUT` or `CORRELATED_DUPLICATE`, so the
  selection rule itself can be evaluated.
- It runs after the existing arbitration (`app/strategy/arbitration.py`, unchanged), through hook H1.

### L20.7 Behavior report on manual trades

The owner also trades by hand. From the manual trades and their matched signals (TAA-1006), the analytics show
patterns that are typical human weaknesses. The text is descriptive and non-judgmental, and the values are
hypothetical comparisons, not promises:

| Pattern | Detection |
|---|---|
| Early exit of winners | Closed in profit before TP while the plan was intact, and price later reached the TP |
| Stop moved away | The SL was widened or removed after entry |
| Revenge trade | A new trade within `revenge_minutes` (default 30) after a loss, or with a larger risk than the previous one |
| Overtrading | Trades per day above the profile's `max signals per day`, or after the daily loss limit |
| Off-plan trade | A manual trade without a matching signal, or against the current playbook |
| Comfort-zone bias | The share of trades by playbook and asset class vs where the opportunities were |

Each pattern gets its count, its share, and the hypothetical difference in R between "as traded" and "as
planned". The point is to show where the system's discipline would have helped, not to grade the user.

### L20.8 Safety

- The router, playbooks, transitions and selection can only **choose among predefined, shadow-evaluated
  rules** or **disable** trading. None of them creates risk beyond the per-signal budget, widens a stop, or
  bypasses risk, mode gates, breakers or the kill switch.
- Runner and adds: the total idea risk is always ≤ the initial budget, and the SL only moves favorably.
- Each new playbook rule follows L13: shadow first, then DEMO with the acceptance numbers, and LIVE only after
  Phase 14 and the user's explicit go-ahead.

## L21. Squad mode: a team of specialist bots (added 2026-10-06)

**Vision (user, 2026-10-06):** the system works like a squad of skilled traders on the board. Each bot has its
own specialty and sees different opportunities, and together they collect many small edges. The existing
single-engine way of working must keep working unchanged.

### L21.1 What the current structure can and cannot do

Checked in the code on 2026-10-06:

| Area | Today | Gap for squad mode |
|---|---|---|
| Strategies | One `StrategySet` from `strategies.items`. All strategies share one timeframe pair (`timeframes.higher`/`entry`, H1/M15) | Each bot needs its own timeframes, symbols, sessions and playbooks |
| Risk | One `risk` cage plus the owner's profile (§A33), applied to the whole engine (`max_open_positions: 3`, `max_positions_per_symbol: 1`) | Each bot needs its own budget inside the account cage, and its own probation and breakers |
| Arbitration | Per symbol and bar: BUY vs SELL cancels both (`CONFLICT`); same direction → best rank wins | Cross-bot rules: different horizons may disagree, so a commander decides by policy |
| Magic numbers | `MAGIC_NUMBER_BASE + index` of the **enabled** strategies (`app/engine/orchestrator.py`) | **Fragile today, not only for squads.** Enabling, disabling or reordering a strategy while positions are open re-maps those positions to another strategy's management rules. A stable, persisted mapping is needed (TAA-L901) |
| Universe | `symbol_catalog` discovers every symbol (`include: ["*"]`), and the ranking covers all of them. The scanner evaluates strategies only on the monitored set (cap 60) | Q10 answer: scan everything tradable. Tiered scanning (L20.5, TAA-L806) removes the cap for tier 0 |
| What is traded | Only `symbols.allowed` (4 symbols) | A per-bot symbol scope, inside an account-level trading universe that can be the whole tradable catalog (L21.6) |
| Account type | Hedging is detected (`margin_mode`), and FakeMT5 defaults to retail hedging | Squad policies must also handle netting accounts (L21.4) |

### L21.2 Concepts

- **Bot** (`BotSpec`, one per specialty): a stable `bot_id` and display name, plus:
  - playbooks (L20) and strategies/setups
  - timeframes (bias TF, entry TF, optional trigger TF)
  - symbol scope (asset classes, include/exclude patterns, or "the universe")
  - session windows
  - entry/exit style (entry-mode policy L19, runner or fixed TP L20.3, time stop)
  - a **risk budget share**
  - a status (`SHADOW` / `PAPER` / `ACTIVE` / `PAUSED` / `RETIRED`)

  Bots are configured locally in `config.yaml` (`squad.bots`), because they carry risk.
  - **Sessions and weekends:** today `sessions` and `friday_cutoff_utc` apply engine-wide, which would stop
    `crypto_247` at the weekend. A bot may declare its own sessions and weekend rule only for its own scope
    (for example, crypto). News blackouts and the account breakers still apply to every bot.
- **Commander** (`app/squad/commander.py`, plugged in through hook H1): the single place that sees every bot's candidates for a decision
  cycle. It:
  - applies cross-bot conflict and correlation rules (L21.4)
  - ranks candidates by expected R per unit of risk (L20.6)
  - allocates the account's open-risk headroom among bots (L21.5)
  - hands the selected decisions to the unchanged decision engine → risk → mode gate → execution path

  It never sizes above the cage and never bypasses breakers or the kill switch.
- **Shared intelligence (compute once):** candles, indicators, evidence, profiles (L5), regime and playbook state
  (L20.1) and micro features (L4) are computed once per symbol × TF × bar and shared by every bot that needs
  them. Bots only add their own strategy logic. This extends the PLAN §A30 principle and keeps CPU proportional
  to symbols × TFs, not symbols × bots.
- **Legacy mode** = squad mode with exactly one implicit bot, `default`, built from today's `strategies`,
  `timeframes`, `symbols.allowed` and `risk`. `squad.enabled: false` (default) gives today's behavior
  bit-for-bit: the same decisions, sizes and backtest results (golden test).

### L21.3 Starting roster (proposal; each bot proves itself before it trades)

| Bot | Specialty | Bias → entry (→ trigger) TF | Scope | Playbook / style |
|---|---|---|---|---|
| `trend_rider` | Rides established trends | H4 → H1 (→ M15) | Majors, metals, indices | `TREND_RUNNER`: pullback entries, runner exits, budget-capped adds |
| `range_sniper` | Fades clean ranges | H1 → M15 (→ M5) | Majors/minors, quiet sessions | `RANGE`: edge entries, mid/opposite-edge targets |
| `breakout_hunter` | Compression → expansion | H1 → M15 | All liquid classes, session opens | `BREAKOUT`: squeeze/NR7, opening-range, retest entries |
| `pattern_specialist` | Chart and harmonic patterns | H1 → M15 | Universe (tiered) | Existing pattern setups (§A29), filtered by the router |
| `session_opener` | Cash-session opens of indices and stocks | M15 → M5 | Indices, stocks | Opening-range breakout and fade, within the exchange session |
| `crypto_247` | Crypto including weekends | H1 → M15 | Crypto | Trend and range playbooks with the crypto profile (spread, weekend liquidity) |

The roster is a starting point. Bots are added, retired or re-scoped by evidence (L21.7). "Small profits" only
work when costs are small relative to targets, so each bot × symbol pair must pass the cost filter
(target ≥ `min_target_cost_ratio` × round-trip cost, default 4).

### L21.4 Cross-bot rules (commander)

1. **Opposite directions on one symbol:**
   - Default policy `net_direction`: at most one direction per symbol across all bots. When candidates
     disagree, the candidate with the higher expected R per unit of risk wins if its lower CI bound beats the
     other's point estimate. Otherwise neither trades (`SQUAD_CONFLICT`), which keeps today's fail-closed
     spirit.
   - An existing position's direction holds until it is closed, so new opposite candidates are suppressed
     (`SQUAD_OPPOSES_OPEN`).
   - Hedging-only policy `independent` (opt-in, shadow first) lets bots on different horizons hold opposite
     positions. It is shown with the cost of paying the spread twice for a near-zero net exposure.
   - On a **netting** account, `independent` is impossible: the commander forces `net_direction` and refuses to
     start with `independent`.
2. **Same direction, same symbol, several bots:** allowed up to `max_bots_per_symbol` (default 1, then raised
   by evidence) and within the per-symbol risk cap (`max_symbol_risk_percent`). Each bot's position keeps its
   own magic, stop and management.
3. **Correlation:** L20.6 clusters apply across bots. Same-currency exposure from different bots counts as one
   bet against `max_per_cluster_direction`.
4. **Ordering:** commander decisions are deterministic for a given cycle (stable sort by expected R, then
   bot priority, then `bot_id`). The decision record stores the whole candidate list and why each lost.

### L21.5 Risk budgets

- **Account cage first:** `risk` + the owner's profile (§A33) stays the outer limit for the sum of all bots. No
  bot setting can exceed it, and remote changes can only lower risk (§A13/§A20).
- **Per-bot budget:**
  - `risk_share` (fraction of the account's open-risk headroom, Σ ≤ 1)
  - `max_risk_per_trade_percent` (≤ the cage)
  - `max_open_positions`
  - its own daily-loss stop

  A bot that hits its own daily stop pauses itself, and the others continue. The account-level breakers still
  stop everyone.
- **Per-bot probation:** the existing probation (`probation_trades`, `probation_multiplier`) applies per bot,
  so a new bot starts small even when the account is past probation.
- **Evidence-based allocation (opt-in, `allocation: evidence`):**
  - weekly, each ACTIVE bot's `risk_share` is moved toward a weight proportional to the lower 90% bound of
    its expectancy (L20.0) per unit of risk, floored at 0
  - steps ≤ `max_share_step` (default 0.05) per week, floor `min_share` while ACTIVE, every change audited
  - **decreases apply automatically** (fail closed). **Increases are proposals** that the owner confirms
    (CLI or a step-up PWA action), in line with "backtest first, never auto-apply" for anything that adds
    risk
  - a bot whose lower bound is ≤ 0 over ≥ `min_n` trades is set to `PAUSED` with reason `BOT_NO_EDGE`; its
    signals keep shadow tracking so it can come back
- **Default allocation `static`:** the shares from config only.

### L21.6 Trading universe (Q10)

- `squad.trade_universe`:
  - `allowlist` (today's `symbols.allowed`, the default)
  - `catalog`: every symbol that is enabled in `symbol_catalog`, present, tradable (trade mode full), and passes
    the cost filter and the spec checks (min lot vs risk, margin, stops level)
- Each bot's scope is intersected with the trading universe. Symbol overrides (`max_spread_points`,
  `max_lot`, daily breaks) still apply.
- Tier-0 scanning (L20.5) runs over the whole catalog either way, so advisory alerts cover everything. Only
  trading is limited by `trade_universe`.
- Switching to `catalog` for DEMO is a config decision. For LIVE it needs Phase 14, the further DEMO evidence
  of L13 and the user's explicit go-ahead.

### L21.7 Bot lifecycle and evaluation

```
SHADOW (signals + shadow trades only) → PAPER → ACTIVE in DEMO → ACTIVE in LIVE
                      ↘ PAUSED (BOT_NO_EDGE, own daily stop, user) ↗        → RETIRED
```

- Promotion per bot with the L13 criteria (n, paired CI, drawdown), via `app.cli squad promote BOT --reason`,
  audited. LIVE always needs Phase 14 and the user's explicit go-ahead.
- **Per-bot reports:** the expectancy decomposition (L20.0), the timing failure modes (L19.2), the fit matrix
  slice, the trade count, max drawdown and the correlation with other bots. Bots that only duplicate another
  bot's trades add risk without adding opportunities, and this is flagged.
- **Squad backtest:** the backtester runs the commander over all bots together (portfolio mode), because
  interactions (conflicts, heat, correlation) change results. Each bot's stand-alone backtest is shown next to
  its squad contribution.

### L21.8 Identity and magic numbers

- **`magic_registry` table:** `(bot_id, strategy) → magic`, assigned once, persisted, never reused. Legacy mode
  registers `("default", strategy)` with today's values on first start, so existing open positions keep their
  mapping.
- **Block layout:** `MAGIC_NUMBER_BASE + bot_slot × 100 + strategy_slot` (fits in today's `MAGIC_RANGE`
  10 000: up to 100 bots × 100 strategies).
- A position whose magic is in the bot range but unknown to the registry is treated like a stray: the
  reconciler's existing policy applies, and it is never managed by a guess.
- The order comment carries `bot_id` (≤ 25 chars, informational only). Matching stays by magic + ticket.
- (TAA-L901 decisions, 2026-10-06) `app/engine/magic_registry.py`, table `magic_registry` (migration 0038):
  - Slots are stored, not absolute numbers, so a new `MAGIC_NUMBER_BASE` moves the whole block, as before.
  - The table is **engine-local** for now; replication comes with the Squad page (TAA-L909).
  - The backtester keeps its in-memory index mapping: a run starts empty and has no open positions to re-map.
  - Found while doing it: the loss tracker counted only the magics of the strategies enabled *now*, so the
    closing deal of a disabled strategy's open trade did not count toward the loss breakers. It now uses the
    whole bot range, like `ExposureManager`.
  - The orchestrator no longer falls back to the base magic (which belonged to the first strategy) for an
    unknown strategy; every enabled strategy is registered at start.
  - The bot `comment` with `bot_id` waits for squad mode (TAA-L902).

### L21.9 Cloud, API & PWA

- Replicated tables: `bots` (spec summary, status, budget), `bot_reports`, `magic_registry`, and the commander
  decision summaries. Opportunities and shadow rows get `bot_id`.
- **Squad page:**
  - one card per bot: specialty, status, budget share, open positions, today's P/L in R, and the expectancy CI
    (hypothetical where shadow)
  - the commander's recent decisions (who won, who lost and why)
  - pause/resume per bot as a step-up control action through the command queue (risk-lowering only, like the
    kill switch)
- Alerts and opportunities show which bot found them.
- i18n th + en for bot names, statuses and reason codes (`SQUAD_CONFLICT`, `SQUAD_OPPOSES_OPEN`,
  `BOT_NO_EDGE`, `BOT_DAILY_STOP`, `BOT_BUDGET_FULL`). No ranking text implies future profit.

### L21.10 Safety invariants (tests)

1. Σ of all bots' open risk ≤ the account cage. Each bot stays within its own budget (property test with random
   candidate sets).
2. Legacy mode (`squad.enabled: false`) yields identical decisions and backtest results to the pre-squad code
   (golden test).
3. Magic numbers are stable across config changes; an unknown magic is never managed.
4. The commander can only select, suppress or scale down candidates; it never creates a signal or scales up.
5. On a netting account, opposite positions across bots are impossible.
6. The kill switch, account breakers and mode gates act on every bot at once.

## L9. Learning loop & model governance

**Schedule** (engine, worker thread, never in the trading loop):

| Job | When | Output |
|---|---|---|
| Micro-bar build | Every minute, for closed minutes | micro-bars |
| Profiles + regime | Nightly after `nightly_hour_utc` | `symbol_profiles` version |
| Fit matrix | Nightly after calibration | `fit_matrix` version |
| Timing diagnostics + entry-mode policy | Nightly after the fit matrix | `timing_diagnostics`, `entry_mode_policy` versions |
| Dataset + model training | Weekly (`retrain_weekday`), or `app.cli learning train` | `ml_model_versions` CANDIDATE |
| Drift monitor | Hourly | drift metrics, possible demotion |
| Expectancy, behavior and bot reports | Nightly | `expectancy_reports`, `behavior_reports`, `bot_reports` |
| Evidence-based allocation (§L21.5) | Weekly | Automatic decreases, increase proposals |
| Tier-0 scan (§L20.5) | Every entry-TF close | Interest scores, tier-1 queue |

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
7. The separation rules of §L0.2 and the squad invariants of §L21.10 are part of this list: flags off means
   today's behavior (golden tests), and nothing automatic ever raises risk.

## L11. Cloud, API & PWA

- **Replicated tables** (engine-scoped like the rest, TAA-709): `symbol_profiles`, `micro_bar_daily`,
  `fit_matrix`, `ml_model_versions` (metadata and metrics only; the model text stays local),
  `model_predictions` (per opportunity), `pending_entries` outcomes.
- **API** (owned engines only, as in the other read APIs):
  - `GET /engines/{id}/symbols/{symbol}/profile` (latest and history)
  - `GET /engines/{id}/fit-matrix`
  - `GET /engines/{id}/models` and `.../models/{mid}` (metrics, reliability, status history)
  - `GET /engines/{id}/confirmation/stats` (A/B results)
  - `GET /engines/{id}/timing`, `.../expectancy`, `.../playbooks`, `GET /me/behavior` (timing, expectancy,
    playbook state, the owner's behavior report)
  - `GET /engines/{id}/bots`, `.../bots/{bot_id}`, `.../commander/decisions` (squad)
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
| Timing diagnostics (L19.2) | Always (labelled hypothetical, with n and CI) | — (diagnostic only) | — |
| Entry-mode variant (L19.3) | ≥ 50 A/B opportunities | Paired ΔR CI > 0 over ≥ 200 live-shadow opportunities | Same result over a further DEMO period |
| `TIME_STOP_LEARNED`, `REENTRY_1` (L19.5) | ≥ 50 A/B opportunities | Same as entry modes + the user opts in | Same + explicit user go-ahead |
| Time-to-move estimate (L19.6) | n ≥ `min_n` and beats Kaplan–Meier OOS | Not used for trading decisions except the learned time stop | Same |
| Expectancy report, behavior report (L20.0, L20.7) | Always (hypothetical, with n and CI) | — (reports only) | — |
| Playbook router (L20.1) | Always (reason codes) | Disable-only; the fit matrix allows the playbook on the symbol | Same + ≥ 4 weeks in DEMO |
| Range fade, runner, adds, transitions (L20.2–L20.4) | ≥ 50 A/B opportunities | Paired ΔR CI > 0 over ≥ 200 live-shadow opportunities, max DD not worse beyond the CI | Same over a further DEMO period + explicit go-ahead |
| Tiered scanning, correlation selection (L20.5–L20.6) | Always | When scan metrics stay within budget for 2 weeks | Same |
| Squad mode, per bot (L21.7) | Always (SHADOW bots show signals) | The bot passes L13 for its own playbooks; commander and budget tests green | Per bot: further DEMO period + Phase 14 + explicit go-ahead |
| `trade_universe: catalog` (L21.6) | — | Config decision | Further DEMO evidence + explicit go-ahead |
| `conflict_policy: independent` (L21.4) | Shadow comparison | Hedging account + paired ΔR CI > 0 vs `net_direction` | Same + explicit go-ahead |
| `allocation: evidence` (L21.5) | Proposals shown | Decreases automatic, increases confirmed by the owner | Same |

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
  timing:
    enabled: false
    lookahead_hours: null        # null = the strategy's time stop
    pullback_quantile: 0.5       # winners' MAE quantile for PULLBACK
    min_pullback_atr: 0.2
    wide_stop_quantile: 0.8
    trigger_tf_divisor: 3        # entry TF ÷ this ≈ trigger TF (M15 → M5)
    time_stop_quantile: 0.75
    reentry_enabled: false       # shadow evaluation always runs; this only allows real re-entries
    min_policy_n: 200
    eta_min_n: 50                # time-to-move text in alerts
  playbooks:
    enabled: false
    switch_bars: 2
    range: {min_width_atr: 2.0, edge_zone: 0.2, min_touches: 2}
    runner: {tp1_r: 1.5, part_a_share: 0.5, chandelier_atr: 3.0, adds_enabled: false, max_adds: 2}
    scan: {tier1_max: 30, rotation_bars: 12, cycle_budget_seconds: 20}
    selection: {max_per_cluster_direction: 1}
    behavior: {revenge_minutes: 30}
  # squad mode lives at the top level of config.yaml (not under learning), because it carries risk
  drift:
    psi_threshold: 0.25
    rolling_trades: 50
```

Squad mode (§L21), top level of `config.yaml`:

```yaml
squad:
  enabled: false                 # false = legacy: one implicit `default` bot, identical behavior
  trade_universe: allowlist      # allowlist | catalog
  conflict_policy: net_direction # net_direction | independent (hedging accounts only, shadow first)
  max_bots_per_symbol: 1
  max_symbol_risk_percent: 1.0
  allocation: static             # static | evidence
  max_share_step: 0.05
  min_target_cost_ratio: 4
  bots:
    - id: trend_rider
      status: SHADOW
      playbooks: [TREND_RUNNER]
      timeframes: {bias: H4, entry: H1, trigger: M15}
      scope: {classes: [FOREX_MAJOR, METAL, INDEX]}
      risk: {share: 0.3, max_risk_per_trade_percent: 0.5, max_open_positions: 2, max_daily_loss_percent: 1.0}
      strategies: [setup_fib_pullback, example_trend_pullback]
    # range_sniper, breakout_hunter, pattern_specialist, session_opener, crypto_247 ...
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
| `timing_diagnostics` | replicated | version, scope (symbol × strategy × session or manual), failure-mode shares + CI, MAE and time quantiles, baseline, n |
| `entry_mode_policy` | replicated | version, symbol, strategy, mode, ΔR + CI, n, user override |
| `playbook_state` | replicated | server, symbol, playbook, since, regime inputs, switch pending |
| `expectancy_reports` | replicated | version, scope, p, W, L, c, E[R] + CI, opportunity rate |
| `behavior_reports` | replicated (user-scoped) | user, period, pattern, count, share, ΔR vs plan |
| `magic_registry` | engine (replicated later, L909) | bot_id, strategy, bot_slot, strategy_slot, assigned_at (never reused) |
| `bots` | replicated | bot_id, spec hash, status, risk share, status history |
| `bot_reports` | replicated | bot_id, version, expectancy decomposition, failure modes, max DD, overlap with other bots |
| `bot_id` columns | both | added to decisions, opportunities, shadow trades, intents, positions |

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
| L7 | Entry timing (L19): diagnostics, entry-mode variants, timing detectors, learned time stop and re-entry, time-to-move model | L701 needs only existing shadow data, but follows the same order |
| L8 | Regime playbooks (L20): expectancy report, router, range playbook, trend runner + adds, transitions, tiered scanning, correlation selection, behavior report | Combines L3, L8 and L19 into one trading approach |
| L9 | Squad mode (L21): stable magic registry, bots, shared computation, commander, per-bot budgets, trading universe, lifecycle, squad backtest, Squad page | Turns the playbooks into a team of specialist bots; legacy mode stays the default |

**Placement against the main plan:** after Phase 14 and the wrap-up (the 2026-10-06 decision). TAA-L001 (probe)
and TAA-L101–L102 (tick capture) are small, read-only and independent, so starting them early was considered.
**User decision (2026-10-06): no early start.** Phase 14 and the wrap-up finish first.

**Order of work (decided by Claude, 2026-10-06, at the user's request):** the phases above group tickets by
topic. The order of work is the **waves** in TICKETS_LEARNING.md:

- Wave 0: TAA-L901, recommended during Phase 14 / wrap-up, before LIVE go-live
- Wave 1: quick wins on existing data (L701, L801, L808)
- Wave 2: tick foundation
- Wave 3: character and regime
- Wave 4: scan everything + squad foundation
- Wave 5: playbooks
- Wave 6: squad
- Wave 7: timing variants and models
- Wave 8: tick microstructure in use
- Wave 9: governance

Measure first (Wave 1), so later waves work on the levers that matter most.

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
- **Multiple comparisons:** many bots × variants × symbols × playbooks are tested. Some will pass a threshold by
  chance. The counter-measures are pooled (hierarchical) estimates, CIs instead of point values, recording
  the number of comparisons, requiring live-shadow confirmation (replay alone never enables anything), and
  the further DEMO period before LIVE.
- **More trades, more costs:** a squad that takes many small edges pays spread and commission on each. The
  cost filter (`min_target_cost_ratio`) and the `c` lever of the expectancy report must stay visible.
- **Instrument specifics:** stock and index CFDs have dividend adjustments, corporate actions and session
  gaps; crypto has thin weekend liquidity and wide spreads. Profiles and costs are per symbol for this
  reason.
- **One account's view:** affordability and the trading universe are judged on the engine owner's account
  (as today, HANDOFF homework item 6). Serving other users' accounts is a later, multi-user question.

## L18. Open questions for the user

1. ~~Q1: May TAA-L001 (feed probe, read-only on the real demo terminal) and TAA-L101–L102 (tick recording) start
   before Phase 14 is finished, so data accumulates early?~~ **Answered 2026-10-06: no.** Finish Phase 14 and
   the wrap-up first, then follow the waves of TICKETS_LEARNING.md.
2. Q2: Which symbols get ticks recorded first (default: watchlists + open positions, max 20)?
3. Q3: Is a new dependency (`lightgbm`, engine only) acceptable, or should L4 stay numpy-only (logistic + simple
   trees)?
4. Q4: Should deep learning or RL be revisited after L4 has ≥ 6 months of live shadow data?
5. Q5: Should the HMM regime experiment be in scope, or rules only?
6. Q6: Should the profile-based SL/TP suggestion be applied automatically in DEMO, or shown only?
7. Q7: Should `REENTRY_1` be evaluated at all, or left out because of its behavioral risk? (Default: evaluate
   in shadow only, and keep real re-entries off.)
8. Q8: Should the default entry mode switch automatically per symbol × strategy once the L19.7 criteria are met,
   or always need the user's confirmation in the PWA? (Default: needs confirmation.)
9. ~~Q9: Should risk-free adds (pyramiding) be evaluated, and with what cap?~~ **Answered 2026-10-06: yes.**
   They are evaluated in shadow with at most 2 adds. Real adds stay off until they pass L13.
10. ~~Q10: How large should the tier-0 universe be?~~ **Answered 2026-10-06: scan everything tradable.**
    Today the catalog and ranking already cover every symbol, but strategies run only on the monitored set
    (cap 60) and trading is limited to `symbols.allowed`. TAA-L806 (tiered scanning) and TAA-L906 (trading
    universe) close that gap.
11. ~~Q11~~ **Decided 2026-10-06 (ordering delegated to Claude):** TAA-L901 is Wave 0, recommended during
    Phase 14 / wrap-up before LIVE go-live. Its hand-over to the Phase 14 work is the user's call.
12. Q12: Which bots of the starting roster (L21.3) should exist first, and with which risk shares?
