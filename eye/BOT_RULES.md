# The bot's rules - the current specification

**This file is the specification in force** - the rules the bot uses now, their parameters, the acceptance
cases a build must pass, and the plan for judging it. Where each rule came from, and every rule tried and
dropped, is in `eye/BOT_SPEC.md` (the history); measurements are in `eye/BOT_RESEARCH.md`. A developer builds
from this file alone; where it and the history differ, this file wins.

Each rule says whose it is: **(owner)** - the owner's rule or words (METHOD 2e); **[Claude]** - a definition
Claude gave where the owner gave none: a named parameter with a default, written into every decision, for the
owner to change. A question or a chart the owner shows, and any number inside one, is never a rule.

## Words used

- **Fixed pivot** - a pivot returned by `app.indicators.chart_read.zigzag_pivots` (MT5's ZigZag 12 / 5 / 3, owner)
  run on the last **1,500 closed bars present in the data** of the timeframe being read, up to `now` [Claude]; it is **known** from its
  `confirm_pos` bar (the opposite candidate's bar + `backstep`) - "fixed by `now`" means that bar has closed by
  `now`. A pivot's **time** is its pivot bar's open time (UTC in the data; Thai = Asia/Bangkok for reading).
- **Setup timeframe** `fib_tf` [Claude] - M5 or M15, one per run; the leg (rule 2) is read on it. **Sideways is read
  on H1** (owner; rule 11).
- **The price** [Claude] - the last closed **M5** close at `now`.
- **The counter-leg** [Claude's term] - the move the Fibo is drawn on (rule 2). **The trend run** [Claude's term] -
  the moves before it in the trade's direction (rules 3, 5).
- **M and W** (owner) - the owner's M is a **buy**, formed coming down into a support; the W a **sell** at a
  resistance (the textbook's reversed).
- **Exact levels** [Claude]: Fibo 0.236 / 0.382 / 0.618; extensions 1.272 / 1.618; the H1 range's edge zones -0.27 to
  0.12 (the low edge) and 0.88 to 1.27 (the high edge), as shares of its height above its low (rule 11).
- **BUY and SELL** - rules 1-10 are written for a BUY; a SELL is their mirror [Claude]: prices negated (a level
  `L0 + x * leg` becomes `top - x * leg`), highs and lows swap, above and below swap, MACD -> -MACD, RSI -> 100 - RSI;
  for a SELL, `L0` is the **top** and `H100` the **low** the rise began from. The spread stays a positive cost.
  Rule 11 (the H1 range) is written for both sides and is not mirrored.

## Order of evaluation, at each M5 close inside a window

0 (time, window, warm-up, `max_orders`) -> 11 (the H1 state: a range, a trend or none - and the side it gives; with
`h1_read` lean, rule 1 gives the side outside a sideways range) -> 2 (the latest leg) -> 10 (has it run?) -> 3 (M5 trend, and the side) -> 4 (count, if
on) -> 5 (trend run) -> 6 (level, order price, bounce) -> 7 (stop) -> 8 (target, 1:2) -> 6 (played out, which needs 7
and 8) -> 9 (reach) -> write. Rule 13 decides between a BUY and a SELL candidate; rule 12 governs the order's life.

## Parameters

| name | values | default | whose |
|---|---|---|---|
| `mode` | fib, 2e | fib (2e is a record only - not run) | [Claude] |
| `fib_tf` | M5, M15 | M5 | [Claude] |
| `fib_entry` | 0.618, 0.382, 0.236 | 0.618 (until the real run picks the best - rule 6) | owner's levels, [Claude] default |
| `fib_early` | 0, 0.10 (x the leg) | 0 | [Claude], the owner's idea |
| `fib_stop` | line, swing, line_tight | line (line and swing matter at 0.618 only - at 0.382 / 0.236 the stop is `L0 - stop_buffer`; line_tight is the 0.382 variant with `fib_early`, rule 7) | line: owner (0.618 "beyond 23 %"); swing, line_tight: [Claude] |
| `fib_count` | off, on | off | owner: "try both"; the default [Claude] |
| `max_trend_legs` | 5, 3 | 5 | [Claude] |
| `fib_target` | 1.618, 1.272 | 1.618 | the owner's extensions; default [Claude] (rule 8) |
| `max_entry_frac` | 0.15, 0.25, 0.35 | 0.25 | [Claude] |
| `h1_read` | state, lean | state | [Claude] (rule 11's H1 state gives the side; `lean` = rule 1, a record for comparison) |
| `fib_lean` | on, off | on | [Claude], a research switch: the H1 trend side refuses the other side, or not (rules 1, 11) |
| `fib_range` | on, off | on | [Claude] (rule 11: read the H1 range) |
| `range_min_leg` | 3, 4 | 3 | the owner's "from the third leg"; variant 4 [Claude] |
| `range_tp` | edge, ext | edge | [Claude] (rule 11) |
| `stop_buffer`, `target_buffer` | USD | 0.50, 0.50 | [Claude] |
| `spread` | USD | 0.30 | [Claude] |
| `max_orders` | count | 1 | [Claude] |
| `order_life_bars` | M5 bars | 24 | [Claude] |
| `min_r` | R | 2.0 | owner (1:2) |

A combination without meaning (`fib_early` > 0 with an entry other than 0.382 or without `line_tight`; `fib_stop`
swing with an entry other than 0.618; `line_tight` without `fib_early`) is refused at start [Claude].

## 0. Data, time, costs

- **Data:** FBS-Demo XAUUSD bars - H4, H1, M15, M5 (`data/history/FBS-Demo/XAUUSD`); MACD 12 / 26 / 9 as MT5 draws it
  (`walk.macd_mt5`, main line), RSI 14 (owner).
- **Closed bars only** (the project's rule, CLAUDE.md): at `now` a bar of timeframe `tf` exists only if
  `open_time + tf <= now`.
- **Warm-up** [Claude]: no decision until each timeframe read (H4, H1, M15, M5) has 1,500 closed bars before `now`.
- **Windows (owner):** Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai. A decision is made only at an
  M5 close (`now` = that bar's open + 5 min) inside a window, start and end included [Claude]. A written order may
  fill and run outside the windows [Claude].
- **R** [Claude] = (target - entry - spread) / (entry - stop) for a BUY, (entry - target - spread) / (stop - entry)
  for a SELL, `entry` = the order price - the **planned** R. The owner's rule is the 1:2 floor; the net-of-spread form is Claude's. The spread enters only R and the
  floor; fills and touches use the bar prices.
- **This path is the owner's Fibonacci** (METHOD 2e, "The owner's Fibonacci"): its entry (rule 6) and target (rule 8)
  take the place of 2e's break-and-retest entry (2e steps 3-5) and "at a level from the left" (2e steps 1-2), by the
  owner's later words *"price usually turns before a level; when it reaches the level it usually carries on"*
  (METHOD 2e, "Levels and the turn"). The 2e setup stays in the code as `mode = 2e` - a record only; **the default `mode` is `fib`** (this path). METHOD's nine rules
  were written for the walk by hand; on this path [Claude]: no. 4 and no. 9 were replaced by 2e; no. 1-3 (frames,
  levels from the left, wait for a level) and no. 5 (the structure at the level) are replaced by rules 1-3, 6 and the
  owner's "Levels and the turn"; no. 6 ("enter on a timeframe, exit on that timeframe") holds - the stop and target
  are the setup's, M5 bars only time the touches; no. 7 is rule 9; no. 8 is rule 6's played-out test.

## 1. The H1 lean (owner: "H1 is the lean; the trend is measured on M5")

[Claude, after the owner's description as Claude restated it and the owner confirmed: price below the latest high
and making lower lows], closed H1 bars, fixed H1 pivots,
recomputed at every decision (not latched):
- **SELL lean:** `Hf` = the latest fixed H1 HIGH, `Lp` = the latest fixed H1 LOW with a time before `Hf`'s. The last
  H1 close is strictly below `Hf`, **and** some H1 bar after `Hf`'s pivot bar has a low strictly below `Lp`. No `Lp` -
  no SELL lean.
- **BUY lean:** the mirror (`Lf`, `Hp`).
- Both hold: the one whose pivot (`Hf` / `Lf`) is later. Neither: **no lean**.
- **(owner)** never against a clear lean; with no lean the M5 trend (rule 3) decides alone - *"if you wait for H1 to
  be clear, the market has run already."*
- **Under test** [Claude, at the owner's word, 2026-10-29]: this reading, and three other readings of H1, showed no
  edge at the traded move sizes, and October with and without it is under 30 fills (`eye/BOT_RESEARCH.md`, the
  sections from "The H1 lean and the major levels - tested"). Until the owner decides, this rule stays as written.
- **`fib_lean` off** [Claude, the owner's word 2026-10-29: run the bot with and without the lean]: the lean is still
  computed and written (rule 14; while H1 is sideways it is not read - rule 11) but refuses nothing (rule 3's refusal by the H1 trend or the lean is skipped); the H1 range's side
  (rule 11) is not affected. `on` is this rule as written. `off` goes against the owner's "never against a
  clear lean" (METHOD 2e) - it is a measurement the owner asked for, never the real-run setting without the owner's word.
- **While H1 is sideways** (rule 11) the H1 range gives the side instead of this rule.
- **With `h1_read` state (the default) this rule gives no side** - rule 11's H1 trend does; the lean is still
  computed and written for the record (rule 14). `h1_read` lean is this rule as the side outside a sideways range.

## 2. The counter-leg - the owner's Fibonacci

**(owner)** *"To play an up move, draw high -> low; to play a down move, draw low -> high"* - 0 % at the low, 100 % at
the high. On the setup timeframe's fixed pivots [Claude]:
- **`L0`** = the latest fixed LOW that meets all three: strictly lower than every fixed low after it; at least one
  fixed low after it; no setup-timeframe close below it after its pivot bar.
- **The pullback run** = `L0` and, walking back, every earlier fixed low while each is strictly higher than the one
  after it; its **first low** is the oldest. Its length = the number of lows, `L0` included (three lows = three legs
  down).
- **`H100`** = the **highest** fixed HIGH from the high pivot immediately before the first low (inclusive) up to `L0` -
  the top of the whole fall. The owner's words are "the previous highest price"; the research compared this with
  the high just before `L0` and chose the highest [Claude] (BOT_RESEARCH, `start`). None - no leg.
- **Levels** `L0 + x * (H100 - L0)`; **the leg** = `H100 - L0`.
- **The latest leg of each side** is considered at a decision [Claude] - the latest `L0` (a BUY) and the latest top (a
  SELL), each evaluated on its own; an older leg of the same side is not.
- **One order per leg** [Claude]: key = side, setup timeframe, `L0` time, `H100` time; the leg is **used** once an order
  is written on it, whatever happens to that order - in this run or an earlier one (the keys of the rows already in
  the ledger are used from the start of a run - every row the run keeps, earlier or later than the days it walks;
  the rows of the days it walks are replaced). Until then, while it is still the latest leg, it is a candidate
  at every decision, with no age limit; refused once (by a rule, or because `max_orders` was full) it may pass
  later. Rule 10 ends it for good.

## 3. The trend on M5 (owner: "the trend is measured on M5")

[Claude] On **M5** fixed pivots for M5 and M15 legs alike: a BUY needs `H100` strictly above the latest fixed M5 HIGH
whose time is strictly before `H100`'s and which is fixed by `now` - the fall is a pullback in an M5 rise. None - no
order on this leg. Then the side (rule 11): **while H1 is sideways**, refused when the range's side is SELL (from leg 6
there is no range side and nothing is refused here); **otherwise** refused when the H1 side is SELL - the H1 trend
(`h1_read` state) or the lean (`h1_read` lean); skipped when `fib_lean` is off. No H1 side: nothing is refused.

## 4. The pullback's count - a filter (owner: "try both, counting and not counting")

`fib_count`: **off** (default) - any pullback run passes. **On** (owner: "3-5 peaks", counted as **legs, both sides** -
asked whether that means legs with lower lows, the owner said yes; so a leg here = one low of the run [Claude's
rendering]): the run has **3 to 5** lows - 1 low and 6 or more fail [Claude] - **and** divergence at `L0` against the previous low
of the run on at least one oscillator (owner: "one is enough") - [Claude's rendering]: MACD main or RSI at `L0`'s pivot
bar higher than at the previous low's pivot bar, setup timeframe. **Or the owner's M** (owner: two peaks that make an M
count; a clear M is entered without divergence): a run of exactly **2** lows passes without divergence - any two-low run is taken as the M
(the owner, 2026-10-29: *"try it this way first"*). Which oscillator
diverged (MACD / RSI / both / none) is written into every decision (owner: "the record says which").

## 5. The trend run's count - no chasing

The owner, on the spec: *"two problems: chasing the price, and no trade when it goes sideways - don't let these two
happen."* [Claude - provisional, for the owner to judge] The `H100` price is the anchor (for an M15 leg too). Take the
fixed **M5** HIGHs fixed by `now` with a time strictly before `H100`'s, latest first, while each is strictly lower than
the one counted before it (the first strictly lower than `H100`); the trend's legs = 1 + their number. At
`max_trend_legs` (5; variant 3) or more, no order. [Claude's inference]: the owner's 3-5 count, applied to the trend,
says a fifth leg is the trend ending, and buying its pullback is chasing.

## 6. The entry

- **Level** `fib_entry` - from the owner's *"wait for it to fall back to around 38 - 23 %; if the bulls are really
  strong, maybe from 61 %"*. **The default is the level that works best** (owner, 2026-10-29: *"use the level that works
  best"*): [Claude] the three are run on the same months; best = the highest mean R a filled trade, every trade drawn
  and checked (ties: more trades); the owner confirms; **the choice is made on months that are not clean (rule 15) and
  frozen before the forward test.** Until the real run: 0.618 (the research's best, [Claude]).
- **Order price** = the level + `fib_early x leg` (above the level for a BUY) - `fib_early` [Claude, the owner's idea of
  getting in before the line]: 0 by default; variant 0.10 with `line_tight`, at the 0.382 level only.
- **The bounce** [Claude]: an order is written only once an **M5** bar after `L0`'s pivot bar (opening at or after the
  pivot bar's close) has a high strictly above
  the order price, and only while the price is strictly above it - a **plain buy limit**. A touch of the order price
  after the bounce and before `now` does not stop it (no order was resting then).
- **Played out** [Claude], checked after rules 7 and 8: on the **M5** bars from that first M5 bar above the order price
  up to `now`, a high at or above the order's target (rule 8, or rule 11's edge target), or a low at or below the stop on a later M5 bar - no
  order. (On that first bar only the target counts: its low may be the climb out of `L0`.)

## 7. The stop

The owner's words differ by case: 2e step 6 - *"beyond the highest top / lowest bottom"*; the Fibonacci - *"the SL is
beyond 88 % - 0 %"*, and for the 61 % entry *"beyond 23 %"*. **The owner confirmed (2026-10-29): for the 0.618
entry the stop is beyond 23 %** - the Fibonacci's specific words govern:
- 0.382 / 0.236: `L0 - stop_buffer` (beyond the lowest bottom - both sentences hold).
- 0.618, `fib_stop` **line**: the 23.6 % level - `stop_buffer` ("beyond 23 %"; above `L0`, so not beyond the lowest
  bottom).
- 0.618, `fib_stop` **swing** [Claude, a variant]: one `stop_buffer` below the lower of the 23.6 % level and the **lowest** fixed
  setup-timeframe low formed after `L0` and fixed by `now`. No such low: the line stop.
- `line_tight` [Claude, a variant] (with `fib_early`): the 0.382 level - `stop_buffer`.

## 8. The target - the ladder

The owner: *"the target from the Fibo; the take-profit placed is what can be reached"* - 1.618 if nothing major stands
before it, else 1.272, else just before that level (METHOD 2e). **A level is major only if price turns at it more
often than at a control** - the test in `eye/BOT_RESEARCH.md`, "The H1 lean and the major levels - tested" [Claude, at
the owner's word *"find the answers by testing and proof"*, 2026-10-29]. No tested band - H1 or H4 pivots, one or
several - turned price more than the control with any consistency, so **no level counts as major on this path**
and the take-profit is the extension:

- **TP** = `L0 + fib_target x leg - target_buffer`, `fib_target` 1.618 (variant 1.272) [Claude, the owner's two
  extensions; 1.618 is the owner's first step]. A SELL: the mirror, `L0 - fib_target x leg +
  target_buffer`.
- In legs `range_min_leg` to 5 of a sideways H1, rule 11's `range_tp` may bring the TP nearer (the opposite edge of
  the H1 range); not from leg 6.
- If R (rule 0) is under `min_r`, or the TP is not beyond the order price (above it for a BUY, below for a SELL), no
  order.
- A level definition that passes the test (consistently above the control, month by month) brings back the steps before a major level (1.272, then just before the
  level); until one does, none is built.

*Example (27/10, BUY, leg 3989.14 -> 4025.45 = 36.31, entry 0.382 = 4003.01, stop 3988.64): the raw 1.618 extension is
4047.89; TP = 4047.89 - 0.50 = 4047.39, R = (4047.39 - 4003.01 - 0.30) / 14.37 = 3.07.*

## 9. The entry must be reachable

METHOD's nine rules, no. 7 - *"the entry must be a price the market can reach from here"* - with the owner's reason,
*"an obvious level may never be reached precisely because it is obvious."* [Claude] abs(the price - the order price) at
most `max_entry_frac` x the leg. The owner's "4 USD" was an example.

## 10. A leg that has run is over

The owner confirmed it (2026-10-29: *"confirm the two you said"* - this rule and rule 9's reach), from the drawn
October trades. [Claude's test], one test for both uses: once any **M5** bar after `L0`'s pivot bar - an M5 bar whose
open is at or after the pivot bar's close - has a high **strictly above** `H100` (a touch at `H100` is not enough), no order on the
leg, ever, and a resting order on it is withdrawn (rule 12).

## 11. Sideways - the H1 range gives the side (owner: sideways is read on H1, the trend is found on M5)

The owner, 2026-10-29: *"sideways means in the 1-hour timeframe, and the trend is found in the 5-minute"*; the range
counts once price has gone back and forth inside it, *"at least one to two times each side"*, and then the trade is in
the fourth and fifth leg - *"if it can be found from the third leg, that is good"*; asked whether, at the top edge
with M5 turning down, the sell is taken on the M5 Fibo pullback as on a leg: *"yes"*. The edges are the owner's
*"around 88 - 127 %"*, the target *"around 100 %"* (METHOD 2e, "The owner's Fibonacci"). `fib_range` on: rule 11 is
read; off: no H1 state is read at all - never sideways, no range side, no edge target, no H1 trend side; with
`h1_read` lean the lean alone (rule 1), with `h1_read` state no H1 side.

- **The H1 state** [Claude, the owner's way of reading it, 2026-10-30: the swings inside a range do not end it; a
  range ends when H1 closes beyond its edge, and the market then trends that way until price goes back and forth
  again - the owner, on the drawn prototype: *"about this; fix the code to do what we think"*]. Read at `now` from the
  H1 fixed pivots (fixed by `now`, time order, oldest first) and the closed H1 closes of the same frame, by walking
  the pivots once:
  - **A range starts** with two consecutive pivots `P(k)`, `P(k+1)` - the first two of the frame, or the two named
    under "A break": edges `lo` = the lower price, `hi` = the higher, `h = hi - lo`; **legs = 1**; the **last touch** =
    the kind of `P(k+1)` (HIGH or LOW). A pair with `h` <= 0 is dropped: `P(k+2)` and `P(k+3)` start the range.
  - **Each later pivot**, tested with `h` from the edges as they stood before it: a HIGH at or above `lo + 0.88 h` **touches the high
    edge** - `hi` becomes max(`hi`, its price); a LOW at or below `lo + 0.12 h` **touches the low edge** - `lo` becomes
    min(`lo`, its price); a touch of the other edge than the last touch adds **1 leg** and becomes the last touch (two
    touches of the same edge in a row add nothing). A pivot between the two is **in the middle and ignored** - the
    range stands.
  - **A break**: after each pivot `P(i)` is taken in (the range's second pivot included), the H1 closes on the bars
    after its pivot bar, up to and including the next pivot's bar (the last closed bar when there is none), are
    checked against the edges as they stand after it - `h` recomputed after any widening: the first close strictly
    above `hi + 0.27 h` is a break **up**, strictly below `lo - 0.27 h` a break **down**. The range ends; **the H1
    trend** becomes up / down; `P(i+1)` (the pivot whose bar ends that segment) and `P(i+2)` start the next range.
  - **At `now`**: the range in force with **legs >= 2** (price has reached each edge and come back at least once) -
    H1 is **sideways**. Otherwise, after a break: H1 is **trending** the break's way (a range still forming after a
    break - legs 1 - leaves the trend in force). Otherwise (a range forming, legs 1, with no break before it in the frame, or no range yet): **no H1 side**.
  - **The H1 trend's side** (`h1_read` state): up - **BUY** only; down - **SELL** only (rule 3).
- **Sideways** is the state above; the range's edges are `lo` / `hi` as they stand at `now`.
- **The leg being traded** = the range's legs + 1 (the move away from the last touch): **3** with two legs. Trades are
  taken in legs `range_min_leg` (default **3**, the owner's *"from the third leg"*; variant 4) to **5** (the owner's
  *"the fourth and fifth"*). A sideways H1 whose leg is under `range_min_leg` (leg 3 with the variant 4): **no order**
  [Claude - the range is not yet ready for that variant, and H1 is not trending].
- **Leg 6 on** - the owner, 2026-10-29: *"at the sixth leg, be ready for it to run through the edge, which can be
  where we make a big profit"*. [Claude's reading, confirmed by the owner the same evening:] from leg 6 the range gives **no side and no edge target**: the
  legs of either side are taken on the M5 trend (rules 2-10; the lean is still not read - H1 is still sideways),
  with rule 8's extension as the target, so a move through the edge is not cut at it.
- **The side**, in legs `range_min_leg` to 5 [Claude, from the owner's legs]: away from the last touch - the last
  touch at the high edge: **SELL**; at the low edge: **BUY**. Only legs of that side are traded (leg 6 on: above); rules 2-10 apply unchanged (the M5 trend is found by
  rules 2-3, the entry by the Fibo, rule 6). The lean (rule 1) is not used while H1 is sideways: an H1 that reads as
  sideways has no clear lean (the owner's "sideways is read on H1"; the precedence is [Claude]).
- **The target** (owner, 2026-10-29: *"go by the 5-minute target, and look at the 1-hour price edges alongside, as
  support, resistance and the take-profit"*) - `range_tp`: `edge` (default; the formula [Claude]) - the nearer of rule 8's extension and the opposite edge less `target_buffer` (a BUY:
  min(extension TP, `hi - target_buffer`); a SELL: max(extension TP, `lo + target_buffer`)); `ext` - rule 8 alone. R
  and the 1:2 floor are computed on the target chosen.
- A range order is a leg order in every other way (rule 12: its fill, withdrawal by its `H100`, hold); the decision
  writes the H1 state (sideways: the edges, the legs, the leg traded, the last touch; trending: up / down) in its
  structure.

## 12. Orders and their life [Claude, except the hold]

- **At a time** `max_orders`: pending orders plus open trades. **Event order at each M5 close** [Claude]: first the
  bar just closed updates the orders already written (fills, exits, expiries, withdrawals); then the decision
  counts `max_orders` and evaluates.
- **Fixed when written:** an order's price, stop, target and planned R never change. The scorer reports the
  **realised** R: the actual fill price in the numerator, the planned risk (order price to stop) in the
  denominator (below).
- **Fill**, on **M5** bars from the bar after the decision, within `order_life_bars` (the last included): a buy limit fills on the first bar whose
  low is at or below its price, at min(that bar's open, the price); a sell limit at max(open, price). Not filled after
  the last of them: **expired** (`no fill`); it frees `max_orders`; its leg stays used.
- **Withdrawn** - by an M5 bar **before** the fill bar only; **the scorer** writes the reason as the row's `why` (the
  bot writes only the markers below; where both a target and an `H100` crossing happen on one bar, the target's
  reason is written): its target touched
  (`no fill (stop or target first)` - a stop cannot be reached first, the limit lies between); a leg's `H100` crossed strictly (`withdraw beyond <H100>` in the decision
  text), judged on M5 bars as rule 10 says. A bar that both fills and withdraws keeps the fill.
- **Held (owner)** until the stop or the target, no time limit, judged on M5 bars from the fill bar on. On the fill bar
  only the stop counts; from the next bar a bar touching both counts as the stop. **Exit price:** the stop or target
  price; a bar that opens beyond the stop exits at its open [Claude]. **Realised R** = (exit - fill - spread) / (order
  price - stop) for a BUY (mirror for a SELL) - `r_net`: the denominator is the planned risk, the same for every fill
  of the order, so a gap fill beyond the stop is still defined [Claude]. A trade still open when the data ends is `open`, not a result. A change
  of the H1 range or the lean does not touch an order already written.

## 13. Which one, when several qualify [Claude]

A BUY and a SELL candidate at one decision (a leg of each side, when neither the lean nor the H1 range picks a side):
the smaller |the price - the order price|; then a BUY before a SELL.

## 14. What the bot writes, and the acceptance cases [Claude]

- **Files:** decisions to `eye/bot_ledger.csv`, the log to `eye/bot_log.csv`; research runs to
  `eye/research/<variant>/`.
- **The decision row** - the columns of `eye/ledger.csv`: id, cutoff_thai, decided_at, reader = `bot2e`, side, entry,
  stop, target; fill, exit, why, r_net, at_decision_r, missed_by left to the scorer; trigger, rules, conflict, setup
  empty; `structure` names the leg (`L0`, `H100`, prices and Thai times), the levels, the
  order price, stop, target and its extension (or the range edge), planned R, the lean (`not read (H1 sideways)` while H1 is
  sideways), the H1 range when sideways (rule 11), the M5 trend comparison, the counts and which
  oscillator diverged, every parameter, and the withdrawal marker.
- **The log** - one row per evaluated bar: the time, the lean, each rule's state and numbers, and the reason no order
  was written; with several candidates, the reason of the one that got furthest in the order of evaluation (the last
  rule it reached; on a tie, the BUY).
- **Acceptance cases** - evaluated with the window test switched off where the time is outside a window; times are
  Thai, `now` = the time given; `fib_tf` M5, other parameters at their defaults unless named. Each expected outcome
  below is what the rules give; the developer computes every case from the bars and **reports** each one - a case that
  does not come out as written is reported, not bent to fit; where a part is marked *report*, the developer reports
  what the bars give:
  - The H1 state (computed with the research prototype `eye/research/h1_state.py`; the developer confirms or reports):
    01/10/2026 07:00 - **down** (a range forming after the 26/09 break, legs 1); 06/10 13:00 - **sideways**, `lo`
    4110.78, `hi` 4228.63, legs 2, last touch LOW; 07/10 07:30 and 08/10 07:00 - sideways, `lo` 4104.21, `hi` 4228.63,
    legs 2, last touch LOW (leg 3, **BUY**); 10/10 13:00 - sideways, `lo` 4066.42, `hi` 4228.63, legs 2, LOW; 16/10 19:30,
    19/10 07:00, 22/10 13:00, 19:30, 22:00 and 23/10 07:00 - sideways, 4066.42 - 4228.63, legs 4, last touch LOW (leg 5,
    **BUY**); 23/10 13:00, 19:30, 22:00 and 24/10 07:00 - **down**; 27/10 18:30 - sideways, `lo` 3975.58, `hi` 4034.23,
    legs 2, last touch LOW (leg 3, **BUY**); 27/10 19:30 - the same range, legs 3, last touch HIGH (leg 4, **SELL**);
    28/10 07:00 - **up**.
  - With `h1_read` lean, at 22/10/2026 19:30 and 22:00 and 23/10/2026 07:00, 13:00, 19:30 and 22:00 (rule 1 computed
    and written in any case): lean **SELL**.
  - 07/10/2026 07:30: H1 sideways, leg 3, **BUY** side; the SELL candidate (top 4184.25, 100 % low 4143.51) - **no
    order** (the range's side); the BUY candidate - *report*. With `h1_read` lean the lean is BUY - the same refusal.
  - 27/10/2026 18:30, the BUY leg 4025.45 -> 3989.14: rule 3 passes (`H100` 4025.45 above the M5 high 4019.18); at 0.618
    the order price 4011.58 is above the price 4010.95 - **no order** (rule 6); at 0.382 the order price 4003.01 is 7.94
    away, within 0.25 x 36.31 = 9.08 (rule 9). H1 is sideways there (the H1 state case above): the BUY is the range's
    side, the lean is not read, and `range_tp` edge gives TP 4033.73 (the H1 high 4034.23 - 0.50), R 2.12 - **an order**;
    with `range_tp` ext, TP 4047.39, R 3.07 (rule 8's example).
  - 19/10/2026 07:00, the BUY leg 4198.73 -> 4155.81 at 0.618 (order price 4182.33): *report* the target and R (R under 2 means
    no order).
  - `fib_lean` off: at 23/10/2026 13:00 (H1 down) a BUY leg is not refused by the H1 side - *report* how far it gets;
    while H1 is sideways (07/10 07:30, 27/10 18:30) the range's side still applies - the same outcomes as above.
  - With `range_min_leg` 4 at 27/10/2026 18:30: leg 3 - no order. With `fib_range` off at 18:30: no H1 range is read,
    the H1 side is none with `h1_read` state (or the lean SELL with `h1_read` lean) - *report*.
  - Rules 4, 5 and 12 have no stored-bar case yet: the developer tests each branch on constructed bars (unit tests)
    and reports which stored-bar case first exercises it.

## 15. How results are judged

[Claude, from the owner's "no test or research run until the code is confirmed correct"] No number is believed until
each trade behind it is drawn (`eye/draw_trades.py`) and checked against these rules. **The bar** is the owner's goal:
at least **+0.15 R a trade after costs** (CLAUDE.md); [Claude] not judged on fewer than 30 filled trades. The real run: the defaults, beside these
variants one at a time - `fib_entry` 0.382 and 0.236, `fib_stop` swing (at 0.618), `fib_count` on, `fib_early` 0.10 with
`line_tight` (at 0.382), `fib_tf` M15, `max_trend_legs` 3, `fib_target` 1.272, `max_entry_frac` 0.15 and 0.35, `fib_lean` off,
`range_min_leg` 4, `range_tp` ext, `fib_range` off, `h1_read` lean. October 2026
first, then the stored months before it (M5 from 2025-10), month by month - **not clean**: the research that chose `H100` and the entry
depth used them. **The clean test is forward**, on the months after 2026-10-28 as their bars arrive.

## Withdrawn - do not build

None of these is a parameter to implement; they live only in the history (`eye/BOT_SPEC.md`): a side from H1
structure alone (`fib_side` h1 / entry / any - replaced by the lean); revision 5's leg drawn in the trade's direction; the M1 entry; a fixed USD
reach; "the leg's extreme must sit on a level" and 2e's "Where" row on this path (replaced by the owner's "Levels and
the turn"); the bands of H1 / H4 pivots capping the target and their parameters (`major_tf`, `level_bars`,
`level_min_age_h`, `band_frac`, `band_legs` on this path - no band turned price more than a control); **the range read on the setup timeframe (M5 / M15) and faded at its
88 % / 12 % edges** (rule 11 before 2026-10-29 evening - Claude's misreading: the owner's sideways is on H1, the trend
on M5); **the H1 range that needed every pivot at an edge** (rule 11 of 2026-10-29 evening - its middle swings
ended every range; replaced by the H1 state, 2026-10-30); a depth-dependent choice of `H100`; the 2e
path as a live option; the nine rules no. 4 ("trade the fifth leg") and no. 9 (target a full leg away) - replaced by
2e before this path.

## Code status, 2026-10-30 (not a rule)

`eye/bot2e.py` builds every rule above except **rule 11's H1 state** (and `h1_read`): it still has the range that needs
every pivot at an edge. **To build:** the H1 state (rule 11), `h1_read`, the H1 trend side in rule 3, the acceptance
cases above. Rule 1 stays in the code as `h1_read` lean.
