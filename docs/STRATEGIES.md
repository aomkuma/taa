# Strategies

How strategies are built, configured and explained (PLAN §A7, §A29). Every strategy in Milestone 1 is a
**demonstration**: none is production-proven, and nothing in this project claims profitability. Leveraged
FX/CFD trading is high risk.

## Framework

| Piece | Module | Role |
|---|---|---|
| Models | `app/strategy/signal_models.py` | `Signal`, `Condition`, `SignalEvidence`, `MarketContext`, `TimeframeState`, `StrategyContext`, `ReasonCode` |
| Context | `app/strategy/context_builder.py` | fetches each enabled timeframe, computes indicators, aligns on bar close time, logs one analysis line per timeframe |
| Regime | `app/strategy/regime_detector.py` | trend (EMA alignment), regime (ADX bands, ATR percentile), volatility state |
| Base class | `app/strategy/base_strategy.py` | `BaseStrategy` contract and the `hold()` / `entry()` signal builders |
| Registry | `app/strategy/registry.py`, `catalog.py` | builds the enabled strategies from `config.yaml`; the plugin boundary turns a crash or a foreign signal into HOLD `STRATEGY_ERROR` |
| Enrichment | `app/strategy/enrichment.py`, `app/evidence/confluence.py` | attaches the active evidence of every timeframe to each signal (supports / conflicts / neutral); an entry's `setup_strength` becomes the confluence score (docs/PATTERNS.md "Confluence score") |
| Arbitration | `app/strategy/arbitration.py` | one signal per strategy/symbol/bar, cooldown, BUY-vs-SELL conflict, ranking |

**Rules every strategy follows:**

- It is pure. It gets a `StrategyContext` of values: closed candles with indicator columns, the market
  context, the symbol spec and evidence snapshots. It has no broker, database, secret or wall-clock access;
  `tests/unit/test_architecture.py` enforces this.
- It returns exactly one `Signal` per call: BUY, SELL or HOLD, always with reason codes.
- Every signal carries its **condition checklist**. Before enrichment, `setup_strength` is the weighted
  share of passed conditions (0–100). Enrichment turns it into the confluence score: the checklist is the
  core term, and evidence families the checklist already measures (`core_families`) add no support.
  `score` is a ranking heuristic. Neither number is a probability.
- Parameters are a pydantic model (`extra="forbid"`, bounded fields). A typo in `config.yaml` is a
  startup error, even for a disabled strategy.
- Missing data (indicator warm-up, no spec, no spread) means HOLD `INSUFFICIENT_DATA`, never a guess.

**Timeframe alignment.** The decision time is the close of the newest entry-timeframe bar. Every other
timeframe is cut to bars with `close_time <= decision_time`, so a higher-timeframe bar that is still forming
is never seen. A timeframe whose last bar is two or more bars behind gets an `ALIGNMENT_LAG` quality flag.

**Regime thresholds** (`config.yaml` → `regime:`):

| State | Rule |
|---|---|
| Trend | BULLISH: close > EMA(slow) and EMA(mid) > EMA(slow); BEARISH mirrored; otherwise NEUTRAL |
| Regime | VOLATILE: ATR percentile > 90 (checked first); TRENDING: ADX >= 20; RANGING: ADX < 18; UNCLEAR in between or during warm-up |
| Volatility | LOW < 25 ≤ NORMAL ≤ 75 < HIGH ≤ 90 < EXTREME (ATR percentile) |

**Arbitration** (per symbol and bar, in this order): duplicates → `DUPLICATE_SIGNAL`; the same strategy
within `strategies.cooldown_bars` of its last selected signal on the symbol → `COOLDOWN_ACTIVE`; BUY and SELL
candidates together → all `CONFLICT`, nothing selected; otherwise the best by score, then setup strength,
then RR wins and the rest are `LOWER_RANK`. An existing opposite position is never reversed by a signal.

## `example_trend_pullback` (DEMONSTRATION ONLY)

A textbook trend-pullback setup, used to show the full path from candles to an explained signal. It is not
production-proven.

