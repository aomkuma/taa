# Chart read — the bot reads a chart the way a trader does

Status: **CR-1 done (2026-10-14): `app/indicators/chart_read.py`, `context_map.chart_read`; the port matches
the terminal's ZigZag on 15 of 15 exports** (§4.8). CR-2 in work; the rest is a plan (owner, 2026-10-14). Ticket: TAA-L813 in
`docs/TICKETS_LEARNING.md`. Related: `docs/CONFLUENCE_DIRECTION.md` (TAA-L812, which this read feeds),
`docs/STRATEGIES.md` ("A signal alone is not enough"), `docs/PLAN_LEARNING.md` §L20.9 (the market map),
`docs/SETUP_REVIEW.md` §15-§16. No profitability claims: this is a plan to measure, not a result.

## 1. The owner's question (2026-10-14, in Thai, summarized)

The owner showed a chart with a zigzag, a falling trendline and horizontal levels and asked which way it trends.
The answer was a short-term down trend (two rounds of lower highs and lower lows) testing a support, with
two scenarios: a break that holds (down to the next support) or a false break that reclaims the level (a
rally into the broken levels above, now resistance, where a sell with the trend sits better). The owner then
asked: **how does the bot get to read a chart the same way?**

The reading took five steps, and each one is something the code can do deterministically:

1. **Major swings**: the zigzag legs a trader draws, not every three-bar wiggle; each swing labelled HH, HL,
   LH or LL against the previous swing of its kind.
2. **Structure**: LH + LL is a down trend; it ends only when price closes above the last lower high (the
   invalidation). LH + HL (contracting, the "ABCDE" triangle the owner sees before gold picks a side) and
   HH + LL (broadening) are neither.
3. **Levels with a role**: horizontal levels at the swings; a support that price closed through becomes a
   resistance (and the reverse).
4. **Trendline and position**: the line through the last two lower highs (or higher lows), and how deep the
   current move has gone into the previous leg (in the example, about 68 % of the prior up leg).
5. **Scenarios at the level**: a break that holds, or a sweep that closes back (a false break), each with its
   trigger and invalidation price.

## 2. What the bot sees today (measured, 2026-10-14)

Scripts: `research/2026-10-14-chart-read/structure_read.py`, `structure_trades.py` (one year of FBS-Demo history,
2025-10 .. 2026-09; the trades are the backtests that made harmonic V1 and breakout F1 pass, SETUP_REVIEW §15-§16).

Three ways to read the trend:

- **A, the market map state** (`app/indicators/market_map.py`, `state_frame`): UP/DOWN need ADX ≥ 20, an
  efficiency ratio ≥ 0.3, close and EMA50 on one side of EMA200 and a fractal structure not against.
  The setups' Elder screens (`screen_h4` / `screen_h1`) read this.
- **B, the fractal structure** (`market_structure`, k = 3: a swing is any bar higher than 3 bars on each side).
  `_structure_with` and `_not_broadening` read this.
- **C, the major-swing structure**: pivots of the ATR zigzag (`app/evidence/zigzag.py`, 3 × ATR14, the
  `intermediate` degree of `evidence.zigzag_degrees`) labelled HH/HL/LH/LL. This is the read a trader draws.

| Read (mean of XAUUSD, EURUSD, GBPUSD, USDJPY) | Bars it calls a trend | Label changes / 1,000 bars | Next 24 bars go its way |
|---|---|---|---|
| H1, A map state | 17 % | 3.4 | 48 % |
| H1, B fractal k=3 | 58 % | 33.8 | 50 % |
| H1, C major swings | 65 % | 9.0 | 50 % |
| H4, A map state | 19 % | 3.1 | 48 % |
| H4, B fractal k=3 | 62 % | 36.5 | 50 % |
| H4, C major swings | 68 % | 9.3 | 48 % |

- **The bot rarely sees a trend.** On XAUUSD H1, when the major swings say DOWN the map says DOWN on 15 % of
  those bars, TRANSITION on 61 % and RANGE on 17 %. A chart like the owner's is mostly "no trend" to the bot.
