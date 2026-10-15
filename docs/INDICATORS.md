# Indicators

Formulas and conventions for `app/indicators/` (PLAN §A6). Indicators are implemented in-house with numpy/pandas
(PLAN D8); TA-Lib is a dev-only reference used in tests.

## Conventions

- **Pure functions.** Inputs are pandas Series from one candle frame; outputs keep the input index and are
  `float64`. No I/O, no clock, no broker access.
- **No look-ahead.** The value at position *t* depends only on positions ≤ *t*. Every indicator has a mutation
  test: replacing the bars after *t* must not change any output at or before *t*.
- **Warm-up is NaN.** Callers treat NaN as "insufficient data" and HOLD. The first defined position of each
  indicator is listed below (0-based).
- **Recursive smoothers** (EMA, Wilder) seed with the simple mean of the first *n* consecutive finite inputs, so
  the warm-up NaNs of an upstream series are skipped. A NaN *after* the seed propagates to every later value:
  validated candles never contain NaN, so one appearing means the data is broken, and the output fails closed.
- **History-length sensitivity.** Recursive indicators depend on where the series starts, and the effect decays
  geometrically (factor `1 − α` per bar). Fetch at least the strategy's `warmup_bars()` plus a burn-in of several
  periods; the TA-Lib cross-checks compare only after a 300-bar burn-in.
- **Multi-input indicators** (high/low/close) require series with the same index; otherwise they raise
  `DataQualityError`. Invalid periods raise `ConfigError`.
- **Smoothing factors.** EMA: `α = 2 / (n + 1)`. Wilder (RMA): `α = 1 / n`. Recursion:
  `y[t] = α · x[t] + (1 − α) · y[t−1]`.

## Trend (`app/indicators/trend.py`)

| Function | Formula | First defined |
|---|---|---|
| `sma(close, n)` | mean of the last *n* closes | `n − 1` |
| `ema(close, n)` | EMA with `α = 2/(n+1)`, seeded with SMA(n) | `n − 1` |
| `macd(close, fast=12, slow=26, signal=9)` | `macd = EMA_fast − EMA_slow`; `signal = EMA_signal(macd)`; `hist = macd − signal` | macd: `slow − 1`; signal/hist: `slow + signal − 2` |
| `adx(high, low, close, n=14)` | see below; columns `plus_di`, `minus_di`, `adx`, each in [0, 100] | DI: `n`; ADX: `2n − 1` |

**ADX / ±DI (Wilder).**

- `up = H[t] − H[t−1]`, `down = L[t−1] − L[t]`
- `+DM = up` if `up > down` and `up > 0`, else 0; `−DM = down` if `down > up` and `down > 0`, else 0
- `TR = max(H − L, |H − C[t−1]|, |L − C[t−1]|)`; position 0 has no previous close and is NaN
- `+DI = 100 · RMA_n(+DM) / RMA_n(TR)`, `−DI` likewise
- `DX = 100 · |+DI − −DI| / (+DI + −DI)`, and 0 when both DIs are 0
- `ADX = RMA_n(DX)`

Edge cases: while the smoothed TR is 0 (a perfectly flat market) the DIs, DX and ADX are NaN, because direction is
undefined.

**Difference from TA-Lib.** TA-Lib seeds the smoothed DM/TR with the *sum* of the first `n − 1` values, while
TAA seeds the Wilder average with the mean of the first *n*. The ratio converges, and after the burn-in both agree
to within 1e-6. SMA and EMA match TA-Lib exactly; MACD matches within 1e-10 after the burn-in.

## Momentum (`app/indicators/momentum.py`)

| Function | Formula | First defined |
|---|---|---|
| `rsi(close, n=14)` | `change = C[t] − C[t−1]`; `RSI = 100 · RMA_n(gain) / (RMA_n(gain) + RMA_n(loss))` | `n` |
| `stochastic(high, low, close, k=14, k_smooth=3, d=3)` | `raw = 100 · (C − LL_k) / (HH_k − LL_k)`; `k = SMA_k_smooth(raw)`; `d = SMA_d(k)` | k: `k + k_smooth − 2`; d: `k + k_smooth + d − 3` |
| `cci(high, low, close, n=20)` | `TP = (H + L + C)/3`; `(TP − SMA_n(TP)) / (0.015 · MAD_n)`, MAD = mean absolute deviation from the window mean | `n − 1` |

Edge cases (all NaN, because the oscillator is undefined and a fabricated neutral value could pass a threshold):
RSI when there was no price change at all, Stochastic when `HH = LL`, CCI for a flat window. Flatness is tested
exactly (window max = min), because the float mean of equal values carries rounding noise.

