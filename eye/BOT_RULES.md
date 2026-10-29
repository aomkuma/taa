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
  run on the closed bars of a frame that starts **1,500 bars before `now`** [Claude]; it is **known** from its
  `confirm_pos` bar (the opposite candidate's bar + `backstep`) - "fixed by `now`" means that bar has closed by
  `now`. A pivot's **time** is its pivot bar's open time (UTC in the data; Thai = Asia/Bangkok for reading).
- **Setup timeframe** `fib_tf` [Claude] - M5 or M15, one per run; the leg (rule 2) and the range (rule 11) are read
  on it.
- **The price** [Claude] - the last closed **M5** close at `now`.
- **The counter-leg** [Claude's term] - the move the Fibo is drawn on (rule 2). **The trend run** [Claude's term] -
  the moves before it in the trade's direction (rules 3, 5).
- **M and W** (owner) - the owner's M is a **buy**, formed coming down into a support; the W a **sell** at a
  resistance (the textbook's reversed).
- **Exact levels** [Claude]: Fibo 0.236 / 0.382 / 0.618; extensions 1.272 / 1.618; the range 0.12 / 0.88 with its
  stops and breaks at -0.27 / 1.27.
- **BUY and SELL** - rules 1-10 are written for a BUY; a SELL is their mirror [Claude]: prices negated (a level
  `L0 + x * leg` becomes `top - x * leg`), highs and lows swap, above and below swap, MACD -> -MACD, RSI -> 100 - RSI;
  for a SELL, `L0` is the **top** and `H100` the **low** the rise began from. The spread stays a positive cost.
  Rule 11 is written for both sides and is not mirrored.

## Order of evaluation, at each M5 close inside a window

0 (time, window, warm-up, `max_orders`) -> 1 (lean) -> 2 (leg) -> 10 (has it run?) -> 3 (M5 trend, and the lean) ->
4 (count, if on) -> 5 (trend run) -> 6 (entry, bounce, played out) -> 7 (stop) -> 8 (target, 1:2) -> 9 (reach) ->
write. Then 11 (range) if no leg was written and its conditions hold. Rule 13 picks one; rule 12 governs the
order's life.

## Parameters

| name | values | default | whose |
|---|---|---|---|
| `fib_tf` | M5, M15 | M5 | [Claude] |
| `fib_entry` | 0.618, 0.382, 0.236 | the level that works best (rule 6); until the real run 0.618 | owner's levels, [Claude] default |
| `fib_early` | 0, 0.10 (x the leg) | 0 | [Claude], the owner's idea |
| `fib_stop` | line, swing, line_tight | line | [Claude] |
| `fib_count` | off, on | off | owner: "try both" |
| `max_trend_legs` | 5, 3 | 5 | [Claude] |
| `major_tf` | H4, H1 | H4 | [Claude] |
| `level_bars`, `level_min_age_h`, `band_frac`, `band_legs` | 500 bars, 24 h, 0.10, 20 | as listed | [Claude] |
| `max_entry_frac` | 0.15, 0.25, 0.35 | 0.25 | [Claude] |
| `fib_range` | on, off | on | [Claude] |
| `stop_buffer`, `target_buffer` | USD | 0.50, 0.50 | [Claude] |
| `spread` | USD | 0.30 | [Claude] |
| `max_orders` | count | 1 | [Claude] |
| `min_r` | | 2.0 | owner (1:2) |

A combination without meaning (`fib_early` > 0 with an entry other than 0.382; `fib_stop` swing with an entry
other than 0.618; `line_tight` without `fib_early`) is refused at start [Claude].

## 0. Data, time, costs

- **Data:** FBS-Demo XAUUSD bars - H4, H1, M15, M5 (`data/history/FBS-Demo/XAUUSD`); MACD 12 / 26 / 9 as MT5 draws it
  (`walk.macd_mt5`, main line), RSI 14 (owner).
- **Closed bars only** (the project's rule, CLAUDE.md): at `now` a bar of timeframe `tf` exists only if
  `open_time + tf <= now`.
- **Windows (owner):** Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai. A decision is made only at an
  M5 close (`now` = that bar's open + 5 min) inside a window, start and end included [Claude]. A written order may
  fill and run outside the windows [Claude].
- **R** [Claude] = (target - entry - spread) / (entry - stop) for a BUY, (entry - target - spread) / (stop - entry)
  for a SELL. The owner's rule is the 1:2 floor; the net-of-spread form is Claude's. The spread enters only R and the
  floor; fills and touches use the bar prices.
- **This path is the owner's Fibonacci** (METHOD 2e, "The owner's Fibonacci"): its entry (rule 6) and target (rule 8)
  take the place of 2e's break-and-retest entry (2e steps 3-5) and "at a level from the left" (2e steps 1-2), by the
  owner's later words *"price usually turns before a level; when it reaches the level it usually carries on"*
  (METHOD 2e, "Levels and the turn"). The 2e setup stays in the code as `mode = 2e` - a record only. The owner's nine
  rules no. 4 and no. 9 were replaced by 2e earlier (METHOD); no. 6 ("enter on a timeframe, exit on that timeframe")
  holds - the stop and target are the setup's, M5 bars only time the touches.

## 1. The H1 lean (owner: "H1 is the lean; the trend is measured on M5")

[Claude, after the owner's "price below the latest high and making lower lows"], closed H1 bars, fixed H1 pivots,
recomputed at every decision (not latched):
- **SELL lean:** `Hf` = the latest fixed H1 HIGH, `Lp` = the latest fixed H1 LOW with a time before `Hf`'s. The last
  H1 close is strictly below `Hf`, **and** some H1 bar after `Hf`'s pivot bar has a low strictly below `Lp`. No `Lp` -
  no SELL lean.
- **BUY lean:** the mirror (`Lf`, `Hp`).
- Both hold: the one whose pivot (`Hf` / `Lf`) is later. Neither: **no lean**.
- **(owner)** never against a clear lean; with no lean the M5 trend (rule 3) decides alone - *"if you wait for H1 to
  be clear, the market has run already."*

## 2. The counter-leg - the owner's Fibonacci

**(owner)** *"To play an up move, draw high -> low; to play a down move, draw low -> high"* - 0 % at the low, 100 % at
the high. On the setup timeframe's fixed pivots [Claude]:
- **`L0`** = the latest fixed LOW that meets all three: strictly lower than every fixed low after it; at least one
  fixed low after it; no setup-timeframe close below it after its pivot bar.
- **The pullback run** = `L0` and, walking back, every earlier fixed low while each is strictly higher than the one
  after it; its **first low** is the oldest. Its length = the number of lows, `L0` included (three lows = three legs
  down).
- **`H100`** = the highest fixed HIGH from the high pivot immediately before the first low (inclusive) up to `L0`. The
  owner's words are "the previous highest price"; which high, when a fall has several, was chosen by research: the
  high the fall began from [Claude]. None - no leg.
- **Levels** `L0 + x * (H100 - L0)`; **the leg** = `H100 - L0`.
- **One order per leg** [Claude]: key = side, setup timeframe, `L0` time, `H100` time; the leg is **used** once an order
  is written on it, whatever happens to that order. Until then it stays a candidate at every decision, with no age
  limit; a leg refused by a rule (or because `max_orders` was full) may pass at a later decision. Rule 10 ends it for
  good.

## 3. The trend on M5 (owner: "the trend is measured on M5")

[Claude] On **M5** fixed pivots for M5 and M15 legs alike: a BUY needs `H100` strictly above the latest fixed M5 HIGH
whose time is strictly before `H100`'s and which is fixed by `now` - the fall is a pullback in an M5 rise. None - no
order on this leg. Then rule 1: refused under a SELL lean. *(This one comparison can hold in a broadening market that
rule 11 calls "no trend"; rule 13 decides between them.)*

## 4. The pullback's count - a filter (owner: "try both, counting and not counting")

`fib_count`: **off** (default) - any pullback run passes. **On** (owner: "3-5 peaks", counted as **legs, both sides**):
the run has **3 to 5** lows - 1 low and 6 or more fail [Claude] - **and** divergence at `L0` against the previous low
of the run on at least one oscillator (owner: "one is enough") - [Claude's rendering]: MACD main or RSI at `L0`'s pivot
bar higher than at the previous low's pivot bar, setup timeframe. **Or the owner's M** (owner: two peaks that make an M
count; a clear M is entered without divergence): a run of exactly **2** lows passes without divergence - [Claude,
provisional: any two-low run is taken as the M; the owner has been asked what makes an M "clear"]. Which oscillator
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
- **The bounce** [Claude]: an order is written only once a **setup-timeframe** bar after `L0`'s pivot bar has a high
  strictly above the order price, and only while the price is strictly above it - a **plain buy limit**.
- **Played out** [Claude]: judged on the **M5** bars from the start of that setup-timeframe bar (its first M5 bar) up to
  `now`: if the target rule 8 selects was touched (a high at or above it), or the stop was touched on an M5 bar after
  the setup bar's first one (a low at or below it), no order. *(Within that first M5 bar only the target counts - its
  low may be the climb out of `L0`.)*

## 7. The stop

The owner's words differ by case: 2e step 6 - *"beyond the highest top / lowest bottom"*; the Fibonacci - *"the SL is
beyond 88 % - 0 %"*, and for the 61 % entry *"beyond 23 %"*. [Claude] the Fibonacci's specific words govern:
- 0.382 / 0.236: `L0 - stop_buffer` (beyond the lowest bottom - both sentences hold).
- 0.618, `fib_stop` **line**: the 23.6 % level - `stop_buffer` ("beyond 23 %"; above `L0`, so not beyond the lowest
  bottom).
- 0.618, `fib_stop` **swing**: one `stop_buffer` below the lower of the 23.6 % level and the lowest fixed setup-timeframe
  low formed after `L0` and fixed by `now` (beyond the latest swing; still above `L0`). No such low: the line stop.
- `line_tight` (with `fib_early`): the 0.382 level - `stop_buffer`.

## 8. The target - the ladder

The owner: *"the target from the Fibo; the take-profit placed is what can be reached."* The three steps are the
owner's; the bands and the "in the way" test are [Claude]. **One step is chosen by the bands; if its R is under
`min_r`, or its target is not above the order price, no order - there is no fall-through to another step.**

| take-profit | when |
|---|---|
| 1.618 extension: `L0 + 1.618 x leg - target_buffer` | no band in the way up to it |
| 1.272 extension: `L0 + 1.272 x leg - target_buffer` | a band in the way before 1.618, none before 1.272 |
| the nearest band's near edge - `target_buffer` | a band in the way before 1.272 |

**Bands** [Claude], on `major_tf`: every fixed pivot (highs and lows) among its last `level_bars` bars whose time is at
least `level_min_age_h` before `now` is one band, not merged, centre the pivot price, half-width `band_frac` x the median
of the last `band_legs` absolute price moves between consecutive fixed pivots of that timeframe, as fixed by `now`
(fewer than `band_legs` moves: the moves there are; fewer than 2 pivots: no bands); edges inclusive. **In the way:** a
band whose near edge (the lower for a BUY) lies strictly above the order price and strictly below the extension
tested; a band the order price sits inside is ignored; "nearest" = the near edge closest to the order price.
*Example (27/10, BUY, leg 3989.14 -> 4025.45 = 36.31, entry 0.382 = 4003.01, stop 3988.64): 1.618 = 4047.39; if no band
lies above 4003.01 and below 4047.39, TP 4047.39, R = (4047.39 - 4003.01 - 0.30) / 14.37 = 3.07.*

## 9. The entry must be reachable

The owner's nine rules, no. 7: *"the entry must be a price the market can reach from here."* [Claude] |the price - the
order price| at most `max_entry_frac` x the leg (a range: its height). The owner's "4 USD" was an example.

## 10. A leg that has run is over

The owner confirmed it (2026-10-29), from the drawn October trades. [Claude's test]: once a **setup-timeframe** bar
after `L0`'s pivot bar has a high **strictly above** `H100` (a touch at `H100` is not enough), no order on the leg,
ever; a resting order is withdrawn under rule 12 by the same strict test on **M5** bars.

## 11. The range - the owner's sideways rule

The owner: *"Sideways: enter at the edge, around 88 % - 127 %"*; the target *"around 100 %"*. Written for both sides,
not mirrored. `fib_range`: on in the real run [Claude].
- **When** [Claude]: no H1 lean, **and** no trend on **M5** at `now`: of the latest two fixed M5 highs and the latest
  two fixed M5 lows, neither "higher high and higher low" nor "lower high and lower low"; fewer than two of either -
  no range.
- **The range** [Claude]: the latest fixed HIGH and the latest fixed LOW on the setup timeframe, in whichever order;
  height = high - low; 0 % at the low, 100 % at the high. A new fixed pivot makes a new range.
- **Orders** [Claude, within the owner's "around 88 - 127 %"; "around 100 %" read as the edge far from the entry]:
  - **SELL** limit at 0.88 while 0 < the price's level < 0.88; stop 1.27 + `stop_buffer`; TP the low edge (0) +
    `target_buffer`.
  - **BUY** limit at 0.12 while 0.12 < the price's level < 1; stop -0.27 - `stop_buffer`; TP the high edge (1) -
    `target_buffer`.
  - If both qualify, the one nearer the price. At least `min_r`; rule 9 with the height. No minimum height.
- **Broken** [Claude]: a closed setup-timeframe bar beyond 1.27 or -0.27 (no buffer) after the later of the two pivots
  ends the range for both sides; a resting order is withdrawn (rule 12). One order per range (its two pivot times).
- Rules 3-8 and 10 do not apply to the range.

## 12. Orders and their life [Claude, except the hold]

- **At a time** `max_orders`: pending orders plus open trades.
- **Fixed when written:** an order's price, stop, target and planned R never change. The scorer reports the
  **realised** R, from the actual fill price.
- **Fill**, on **M5** bars from the bar after the decision, the 24th included: a buy limit fills on the first bar whose
  low is at or below its price, at min(that bar's open, the price); a sell limit at max(open, price). Not filled after
  the 24th bar: **expired** (`no fill`); it frees `max_orders`; its leg or range stays used.
- **Withdrawn** - by an M5 bar **before** the fill bar only, the reason written as the row's `why`: its stop or target
  touched (`no fill (stop or target first)`); a leg's `H100` crossed strictly (`withdraw beyond <H100>` in the decision
  text); a range broken by a setup-timeframe close (`range break <tf> close beyond <price> / <price>`) - an M15 close
  counts on the M5 bar that closes with it. A bar that both fills and withdraws keeps the fill.
- **Held (owner)** until the stop or the target, no time limit, judged on M5 bars from the fill bar on. On the fill bar
  only the stop counts; from the next bar a bar touching both counts as the stop.

## 13. Which one, when several qualify [Claude]

A leg is preferred to a range; among legs, the later `L0`; then the order price nearer the price; then a BUY before a
SELL.

## 14. What the bot writes, and the acceptance cases [Claude]

- **Files:** decisions to `eye/bot_ledger.csv`, the log to `eye/bot_log.csv`; research runs to
  `eye/research/<variant>/`.
- **The decision row** - the columns of `eye/ledger.csv`: id, cutoff_thai, decided_at, reader = `bot2e`, side, entry,
  stop, target; fill, exit, why, r_net, at_decision_r, missed_by left to the scorer; trigger, rules, conflict, setup
  empty; `structure` names the leg (`L0`, `H100`, prices and Thai times) or the range (its pivots), the levels, the
  order price, stop, target and its ladder step, planned R, the lean, the M5 trend comparison, the counts and which
  oscillator diverged, every parameter, and the withdrawal marker.
- **The log** - one row per evaluated bar: the time, the lean, each rule's state and numbers, and the reason no order
  was written; with several candidates, the reason of the one that got furthest (on a tie, the leg before the range).
- **Acceptance cases** - evaluated with the window test switched off where the time is outside a window; times are
  Thai, `now` = the time given; `fib_tf` M5. The developer computes each case's full outcome (lean, the rule-6 bounce
  state, order or no order, ladder step, R) from the bars and reports it - a case that does not come out as written is
  reported, not bent to fit:
  - 22/10/2026 19:30 to 23/10/2026 22:00, every window open: H1 lean SELL.
  - 07/10/2026 07:30: H1 lean BUY - the SELL leg there is refused.
  - 27/10/2026 18:30, the BUY leg 4025.45 -> 3989.14: rule 3 passes (`H100` above the M5 high 4019.18); at 0.618 the order
    price 4011.58 is above the price 4010.95 - no order (rule 6); at 0.382 the order price 4003.01 is 7.94 away, within
    0.25 x 36.31 = 9.08 (rule 9) - the lean and the rest decide.
  - 19/10/2026 07:00: no ladder target at or below the order price.

## 15. How results are judged

[Claude, from the owner's "no test run until the code is confirmed correct"] No number is believed until each trade
behind it is drawn (`eye/draw_trades.py`) and checked against these rules. The real run: the defaults, beside these
variants one at a time - `fib_entry` 0.382 and 0.236, `fib_stop` swing (at 0.618), `fib_count` on, `fib_early` 0.10 with
`line_tight` (at 0.382), `fib_tf` M15, `max_trend_legs` 3, `major_tf` H1, `max_entry_frac` 0.15 and 0.35. October 2026
first, then the stored months before it, month by month - **not clean**: the research that chose `H100` and the entry
depth used them. **The clean test is forward**, on the months after 2026-10-28 as their bars arrive.

## Withdrawn - do not build

None of these is a parameter to implement; they live only in the history (`eye/BOT_SPEC.md`): a side from H1
structure alone (replaced by the lean); revision 5's leg drawn in the trade's direction; the M1 entry; a fixed USD
reach; "the leg's extreme must sit on a level" (replaced by the owner's "Levels and the turn"); the fixed 1.618 target
without the ladder; a range drawn on H1; a depth-dependent choice of `H100`; the 2e path as a live option.

## Code status, 2026-10-29 (not a rule)

`eye/bot2e.py` at commit fff8c1a builds rules 2, 6 (at the level), 7 (line, swing), 10 and the scorer's `H100`
withdrawal. Everything else here is **to build**, including: the lean (it replaces the code's `fib_side` / H1 side),
rules 3, 4 as written, 5, 8, 9 (the code has a fixed 4.0 USD and a comment calling it "the owner's rule 7"), 11, 12's
expiry and gap fills, 13, the parameter defaults, and the refusal of meaningless combinations.
