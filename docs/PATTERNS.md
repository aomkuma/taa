# Technical evidence detectors

Catalog and conventions for `app/evidence/` (PLAN §A29). Every detector in `app/evidence/catalog.py` must be
documented here; `tests/unit/test_evidence_catalog.py` enforces it and runs the look-ahead harness against each
one.

Nothing here claims predictive value. Academic support for chart patterns is weak (PLAN R29), and Elliott counts
are ambiguous by nature (R31). Each detector's actual contribution is **measured** on shadow and replay outcomes
(Phase 6C) before it moves any probability.

## Framework

| Concept | Where | Summary |
|---|---|---|
| `Evidence` | `framework.py` | immutable record: detector id/version, family, tier, direction, `detected_at` (confirmation bar close, UTC), quality 0–1, key levels, invalidation, targets, i18n key, details |
| `Detector.scan(ctx, params)` | `framework.py` | returns **every** instance in the frame; an instance stamped at bar *t* uses only bars ≤ *t* |
| `activate` | `framework.py` | the central rule for "still in force": age ≤ `max_age_bars` and no **close** beyond the invalidation level since detection |
| `EvidenceSnapshot` | `framework.py` | what was active at `as_of`; canonical JSON + SHA-256 digest; stored with each opportunity and never updated |
| `EvidenceContext` | `framework.py` | one symbol/timeframe of closed candles, indexed by close time, with memoized ATR, swings and zigzag pivots |
| `DetectorRegistry` / `RunPlan` / `EvidenceEngine` | `registry.py` | catalog validation, prerequisite closure, per-detector timing and call counters |
| zigzag | `zigzag.py` | online, ATR-scaled, multi-degree pivots (below) |

**Identity.** `evidence_id` is a hash of detector id and version, symbol, timeframe, `detected_at`, direction and
key levels. Finding the same instance again in a later scan gives the same id; quality is not part of the id.

**Tiers.** T1 objective (a formula or exact rule), T2 rule-based geometry with tolerances, T3 heuristic.

**Configuration** (`config.yaml` → `evidence:`). `default_enabled` applies to detectors not listed. Each entry in
`detectors:` can set `enabled` and `params`, which are validated against the detector's own bounded parameter
model, so unknown keys or out-of-range values are startup errors. Every detector has `max_age_bars` (default 3).

**Selective computation.** The engine runs only the requested detectors plus their declared prerequisites
(`depends_on`, transitively, in dependency order). Prerequisites run only to feed others and report nothing.
Disabled detectors are never executed.

**Look-ahead harness** (`tests/evidence_harness.py`). At several probe bars *t*:
1. Scanning the frame cut at *t* must give exactly the full-frame records with `detected_at ≤ t`.
2. Replacing every bar after *t* must not change those records.

## Zigzag pivots (`zigzag.py`)

- A leg reverses when price moves against its running extreme by at least `multiple × ATR[t]`. The extreme is then
  confirmed as a pivot at bar *t*, its confirmation bar.
- Degrees come from `evidence.zigzag_degrees` (default: minor 1.5, intermediate 3, major 6 ATR).
- The walk is strictly forward and never revisits a decision, so a prefix of the data gives a prefix of the
  pivots: confirmed pivots never repaint. The running extreme of the current leg is never a pivot.
- A bar cannot both extend a leg and reverse it, because the intrabar order is unknown. Bars before the ATR warm-up
  can set extremes but cannot confirm reversals.
- Pivots alternate HIGH/LOW and are `Swing` records, so `label_structure` and `sr_zones` accept them directly.

## Shared rules for level detectors

- **Touch and rejection** (`common.touch_rejection`): a bar *probes* a level when its low (or high) comes within
  `tol_atr × ATR` of it. It *rejects* the level when open and close both stay on the near side. Support gives
  BULL, resistance gives BEAR. A bar that closes through the level is not a rejection.
  - Quality: `0.3 + 0.5 × rejecting-wick share + 0.2 × closeness of the probe`.
- **Repeats**: `Cooldown` suppresses an event of the same direction over an overlapping price range within
  `cooldown_bars`. Typically it is the same level seen again after a rebuild.
- **Trading periods**: days and ISO weeks start at midnight in `evidence.session_timezone` (FBS server time,
  `Europe/Athens`), using each bar's open time. The first period of a frame may be cut off by the history window,
  so it is never used as a source of levels (fail closed).

## Detector catalog