**Difference from TA-Lib.** RSI, Stochastic (SMA smoothing) and CCI match exactly. TA-Lib blanks slow %K until %D
is defined; TAA publishes %K two bars earlier (`k_smooth`/`d` = 3).

## Volatility (`app/indicators/volatility.py`)

| Function | Formula | First defined |
|---|---|---|
| `true_range(high, low, close)` | `max(H − L, |H − C[t−1]|, |L − C[t−1]|)` | `1` |
| `atr(high, low, close, n=14)` | `RMA_n(TR)`, in price units | `n` |
| `bollinger(close, n=20, k=2)` | `mid = SMA_n`; `upper/lower = mid ± k·σ` with population σ (ddof = 0); `width = (upper − lower)/mid`; `percent_b = (C − lower)/(upper − lower)` | `n − 1` |
| `historical_volatility(close, n=20, bars_per_year=…)` | sample stdev (ddof = 1) of the last *n* log returns × √bars_per_year; a fraction (0.12 = 12 %) | `n` |
| `atr_percentile(atr, lookback=100)` | `100 · count(previous lookback − 1 values ≤ current) / (lookback − 1)`; 100 = highest ATR of the window | ATR(n): `n + lookback − 1` |

Notes:
- `bars_per_year` is the caller's choice: `Timeframe.bars_per_year` assumes a 24x5 market; crypto trades 24x7.
- Bollinger on a flat window: σ is exactly 0, `width = 0`, `percent_b` NaN.
- Historical volatility is NaN where a price is ≤ 0.
- ATR, true range and Bollinger match TA-Lib exactly.

## Volume (`app/indicators/volume.py`)

FX/CFD symbols have no exchange volume; MT5 `tick_volume` counts price updates. It tracks activity but is
broker-specific, so features are relative to the bar's own history and never compared across brokers.

| Function | Formula | First defined |
|---|---|---|
| `volume_ratio(volume, n=20)` | `V[t] / mean(V[t−n … t−1])` | `n` |
| `volume_zscore(volume, n=20)` | `(V[t] − mean) / stdev` over `V[t−n … t−1]` (ddof = 1) | `n` |

The baseline excludes the current bar, so a spike is measured against the activity before it. A zero baseline
mean (a dead session) or a zero stdev is NaN.

## Price action (`app/indicators/price_action.py`)

**Candle anatomy.** `candle_anatomy(open, high, low, close)` returns `body = |C − O|`, `range = H − L`, the
`body_ratio`, `upper_wick_ratio = (H − max(O, C))/range` and `lower_wick_ratio = (min(O, C) − L)/range` (the three
ratios sum to 1), and `direction` = sign(C − O). A zero-range bar has NaN ratios.

**Swings.** `find_swings(high, low, k)` returns `Swing(kind, price, pivot_pos, confirm_pos, pivot_at, confirm_at)`.

- A pivot high at bar *i* is strictly above the *k* highs before it and at least equal to the *k* highs after it
  (pivot lows mirror this). The asymmetric tie rule makes the first bar of a flat top the pivot, so a flat top
  yields exactly one swing.
- A pivot is **confirmed at bar `i + k`**, the first bar at which it can be known. The last *k* bars never hold a
  confirmed pivot. A window containing NaN never produces a pivot.
- `swing_points` gives the per-bar view: the pivot price sits on the confirmation bar, never on the pivot bar.
- `pivot_at` / `confirm_at` are index labels (UTC timestamps for candle frames). They stay stable across
  re-fetches, while positions do not.

**Structure.** `label_structure(swings, equal_tolerance)` labels each swing against the previous one of the same
kind: HH / LH / EQH for highs, HL / LL / EQL for lows. `equal_tolerance` is an absolute price distance (for example
0.1·ATR). The first swing of each kind has no label. `market_structure(high, low, k)` gives, per bar and from the
swings confirmed at or before it, the last high and low labels and `trend`: UP (HH + HL), DOWN (LH + LL), RANGE
(anything else), or None until both kinds are labeled.

**S/R zones.** `sr_zones(swings, as_of_pos, atr_value, tolerance_atr, min_touches=1)`:

- Uses only swings with `confirm_pos ≤ as_of_pos`.
- Sorted by price, a swing joins the current cluster while it lies within `atr_value · tolerance_atr` of the
  cluster's lowest price, so a zone is never wider than the tolerance (no single-linkage chaining).
- A zone records `low`, `high`, `touches` (its strength), and how many members were swing highs and swing lows.
  Zones are returned strongest first, then most recent.
- `Zone.role(price)` is SUPPORT (the zone is below the price), RESISTANCE (above) or INSIDE.
- Without a positive, finite ATR it raises `InsufficientDataError`: zones sized by NaN would be meaningless.

