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
| Arbitration | `app/strategy/arbitration.py` | one signal per strategy/symbol/bar, cooldown, BUY-vs-SELL conflict, ranking |

**Rules every strategy follows:**

- It is pure. It gets a `StrategyContext` of values: closed candles with indicator columns, the market
  context, the symbol spec and evidence snapshots. It has no broker, database, secret or wall-clock access;
  `tests/unit/test_architecture.py` enforces this.
- It returns exactly one `Signal` per call: BUY, SELL or HOLD, always with reason codes.
- Every signal carries its **condition checklist**. `setup_strength` is the weighted share of passed
  conditions (0–100). `score` is a ranking heuristic, **not a probability**.
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