Record counts on a 600-bar synthetic random walk are shown only as a noise sanity check. They are not a measure of
usefulness.

### Fibonacci (`fibonacci.py`, T1)

An *impulse* is two consecutive zigzag pivots A → B of `params.degree` (default `intermediate`). It is the last
impulse from the bar after B is confirmed until the bar that confirms the next pivot. A close beyond A spends it.
Retracement `r` is at `B − r·(B − A)`; extension `e` is at `A + e·(B − A)` (signs flip for a down impulse).

| Detector | Fires when | Direction | Quality | Invalidation / targets |
|---|---|---|---|---|
| `fib.retracement` | a bar probes and rejects one of the 23.6/38.2/50/61.8/78.6 % levels (each level once per impulse) | impulse direction | touch quality × level weight (61.8: 1.0, 50: 0.95, 38.2: 0.85, 78.6: 0.8, 23.6: 0.6) | A / B, 127.2 %, 161.8 % |
| `fib.golden_zone` | a pullback reaches the 50–61.8 % zone without closing beyond 78.6 %, and the bar closes in the impulse direction with a rejecting wick ≥ `min_wick`, back at or above 61.8 % (once per impulse) | impulse direction | 0.5 × wick score + 0.5 × closeness of the probe to 61.8 % | 78.6 % / B, 127.2 % |
| `fib.extension` | A → B, a retracement pivot C between 23.6 % and 78.6 %, then the first close beyond B | impulse direction | 1.0 if C retraced 38.2–61.8 %, else 0.7 | C / 127.2 %, 161.8 % |
| `fib.cluster` | retracements (38.2–78.6 %) and extensions of the last impulses of the minor, intermediate and major degrees coincide within `cluster_atr × ATR`, with at least `min_levels` levels from **at least two distinct impulses**, and the cluster is probed and rejected | touch direction | touch quality × min(1, 0.4 + 0.2 × levels) | beyond the cluster |

### Levels (`levels.py`, T1)

| Detector | Fires when | Direction | Quality | Invalidation |
|---|---|---|---|---|
| `levels.round_number` | a round price is probed and rejected. Step = `10^(round(log10 price) − 2)` (EURUSD and AUDUSD 0.01; USDJPY and AUDJPY 1; XAUUSD 10 below ≈ 3,162 and 100 above; BTC 1,000) unless `step` is set. Variants: major (10 steps), minor (1 step), half (0.5 step) | touch | touch quality × 1.0 / 0.8 / 0.6 | level ∓ tolerance |
| `levels.pivot_points` | a classic / Fibonacci / Camarilla pivot of the previous day (previous week on D1) is probed and rejected, at most once per level per period. Default method: classic | touch | touch quality | level ∓ tolerance |
| `levels.prev_high_low` | previous day/week high or low: `reject` (BEAR at the high, BULL at the low) or `break` (first close beyond it), each at most once per period | reject: against the level; break: with it | reject: touch quality; break: 0.7 | reject: level ± tolerance; break: the level |
| `levels.sr_zone` | a zone of ≥ `min_touches` (3) clustered swings (`sr_zones`, rebuilt after each new swing) is approached from one side, probed, and rejected with a wick ≥ `min_wick`, closing back outside | support BULL / resistance BEAR | min(1, 0.4 + 0.15 × touches) | beyond the zone |
| `levels.sr_breakout` | a close through a zone that held at least one swing on that side, after `min_bars_before` closes on the near side (a base, not a whipsaw), judged after `confirm_bars` bars. `confirmed` holds outside; `false` closes back inside. **Stamped when decided**, never at the breakout bar | confirmed: breakout direction; false: opposite | min(1, 0.4 + 0.15 × touches) | confirmed: the broken edge; false: the breakout bar's extreme |

### Chart patterns (`chart_patterns.py`, T2)

These detectors use explicit extrema rules with tolerances (PLAN R29). They are built from runs of consecutive
confirmed zigzag pivots (`params.degree`, default `minor`; cup and handle: `intermediate`).

- **Completion and breakout.** A pattern is complete when its last pivot is confirmed. It becomes evidence on the
  first close beyond its neckline or boundary, plus `breakout_atr × ATR`, within `max_wait_bars` (20) of
  completion. A close beyond the invalidation level first kills it. The record is stamped at the breakout bar.
