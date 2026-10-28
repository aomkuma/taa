# Trading by eye: the method

The owner, 2026-10-28, after everything else was archived: *"start from looking at price structure and
finding an entry with an edge. That is all. Any timeframe; the principle is enter on a timeframe, exit on
that timeframe. Try trading with your bare eyes."* Then: *"you need to trade a hundred times before the
picture appears."*

So this folder is a hundred hand-read trades on real candles, and nothing else. No indicator, no rule set,
no filter, no knowledge base. **These rules are written before the first chart is drawn**, so that what
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

1. **H1, about three weeks** - where the levels are. Read this first, always.
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
| **The side with the edge** | **the trend on H1** |
| **Where** | **at resistance when the sell side has the edge, at support when the buy side has the edge** - never the other way round |
| **The count** | **3 to 5 peaks, counted from MT5's ZigZag** |
| **Divergence** | **on MACD, on RSI, and on price** - price's peaks against the oscillators' (the owner's "yes" to that reading; to confirm) |
| **The entry** | **wait for the structure to break, then the retest of the support or resistance it broke** |
| **Settings** | **MT5's own defaults** - ZigZag 12 / 5 / 3, MACD 12 / 26 / 9, RSI 14 |
| **Entry timeframe** | **M5 to M15** |
| **The stop** | **beyond the High** (sell) / **Low** (buy) - see the principle below |
| **The target** | **just before the opposite level on the left** - see the principle below |

Read together, in order: H1 says which side has the edge; price comes into a level on that side; ZigZag
counts 3 to 5 peaks into it with divergence on MACD, RSI and price; the structure breaks; the entry is the
retest of the line it broke, on M5 to M15. (This sentence only strings the owner's answers together; it
adds nothing.)

### The principle, generalised from the owner's example

The owner, 2026-10-28: *"this is an example - you have to summarise it into a principle, not turn the
example into a fixed rule."* So no number from the example is a rule; the example below only shows what
the words mean. Written for a sell; a buy is the mirror of every line.

1. **Context** - the H1 trend gives the sell side the edge, and price has come up into a **resistance**
   the left of the chart built.
2. **Exhaustion** - ZigZag counts **3 to 5 peaks** into that level, with **divergence** on MACD, RSI or
   price.
3. **The structure breaks** - price takes out the **last swing low**: the up leg is over.
4. **The retest** - a **weak bounce** that makes a **lower high** under the top.
5. **The entry** - sell when price **breaks the low the bounce started from**: the new lower low.
6. **The stop** - beyond **the high whose break would cancel the lower-high / lower-low structure**: the
   bounce's high (the lower high), not the top of the whole move. *Claude's reading of "above the High",
   from the logic of the setup - to be confirmed by the owner.*
7. **The target** - **just before** the opposite level from the left: for a sell, a little above the next
   support, never on the line.

Not yet given: how long a trade is held (the example's target came after 4 h 25 min, past the 4-hour
resolve window of section 4).

**The owner's own example, 2026-10-28** (on the FBS-Demo M15 chart, server time): *"suppose that around
03:15 it bounced lightly and then made an LL - sell; SL above the High; TP above the resistance on the left
of the chart at 4030."* On the stored bars: top 4070.76 at 02:10; the structure broke at 03:00-03:05 (low
4055.57 under the 4059.30 and 4057.66 lows); the light bounce reached 4062.76 at 03:20-03:25 (a lower
high - the retest); 03:30 broke 4055.57 for the LL - **sell on the break of 4055** (the owner: *"when it
loses 4055"*). TP 4031 was reached at 07:55 and the highest price on the way was 4059.31. With the stop
above the bounce's high (4063): risk 8.0, **+2.96 R**; above the top (4071): risk 16.0, **+1.48 R** (both
after the 0.30 spread). One example,
read after the fact - it shows what the words mean, not that they pay.

It also lands on an open question: the target came **4 h 25 min after the entry**, past `score.py`'s
4-hour resolve window (section 4), which would have closed it at the market at 07:30.

### What Claude understands (Claude's words, for the owner to correct)

**It is a trade with the H1 trend, entered at the end of a counter-move.** H1 says which way the market is
going. On M5-M15 price moves against that - up into a resistance in an H1 down trend, down into a support
in an H1 up trend. That counter-move is what gets counted: 3 to 5 ZigZag peaks into the level, each
push weaker than the last on MACD, RSI or price - the divergence. The counter-move is tired; it is not yet
over. **It is over when the structure turns**: the last swing low (for a sell) breaks, price bounces
weakly into a lower high, and the next lower low is the entry. So the trade is never a guess that a level
will hold - the level is where to look, the peaks and divergence say the push is tiring, and the
structure turning is the proof. The stop sits where that proof would be undone; the target is the next
level the H1 move runs into.

What this is **not**: not 2d (2d refused every reversal on M5 until a trend had formed; here the M5-M15
reversal *is* the entry, in the H1 direction). Not a fade of the H1 trend: a buy at support in an H1 down
trend is not this setup, however good the divergence.

Every step except two can be read the same way by anyone: ZigZag peaks, MACD and RSI values, a swing low
broken, a lower high, a lower low. **The two that need judgement are which level from the left counts,
and what "the H1 trend" is at that moment** - that is where a reader's bias can enter, and where the
record has to say what was seen before the reveal.

### What can be done with it

