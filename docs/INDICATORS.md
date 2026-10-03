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

## Verification

| Check | Where |
|---|---|
| Hand-computed reference values for every indicator | `tests/unit/test_indicators_*.py` |
| TA-Lib cross-check (skipped when TA-Lib is absent): exact for SMA, EMA, RSI, Stochastic, CCI, TR, ATR and Bollinger; within 1e-10 (MACD) and 1e-6 (±DI, ADX) after a 300-bar burn-in | `TestTalibCrossCheck` in the per-module test files |
| Contract for every indicator: output columns and index, NaN exactly before the documented first position and finite after it on clean data, all-NaN (not an error) on short input, and no look-ahead (replacing the bars after *t* leaves every output at or before *t* unchanged) | `tests/unit/test_indicators_contract.py` (`REGISTRY`) |
| Structured price action (swings, structure, breakouts) has its own look-ahead and truncation tests | `tests/unit/test_indicators_price_action.py` |
| Invariants on arbitrary valid OHLC (hypothesis): oscillators in [0, 100], averages within the input range, Bollinger ordering, ATR ≤ the largest true range, candle ratios partition the range, swings are local extremes confirmed *k* bars later | `tests/property/test_indicator_properties.py` |

A new indicator gets an entry in this document, a hand-computed reference test and a `REGISTRY` entry in the
contract test.
