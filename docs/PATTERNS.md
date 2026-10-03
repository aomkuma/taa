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

Formulas used by `levels.pivot_points`, from the previous period's high H, low L and close C:

- **Classic**: `P = (H + L + C)/3`; `R1 = 2P − L`; `S1 = 2P − H`; `R2/S2 = P ± (H − L)`; `R3 = H + 2(P − L)`;
  `S3 = L − 2(H − P)`.
- **Fibonacci**: P as classic; `R/S n = P ± {0.382, 0.618, 1.0} × (H − L)`.
- **Camarilla**: `R/S n = C ± (H − L) × 1.1 / {12, 6, 4, 2}` for n = 1…4.