- **Tolerances.**
  - Equality (tops, shoulders, flatness): `equal_tol_atr × ATR + equal_tol_frac × height`, defaults 0.5 and 0.1,
    with ATR taken at completion and height = the pattern's actual price range.
  - Boundary lines (triangles, wedges, rectangles): every pivot within `fit_tol_atr × ATR` (0.5) of its least-squares
    line.
  - Minimum height: `min_height_atr` (2) × ATR.
- **Context.** Reversal patterns need the move into the first extreme to start beyond the neckline: a top forms
  after a rise from below it. A pattern starting at the frame's first pivot has no context and fails closed.
- **Quality** = 0.4 · fit + 0.3 · symmetry + 0.3 · volume.
  - fit: the share of the tolerance left unused.
  - symmetry: even spacing of the pivots in time; for triangles, agreement of the breakout with the triangle's bias.
  - volume: the breakout bar's tick volume against the 20 bars before it. Ratio 2 scores 1.0, ratio 1 scores 0.33,
    and missing volume is neutral (0.5).
- **One record per (variant, breakout bar, direction):** overlapping pivot windows find the same breakout.

| Detector | Pattern rule | Breakout | Direction | Invalidation / target |
|---|---|---|---|---|
| `chart.double` | `top` (M): H, L, H with equal tops (within tolerance), ≥ 5 bars apart; `bottom` (W) mirrors it | close beyond the reaction pivot (neckline) | top BEAR, bottom BULL | the tops (bottoms) / neckline ∓ height |
| `chart.triple` | three equal extremes H, L, H, L, H (mirror for bottoms); neckline = the deeper reaction | close beyond the neckline | top BEAR, bottom BULL | the extremes / neckline ∓ height |
| `chart.head_shoulders` | `top`: shoulders H₀ ≈ H₄, head H₂ beyond both by more than the tolerance (otherwise a triple top), reactions L₁ ≈ L₃; neckline through L₁ and L₃. `inverse` mirrors it | close beyond the neckline at that bar | top BEAR, inverse BULL | right shoulder / neckline ∓ (head − neckline) |
| `chart.triangle` | 5–6 alternating pivots; highs and lows on lines; converging (end width ≤ 80 % of start). `ascending`: flat top, rising lows; `descending`: flat bottom, falling highs; `symmetrical`: falling highs, rising lows | close beyond either line before the apex | breakout direction (a break against the ascending/descending bias scores lower) | opposite line / edge ± height |
| `chart.wedge` | both lines slope the same way and converge. `rising_wedge` only counts on a break down, `falling_wedge` only on a break up | close beyond the line | rising BEAR, falling BULL | opposite line / edge ± height |
| `chart.rectangle` | flat top and flat bottom | close beyond either side | breakout direction | opposite side / edge ± height |
| `chart.flag` | pole: from the latest pivot (or the one before) to the running extreme since, ≥ `pole_atr` (4) × ATR within `max_pole_bars` (15). Consolidation: the following 3–20 bars, retracing ≤ 38.2 % of the pole. `pennant` when the consolidation's high and low regression lines converge, else `flag` | close beyond the consolidation's high (bull) / low (bear) regression line | pole direction | consolidation extreme / breakout edge ± pole |
| `chart.cup_handle` | left rim: HIGH pivot before a recent LOW pivot (the bottom); right rim: running high since the bottom, within 15 % of the depth of the left rim; cup ≥ 15 bars and depth ≥ 3 ATR; **rounded**: ≥ 15 % of the cup's closes within 10 % of the depth from the low (a cosine U ≈ 20 %, a V ≈ 10 %); handle: 1–20 bars, ≤ 50 % of the depth, above the bottom | close above the higher rim | BULL | handle low / rim + depth |

### Candlesticks (`candlesticks.py`, T1)

- **Reference sizes** follow TA-Lib: `ref_range` and `ref_body` are the mean high-low range and the mean real
  body of the **previous 10 bars** (the bar itself is excluded).
- **Cross-check.** The bare geometry functions (`engulfing_mask`, `doji_mask`, `harami_mask`, `marubozu_mask`)
  match TA-Lib's `CDLENGULFING`, `CDLDOJI`, `CDLHARAMI` and `CDLMARUBOZU` bar for bar after TA-Lib's lookback.
- **Prior trend.** A reversal pattern needs the close before its first bar to have moved at least `trend_atr`
  (1.0) × ATR over `trend_bars` (5) bars against the signal.
