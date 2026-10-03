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
| `levels.round_number` | a round price is probed and rejected. Step = `10^(floor(log10 price) − 2)` (EURUSD 0.01, USDJPY 1, XAUUSD 10) unless `step` is set. Variants: major (10 steps), minor (1 step), half (0.5 step) | touch | touch quality × 1.0 / 0.8 / 0.6 | level ∓ tolerance |
| `levels.pivot_points` | a classic / Fibonacci / Camarilla pivot of the previous day (previous week on D1) is probed and rejected, at most once per level per period. Default method: classic | touch | touch quality | level ∓ tolerance |
| `levels.prev_high_low` | previous day/week high or low: `reject` (BEAR at the high, BULL at the low) or `break` (first close beyond it), each at most once per period | reject: against the level; break: with it | reject: touch quality; break: 0.7 | reject: level ± tolerance; break: the level |
| `levels.sr_zone` | a zone of ≥ `min_touches` (3) clustered swings (`sr_zones`, rebuilt after each new swing) is approached from one side, probed, and rejected with a wick ≥ `min_wick`, closing back outside | support BULL / resistance BEAR | min(1, 0.4 + 0.15 × touches) | beyond the zone |
| `levels.sr_breakout` | a close through a zone that held at least one swing on that side, after `min_bars_before` closes on the near side (a base, not a whipsaw), judged after `confirm_bars` bars. `confirmed` holds outside; `false` closes back inside. **Stamped when decided**, never at the breakout bar | confirmed: breakout direction; false: opposite | min(1, 0.4 + 0.15 × touches) | confirmed: the broken edge; false: the breakout bar's extreme |

Formulas used by `levels.pivot_points`, from the previous period's high H, low L and close C:

- **Classic**: `P = (H + L + C)/3`; `R1 = 2P − L`; `S1 = 2P − H`; `R2/S2 = P ± (H − L)`; `R3 = H + 2(P − L)`;
  `S3 = L − 2(H − P)`.
- **Fibonacci**: P as classic; `R/S n = P ± {0.382, 0.618, 1.0} × (H − L)`.
- **Camarilla**: `R/S n = C ± (H − L) × 1.1 / {12, 6, 4, 2}` for n = 1…4.