| # | Condition (`name`) | Weight | Rule (BUY; SELL mirrored) | Reason code when it fails |
|---|---|---|---|---|
| 1 | `htf_bias` | 2 | higher TF: close > EMA200, EMA50 > EMA200, ADX >= 20 | `NO_BIAS` |
| 2 | `htf_trending` | 2 | higher-TF regime is TRENDING | `REGIME_NOT_TRENDING` |
| 3 | `pullback_to_ema` | 1 | a low touched EMA20 within the last 3 entry bars | `NO_SETUP` |
| 4 | `close_beyond_ema` | 1 | the signal bar closes above EMA20 | `NO_SETUP` |
| 5 | `rsi_cross_50` | 1 | RSI(14) >= 50 now, below 50 in the 3 bars before | `NO_SETUP` |
| 6 | `clear_of_opposing_level` | 1 | nearest resistance zone more than 1 ATR away | `NEAR_OPPOSING_LEVEL` |
| 7 | `sl_within_limit` | 1 | SL at most 3 ATR from the entry | `SL_TOO_FAR` |
| 8 | `rr_ok` | 1 | RR >= 1.5 | `RR_TOO_LOW` |
| 9 | `spread_ok` | 1 | spread <= 15 % of the SL distance | `SPREAD_TOO_HIGH` |
| 10 | `session_window` | 1 | entry-bar close Monday–Friday 07:00–20:00 UTC | `OUTSIDE_SESSION` |
| 11 | `before_friday_cutoff` | 1 | not after Friday 20:00 UTC | `FRIDAY_CUTOFF` |

- **Entry:** the live ask (BUY) or bid (SELL); without a quote, the bid-based close plus the spread for a BUY.
- **Stop:** beyond the last confirmed swing low, or 1.5 ATR below the entry, whichever is farther, plus the
  spread as a buffer.
- **Target:** 2R.
- **Score:** `setup_strength × (0.75 + 0.25 × min(1, (ADX − 20) / 20))`, ranking only.
- **Explanation:** one `[x]`/`[ ]` line per condition with the measured value, e.g.
  `[x] htf_bias: H1 trend BULLISH, ADX 24.1 (min 20); [ ] rsi_cross_50: RSI 47.2; …`. The PWA shows the
  translated condition names (`condition.<name>`) and reason codes (`reason.<code>`).
- **Management** (position manager, Phase 6): break-even at +1R, trail 2 ATR after +1.5R, close when the
  higher-timeframe bias flips (`TrendPullback.bias`).

Every parameter is in `TrendPullbackParams` and can be set under `strategies.items[].params`.

## Pattern-based setups (DEMONSTRATION ONLY, unproven)

`app/strategy/setups.py` (PLAN §A29, use 2). Each setup turns one family of trigger detectors on the entry
timeframe into an explicit plan. All are listed in `config.yaml`; since 2026-10-09 the bot trades **one setup
at a time** (the one under study, `setup_harmonic_prz` first; docs/SETUP_REVIEW.md), while the scanner and shadow
keep every setup the users follow. They need the evidence engine in the context builder. Every entry carries the
reason codes `<SETUP_CODE>` and `DEMO_UNPROVEN`.

**A signal alone is not enough (owner, 2026-10-14; a principle for every setup).** A trigger is only the
timing. Every setup is read together with its context before it trades:

