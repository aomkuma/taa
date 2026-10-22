# Strategies

How strategies are built, configured and explained (PLAN §A7, §A29). Every strategy in Milestone 1 is a
**demonstration**: none is production-proven, and nothing in this project claims profitability. Leveraged
FX/CFD trading is high risk.

## Setups and variants at a glance (kept current; last update 2026-10-22 08:00 Thai time)

The short names used in the setup work. A *variant* is a set of parameters of an existing setup, not new code.
Results are backtests (R per trade, net of the modelled costs); they describe the past, not the future.

| Name | Code setup | What it does | Entry TF, symbols | State | Result | Details |
|---|---|---|---|---|---|---|
| **OWN F1 CONF-72** (Setup OWN, owner 2026-10-18) | `setup_own_conf72` (lane `own`) | The H1 tide, at a level (today / yesterday / Asia / round 50 / M15 / H1 read), price action, 2 of 3 M5 indicators, the 72-hour extreme less than 4 U in front or behind, no fast tape; the stop is 1 M1 ATR beyond the level (3-10 U, floor 0.5 M15 ATR) and the target 8 U. Exits: break-even at 4.8 U, 60 min. v2: a runner in a strong-volatility phase, a 10-bar scratch. Half risk off the round 50 | M1; XAUUSD | **off** (lane disabled for the plan1 DEMO, 2026-10-22; before: DEMO paused (2026-10-18 .. 10-19; owner) | window (2026-03..10-14) 35 trades, +0.219 R, +63 USD at 0.01 lot; design +0.188; engine = research 35/35 | OWN_SETUP_ROUNDS round 17 |
| **OWN S2** (CPI / NFP straddle) | `setup_own_s2` (lane `news`) | At 08:30:00 New York: a buy stop 2 U above the ask and a sell stop 2 U below the bid, one cancels the other, live 60 s; the stop 8 U; out at the end of the release minute (quotes, not bars) | quotes; XAUUSD | **off** (lane disabled for the plan1 DEMO, 2026-10-22; before: DEMO paused (2026-10-18 .. 10-19; owner) | window ticks 14 trades, +1.23 R, +144 USD; the release-second fills are the open risk | OWN_SETUP_ROUNDS round 17 (S2) |
| W11-b1 (round 50 at a fresh extreme; weapon 4) | research only | The round 50 at the 72-h / 24-h / 5-day / session extreme (a London session extreme at least 60 min old), price action, market entry | M1; XAUUSD | research | window +0.166 R at 0.41/day; the trades beyond F1 +0.097 R | agents/weapon4/notes.md |
| LV3 (with every larger timeframe, sell the bounce into an earlier level; owner 2026-10-18) | research only (`research/2026-10-18-moments/agents/precursors/lvl3.py`) | Every larger timeframe's trend agrees; the entry TF is the smallest of M1 / M5 / M15 / M30 whose ATR covers 5 USD; the level from M15 / M30 / H1 swings; enter after at least N M1 legs of the pause with the newest peak lower (trough higher); the stop beyond the level by a learned buffer (walk-forward percentile of the winners' overshoot), target >= 5 USD; exits on the entry TF | M1-M30; XAUUSD | stopped 2026-10-18 (its components - trend, pullback, levels, the signal - each measured at chance) | walk-forward on the latest 12 months: learning +0.013 R (66 trades), the exam -0.139 R (95 trades, -198 USD); LV2 (its parent) design -0.032 R over three years | `agents/precursors/notes.md` |
| **OWN PLAN-1** (the daily plan; 2026-10-20, journal rules 2026-10-21) | `setup_plan1_b2`, `setup_plan1_b2m5`, `setup_plan1_orb`, `setup_plan1_ny` (lane `plan1`, TAA-OWN-P1) | Asia B2 at the owner's H1 levels 07-09 Thai (a second B2 of the morning only the first's way) + the London 13:00-Thai ORB, target 1.5 R, in a contracting H4 only after a pool break + the NY 08:30 straddle +-2 / stop 8 USD, out after 30 min; no ATR gate; trades only while the D1 ATR(20) >= 60 USD; one position at a time | M1 / M5 / quotes; XAUUSD | **DEMO from 2026-10-22 07:43 Thai** (the taa-demo worktree, AGGRESSIVE 7.5 %) | learning 26 weeks +0.213 R on 265; **exam (read once) +0.148 on 282** (straddle +0.285, B2 +0.140, ORB -0.006); the old years lose below a D1 ATR(20) of 50 | `research/2026-10-18-moments/agents/journal/PLAN1_JOURNAL.md`, CHECKLIST rows 61-63, `docs/PLAN1_LANE.md` |
| **OWN V2** (the library of researched pictures; owner 2026-10-18/19) | research only (`research/2026-10-18-moments/agents/precursors/v2b.py`, `v2s.py`, `v2e.py`) | At each of the owner's snap times the bot finds the earlier days that looked the same and trades the way they went: V2b - the same core codes per layer; V2s - the same M5 + M1 situation (smoothness, the deepest pullback, the close against the last top / bottom [+ the 120-bar way, size, position]); entry at the snap (V2e: a dip limit or an M1 turn), the stop one entry-TF ATR >= 5 USD, the target 10 U | M1-M30; XAUUSD | research; code proven (hand-worked tests, planted bugs, independent re-derivations: V2b 408 / 408, V2s 723 / 723 trades) | V2b exam -0.169 R; the same picture by eye almost never repeats (0.0-0.1 % of snaps); V2s: the lean tells the next half hour's run way (edge +0.12 exam), but trades lose - learning -0.020 R, the exam -0.085 R (278 trades, -240 USD); V2e entries (a dip limit, an M1 turn, a stop order the lean's way; 28 variants) all negative on the learning half; the lean's drift after costs negative at every holding time | `agents/precursors/notes.md` |

### Stopped and off (the record; details in `docs/archive/SETUP_REVIEW.md`)

Every setup below stopped on 2026-10-17 (owner: the bot starts over with Setup OWN) or was off before; the code
and parameters stay.

| Name | Code setup | What it does | Entry TF, symbols | State | Result | Details |
|---|---|---|---|---|---|---|
| **V1** (harmonic V1) | `setup_harmonic_prz` | Harmonic patterns (AB=CD, XABCD) entered at the PRZ (point D), only while the H4 map is against the trade or ranging, R:R ≤ 3, no break-even; own stop cap off (`max_sl_atr: 20`, owner 2026-10-16) | M15, 8 | **stopped** (owner, 2026-10-17: the bot starts over with Setup OWN; parameters kept); was priority 2 | year +0.211, 181 trades | SETUP_REVIEW §15.3 |
| **F1** (breakout F1) | `setup_breakout` | Waits for a break *against* the H4 and H1 trend (usually a false break) and trades it the other way, with the big trend (`fade_counter_trend: true`, `trend_entries: false`); own stop cap off (`max_sl_atr: 20`, owner 2026-10-16) | M15, 8 | **stopped** (owner, 2026-10-17: the bot starts over with Setup OWN; parameters kept); was priority 3 | year +0.159, 99 trades; out of sample (2024-10 .. 2025-01) −0.012 (45) | SETUP_REVIEW §16, docs/archive/OUT_OF_SAMPLE.md |
| Breakout (original) | `setup_breakout` | Trades every break in its own direction | M15, 8 | off (replaced by F1); **parked** (owner, 2026-10-17: its direction is worse than random, the edge is in fading it - F1, S1) | year −0.154 | SETUP_REVIEW §3-§5, §22 |
| **S1** (M1 gold scalping; the day-trade setup, owner 2026-10-15) | `setup_breakout_scalp` (lane `s1`) | F1's fade on M1: screens H1 (tide) / M15 (wave), stop 2 × ATR(60 M1 bars), target about 2 × the fade's stop, no entries 08:00-12:00 New York, time stop 60 bars; own stop cap off (owner 2026-10-17) | M1, XAUUSD only | **stopped** (owner, 2026-10-17: the bot starts over with Setup OWN; parameters kept); lane `s1`; year met 3 of 4 goals; unstable with real costs (OWN_SETUP: 2025-09..26-02 -0.36 R) | year +0.277, 76 trades, DD 6.2 R; 1st-half CI reaches below 0; out of sample (2024-10 .. 12) +0.179 (25) | SETUP_REVIEW §17, docs/archive/OUT_OF_SAMPLE.md |
| S1 + resume | `setup_breakout` (research config) | S1 with `entry_on: resume` (Elder's third screen: after the trigger, wait up to 15 M1 bars (`resume_bars: 15`) for the first close beyond the previous bar's extreme in the trade's direction, and enter there) | M1, XAUUSD only | not kept: the year stopped at 7 of 12 months (2026-10-17), no clear gain | 7 months +0.270 (39) against S1 +0.235 (43) in the same months | SETUP_REVIEW §19 |
| **TS** (triple screen pullback; the owner's own setup, 2026-10-17) | `setup_triple_screen` | M15 structure break after a pullback whose extreme sits within 0.5 read ATR of an H1/H4 level, with the EMA tide (`tide_ema_tfs`); TS-h4 = the day-trade version (H4 tide, 2 R, at most 12 h) | M15; XAUUSD | **stopped** (2026-10-17): the trigger has no edge over five years; every rule picked in-sample (TS-n3, B1-B5, A0-A5) failed its hold-out years | TS-h4 study +0.195 (2 years); TS-d1 backtest +0.068 (135) | OWNER_TRADING "TS" sections |
| **D1a-D1d** (day trade on M5, closed: S1 is the day-trade setup) | `setup_breakout` | S1's logic on M5, flat within the day (entries 07-12 and 16-18:30 UTC, time stop 2 hours); screens D1a H1/M15, D1b H4/M30 (map state), D1c / D1d the same on swings | M5, XAUUSD only | none passes two rungs (owner to choose the next lever) | March a −0.74 (3), b +0.48 (2), c −0.60 (7), d +0.43 (2); August b 0 trades, d −1.02 (3) | `research/2026-10-15-day-trade/D1_NOTES.md` |
| V1 + h4_room_2 | `setup_harmonic_prz` | V1 plus at least 2 R of room to the nearest opposing level of the H4 chart read (`structure_tf: H4`, `room_min_r: 2`) | M15, 8 | **stopped** (owner, 2026-10-17: the bot starts over with Setup OWN; parameters kept); year 4 of 5 goals (2nd-half CI below 0) | year +0.226, 173 trades, DD 9.5 R (base same runs +0.175, 191); out of sample (2024-10 .. 2025-02) −0.230 (100); rules R1-R3 wait for fresh data (§21) | SETUP_REVIEW §18, §21 |
| Pattern breakout | `setup_pattern_breakout` | Chart-pattern breakouts | M15 | off; **parked** (owner, 2026-10-17) | signals −0.222 (901), direction worse than random; DEMO 6 trades, all stopped | SETUP_REVIEW §9, §22 |
| Candle reversal | `setup_candle_reversal` | Reversal candles at levels | M15 | off | losing | - |
| Fib pullback | `setup_fib_pullback` | Pullbacks to Fibonacci levels | M15 | off | year −0.16 | SETUP_REVIEW §3 |
| Elliott wave | `setup_elliott_wave` | Elliott wave entries | M15 | off | year −0.08 | SETUP_REVIEW §3 |
| Neckline break | `setup_neckline_break` | Double top/bottom, head and shoulders neckline breaks | M15 | off | not reworked yet | - |
| SMC reversal | `setup_smc_reversal` | Liquidity sweep + change of character | M15 | off | about 1 signal a year | SETUP_REVIEW §3 |

**Priorities (owner, 2026-10-17 morning; superseded the same day when every setup above stopped; SETUP_REVIEW §22):** development time went to S1, then V1, then F1, one setup
at a time; TS is the other session's. Parked (no development; the code stays and the scanner keeps them):
the original breakout, pattern breakout and the box breakout - breakouts traded in their own direction, whose
direction measured worse than random. Low priority: candle reversal, fib pullback, Elliott wave, neckline break,
SMC reversal (raw signals negative or too few; never measured with the context screens).

Tried and not kept (2026-10-15, `research/2026-10-15-day-trade/BREAKOUT_NOTES.md`): breaks *with* the trend -
the box breakout `setup_breakout_box` (code stays, lane only, off: 8 symbols M5 -0.24 R over 199 trades; Asia-only
gold +0.46..+1.07 on ~10 trades a year; **parked**, owner 2026-10-16/17: a fresh analysis only if its turn comes), H4/D1 trend following on 29 markets (-0.06..-0.17), momentum burst
scalps (M5 -0.34 or worse); F1 on the 21 crosses (March -0.373, 16 trades); F1 + `entry_on: resume` (Elder's
third screen: March +0.157 on 5 against +0.248 on 12). Not kept: S1 + `entry_on: resume` (§19), S1 on the 7
FX majors (August: on M1 the spread is 34-80 % of S1's stop, so its own spread rule passes almost no bar). Earlier: S1s (S1 with swing screens: March +0.063, 25 trades, below S1's +0.397); the inverted copies (`*_inverted`, docs/archive/INVERTED_SETUPS.md); V2 (V1 + a PRZ confirmation,
−0.10); plain session breaks on M5 for day trading (FX lose to the spread, gold flips in the second half;
D1_NOTES.md). Building blocks used by the variants: the market map (`MarketContext.htf`) and the chart read
(docs/CHART_READ.md). Planned: `setup_confluence` (docs/archive/CONFLUENCE_DIRECTION.md).

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
at a time** (the one under study, `setup_harmonic_prz` first; docs/archive/SETUP_REVIEW.md), while the scanner and shadow
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
(`fade_counter_trend`). [docs/archive/INVERTED_SETUPS.md](archive/INVERTED_SETUPS.md) keeps the history.

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
