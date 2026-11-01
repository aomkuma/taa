# Trading by eye: the method

The owner, 2026-10-28, after everything else was archived: *"start from looking at price structure and
finding an entry with an edge. That is all. Any timeframe; the principle is enter on a timeframe, exit on
that timeframe. Try trading with your bare eyes."* Then: *"you need to trade a hundred times before the
picture appears."*

So this folder is a hundred hand-read trades on real candles, and nothing else. No indicator, no rule set,
no filter, no knowledge base (since 2e, 2026-10-28: the owner's own setup, with MACD, RSI and ZigZag as its
only tools). **These rules are written before the first chart is drawn**, so that what
follows can judge them.

## 1 What is read

Gold, drawn as candles and looked at as a picture - never read as a table of numbers. **Since 2026-10-28 (2e)
`walk.py` draws H1 above M15 (`_a`) and M5 (`_b`), with MT5's ZigZag 12/5/3 on each frame and MACD
12/26/9 and RSI 14 under M15 and M5.** What follows was the reason for M5 alone. M5 because
of what the first hand-read showed on 2026-08-14: the newest structure on M5 sat 6-8 USD from price while
on M15 it sat 17-20 USD away, so the M15 plan bought a shelf the market had already left. M5 keeps the
entry current and halves the stop, and its stops stay many times the spread, which M1 would not.

Section 2c replaced the sheets: the chart is now advanced bar by bar through a real day, not printed six
panels to a page. `sheets.py` and `moments.csv` are kept as the record of
where the control trades came from, and are no longer run.

## 2 How the moments were chosen - the sampling design, superseded 2026-10-28 by 2c

**By the clock, never by what they look like.** Picking moments that look interesting is how a library of
"patterns" becomes a record of hindsight (the lesson that voided an earlier body of work).

- Start 2026-02-02, then **every second trading day**.
- The hour rotates through the owner's windows: **08:00, 14:00, 20:30 Thai**, one per sampled day, in turn.
- A moment is skipped only when the data has no bars for it (a weekend or a gap), and the next day is taken
  in its place, keeping the rotation.
- July 6-9 and October 19-27 of 2026 are **excluded**: those days were examined in earlier work and are no
  longer unseen.

## 2b A sampled moment is where I sit down, not where I trade

The owner, 2026-10-28, after looking at the first sheets: **90 % of them were not spots worth watching.**
The structure was not clear and the wave legs were not complete; and price was not near the support or
resistance of the side being watched - or if it was near, it looked likely to go straight through, because
the structure at that level gave no picture.

The sampling is not the fault. The fault was treating the sampled bar as a decision. So:

- A sampled moment is **where I sit down at the screen**.
- From there the chart advances a few bars at a time (`walk.py`), and I look again. I see only what had
  printed by then; no bar from the future is ever on the screen.
- **If the picture is not worth trading, I wait and look again.** If it never becomes worth trading inside
  the session, that is recorded as a session with no setup - which is the normal outcome.
- Every wait is part of the record: how many bars I sat before a setup appeared, or that none did.