- **The bot's swing labels are noisy.** The three-bar fractal swings change label about 3.7 times as often as
  the major swings.
- **A trend read on its own does not predict the next move** (about 50 % either way, for every read). Structure
  is context for a setup's trigger, not a signal. This matches the system rule: a signal alone is not enough,
  and neither is context alone.

The proven setups' trades, split by the H1 major-swing structure at entry (relative to the trade's side;
"mixed" = contracting or broadening). The 90 % interval is a bootstrap of the mean; the halves split at 2026-04-09:

| Setup | H1 structure vs the trade | Trades | R/trade | 90 % interval | 1st half / 2nd half |
|---|---|---|---|---|---|
| harmonic V1 | with | 39 | **+0.715** | +0.343 .. +1.094 | +0.824 / +0.588 |
| harmonic V1 | mixed | 75 | **+0.009** | −0.255 .. +0.288 | −0.065 / +0.156 |
| harmonic V1 | against | 67 | +0.144 | −0.129 .. +0.429 | +0.287 / −0.081 |
| breakout F1 | with | 70 | **+0.203** | +0.097 .. +0.303 | +0.258 / +0.147 |
| breakout F1 | mixed | 22 | **−0.005** | −0.262 .. +0.202 | −0.025 / +0.037 |
| breakout F1 | against | 7 | +0.233 | −0.166 .. +0.447 | +0.159 / +0.418 |

With the 3 × ATR swings, the mixed phase looked like the place where both setups earn nothing, and harmonic
with the H1 swing structure looked strongest. **The owner then chose the MT5 standard ZigZag (Depth 12,
Deviation 5, Backstep 3) as the swing definition** (2026-10-14), and the same measurements with it
(`research/2026-10-14-chart-read/mt5_zigzag.py`) give:

| Read (MT5 ZigZag 12/5/3, mean of the 4 symbols) | Bars per pivot | Trend | Contracting | Broadening | Label changes / 1,000 bars | Next 24 bars go its way |
|---|---|---|---|---|---|---|
| H1 | 17.6 | 60 % | 21 % | 18 % | 10.8 | 51 % |
| H4 | 18.4 | 62 % | 21 % | 15 % | 10.7 | 48 % |

On XAUUSD H1, when the MT5 swings say DOWN, the map says DOWN on 13 % of those bars and TRANSITION on 62 %.

| Setup | MT5 structure vs the trade | Trades | R/trade | 90 % interval | 1st half / 2nd half |
|---|---|---|---|---|---|
| breakout F1 | H1 with | 66 | +0.077 | −0.052 .. +0.203 | +0.094 / +0.058 |
| breakout F1 | H1 mixed | 21 | **+0.395** | +0.259 .. +0.474 | +0.470 / +0.296 |
| breakout F1 | H1 against | 12 | +0.193 | −0.048 .. +0.427 | +0.067 / +0.444 |
| breakout F1 | H4 with | 45 | +0.155 | −0.000 .. +0.289 | +0.269 / +0.037 |
| breakout F1 | H4 mixed | 29 | **+0.402** | +0.304 .. +0.459 | +0.469 / +0.340 |
| breakout F1 | H4 against | 25 | **−0.118** | −0.345 .. +0.105 | −0.182 / +0.048 |
| harmonic V1 | H1 with | 33 | +0.085 | −0.318 .. +0.489 | +0.300 / −0.117 |
| harmonic V1 | H1 mixed | 86 | +0.167 | −0.090 .. +0.434 | +0.083 / +0.331 |
| harmonic V1 | H1 against | 62 | **+0.339** | +0.043 .. +0.646 | +0.417 / +0.208 |
| harmonic V1 | H4 with | 37 | +0.316 | −0.086 .. +0.721 | +0.513 / +0.026 |
| harmonic V1 | H4 mixed | 77 | +0.176 | −0.089 .. +0.443 | +0.292 / −0.051 |
| harmonic V1 | H4 against | 67 | +0.193 | −0.094 .. +0.477 | −0.010 / +0.476 |