| | what | state |
|---|---|---|
| 1 | **Walk real days under 2e**, from 2026-04-03 Asia 07:00, with `walk.py` (H1 + M15, and M5; ZigZag, MACD, RSI at MT5's defaults). At each decision write which of the seven steps held | ready once the two open answers below are in |
| 2 | **Record the seven steps on every trade**: a `steps` column in the ledger, seven characters like `rules` (`+` held, `-` broken), so each step is measured the way the nine rules are | to add before day 3 |
| 3 | **Let the code find the candidates, the eye judge them.** Steps 2-5 are mechanical: a scan of the stored bars can list every place where 3-5 ZigZag peaks with divergence were followed by a structure break and a lower-high retest - found by the clock, not picked by a reader. The reader then judges only the level and the H1 trend, before seeing what followed. This answers the "one reader chooses the trades" hole | possible now; not built |
| 4 | **Score both hold times** on every trade - the 4-hour window and to the end of the day (section 4 already asks for both) - until the owner says how long a trade is held | the second column is not in `score.py` yet |
| 5 | **A second reader**: Codex given the seven steps and the same charts, reading apart | the tool works (stdin); not run on charts |
| 6 | **Check MACD and RSI against the owner's MT5** (Data Window) at a few bars - ZigZag on M15 already matched | waiting for the owner |

**Still open, the owner's to answer:** step 6 - the stop beyond the bounce's lower high rather than the
top (Claude's reading); how long a trade is held; and that "divergence on price" means price's peaks
against the oscillators'.

The nine rules stand where this does not contradict them; where it does, this wins.

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
- Entry at the market on that close, provided it is within rule 7's 4 USD of the turn's extreme;
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
- After the fill, the first of stop or target decides the result. **A bar touching both counts as the
  stop.**
- If neither is touched within **48 bars** (4 hours) of the fill, the trade is closed at that bar's close.
  The fill bar itself is included in that window, so a bar that reached the entry and the stop is scored as
  a stop: five-minute OHLC cannot say which came first, and the conservative reading is taken.
  Enter on M5, exit on M5.
- R = (the move in my favour) / (entry - stop). Costs: the spread, **0.30 USD**, taken off every entry -
  the owner's real account pays about 30 points on gold.

**Open question about the 4 hours (written 2026-10-28, not yet decided).** The 2-hour fill and 4-hour
resolve windows were chosen when a moment was a single panel, and they have never been checked against the
owner's standing rule that *a setup needing four to eight hours of holding, even overnight, is fine if it
pays - the sixty-minute scalp was a method, not the goal.* Real day 1 is exactly that case: the London plan
was never filled, and the price it was aiming at arrived at 22:40, about **eight hours** after the
decision. A 4-hour cap scores that day as nothing happening. Both columns will be kept on every trade from
here (resolved at 4 hours, and resolved at the end of the day) before either is called the measure.

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

The owner's bar is **+0.15 R a trade after costs**. The number this body of work has to beat is the one
measured the night everything was archived: **-0.115 R a trade**, where the direction was right 53.8 % of
the time and the winners paid only +0.643 R against losers at -1.00 R. So the question is not "is the
direction right" - it was already. It is **whether a hand-read entry at a live structure pays more than
one R when it is right**.

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
| 1 | **Two frames, upper read first.** H1 about three weeks, where the levels are; M5 about 33 hours, the entry. The left of the chart must go back far enough to hold a level |
| 2 | **Levels come from the left** - shelves earlier days built, never one that formed minutes ago |
| 3 | **Wait for price to run into one of them.** Not at a level, nothing to decide |
| 4 | **Three or four legs complete, then trade the fifth - with it, never against it.** Ask each time which leg is alive and whether this trade goes its way |
| 5 | **The structure AT the level says whether it holds.** Buying a support needs **HH and HL together**; selling a resistance needs **LH and LL together**; and a named chart pattern on top |
| 6 | **Enter on a timeframe, exit on that timeframe** |
| 7 | **The entry must be a price the market can reach from here**, not one I would like. If the level I want is already behind price, there is no trade. **And no further than 4 USD from the price on the screen** (owner, 2026-10-28: an obvious level may never be reached precisely because it is obvious). Beyond that, take it at the market or pass - measured over 12 trades: the planned entries made -0.378 R a trade and the same ideas taken on sight made -0.217 (corrected 10-28 from -0.124, `RULES_REVIEW.md` C1), with all three unfilled plans winning and the misses 3.37, 3.85 and 3.82 USD - and on the nine filled trades, on sight was worse |
| 8 | **The order must fill while the idea is still intact.** Not a question to anyone - a check on where the order sits against price. A sell limit above price in a rising market fills only because price kept rising, which is the idea failing (moment #13: filled 5370, stopped five minutes later). A buy limit below price in a rising market fills on the pullback, which is what was wanted |
| 9 | **The stop sits beyond the structure that proves the idea wrong; the target is a full leg away** - the next level from the left |

**The four that are not trading rules:** no indicators (a stance); a sampled moment is where I sit down and
the chart advances until the picture is worth trading (how the test is run); the decision is written before
the reveal and every trade and every wait is recorded, scored with 2 hours to fill, 4 hours to resolve, a
bar touching both counted as the stop and 0.30 USD of spread off every entry (how it is recorded);
+0.15 R a trade after costs (the bar).

Of the nine, only rule 5 has any evidence yet, and it is backward-looking on eight trades - the ledger
now holds nine fills, and the ninth is not labelled for it (`LESSONS.md` section 1 says why).