- **Location weighting.** quality = geometry × (0.6 + 0.4 × `at_level`). `at_level` is 1 when one of the
  location sources reported a rejection in the same direction on one of the pattern's bars: `fib.retracement`,
  `levels.sr_zone`, `levels.round_number`, `levels.pivot_points`, `levels.prev_high_low`. These are declared in
  `depends_on`, so they run even when not enabled for output. Neutral patterns are not weighted.
- **Stamping.** A record is stamped at the pattern's last bar. `max_age_bars` = 2. Invalidation is beyond the
  pattern's extreme (its lowest low for bullish patterns).

| Detector | Rule | Direction |
|---|---|---|
| `candle.engulfing` | opposite colours; the second body covers the first with at least one edge strictly beyond (TA-Lib geometry); after a counter-move | second bar's colour |
| `candle.hammer` | lower tail ≥ 60 % of the range and ≥ 2 × the body; upper shadow ≤ 15 %; range ≥ 0.5 ATR; after a decline | BULL |
| `candle.shooting_star` | mirror of the hammer, after a rise | BEAR |
| `candle.doji` | body ≤ 0.1 × `ref_range` and range ≥ 0.3 ATR. `dragonfly` (upper ≤ 10 %, lower ≥ 60 %) BULL after a decline; `gravestone` mirrors it as BEAR; `long_legged` (both shadows ≥ 30 %, range ≥ ATR) and `standard` are NEUTRAL | see rule |
| `candle.inside_outside` | `inside`: range within a previous bar whose range is at least `ref_range` (NEUTRAL). `outside_bull`/`outside_bear`: range beyond both ends of the previous bar, at least `ref_range`, closing in the top / bottom quarter in its colour | see rule |
| `candle.star` | `morning`: long bearish bar (≥ 0.5 ATR), small body (≤ 30 %) at or below its close (within 10 % of its body; FX rarely gaps), then a bullish close above the first bar's midpoint, after a decline. `evening` mirrors it | morning BULL, evening BEAR |
| `candle.three` | `soldiers`: three bullish bars ≥ 0.5 ATR, each opening inside the previous body and closing higher, upper shadows ≤ 30 % of the body. `crows` mirrors it | soldiers BULL, crows BEAR |
| `candle.harami` | a body above `ref_body`, then a body below `ref_body` inside it (TA-Lib geometry); after a counter-move | opposite to the first bar |
| `candle.tweezer` | `top`: equal highs (within 5 % of `ref_range`), bullish then bearish, after a rise. `bottom` mirrors it | top BEAR, bottom BULL |
| `candle.marubozu` | body above `ref_body`, both shadows below 10 % of `ref_range` (TA-Lib geometry); no trend needed | its colour |

### Momentum (`momentum.py`, T1)

Oscillators: RSI(14), MACD(12, 26, 9) line, slow Stochastic %K(14, 3, 3), CCI(20), all from `app/indicators`
(docs/INDICATORS.md).

| Detector | Rule | Direction | Quality / invalidation |
|---|---|---|---|
| `momentum.divergence` | Two consecutive same-kind zigzag pivots (`minor`), 5–60 bars apart, with the oscillator read at each pivot bar. **Regular**: price makes a higher high while the oscillator makes a lower high (bearish), or a lower low with a higher oscillator low (bullish). **Hidden**: a lower high with a higher oscillator high (bearish), or a higher low with a lower oscillator low (bullish). Variants `rsi/macd/stoch` × `regular/hidden`. Stamped at the second pivot's confirmation; `max_age_bars` 5 | highs BEAR, lows BULL | 0.5 + 0.5 × oscillator gap ÷ scale (RSI 10, %K 20, MACD 0.5 ATR) / beyond the second pivot |
| `momentum.ob_os` | RSI back below 70 / above 30, or %K back below 80 / above 20 (`*_overbought_exit`, `*_oversold_exit`) | exit from overbought BEAR, from oversold BULL | 0.5 + 0.5 × depth of the excursion ÷ 15 / the price extreme reached during the excursion |
| `momentum.cross` | `macd`: the line crosses its signal (1.0 when on the far side of zero, an early turn; otherwise 0.6). `stoch`: %K crosses %D while %D is beyond 20 / 80 | cross direction | as stated / the bar's extreme |
| `momentum.cci_extreme` | `extreme_exit`: CCI back inside ±100 after reaching ±200 within 10 bars (exhaustion). `breakout`: CCI crossing ±100 from inside (momentum push) | exit: against the extreme; breakout: with it | 0.4 + 0.3 × peak ÷ 200 / the bar's extreme |