**See the whole structure before anything else** (the owner, 2026-10-28, after watching the first walk:
*"the left of the chart shows nothing at all - there are no levels there"*, *"I mean the LEFT of the chart,
it has to go back far"*, and *"the main thing is you probably need to see the complete price structure
first - then it is easier to trade"*).

The first chart was 110 M5 bars - nine hours. Nothing on it was older than a morning, so every "level" I
named was a shelf built minutes earlier, and I twice sold into the strongest move on the screen because
the thing that made it strong was off the left edge. At moment #13 the nine-hour window could not show
that price had just broken a week-long ceiling at 5200-5240; it read as "under resistance" when it was
"above a broken range", and the trade that was there paid +7.1 R in the direction I sold.

So the eye now gets, in this order:

1. **H1, about four weeks** (500 bars) - where the levels are. Read this first, always.
2. **M5, about 33 hours** - the width of the owner's own screen, for the entry.

If the upper chart shows nothing at price - no level the left side built - there is no moment, whatever the
lower chart is doing.

**What makes a picture worth trading** (the owner's words, 2026-10-28):

1. **The legs are complete.** Three or four legs are on the chart and the last one has **finished** - then
   the trade is the fifth leg. Not a pullback inside a leg that is still running.
2. **Price is at the support or resistance of the side being watched** - a level the structure built, where
   price has turned before or where a large leg left from. Not a shelf that formed in passing minutes ago.
3. **The structure AT the level says it will hold** (the owner, 2026-10-28, asked how you tell a level that
   holds from one that breaks: *"the price structure at the level - the chart pattern together with HH/HL
   and LH/LL"*). Read the last two swing highs and the last two swing lows as price works the level:
   - buying a support needs **HH and HL together**; a higher low under a **lower** high is still a
     downtrend and the level is more likely to break;
   - selling a resistance needs **LH and LL together**;
   - and a named chart pattern on top of it - a double bottom or top, a base and its break, a sweep that
     closed back, a head and shoulders.

   Measured on the first eight filled trades: four taken with this structure made +0.14 R a trade, four
   taken against it **all lost a full stop**, -1.02 R a trade (`LESSONS.md`).

If the three are not there, there is nothing to decide and no entry is written.

## 2c Real trading days, one at a time (owner, 2026-10-28)

*"This way may not work. How about we run real days, one at a time?"* - said after the sampled moments
produced nine decisions and one winner. So the sampling in section 2 is retired and this is the method
being run:

- A date is taken whole, in order, and **every one of the owner's windows is walked, in sequence** - no
  window is skipped because the previous one gave nothing:

  | window | Thai time | what it is |
  |---|---|---|
  | Asia | 07:00 - 09:00 | the Asian session, the quietest of the three |
  | London | 13:00 - 15:00 | the London open, give or take a little |
  | New York | 19:30 - 23:00 | the New York open and the hours after it |

  (The owner's windows, unchanged from the archived work; outside them is the lowest priority and only a
  really clean picture is worth taking, which is the owner's judgement to make.)
- Inside a window the chart advances a few bars at a time from the opening price, exactly as in 2b. The
  upper frame is drawn first, every time.
- **The window is written down whether or not it produced a trade** - `sessions.csv`, one row per window:
  how many steps were walked, the price at the start and the end, how many setups appeared, how many trades
  were taken, what was being watched, and **`reach`** - what the method was able to do with the window:

  | `reach` | meaning |
  |---|---|
  | `no-setup` | nothing worth trading appeared; refusing cost nothing |
  | `shut` | a real move happened **and the rules could not take it** - the expensive case |
  | `open-missed` | the rules authorised a trade and it was not taken, or was taken wrong |
  | `open-taken` | a decision was written, and it is in the ledger |

  `shut` and `open-missed` are the two that have to be counted, because neither leaves a row in the
  ledger and both are how a method quietly fails (`LESSONS.md` section 6). A window with nothing in
  it is the normal outcome and has to cost
  something to leave out, or "fifty trades" could be fifty picked out of an unknown number of walks
  (the reviewer's finding, 2026-10-28).
- The day is reported to the owner as it happens, trade by trade.

`walk.py` takes either a sampled moment's id or a real datetime: `walk.py "2026-04-01 07:00" 12`.

## 2e The owner's principle: price structure + divergence + counting the peaks (owner, 2026-10-28)

**This is the principle the work holds to.** The owner, 2026-10-28, on reading Claude's plain summary of
2d below: *"this is not really my way. What I trade is price structure + divergence and counting the
peaks of the chart"* - and then: hold to this principle instead.

Before that day none of the thirteen rules mentioned divergence, and counting was only rule 4's undefined
"three or four legs, trade the fifth". The owner then answered, one question at a time:

### The owner's setup, as answered on 2026-10-28

| | the owner's answer |
|---|---|
| **The side with the edge** | *(Superseded 2026-10-31 - the side is held on M15 with M and W, row "The side (2026-10-31)". Before:)* *(The bot, since 2026-10-30 evening: H1 and M30 removed; the side is rule 16 - **H4's clear trend (a trend leg, traded with it), else a fade of the latest run** (the owner, 2026-10-30 evening: *"if price has run up, look for a sell; if it has come down a lot, look for a buy - unless the big trend is very clear"*, *"only up to H4"*); see the row "The side".)* **H1 gives the lean (the tendency); the trend that is traded is measured on M5.** *(The higher timeframe is **M30** since 2026-10-30 - the owner: "change it all to M30"; see "The owner's Fibonacci", Sideways and The side.)* Never trade against a clear lean on the higher timeframe (M30); when that lean is not clear, M5's trend decides - *"if you wait for H1 to be clear, the market has run already"* (the owner, 2026-10-29). The larger timeframe's lean is never ignored |
| **Where** | **at resistance when the sell side has the edge, at support when the buy side has the edge** - never the other way round |
| **The count** | **3 to 5 peaks, counted from MT5's ZigZag** - **or two, when they make the owner's W (sell, at resistance) or M (buy, at support)** - the owner, 2026-10-28 |
| **Divergence** | **on MACD or RSI, against price - one is enough** (the owner, 2026-10-28); both is the clear case - see the principle below |
| **The entry** | **wait for the structure to break, then the retest of the support or resistance it broke** |
| **Settings** | **MT5's own defaults** - ZigZag 12 / 5 / 3, MACD 12 / 26 / 9, RSI 14 |
| **Entry timeframe** | **M5 to M15** |
| **The stop** | **beyond the High** (sell) / **Low** (buy) - see the principle below |
| **Levels and the turn** | **price usually turns before it reaches a level; when it does reach the level, it usually carries on the same way** (the owner, 2026-10-29 - the same as the morning's "get in before the line": a pullback that reaches the line tends to go through it). So a setup does not need its top / bottom to sit on a level |
| **The target** (the Fibo extensions) | **the Fibo extension is the target; the take-profit actually placed is the one price can reach** - 161.8 % if nothing major stands before it, else 127 %, else just before that level; at least 1:2 (the owner, 2026-10-29) |
| **No chasing, and trades in a range too** | the owner, 2026-10-29, on the bot's spec: *"don't let these two happen"* - entering late after the move has run (chasing), and no trade at all when the market goes sideways |
| **The target** | **just before the opposite level on the left** - see the principle below |
| **How long a trade is held** | **until the stop or the target** - the owner: *"hold it"*. No time limit |
| **Reward** | **at least 1:2** - the owner, 2026-10-28: *"the profit has to be 1:2, 1:3"*; when the target just before the next level gives less: *"no trade, for now"* |

Read together, in order *(as dictated on 10-28; the bot's side since 2026-10-30 evening - the row "The side" below)*: the higher timeframe (M30; H1 as first dictated) says which side has the edge; price comes into a level on that side; ZigZag
counts 3 to 5 peaks into it with divergence on MACD or RSI against price (one is enough - the owner; *corrected
2026-10-30, it read "MACD and RSI"*); the structure breaks; the entry is the retest of the line it broke, on M5
to M15. (This sentence only strings the table's answers together.)

*Corrected 10-29: the written-out steps had the textbook's sides (a sell from an M, a buy from a W); they
now read the owner's way - a W is the sell, an M the buy.*

### The owner's words for patterns - read them the owner's way

The owner, 2026-10-28: *"I have always understood M as buy and W as sell, in the leg where it has already
projected."* **This is the opposite of the textbook** (where an M, a double top, is a sell and a W, a
double bottom, a buy), and Claude translated "M" the textbook way and got the side wrong on day 3. In the
owner's usage: the M is drawn by the counter-move **coming down into
a support** - its lows on the level - so it is the end of that move and a **buy**; the W is drawn going
**up into a resistance**, and is a **sell**. Day 3 London fits: an asymmetric M (tops 4678.79, 4667.74)
with its lows 4643.61 / 4644.97 on the 4642-4651 support, and the run to 4706.58 after it.

**Measured on the stored gold bars, 2026-10-28** (the owner: *"the textbook is one thing - how is it really
used?"*). Every M and W that MT5's ZigZag 12/5/3 drew on M15 from 2023-08 to 2026-10 - two tops (bottoms)
within 35 % of the pattern's height of each other, asymmetry allowed - followed from the bar the second top
is known, for two days: which came first, the neckline broken by a quarter of the height, or the far
extreme taken.

| | n | up first | down first |
|---|---:|---:|---:|
| M after a leg up (the textbook's) | 499 | 52.5 % | 47.3 % |
| M in a leg down (the owner's buy) | 404 | 53.7 % | 44.3 % |
| W after a leg down (the textbook's) | 393 | 53.4 % | 45.8 % |
| W in a leg up (the owner's sell) | 434 | 56.9 % | 42.4 % |

**Every kind went up first more often** - gold rose from about 1,900 to over 4,000 in these years, and that
drift is in all four rows. **The shape alone, and the leg it forms in, separate little.** Not tested here,
because they cannot be counted without judgement: the level from the left the pattern sits on, the H1 side,
and divergence - the rest of the owner's setup, which is where the difference has to come from if it is
anywhere. Claude's definitions (35 %, a quarter of the height, two days); one timeframe; no costs.

### The principle, generalised from the owner's example

The owner, 2026-10-28: *"this is an example - you have to summarise it into a principle, not turn the
example into a fixed rule."* So no number from the example is a rule; the example below only shows what
the words mean. Written for a sell; a buy is the mirror of every line. **Steps 1, 2, 6 and 7 are the
owner's answers; steps 3 and 4 are Claude's generalisation of the owner's example** (the bounce, the
lower high, the low that breaks), and **step 5 is the owner's answer** of the same evening (*"break the
low, then retest"*). The example's own words - *"bounced lightly and then made an LL - sell"* - are read
through that later answer: the LL is the break, the sell is its retest.

1. **Context** - the H1 trend *(the bot since 2026-10-30 evening: rule 16 - H4's clear trend, else a fade of the run)* gives the sell side the edge, and price has come up into a **resistance**
   the left of the chart built.
2. **Exhaustion** - ZigZag counts **3 to 5 peaks** into that level - **or two that make a W** - the owner's sell (it need not be symmetric) - with **divergence** on MACD or RSI
   against price. **A clear W at resistance (M at support, for the buy) is taken without divergence** - the owner,
   2026-10-28, on day 3 London's M, whose second low had MACD and RSI lower: *"it can be entered."* Divergence is required
   for the 3-5 count - **on one oscillator is enough** (the owner, 2026-10-28); both is the clear case. For an M or W it adds strength, it is not a condition. **Both diverging is a clear signal** (the owner: *"if both happen, it is clear"*); nothing is
   recorded about one alone - the record says which it was. The peaks are counted on the entry timeframe, M5 or M15 *(Claude's reading - the owner
   gave the entry timeframe, not the counting one; the example has 3 peaks on M15 and 4 on M5)*.
3. **The structure breaks** - price takes out the **last swing low**, and the bounce after it fails under
   the top - a lower high: the up leg is over.
4. **The low breaks** - price goes through **the low that bounce started from**.
5. **The entry - on the retest** - sell when price comes **back up to that broken low from below** and
   turns down there. The owner, 2026-10-28: *"break the low, then retest"* - not on the break itself.
   **The order is a Sell Stop Limit** (it is the order that does exactly this): its stop price a little under the low, so it wakes only once the low has
   broken, and its limit price at the low, filled on the retest. It can be placed before the break.
6. **The stop** - beyond **the highest high of the move** (sell) / **the lowest low** (buy): the top or
   bottom where the peaks and the divergence formed, not the bounce's lower high. The owner, 2026-10-28:
   *"the SL goes beyond the highest top or the lowest bottom."* (Claude had first read it as the bounce's
   high; the owner corrected it.)
7. **The target** - **just before** the opposite level from the left: for a sell, a little above the next
   support, never on the line - the owner's standing rule that a level is a band and the target goes
   before the line (`LESSONS.md` 5).

**The entry, settled by the owner on 2026-10-28:** *"break the low, then retest."* The table said the
same - *"wait for the structure to break, then the retest of the support or resistance it broke"* - and
two reviewers had read Claude's first step 5 (sell on the break) as a different entry; it was. On the
example's bars: 08:30 Thai broke the 4055.57 low (to 4053.11); 08:35-08:40 came back up to 4055.39 and
4057.54 - the retest of the broken low from below - and turned down. **The sell is on that retest.**

**The buy, written out** - *Claude's mirror of the sell steps; the owner asked "and the buy side?" and
had said a buy is the mirror, nothing more:*

1. the **H1 trend** *(the bot: rule 16 - H4's clear trend, else a fade of the run)* gives the buy side the edge, and price has come down into a **support** the left of
   the chart built;
2. ZigZag counts **3 to 5 lows** into it - or two that make an **M** (the owner's buy) - with **divergence**: price makes a lower or equal low while MACD
   or RSI makes a higher low - one is enough, both is clear; a clear M needs none;
3. the structure breaks - price takes out the **last swing high**, and the dip after it holds above the
   bottom - a higher low;
4. **the high breaks** - price goes through the high that dip started from;
5. **buy on the retest** - when price comes back down to that broken high from above and turns up there:
   a **Buy Stop Limit**, stop price a little over the high, limit price at the high;
6. the stop beyond **the lowest low** of the move;
7. the target just before the next **resistance** from the left; held until the stop or the target.

**Divergence, as the book has it** (the owner: *"divergence is divergence - what is it by the book?"*). The
definition below is *Claude's rendering of the textbook*, including "or equal". Compared between ZigZag
peaks of the counter-move, price against MACD and against RSI:

- for a sell at resistance: price makes a **higher or equal high**, the oscillator a **lower high** - the
  push reaches further with less force behind it;
- for a buy at support: price makes a **lower or equal low**, the oscillator a **higher low**.

*The owner:* both diverging is clear; **one alone is enough for the count** (*"one"*, 2026-10-28). *Claude's reading:* hidden
divergence - the continuation kind - is a different signal and is left out unless the
owner adds it.

**A trade is held until its stop or its target** - no time limit (asked "until the stop or the target with
no time limit, or a time to cut?", the owner, 2026-10-28: *"hold it"*). `score.py` scores every trade that
way; the twelve earlier trades' planned columns were never time-closed, and their on-sight column was
re-scored under it.

**The owner's own example, 2026-10-28** (on the FBS-Demo M15 chart, server time): *"suppose that around
03:15 it bounced lightly and then made an LL - sell; SL above the High; TP above the resistance on the left
of the chart at 4030."* On the stored bars: top 4070.76 at 02:10; the structure broke at 03:00-03:05 (low
4055.57 under the 4059.30 and 4057.66 lows); the light bounce reached 4062.76 at 03:20-03:25 (a lower
high); 03:30 broke 4055.57 for the LL (the owner: *"when it loses 4055"*), and 03:35-03:40 came back up
to 4055.39 and 4057.54 - **the retest; the sell is there, at about 4055** (the owner: *"break the low,
then retest"*). TP 4031 was reached at 07:55 and the highest price on the way was 4059.31. With the stop
above the top, as the owner's principle puts it (4071): risk 16.0, **+1.48 R** after the 0.30 spread.
(Above the bounce's high, 4063, it would have been risk 8.0 and +2.96 R - Claude's first reading, not the
owner's.) One example,
read after the fact - it shows what the words mean, not that they pay.

**The divergence in the example**, measured on the bars known at the entry (03:30), at the ZigZag highs of
the counter-move up from 3989 - on M15 the top was still MT5's moving last point at that moment, which
`walk.py` now draws dashed and labelled with a "?" (as it does the break to 4055.57):

| M15 high (server) | price | MACD main | RSI 14 |
|---|---:|---:|---:|
| 27 Oct 19:30 | 4065.68 | 12.20 | 78.25 |
| 28 Oct 00:45 | 4064.56 | 4.96 | 65.74 |
| 28 Oct 02:00 - the top | **4070.76** | **3.96** | **68.61** |

Three peaks, the last the highest in price, and both MACD (12.20 -> 3.96) and RSI (78.25 -> 68.61) lower:
a divergence on both. On M5 there were four highs at the top (4065.68, 4064.17, 4064.56, 4070.76) and the
same shape, weaker: MACD 2.84 -> 1.29, RSI 66.04 -> 64.94.

The target came **4 h 25 min after the entry** - held, as the owner holds, it is reached.

### The owner's Fibonacci (2026-10-29)

The owner's words, volunteered: *"Have you ever measured with Fibo? I like to use it. Sideways: enter at the
edge, around 88 % - 127 %. Up trend: draw the Fibo with the ZigZag alongside - 0 % at the previous lowest
price, 100 % at the previous highest price - then wait for it to fall back to around 38 - 23 %; if the bulls
are really strong, maybe enter from the pullback to 61 %. The SL is beyond 88 % - 0 %. Down trend: the reverse
of the up trend."*

**The owner's rules for it** (each in the owner's words where quoted; the bot's form of every rule is in
`eye/BOT_RULES.md`):

| | the rule |
|---|---|
| **The drawing** | **Corrected 2026-10-30** - the owner, on the bot's drawing of 07/10: *"I draw it the other way round, to see the target below, if I expect it to go on down - drawn like this you would be buying, right?"*; then *"as I said"*: **the Fibo is drawn on the leg running the way price is expected to go on, 0 % at its start, 100 % at its end; the entry on the pullback into 38 - 23 % (61 % if strong), the stop beyond 0 %, the target 127 - 161 % the same way.** The earlier record - *"To play an up move, draw high -> low; to play a down move, draw low -> high"*, read by Claude as the Fibo on the counter-move traded against it - was Claude's misreading (`eye/BOT_RULES.md` rule 2) |
| **The entry** | the pullback to around 38 - 23 %; from 61 % *"if the bulls are really strong"*; entering a little **before** the line, with the stop just beyond it, is the owner's idea - run as a variant (`eye/BOT_RULES.md` rule 6) |
| **The stop** | beyond 0 % (*"beyond 88 % - 0 %"*); for the 61 % entry *"beyond 23 %"* - confirmed 2026-10-29 as the rule for that entry (not 2e's "beyond the lowest bottom") |
| **The target** | the extension - 127 - 161 % in a trend; **the take-profit placed is the one price can reach** |
| **The count** | try it both ways - with and without; counted as **legs, both sides**: 3-5 lower lows into a bottom (buy), 3-5 higher highs into a top (sell); or two that make the M (buy) / W (sell) - for now any two-low (two-high) pullback is taken as one: *"try it this way first"* (2026-10-29) |
| **Sideways** | *(Superseded 2026-10-30 - see the status note at the top of `eye/BOT_RULES.md`.)* *The M30 range reading below (rule 11) failed the market check and is withdrawn; the owner's words stand as the record.* **read on the trend timeframe - M30 since 2026-10-30 (H1 before) - the trend for the entry is found on M5** - the owner, 2026-10-29: *"sideways means in the 1-hour timeframe, and the trend is found in the 5-minute"*. The range counts once price has gone back and forth inside it, *"at least one to two times each side"*; then the trade is in the fourth and fifth leg - *"if it can be found from the third leg, that is good"*. At the top edge with M5 turning down, the sell is taken on the M5 Fibo pullback, as on any leg (*"yes"*). The edges around 88 - 127 %, the target around 100 %: *"go by the 5-minute target, and look at the 1-hour price edges alongside, as support, resistance and the take-profit"*. The sixth leg: *"be ready for it to run through the edge, which can be where we make a big profit"*. (Claude had read sideways on M5 and faded its edges - a misreading, withdrawn.) **The trend timeframe is M30** (the owner, 2026-10-30: *"we change to M30 and drop 1H - change it all to M30"* - faster signals, closer to M5): everything above said of H1 - sideways, the lean, the trend - is read on M30. **How it is read** (Claude's proposal, the owner 2026-10-30: *"I have no problem with the way of thinking"*; on the drawn October: *"about this - fix the code to do what we think"*): the swings inside a range do not end it - only price reaching an edge counts as a leg; a range ends when M30 closes beyond its edge, and M30 then trends that way until price goes back and forth in a new range (`eye/BOT_RULES.md` rule 11). **Where a range starts** (Claude, from outside sources - Wyckoff, Al Brooks, `eye/BOT_RESEARCH.md` "What a range is - outside sources"; the owner 2026-10-30: *"yes"*): a range starts when a trend stops making new extremes - the trend's last extreme is one edge, the first bounce from it the other; it counts once price comes back to test the first edge without a new extreme beyond it; the swings inside are not counted; a break is an M30 close beyond the 127 % line. A pivot beyond the first edge with no close beyond 127 % is a test of the edge, not a new extreme (the owner, 2026-10-30, choosing it: *"once it breaks, you have to wait for the retest anyway"*). |
| **Two views: the trend and the trade** | *(Superseded 2026-10-30 - see the status note at the top of `eye/BOT_RULES.md`.)* *The trend and range looks belonged to rule 11 and are withdrawn; the leg look (M5, 2 trading days) stands as BOT_RULES "The setup look".* the owner, 2026-10-30: *"looking at the big picture to see the trend and digging into the chart to find the entry are different things"*. **The trend** - *"looking back many days, on any timeframe - M15 to 1H all work"*. **The trade** (the range to trade, its edges and legs, the entry) - a short look, so the price zone is one that can be traded today: the owner's example charts (MT5, 30/10/2026) were **M30 over about 4 days** and **M5 over about 2 days** - an example, the principle being a look sized to the day's trading, not a fixed number; looking back as far as a month *"makes you miss the day's trades"*. **The owner then set the looks** (2026-10-30, as the bot's settings): the trend - M30, 7 trading days (the side with the edge when there is no range); the range traded - M30, 4 trading days first (its edges, legs, side and target); the leg - M5, 2 trading days (the Fibo leg and the M5 trend at the entry) (`eye/BOT_RULES.md`, "The looks"). When the 7 days show no trend there is a range, and it is traded as a range (the owner, 2026-10-30). How the looks are read (the owner's choice, 2026-10-30, of Claude's proposal): the bot reads M30 continuously from far back and the looks only decide what counts - the range traded is one that started in the last 4 days, the trend a break in the last 7 - so a look's start never makes a range of its own; the owner: *"careful not to get the same result as before - write the code tightly"*. |
| **The side** | *(Superseded 2026-10-31 - row "The side (2026-10-31)".)* **Since 2026-10-30 evening: the side is rule 16 - **H4's clear trend (a trend leg, traded with it), else a fade of the latest run** (the owner, 2026-10-30 evening: *"if price has run up, look for a sell; if it has come down a lot, look for a buy - unless the big trend is very clear"*, *"only up to H4"*) (BOT_RULES rules 2 and 16, the form Claude's). Earlier the same day: the M15 structure side (a close beyond the latest fixed M15 swing) - built, then withdrawn.** the leg's 0 % is the latest fixed low and an early leg is drawn once the pullback reaches about 38 % (BOT_RULES rule 2).** *(Superseded 2026-10-30 - see the status note at the top of `eye/BOT_RULES.md`.)* Before: the trend timeframe (M30 since 2026-10-30; H1 before) gives the side, M5 measures the trend; never against a clear trend on it (the 2e side row) - in the bot (`eye/BOT_RULES.md` rule 11, `h1_read` state, the default) the trend is the way M30 last broke out of a range, and rule 1's lean is kept for comparison; when M30 is sideways, the side is the range's current leg in its third to fifth legs (the row above); from the sixth leg the range gives no side and no edge target - Claude's reading of the owner's "be ready for it to run through the edge", confirmed by the owner (`eye/BOT_RULES.md` rule 11) |
| **When the bot trades** | **All day** - the owner, 2026-10-31: *"no need [for the three windows] - run it all the time"*. The form [Claude]: the bot decides at every 5-minute time of the day, 00:00 - 23:55 Thai (00:00 = the close of the previous day's last bar); the three windows (2c) are no longer its limit (`eye/BOT_RULES.md` rule 0, `windows` off). |
| **The side (2026-10-31)** | **Buy the pullback while there is no LL; to sell, wait for a clear picture - the ZigZag makes an LL first, and an LL on M15 is enough** (the owner, on 2026-08-12: *"there is no LL yet"*, *"two things - buy the pullback, and wait for a clear picture to sell; to sell, the ZigZag should make an LL first"*, *"an LL on M15 is enough to sell"*); **the owner's M and W count** (*"I see W and M clearly - try applying it"*; an M a buy, a W a sell). Judged by the trades, not by drawn strips (the owner chose "C"). The form [Claude]: `eye/BOT_RULES.md` rule 16, `side_rule` m15. |
| **Measuring the target (2026-11-01)** | The owner's words, 2026-10-31 / 11-01: *"the wins must be more than 50 %"* and 1:2 *"not relaxed - enter at the top and the bottom; you must measure the target"*; *"if you can measure the target and find the tops and bottoms, taking only 30 - 50 % of the move is enough"*; *"use the Fibo to measure the target"* - the 30/10/2026 M15 charts: a leg down drawn 0 % at the top, 100 % at the bottom, the bounce to the **23.6 % line**, then the extensions 161.8 - 423.6 %; *"the previous leg is the ruler - each one has its own target"*; *"the turning point of the current price is the target measured from the previous leg"*; counting: *"after 5 points - up 1, down 2, up 3, down 4, up 5 - look for a sell"*, *"after 3, down 4 - if an entry is found, buy then and sell the top above first"*; *"the counts are all right - it is how you interpret the chart in front of you"*; *"go in 0.01 lot at every important Fibo % line"* - to learn which line to enter; *"TP at the Fibo level it can reasonably reach"*; *"I think gold likes M30"*. Not yet a bot rule: the forms Claude measured did not hold (`eye/BOT_RESEARCH.md`, 2026-10-31 - 11-01); the owner's own choice of leg is still to be put in words. |
| **The run zones (2026-11-01)** | The owner's words, 2026-11-01: gold's run is set at **70 - 80 USD**; the zones are **equal steps** - *"I find a price zone in the past and draw a box, then move the box along step by step and draw the lines; price in this period runs about this much, with a **zone shift** when price turns or the trend changes"*; the step *"depends on the market - lately, with gold running strongly, it is at this number"*; the lines are **price targets and turning lines** - *"they are for use as points to watch, to keep an eye on price"* (marks to watch price at, not entries on their own). **The stop**: *"SL about past one third of the box"* - [Claude's reading, for the owner to correct] beyond the line by about a third of a step (about 25 USD at a 76 step); **The target**: *"TP is the opposite edge"* - the box's other edge, one step away; with the stop a third of a step beyond the line, about 1:3. The first box: *"look at the price cluster"* - the box is drawn over a cluster of prices. At a zone shift the box is drawn again from the turning point - the turning point becomes the new box's edge and the lines are redrawn from it (asked so, the owner: *"yes"*). When the cluster's height is not a whole number of steps: *"let the leftover go - it is never that exact; it is the fake-break distance"* - the step stays the run (70 - 80 lately), and price passing a line by a little is a fake break, not a new zone. When the zone shifts: *"a zone shift is not known at once - you have to wait for price to run the full distance the opposite way"* - a turning point becomes the new box's edge only after price has run one full step back from it, measured from the turning point (the owner's illustration, 2026-11-01: a run up from a low by about one step *"could be read as a zone shift"* - an illustration, not its numbers). *"It is an assumed example - the price structure has to be read with it"*; *"if it does not get there [a full step back], it has the chance to come down to the next line [3837] the same way"* - a run back short of a full step leaves the zones as they are, and the next line on the same side is the target. The box is a ruler of the run: shown two boxes drawn on H4 in September (each about one step, the second moved along and down by one), *"it is the equal distance of the run"* - price runs in equal distances, and the box measures one. **The frame is the box, the shift is a reading**: *"this [the zone shift] is reading the market, but the 80-dollar box level is the main frame"*. [Claude, measured on the example over FBS H4, 2026-11-01] the lines 4066.41 and 4217.25 sit on the October cluster's low (07/10 16:00 Thai, 4066.42) and high (12/10 08:00, 4217.08), 150.84 apart = two steps of 75.42 with 4141.83 between (the owner, asked: *"yes - it is the October price cluster"*); the other H4 ZigZag turns from August to October lie 0 - 38 USD from the nearest line (the low of 23/10, 3975.58, 14 beyond 3989.57). The owner's example (MT5, XAUUSD H4, 2026-11-01, FBS-Demo): lines at 4522.13, 4445.15, 4369.19, 4293.24, 4217.25, 4141.83, 4066.41, 3989.57, 3912.64, 3835.84 - [Claude, from the screenshot's labels] steps 75.4 - 77.0 USD, mean 76.25; an example, the step is not a fixed number. Not yet a bot rule. |
| **The goal** | the owner, 2026-10-30: *"my real, highest goal is that we know where 100 and 0 are"* - reading the leg's start and end right is the whole method; everything else follows from it. How (the owner's thoughts the same day - information, not yet a rule): price gathers in **2-3 clusters**, around **61 - 38 %** and **61 / 78 - 88 %** of a leg, so the clusters show where the levels - the tops and bottoms - are; *"seen from another angle it is counting three peaks - Elliott waves"*, *"in each wave we aim at"*. On 07/10 (leg 4184.25 -> 4161.42, the owner's labels) Claude measured two clusters: 4174-4178 (about 30-43 %, thin) and 4163-4169 (about 65-91 %, thick) - one leg, not evidence. Common Elliott guidelines (outside sources, trading-education posts): wave 2 retraces 50 / 61.8 / 78.6 / 88.6 % of wave 1, wave 4 23.6 / 38.2 % of wave 3, wave 3 reaches 161.8 / 200 / 261.8 % of wave 1. |
| **07/10/2026 07:00, the owner's drawing** | shown the bot's BUY Fibo on the up leg 4154.21 -> 4184.25 (0 % at 4154.21): *"this is the picture I use - only I draw it the other way round"*, and asked whether that means a buy: *"buy what? sell!"* - **0 % at the top 4184.25, 100 % at 4154.21, a SELL in the zone (price was at about 50 - 61.8 %, 4169 - 4166), targets 127.2 / 161.8 % = 4146.04 / 4135.64 below** (both reached that day). The bot's side then (M15 structure, rule 16) was still BUY until 09:15 - the direction was the bot's error, the drawing was not. The owner earlier: *"the edge is when the big trend is down"* |
| **Keep it simple** | the owner, 2026-10-30, on the signal study: *"really, the principle is simple - find the turning point; the target, SL and TP from ZigZag and Fibo together; draw the levels right, that's enough"*; and how a test runs: *"from the start date, wait until a clear ZigZag leg appears, draw the Fibo, and trade from there when price comes into the zone; win or lose, find the next leg, draw the Fibo again, and trade when price comes into the zone"* - one trade at a time, leg after leg. **While there is no trade yet**, a break moves the Fibo (the owner, 2026-10-30: *"if it breaks the price you have to move the Fibo - it means the run is not over"*; asked if this is while there is no trade: *"while we have no trade yet"*). [Claude's wording of it:] a new low past 0 % moves 0 % down; a new high past 100 % retires the drawing and the next pullback is drawn from the new top; once filled, the trade's stop and target stay as written (BOT_RULES rule 12, the owner's "hold it"). On the filters (2026-10-30): *"cut what makes the decision worse - with the Fibo, cut the trend legs at the entry"*; and on 61.8 vs 38.2 %: *"61 and 38 are almost the same, just the Fibo the other way round"* (the entry level stays as written). On the bot's MT5-style drawing of 07/10 (0 % at the low 4161.42, 100 % at the top 4184.25): *"the Fibo is reversed from what I use - but try it first"* - the owner's labels run the other way (a level x of the bot's is the owner's 1 - x: the bot's 61.8 % is the owner's 38.2 %). On the same day, the pullback to the entry never came (price rose only to 4169.59 after 07:00, the 38.2 % entry 4175.53): *"once it breaks the low it has to be entered anyway, whichever way the Fibo is drawn"*; how - *"by the principle, the retest of the old low"*; the stop and target, chosen from Claude's three (07/10: SL above the bounce's high 4169.89, TP the 261.8 % extension 4124.48, R about 4): **"C"** (2026-10-30). |
| **Examples** | a question or a chart the owner shows is information, never a rule; a number in an example is not a rule |

The owner foresaw the hard part: reading whether the market is trending or sideways. Which high is 100 %
when a fall has several highs was researched at the owner's request: the high the fall began from
(`eye/BOT_RESEARCH.md`, "Correction - the fill bug").

### The bot (2026-10-28)

The owner: *"write the code and let a bot do the work - correct, with every condition."* `eye/bot2e.py`
applies these steps bar by bar on the stored data - since 2026-10-31 at every 5-minute time of the day, 00:00 - 23:55 Thai (the owner: *"run it all the time"*; before, inside the owner's windows) - on closed bars only, and
writes its decisions to `eye/bot_ledger.csv` (scored by `score.py`, read in money by `money.py --ledger`);
research runs write to `eye/research/<variant>/` instead, so `bot_ledger.csv` may be empty.
Its rules in force are `eye/BOT_RULES.md` (`eye/BOT_SPEC.md` is their history); every definition the owner did not
give is marked `[Claude]` there and is a parameter written into each decision. Built by a Sonnet agent, reviewed twice by Codex, checked by
Claude. **First runs (06-07/04 and 20-27/10/2026): no decision** - the reward floor and step 2 refused
everything; the count was found splitting a double top in one zone (BOT_SPEC revision 3). **October 2026
under the owner's rules (revision 3, 11 variants): no trade** (`eye/BOT_RESEARCH.md` round 1). An entry on M1
(revision 4) was **Claude's misreading of a question of the owner's** and was removed at the owner's word
(10-29). The owner's Fibonacci (above): round 3 (revision 5, Claude's wrong leg) lost; round 4 (revision 6) won October and
failed September; the current build follows `eye/BOT_RULES.md` ; its runs, before and after rule 11 was rewritten, are in
`eye/BOT_RESEARCH.md`.

### What Claude understands (Claude's words, for the owner to correct)

*(Written 2026-10-28 with H1 as the higher timeframe; the bot's side since 2026-10-30 evening is H4's clear trend, else a fade of the latest run - BOT_RULES rule 16.)*

**It is a trade with the H1 trend, entered at the end of a counter-move.** H1 says which way the market is
going. On M5-M15 price moves against that - up into a resistance in an H1 down trend, down into a support
in an H1 up trend. That counter-move is what gets counted: 3 to 5 ZigZag peaks into the level, each
push weaker than the last on MACD and RSI against price - the divergence. The counter-move is tired; it is not yet
over. **It is over when the structure turns**: the last swing low (for a sell) breaks, price bounces
weakly into a lower high, the low that bounce left from breaks, and the entry is the retest of that broken
low from below. So the trade is never a guess that a level
will hold - the level is where to look, the peaks and divergence say the push is tiring, and the
structure turning is the proof. The stop sits beyond the extreme of the counter-move - the top
(or bottom) the peaks were counted into - because a new extreme means the counter-move was not over; the
target is the next level the H1 move runs into.

What this is **not**: not 2d (2d refused every reversal on M5 until a trend had formed; here the M5-M15
reversal *is* the entry, in the H1 direction). Not a fade of the H1 trend: a buy at support in an H1 down
trend is not this setup, however good the divergence *(Claude's inference from the owner's "at support
when the buy side has the edge" - the owner's words are the table's)*.

Every step except two can be read the same way by anyone: ZigZag peaks, MACD and RSI values, a swing low
broken, a lower high, a lower low. **The two that need judgement are which level from the left counts,
and what "the H1 trend" is at that moment** - that is where a reader's bias can enter, and where the
record has to say what was seen before the reveal.

### What can be done with it

| | what | state |
|---|---|---|
| 1 | **Walk real days under 2e** (days 3 and 4, 04-06 and 04-07, walked; next 04-08), with `walk.py` (H1 + M15, and M5; ZigZag, MACD, RSI at MT5's defaults). At each decision write which of the seven steps held | **in progress** |
| 2 | **Record the seven steps on every trade**: a `setup` column in the ledger (not `steps` - `sessions.csv` already has a `steps` column, the bars walked), seven characters like `rules`: `+` held, `-` broken, `?` not judged, so each step is measured the way the nine rules are. **A 2e trade is judged by `setup`; its `rules` column still records the nine, where 2e has replaced rules 4 and 9 (below)** | **done** 10-28 |
| 3a | **`score.py` fills an order by the side price was on** - it filled every SELL as a sell limit, so a sell under price filled before price got there (RULES_REVIEW M1); it now withdraws an order whose stop or target trades first (rule 8), and fills a gapped stop at the bar's open. Trades still open when the stored bars end are `open`, not a result | **done** 10-28; the twelve stored trades re-score identically in every planned column (fill, exit, result, R, miss); the on-sight column was re-scored under the hold rule |
| 3 | *(Claude's proposal)* **Let the code find the candidates, the eye judge them.** Steps 2-5 are mechanical: a scan of the stored bars can list every place where 3-5 ZigZag peaks with divergence were followed by a structure break, the low breaking and its retest - found by the clock, not picked by a reader. The reader then judges only the level and the H1 trend, before seeing what followed. This answers the "one reader chooses the trades" hole | possible now; not built |
| 4 | **Hold until the stop or the target** - the owner answered 10-28 | **done** in `score.py` |
| 5 | **A second reader**: Codex given the seven steps and the same charts, reading apart | the tool works (stdin); not run on charts |
| 6 | **Check MACD and RSI against the owner's MT5** (Data Window) at a few bars - ZigZag on M15 already matched | waiting for the owner |

*(2026-10-30: values the owner has not given are open again for the signal study - `eye/SIGNAL_STUDY.md`, "For the owner to settle".)* **Nothing in the setup is open any more** (10-28): step 6 - beyond the highest top / lowest bottom; held
until the stop or the target; divergence as the book has it. What remains is checking the tools (row 6); row 3 became the bot (`eye/bot2e.py`).

**What 2e replaces among the nine rules.** Rule 4's count ("three or four legs, trade the fifth") is
replaced by 2e step 2 (3 to 5 ZigZag peaks) and its entry by steps 3-5; rule 9's target ("a full leg away")
by step 7 (just before the next level from the left) and its stop by step 6. Rules 1-3, 5-8 stand, and
rule 7's reach fits: the entry is a sell limit resting at the broken low, written once price has
closed under it, a few dollars from the price on the screen. Rule 6 (enter and exit on one
timeframe) stands for reading; a trade's fixed stop and target are scored on M5, the finest frame the
walk shows, whichever of M5 or M15 it was read on - finer bars only make "a bar touching both" rarer.

## 2d The picture decides first - Claude's proposal, ON HOLD (2026-10-28), superseded by 2e

> **On hold, the evening of 2026-10-28, before any day was walked under it.** The owner asked how to fix the
> entries; everything below is **Claude's answer, not the owner's method** - the owner said "try it", then,
> on reading the plain summary: *"this is not really my way. What I trade is price structure + divergence
> and counting the peaks of the chart."* None of the thirteen rules mentions divergence, rule 4 is the only
> one near counting, and this section drops counting altogether and refuses the reversals counting finds
> (the 02/04 Asia triple top). Kept as a record; real day 3 waits for the owner's method to be written
> down in the owner's terms.

The owner, looking at every chart in `eye/` the evening of 2026-10-28: *"from all the pictures, the price
structure was not one to enter at all. How do we fix it?"* Read again, all twelve decisions: the two
clean trend pullbacks into a level paid or would have (#3, D1-1); seven of the eight losers were taken in
one of four pictures - in the middle of a leg still falling or rising without a pause, in the middle of a
chop, against a break that had just happened, or on a news bar - and the eighth (#23) was the nearest to
acceptable and still not a trend. **Against it:** #11 and #17 were not trend pictures either, never filled,
and would have won on sight (`RULES_REVIEW.md` section 4). That reading was made **after** the results
were known, by the reader who took the trades, on twelve trades - it is the hypothesis, not the evidence. This section is written before
day 3 so that the days after it can judge it, and **it is not edited once day 3 starts**; a change is a
new section with its date.

Until now the order was "price is near a level, so find a reason to trade it". It is reversed: **the
picture decides whether there is a trade at all; the level only decides where.**

**Step 1 - label the picture at every look, before advancing,** in `looks.csv` (one row per look: the
time `walk.py` printed, the price, the label, the nearest level band and its distance, the decision). The
labels, read on the M5 frame with H1 for context:

A **swing** is a turn on M5 after which price retraced **at least a third of the leg that led into it**.
Smaller wiggles are not swings. Scale-free on purpose: the same words work at 7 and at 57 USD of risk.

| label | the picture | allowed |
|---|---|---|
| **TREND** | the last two swing highs AND the last two swing lows both higher (up) or both lower (down), and no close beyond the last swing low (up) / high (down) since | the one entry, step 2 |
| **VERTICAL** | the live leg is longer than the leg before it and has not yet printed a one-third retrace | no trade - wait for the pause |
| **CHOP** | neither TREND condition holds: highs and lows do not agree | no trade |
| **FRESH BREAK** | price closed through a level from the left within the last 12 bars and has not come back to it | no trade against it; wait for the retest, which may become step 2 |
| **NEWS** | 19:15-20:45 Thai on the first Friday of the month (the US jobs report, 19:30 or 20:30 by daylight saving), or within 15 minutes after an M5 bar whose range is more than three times the average of the 12 before it | no trade, and no order resting through it |

When two fit, the more restrictive one wins (NEWS, then VERTICAL, then FRESH BREAK, then CHOP).

**Step 2 - the one entry: a pullback in a trend, into a level, with the higher low printed.**

- The picture is TREND, and the trade goes **with** it.
- Price pulls back into a band from the left - a level earlier days built, or the band of the swing it
  last broke.
- At that band M5 prints the turn: a low (in an up trend) followed by **two closed bars that do not
  undercut it, the second closing above the high of the low bar** (mirror for a down trend).
- Entry at the market on that close, provided it is within rule 7's reach of the turn's extreme;
  otherwise no trade.
- Stop beyond the band and beyond the turn's extreme, whichever is further (`LESSONS.md` 5).
- Target before the last swing high (up) / low (down) - a few dollars short of the line, not on it.
- If the target is less than 1 R away, no trade.

Nothing else is an entry. Of the four patterns rule 5 names, the sweep that closed back qualifies only
when it happens as this pullback inside a TREND; a reversal from a falling market is not taken until the
picture has become an up TREND.

**Step 3 - be there when it happens.** Advance 12 bars at a time while price is more than one band width
from the nearest level, and **3 bars at a time inside that distance** (`RULES_REVIEW.md` C9: the catch
window at 01/04 New York was about 20 minutes, a third of a 12-bar step).

**What would decide it.** After about thirty windows: how often TREND occurs at all, what the step-2 trades
pay, and what each refused picture would have paid had it been taken - the last written as a priced
candidate at the look, before advancing, so that `shut` stops being a word without a number (Codex X1).

## 3 What a decision is

For each panel, before anything after the cut-off is drawn, I write:

- **the structure I see** in a sentence - what the swings are doing, where the shelves and the origins of
  moves are;
- **BUY, SELL or no trade**;
- when it is a trade: **entry, stop and target, as prices**, and the structure each one comes from.

The entry must be a price the market can reach from where it is now - not a price I would like. If the
level I want is already far behind price, that is **no trade**, and it says so.

## 4 How a trade is scored

- **The clock starts when the decision is made**, not at the sampled bar: a moment is where I sit down and
  the decision comes after however long I waited (section 2b), so `decided_at` is the start of both windows
  below (`score.py`). The text used to say "the cut-off" while the code used `decided_at`; the code is
  right and this is the correction (reviewer, 2026-10-28).
- Entry fills when price trades through it within **24 bars** (2 hours) of the decision. If it never does:
  **no fill**, which is recorded and counted - a plan that does not fill is a plan that earned nothing.
  If the stop or the target trades on a bar before the entry does, the order is withdrawn: **no fill (stop
  or target first)** - rule 8. While fewer than 24 bars after the decision are stored, an unfilled order
  is `open`, not a no-fill. A stop order that a bar gaps through fills at that bar's open; R stays on the
  planned risk.
- **A 2e entry is a stop limit** - the ledger's `trigger` column holds its stop price (a little beyond the
  low, for a sell), `entry` its limit price (the broken low). `score.py` wakes the order when price trades
  through `trigger`, then fills the limit on the retest from the next bar, with its own 24 bars; the stop
  traded before the trigger withdraws it, and a trigger never reached in 24 bars is `no fill (never
  triggered)`. Written without a `trigger`, a 2e decision must wait until a bar has closed through the low,
  and is then a plain sell limit. **Never a plain order at the low before the break:** it would sit under
  the price on the screen and score as a sell stop - filled on the break, which is the entry the owner
  rejected (reviewer, 2026-10-28; on the example: decided 08:30 Thai,
  after the break bar, it fills 08:35 on the retest; decided 08:15, it fills 08:30 on the break).
- After the fill, the first of stop or target decides the result. **A bar touching both counts as the
  stop.**
- ~~If neither is touched within 48 bars (4 hours) of the fill, the trade is closed at that bar's close.~~
  **Superseded 2026-10-28 (the owner: "hold it"): a trade is held until its stop or its target.** A trade
  neither has reached when the stored bars end is `open` - not a result, scored again when there are more
  bars. None of the twelve earlier trades was time-closed in its planned columns; their on-sight column
  was re-scored under the hold rule. The fill bar itself counts, so a bar that
  reached the entry and the stop is scored as a stop: five-minute OHLC cannot say which came first, and
  the conservative reading is taken.
- **An order fills when price trades through the entry from the side it was on at the decision** - a limit
  and a stop alike (2026-10-28, RULES_REVIEW M1). Scored on M5.
- R = (the move in my favour) / (entry - stop). Costs: the spread, **0.30 USD**, taken off every entry -
  the owner's real account pays about 30 points on gold.

**Answered 2026-10-28 by the owner: hold until the stop or the target - no time limit** (2e; `score.py`
scores new trades that way). The question as it was written:

**Open question about the 4 hours (written 2026-10-28, not yet decided).** The 2-hour fill and 4-hour
resolve windows were chosen when a moment was a single panel, and they have never been checked against the
owner's standing rule that *a setup needing four to eight hours of holding, even overnight, is fine if it
pays - the sixty-minute scalp was a method, not the goal.* Real day 1 is exactly that case: the London plan
was never filled, and the price it was aiming at arrived at 22:40, about **eight hours** after the
decision. A 4-hour cap scores that day as nothing happening. ~~Both columns will be kept on every trade
from here (resolved at 4 hours, and resolved at the end of the day) before either is called the measure.~~
(Not done, and no longer needed: the owner answered - hold until stop or target.)

## 5 What is written down

`ledger.csv` - one row a trade: sheet, panel, cut-off, side, entry, stop, target, fill, exit, exit reason,
R net of the spread, the structure named at entry, which pair of rules fought (`conflict`), what the
same idea paid taken at the price on the screen (`at_decision_r`) and how far the planned entry was
missed by (`missed_by`). **`rules` is nine characters**, one per trading rule in the order they are listed
below: `+` held, `-` broken, `?` not judged - the trades taken before the rules existed. So `++---+-++`
reads: rules 1, 2, 6, 8 and 9 held, rules 3, 4, 5 and 7 did not. `ledger_control.csv` is the same
shape and holds
the trades taken before the nine rules existed; the two are never mixed in a figure.

`looks.csv` - made for section 2d (on hold) and unused: header only.

`sessions.csv` - one row per window walked, trade or no trade (section 2c). The denominator for everything
in the ledger.

`SHEETS.md` - every reading in my own words, written before the reveal, and the score after it: the
sampled panels first, then the reset and the real days.

`LESSONS.md` - only what the ledger supports, with the trade numbers that support it. Nothing that comes
from one trade.

## 6 What would make this worth keeping

The owner's bar is **+0.15 R a trade after costs**. The question is **whether a hand-read entry at a
live structure pays more than one R when it is right**.

A hundred trades at a win rate near 50 % still carries a standard error of about 0.1 R, so a hundred will
show a shape, not a verdict. That is what the owner asked for: *see the picture*, not prove a system.

---

## The nine trading rules, separated from the rest (owner, 2026-10-28)

Asked for the rules, I listed thirteen and the owner separated them: **nine are the rules you look at a
chart and decide by. The other four are not trading rules at all** - one is a stance, one is how the test
is run, one is how it is recorded, one is the bar it is judged against. Keeping them in one list hid which
ones a trade actually turns on.

**The nine, in the order they are used:**

| | |
|---|---|
| 1 | **Two frames, upper read first.** H1 about four weeks, where the levels are; M5 about 33 hours, the entry (since 2e: M15 about three days as well). The left of the chart must go back far enough to hold a level |
| 2 | **Levels come from the left** - shelves earlier days built, never one that formed minutes ago |
| 3 | **Wait for price to run into one of them.** Not at a level, nothing to decide |
| 4 | **Three or four legs complete, then trade the fifth - with it, never against it.** Ask each time which leg is alive and whether this trade goes its way |
| 5 | **The structure AT the level says whether it holds.** Buying a support needs **HH and HL together**; selling a resistance needs **LH and LL together**; and a named chart pattern on top |
| 6 | **Enter on a timeframe, exit on that timeframe** |
| 7 | **The entry must be a price the market can reach from here**, not one I would like. If the level I want is already behind price, there is no trade. **And not far from the price on the screen** *(the owner gave 4 USD as an example, not as the rule - 2026-10-29)* (owner, 2026-10-28: an obvious level may never be reached precisely because it is obvious). Beyond that, take it at the market or pass - measured over 12 trades: the planned entries made -0.378 R a trade and the same ideas taken on sight made -0.144 (held until stop or target; corrected twice on 10-28 from -0.124, `RULES_REVIEW.md` C1 and section 7), with all three unfilled plans winning and the misses 3.37, 3.85 and 3.82 USD - and on the nine filled trades, on sight was worse. *(Measured at 12; with D3-1, 13 decisions: -0.348 a trade planned, -0.012 on sight - `docs/HANDOFF.md`.)* |
| 8 | **The order must fill while the idea is still intact.** Not a question to anyone - a check on where the order sits against price. A sell limit above price in a rising market fills only because price kept rising, which is the idea failing (moment #13: filled 5370, stopped five minutes later). A buy limit below price in a rising market fills on the pullback, which is what was wanted |
| 9 | **The stop sits beyond the structure that proves the idea wrong; the target is a full leg away** - the next level from the left |

**The four that are not trading rules:** no indicators (a stance - since 2e, MACD, RSI and ZigZag are the
owner's exception); a sampled moment is where I sit down and
the chart advances until the picture is worth trading (how the test is run); the decision is written before
the reveal and every trade and every wait is recorded, scored with 2 hours to fill, held until stop or target (4 hours until 2e), a
bar touching both counted as the stop and 0.30 USD of spread off every entry (how it is recorded);
+0.15 R a trade after costs (the bar).

Of the nine, only rule 5 has any evidence yet, and it is backward-looking on eight trades - the ledger
now holds nine fills, and the ninth is not labelled for it (`LESSONS.md` section 1 says why).

