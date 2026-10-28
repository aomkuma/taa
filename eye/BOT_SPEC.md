# Bot 2e - specification

Written by Claude on 2026-10-28 from `eye/METHOD.md` section 2e, at the owner's word: *"write the code and
let a bot do the work - correct, with every condition. A Sonnet agent writes it, Codex reviews it, Claude
checks the final spec."* The owner's rules are quoted from 2e. **Every definition the owner did not give is
marked `[Claude]`, is a named parameter with a default, and is written into each decision the bot makes**,
so that the owner can change it and the record shows which one produced which trade.

## 1. What the bot does

It walks real trading days bar by bar on stored gold data, exactly as Claude walks them by hand, and at
every closed M5 bar inside the owner's windows applies the seven steps of METHOD 2e. When all of steps 1-4
hold it writes a decision - a stop-limit (or limit) order with its stop and target - into its own ledger.
The existing `eye/score.py` scores that ledger and `eye/money.py` reads it in money. The bot never sees a
bar that had not closed at the moment it decides.

## 2. Files

| file | what |
|---|---|
| `eye/bot2e.py` | the bot: pure functions for each step, a `decide(frames, now, params)` entry point, and a CLI that walks a date range |
| `eye/bot_ledger.csv` | its decisions - **the same columns as `eye/ledger.csv`**, `reader` = `bot2e` |
| `eye/bot_log.csv` | one row per evaluated bar: the time, each step's state and numbers, and why no order was written |
| `tests/unit/test_eye_bot2e.py` | the tests in section 10 |
| `eye/money.py` | gains an optional `--ledger NAME` argument to read one ledger only (default unchanged: both of Claude's) |

Do not change `app/`, `eye/METHOD.md` or any other document. Do not change the behaviour of `score.py`
for the existing ledgers.

## 3. Data, time and indicators

- Bars: `data/history/FBS-Demo/XAUUSD/{H1,M15,M5}.parquet`, read as `eye/walk.py` `frame()` does (UTC index
  from the time column). Thai time is `Asia/Bangkok`.
- **Closed bars only:** at moment `now`, a bar of timeframe `tf` exists if `open_time + tf <= now`. Every
  computation takes frames already cut this way. `now` advances in 5-minute steps.
- **ZigZag:** `app.indicators.chart_read.zigzag_pivots(high, low, point, depth=12, deviation=5, backstep=3)`,
  `point` from `spec.json` (0.01). **Only fixed pivots** - the function's output - are used; the moving last
  point MT5 draws is not a pivot for the bot.
- **MACD:** `eye.walk.macd_mt5` (MT5's: main = EMA12 - EMA26 of close via `app.indicators.common.ema_values`,
  signal = simple 9-bar mean). Divergence uses `main`.
- **RSI:** `app.indicators.momentum.rsi(close, 14)`.
- Warm-up: at least 1,500 bars before the first bar evaluated on each timeframe.

## 4. When it looks

The owner's windows (METHOD 2c), Thai time: **Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00.**
A decision can be written only at a `now` inside a window. The bot evaluates at every M5 close inside a
window. Outside the windows it writes nothing (orders already written live on as `score.py` scores them).

**One order or position at a time** `[Claude]`: while a written order has not been filled, withdrawn or
closed (as `score.py` would score it from the bars known at `now`), no new decision is written.

## 5. The seven steps (written for a BUY; a SELL is the mirror of every line)

**Step 1 - the side, from H1.** The owner: *"the trend on H1"*. `[Claude]` `h1_mode`:
- `strict` (default): from H1 fixed pivots, up = the last high above the high before it **and** the last
  low above the low before it; down = both lower; anything else = no side, no trade.
- `lows`: up = the last H1 low above the low before it and price above that last low; down = the last H1
  high under the high before it and price under that last high; both or neither = no side.
Only the side the trend gives is traded - *"at resistance when the sell side has the edge, at support
when the buy side has the edge - never the other way round."*

**Step 2a - the level from the left.** The owner: *"a level the left of the chart built"*; *"a level is a
band - the target goes before the line, the stop beyond the band"* (LESSONS 5). `[Claude]`:
- candidate levels = prices of **H1 fixed pivots** in the last 500 H1 bars whose bar is at least
  `level_min_age_h` = 24 hours before `now` ("from earlier days");
- each is a band of half-width `band_frac` = 0.10 × the median height of the last 20 H1 ZigZag legs; bands
  that overlap merge into one;
- a **support** is a band below the price at the start of the counter-move; a **resistance** one above.

**Step 2b - the count, on the entry timeframe.** Evaluated on **M5 and on M15** (the owner: *"M5-M15"*);
either may produce the decision, M5 first. The counter-move `[Claude]`: start = the highest fixed HIGH
among the last 12 fixed pivots; the lows counted = the fixed LOW pivots after it; its extreme `L*` = the
lowest of them. Step 2 holds if `L*` lies inside a support band and **either**:
- **the count**: 3 to 5 lows (the owner: *"3 to 5 peaks"*) **and divergence on both** at `L*` against the
  low before it - price lower or equal, MACD main higher, RSI higher (the owner: *"if both happen, it is
  clear"*; METHOD 2e: divergence is required for the count); **or**
- **the M** (the owner's word for a buy - *"M as buy, W as sell"*; *"two legs, but it is an M pattern"*;
  *"an asymmetric M"*): exactly the last two counted lows both inside the same support band, a high between
  them. No divergence needed (the owner: *"it can be entered"*). Record whether it diverged anyway.

**Step 3 - the structure breaks.** After `L*`: a bar's high goes above the last fixed HIGH before `L*`, and
then a fixed LOW `L_hl` forms above `L*` - a higher low.

**Step 4 - the high breaks.** `H_d` = the fixed HIGH the dip to `L_hl` started from. The order waits for
price to go through `H_d`.

**Step 5 - the entry on the retest: a Buy Stop Limit.** The owner: *"break the high, then retest"*; *"a stop
limit"*. Written once `L_hl` is fixed: `trigger` = `H_d` + `trigger_offset` (`[Claude]` 0.50 USD - "a
little over"), `entry` (limit) = `H_d`. If a bar has already closed above `H_d` when the decision is
written, `trigger` is left empty and the order is a plain buy limit at `H_d`, below the price on the
screen. If price is already below `L_hl` the setup is void.

**Step 6 - the stop.** The owner: *"beyond the highest top or the lowest bottom"*; with the band rule:
`stop` = min(`L*`, the support band's lower edge) - `stop_buffer` (`[Claude]` 0.50 USD).

**Step 7 - the target.** The owner: *"just before the opposite level on the left"*: the nearest resistance
band whose lower edge is above `entry`; `target` = that lower edge - `target_buffer` (`[Claude]` 0.50 USD).
No such band in the last 500 H1 bars = no trade. **Held until stop or target** - `score.py` already does
this.

**Reward** `[Claude]` `min_r` default **0** (no filter - the owner has not set one; the question is open).
R = (target - entry - 0.30) / (entry - stop) is written into every decision whatever `min_r` is.

**SELL:** the mirror - H1 down; a resistance band; the lowest LOW among the last 12 fixed pivots starts the
counter-move; highs counted; divergence = price higher or equal, MACD main lower, RSI lower; the owner's
**W** is the sell pattern; step 3 = a bar's low under the last fixed LOW before the extreme `H*`, then a
fixed lower high; `L_d` = the fixed LOW the bounce started from; Sell Stop Limit `trigger` = `L_d` -
offset, `entry` = `L_d`; stop = max(`H*`, band's upper edge) + buffer; target = the nearest support band's
upper edge + buffer.

## 6. The decision row

`id` `B-YYYYMMDD-n`; `cutoff_thai` = the day at `07:00`; `decided_at` = `DD/MM HH:MM` - the **open time of the
last closed M5 bar** (the `Now` label of `walk.py`; `score.py` starts five minutes later); `reader` `bot2e`;
`side`, `entry`, `stop`, `target`, `trigger`; `fill`, `exit`, `why`, `r_net`, `at_decision_r`, `missed_by`
empty (score.py fills them); `rules` = `?????????`; `conflict` empty; `setup` = `+++++++`;
`structure` = one line with the timeframe, the side mode, the level band, the counted pivots with price /
MACD / RSI, whether it was the count or the M/W, the divergence flags, `H_d`/`L_d`, R, and every `[Claude]`
parameter value.

## 7. The log

`eye/bot_log.csv`, one row per evaluated `now`: time (Thai), window, price, step 1 side and mode, level
band (or none), timeframe, count and pivots, divergence flags, M/W flag, steps 3-5 state, and `reason` -
the first step that failed, or `order written`, or `order pending`.

## 8. The CLI

```powershell
.venv\Scripts\python eye/bot2e.py --from 2026-04-06 --to 2026-04-07     # walk days, write ledger and log
.venv\Scripts\python eye/bot2e.py --from 2026-04-06 --to 2026-04-07 --h1-mode lows --min-r 1
.venv\Scripts\python eye/score.py bot_ledger.csv                        # score its rows
.venv\Scripts\python eye/money.py --ledger bot_ledger.csv               # in money, 200 USD, 0.01 lot
```

Re-running a range replaces the bot's rows for those days (ledger and log), nothing else.

## 9. Things it must never do

- read a bar whose `open_time + tf > now`, or a ZigZag pivot not yet fixed at `now`;
- trade against the H1 side, or at a level of the wrong kind;
- write an entry on the break itself (a plain stop) - only a stop limit or a limit at the broken level;
- change `app/`, the owner's documents, or Claude's ledgers.

## 10. Tests (`tests/unit/test_eye_bot2e.py`)

1. **No look-ahead:** decisions for a day computed on the full data equal those computed with every bar
   after each `now` removed (or randomised).
2. **Mirror:** a synthetic series and its price-negated mirror give a BUY and the mirrored SELL with mirrored
   prices.
3. **Count and divergence:** synthetic M5 series with 2, 3, 5 and 6 lows; with and without divergence on
   each oscillator - step 2 holds only for 3-5 with both, or for the M.
4. **M:** two lows in one band with a high between - step 2 holds without divergence; two lows in different
   bands - it does not.
5. **Steps 3-5:** the order is written only after the higher low is fixed; trigger / limit / stop / target
   equal the formulas in section 5; a stop limit when `H_d` is unbroken, a plain limit when a bar has already
   closed above it.
6. **H1 modes:** constructed pivots giving up / down / none under `strict` and `lows`.
7. **Windows and one-at-a-time:** nothing written outside a window or while an order is live.
8. **Ledger compatibility:** a written row scores with `score.py` without error, and `money.py --ledger` reads it.

Gate before handing back: `ruff format` and `ruff check` on the new and changed files, `mypy` on
`eye/bot2e.py`, `pytest tests/unit/test_eye_bot2e.py`. Run the bot on 2026-04-06 and 2026-04-07 in both h1
modes and report each decision and the log's reason counts - **not** whether they made money.

---

## Revision 1 (2026-10-28 evening) - after the first build, Codex's review and the owner

These override the sections above where they differ.

**R1. Levels are not merged** (the first build chained overlapping bands into one support of 4460-4625 and a
stop 211.94 USD under the entry - Claude's spec error). Each H1 fixed pivot is its own band, centre the
pivot price, half-width as in 2a. `L*` is "inside a support" if it lies inside at least one support band;
**the band used is the one whose centre is nearest `L*`**. Stop (step 6) and the target band (step 7) use
single bands only.

**R2. The reward floor is the owner's: `min_r` = 1.0.** The owner, on a plan risking about 72 USD for 41:
*"risk 72 against a profit of 41 - that is against the principle; it should not be traded."* No decision is
written when R = (target - entry - 0.30) / (entry - stop) is under 1.0. The log reason is `reward under
1R`, with R.

**R3. The M is exactly two lows** (Codex). The M path holds only when the counted lows are exactly two, both
inside the same support band. A count of 3-5 needs divergence on both, always. Test: three lows, the last
two in one band, no divergence - step 2 fails.

**R4. The cut guard checks every bar** (Codex): `_check_cut` verifies the index is sorted and that every
bar's `open_time + tf <= now`, not only the last. Test: a future bar inserted inside an otherwise closed
frame is refused.

**R5. The plain limit** (Codex on SPEC-QUESTION 3): a plain limit at `H_d` only while the last close is above
`H_d`; if price has fallen back to or under `H_d`, the order is a stop limit again (a fresh break is needed).

**R6. Every SPEC-QUESTION in the report is marked in the code** - the first build reported nine and marked
four.
