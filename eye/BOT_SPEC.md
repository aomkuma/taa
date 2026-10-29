# Bot 2e - specification (the history)

> **The rules in force are in `eye/BOT_RULES.md`.** This file is the record of how each rule came to be -
> every revision, including the ones withdrawn. Read it to know why; build from `BOT_RULES.md`.

Written by Claude on 2026-10-28 from `eye/METHOD.md` section 2e, at the owner's word: *"write the code and
let a bot do the work - correct, with every condition"*; and the division of the work: a Sonnet agent writes
it, Codex reviews it, Claude checks the final spec. The owner's rules are quoted from 2e. **Every definition the owner did not give is
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
- **the count** *(divergence on one is enough - R11 supersedes "both")*: 3 to 5 lows (the owner: *"3 to 5 peaks"*) **and divergence on both** at `L*` against the
  low before it - price lower or equal, MACD main higher, RSI higher (the owner: *"if both happen, it is
  clear"*; METHOD 2e: divergence is required for the count); **or**
- **the M** (the owner's word for a buy - *"M as buy, W as sell"*; it need not be symmetric): exactly the last two counted lows both inside the same support band, a high between
  them. No divergence needed (the owner: *"it can be entered"*). Record whether it diverged anyway.

**Step 3 - the structure breaks.** After `L*`: a bar's high goes above the last fixed HIGH before `L*`, and
then a fixed LOW `L_hl` forms above `L*` - a higher low.

**Step 4 - the high breaks.** `H_d` = the fixed HIGH the dip to `L_hl` started from. The order waits for
price to go through `H_d`.

**Step 5 - the entry on the retest: a Buy Stop Limit.** The owner, for the sell: *"break the low, then retest"*; *"a stop
limit"* - the buy's "break the high" is Claude's mirror. Written once `L_hl` is fixed: `trigger` = `H_d` + `trigger_offset` (`[Claude]` 0.50 USD - "a
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
*Superseded: R2 (1.0, Claude's), then R9 - **2.0, the owner's**.*
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
`eye/bot2e.py`, `pytest tests/unit/test_eye_bot2e.py`. *(The first build's run instruction is retired: from
2026-10-29 no bot or research run until the code is confirmed correct - "The side, after September".)*

---

## Revision 1 (2026-10-28 evening) - after the first build, Codex's review and the owner

These override the sections above where they differ.

**R1. Levels are not merged** (the first build chained overlapping bands into one support of 4460-4625 and a
stop 211.94 USD under the entry - Claude's spec error). Each H1 fixed pivot is its own band, centre the
pivot price, half-width as in 2a. `L*` is "inside a support" if it lies inside at least one support band;
**the band used is the one whose centre is nearest `L*`**. Stop (step 6) and the target band (step 7) use
single bands only.

**R2. A reward floor, `min_r` = 1.0 - the number is Claude's reading `[Claude]`.** The owner, on a plan
risking about 72 USD for 41: *"risk 72 against a profit of 41 - that is against the principle; it should not
be traded."* The owner said that trade should not be taken; **the owner did not say 1R** - asked *"who set
1R?"*, Claude had written its own reading as the owner's rule. 1.0 stays the default until the owner gives
the number. No decision is
written when R = (target - entry - 0.30) / (entry - stop) is under 1.0. The log reason is `reward under
1R`, with R.

**R3. The M is exactly two lows** (Codex). The M path holds only when the counted lows are exactly two, both
inside the same support band. A count of 3-5 needs divergence on both, always *(superseded by R11: one)*. Test: three lows, the last
two in one band, no divergence - step 2 fails.

**R4. The cut guard checks every bar** (Codex): `_check_cut` verifies the index is sorted and that every
bar's `open_time + tf <= now`, not only the last. Test: a future bar inserted inside an otherwise closed
frame is refused.

**R5. The plain limit** (Codex on SPEC-QUESTION 3): a plain limit at `H_d` only while the last close is above
`H_d`; if price has fallen back to or under `H_d`, the order is a stop limit again (a fresh break is needed).

**R6. Every SPEC-QUESTION in the report is marked in the code** - the first build reported nine and marked
four.

## Revision 2 (2026-10-28 evening) - Claude's final check

**R7. A window opens at its start.** The first look of a window is the close at its start (07:00, 13:00,
19:30 Thai - the bar before it has just closed), as in the walks by hand: `start <= now <= end`.

**R8. A setup already played out is not written** `[Claude]` (Codex's second review: implemented but not in
the spec): if, after the higher low formed and before the decision, price has traded at the stop or the
target, the setup is over - the order would have been withdrawn the moment it was written (METHOD rule 8).
Reason `setup already played out`; a test for it.

## The owner's reward rule, and what the first longer run showed (2026-10-28, late)

**The owner: *"the profit has to be 1:2, 1:3."*** So `min_r` = **2.0** is the owner's (R2's 1.0 was
Claude's reading and is replaced). Whether 3 is wanted where 2 is reachable is not said.

Run 2026-10-20..27, `min_r` 2, both h1 modes: **no decision.** On the owner's example - the fall from 4141:
- 21/10 New York: sell side, five M5 highs into the 4137-4150 resistance (4124, 4126, 4129, 4126, 4141.87),
  no divergence on both at the last - step 2 failed, rightly by the rule.
- 22/10 Asia: the top 4142.23 (03:00 Thai) counted as **one** high, because the counter-move is defined from
  the lowest low of the last 12 pivots and the dip to 4104.92 (01:00-02:00) between the two tops at 4142
  restarted it. **A reader sees a double top at 4141-4142 in one zone; the bot's definition split it** - a
  spec error. The owner asked: *"can you find the trough of a price zone, or its top?"* - the count should be
  of the tops (bottoms) that touch the same zone, not of a counter-move cut at its lowest low. **Open:
  rewrite step 2b so.**
- Even counted right, the sell on the retest of 4105 (London 22/10 reached 4102.77) had its target just
  before the next support from the left, 4066-4073: about 39 risk for 28 - **0.7R, under 1:2.** Price went on
  to 3976. **Open for the owner: when the next level is too close for 1:2 - skip to the level after it,
  target 2R / 3R regardless of levels, or no trade.** *(Answered: "no trade, for now" - R9 below.)*

## Revision 3 (2026-10-28, late) - the owner's reward rule, and counting by zone

**R9. Reward: at least 1:2 - the owner's.** *"The profit has to be 1:2, 1:3"*; and, asked what to do when
the next level from the left is too close for that - skip to the level after it, a 2R / 3R target
regardless of levels, or no trade: *"no trade, for now."* So `min_r` defaults to **2.0**; the target stays
**just before the nearest opposite level** (step 7); when that gives R under 2.0 there is **no decision**
(reason `reward under 2R`, with R). No skipping to a further level, no fixed-R target.

**R10. Step 2b counts by zone** (replaces the counter-move definition of 2b; the owner: *"can you find the
trough of a price zone, or its top?"*). For a BUY:
- the zone = a support band (step 2a, single bands as R1) that holds the latest fixed LOW on the entry
  timeframe;
- the zone's lows = the fixed LOW pivots on that timeframe whose price is inside the band, among the last
  `counter_pivots` (`[Claude]` default 20) fixed pivots, **and after the last close below the band's lower
  edge** (a close through the zone ends it as a support; lows before that do not count);
- `L*` = the lowest of the zone's lows; the count = how many zone lows there are;
- step 2 holds for 3-5 zone lows (SELL: zone highs) with divergence on both *(R11: one)* at `L*` against the zone low before it, or for
  exactly 2 zone lows (the owner's M) without divergence;
- steps 3-7 as before, from `L*`.
SELL: the mirror - a resistance band, its highs, reset by a close above its upper edge; exactly two zone
highs = the owner's W.

The case it must get right (a test on the stored bars): at 22/10/2026 07:00 Thai on M15 (or M5), the
resistance zone round 4141-4142 holds two fixed highs, 4141.87 (21/10 19:00 Thai) and 4142.23 (22/10 03:00
Thai), with the dip to 4104.92 between them inside the count window - the bot counts **two zone highs (the
owner's W)**, not one. (What it then decides is for steps 3-7 and R9.)

**R11. Divergence on one oscillator is enough - the owner's** (2026-10-28). `div_mode` defaults to **one**; which oscillators diverged is still written
into each decision (both = the owner's "clear" case).

## Revision 4 (2026-10-29) - REMOVED: an entry on M1 - Claude's misreading of a question

**Removed from the code at the owner's word (2026-10-29: *"take it out"*).** It was built on a misreading:
the owner, after seeing it: *"1H 6 USD was only a question - not meant to be researched or taken further; it was a comparison."* The text below is kept as the record of what was built and
run (`eye/BOT_RESEARCH.md` round 2: 3 distinct trades, none won); none of it is the owner's rule.

### As it was written (record only)

Asked how a real trade reaches 1:2 - 1:3 with the stop beyond the extreme and the target before the next
level, the owner: *"As we discussed: if 1H runs 6 USD, and M1 gets in near the top or the bottom of price, and it turns, that is 2R already."* Earlier the same evening, the owner's own question: *"say an H1 bar has
an ATR of 6 and M1 runs 0.9 - how many R is that?"* and *"SL beyond the top of the H1 bar by 60 %"*.

**The principle, generalised by Claude (for the owner to correct; not the numbers 6, 0.9 or 60 %):** the
reward is measured on the large timeframe - the H1 move to the next level; the risk on the smallest - the
entry is taken on M1 close to the zone's extreme, so the stop beyond that extreme is short and an ordinary
H1 move is two stops or more. Round 1 put the stop beyond the extreme *and* the band edge and entered on the
M5 / M15 retest, far from the extreme: no setup in October reached 1:2.

**R12.** Steps 1, 2 and 7 as before (H1 side and levels; the zone count or M / W with divergence on M5 /
M15; the target just before the next opposite level; at least 2R, the owner's). Steps 3-6 move to M1:
- `[Claude]` From the M1 bars that opened at or after the bar of `L*` (the setup timeframe's zone extreme):
  `L1` = the M1 fixed LOW with the lowest price there (for a BUY; the mirror for a SELL). Its price is
  `L*`'s or close to it - the same extreme seen on M1.
- Step 3 on M1: an M1 bar's high above the last fixed M1 HIGH before `L1`, then a fixed M1 higher low
  after that break, above `L1`.
- Step 4 on M1: `H_d` = the fixed M1 HIGH the dip to that higher low started from.
- Step 5 on M1: void if the last M1 close is below the M1 higher low; entry at `H_d`, a stop limit while
  the last M1 close is at or under `H_d`, a plain limit while it is above (R5).
- Step 6: **stop = the extreme (`min(L*, L1)` for a BUY) - `stop_buffer`** - beyond the lowest bottom, the
  owner's words; the band edge is no longer added (that was Claude's).
- `entry_mode` = `m1` (default) | `setup` (round 1's behaviour, kept for comparison). ZigZag 12 / 5 / 3 on
  M1 as on every frame. Decisions use closed M1 bars only (the cut guard covers M1).
- The setup's identity for "already used" is side, setup timeframe, `L*` time and the M1 higher-low time.
- R8 (played out) is read on M1 bars after the M1 higher low.
- `[Claude]` `stop_buffer` stays 0.50 USD. *(The "60 %" question written here is closed: it belonged to
  the owner's comparison, not to a rule.)*

Ledger: the `entry_tf` / setup columns say `M15>M1` or `M5>M1`; the decision text names `L*`, `L1`, the M1
break, the M1 higher low and `H_d`.

## Revision 5 (2026-10-29) - the owner's Fibonacci, with and without the count

The owner's words are in METHOD 2e, "The owner's Fibonacci". Asked whether the count / M-W / divergence is
still needed with it: *"try both, counting and not counting"*, then *"go on"*. The scale, the stop, the
target and the sideways drawing were asked and, when this was written, **not yet answered** (the target
and the 61.8 % entry's stop were answered later - below): every reading below that is not in the
owner's words is `[Claude]`, and the variants run each open reading rather than choosing one.

*Corrections after review (10-29): the count-on path does not use M1 (revision 4 is removed) - see the
note "R16 as built" below; the trend target and the sideways target are the owner's proposals, put as a
question, run as variants.*

The owner on what will be hard: *"the problem I can see coming is reading whether it is a trend or sideways
- but never mind, try it first."* Trend = an H1 side from step 1, sideways = none: `[Claude]`.

**R13. The Fibo leg (a BUY in an up trend; SELL the mirror in a down trend).** *(The leg is superseded by R18, revision 6.)*
- The side: step 1 as now (H1). `[Claude]`
- The leg, `[Claude]`: on the setup timeframe (`fib_tf`, default M15; variant M5), the latest fixed ZigZag
  HIGH and the fixed LOW before it, the leg rising (high > low) - *"0 % at the previous lowest price, 100 %
  at the previous highest price"*. A level at `x` = low + x * (high - low).
- The leg is live while no bar has closed below its 0 % since the high, and no bar has made a new high
  above 100 % (a new high is a new leg once ZigZag fixes it).

**R14. Entry, stop, target.**
- Entry level `fib_entry` (the owner: *"then wait for it to fall back to around 38 - 23 %; if the bulls are
  really strong, maybe enter from the pullback to 61 %"*): variants **0.382**, **0.236**, **0.618** - on the scale above (0 % at the low),
  a level of 0.382 is a pullback of 61.8 % of the leg. `[Claude: this is the reading of the scale, asked]`
- The stop: below the 0 % (the leg's low) - `stop_buffer` (*"beyond 88 % - 0 %"*, read as beyond 0 %
  `[Claude]`); for the 0.618 entry, beyond 23.6 % (the owner - below).
- The target, `[Claude]`, two variants: `fib_target = level` - the 2e rule, just before the nearest
  opposite H1 band above the entry (as step 7); `fib_target = high` - the leg's 100 % - `target_buffer`.
- **At least 2R - the owner's**; under it, no decision. Spread 0.30 as now.

**R15. Without the count (`fib_count = off`).** *(Its trigger is superseded by R18 for the owner's leg.)* When the leg is live and the last close is above the entry
level, write a **plain limit** at the entry level with the stop and target above. One order per leg (key:
side, fib_tf, leg low time, leg high time). R8 played-out applies (stop or target traded since the leg's
high was fixed).

**R16. With the count (`fib_count = on`).** The Fibo zone `[0 %, entry level]` takes the place of the H1
band as "where": step 2 (R10 zone count by fixed lows inside that zone; 3-5 with divergence on one, or the
M / W of exactly two) on the setup timeframe; the order as in "R16 as built" below (no M1 - revision 4
is removed); the stop of R14, the target per `fib_target`, at least 2R.

**R17. Sideways (no H1 side), `[Claude]` drawing, on by `fib_range = on`:** the range = the last fixed H1
HIGH and LOW (the latest two pivots); drawn 0 % at the low, 100 % at the high. Sell zone 88 % - 127 % (*"at
the edge, around 88 % - 127 %"*): a plain limit sell at 88 %, stop above 127 % + `stop_buffer`, target the
range's 12 % level + `target_buffer` `[Claude]` *(superseded below: the range's other edge)*; the buy the
mirror (limit at 12 %, stop below -27 %, target 88 % - likewise the other edge). At least 2R. With `fib_count = on`, step 2 must hold at that edge as in R16.

Every decision text names: mode, the leg's low and high (prices, Thai times), the levels used, entry,
stop, target, R. Every one of these is written into the ledger's structure text so the walk-by-hand can
check it.

**The owner on the target (2026-10-29, after revision 5 was written):** *"TP: if sideways, yes, around
100 %; but in a trend, shouldn't it be 127 - 161 %?"* So `fib_target` gains **`ext127`** (low + 1.272 x
leg - `target_buffer`) and **`ext161`** (low + 1.618 x leg - `target_buffer`) - the owner's for a trend;
`level` and `high` are kept for comparison only. In R17 the target is **the range's opposite edge** -
Claude's reading of the owner's "around 100 %" (open: on a 0 %-low scale the far edge from a sell at 88 % is
0 %) - replacing Claude's 12 % level. Arithmetic (stop at 0 %, before spread): entry
0.382 -> 2.3 R at 127 %, 3.2 R at 161 %; 0.236 -> 4.4 R at 127 %. (The 0.618 entry's stop is at 23.6 % -
the next paragraph.)

**The owner on the 61.8 % entry's stop (2026-10-29):** asked where the stop goes when entering at 61.8 %:
*"beyond 23 %."* So for `fib_entry` 0.618 the stop = the 0.236 level - `stop_buffer`; for 0.382 and 0.236 it
stays beyond 0 % `[Claude's reading of "beyond 88 % - 0 %"]`. Arithmetic before spread: 0.618 entry, stop 0.236 -> 1.7 R at 127 %, 2.6 R at 161 %.

**R16 as built (2026-10-29, after revision 4 was removed; for revision 5's leg only - revision 6 has its own
entry):** with the count on, the order is written when
price has entered the Fibo zone `[0 %, entry level]` and step 2 holds there (the zone count 3-5 with
divergence on one, or the owner's M / W of two) on the setup timeframe: a plain limit at the **last close**
`[Claude]`, the stop and target of R14, R recomputed from that entry, at least 2R. No M1.

## Revision 6 (2026-10-29) - the Fibo leg the owner draws: the counter-move just ended

The owner's drawing rule (2026-10-29): *"to play an up move, draw high -> low; to play a down move, draw
low -> high."* Revision 5 drew the finished leg in the trade's direction (low, then the
high after it) - the wrong leg (Claude's). **R18 replaces R13 / R15's leg:**

- **The leg, for a BUY (SELL the mirror):** on `fib_tf`, `L0` `[Claude]` = the latest fixed LOW lower than
  every fixed low after it (later lows are higher - a bottom), with no bar closed below it since. `H100`
  `[Claude]` = the
  highest fixed HIGH of the descending run into `L0`: walking back from `L0` while each earlier fixed low is
  higher than the one after it, the highest fixed high met (on M15 at 27/10: 4025.45 -> 3989.14). **Chosen by
  Claude from research the owner asked for** (BOT_RESEARCH, "Which high is 100 %"; not yet confirmed by the
  owner): the high the fall began from was ahead of the latest high before `L0` in 3 of 5 entry / target
  pairs over three years of M15, and at 61.8 % / 161 % in both halves; one timeframe, all hours - a guide.
  **Superseded by the M5 / M15 run the owner asked for** (*"go by the facts ... on the timeframe we trade"*):
  `fib_high` = `start` for the 0.618 entry, `latest` (the fixed high just before `L0`) for the 0.236
  entry; for 0.382 both are run. Mirror for a sell. **Withdrawn after the research fill-bug fix**
  (BOT_RESEARCH, "Correction"): `start` for every entry; `latest` kept only as a comparison variant.
  Revision 4 (M1) is removed from the code, and revision 5's count-on (R16) never used M1.
  Levels: `L0 + x * (H100 - L0)`; 0 % at the low, 100 % at the high (the owner's scale).
- **Entry:** once a bar has traded above the entry level after `L0` (the bounce), and while the last close is
  above it, a plain limit at the entry level (*"wait for it to fall back to around 38 - 23 %; 61 % if the
  bulls are really strong"*). One order per (`L0`, `H100`).
- **Stop:** below 0 % - `stop_buffer` (`[Claude]` reading of "beyond 88 % - 0 %"); for the 0.618 entry below
  23.6 % (the owner). **Target:** `ext127` / `ext161` (the owner's proposal). At least 2R. R8 as before.
- **Side** - *superseded: only `fib_side = h1` keeps the owner's rules ("The side, after September"); the
  other two are a historical record.* `[Claude]`, three variants: `fib_side = h1` (the H1 side must allow it, as now); `entry` (the
  entry timeframe's own structure: a BUY only once, after `L0`, a bar has traded above the last fixed high
  before `L0`); `any` (no side filter).
- **Count on** (SELL: the ascending run into the top, 3-5 fixed highs each higher than the one before):
  the descending run into `L0` has 3-5 fixed lows (each lower than the one before) with
  divergence on one oscillator at `L0` against the low before it - the three legs the owner pointed to on
  27/10, read by Claude as the M5 lows 4000.00, 3997.23, 3989.14 (MACD and RSI both higher at the last). `[Claude]`: the count is of lower lows
  ("legs"), not of touches of one zone; the M / W is not part of this path yet.
- Range mode (R17) is unchanged and not run in this round.

**The owner on the count (2026-10-29):** "3 to 5 peaks" = legs - *"yes - but when we talk about the
framework, I want both sides included."* So R18's count is the owner's: **BUY - 3-5 legs down, each fixed
low lower than the one before, into `L0`; SELL - 3-5 legs up, each fixed high higher than the one before,
into the top.** Which high is 100 % (`H100`) is researched (BOT_RESEARCH, "Which high is 100 %").

## Claude's rules in the code, written down (2026-10-29, after Codex compared the code with this spec)

Every choice the code makes where the owner gave no rule - each marked `# SPEC-QUESTION:` in
`eye/bot2e.py` - is a `[Claude]` rule:
- **2e, setup age:** no limit - a higher low fixed hours before a window can still give an order there.
- **2e, the zone:** the latest fixed low of the last `counter_pivots` that lies inside any band picks the
  zone (the nearest centre if several); the count is the zone lows **up to and including `L*`** - a zone low
  after `L*` is the higher low of step 3, not part of the exhaustion.
- **Fibo stop:** the stop beyond 23.6 % applies to any entry at or above 0.618.
- **R18, R8 (played out):** read from the bar that first traded above the entry level, not from `L0` - the
  climb out of `L0` always passes under the 23.6 % stop of a 0.618 entry. On that crossing bar only the
  target counts (its low may be the climb itself); from the next bar on, stop and target both count
  (Codex's second code review, 2026-10-29).
- **Money:** the USD reading stops at a balance of 0 or below ("account gone"); the R totals still count
  every trade. A variant's spread must match the scorer's.
- **R18, `L0`:** a low is a bottom only once a later fixed low above it exists.
- **R18, the count** can include more lows than the owner counted by eye (the whole descending run).
- **`fib_side` = `any` / `entry`:** when both the BUY and the SELL view qualify, the later `L0` (top) wins.
- **`fib_side` = `entry`:** "the last fixed high before `L0`" is the pivot just before it.
- **R17 range:** broken by any M5 close beyond the stop level since the later H1 pivot; an edge limit only
  while the last close is on the far side of the edge; the range sees the M5 bars from that pivot's H1 bar.
- **The log:** one row per bar; its reason is the timeframe that got furthest (M5 on a tie).
- **Defaults** (from 2026-10-29): `fib_high` = `start`; `fib_target` = `ext161`; `fib_leg` = `counter`
  (`trend` = revision 5's leg, comparison only); R18's count-on writes the same plain limit at the level as
  count-off (the last-close entry belongs to revision 5's R16 only).

## The side, after September (2026-10-29) - the owner's rule restated

The owner: *"the big trend was down and the trade bought - that alone is already wrong"*, and: *"'ignoring
the trend' - you must except the larger timeframe, understand?"* **The larger timeframe's trend (H1) is
never ignored; only a smaller timeframe's trend may be set aside.** So:
- **`fib_side = h1` is the only side rule that keeps the owner's rules** - the only one a candidate may use.
- `fib_side = entry` (the entry timeframe's structure alone) and `any` (no side) drop the H1 trend: **they
  break the owner's rule and are to be removed from the code.** They are kept in this record only because
  October's and September's runs used them.
- An entry-timeframe confirmation may be added **on top of** the H1 side (H1 allows the side, then the
  entry timeframe's structure confirms) - never instead of it.

**No test or research run until the code is confirmed correct** (the owner, 2026-10-29). The confirmation
planned: remove the side options that break the rule; draw each October trade of the H1-side 61.8 % variant
on its chart for the owner to judge by eye; a last Codex review.

## Revision 7 (2026-10-29) - from the October trades drawn and judged by eye

Claude drew every October decision of the H1-side 61.8 % variant (`eye/draw_trades.py`,
`eye/trades/h1L_618_m5/`) and judged each against METHOD 2e and this spec: of 14, one (07/10) kept every
rule. The owner confirmed the two rules below, and asked that the two open points be run both ways and
judged in the real run.

**R19. A leg that has run is over.** For a BUY (SELL the mirror): once any bar after `L0` has traded above
`H100` (the 100 % level) before the order fills, the leg is finished - the move the setup waits for has
already happened. No order is written on it, and an order resting on it is withdrawn. (The 27/10 picture:
the entry is the pullback after the bounce, before the high breaks.)

*(R20 below is superseded - see "R20 corrected": the 4 USD was the owner's example.)*
**R20. The entry must be reachable - the owner's rule 7.** No order whose entry is more than **4 USD** from
the last close (the owner, 2026-10-28: an order goes no further than 4 USD from the price on the screen).

**Run both ways (Claude's two readings, the owner to judge on the real run):**
- `fib_stop` = `line` (default - beyond the 0 % line, or beyond 23.6 % for a 0.618 entry) | `swing` - also
  beyond the most extreme fixed pivot on the stop side formed after `L0` (the latest higher low for a buy),
  per 2e's "beyond the highest top / lowest bottom"; R recomputed, under 2R no order.
- `fib_level` = `off` (default) | `on` - `L0` must lie inside a support band from the left (2e step 2a, the
  H1 bands; resistance for a sell).

**Acceptance cases (the stored bars, h1 side lows, M5, 0.618, ext161, the decisions of `eye/research/h1L_618_m5/`):**
07/10 07:30 SELL is still written (entry 4159.07); 01/10 06:55, 12/10 06:55, 16/10 13:15, 21/10 21:00 and
27/10 14:00 are refused by R19; 09/10 06:55 is refused by R20.

### Revision 7, made precise after review (Codex and the developer, 2026-10-29) - all `[Claude]` unless said

- **R19, the crossing:** a wick counts - for a BUY any bar with `high > H100`, for a SELL `low < H100`
  (touching it exactly does not). Counted on the setup-timeframe bars from the bar after `L0`'s pivot bar
  (its confirmation bars included) up to the decision. **The scorer** withdraws a resting order when a bar
  *before* the fill bar crosses `H100`; a bar that both fills the order and crosses `H100` keeps the fill
  (the same rule as a fill bar that reaches the stop - order inside a bar is unknown).
- **R19 and R8:** the ext127 / ext161 targets lie beyond `H100`, so R8's target check is covered by R19; R8's
  stop check stays.
- **R20, the price:** the last closed **M5** close at the decision, for an M5 and an M15 leg alike; the
  absolute distance from the entry; over **4 USD** the setup is **passed** (rule 7 also allows taking it at
  the market - not used here: it changes the stop and the R).
- **Leg life:** a leg is used once an order is written on it, whatever happens to that order; a leg that
  has not run (R19) has no age limit. *(Stale legs across a weekend that never crossed `H100` stay
  possible - to be judged on the drawn trades.)*
- **`H100`** is the high the fall began from (`start`) in every rule and acceptance case; `latest` is a
  comparison only.
- **`fib_stop = swing`:** the most extreme fixed pivot on the stop side on the setup timeframe, formed after
  `L0` and fixed by the decision (the lowest such low for a BUY); the stop is one `stop_buffer` beyond the
  farther of that pivot and the line stop. It changes only the 0.618 entry (with a 0 % stop every later low
  is above `L0`).
- **`fib_level = on`:** `L0` inside a single H1 band (R1), edges inclusive, no extra buffer; a SELL's top in
  a resistance band (the view's mirror).
- **The real run** is four independent ledgers - `fib_stop` line / swing x `fib_level` off / on - every other
  setting equal, for the owner to judge. `fib_level = off` leaves out 2e's "at a level from the left": it is
  a comparison, not the rule.
- **The log:** R19's reason is checked right after the leg is found.
- **The 27/10 18:30 pin** (BUY 4003.01): the last M5 close was 4010.95, 7.94 USD away - R20 refuses it. That
  is the rule working (the order never filled - the low after was 4007.53); the pin changes to the refusal.

## Revision 8 (2026-10-29) - H1 is the lean, M5 measures the trend

**Why:** the bot's H1 side (ZigZag 12 on H1, two fixed highs and two fixed lows in order) said "no side" on 13
of the 24 October window opens where gold had moved over 40 USD in 24 h - all six from 22/10 19:30 to 23/10
22:00 while it fell 56-107 USD. A fixed H1 pivot needs about 12 H1 bars; by then the move is over.

**The owner (2026-10-29):** H1 is not a gate that must show a trend before a trade - *"H1 is the lean; the
trend is measured on M5"*; never trade against a clear H1 lean; when the H1 lean is not clear, M5 decides;
*"if you wait for H1 to be clear, the market has run already."*

**R21. The H1 lean `[Claude]`, by the owner's description** ("price below the latest high and making lower
lows"): with `Hf` the latest fixed H1 HIGH and `Lp` the latest fixed H1 LOW before `Hf`:
- **SELL lean** when the last close is below `Hf` and some bar after `Hf` (fixed or not) has traded below
  `Lp` - a lower low made under the latest high;
- **BUY lean** the mirror (`Lf` the latest fixed LOW, `Hp` the latest fixed HIGH before it: last close above
  `Lf` and some bar after `Lf` above `Hp`);
- **no lean** otherwise. (If both were true, the one whose pivot is later wins.)

**R22. The trade's side from M5 `[Claude]`:** for the R18 counter leg, the M5 trend is read at the leg - a
**BUY** needs `H100` (the high the fall began from) to be a **higher high** than the fixed M5 high before it
(the fall is a counter-move in an M5 rise); a **SELL** needs the 100 % low to be a **lower low** than the
fixed M5 low before it. Then: **a BUY is refused when the H1 lean is SELL, a SELL when it is BUY; with no
lean, M5 decides alone.** This replaces step 1's H1 side for the fib path (`fib_side = h1` -> `lean`); the
2e path keeps step 1 unchanged.

**Acceptance cases to check before coding (from the stored bars):** 22/10 19:30 - 23/10 22:00: H1 lean
SELL (not "no side"); 27/10 18:30 BUY leg 4025.45 -> 3989.14: H100 4025.45 against the M5 high before it
(4019.86 / 4019.18) - an M5 higher high, so the BUY side holds (the R20 distance still refuses that order);
07/10 07:30 SELL still written. The share of window opens with "no lean" and with a lean against the 24 h
move is to be reported against the old H1 side (34 % / 49 % "no side"; 2 against).

### Revision 8, made precise after Codex's review (2026-10-29) - `[Claude]` unless said

- **R21 bars and times:** closed **H1** bars only, up to the decision; "after `Hf`" = after `Hf`'s pivot bar
  (by pivot time, not the time it became fixed); comparisons strict (a bar exactly at `Lp` is not a lower
  low; a close exactly at `Hf` is not below it). If both leans held, the one whose pivot (`Hf` or `Lf`) has
  the later pivot time wins. **The lean renews itself:** each new fixed H1 pivot replaces `Hf` / `Lf`, and a
  close back above `Hf` ends a SELL lean - an old break does not keep a lean alive past that.
- **R22 comparator:** the immediately preceding fixed M5 HIGH by pivot time, strictly before `H100`; `H100`
  must be strictly above it (equal is not a higher high). No such pivot - no side, no order. SELL mirrored
  (the immediately preceding fixed M5 LOW, the 100 % low strictly below it). On 27/10 that comparator is
  4019.18 (not 4019.86).
- **R22 is read at the leg** (at `H100`): the trend the counter-move interrupted. It applies always - with
  an H1 lean it must agree with it; with no lean it decides alone.
- **Scope:** revision 8 is the fib path's side rule (`fib_side = lean` replaces `h1`); the 2e path (`mode =
  2e`) is a record and keeps step 1.
- **Acceptance case corrected:** at **07/10 07:30 the H1 lean is BUY** (the low 4104.21, the high 4170.28
  before it exceeded on 06/10) - so the 07/10 SELL is **refused** under the owner's rule (never against a
  clear H1 lean). Claude's earlier acceptance line ("07/10 still written") was wrong.

**Measured by Codex on October's 76 window opens (closed bars):** R21 gives no lean on 9 (11.8 %, against
34 % "no side" before); of the 24 opens after a move over 40 USD in 24 h, no lean on **0** (13 before) and a
lean against the move on 2 (15/10 22:00, 20/10 07:00; 2 before). 22/10 19:30 - 23/10 22:00: SELL lean on all
six.

**Revision 8, last precisions (Codex's second review):** R22's comparator is the preceding M5 high by pivot
time that is **fixed by the decision** (not necessarily by `H100`); the H1 lean checked against it is the lean
**at the decision**. The October count's population: the window opens 07:00, 13:00, 19:30 and 22:00 Thai on
the trading days 01-27/10 where the M5 bar closing then exists (76); a strong move = |the last H1 close - the
H1 close 24 bars before| > 40 USD.

## Revision 9 (2026-10-29) - no chasing, and a range is traded too

**The owner**, on revision 8: two problems will follow - chasing the price, and no trade when the market goes
sideways - *"don't let these two happen."* Claude's definitions below (`[Claude]`) are the means; the owner
judges them on the real run.

**R23. No chasing - three checks, all on the fib path:**
- **(a) The trend is not exhausted:** count the M5 legs of the trend the counter-move interrupted - for a
  BUY, the higher highs in a row up to and including `H100` (each fixed M5 high higher than the one before);
  a SELL the mirror (lower lows to the 100 % low). At **5 or more** (`max_trend_legs`, default 5; run also at
  3), no with-trend order - the owner's own count says the move is ending (METHOD 2e: 3 to 5 peaks, then
  the turn).
- **(b) At the level of the right kind:** `fib_level = on` becomes the default - `L0` (a SELL: its top) inside
  an H1 band, support for a BUY and resistance for a SELL (2e "where").
- **(c) Room to the target:** if an opposite H1 band (resistance for a BUY) lies between the entry and the
  161.8 % target, the target becomes just before that band (2e step 7: `band edge - target_buffer`); R
  recomputed; under 2R no order. *(2e's own target rule, applied to the Fibo target.)*

**R24. A range is traded (called "the owner's sideways rule" here - a misattribution: reading it on the setup
timeframe was Claude's misreading, withdrawn 2026-10-29 evening; see "Rule 11 rewritten" below):** when the H1 lean
is none **and** R22 gives no M5 trend, the range is the latest fixed HIGH and LOW on the **setup timeframe**
(M5 or M15 - not H1, too slow): drawn 0 % at the low, 100 % at the high; a SELL limit at 88 %, stop beyond
127 % + `stop_buffer`, target the low edge + `target_buffer` (the owner's "around 100 %" read as the other
edge); a BUY the mirror; at least 2R; R20 applies; a range is broken (no order, a resting one withdrawn) once
a bar closes beyond its 127 % line. One order per range (its two pivot times). This replaces R17's H1 range for
the fib path.

**To check before coding (from the stored bars):** how many October window opens fall to R24 (no lean and no
M5 trend), and how many orders R23 (a) / (b) / (c) would each remove from revision 7's October run.

## The principles behind revisions 7-9 - what October taught, written to hold in any month (2026-10-29)

The owner: *"have the observations been turned into understanding? Every month these pictures will occur - if
you remember this month's pictures without turning them into a way of thinking or rules, they work for this
month only. Be careful."* The October trades are the evidence; the rules rest on these principles, not on
the trades. **The October cases are tests that the code does what the principle says - never the reason for
a rule.**

1. **A setup is a moment, not a level.** Once the move it waits for has happened (price beyond 100 %), it is
   gone; an order left on it is a different trade. *(R19)*
2. **Enter where the market still is.** An entry far from price is a hope; the deep fill it gets is often the
   idea failing - the pullbacks that reach a deep line are the ones that keep going. *(R20; "Filled against
   not filled")*
3. **The stop belongs beyond what proves the idea wrong** - the latest swing on the stop side, not a fixed
   line that a new swing has already passed. *(`fib_stop = swing`)*
4. **The larger timeframe gives the lean, read from its latest break - not from a structure that takes half a
   day to confirm.** The trade's trend is read on the entry timeframe; a trade never goes against a clear
   lean. *(R21, R22)*
5. **A trend has a count.** After 3-5 legs it is ending; following it further is chasing. *(R23 a)*
6. **Price usually turns before a level; reaching it, it tends to carry on** (the owner) - so a setup need
   not sit on a level, and **the take-profit is the extension price can reach before a major level** *(R23 c,
   the ladder; R23 b withdrawn)*.
7. **A range is traded at its edges**, not skipped. *(R24)*
8. **No number is believed until the trades behind it are drawn and every one keeps the rules.**

**Scale:** numbers carried in USD (the 0.50 buffers; the 4 USD reach, withdrawn - see "R20 corrected") are Claude's
for gold near 4,000 in 2026; the levels, the counts and the percentages are scale-free. **The check that the
rules are not October's:** after the code is built and judged on October, it is run on months **never looked
at** (M5 is stored from 2025-10: November 2025 - August 2026), unchanged, and reported month by month.

## R20 corrected - the reach is a principle, not 4 USD (2026-10-29)

The owner: *"4 USD - that was an example too; I did not mean it as a rule."* The rule is the principle: **the
entry must be a price the market can still reach from where it is** (rule 7; principle 2 above). Claude
wrote the owner's example in as the rule (R20, and "made precise"); corrected here. **R20 now, `[Claude]`,
scale-free:** the distance from the last closed M5 close to the entry may be at most **`max_entry_frac` of
the leg** (`|H100 - L0|`; for R24 the range's height) - default **0.25**, run also at 0.15 and 0.35. A fixed
USD distance is not used. *(For scale only, on October's legs of 20-40 USD, 0.25 is 5-10 USD.)*

## Revision 9 corrected (2026-10-29) - after Codex's review and the owner's answers

**The owner on R23 (c):** *"the target from the Fibo, but the take-profit actually placed - what can be
reached."* **On R23 (b):** *"price turns before it reaches a level; if it reaches the level it usually goes on
the same way - we discussed this in the morning."* So:

- **R23 (b) is withdrawn** - a top / bottom is **not** required to sit in a band. `fib_level` stays a
  comparison only (default `off`). The owner's principle runs the other way: a setup whose pullback reaches a
  level tends to break it.
- **R23 (c) becomes the target ladder** (replaces "room to the target"): for a BUY, **TP = the 161.8 %
  extension if no major resistance band lies between the entry and it; else the 127 % extension if none
  lies before that; else just before the first major band (`near edge - target_buffer`)**; R recomputed;
  under 2R no order. SELL mirrored. **"Major" `[Claude]`:** a single band (R1 rules: pivot centre,
  half-width `band_frac` x the median of the last `band_legs` legs, inclusive edges) built from **H4**
  fixed pivots; a band counts as "between" when any part of it lies strictly between the entry and the
  target. *(H1 bands are too dense - one stood before almost every target in October.)* Variant:
  `major_tf = H1`.
- **R23 (a), counted precisely:** for a BUY, walk back from `H100` over the fixed M5 HIGHs by pivot time
  while each is strictly higher than the one before it; the count is the number of highs in that run,
  `H100` included (three highs = three legs up). For an M15 leg, the same on M15 pivots. At `max_trend_legs`
  (default 5; run also at 3) or more, no order. SELL mirrored on lows.
- **R24 (the range), precisely:**
  - **When:** the H1 lean is none (R21) **and** the setup timeframe shows no trend at the decision -
    `[Claude]`: of its latest two fixed HIGHs and latest two fixed LOWs, neither "both higher" nor "both
    lower" holds.
  - **The range:** the latest fixed HIGH and the latest fixed LOW on the setup timeframe, whichever came
    first; its height = high - low; 0 % at the low, 100 % at the high.
  - **Orders:** a SELL limit at 88 % only while the last M5 close is below it (price inside the range), stop
    above 127 % + `stop_buffer`, TP the low edge + `target_buffer`; a BUY limit at 12 % only while the
    close is above it, stop below -27 % - `stop_buffer`, TP the high edge - `target_buffer`. If both could be
    written, the one nearer the last close. At least 2R; R20 with the range height as the leg.
  - **Broken:** a closed **setup-timeframe** bar beyond the 127 % / -27 % line (no buffer) after the later
    pivot - no order, and a resting one is withdrawn (the scorer marker as R19). One order per range (its
    two pivot times); a new pivot makes a new range.
  - **Not applied to R24:** R18's count, R22, R23 (a), the target ladder.
- **R20 everywhere** uses the last closed M5 close and `max_entry_frac` of the leg (or range height).

## Consolidation into BOT_RULES.md (2026-10-29) - what changed on the way

The rules in force moved to `eye/BOT_RULES.md` after three reviews (Codex, a fresh Sonnet, a fresh Haiku). The
changes against this history, all `[Claude]`: the M5 trend (R22) is read on **M5 pivots** for M5 and M15
legs; a major band counts as **in the way only if its whole width is beyond the entry** (it replaces "any part
between" of revision 9 corrected - a band the entry sits inside is ignored; it gave a target below the entry
on 19/10); the swing stop applies to the **0.618 entry only**; the count needs **3-5** lows (6 or more fail)
and divergence mirrored for a SELL; **defaults** `fib_tf` M5 and `fib_entry` 0.618 (the research's strongest);
`fib_early` (before the line) added as a variant; a priority when several qualify; fills, withdrawals and
exits judged on M5; the plan's "months never looked at" corrected - those months were used by the research,
so the clean test is forward.

**Second review round (2026-10-29, Codex + fresh Sonnet + fresh Haiku) - further changes, all `[Claude]`:** the
trend run's count (R23 a) is read on **M5** pivots for M5 and M15 legs, like R22 (the history had M15 pivots for
an M15 leg); the range's "no trend" is read on **M5** (the owner's trend frame); **the default entry is 0.382**
(the owner's primary "around 38 - 23 %"; 0.618 is the owner's strong-bull case, a variant - the research favoured
it on months that are not clean); an order's prices are fixed when written; the fill is an M5 low at or below
the price from the bar after the decision; a range break ends both sides; `fib_range` on in the real run.

**The entry level (the owner, 2026-10-29):** *"use the level that works best."* `fib_entry` defaults to the best
level by results - all three run, the best kept and checked forward; until the real run, 0.618 (the research's
best). This replaces the second round's 0.382 default.

**Third review round (2026-10-29, Codex + fresh Haiku; Sonnet stopped by a usage limit) - changes, `[Claude]`
unless said:** the lean is recomputed at every decision; the trend-run count anchors on the `H100` price for an
M15 leg; **the owner's M (exactly two lows, no divergence) passes the count** - the history's "not built" left it
refused, against METHOD 2e; which oscillator diverged is written into each decision (owner); setup-timeframe
events withdraw on the M5 bar that closes with them; the SELL near edge of a band; range bounds strict; a final
tie-break (BUY before SELL); the 27/10 acceptance case corrected (at 0.618 the price is under the order price -
rule 6; at 0.382 rule 9 passes - Haiku found the old line wrong on its own numbers); the Fibonacci path stated as
taking the place of 2e's entry and "where", with 2e kept as `mode = 2e`.

**Fourth review round (2026-10-29, Codex + fresh Haiku):** the fill window's expiry and gap fills; "best level"
defined (the highest mean R a filled trade, the owner confirms); "played out" judged on M5; the M / W words and
exact levels in the glossary; the band moves absolute, as of `now`; the files named; a "Withdrawn - do not
build" list. All `[Claude]` except the owner's words quoted.

**Fifth review round (2026-10-29, Codex + fresh Sonnet + fresh Haiku) - BOT_RULES.md rewritten:** a parameter table
and the order of evaluation; the fixed-pivot frame (1,500 bars) and the known bar; the stop section corrected -
`swing` sits above `L0` and does **not** meet 2e step 6 (Claude had written that it met both of the owner's
sentences; Haiku found it); the ladder picks one step, no fall-through; "played out" timed on M5 from the setup
bar; one withdrawal mechanism with its `why`; on the fill bar only the stop counts; realised R reported; the
decision row's columns listed; the acceptance cases with windows switched off, Thai `now`, M5; nine rules no. 4 / 9
replaced by 2e, no. 6 holding. Two points asked of the owner: the 0.618 stop (line vs beyond the lowest bottom) and
what makes an M "clear".

**Sixth review round (2026-10-29, Codex + fresh Sonnet + fresh Haiku):** the owner confirmed the 0.618 stop beyond 23 %
and, for now, any two-low run as the M. Changes, `[Claude]`: the order of evaluation puts "played out" after the stop
and target; only the latest leg is considered (the "later `L0`" tie-break dropped); rule 10 and the bounce read **M5**
bars for M5 and M15 legs; `H100` worded as the highest high of the fall (what the research's `start` and the code
take - one reviewer read "began from" as the first high); a stop cannot withdraw a resting limit; `order_life_bars`
in the table; warm-up restored; the judging bar (+0.15 R a trade, at least 30 filled trades); the withdrawn list
completed; acceptance cases with expected verdicts or *report*.

## Rule 11 rewritten - sideways is read on H1 (2026-10-29 evening)

The owner, on the drawn October trades: *"sideways means in the 1-hour timeframe, and the trend is found in the
5-minute"*; the range counts after price has gone back and forth inside it, *"at least one to two times each side"*;
the trade is in the fourth and fifth leg, *"if it can be found from the third leg, that is good"*; at the top edge
with M5 turning down, the sell on the M5 Fibo pullback - *"yes"*. Rule 11 before this (a range read on the setup
timeframe from its latest two pivots, faded at 88 % / 12 %) was **Claude's misreading** and is withdrawn. In force:
`eye/BOT_RULES.md` rule 11 - the H1 range (pivots touching the 88-127 % / -27-12 % edge zones), sideways from three
pivots, legs 3-5, the side away from the latest pivot, the leg path's rules 2-10 on that side, the target capped at
the opposite edge (`range_tp`).
