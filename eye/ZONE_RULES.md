# The run-zone setup - the specification

**This file is the specification of the run-zone setup** - its rules, parameters, outputs and the acceptance cases a
build must pass. Where the rules came from: METHOD 2e, the row "The run zones" (the owner's words, 2026-11-01). Every
form tried, and every number below: `eye/BOT_RESEARCH.md`, from "The owner's run zones, drawn" to "Price far from its
mean in H1 ATR units". The prototype the measurements came from is **`eye/research/zone_reference.py`** (the
reference); a build must reproduce its trades (rule 12). Where the reference and this file differ, this file wins
and the difference is reported, never silently copied.

Each rule says whose it is: **(owner)** - the owner's rule or words; **[Claude]** - a form or number Claude gave where
the owner gave none: a named parameter with a default, for the owner to change. A question or a chart the owner shows,
and any number inside one, is never a rule.

## 0. A setup of its own (the owner, 2026-11-01: *"careful that conditions from the old setup do not make the system
## contradict itself - if possible, split it into a new one"*)

- **Separate from the Fibonacci bot** (`eye/BOT_RULES.md`, `eye/bot2e.py`): no rule, parameter, function, file or
  database table of that bot is used, changed or imported, and that bot does not import this one. Shared only:
  the stored bars (`data/history/FBS-Demo/XAUUSD`), `app.indicators.chart_read.zigzag_pivots`, and the database
  *file* `data/bot_config.db` (a table of its own, rule 1).
- **Files**: `eye/zone_bot.py` (the setup, a run on stored bars), `eye/zone_config.py` (its parameters, rule 1),
  `tests/unit/test_zone_bot.py` and `tests/unit/test_zone_config.py`; outputs under `eye/research/zone/` (rule 11).
- **No order is sent anywhere.** It is a simulation on stored bars, like the reference. DEMO / LIVE are not part of
  this build and need the owner's word.

## Words used