### Trend (`trend.py`, T1)

These describe states that persist, so they are stamped when the state begins and stay active up to a long
`max_age_bars` (50 for alignment, 20 for ADX). Their invalidation level ends them earlier.

| Detector | Rule | Direction | Quality / invalidation |
|---|---|---|---|
| `trend.ma_alignment` | `aligned_bull`: EMA20 > EMA50 > EMA200 with the close above EMA20, from the bar it begins (`aligned_bear` mirrors it). `golden_cross` / `death_cross`: EMA50 crossing EMA200. `slow_reclaim` / `slow_loss`: the close crossing EMA200 (half weight) | as named | 0.5 + 0.5 × min(1, ADX ÷ 40) / the mid EMA (alignment) or EMA200 (crosses) at detection |
| `trend.adx_strength` | ADX(14) rising through 25 | +DI > −DI BULL, else BEAR | 0.5 + \|+DI − −DI\| ÷ 40 / the bar's extreme |

### Volatility and volume (`volatility.py`, T1)

| Detector | Rule | Direction | Quality / invalidation |
|---|---|---|---|
| `volatility.bollinger_squeeze` | Bollinger(20, 2) width in the lowest 10 % of its last 120 values (a squeeze episode; gaps ≤ 20 bars belong to the same episode), then the first close outside a band within 20 bars, once per episode. The breakout bar may itself still rank as a squeeze | breakout side | 0.6 + 0.4 × freshness / the middle band |
| `volatility.keltner` | first close outside EMA(20) ± 2 × ATR(10) | breakout side | 0.5 + distance beyond ÷ ATR / EMA(20) |
| `volatility.donchian` | first close above the previous 20 bars' highest high (below their lowest low) | breakout side | 0.7 / mid of the channel |
| `volatility.atr_expansion` | a range-expansion bar: true range ≥ 2 × the previous ATR, closing in its top / bottom 30 % | close side | TR ÷ (2 ATR) × 0.6 / the bar's midpoint |
| `volume.tick_spike` | tick volume ≥ 2.5 × the previous 20 bars' mean. `climax`: after a move of ≥ 3 ATR over 10 bars, the bar closes back in its far half (a selling climax after a decline is BULL). Otherwise `spike` in the direction of a close in the outer 30 % | as stated | 0.4 + 0.2 × ratio ÷ 2.5 / the bar's extreme |
| `volume.session_vwap` | VWAP = Σ(typical price × tick volume) ÷ Σ tick volume, reset at each trading day (`evidence.session_timezone`). `reclaim` / `loss`: the close crossing it, ignoring the first 3 bars of a session | reclaim BULL, loss BEAR | 0.6 / the VWAP at detection |

### Sessions (`sessions_ranges.py`, T1)

- Sessions are defined in each exchange's **local** time (zoneinfo), so daylight-saving changes move them
  correctly. A bar belongs to a session by its open time.
- A range is used only if every bar of its session is present (fail closed) and it has closed before the
  breakout bar. Range height must be 0.5–4 ATR.
- Intraday timeframes only (≤ H1).

| Detector | Rule | Direction | Quality / invalidation / target |
|---|---|---|---|
| `sessions.asian_breakout` | the Tokyo range (09:00–15:00 Asia/Tokyo), broken by the first close beyond it in the London morning (08:00–12:00 Europe/London) of the same London calendar day, once per day | breakout side | 0.5 + 0.5 × volume score / range midpoint / range height beyond the edge |
| `sessions.open_breakout` | opening range = the first 60 minutes after 08:00 local in London and New York (variants `london`, `new_york`); the first close beyond it within the next 180 minutes, once per session per day | breakout side | same |

### Ichimoku (`ichimoku.py`, T1)

- Tenkan and Kijun are the midpoints of the last 9 and 26 bars' high/low.
- Senkou A = (Tenkan + Kijun) / 2 and Senkou B = the 52-bar midpoint, both *plotted* 26 bars ahead. The cloud at
  bar *t* is therefore the Senkou values computed at `t − 26`; a test checks this shift.
- Chikou (the close plotted 26 bars back) is compared through `close[t]` against `close[t − 26]`.

