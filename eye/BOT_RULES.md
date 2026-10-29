# The bot's rules - the current specification

**This file is the specification in force.** It holds the rules the bot uses now and nothing else. Where each
rule came from, and every rule tried and dropped, is in `eye/BOT_SPEC.md` (the history); measurements are in
`eye/BOT_RESEARCH.md`. A developer builds from this file alone; where it and the history differ, this file
wins.

Each rule says whose it is: **(owner)** - the owner's rule (METHOD 2e); **[Claude]** - a definition Claude gave
where the owner gave none: a named parameter with a default, written into every decision, for the owner to
change. A question or a chart the owner shows, and any number inside one, is never a rule.

## Words used

- **Fixed pivot** - a pivot returned by MT5's ZigZag 12 / 5 / 3 (owner), `app.indicators.chart_read.zigzag_pivots`,
  on closed bars; "fixed by `now`" = confirmed on a bar closed by `now`. A pivot's **time** is its pivot bar's
  open time.
- **Setup timeframe** `fib_tf` [Claude] - M5 (default) or M15; one per run. The leg (rule 2) is read on it.
- **The price** [Claude] - the last closed **M5** close at `now`, whatever the setup timeframe.
- **The counter-leg** - the move the Fibo is drawn on (rule 2). **The trend run** - the moves before it, in the
  trade's direction (rules 3, 5). They are counted separately.
- **BUY and SELL** - every rule is written for a BUY; a SELL is the mirror [Claude]: prices negated (a level
  `L0 + x * leg` becomes `top - x * leg`), highs and lows swap, above and below swap, MACD -> -MACD, RSI ->
  100 - RSI. For a SELL, `L0` is the **top** and `H100` the **low** the rise began from.

## 0. Data, time, costs

- **Data:** FBS-Demo XAUUSD bars - H4, H1, M15, M5 (`data/history/FBS-Demo/XAUUSD`); Thai time = Asia/Bangkok;
  MACD 12 / 26 / 9 as MT5 draws it (`walk.macd_mt5`, main line), RSI 14 (owner).