- **Closed bars only** (the project's rule): at a time `now` a bar of timeframe `tf` exists only if its close time
  (`close_time`) is at or before `now`. Times in the data are UTC; Thai = Asia/Bangkok, used for months and reading.
- **Fixed pivot** - a pivot of `zigzag_pivots(high, low, point)` (MT5's ZigZag 12 / 5 / 3, owner) run on **all stored
  bars of the timeframe from the first bar in the file** [Claude] (not a rolling window - the reference does this, and
  a run's start must not change the pivots: BOT_RESEARCH, "The whole system in one run", the 01/05 / 04/05 difference).
  A pivot is **known** from the close of its `confirm_pos` bar. Used: H4 (zones), and D1 / H4 / H1 / M15 (the state).
- **The step `S`** - the box, the run of gold (owner: *"the zone is a box of the run"*), rule 2.
- **A grid** - an anchor `A` and a step `S`; its **lines** are `A + k * S` for every integer k (rule 3).
- **BUY / SELL** - every rule is written for both sides; `sgn` = +1 for a BUY (price came **down** to a line), -1 for a
  SELL (price came **up** to it).
- **Point** - the symbol's `point` from `spec.json` (0.01). **USD** - at 0.01 lot a position, 1.00 of price = 1 USD
  (contract 100).

## Parameters (rule 1: read from the database; this table is the seed)

| name | default | meaning | whose |
|---|---|---|---|
| `step_mode` | `watr` | `watr` = `step_factor` x weekly ATR(14); `fixed` = `step_fixed` | owner: *"the zone may be 1/2 - 1/3 of the ATR"*; the form [Claude] |
| `step_factor` | 0.3333 | x the weekly ATR | owner's range 1/3 - 1/2; 1/3 measured (BOT_RESEARCH - a narrow peak: 0.3 and 0.4 much lower) |
| `step_fixed` | 76.0 | the step when `fixed` | owner (*"about 80"*, the lines of 01/11/2026) |
| `grid_ks` | 1,2,3 | a cluster spans k steps | [Claude] (the owner's boxes were 2 steps; v8) |
| `grid_tol` | 0.10 | a pair's distance within this x S of k S | [Claude] |
| `shift_tol` | 0.20 | a new anchor more than this x S off the lines shifts the grid | [Claude] (the owner: the leftover is the fake-break distance) |
| `step_remake` | 0.20 | a month's step this far (relative) from the grid's step remakes the grid | [Claude] |
| `near_frac` | 0.131579 (10/76) | a visit: within `near_frac` x S of a line | [Claude] |
| `away_frac` | 0.5 | a line is armed again once a whole H1 bar is this x S away; orders withdrawn at this x S away | [Claude] |
| `p1_frac` | 0.131579 (10/76) | P1 - this x S before the line | owner: *"one before price"*; the number [Claude] |
| `p2_frac` | 0.197368 (15/76) | P2 - this x S past the line (in the fake break) | owner: *"one on the fake break"*; the number [Claude] |
| `sl_frac` | 0.5 | SL this x S past the line, for both | owner: *"SL beyond the liquidation zone"*; the number [Claude] |
| `tp_steps` | 1 | TP this many steps from the line (the opposite edge) | owner: *"TP is the opposite edge"* |
| `order_life_h` | 48 | hours an unfilled setup waits | [Claude] |
| `cancel_frac` | 0.3333 | momentum cancel: price ran this x S toward the line in the last hour | [Claude], from the owner's *"no fade against momentum"* |
| `mom_bars`, `mom_med_bars`, `run_bars` | 3, 120, 6 | momentum skip (rule 5a) | [Claude], from the owner's 05/05 and 06/05 trades |
| `gate_w` | D1 0.4, H4 0.3, H1 0.2, M15 0.1 | the state weights | owner: *"find the trend on M15, 1H, 4H, 1D and weight them"*; the weights [Claude], fixed before measuring |
| `gate_min` | 0.25 | trade when the sideways share is over this | [Claude] |
| `abn_atr` | 3.0 | skip when |H1 close - EMA50| >= this x H1 ATR(14) | owner: *"maybe as far as 2.5 - 3 ATR"*, *"measure which is best"*; 3 = the middle of the 2.5 - 3.5 plateau (BOT_RESEARCH) |
| `ema_len`, `atr_len` | 50, 14 | H1 EMA and ATR lengths for `abn_atr` | [Claude]; ATR as MT5 (owner's screen) |
| `exec_tf` | M15 | the frame fills and exits are judged on | [Claude] (M5 starts 2025-10-05; the measurements over 2023 - 2026 were on M15) |

Every name above is one field of `ZoneParams` (rule 1). A value outside its meaning (a fraction <= 0, `gate_min` outside
[0, 1), `exec_tf` not M5 / M15, `step_mode` not `watr` / `fixed`, weights that do not sum to 1 within 1e-9, an empty
`grid_ks`) is refused at start [Claude].

## 1. The parameters come from a database (the owner, 2026-10-31: *"every config value read from a db"*)

The same design as the Fibonacci bot's (BOT_RULES, "The parameters come from a database"), **in its own table and
module**, so the two never touch:

- File `data/bot_config.db`; table **`zone_config_change`** (append-only: `id`, `market`, `set_name`, `name`, `value`,
  `changed_at_utc`, `changed_by`, `note`); module **`eye/zone_config.py`** with `load_params(db, market, set_name) ->
  (ZoneParams, version)` and the command line `seed / copy / set / show / list / history` exactly as there (a set's
  current values = per name the highest `id`; version = the highest `id`; no value falls back to the code; every
  `ZoneParams` field present and no other; a write checked whole through `ZoneParams` inside `BEGIN IMMEDIATE`; the
  time passed in from `main`; market and set names: letters, digits, `_`, `-`).
- Text form: floats as Python `repr`, ints as digits, `grid_ks` as `1,2,3`, `gate_w` as `0.4,0.3,0.2,0.1` (D1, H4, H1,
  M15 in that order); reading back gives exactly the value written.
- `eye/zone_bot.py` takes `--db`, `--market` (default `XAUUSD`, the only market with bars wired - another stops with
  "no bars for <market>" before loading bars) and `--set` (default `default`); no parameter flags.
- Every output names `zone=<market>/<set>@v<version>` and every value (rule 11).

## 2. The step `S` (owner: the run of gold; *"lately 70 - 80"*; *"it depends on the market"*; *"maybe 1/2 - 1/3 of the ATR"*)

- **Weekly bars** [Claude]: built from the stored D1 bars in **broker server time** (`time_server`, seconds): weeks
  starting Sunday 00:00 server time (pandas `resample("W-SUN", label="left", closed="left")`), high = max, low =
  min, close = the last D1 close. **ATR(14)** = the simple mean of the last 14 weekly true ranges (TR = max(high -
  low, |high - previous close|, |low - previous close|)) - MT5's ATR. Acceptance: the week starting 2026-10-25 gives
  **195.99** (the owner's screen, 01/11/2026).
- A week is **closed** for use at its start + 7 days (server time, read as UTC) [Claude, as the reference].
- **The month's step**: at each Thai month start `m` (00:00 Asia/Bangkok), `S(m)` = `step_factor` x the ATR of the
  last week closed at or before `m` (`step_mode` watr), or `step_fixed` (fixed). A time `t` uses `S` of its Thai month.

## 3. The zones - grids (owner: a box over a price cluster, moved along; a zone shift after a full step back, read with the structure)

Events in time order: every **H4 pair** (two neighbouring fixed H4 pivots a, b - known at the close of b's
`confirm_pos` bar) and every **Thai month start**. Equal times: the reference's order (a stable sort of pairs, then
months, by time) [Claude].

- **A pair** is a cluster when its distance `d = |a - b|` is within `grid_tol x S` of `k x S` for some k in
  `grid_ks` (`S` = the step of the pair's time). Then the candidate anchor is `lo = min(a, b)`.
  A **new grid** (`lo`, `S`) starts at the pair's time when there is no grid yet, or `lo` is more than
  `shift_tol x S_g` off the current grid's lines (off = the distance to the nearest line, `min((lo - A_g) mod S_g,
  S_g - (lo - A_g) mod S_g)`), or `|S - S_g| > step_remake x S_g` (`A_g`, `S_g` = the current grid).
- **A month start** with a current grid and `|S(m) - S_g| > step_remake x S_g` starts a new grid (`A_g`, `S(m)`) - the
  same anchor, the new step.
- The grid **in force** at `t` = the last grid whose start is at or before `t`. Before the first grid: nothing.
- Acceptance (`step_mode` fixed 76, from 2025-11-01): the grids that start from 2025-09-24 on are 24/09/25 3627.90,
  05/11/25 3886.43, 05/05/26 4510.20, 02/07/26 3942.95, 09/09/26 4282.45, 22/09/26 4253.59, 14/10/26 4066.42 (BOT_RESEARCH,
  "The whole system in one run"; dates Thai).

## 4. Visits - price comes to a line (H1)

At each **H1 bar** `i` (its open `t_i`, from the run's start on; warm-up: no visit before H1 bar 130 of the file and
never without a grid):

- For the grid in force at `t_i` (`A`, `S`), the lines `L = round(A + k S, 2)` for `k = floor((low_i - A) / S) - 1` to
  `k + 3`. `Z = near_frac x S`.
- **A visit** on `L`: (`low_i <= L + Z` and `open_i > L`) -> a **BUY** visit; else (`high_i >= L - Z` and `open_i < L`)
  -> a **SELL** visit; and the line is **armed**. The visit's time is `t_i` (the bar's open: the setup's limit orders
  are resting from then on - only bars closed before `t_i` decide anything, rules 5 - 6).
- **Armed** [Claude]: a line key (`round(A,2)`, `round(S,2)`, `L`) is armed until it is visited; it is armed again
  after an H1 bar whose high and low are both at least `away_frac x S` from `L`. A new grid has new keys - all armed.
  A visit disarms the line whatever rule 5 then decides.

## 5. Skips - when the market is not this setup's (in this order; the first that applies is the reason)

a. **Momentum into the line** (owner: *"a green candle that big - would you still sell? wait and see"*; *"the momentum
   came near the zone - respect a trend like this"*) [Claude, the form]: one of the `mom_bars` H1 bars before `i`
   (`i-3 .. i-1`) has a body toward the line (`(close - open) x -sgn`) at least the median H1 range (high - low) of
   the `mom_med_bars` bars `i-120 .. i-1`; **or** the last `run_bars` H1 bars (`i-6 .. i-1`) ran `S` toward the line
   (`(close_{i-1} - open_{i-6}) x -sgn >= S`). Reason `momentum`.
b. **One setup at a time** [Claude]: a visit at or before the exit time of the last setup that filled. Reason `busy`.
c. **Price far from its mean** (owner: *"measure from volatility or price much further than normal, on a smaller frame -
   it should tell at once"*; *"2.5 - 3 ATR"*): at H1 bar `i-1`, `|close - EMA(ema_len)| >= abn_atr x ATR(atr_len)` (EMA:
   pandas `ewm(span=ema_len, adjust=False)` over the whole stored H1 series; ATR: the simple mean of the last
   `atr_len` H1 true ranges). Reason `abnormal`.
d. **The market state** (owner: *"if that period is a trend, no trade"*; *"sideway, sideway up, sideway down"*): for
   each of D1, H4, H1, M15, read the last two fixed HIGH and the last two fixed LOW pivots known by `t_i`; the frame
   **trends** when both pairs rise or both fall, else it is **sideways** (also with fewer than two of either). The
   **sideways share** = the sum of `gate_w` over the sideways frames. Skip when the share `<= gate_min`. Reason
   `trend`.

## 6. The setup - two positions (owner: *"one before price and one on the fake break, SL beyond the liquidation zone"*; *"TP is the opposite edge"*)

For a visit not skipped, with `sgn`:
- **P1** a limit at `L + sgn x p1_frac x S`; **P2** a limit at `L - sgn x p2_frac x S`.
- **SL** for both `L - sgn x sl_frac x S`; **TP** for both `L + sgn x tp_steps x S`.
- On the **`exec_tf` bars from the bar that opens at or after the visit's time** (`j0`), until `j0 + order_life_h x
  bars-per-hour` (12 for M5, 4 for M15), bar by bar, before any fill:
  - **Withdrawn** if `j >= end`, or (from the bar after `j0`) the bar reaches `away_frac x S` beyond the line on the far
    side (`sgn x (high or low - L) >= away_frac x S`: the high for a BUY, the low for a SELL). Reason `no fill`.
  - **Momentum cancel** (rule 5a, at the fill moment) [Claude]: the `exec_tf` bars of the last hour (`j - per_h .. j-1`,
    closed) ran `cancel_frac x S` toward the line (`(close_{j-1} - open_{j-per_h}) x -sgn`), or, on a bar that would
    fill the first position, the move from `open_{j-per_h}` to that position's price is that far toward the line.
    Reason `cancel`.
- After the first fill the orders stay until the exit (no withdrawal or expiry for P2).

## 7. Fills and exits [Claude, as the reference]

- Bars are bid. **BUY** fills when the ask reaches the price: `low + spread x point <= price`; **SELL** when `high >=
  price`. P1 and P2 fill on the same bar if both prices are reached. The fill price is the limit price.
- **Exit** on the bars from the first fill on: BUY - SL when `low <= SL`, else TP when `high >= TP`; SELL - SL when `high +
  spread x point >= SL`, else TP when `low + spread x point <= TP`. SL first when a bar holds both; **TP only on a bar
  after every fill** (on a fill bar only the SL counts). Exit price = the SL or TP price. Both positions exit together.
  A setup still open when the data ends is `open` (its last close), not a result.
- **Cost** = the spread only (the owner, 10/20), through the fills and exits above; no slippage.
- **Results**: a position's `pnl = sgn x (exit - fill)` (USD at 0.01 lot), `risk = sgn x (fill - SL)`; a **setup's R** =
  the sum of its positions' pnl / the sum of their risks. Every SL exit has pnl < 0 (asserted).

## 8. Order of evaluation [Claude]

For each visit in time order: 5a momentum -> 5b busy -> 5c abnormal -> 5d state -> 6 orders (withdrawn / cancel / fill)
-> 7 exit; the setup's exit time is the next visit's `busy` reference.

## 9. Not in this setup (the owner's words recorded, not built)

- **The stop limit when a line does not hold** (owner) - measured as a book of its own: no gain (BOT_RESEARCH); not
  built. The **M5 / M15 turn** entries, the limit at the line (variant B), the H1 trend-run filter, the D1 ER skip,
  the market-measured "half the cluster" step - tried and not kept (BOT_RESEARCH).
- **Review every 3 - 6 months** (owner): the setup's results are looked at against the market of the time; a review is
  the owner's.

## 10. Data

FBS-Demo XAUUSD, `data/history/FBS-Demo/XAUUSD/{D1,H4,H1,M15,M5}.parquet` and `spec.json`; `spread` (points) from the
bar of `exec_tf`. The run's span: `--start` and `--end` (Thai dates; default 2023-10-01 to the last stored bar).

## 11. What the setup writes

Under `eye/research/zone/<market>/<set>/`:
- `positions.csv` - one row per filled position: visit time (Thai), P1 / P2, side, line, S, entry time, fill, SL, TP,
  exit time, exit, how (SL / TP / open), risk, pnl.
- `visits.csv` - one row per visit: time, side, line, S, grid anchor, and its outcome: the skip reason (`momentum`,
  `busy`, `abnormal`, `trend`), `no fill`, `cancel`, or `traded`; with the numbers each skip read (the momentum
  body and median, the 6-bar run, the EMA distance and ATR, the sideways share and each frame's reading).
- `grids.csv` - every grid: start time (Thai), anchor, step, what started it (pair a / b, or month).
- `summary.csv` - `zone=<market>/<set>@v<version>`, every parameter, the span, setups, R a setup, TP share, USD, by
  year and by month, the deepest drawdown.

## 12. Acceptance - what a build must show

Every case is computed by the build from the stored bars and **reported**; a case that does not come out as written
is reported, not bent to fit.

1. **Weekly ATR**: 195.99 for the week starting 2026-10-25 (rule 2).
2. **Grids**: the list in rule 3 (`step_mode` fixed, 76).
3. **The reference reproduced, setup for setup** (`eye/research/zone_reference.py` with the same settings; its CSV
   under `eye/research/zone_reference_out/`):
   - the **defaults**, 2023-10-01 to 2026-11-01: **104 setups, +0.340 R a setup, 50 % TP, +1211.4 USD**, drawdown
     -744.2 USD (to 06/04/26), 15 of 35 months negative; skips: momentum 547, trend 138, busy 58, cancel 63, no fill 71,
     abnormal 133 (the reference's counter order differs; the counts must match). (These are after the SELL-fill fix of
     2026-11-01 in the reference - before it, +0.348 R / +1228.2 USD, the numbers in BOT_RESEARCH.)
   - `step_mode` fixed 76, `exec_tf` M5, `abn_atr` off (a value so large it never applies, e.g. 1e9), 2025-11-01 to
     2026-11-01: **41 setups, +0.615 R, +1378 USD**.
   Every setup's visit time, side, line, positions, fills, exit and pnl equal the reference's; any difference listed.
4. **No look-ahead** [Claude]: a run on the bars cut at a time `T` (every timeframe's bars with `close_time <= T`) gives
   the same visits, skips and setups for every visit before `T - order_life_h`, and the same fills / exits for every
   setup that exited before `T` - tested at three cuts (2024-06-01, 2025-12-15, 2026-08-01).
5. **Unit tests on constructed bars** for: the weekly ATR; a pair at 1, 2, 3 steps (+- the tolerance edge) and one
   just outside; a shift and a non-shift by `shift_tol`; a month remake; arming and re-arming; each skip (a-d) on and
   off at its edge; P1 / P2 / SL / TP prices for a BUY and a SELL; withdrawal, expiry and both cancels; a bar filling
   both positions; SL first in a bar holding both; no TP on the fill bar; the spread on each side; `open` at the end;
   R and pnl.
6. **The parameters**: the BOT_RULES database cases, for `zone_config` (seed loads back equal to `ZoneParams()`, the
   text round trip of every field, missing / unknown names stop, an invalid write writes nothing, history and
   version, two writers), and the Fibonacci bot's `config_change` table untouched by any zone command.
7. **Independence**: `eye/zone_bot.py` and `eye/zone_config.py` import nothing from `eye/bot2e.py`,
   `eye/bot_config.py` or `eye/bot_research.py`, and those import nothing from them (a test reads the imports).
8. **Gates**: ruff, mypy (the new files), and the full test suite green.

## 13. How results are judged

The owner's bar: at least **+0.15 R a trade after costs** (CLAUDE.md). The measured numbers came from a search over
one year and a check on the two years before it (BOT_RESEARCH) - **the clean test is forward**, on the months after
2026-11-01 as their bars arrive, with the parameters unchanged. No number is believed until its trades are drawn and
checked against these rules; the owner does not believe pooled numbers - single trades first.
