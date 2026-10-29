# The bot's rules - the current specification

**This file is the specification in force.** It holds only the rules the bot uses now. Where each rule came from, and every rule tried and dropped, is in `eye/BOT_SPEC.md` (the
history) and `eye/BOT_RESEARCH.md` (the measurements). A developer builds from this file alone; where this
file and the history differ, this file wins.

Every rule says whose it is: **(owner)** - the owner's rule (METHOD 2e); **[Claude]** - a definition Claude
gave where the owner gave none: a parameter with a default, written into every decision, for the owner to
change. A question or a chart the owner shows, and any number inside one, is never a rule.

Everything is written for a **BUY**; a **SELL is the mirror of every line** (prices negated: highs and lows
swap, "above" and "below" swap, MACD -> -MACD, RSI -> 100 - RSI).

**Status of the code** (`eye/bot2e.py`, commit fff8c1a): built - rules 2, 4, 6 (at the line), 7, 10, 12, and the drawing tool of
rule 14; **to build** - rule 1 (the lean replaces the old H1 side), rule 3, rule 5, rule 6's early entry, rule
8 (the ladder replaces the fixed 161.8 % target), rule 9 (a share of the leg replaces the fixed 4 USD), rule
11 (the range on the setup timeframe replaces the H1 range), rule 13 (priority); the defaults `fib_tf` M5 and `fib_entry` 0.618 (the code has M15 and 0.382); the code's
comment calling 4 USD "the owner's rule 7" (it was an example). The `mode = 2e` path in the
code is a record of the first setup and is not part of these rules.

## 0. Data, time, windows

- **Data:** FBS-Demo XAUUSD bars - H4, H1, M15, M5 (`data/history/FBS-Demo/XAUUSD`); Thai time = Asia/Bangkok.
- **Closed bars only (owner):** at the moment `now` a bar of timeframe `tf` exists only if
  `open_time + tf <= now`. **Pivots** are MT5's ZigZag 12 / 5 / 3 (owner) - `app.indicators.chart_read.zigzag_pivots`
  on the closed bars; only the pivots it returns (fixed - confirmed `backstep` bars after the opposite extreme)
  are used; "fixed by `now`" = confirmed on a bar closed by `now`. MACD 12 / 26 / 9 as MT5 draws it
  (`walk.macd_mt5`, the main line), RSI 14 (owner).
- **Windows (owner):** Asia 07:00-09:00, London 13:00-15:00, New York 19:30-23:00 Thai; decisions only at an M5
  close inside a window, the start and end included [Claude]; orders already written live on outside the
  windows [Claude].
- **Setup timeframe** `fib_tf` [Claude]: M5 (default) or M15 - where the leg (rule 2) and the range (rule 11) are
  read. **"The price"** = the last closed M5 close at `now`, for either setup timeframe.
- **Spread** 0.30 USD [Claude]. **Buffers** `stop_buffer`, `target_buffer` 0.50 USD [Claude].
- **R** = (target - entry - spread) / (entry - stop) for a BUY; (entry - target - spread) / (stop - entry) for a
  SELL.
- **Warm-up** [Claude]: at least 1,500 bars of each timeframe before the first decision.
- **Not on this path:** 2e's "at a level from the left" (the owner: price usually turns before a level) and
  2e's structure-break entry (steps 3-5) - the Fibo path has its own entry (rule 6). `fib_level` (the leg's
  extreme inside a band) is a comparison only, off.

## 1. The H1 lean (owner: "H1 is the lean; the trend is measured on M5")