**Breakouts.** `detect_breakouts(close, atr, zones, buffer_atr, false_breakout_bars, start_pos)`:

- An up breakout happens at bar *t* when `C[t] > zone.high + buffer_atr · ATR[t]` and the previous close was not
  beyond its own level; a down breakout mirrors this below `zone.low`.
- It is FALSE if a close returns inside the zone (`≤ zone.high` for an up breakout) within `false_breakout_bars`
  bars, CONFIRMED after that many bars outside, and PENDING while the data ends earlier.
- `resolved_pos` is the bar that settled the status. Statuses never use bars after it, which a truncation test
  checks.
- The caller must build the zones from swings confirmed **before** `start_pos`; zones built later would leak
  future pivots into earlier breakouts.

## Market map (`app/indicators/market_map.py`, TAA-L809)

The higher-timeframe context every setup records (`timeframes.context: [H4, D1]`, parameters in `context_map:`).
Closed bars only; the value at bar *t* uses bars ≤ *t* (a mutation test checks it).

**State per bar** (`state_frame`):

| State | Rule |
|---|---|
| `UP` | ADX ≥ `regime.trend_adx`, efficiency ratio ≥ `er_trend`, close and EMA50 above EMA200, swing structure not DOWN |
| `DOWN` | the mirror |
| `RANGE` | ADX < `regime.range_adx` and efficiency ratio < `er_range` |
| `TRANSITION` | anything else |
| `UNKNOWN` | warm-up (EMA200, ADX or the ratio not defined yet) |

- Efficiency ratio over *n* = `er_bars` bars: `|C_t − C_{t−n}| / Σ |C_i − C_{i−1}|` (1 = a straight line, near 0 =
  back and forth).
- Hysteresis: the reported state changes only after `switch_bars` consecutive bars agree on a new raw state.
- `compression` (direction-neutral): the ATR percentile and the Bollinger width percentile (both over
  `atr_percentile_lookback` bars) are below `compression_pct`.
- In `RANGE`, the box is the high and low of the last `range_bars` bars, with its width in ATR and the confirmed
  swing highs (lows) within `zone_tolerance_atr` × ATR of the top (bottom).

**Zones** (`zones_at`, over the last `zone_lookback_bars` bars):

- `SWING`: `sr_zones` clusters with at least `min_touches` touches; below the close `DEMAND`, above `SUPPLY`, a
  cluster containing the close takes the side of most of its touches. Strength = touches.
- `BASE`: 1-4 tight bars (range ≤ 0.6 ATR) right before a displacement leg of ≤ 3 bars that moves
  ≥ `displacement_atr` ATR and closes beyond the previous 10 bars' extreme (the `smc.supply_demand` rule, kept as a
  map). `DEMAND` below a rally, `SUPPLY` above a drop. `tests` counts later bars that traded into it; a close
  through its far side removes it, and so do more than `max_tests` tests. Strength = the base's bars.
- The nearest `max_zones` per kind are kept.

**Features of a trade** (`signal_features`, keys `ctx:<tf>_*`): `trend` (+1 with the side, −1 against, 0 in a
range or transition; absent while UNKNOWN), `range`, `range_pos` (0 = the favourable edge of the box, 1 = the
opposite edge), `compression`, `zone_with` and `zone_with_strength` (the entry within `zone_near_atr` ATR of a zone
on its side: demand for a BUY), `room_r` (distance to the nearest opposing zone, in R of the trade's risk, capped at
10) and `zone_before_tp` (an opposing zone lies between the entry and the target).

## Chart read (`app/indicators/chart_read.py`, TAA-L813)

One timeframe's chart read the way a trader does (design: `docs/CHART_READ.md` §4; parameters in
`context_map.chart_read:`). `ChartReadFrame(timeframe, candles, point, params)` computes the swings and ATR(14)
of a frame once; `.at(pos)` reads one bar (None before the ATR is defined). Closed bars only. The PWA chart
draws `ChartReadParams().for_display()` (minor-swing levels, a level spent after 4 crossings, the read "now"
with a break in progress and mixed swings read by the broken side: `docs/CHART_READ.md` §4); rules keep the
defaults until a backtest passes a change.

**Swings: the MT5 standard ZigZag** (Depth 12, Deviation 5 points, Backstep 3), ported from MetaQuotes'
`ZigZag.mq5` (full-calculation path):

- maps: at bar *s* the lowest low of the last `depth` bars is a low candidate when it differs from the previous
  bar's window low and the bar's own low equals it (within `deviation` × point for the erase step); a new
  candidate erases higher candidates of the last `backstep` bars. Highs mirrored;
