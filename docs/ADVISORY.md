# Advisory: formulas, definitions and caveats

This document explains how TAA's advisory numbers are computed: the symbol ranking, the two numbers shown on
each opportunity, the shadow trades behind them, calibration and the accuracy statistics. It is the reference
for anyone who changes this code or reviews what the app tells users. Design rationale lives in `docs/PLAN.md`
§A25–§A31. The code is in `app/advisory/`.

> **Every advisory result is hypothetical.** Shadow and replay trades are simulations with simplified fills.
> None of these numbers predicts future results, and no part of the app may present them as a profit promise.

---

## 1. Symbol ranking (§A25)

The ranking says how well a symbol suits **this account now**. It never changes what the bot trades.

### Inputs and gates (`suitability.py`)

- **Typical stop:** `typical_SL = k × ATR(H1, 14) + median spread`, with `k = advisory.suitability.sl_atr_multiple`
  (1.5).
- **Min-lot risk:** `volume_min × (loss_per_lot + cost_per_lot)` at the typical stop.
  **Required equity** is the equity whose risk budget covers the min-lot risk.
- **Risk-sized lot:** produced by the real `PositionSizer`, which always floors to the volume step.
- **Effective leverage:** `|P/L of a 1% move| × 100 / equity`.
- **Cost ratio:** `(median spread cost + commission) / loss at the typical stop`.

| Gate | Passes when |
|---|---|
| G1 Tradable | trading is enabled in a direction, the spec is consistent, and a filling mode exists |
| G2 Min-lot affordability | min-lot risk ≤ risk budget |
| G3 Margin | margin × `margin_buffer` (2×) ≤ free margin × utilization cap, and the projected margin level ≥ minimum |
| G4 Cost | cost ratio ≤ `risk.max_spread_to_sl_ratio` |
| G5 Stops level | `stops_level × point` < 0.5 × typical stop |
| G6 Data | ATR is known, there are enough candles, and the quote is fresh while the market is open |

A symbol is eligible only when every gate passes. Every gate carries a TH/EN explanation key.

### Soft scores (`scoring.py`, each 0–100)

| Score | Formula |
|---|---|
| S1 Sizing granularity | `log2(risk budget / min-lot risk)`, scaled 1× → 0 and 16× → 100 |
| S2 Cost efficiency | `1 − cost ratio / max_spread_to_sl_ratio` |
| S3 Leverage/margin comfort | mean of `1 − L / max_effective_leverage` and `1 − margin share` |
| S4 Liquidity now | `ρ / 2`, where ρ = this hour-of-week's tick volume ÷ the symbol's median |
| S5 Volatility regime | 100 inside ATR percentiles 20–80, falling linearly to 0 at 0 and at 100 |
| S6 Regime fit | preferred regime → 100, UNCLEAR → 50, any other regime → 0 |
| S7 Diversification | `1 − max |correlation|` with open exposure and with the picks ranked above |
| S8 Historical edge | `50 + 50 × shrunk / edge_full_scale_r`, with `shrunk = n / (n + 20) × expectancy_R`; neutral 50 below `edge_min_trades` (30) |
| S9 Holding cost | swap credit → 100; otherwise `1 − (swap per night / loss at typical stop) / swap_max_fraction` |

- **Overall** is the weighted mean of S1, S2, S3, S8 and S9. **Now** is the weighted mean of all nine scores.
- Order: eligible symbols first, then symbols whose market is open, then Now, then Overall, then the name.
- **S8 input** (`stats.edge_estimates`): per symbol, the mean `r_net` of closed PLAN shadow trades.
  - LIVE trades count fully.
  - REPLAY trades count as at most `calibration.replay_cap` (50) trades per symbol.
  - The engine reloads this hourly (`EdgeBook`).

---

## 2. The two numbers on an opportunity (§A26, §A29)

An **opportunity** is one strategy's entry signal on one symbol and bar. It must pass the ADVISORY decision
profile's hard checks: valid data, open market, SL/TP geometry, minimum RR, spread, min lot and margin.
Account-rule hits become warnings, not blocks.

