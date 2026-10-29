# The bot's rules - the current specification

**This file is the specification in force.** It holds only the rules the bot uses now, in the order the bot
applies them. Where each rule came from, and every rule that was tried and dropped, is in `eye/BOT_SPEC.md`
(the history) and `eye/BOT_RESEARCH.md` (the measurements). A developer builds from this file alone.

Every rule says whose it is: **(owner)** - the owner's rule, in METHOD 2e; **[Claude]** - a definition Claude
gave where the owner gave none: a parameter with a default, written into every decision, for the owner to
change. A number inside an owner's example is never a rule.

Status of the code: `eye/bot2e.py` at commit fff8c1a implements rules 1-4, 6-7 (line / swing), 9 (as a fixed
4 USD - to be changed) and 10; **rules 2-3 (lean / M5 trend), 5 (the count of the trend), 8 (the target
ladder), 9 (the share of the leg) and 11 (the range) are to be built.** The `mode = 2e` path in the code is a
record (the original setup, BOT_SPEC revisions 1-3) and is not part of these rules.

## 0. Data, time, windows

- **Data:** FBS-Demo XAUUSD bars - H4, H1, M15, M5 (`data/history/FBS-Demo/XAUUSD`); Thai time =
  Asia/Bangkok.
- **Closed bars only (owner):** at the moment `now` a bar of timeframe `tf` exists only if
  `open_time + tf <= now`; every reading uses frames cut so. Pivots are MT5's ZigZag 12 / 5 / 3 (owner) -
  `app.indicators.chart_read.zigzag_pivots`, **fixed pivots only**. MACD 12 / 26 / 9 as MT5 (`walk.macd_mt5`,
  main line), RSI 14 (owner).
- **Windows (owner):** decisions only at an M5 close inside Asia 07:00-09:00, London 13:00-15:00, New York
  19:30-23:00 Thai (start and end included). Orders already written live on outside the windows.
- **Setup timeframe** `fib_tf` [Claude]: M5 (default) or M15. "The price" in these rules is **the last closed
  M5 close** at `now`, for either setup timeframe.
- **Spread** 0.30 USD in every R and every score [Claude]. Buffers: `stop_buffer` and `target_buffer` 0.50 USD
  [Claude].
- **Orders at a time** `max_orders` [Claude], default 1: no new order while that many are pending or open.

## 1. The H1 lean (owner: "H1 is the lean; the trend is measured on M5")