- **the trend** on the higher timeframes (Elder's screens: H4 the tide, H1 the wave; `screen_h4` / `screen_h1`);
- **support and resistance** (the H4/D1 demand and supply zones and the range box of the market map);
- **market structure**: higher highs and higher lows (an up structure), lower highs and lower lows (a down
  structure), and where the last swing broke (`app/indicators/price_action.py`: `label_structure`,
  `market_structure`; the market map's UP/DOWN state already needs a structure that is not against it);
- **the market phase** that suits the setup (a setup trades less, only its surest signals, in a phase that does
  not suit it: CLAUDE.md, "System principle").

How each element is used is decided per setup from its backtests (theory about a third, measured price behaviour
the rest): for `setup_breakout` the trend screens and a counter-trend fade held, a blanket "no zone before the
target" gate did not (it removed winners; SETUP_REVIEW §16). Each element is coded as a setup parameter, off by
default, and switched on per setup in `config.yaml` once its backtest holds.
The planned chart read (`docs/CHART_READ.md`, TAA-L813) gives every setup the same reading of major swings,
levels with their role, trendline and false breaks; measured first (its §2), adopted per setup only after its
backtests hold.

**Inverted setups (2026-10-09 .. 2026-10-14, removed).** Every strategy used to exist as `<name>_inverted` (the
signal on the other side, the stop at the original's target). A year of two-world backtests showed no edge on the
blind inverted side (SETUP_REVIEW §14-§16), so the copies were removed from the code on 2026-10-14 (owner). What
held is narrower and lives inside the setup: a trigger against both the H4 and the H1 trend is faded
(`fade_counter_trend`). [docs/INVERTED_SETUPS.md](INVERTED_SETUPS.md) keeps the history.

**Higher-timeframe market map (TAA-L809).** Every signal of every setup records the H4/D1 map as `ctx:h4_*` /
`ctx:d1_*` features: trend vs consolidation, range position, compression, whether the entry sits at a demand
(BUY) or supply (SELL) zone, the room to the nearest opposing zone in R and whether one lies before the target
(docs/INDICATORS.md, "Market map"). It is **measured, not a filter**: a setup gets a context rule only after the
rule holds walk-forward on the half and the symbols it was not chosen on (TAA-L810, hook H1).

**Shared rules** (`SetupParams`, all overridable per setup under `params`):

| Step | Rule |
|---|---|
| Trigger | an active, directional item of the setup's detectors, fired on the decision bar (`trigger_max_age_bars: 0`), quality ≥ `min_quality`; triggers in both directions → HOLD `CONFLICT`; best quality wins |
| Entry | market: live ask / bid, else the bid-based close (+ spread for a BUY) |
| Stop (`stop_mode`) | `invalidation`: the trigger's invalidation (or the setup's reference) ∓ `stop_buffer_atr` (0.1) ATR · `atr`: `sl_atr_multiple` (1.5) ATR · `nearer`: the closer of the two. Wrong-side invalidation → ATR stop. The spread is always added |
| Target (`target_mode`) | `measured`: the nearest trigger target beyond the entry with RR ≥ `min_rr` (else the farthest) · `level`: the same over the context's opposing S/R zones · `rr`: `rr_target` (2) R; no usable price → `rr` |
| Checks | `sl_within_limit` (≤ 3 ATR), `rr_ok` (≥ 1.5), `spread_ok` (≤ 15 % of SL), `session_window`, `before_friday_cutoff`, plus the setup's confirmations |
| Score | `setup_strength × (0.5 + 0.5 × trigger quality)`, ranking only |

| Setup (`name`) | Triggers | Stop / target defaults | Extra conditions |
|---|---|---|---|
| `setup_neckline_break` | `chart.double`, `chart.triple`, `chart.head_shoulders` | nearer / measured move | — |
| `setup_pattern_breakout` | `chart.triangle`, `chart.wedge`, `chart.rectangle`, `chart.flag`, `chart.cup_handle` | nearer / measured (pattern height) | — |
| `setup_fib_pullback` | `fib.golden_zone` | beyond 78.6 % / prior high B or 127.2 % | `htf_not_opposed` (higher-TF trend not against) |
| `setup_harmonic_prz` | `harmonic.*` (7 patterns) | beyond the PRZ far edge / 38.2 or 61.8 % of AD | optional (off by default): `h4_phase` (`phase_gate: h4_against_or_range`), `prz_confirmed` (`confirm: prior_bar_break`), `rr_not_too_far` (`max_rr`) |
| `setup_elliott_wave` | `elliott.wave`, variants `wave3`/`wave5`, primary count only | beyond the wave-1/4 limit / the detector's projections | — |
| `setup_smc_reversal` | `smc.fvg` retest | beyond the sweep extreme / next opposing level | `liquidity_sweep` and `change_of_character` (CHoCH) the same way within `confirm_window_bars` (30) |
| `setup_breakout` | `volatility.donchian`, `sessions.asian_breakout`, `sessions.open_breakout` | nearer / measured, else 2R | — |
| `setup_candle_reversal` | directional reversal candles (engulfing, hammer, shooting star, dragonfly/gravestone doji, outside bar, stars, harami, tweezer) | beyond the candle extreme / next opposing level | `at_level`: the candle sits on a level |

Notes:

- **Why "nearer" for chart patterns.** A stop beyond the pattern extreme with a measured-move target gives
  RR below 1 by construction, so the setup could never pass min RR. Set `stop_mode: invalidation` to use the
  textbook stop anyway.
- **Harmonic refinements (SETUP_REVIEW §15, 2026-10-12).** `phase_gate: h4_against_or_range` trades only while
  the H4 market map trends against the trade or ranges (a missing map holds); `confirm: prior_bar_break` waits
  after the PRZ completion (at most `trigger_max_age_bars` bars) for the first close beyond the previous bar's
  high/low (Elder's third screen) and drops a pattern that closed through its invalidation; `max_rr` (any setup)
  refuses targets farther than that many R. The backtester gives strategies the H4/D1 map since 2026-10-12.
- **SMC confirmations** are read from the active evidence, so `smc.liquidity_sweep` and `structure.bos_choch`
  need `max_age_bars` ≥ `confirm_window_bars` under `evidence.detectors` (their default is 3 bars).
- Confluence enrichment ignores support from each setup's own family (`core_families`), so a setup is not
  credited twice for its trigger.
