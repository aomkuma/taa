# Trading by eye: the method

The owner, 2026-10-28, after everything else was archived: *"start from looking at price structure and
finding an entry with an edge. That is all. Any timeframe; the principle is enter on a timeframe, exit on
that timeframe. Try trading with your bare eyes."* Then: *"you need to trade a hundred times before the
picture appears."*

So this folder is a hundred hand-read trades on real candles, and nothing else. No indicator, no rule set,
no filter, no knowledge base. **These rules are written before the first chart is drawn**, so that what
follows can judge them.

## 1 What is read

Gold, **M5**, drawn as candles and looked at as a picture - never read as a table of numbers. M5 because
of what the first hand-read showed on 2026-08-14: the newest structure on M5 sat 6-8 USD from price while
on M15 it sat 17-20 USD away, so the M15 plan bought a shelf the market had already left. M5 keeps the
entry current and halves the stop, and its stops stay many times the spread, which M1 would not.

Section 2c replaced the sheets: the chart is now advanced bar by bar through a real day, not printed six
panels to a page. `sheets.py`, `moments.csv` and the nine `codex_*.png` sheets are kept as the record of
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
  were taken, and what was being watched. A window with nothing in it is the normal outcome and has to cost
  something to leave out, or "fifty trades" could be fifty picked out of an unknown number of walks
  (the reviewer's finding, 2026-10-28).
- The day is reported to the owner as it happens, trade by trade.

`walk.py` takes either a sampled moment's id or a real datetime: `walk.py "2026-04-01 07:00" 12`.

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
R net of the spread, the structure named at entry, which of the nine rules held (`rules`), which pair
fought (`conflict`), and what the same idea paid taken at the price on the screen (`at_decision_r`) with
how far the planned entry was missed by (`missed_by`). `ledger_control.csv` is the same shape and holds
the trades taken before the nine rules existed; the two are never mixed in a figure.

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
| 7 | **The entry must be a price the market can reach from here**, not one I would like. If the level I want is already behind price, there is no trade. **And no further than 4 USD from the price on the screen** (owner, 2026-10-28: an obvious level may never be reached precisely because it is obvious). Beyond that, take it at the market or pass - measured: the planned entries made -0.319 R a trade and the same ideas taken on sight made -0.044, with all three unfilled plans winning and the misses 2.57, 3.85 and 3.82 USD |
| 8 | **The order must fill while the idea is still intact.** Not a question to anyone - a check on where the order sits against price. A sell limit above price in a rising market fills only because price kept rising, which is the idea failing (moment #13: filled 5370, stopped five minutes later). A buy limit below price in a rising market fills on the pullback, which is what was wanted |
| 9 | **The stop sits beyond the structure that proves the idea wrong; the target is a full leg away** - the next level from the left |

**The four that are not trading rules:** no indicators (a stance); a sampled moment is where I sit down and
the chart advances until the picture is worth trading (how the test is run); the decision is written before
the reveal and every trade and every wait is recorded, scored with 2 hours to fill, 4 hours to resolve, a
bar touching both counted as the stop and 0.30 USD of spread off every entry (how it is recorded);
+0.15 R a trade after costs (the bar).

Of the nine, only rule 5 has any evidence yet, and it is backward-looking on eight trades.