### Setup strength (0–100, deterministic)

The confluence score (`app/evidence/confluence.py`):

- the strategy's condition checklist is worth up to 40 points;
- each family adds a noisy-OR of its supporting evidence, `1 − Π(1 − w·q)`, capped at the family weight;
- conflicting evidence subtracts 0.75 × its points;
- the result is clipped to 0–100.

A user's theory toggles recompute it over the families they enabled (`confidence.subset_setup_strength`).

### Win probability: P(TP is hit before SL)

**Bucket model** (`confidence.BucketModel`), always available:

- A hierarchical Beta-binomial over `strategy × symbol × strength bucket × RR band`.
  - Strength buckets: <50, 50–65, 65–80, 80+.
  - RR bands: <1.5, 1.5–2, 2–3, 3+.
- Empirical-Bayes pooling with pseudo-count κ = 20. The prior chain is
  `random baseline → strategy × RR band → strategy × asset class × RR band → leaf`.
  At each level: `a = κ·m + wins` and `b = κ·(1 − m) + losses`, where `m` is the parent's posterior mean.
- REPLAY outcomes count as at most 50 pseudo-trades per cell (`replay_cap`), so live results take over as they
  accumulate.
- Shown with a 90% credible interval and the leaf's *n*.
  - It reads "insufficient data" while the `strategy × asset class × RR band` cell has fewer than 30 outcomes.
  - Its label is `REPLAY` ("backtest-calibrated"), `LIVE` or `MIXED`.

**Evidence model** (`confidence.LogisticModel`), used only when it measurably beats the bucket model:

- L2-regularized logistic regression (numpy IRLS) per `strategy × asset class`. Groups with fewer than 200
  outcomes fall back to one pooled model. REPLAY rows have weight 0.5.
- Features (`confidence.signal_features`):
  - per detector, `ev:<FAMILY>:<id>` = the strongest supporting quality minus the strongest conflicting quality;
  - `ctx:n_families`, the number of distinct supporting families;
  - one-hot RR band, session and regime;
  - HTF alignment.
- **Model selection:** expanding-window walk-forward CV in time order, tested on LIVE rows only. The evidence
  model is used only when its Brier score is at least `min_brier_improvement` (0.5%, relative) below the
  bucket model's **and** its log loss is not worse.

**Attribution** (only when the evidence model is used):

- Shapley values in probability points split `p − base rate` exactly across the evidence that fired.
  - Up to 10 players are enumerated exactly. Above 10, seeded permutation sampling is used; it is still
    exactly efficient.
- A player left out of a coalition takes its training mean. A detector the user disabled takes its training
  mean too, because it is unknown. A detector that did **not fire** is an observed zero.
- `ctx:n_families` counts the present supporting families plus the training activity rate of each imputed
  player.
- So, with every theory enabled, the explained p equals the model's prediction, and a detector that adds
  nothing gets about 0 points.
- The bucket model's 90% interval remains the stated uncertainty.

### Baselines shown next to p

- **Random baseline:** `1 / (1 + RR)`, the TP-first probability of a driftless random walk.
- **Break-even:** `(1 + c) / (1 + RR)`, where `c` is the cost in R.
- **Expected value:** `EV(R) = p·(RR + 1) − 1 − c`.

The personalizer requires p ≥ break-even + 2 pp before it alerts.

---

## 3. Shadow trades (§A27, `shadow.py`, `shadow_tracker.py`)

Every opportunity gets two hypothetical trades, whether anyone was alerted or not, so calibration is not biased
toward alerted signals:

- **PLAN:** the signal's fixed SL and TP. This variant is the "as planned" result and the training data.
- **MANAGED:** break-even, trailing and `time_stop_bars` from `position_management`, applied at every M1 close
  with the ATR recorded at signal time.