From closed H1 bars and fixed H1 pivots at `now` [Claude, after the owner's "price below the latest high and
making lower lows"]:
- **SELL lean:** `Hf` = the latest fixed H1 HIGH, `Lp` = the latest fixed H1 LOW before it (by pivot time). The
  last H1 close is strictly below `Hf`, **and** some H1 bar after `Hf`'s pivot bar has a low strictly below
  `Lp`.
- **BUY lean:** `Lf` = the latest fixed H1 LOW, `Hp` = the latest fixed H1 HIGH before it; the last H1 close
  strictly above `Lf`, and some H1 bar after `Lf`'s pivot bar has a high strictly above `Hp`.
- Both hold: the one whose pivot (`Hf` / `Lf`) is later by pivot time. Neither: **no lean**.
- **(owner)** never trade against a clear lean; with no lean the M5 trend decides alone - *"if you wait for H1
  to be clear, the market has run already."*

## 2. The leg - the owner's Fibonacci

**(owner)** *"To play an up move, draw high -> low; to play a down move, draw low -> high."* For a BUY the Fibo
is drawn on the fall that has just ended [Claude's wording], on the setup timeframe's fixed pivots:
- **`L0`** [Claude] = the latest fixed LOW that is strictly lower than every fixed low after it, with at least
  one fixed low after it, and no setup-timeframe close below it since.
- **The run into `L0`** [Claude]: walking back from `L0` over the fixed lows while each earlier low is strictly
  higher than the one after it; its first low is the oldest of them.
- **`H100`** = the highest fixed HIGH from the pivot just before the run's first low (if it is a high) up to
  `L0` - the high the fall began from [Claude, chosen by research - BOT_RESEARCH "Correction - the fill bug"].
  No such high - no leg.
- **Levels:** `L0 + x * (H100 - L0)` - 0 % at the low, 100 % at the high (owner). **The leg** = `H100 - L0`.
- **One order per leg** [Claude]: the key is side, setup timeframe, `L0` time, `H100` time; a leg is used once an
  order is written on it, whatever happens to that order. A leg that has not run (rule 10) has **no age limit**
  [Claude] - legs carried over a weekend stay possible, to be judged on the drawn trades.

## 3. The trade's trend on M5 (owner: "the trend is measured on M5")

[Claude] Read **on M5 pivots**, whatever the setup timeframe, at the leg: a **BUY** needs `H100` strictly above
the immediately preceding fixed **M5** HIGH by pivot time (fixed by `now`) - the fall is a pullback in an M5
rise. No preceding high - no order on this leg (it does not fall to the range). Then rule 1: a BUY is refused under a SELL lean; allowed under a BUY lean
or no lean.

## 4. The count of the counter-move - a setup filter (owner: "try both, counting and not counting")

`fib_count` [Claude]: **off** (default) or **on**. On (owner: "3-5 peaks" counted as **legs, both sides**): the
run into `L0` (rule 2) has **3 to 5** lows - 6 or more fails [Claude] - and **divergence** at `L0` against the low
before it - the immediately preceding fixed low - on at least one oscillator (owner: one is enough); as
[Claude] renders the book: price lower or equal while MACD main is higher, or RSI is higher.
(SELL: 3-5 higher highs into the top; price higher or equal while MACD main is lower or RSI lower.) The owner's
other form - two peaks making an M (buy) / W (sell) - is **not built** in this path.

## 5. No chasing - the trend's own count (owner: "don't let it happen")

[Claude - provisional, for the owner to judge on the real run] This counts the **trend** the leg pulled back in
(rule 4 counts the **pullback**): from `H100`, step back over the fixed M5 HIGHs by pivot time while each
earlier high is strictly lower than the one after it; the number of highs in that run, `H100` included, is the
trend's legs. At `max_trend_legs` (default **5**; variant 3) or more, no order - after 3-5 legs the trend is
ending (the owner's count), and following it is chasing. *(The variant 3 refuses most legs after any three
higher highs.)*

## 6. The entry

- **Entry level** `fib_entry` [Claude, after the owner's "around 38 - 23 %" and "from 61 % if the bulls are really
  strong"]: **0.618** (default - the strongest in the research), 0.382, 0.236.
- **Before the line** `fib_early` [Claude, the owner's idea "get in before the price you meant, the stop just
  beyond the line"]: the order sits `fib_early x leg` before the level - default **0** (at the level); variant
  **0.10** with `fib_stop = line_tight` (rule 7). *(Research: it held only at 38.2 % on M5.)*
- **The bounce** [Claude, from the owner's "wait for it to fall back to around 38 - 23 %"]: an order is written only once a
  setup-timeframe bar after `L0`'s pivot bar has traded above the entry price, and only while the price (the
  last M5 close) is above
  it - a **plain limit** at the entry price.
- **Played out** [Claude]: from that first bar above the entry, a touch of **the target rule 8 selects** - on
  that bar or after - or a stop touch on a later setup-timeframe bar ends the setup; no order. (Rule 10 covers
  the run beyond 100 % separately.)

## 7. The stop (owner: "beyond the lowest bottom"; for the 61 % entry "beyond 23 %")

- Entry 0.382 / 0.236: `L0 - stop_buffer` [Claude's reading of "beyond 88 % - 0 %"].
- Entry 0.618: below the 23.6 % level - `stop_buffer` (owner: "beyond 23 %"; the 23.6 % level and the buffer
  [Claude]).
- `fib_stop` [Claude], for the **0.618 entry only**: **line** (the above) or **swing** - one `stop_buffer` below
  the lower of the 23.6 % line and the lowest fixed setup-timeframe low formed after `L0` and fixed by `now`.
  *(Run both ways. The owner's two stop sentences differ - 2e "beyond the highest top / lowest bottom" and
  the Fibo "beyond 23 %"; `swing` keeps both, `line` keeps the second.)*
- `line_tight` [Claude], only with `fib_early`: the level - `stop_buffer` (the stop just beyond the line).

## 8. The target - the ladder (owner: "the target from the Fibo; the take-profit placed is what can be reached")

TP = the **161.8 %** extension (`L0 + 1.618 x leg - target_buffer`) if no major band stands in the way; else the
**127.2 %** extension if none stands before that; else **just before the nearest major band** (its near edge -
`target_buffer`). **At least 1:2 (owner)** - under R 2.0, no order (*"no trade, for now"*).
- **Major bands** [Claude], `major_tf` = **H4** (variant H1): every fixed pivot (highs and lows) of that
  timeframe within its last 500 bars whose pivot bar is at least 24 h before `now` becomes one band, centre the
  pivot price, half-width 0.10 x the median of the last 20 legs (|price change between consecutive fixed
  pivots|); bands are not merged; edges inclusive.
- **"In the way"** [Claude, replacing the history's "any part between"]: a band whose near edge lies strictly
  above the entry and strictly below the extension tested; a band the entry sits inside is ignored (price is
  already in it). "Nearest" = the lowest near edge above the entry.

## 9. The entry must be reachable (owner, rule 7 of the nine: "a price the market can reach from here")

[Claude] |the price - the entry| at most **`max_entry_frac` x the leg** (for a range, its height) - default
**0.25**, variants 0.15 and 0.35. The owner's "4 USD" was an example, not this rule.

## 10. A leg that has run is over (owner)

Once the leg's move has happened, it is finished (owner). [Claude]: once any setup-timeframe bar after `L0`'s
pivot bar has a high **strictly above `H100`** (a wick counts; touching does not), the leg is finished:
no order is written on it (and a resting one is withdrawn - rule 12).

## 11. The range (owner: sideways - "enter at the edge, around 88 % - 127 %", the target "around 100 %")

- **When** [Claude]: no H1 lean (rule 1) **and** no trend on the setup timeframe at `now`: of its latest two fixed
  highs and latest two fixed lows, neither "higher high and higher low" nor "lower high and lower low". Fewer
  than two of either - no range.
- **The range** [Claude]: the latest fixed HIGH and the latest fixed LOW on the setup timeframe, in whichever
  order they came; height = high - low; 0 % at the low, 100 % at the high. A new fixed pivot makes a new range.
- **Orders** [Claude, within the owner's "around 88 - 127 %" and "around 100 %"]: a SELL limit at **88 %** while the
  price is below it, stop above **127 %** + `stop_buffer`, TP the **low edge** + `target_buffer`; a BUY limit at
  **12 %** while the price is above it, stop below **-27 %** - `stop_buffer`, TP the **high edge** -
  `target_buffer`; if both, the one nearer the price. At least 2R; rule 9 with the height. No minimum height
  [Claude].
- **Broken** [Claude]: a **closed setup-timeframe bar beyond 127 % / -27 %** (no buffer) after the later of the two pivots - no
  order (and a resting one is withdrawn - rule 12). One order per range (its two pivot times).
- Rules 3, 4, 5, 6's bounce and 8 do not apply to the range.

## 12. Orders, withdrawal, holding (owner: held to the stop or the target, no time limit)

- **At a time** `max_orders` [Claude], default 1, across everything (legs, ranges, M5 and M15).
- **Fill** [Claude]: within **24 M5 bars** of the decision; an order fills when price trades through its price
  from the side it was on.
- **Withdrawn before the fill** [Claude] - only by a bar **before** the fill bar: the stop or the target touched;
  a leg's `H100` crossed by a wick (the decision text carries `withdraw beyond <H100>`); a range's 127 % / -27 %
  line crossed by a setup-timeframe **close** (the text carries `range break <tf> close beyond <price> /
  <price>`). A bar that both fills and crosses keeps the fill.
- **Held (owner)** until the stop or the target, from the fill bar on; a bar touching both counts as the stop
  [Claude] - including the fill bar.
- **Money:** `eye/money.py` - 200 USD (the owner's) at 0.01 lot [Claude]; it stops at a balance of 0 ("account
  gone"); R counts every trade. Fill, withdrawal and exit are judged on M5 bars for every leg and range.

## 13. Which one, when several qualify [Claude]

A leg (rules 2-10) before a range (rule 11); among legs, the one with the later `L0`; then the entry nearer the
price. Only one order is written per bar.

## 14. How results are judged (owner)

No number is believed until each trade behind it is drawn (`eye/draw_trades.py`) and checked against these
rules. **The run** [Claude's plan]: the defaults above (the range on), beside these variants, one at a time - `fib_stop` swing;
`fib_count` on; `fib_entry` 0.382 and 0.236; `fib_early` 0.10 with `line_tight` (at 0.382); `fib_tf` M15;
`max_trend_legs` 3; `major_tf` H1; `max_entry_frac` 0.15 and 0.35. First October 2026; then unchanged, month by month, on November 2025 -
September 2026. **Those months are not clean:** the research that chose `H100` and the entry depth used
them (all hours, no windows, no H1 lean) - the bot's own decisions have not been run on them. **The clean
test is forward:** the months after 2026-10-28, run unchanged as their bars arrive.