**What holds and what does not:**
- **Robust under both swing definitions:**
  - the map state calls a trend on far fewer bars (17-19 %) than a swing read (about 60-68 %);
  - the fractal labels are three times noisier;
  - a trend read alone does not predict the next 24 bars.
  The chart read is worth building for these reasons alone.
- **Not robust: the trade splits.** With 3 × ATR swings, the mixed phase was the worst cell for both setups;
  with MT5 12/5/3 it is the best one for breakout F1 (a fade of a break inside a triangle or a megaphone, the
  owner's "ABCDE" false breaks). Harmonic flips from "with H1" to "against H1". Cells of 12-86 trades over one
  year cannot carry a rule on their own.
- **So no setup rule is taken from these tables.** The rules are chosen on the first half and judged on the
  second half and the hold-out symbols (§8), with the MT5 definition, and only adopted after the backtest
  ladder.

## 3. Goals and non-goals

**Goals:**
- One **chart read per timeframe**, computed once and shared by every setup, the decision record, research and
  the PWA.
- **Deterministic and lookahead-free**: only closed bars and confirmed pivots, with no repainting. A read at bar t
  equals the read computed on the data cut at t.
- **Explainable**: every fact carries its prices and distances in ATR, so a decision can say why.
- **Measured before used**: every fact is recorded on every signal as a `ctx:` feature, and a setup opts into a
  rule only after its backtests hold (owner's selection rules, CLAUDE.md).
- **Visible**: the PWA draws the bot's read on the chart, so the owner can check by eye that the bot sees what
  they see.

**Non-goals:**
- **Not a trigger or a setup of its own.** `setup_confluence` (TAA-L812) may build on it later.
- **No machine learning and no "drawn by eye" rules.** Every definition is a formula with explicit tolerances.
- **No change to today's decisions until a setup opts in.** Every new setup parameter is off by default.

## 4. The read (`app/indicators/chart_read.py`, pure, indicators layer)

One `ChartRead` per timeframe at one instant (the last closed bar), attached to `TimeframeMap.read`.

### 4.1 Swings

- **Pivots: the MT5 standard ZigZag** (Depth 12, Deviation 5 points, Backstep 3; owner, 2026-10-14), so the
  bot's swings are the ones the owner sees on the MT5 chart. It is ported from MetaQuotes' `ZigZag.mq5`
  (research version: `research/2026-10-14-chart-read/mt5_zigzag.py`) in two passes:
  1. **Maps:** the lowest low / highest high of the last `depth` bars is a candidate, and a new candidate
     erases weaker ones of the last `backstep` bars.
  2. **Cutting:** the candidates are made to alternate high/low; a lower low replaces the pending low while the
     indicator is searching for a peak, and the reverse.
- **No repainting:** MT5 redraws its last leg, and the bot may not. A pivot is used only once it is **fixed**
  (the opposite pivot has been registered), and only `backstep` bars after that, when the candidate maps it
  was cut from are final. A live run therefore knows at bar t exactly the pivots the read uses at t.
  - The port has to match MT5 on the owner's charts. A test compares it with ZigZag values exported from the
    MT5 terminal (a script on the owner's machine, a few hundred bars per timeframe).
- **Settings:** `depth` / `deviation` / `backstep` can be overridden per timeframe (`chart_read.by_timeframe`).
  The ATR zigzag (`app/evidence/zigzag.py`) stays for the evidence detectors.
- **Labels:** the last `max_swings` (8) confirmed pivots, each labelled with `label_structure` (HH/HL/LH/LL,
  EQH/EQL within `equal_atr` × ATR = 0.1).
- **Leg in progress:** the running extreme since the last pivot. It is reported separately as the current leg
  and **never used as a pivot**.

### 4.2 Structure

| Field | Rule |
|---|---|
| `trend` | UP = last high HH and last low HL; DOWN = LH and LL; CONTRACTING = LH and HL; BROADENING = HH and LL; FLAT = an EQH/EQL in the pair; NONE before two labelled pivots of each kind |
| `invalidation` | DOWN: the last LH's price; UP: the last HL's price; else none |
| `broken` | a close beyond the invalidation since the last pivot (a change of character before a new pivot confirms) |
| `age_legs` | pivots since the trend value last changed |

### 4.3 Levels with a role

- **Source:** the pivots of the read's degree over `level_lookback` bars (300), clustered within
  `level_tol_atr` (0.5) × ATR. A level is the cluster's mean, with its touch count, first and last pivot.
- **Role** against the last close:

  | Role | Meaning |
  |---|---|
  | SUPPORT / RESISTANCE | below / above the close, never closed through |
  | FLIPPED | closed through an odd number of times, now on the other side (a broken support is now resistance) |
  | SPENT | closed through `spent_crossings` times (rules: 2; the PWA chart: 4); dropped from the read |

  Fewer crossings than that on the side where it formed keep the level's first role.
- **Minor swings** (`minor_depth`; rules: 0 = off, the PWA chart: 5): a second ZigZag adds the levels near the
  price a trader also draws; a cluster made only of minor pivots is `Level.minor` (drawn thin). A minor pivot
  on a major pivot already known at the bar is not counted twice (no look-ahead).
- **The read now** (`prov_atr`, 1.0): the open leg's extreme becomes a provisional pivot once price came back
  `prov_atr` × ATR from it, labelled against the last pivot of its kind; `structure_now` and
  `invalidation_now` count it. It can still move, so rules use the confirmed read first; the PWA draws it
  dashed with "?". `ChartReadParams.for_display()` is what the chart draws; rules keep the defaults until a
  backtest passes the change. Eye check against a blind sub-agent on the 20 charts
  (`research/2026-10-14-chart-read/eye_check_score.py`, 2026-10-15): trend 6/20 → 11/20, both levels within
  0.5 ATR 1/20 → 5/20.

- **Retests:** for a FLIPPED level, the bars that touched it from the new side and closed away (`retests`).
- **Nearest:** the nearest support and resistance below and above (FLIPPED included), with distances in ATR;
  at most `max_levels` (6) per side.

The market map's demand/supply zones (bases before displacement) stay as they are. The read's levels are line
levels from swings. If the measurement shows the two say the same thing, they are merged later.

### 4.4 Trendline

- **Line:** through the last two LH (DOWN or CONTRACTING tops) or the last two HL (UP or CONTRACTING bottoms),
  the same construction as the `Trendline` evidence detector.
- **Fields:** the slope in ATR per bar, the close's signed distance to the line in ATR, touches within
  `tol_atr` (0.25), and `broken` (the first close beyond the line by the tolerance).

### 4.5 Position

- `retrace`: how far the current leg has gone back into the previous leg at the read's degree (0 .. 1+).
- `retrace_major`: the same against the last leg of the next-higher timeframe's read (H1 → H4, H4 → D1). In
  the owner's example: 0.68 of the prior up leg.
- `from_pivot_atr`, `leg_atr`, `leg_bars`: the distance from the last pivot, and the length of the current leg.

### 4.6 Events at levels (the last `event_bars`, 3, of this timeframe)

| Event | Rule |
|---|---|
| BREAK_HOLD | a close beyond a level (or the trendline) by `tol_atr` × ATR, and the next `hold_bars` (1) closes stay beyond |
| SWEEP_RECLAIM | a high/low beyond the level by the tolerance, and a close back on the original side within `reclaim_bars` (1): a false break, the `LiquiditySweep` rule applied to the read's levels |
| RETEST | a bar touches a FLIPPED level from its new side and closes away from it |

Each event has a direction, the level and the bar it happened on.

### 4.7 Scenarios (text only)

From §4.2-§4.6 the read writes the two main paths with their trigger and invalidation prices, for the decision
explanation and the PWA. Example: "break below 2,345 that holds → next support 2,318; reclaim above 2,345 →
resistance 2,361-2,366; the down trend ends above 2,384". The engine never acts on this text.

### 4.8 Notes from building CR-1 (2026-10-14)

- **The port is the full-calculation path of MetaQuotes' `ZigZag.mq5`** (version 1.00, read from the owner's FBS
  terminal). A live chart recalculates only its last three extremes with its tie memory reset, so a chart left
  open can differ from a fresh calculation on equal-high/low bars of its last legs.
- **The swing read lags by about one leg.** In a straight leg the backstep erases every candidate but the
  extreme, so a pivot is fixed only once the next leg's extreme has held `backstep` bars. On FBS-Demo history
  (XAUUSD, EURUSD, GBPUSD, USDJPY; M15, H1, H4) the median lag from the pivot bar is 11-12 bars (p90 about
  21-23) against a median leg of 13-14 bars. The §2 measurements used the same rule. `broken` (§4.2) and the
  leg in progress (§4.5) are the read's early signs of a turn.
- **A false break does not spend a level.** A close through counts only when the next `hold_bars` closes stay
  beyond the level (the BREAK_HOLD rule), so a level that was swept and reclaimed keeps its role and carries
  the SWEEP_RECLAIM event.
- **`retrace` uses the close** (the position inside the previous leg: 0 at the last pivot, 1 back at the one
  before), not the leg's extreme; the extreme is in `leg.extreme` / `leg_atr`. `retrace_major` is the close
  inside the next-higher timeframe's last leg (`with_major`).
- **Trendlines:** a CONTRACTING read has both lines; DOWN only the falling-tops line, UP only the rising-bottoms
  line; none when the last two tops (bottoms) do not fall (rise).
- **Runtime:** about 2 ms per read on H1 (300-bar level lookback), one read per context bar and symbol.
- **The check against MT5 (2026-10-14): an exact match.** `scripts/mt5/TAA_ExportZigZag.mq5` (a read-only
  script) ran headless in the FBS demo terminal (`/config` with `[StartUp] Script=…, ShutdownTerminal=1`, the
  DEMO stack paused for one minute) and wrote the ZigZag buffer and its maps for XAUUSD, EURUSD, GBPUSD,
  USDJPY and AUDUSD × M15/H1/H4, 3,000 closed bars each. `scripts/compare_zigzag.py`: 15 of 15 files match,
  2,513 fixed pivots and every candidate-map bar equal (past the warm-up, before MT5's redrawn last leg). Two
  files (800 bars each) are test fixtures (`tests/fixtures/mt5_zigzag/`).

### 4.9 CR-2 built (2026-10-14)

- `TimeframeMap.read` (only in the map's dict when present: older decision records and their digests load and
  verify unchanged); `MapBook.at(..., point)` builds the read of every context timeframe (the swings once per
  candle frame, the read once per context bar) and sets `retrace_major` from the next-higher context
  timeframe. The backtest, the replay and the live context builder pass the symbol's point; the PWA's map
  endpoint does not yet (CR-4).
- The `ctx:<tf>_*` features of §6 come from `read_features` (`app/indicators/market_map.py`). `inv_r` =
  (entry − invalidation) × side / risk: positive when the invalidation lies behind the entry (below 1 the stop
  is beyond it), negative when it lies ahead.
- Only the context timeframes are read, not the entry timeframe: an M15 (or M1) read on every entry bar would
  cost far more than the budget, and the setups' screens are context timeframes. An entry-timeframe read can be
  added by listing it in `timeframes.context`.
- **Budget and golden check** (breakout F1, March 2026, 8 symbols, run side by side): 1,234 s with the read,
  1,216 s without (+1.5 %); both runs and the earlier baseline give the same 12 trades (identical entries,
  stops, targets and results).

## 5. Where it runs

- **Computation:**
  - `chart_read.py` is pure, in the indicators layer. `MapBook` (`app/strategy/market_maps.py`) builds it next to
    each context timeframe's map.
  - Zigzag pivots are computed once per timeframe over the loaded bars (prefix-consistent), then sliced to the
    pivots confirmed at or before the decision bar.
  - Levels, trendline and events are computed per decision from at most a few dozen pivots.
  - Budget: backtest runtime +10 % at most, measured in a test.
- **Timeframes:** every context timeframe (`timeframes.context`, now H1/H4/D1) plus the entry timeframe.
  For M1 scalping: M15, M30 and H1 (the owner's screens for M1).
- **Persistence:**
  - The read goes into the market map's dict only when present, so the digests of older decision records stay
    valid.
  - `from_dict` accepts maps without it.
- **Config:** a new `context_map.chart_read` block (`extra="forbid"`):

  ```yaml
  context_map:
    chart_read:
      enabled: true          # computed and recorded; no setup uses it until its params say so
      depth: 12              # MT5 standard ZigZag (owner, 2026-10-14)
      deviation: 5           # points
      backstep: 3
      equal_atr: 0.1
      level_lookback: 300
      level_tol_atr: 0.5
      max_levels: 6
      tol_atr: 0.25
      event_bars: 3
      hold_bars: 1
      reclaim_bars: 1
      by_timeframe: {}       # e.g. M1: {depth: 24}; only if the owner's charts use other settings
  ```

## 6. Features on every signal (`signal_features`, `ctx:<tf>_*`)

All features are relative to the trade's side, so the same number means the same thing for a BUY and a SELL:

| Feature | Value |
|---|---|
| `sw_trend` | +1 with the trade, −1 against, 0 otherwise |
| `sw_phase` | 0 trend, 1 contracting, 2 broadening, 3 flat, absent before the warm-up |
| `sw_age` | legs since the structure last changed |
| `sw_broken` | 1 when the trend's invalidation was closed through since the last pivot |
| `inv_r` | the distance from the entry to the invalidation, in R (negative if the stop is beyond it) |
| `lvl_with_atr` | the distance to the nearest level on the trade's side (support for a BUY; FLIPPED counts) |
| `lvl_against_r` | the room to the nearest opposing level, in R (capped at 10) |
| `lvl_flipped` | 1 when the entry sits within `tol_atr` of a FLIPPED level on the trade's side (a retest entry) |
| `tl_atr` | the signed distance to the trendline, in ATR (positive = on the trade's side) |
| `retrace`, `retrace_major` | §4.5 |
| `ev_break_hold`, `ev_sweep_reclaim`, `ev_retest` | +1 with the trade, −1 against, 0 none (last `event_bars`) |

`research hypotheses` reads them like the existing `ctx:` features, so every fact can be crossed with every
setup's trades without new tooling.

## 7. Setup parameters (all off by default; each one on per setup only after §8 holds)

| Parameter | Values | What it does |
|---|---|---|
| `screen_source` | `map` (default) / `swings` | Elder's screens (`screen_h4`, `screen_h1`) read the major-swing trend instead of the map state; the same gates (`with`, `not_against`, `against_or_range`, …) apply, with MIXED counted as range |
| `structure_tf` + `structure_gate` | timeframe; `off` / `not_against` / `with` | the swing structure of one timeframe must not be against (or must be with) the trade |
| `mixed_rule` | `any` / `surest` / `skip` | in a CONTRACTING or BROADENING phase: trade normally, only the surest signals, or not at all. `surest` = the setup's stricter condition set (v1: the next-higher timeframe's swing trend with the trade **and** the entry at a supportive or flipped level); the system principle says `surest` before `skip` |
| `level_gate` | `off` / `at_level` | the entry within `tol_atr` of a supportive or flipped level |
| `room_min_r` | number / none | at least this much room to the nearest opposing level |
| `stop_mode: structure` | | the stop beyond the invalidation pivot plus a buffer, capped by `max_sl_atr` |
| `false_break_entry` | off / on | wait for a SWEEP_RECLAIM in the trend's direction at a level (the owner's observation on gold); a later stage |

Each one becomes a `Condition` with a TH/EN label (frontend `common.json`) and its numbers in the detail, like
today's screens.

**Built (CR-5, 2026-10-14), `app/strategy/setups.py`:** `screen_source`, `structure_tf` (default H1: the one read
every gate below uses), `structure_gate`, `mixed_rule`, `level_gate: at_level`, `room_min_r` and
`structure_stop`. All are judged on the trade actually taken (for a fade, the fade's side) at the plan's entry; a
missing read holds (condition `chart_read`). Two choices made while building:
- `stop_mode: structure` became a separate switch, **`structure_stop: true`**: a fade mirrors the trigger plan,
  whose stop becomes the fade's target, so a stop mode of the plan cannot move the fade's stop. The switch moves
  the stop of the trade taken beyond the last swing pivot behind the entry (`stop_buffer_atr` × ATR plus the
  spread, at most `max_sl_atr` ATR) and keeps the target's R multiple.
- `screen_source: swings` also drives the fade's "against both screens" test, so a fade reads the same trend
  the screens do.

## 8. Measurement and adoption (theory a third, measured behaviour the rest)

- **M0, done (2026-10-14):** §2.
- **M1, features on the year:**
  - Build §4-§6 and replay the year of the proven setups with the features recorded.
  - Cross each feature with the trades: R per trade, 90 % interval, both halves, and the hold-out symbols
    (AUDUSD, XAUUSD).
  - **Walk-forward choice:** at most three rules per setup, chosen on the **first half only** (before
    2026-04-09) from the §7 parameters, written down, then judged on the second half and the hold-out symbols.
    §2 shows why: one year's split changes with the swing definition, so a rule read off the full year would
    be fitted to it.
  - **Candidates to check first** (from §2, not adopted):
    - breakout F1: `structure_gate: not_against` on H4 (H4 against −0.118), and whether the mixed phase is its
      best phase rather than its worst;
    - harmonic V1: `structure_gate` against vs with on H1;
    - both: `screen_source: swings`.
- **M2, backtest ladder per setup** (CLAUDE.md):
  - Order: March 2026 → August 2026 → the full year.
  - A variant whose first run is negative is dropped; only the profitable ones (or the least-losing one) go on.
  - Start with **breakout F1** (the setup in work; owner, 2026-10-14), then harmonic V1. The other setups get
    the read as they are reworked, one at a time.
- **Bar to adopt:**
  - ≥ +0.15 R/trade net (about ±0.05);
  - the 90 % interval's lower bound > 0 in both halves;
  - max drawdown ≤ 15 R;
  - the portfolio's trade count (≥ 300 a year across all setups) is not cut without the owner's say.
- **Owner's eye check, before any rule gates trades:**
  - The PWA overlay (§9) on 20 charts **the bot picks** (owner, 2026-10-14): a sample across the 8 symbols,
    M15/H1/H4 and the phases (up, down, contracting, broadening, a flipped level, a sweep that reclaims, a break
    that holds), drawn from the year's history at random within each group, not chosen by result.
  - The bot's trend and its two nearest levels must agree with the owner's reading on at least 16 of them.
  - Every disagreement becomes a test fixture and, if the owner's reading is the right one, a fix.

## 9. PWA overlay

- **On the chart:** the read's pivots with their labels, the trendline, the levels coloured by role (support,
  resistance, flipped), the invalidation line, and the scenario text (§4.7). One toggle per timeframe.
- **Data:** the read travels with the chart data the PWA already gets from the engine. Its fields are validated
  with zod, and its texts go through i18n keys (TH default, EN).
- **No claims:** no probability or profitability wording (`catalogs.test.ts` checks this).

**Built (CR-4 code, 2026-10-14; the eye check with the owner is pending):**
- `GET /engines/{id}/market-map?...&read_tf=TF` adds `read`: that timeframe's chart read at the map's instant,
  from the engine's uploaded bars (the last 1,500) and the symbol's point in its catalog; `null` without bars,
  without a point, or with `context_map.chart_read.enabled: false` in the engine's config. Without `read_tf`
  the response is as before.
- The charts page: a "Chart read" toggle (`read=1` in the URL) draws the confirmed swings with their labels,
  the trendlines, the levels coloured by role (green support, red resistance, orange flipped) and the
  invalidation (pink dotted), and a panel states the structure, the invalidation, the depth in the last leg,
  the events and the two scenarios (TH/EN keys `charts.read.*`; no probability wording). `end=` (any ISO time)
  shows the chart and the read as they were then, without live refresh.
- The 20 charts: `research/2026-10-14-chart-read/EYE_CHECK.md`, drawn by `eye_check_sample.py` (seed 20261014;
  every symbol, M15/H1/H4, about three per group: UP, DOWN, CONTRACTING, BROADENING, a flipped level within
  1 ATR, SWEEP_RECLAIM, BREAK_HOLD), each with a link that opens the chart at that bar. Before the check the
  PWA needs the new build and a web restart, and the cloud needs the year's bars of the 8 symbols on M15/H1/H4
  (`app.cli sync upload-history`).

## 10. Safety and tests

- **No look-ahead:** for random cut points t, the read on the data cut at t equals the read at t on the full data
  (property test). Confirmed pivots never move.
- **Synthetic paths:**
  - a staircase down gives DOWN with the invalidation at the last LH;
  - a triangle gives CONTRACTING; a megaphone gives BROADENING;
  - a level closed through gives FLIPPED, and a later touch gives RETEST;
  - a wick through and a close back gives SWEEP_RECLAIM; two closes beyond give BREAK_HOLD.
- **Fixtures from the eye check:** the 20 sampled charts (§8), with the owner's reading where it differs.
- **Unchanged until opted in:** with every new setup parameter at its default, the decisions of the existing
  backtests are identical (golden comparison on March 2026); old decision digests verify.
- **Plumbing:** serialization round-trip, config validation, the architecture layer table, and frontend parity
  for the new condition names and reason texts.
- **Performance:** the runtime budget test from §5.

## 11. Steps (TAA-L813)

| Step | Content | Depends on |
|---|---|---|
| CR-1 | `chart_read.py` (§4), config (§5), tests (§10) | — |
| CR-2 | `MapBook` + market document + `ctx:` features (§6); research reads them | CR-1 |
| CR-3 | M1 measurement on the proven setups' year (§8) | CR-2 |
| CR-4 | PWA overlay + the owner's eye check (§9, §8) | CR-2 (can run next to CR-3) |
| CR-5 | setup parameters (§7) with TH/EN labels and tests | CR-1 |
| CR-6 | M2 ladder: breakout F1, then harmonic V1; SETUP_REVIEW sections; config.yaml only for what passes | CR-3, CR-4, CR-5 |
| CR-7 | the read feeds `setup_confluence` (TAA-L812) and the M1 scalping screens (M15/M30/H1) | CR-6 |

Order against the work in progress (2026-10-14): after the M1 scalping S1 ladder and the aggressive preset
merge, unless the owner says otherwise. Full pytest + vitest run at the end of the round (CLAUDE.md); targeted
tests and lint per step.

## 12. Risks and open questions

**Risks:**
- **Overfitting:** many facts × several setups. Countered by at most three pre-registered rules per setup, both
  halves, the hold-out symbols and the March/August/year ladder.
- **Fewer trades:** a gate removes trades. `mixed_rule: surest` before `skip`, and the portfolio's trade count is
  reported with every result.
- **Results depend on the swing definition** (§2: the trade splits flip between 3 × ATR and MT5 12/5/3).
  The definition is fixed to the owner's MT5 standard before any rule is chosen, and is never tuned to a
  backtest.
- **One setting for every symbol and timeframe may not fit.** `by_timeframe` overrides exist, but they are used
  only to match the owner's charts, not to fit results.
- **The swing read is slower to turn than the price:** a pivot is fixed only after the opposite pivot appears
  (plus 3 bars). `broken` (§4.2) catches the turn earlier; whether to trust it is measured, not assumed.
- **The port may differ from MT5 on some bars** (ties, equal highs, the first bars). This is checked against
  values exported from the terminal before CR-2.

**Decided (owner, 2026-10-14):**
- the swing definition is the MT5 standard ZigZag 12/5/3;
- the bot picks the eye-check charts itself (§8);
- breakout F1 first, then harmonic V1;
- the eye check passes with 16 agreements out of 20 charts.