| Step | Rule |
|---|---|
| Entry | At the decision's quote: BUY at the ask, SELL at the bid, plus `advisory.shadow.slippage_points` (1) adverse. The spread is recorded. |
| Sizing | The lot and equity snapshotted at signal time. Without a lot the trade is "not tradable at your capital" (`NOT_TRADABLE`) and counts in R only. |
| Bars | Closed M1 bars, each processed once (`cursor`). A BUY exits on the bid, a SELL on the ask (bid + the bar's spread). |
| Entry minute | Only ticks after the entry count. Without ticks, only a stop touch counts (`PARTIAL_BAR`). |
| Gap | An open beyond the stop fills at the open with slippage (`GAP`). An open beyond the TP fills at the TP, never better. |
| SL and TP in one bar | Ticks from `copy_ticks_range` decide (`TICK_RESOLVED`). Without usable ticks the SL is assumed first (`AMBIGUOUS`). |
| Time stop | The first bar opening at or after entry + 72 h closes at its open. |
| Commission | Round turn per lot: the symbol override, else `advisory.shadow.commission_per_lot`. |
| Swap | Per-lot nightly swap (S9's conversion) × rollover days. Each broker midnight (Europe/Athens) charges the day that ended; weekends are free; `swap_rollover3days` charges three. Unknown swap modes are flagged `SWAP_UNKNOWN`. |
| P/L | Broker `order_calc_profit` at the snapshotted lot, plus commission and swap. If the broker cannot value the trade, it is flagged `PNL_UNAVAILABLE`. |
| R | `r_multiple = (exit − entry)·side / (entry − initial SL)·side`. `r_net` = net P/L ÷ the money at risk to the initial stop (1-lot reference without a lot). |
| MAE/MFE | Worst and best price excursion while open, in price units and in R. |
| VOID | A fill already at or beyond the stop: not a trade, excluded from statistics. |

**Win** means the TP was hit first. A time stop, break-even or trailing exit is not a win.

State is persisted after each pass, so a restart resumes from the cursor using the terminal's M1 history.

---

## 4. Historical replay (`replay.py`)

`python -m app.cli advisory replay --server <srv> --symbols ... [--months 6 | --start/--end]` replays the scanner
over stored history. It uses the backtest's context code, every entry signal of the advisory strategy union
(no arbitration), and the ADVISORY decision profile.

- **Account:** a flat account of `--equity` (default `backtest.initial_balance`) with no positions and no loss
  state. The equity is constant, so there is no compounding.
- **Entry and resolution:** entry at the bar-close quote (bid = close, ask = close + spread). Trades are resolved
  on the finest stored of M1 and M5; the command fails without either. History has no ticks, so SL/TP ties are
  SL first.
- **Rows:** `source = REPLAY`, opportunity id `replay:<signal key>`. Reruns add only new signals; the same inputs
  give identical rows. Trades still open when the data ends are not stored.
- **Cost:** with every detector enabled, evidence costs about 1 s per bar. Narrow it with `--detectors` for
  long windows.

---

## 5. Calibration (`calibration.py`)

- **Training rows:** CLOSED PLAN shadow trades, LIVE and REPLAY. VOID trades and trades without a planned RR are
  skipped.
- **Each build** produces:
  - the bucket model;
  - the evidence model, if it wins selection;
  - the out-of-sample Brier score of the selected model;
  - reliability bins: predicted vs observed win rate in 10 equal-width bins of walk-forward predictions.
- **Versions:** `<UTC timestamp>-<content hash>` in `calibration_tables` and `evidence_model_versions`. The newest
  30 are kept. Each opportunity stores the `calibration_version` its win probability is read from.
- **Schedule:** daily after `nightly_hour_utc` (23), at the first start without a version, or on demand with
  `python -m app.cli advisory calibrate`.
  - In the engine the build runs on a worker thread.
  - A failed build keeps the previous version and retries after an hour.

---

## 6. Accuracy statistics and the theory scoreboard (`stats.py`)

Pure functions over closed PLAN shadow trades, reused by the cloud. LIVE and REPLAY are always reported in
separate sections; S8 is the only consumer that combines them, with REPLAY capped.

| Metric | Definition |
|---|---|
| Hit rate | TP first ÷ resolved, with a 90% Wilson interval |
| Expectancy | mean `r_net`, and mean `net_pnl` over trades with a lot |
| Profit factor | gross wins ÷ gross losses, in R and in money; undefined (None) without a loss |
| Total hypothetical P/L | sum of `net_pnl` at each moment's snapshotted lot |
| Follow-all curve | cumulative net P/L and R in exit order from 0; max drawdown from the running peak |
| Breakdowns | symbol, strategy, asset class, session, strength bucket, side, timeframe, watchlist (a trade counts in every list holding its symbol), alerted, followed |
| Threshold explorer | the metrics for "follow every opportunity with metric ≥ x". It is always flagged **in-sample**, because x is chosen on the same data. |
| Theory scoreboard | per detector and per family × (asset class, timeframe): n, hit rate with CI, expectancy, and lift = hit rate ÷ the group's hit rate. A trade counts once per family; conflicting evidence is not support. |

### AI opinions (TAA-1305, `app/web/ai.py`)

Optional (`ai.advisory`). The engine asks the AI once per new opportunity for a verdict AGREE / DISAGREE /
UNSURE with a confidence *c* (0–100). The AI sees the opportunity's numeric facts only and never changes a
score, probability or alert by itself. Measured against the opportunity's closed PLAN shadow trade:

| Metric | Definition |
|---|---|
| Right rate | (AGREE and TP first) + (DISAGREE and SL first), ÷ judged AGREE/DISAGREE opinions |
| Per verdict | n, hit rate and mean R of the trades the AI agreed with, disagreed with, was unsure about |
| Implied p | AGREE → *c*/100, DISAGREE → 1 − *c*/100, UNSURE → 0.5 (the AI's implied P(TP first)) |
| Calibration | implied p in buckets of 0.2: n, mean implied p, observed hit rate |
| Brier score | mean (implied p − outcome)², shown beside always predicting the window's base hit rate (in-sample) |
| Filter evaluation | mean R of AGREE trades − mean R of all, with a seeded bootstrap 95% interval (1000 resamples) |

The opt-in alert filter (`alerts.ai_filter`) is **offered** only when, over 90 days, at least 30 judged AGREE
opinions and 50 judged opinions exist and the interval lies wholly above 0. While offered and switched on,
DISAGREE / UNSURE opportunities are not pushed; an opportunity whose opinion has not arrived after 90 s is
pushed as usual. The evaluation is in-sample like the threshold explorer, and it is re-checked every 10
minutes, so the offer can disappear again.

---

## 7. Assumptions and caveats

- **Fills are simplified.** There are no requotes, partial fills, real slippage, liquidity limits or broker
  rejections. Replay enters at bar closes, not at live quotes.
- **Bar-based resolution.** M1 bars are pessimistic: SL-first ties, and stop-only counting in an entry minute
  without ticks. Replay on M5 is coarser still. Flags (`AMBIGUOUS`, `PARTIAL_BAR`, `GAP`) show where these
  approximations applied.
- **Costs are estimates.** Commission comes from config. Swap uses the symbol's current rates and supports only
  the points and deposit-currency modes. Replay values money at the conversion rate of the signal time.
- **Selection effects.** Every opportunity is tracked, alerted or not, to avoid alert bias. The threshold
  explorer is still in-sample and overstates what a chosen threshold would have earned.
- **Small samples.** Intervals and the "insufficient data" state are part of the result. A hit rate without its
  interval and *n* must not be shown.
- **Non-stationarity.** Calibration and scoreboard figures describe the past window only. Markets, spreads and
  broker conditions change.
- **AI text is opinion.** AI narratives and opinions are labelled "AI opinion, not advice". A text claiming
  profit or certainty is refused before it is stored, but the wording is still the model's, not a measurement.
- **Heuristic theories.** Tier-T3 detectors (Elliott) are labelled heuristic. A theory's weight comes from
  measured outcomes, not from its popularity.
- **Not advice to trade.** The numbers describe hypothetical past behaviour. Subscriptions stay disabled until a
  legal review (Thai SEC advisory licensing, PDPA; PLAN §A30).