- cutting: highs and lows alternate; a lower low replaces the pending low while searching for a peak, and the
  first high candidate (on a bar without a low candidate) fixes the pending low. A bar with both candidates is
  skipped.
- **No repainting:** a pivot is known from the opposite candidate's bar + `backstep` (when that candidate is
  final). In a straight leg every candidate but the extreme is erased, so a pivot is known only once the next
  leg's extreme has held `backstep` bars: on FBS-Demo history (XAUUSD, EURUSD, GBPUSD, USDJPY) the median lag
  from the pivot bar is 11-12 bars (p90 about 21-23) against a median leg of 13-14 bars, on M15, H1 and H4 alike.
- The live MT5 chart recalculates only its last three extremes, with its tie memory reset, so a chart left
  open can differ from a fresh calculation on equal-high/equal-low bars of its last legs. The port is checked
  against values exported from the terminal: `scripts/mt5/TAA_ExportZigZag.mq5` + `scripts/compare_zigzag.py`.

**The read at bar *t*** (all distances in ATR of bar *t*; the tolerance is `tol_atr` × ATR of the bar tested):

| Part | Rule |
|---|---|
| Labels | HH/LH/EQH, HL/LL/EQL against the previous pivot of the kind; equal within `equal_atr` × ATR at the pivot's known bar |
| Structure | UP = HH + HL, DOWN = LH + LL, CONTRACTING = LH + HL, BROADENING = HH + LL, FLAT = an EQH/EQL, NONE before two labelled kinds |
| Invalidation / broken | DOWN: the last LH, UP: the last HL; `broken` = a close beyond it since the last pivot's bar |
| Age | pivots since the structure last changed |
| Leg in progress | from the last pivot to the extreme since; `retrace` = (P1 − close) / (P1 − P0), 0 at the last pivot, 1 back at the previous one |
| Levels | known pivots of the last `level_lookback` bars, clustered within `level_tol_atr` × ATR; price = the mean |
| Roles | closes through the level (beyond by the tolerance, and the next `hold_bars` closes stay beyond the level; a close inside the band keeps the side): none = SUPPORT/RESISTANCE by side, one = FLIPPED, two or more = SPENT (dropped). A false break does not count as a close through |
| Retests | for a FLIPPED level: bars probing it from the new side within the tolerance that close on that side in their colour |
| Trendlines | DOWN/CONTRACTING: through the last two highs when falling; UP/CONTRACTING: through the last two lows when rising; touches, slope, distance, first close beyond by the tolerance = broken |
| Events (known within the last `event_bars`) | BREAK_HOLD: a close beyond a level or trendline by the tolerance from a close that was not, and `hold_bars` closes beyond; SWEEP_RECLAIM: a high/low beyond a level by the tolerance from a close on the other side, and a close back within `reclaim_bars` (direction = the reclaim's); RETEST: as above, on the last bars |
| Scenarios | at the nearer of the nearest support and resistance: BREAK (on to the next level beyond) and REJECT (back to the opposite level), plus the trend's invalidation in the text |
| `retrace_major` | `with_major(read, higher)`: the close inside the last leg of the next-higher timeframe's read |

## Verification

| Check | Where |
|---|---|
| Hand-computed reference values for every indicator | `tests/unit/test_indicators_*.py` |
| TA-Lib cross-check (skipped when TA-Lib is absent): exact for SMA, EMA, RSI, Stochastic, CCI, TR, ATR and Bollinger; within 1e-10 (MACD) and 1e-6 (±DI, ADX) after a 300-bar burn-in | `TestTalibCrossCheck` in the per-module test files |
| Contract for every indicator: output columns and index, NaN exactly before the documented first position and finite after it on clean data, all-NaN (not an error) on short input, and no look-ahead (replacing the bars after *t* leaves every output at or before *t* unchanged) | `tests/unit/test_indicators_contract.py` (`REGISTRY`) |
| Structured price action (swings, structure, breakouts) has its own look-ahead and truncation tests | `tests/unit/test_indicators_price_action.py` |
| Chart read: the read on data cut at *t* equals the read at *t* (30 random cut points), future mutation, synthetic staircase/triangle/megaphone/flat paths, flips, retests, sweeps, holds, JSON round trip | `tests/unit/test_chart_read.py` |
| Invariants on arbitrary valid OHLC (hypothesis): oscillators in [0, 100], averages within the input range, Bollinger ordering, ATR ≤ the largest true range, candle ratios partition the range, swings are local extremes confirmed *k* bars later | `tests/property/test_indicator_properties.py` |

A new indicator gets an entry in this document, a hand-computed reference test and a `REGISTRY` entry in the
contract test.