From closed **H1** bars and fixed H1 pivots at `now` [Claude, after the owner's "price below the latest high
and making lower lows"]:
- **SELL lean:** `Hf` = the latest fixed H1 HIGH, `Lp` = the latest fixed H1 LOW before it (by pivot time).
  The last H1 close is strictly below `Hf` **and** some H1 bar after `Hf`'s pivot bar has a low strictly below
  `Lp`.
- **BUY lean:** the mirror (`Lf` the latest fixed LOW, `Hp` the latest fixed HIGH before it; last close above
  `Lf`, some bar after `Lf` above `Hp`).
- If both hold, the one whose pivot (`Hf` / `Lf`) is later by pivot time; neither = **no lean**.
- **(owner)** never trade against a clear lean; with no lean the M5 trend decides alone (rule 3) -
  *"if you wait for H1 to be clear, the market has run already."*

## 2. The leg - the owner's Fibonacci (owner)

*"To play an up move, draw high -> low; to play a down move, draw low -> high."* The Fibo is drawn on the
counter-move that has just ended [Claude's wording]. For a **BUY** (a SELL is the mirror of every line, prices
negated):
- **`L0`** [Claude] = the latest fixed LOW on the setup timeframe that is lower than every fixed low after
  it, with at least one fixed low after it, and no bar closed below it since.
- **`H100`** = the high the fall began from [Claude, chosen by research - BOT_RESEARCH "Which high is 100 %"]:
  walking back from `L0` over the fixed lows while each earlier low is strictly higher than the one after
  it, the highest fixed high met.
- **Levels:** `L0 + x * (H100 - L0)` - 0 % at the low, 100 % at the high (owner).
- **One order per leg** [Claude]: the key is side, setup timeframe, `L0` time, `H100` time; a leg is used once
  an order is written on it, whatever happens to that order.

## 3. The trade's trend on M5 (owner: "the trend is measured on M5")

[Claude] The leg's own structure gives the trend it interrupted: a **BUY** needs `H100` strictly above the
immediately preceding fixed high on the setup timeframe (by pivot time, fixed by `now`) - the fall is a
pullback in a rise; a **SELL** needs the 100 % low strictly below the preceding fixed low. No preceding pivot
= no order. Then rule 1: a BUY is refused under a SELL lean, a SELL under a BUY lean.

## 4. The count of the counter-move (owner: "try both, counting and not counting")

`fib_count` [Claude] off (default) / on. **On (owner):** "3-5 peaks" counted as **legs, both sides** - for a
BUY, the descending run into `L0` has 3-5 fixed lows, each strictly lower than the one before, with
divergence at `L0` against the low before it on **one** oscillator or both (MACD main higher, or RSI higher,
while price is lower or equal). SELL: 3-5 higher highs into the top.

## 5. No chasing - the trend's own count (owner: "don't let it happen"; the count of legs)

[Claude] For a BUY, walk back from `H100` over the fixed highs on the setup timeframe while each is strictly
higher than the one before; the number of highs in that run (`H100` included) is the trend's legs. At
`max_trend_legs` (default **5**; run also at 3) or more, no order - the trend is ending (owner: 3-5 peaks,
then the turn). SELL mirrored on lows.

## 6. The entry

- **Entry level** `fib_entry` (owner): **0.618** (*"if the bulls are really strong"*), 0.382, 0.236 (*"wait for
  it to fall back to around 38 - 23 %"*) - default 0.618 [Claude, the strongest in the research].
- **The bounce (owner: the entry is the pullback after the bounce):** an order is written only once a bar
  after `L0` has traded above the entry level, and only while the last close is above it - a **plain limit**
  at the entry level.
- **R8 - played out** [Claude]: from the bar that first traded above the entry level, a target touch on that
  bar or after, or a stop touch after it, ends the setup.

## 7. The stop (owner: "beyond the lowest bottom"; for the 61.8 % entry "beyond 23 %")

- Entry 0.382 / 0.236: below `L0` - `stop_buffer` [Claude's reading of "beyond 88 % - 0 %"].
- Entry 0.618: below the 23.6 % level - `stop_buffer` (owner).
- `fib_stop` [Claude]: **line** (the two above) or **swing** - also beyond the lowest fixed low on the setup
  timeframe formed after `L0` and fixed by `now`: the stop is one `stop_buffer` below the lower of that low and
  the line stop. *(Run both ways; the owner judges on the real run. Swing kept the stop rule in every drawn
  October trade.)*

## 8. The target - the ladder (owner: "the target from the Fibo, the take-profit actually placed - what can be reached")

For a BUY: **TP = the 161.8 % extension** (`L0 + 1.618 x leg - target_buffer`) **if no major resistance band
lies between the entry and it; else the 127.2 % extension if none lies before that; else just before the first
major band** (its near edge - `target_buffer`). **At least 1:2 (owner):** R = (TP - entry - spread) /
(entry - stop); under 2, no order (*"no trade, for now"*).
**Major band** [Claude]: a single band per fixed **H4** pivot (`major_tf`, default H4; variant H1) - centre
the pivot price, half-width `band_frac` (0.10) x the median of the last `band_legs` (20) legs of that
timeframe, only pivots at least `level_min_age_h` (24 h) old, among the last `level_bars` (500) bars; edges
inclusive; "between" = any part of the band strictly between the entry and the target. SELL mirrored
(support bands below).

## 9. The entry must be reachable (owner, rule 7: "a price the market can reach from here")

[Claude] |the price - the entry| at most **`max_entry_frac` x the leg** (`H100 - L0`; for a range its height) -
default **0.25**, run also at 0.15 and 0.35. *(The owner's "4 USD" was an example, not this rule.)*

## 10. A leg that has run is over (owner)

Once any bar on the setup timeframe after `L0`'s pivot bar has a high **strictly above `H100`** (SELL: low
strictly below), the leg is finished: no order is written on it. **The scorer** withdraws a resting order when
a bar *before* its fill bar crosses `H100` (the decision text carries `withdraw beyond <H100>`); a bar that
both fills and crosses keeps the fill.

## 11. The range (owner: sideways - "enter at the edge, around 88 % - 127 %", the target "around 100 %")

- **When** [Claude]: no H1 lean (rule 1) **and** no trend on the setup timeframe at `now` - of its latest two
  fixed highs and latest two fixed lows, neither "both higher" nor "both lower".
- **The range:** the latest fixed HIGH and the latest fixed LOW on the setup timeframe; height = high - low;
  0 % at the low, 100 % at the high.
- **Orders:** a SELL limit at 88 % while the price is below it, stop above 127 % + `stop_buffer`, TP the low edge
  + `target_buffer` [Claude's reading of "around 100 %"]; a BUY limit at 12 % while the price is above it, stop
  below -27 % - `stop_buffer`, TP the high edge - `target_buffer`; if both, the one nearer the price. At least
  2R; rule 9 with the range height.
- **Broken:** a closed setup-timeframe bar beyond 127 % / -27 % after the later pivot - no order; a resting one
  is withdrawn (the scorer marker as rule 10). One order per range (its two pivot times).
- Rules 3, 4, 5 and 8 do not apply to the range.

## 12. Holding and scoring (owner)

Held until the stop or the target - no time limit. `eye/score.py`: an order fills when price trades through
the entry from the side it was on (24 bars to fill); a stop or target on a bar before the fill bar, or a
withdrawal marker crossed, withdraws it; a bar touching stop and target counts as the stop. Money:
`eye/money.py` - 200 USD, 0.01 lot; the reading stops at a balance of 0 ("account gone"), R counts every trade.

## 13. How results are judged (owner)

No number is believed until each trade behind it is drawn (`eye/draw_trades.py`) and checked against these
rules. **The real run:** the defaults above, with `fib_stop` line and swing as the paired variants (rule 7);
the other variants named in rules 5, 8 and 9 one at a time beside them. First on October 2026, then
**unchanged on months never looked at** (November 2025 - August 2026), reported month by month.