| Detector | Rule | Direction | Quality / invalidation |
|---|---|---|---|
| `ichimoku.kumo` | `breakout`: the first close above the cloud top (below its bottom). `twist`: Senkou A crossing Senkou B at the current bar, so the cloud 26 bars ahead changes colour (computed from past bars) | breakout / twist side | breakout 0.6 + 0.4 × min(1, cloud thickness ÷ 2 ATR), twist 0.5 / the far edge of the cloud |
| `ichimoku.tk_cross` | Tenkan crossing Kijun | cross side | 1.0 on the strong side of the cloud, 0.7 inside it, 0.4 on the weak side (0.5 with no cloud yet) / Kijun |
| `ichimoku.chikou` | the first bar at which the close clears both the close and the cloud of 26 bars ago (above both: BULL; below both: BEAR) | as stated | 0.7 / the close of 26 bars ago |

### Market structure (`structure_smc.py`, family TREND, T1)

A confirmed zigzag pivot (`minor`) is used only from the bar after its confirmation. The trend state follows
Dow theory: UP when the last high is HH and the last low is HL, DOWN for LH and LL.

| Detector | Rule | Direction | Quality / invalidation |
|---|---|---|---|
| `structure.dow` | the trend state becomes `up` or `down`; `max_age_bars` 50 | as named | 0.7 / the last opposite pivot |
| `structure.bos_choch` | the first close beyond the last confirmed swing. `bos` when it is with the trend (continuation), `choch` when it is against an established trend (the first sign of a reversal), `break` with no trend | break side | 0.8 / 0.7 / 0.5; invalidation is the last opposite swing |
| `structure.trendline` | lines through the last two swing lows (rising: support) and highs (falling: resistance). `bounce_*`: a later bar probes the line within 0.25 ATR and closes back on its side in the right colour, once per line. `break_*`: the first close beyond the line by the tolerance, which ends it. Detail `channel`: both lines exist and are near-parallel (slopes within 30 % and of the same sign) | bounce off support BULL, off resistance BEAR; break the other way | bounce 0.65 (0.8 in a channel), break 0.7 / the line |

### Smart money and Wyckoff (`structure_smc.py`, family SMART_MONEY, T2)

Zones (FVG, order block, supply/demand) are reported on the first **retest**: a bar that dips into the zone and
closes back out of it in the zone's direction, within `max_bars` (50). A close through the zone first kills it.
Reporting the retest rather than the formation avoids double-counting the impulse that created the zone, which
the momentum and volatility detectors already see.

| Detector | Rule | Direction | Quality / invalidation |
|---|---|---|---|
| `smc.liquidity_sweep` | a bar trades beyond a recent confirmed swing high or low (`swing_k` 3, within 50 bars), where stops rest, and closes back inside. A swing is spent once traded through, swept or not | above highs BEAR, below lows BULL | 0.5 + 0.25 × pools swept + 0.25 × wick ÷ ATR / the sweep extreme |
| `smc.fvg` | a three-bar imbalance: bar *t*'s low above bar *t − 2*'s high (bullish) by ≥ 0.2 ATR; reported on its retest | gap side | 0.5 + 0.5 × gap ÷ ATR / the far edge of the gap |
| `smc.order_block` | the last opposite-colour candle within 5 bars before a displacement leg (≤ 3 bars moving ≥ 2 ATR and closing beyond the previous 10 bars' extreme); its range, reported on its retest | leg direction | 0.7 / the far edge |
| `smc.supply_demand` | a base of 1–4 tight bars (range ≤ 0.6 ATR) right before a displacement leg (demand under a rally, supply over a drop), reported on its retest | leg direction | 0.5 + 0.1 × base bars / the far edge |
| `wyckoff.spring_upthrust` | a sideways range over the last 30 bars (height 2–6 ATR, net drift ≤ half the height). `spring`: a dip below the range low that closes back inside. `upthrust`: a poke above the high that closes back inside. Cooldown 10 bars | spring BULL, upthrust BEAR | by the distance of the close back inside / the probe extreme; target the opposite side of the range |

Formulas used by `levels.pivot_points`, from the previous period's high H, low L and close C:

- **Classic**: `P = (H + L + C)/3`; `R1 = 2P − L`; `S1 = 2P − H`; `R2/S2 = P ± (H − L)`; `R3 = H + 2(P − L)`;
  `S3 = L − 2(H − P)`.
- **Fibonacci**: P as classic; `R/S n = P ± {0.382, 0.618, 1.0} × (H − L)`.
- **Camarilla**: `R/S n = C ± (H − L) × 1.1 / {12, 6, 4, 2}` for n = 1…4.