- **Closed bars only (owner):** at `now` a bar of timeframe `tf` exists only if `open_time + tf <= now`.
- **Windows (owner):** Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai. A decision is made only at
  an M5 close (`now` = the bar's open + 5 min) inside a window, start and end included [Claude]. An order already
  written may fill and run outside the windows [Claude].
- **Spread** 0.30 USD; **buffers** `stop_buffer` and `target_buffer` 0.50 USD; **warm-up** 1,500 bars of each
  timeframe before the first decision - all [Claude].
- **R** [Claude, the owner's "1:2" net of the spread] = (target - entry - spread) / (entry - stop).
- **Not on this path:** 2e's "at a level from the left" (the owner: price usually turns before a level) and 2e's
  structure-break entry (steps 3-5); this path has its own entry (rule 6). The owner's two-peak M / W is not built
  here - with the count on (rule 4) a two-low pullback is refused.

## 1. The H1 lean (owner: "H1 is the lean; the trend is measured on M5")

[Claude, after the owner's "price below the latest high and making lower lows"], closed H1 bars, fixed H1 pivots:
- **SELL lean:** `Hf` = the latest fixed H1 HIGH, `Lp` = the latest fixed H1 LOW before it by time. The last H1
  close is strictly below `Hf` **and** some H1 bar after `Hf`'s pivot bar has a low strictly below `Lp`. A close
  at or above `Hf` ends it; a new fixed pivot renews `Hf` / `Lp`.
- **BUY lean:** the mirror (`Lf`, `Hp`).
- Both hold: the one whose pivot (`Hf` / `Lf`) is later. Neither: **no lean**.
- **(owner)** never against a clear lean; with no lean the M5 trend (rule 3) decides alone - *"if you wait for H1
  to be clear, the market has run already."*

## 2. The counter-leg - the owner's Fibonacci

**(owner)** *"To play an up move, draw high -> low; to play a down move, draw low -> high"* - 0 % at the low,
100 % at the high. On the setup timeframe's fixed pivots [Claude]:
- **`L0`** = the latest fixed LOW that meets all three: strictly lower than every fixed low after it; at least one
  fixed low after it; no setup-timeframe close below it after its pivot bar.
- **The pullback run** = `L0` and, walking back, every earlier fixed low while each is strictly higher than the
  one after it; its **first low** is the oldest.
- **`H100`** = the highest fixed HIGH from the pivot immediately before the first low (inclusive) up to `L0` - the
  high the fall began from [Claude, chosen by research]. None - no leg.
- **Levels** `L0 + x * (H100 - L0)`; **the leg** = `H100 - L0`.
- **One order per leg:** key = side, setup timeframe, `L0` time, `H100` time; a leg is used once an order is
  written on it, whatever happens to it. A leg has **no age limit** (only rule 10 ends it).

## 3. The trend on M5 (owner: "the trend is measured on M5")

[Claude] On **M5** fixed pivots for M5 and M15 legs alike: a BUY needs `H100` strictly above the latest fixed M5
HIGH whose time is strictly before `H100`'s and which is fixed by `now` - the fall is a pullback in an M5 rise.
None - no order on this leg (rule 11 may still apply on its own terms). Then rule 1: refused under a SELL lean.

## 4. The pullback's count - a filter (owner: "try both, counting and not counting")

`fib_count` [Claude]: **off** (default) / **on**. On (owner: "3-5 peaks", counted as **legs, both sides**): the
pullback run (rule 2), `L0` included, has **3 to 5** lows (6 or more fail - [Claude]), **and** divergence at `L0`
against the low just before it on at least one oscillator (owner: "one is enough"). [Claude's rendering]: MACD
main or RSI at `L0`'s pivot bar higher than at the previous low's pivot bar (setup timeframe).

## 5. The trend run's count - no chasing (owner: "don't let it happen")

[Claude - Claude's extension of the owner's 3-5 count to the trend; provisional, for the owner to judge] From
`H100`, step back over the fixed **M5** HIGHs by time while each earlier high is strictly lower than the one
after it; the number of highs, `H100` included, is the trend's legs. At `max_trend_legs` (default **5**; variant
3) or more, no order.

## 6. The entry

- **Level** `fib_entry` [Claude, from the owner's "wait for it to fall back to around 38 - 23 %; if the bulls are
  really strong, maybe from 61 %"]: **0.382** (default), 0.236, 0.618.
- **Order price** = the level + `fib_early x leg` (above the level for a BUY) - `fib_early` [Claude, the owner's
  idea of getting in before the line]: **0** (default), variant **0.10** with `fib_stop = line_tight`, at the
  0.382 level only.
- **The bounce** [Claude]: an order is written only once a setup-timeframe bar after `L0`'s pivot bar has traded
  above the order price, and only while the price is above it - a **plain buy limit** at the order price.
- **Played out** [Claude]: from that first bar above the order price (setup timeframe), a touch of the target
  rule 8 selects - on that bar or later - or a stop touch on a later bar: no order. On the first bar only the
  target counts (its low may be the climb out of `L0`).

## 7. The stop (owner: "beyond the lowest bottom"; for the 61 % entry "beyond 23 %")

- 0.382 / 0.236: `L0 - stop_buffer` [Claude's reading of "beyond 88 % - 0 %"].
- 0.618: the 23.6 % level - `stop_buffer` (owner: "beyond 23 %"; the 23.6 % level and the buffer [Claude]).
- `fib_stop` [Claude], 0.618 only: **line** (default, the above) or **swing** - one `stop_buffer` below the lower of
  the 23.6 % level and the lowest fixed setup-timeframe low formed after `L0` and fixed by `now`. The owner's two
  stop sentences differ (2e "beyond the highest top / lowest bottom"; the Fibo "beyond 23 %"): swing keeps both,
  line the second.
- `line_tight` [Claude], with `fib_early` only: the 0.382 level - `stop_buffer`.

## 8. The target - the ladder (owner: "the target from the Fibo; the take-profit placed is what can be reached")

| take-profit | when |
|---|---|
| 161.8 % extension (`L0 + 1.618 x leg - target_buffer`) | no major band in the way up to it |
| 127.2 % extension (`L0 + 1.272 x leg - target_buffer`) | a band in the way before 161.8 %, none before 127.2 % |
| the nearest band's near edge - `target_buffer` | a band in the way before 127.2 % |

At least **1:2 (owner)** - R under 2.0: no order. **Major bands** [Claude], `major_tf` **H4** (variant H1): every
fixed pivot of that timeframe (highs and lows) among its last `level_bars` = 500 bars whose time is at least
`level_min_age_h` = 24 h before `now`; each its own band (not merged), centre the pivot price, half-width
`band_frac` = 0.10 x the median of the last `band_legs` = 20 moves between consecutive fixed pivots of that
timeframe; edges inclusive. **In the way:** a band whose near (lower) edge is strictly above the order price and
strictly below the extension tested; a band the order price sits inside is ignored; "nearest" = the lowest near
edge (ties: either - same price).

## 9. The entry must be reachable (owner, the nine rules' no. 7: "a price the market can reach from here")

[Claude] |the price - the order price| at most `max_entry_frac` x the leg (a range: its height) - default
**0.25**, variants 0.15 and 0.35. (The owner's "4 USD" was an example.)

## 10. A leg that has run is over (owner)

[Claude's test]: once a setup-timeframe bar after `L0`'s pivot bar has a high strictly above `H100` (a wick
counts, a touch does not), no order on the leg; a resting one is withdrawn (rule 12).

## 11. The range (owner: sideways - "enter at the edge, around 88 % - 127 %", the target "around 100 %")

`fib_range` [Claude]: **on** (default in the real run) / off.
- **When** [Claude]: no H1 lean, **and** no trend on **M5** at `now` (the owner's trend frame): of the latest two
  fixed M5 highs and the latest two fixed M5 lows, neither "higher high and higher low" nor "lower high and lower
  low"; fewer than two of either - no range.
- **The range** [Claude]: the latest fixed HIGH and the latest fixed LOW on the setup timeframe, in whichever
  order; height = high - low; 0 % at the low. A new fixed pivot makes a new range; "the later pivot" = the later
  of the two by time.
- **Orders** [Claude, within the owner's 88-127 % and "around 100 %" read as the other edge]: a SELL limit at 88 %
  while the price is between 0 % and 88 %, stop above 127 % + `stop_buffer`, TP the low edge + `target_buffer`; a
  BUY limit at 12 % while the price is between 12 % and 100 %, stop below -27 % - `stop_buffer`, TP the high edge -
  `target_buffer`; if both, the one nearer the price. At least 2R; rule 9 with the height. No minimum height.
- **Broken** [Claude]: a closed setup-timeframe bar beyond 127 % or -27 % (no buffer) after the later pivot ends the
  range for both sides; a resting order is withdrawn (rule 12). One order per range (its two pivot times).
- Rules 3-8 and 10 do not apply to the range.

## 12. Orders and their life

- **At a time** `max_orders` [Claude], default 1: pending orders plus open trades.
- **Fixed when written** [Claude]: an order's price, stop, target and R never change after it is written.
- **Fill** [Claude], on **M5** bars from the bar after the decision, within 24 of them: a buy limit fills on the
  first bar whose low is at or below its price, at its price.
- **Withdrawn** [Claude] - only by an M5 bar **before** the fill bar: its stop or target touched; a leg's `H100`
  crossed by a wick (the decision text carries `withdraw beyond <H100>`); a range broken by a **setup-timeframe
  close** (the text carries `range break <tf> close beyond <price> / <price>`). A bar that both fills and crosses
  keeps the fill.
- **Held (owner)** until the stop or the target, judged on M5 bars from the fill bar on, no time limit; a bar
  touching both counts as the stop [Claude], the fill bar included.

## 13. Which one, when several qualify [Claude]

A leg before a range; among legs, the later `L0`; then the order price nearer the price.

## 14. What the bot writes [Claude]

- **The decision row** - the columns of `eye/ledger.csv`, `reader` = `bot2e`; `structure` names: the leg (`L0`,
  `H100`, prices and Thai times) or the range (its pivots), the levels, the order price, stop, target and which
  ladder step, R, the lean, the M5 trend comparison, the counts, every parameter, and the withdrawal marker.
- **The log** - one row per evaluated bar: the time, the lean, each rule's state and numbers, and the reason no
  order was written.
- **Acceptance cases** (the stored bars; tests must pin them): 22/10 19:30 - 23/10 22:00 Thai: H1 lean SELL;
  07/10 07:30: H1 lean BUY, so the SELL leg there is refused; 27/10 18:30: the BUY leg 4025.45 -> 3989.14 passes
  rule 3 (`H100` above the M5 high 4019.18) and is refused by rule 9 at 0.25; 19/10 06:55: no ladder target below
  the order price.

## 15. How results are judged

[Claude, from the owner's "no test run until the code is confirmed correct"] No number is believed until each
trade behind it is drawn (`eye/draw_trades.py`) and checked against these rules. The real run: the defaults,
beside these variants one at a time - `fib_entry` 0.618 and 0.236, `fib_stop` swing, `fib_count` on, `fib_early`
0.10 with `line_tight`, `fib_tf` M15, `max_trend_legs` 3, `major_tf` H1, `max_entry_frac` 0.15 and 0.35. October
2026 first, then the stored months before it, month by month - **not clean**: the research that chose `H100`
and the entry depth used them; **the clean test is forward**, on the months after 2026-10-28 as their bars arrive.

## Code status (not a rule)

`eye/bot2e.py` at fff8c1a builds rules 2, 6 (at the line), 7, 10 and the scorer's `H100` withdrawal; everything
else here is **to build** - including the lean (it replaces the old H1 side), the count as written in rule 4, the
defaults (`fib_tf` M5, `fib_entry` 0.382, `fib_target` = the ladder, `fib_range` on), and the code comment that
calls 4 USD "the owner's rule 7".
