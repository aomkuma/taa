# What we have tried, and whether it worked

One row per method, added the day it is tried, with the evidence and a verdict. A row is never rewritten;
when a verdict changes, the change is written underneath with its date and what changed it.

**Verdicts.** `WORKS` - measured, forward, on enough trades to mean something. `FAILS` - measured and it
lost, or it cannot work mechanically. `UNPROVEN` - adopted on reasoning or on a handful of trades, still
owes its forward evidence. `UNRESOLVED` - measured twice with opposite answers.

The bar everything is judged against: **+0.15 R a trade after costs**.

---

## The eye work, from 2026-10-28

| # | The method | What the evidence was | Verdict | The lesson |
|---|---|---|---|---|
| 1 | **Decide at a clock-sampled moment**: sample by the calendar, read the chart, decide there | 12 moments, 9 trades, 7 fills, 1 win, **-0.357 R a fill**. The owner, looking at the sheets: 90 % were not spots worth watching | **FAILS** | A sampled bar is not a decision. Trading 8 of 12 moments is itself the signal that the moments were wrong |
| 2 | **One frame only**: judge from 110 M5 bars, nine hours | Every "level" named was a shelf built that morning. At moment #13 I sold into a market that had just broken a week-long ceiling with nothing above it; the trade that was there paid **+7.1 R in the direction I sold** | **FAILS** | Nine hours cannot contain a level. The missing thing was not skill, it was the left of the chart |
| 3 | **Two frames, read top first**: H1 about four weeks for the levels, M5 33 hours for the entry | Adopted after #2. One trade taken under it so far (lost, for a reason row 6 explains) | **UNPROVEN** | - |
| 4 | **Levels from the left**: only shelves earlier days built, never one that formed minutes ago | Both of the clean winners in the whole record (#3 +3.67 R, and the 14/08 hand-read +1.62 R) were at such a level; the four full-stop losers were at shelves hours old | **UNPROVEN** | Measured only backwards so far |
| 5 | **Wait at the moment**: advance a few bars at a time until the picture is worth trading, or the session ends with nothing | At #13 trading on arrival meant buying a base that broke 40 USD within half an hour; waiting 210 minutes found a real setup instead. But that setup then lost, for reason 6 | **UNPROVEN** | Waiting removes bad trades. It does not by itself make the remaining one good |
| 6 | **The structure AT the level** (owner): buying a support needs **HH and HL together**, selling a resistance needs **LH and LL**, with a named pattern on top | Labelled on all 8 filled trades from the swings in the six hours before each decision: **with it, 4 trades, +0.14 R each; against it, 4 trades, -1.02 R each - all four a full stop, no exception** | **UNPROVEN, and the most promising thing measured** | The split is clean and it was measured backwards on 8 trades, with the "with" side resting on one winner. The next fifty decide it |
| 7 | **Tight stop at the structure, target a full leg away** | The one winner paid +3.67 R, which the archived system never did; across 6 fills the best move in my favour had a median of **3.73 R** and 5 of 6 went past 1 R | **UNPROVEN** | The geometry is right in shape; what kills it is being stopped before the move |
| 8 | **Widen the stop to survive the sweep** | On 2 trades: a stop wide enough to survive costs 4-7x the risk and pays +0.3 to +0.5 R, so **not worth it**. On 6 trades: the median best move was 3.73 R, so surviving **is** worth it | **UNRESOLVED** | I wrote a confident conclusion from each sample and they contradict. Nothing decides this under about thirty trades |
| 9 | **A limit inside the level being faded** (sell limit above price into resistance) | #13: the order could only fill if price rose through the level - it filled at the moment the idea was failing, and the stop went five minutes later | **FAILS** | Before every order: *does this fill when the idea is right, or when it is wrong?* |
| 10 | **Sell the first bounce into a shelf that just broke** | #15: filled 5098, stop 5126 hit **five minutes later**, price ran to 5174 | **FAILS** | After a long run down, the first bounce can be the reversal. Selling it needs the bounce to show exhaustion, not just a level overhead |
| 11 | **Buy a support while the trend is violently down**, on a sweep and a higher low | #1 of the reset: a week-long shelf, a sweep to 4583, a 180 USD bounce, a higher low at 4600 - and the level broke five minutes after the fill, price 213 USD lower | **FAILS** | A 180 USD bounce inside an 18 %-in-three-days collapse is a breath, not demand. And the high was still falling: row 6 would have refused it |
| 12 | **Real trading days, one at a time** (owner): take a date whole, walk all three windows in order, write every window down trade or not | Two days, 2026-04-01 and 2026-04-02: **6 windows walked, 4 with no trade, 2 decisions, 1 fill, -1.02 R**. One of the six could not be judged and is marked an observation | **UNPROVEN** | It is the first method whose denominator is written down (`sessions.csv`), and the denominator is already the interesting part: two thirds of the windows produced nothing |
| 13 | **Take it at the price on the screen if the plan is more than 4 USD away** (owner) | All 12 trades scored twice: the entries I planned made **-0.378 R a trade**, the same ideas on sight **-0.124**. All three unfilled plans would have won, missed by 2.57, 3.85 and 3.82 USD - every one under four | **UNPROVEN, and the only positive difference measured so far** | Backward on 12 trades, and 3 of the 5 differences are the same kind of event. The gap was +0.275 on 11 trades and is +0.253 on 12. Entering worse widens the stop, so the one winner falls from +3.67 to +2.02 R |
| 14 | **Split the hundred with a second reader** (owner: fifty each, Claude and Codex, then compare) | **Not one sheet was ever answered.** The prompt was passed to `codex exec` as an argument, so it sat on `Reading prompt from stdin...` for 5.5 hours and exited 15 with no output, twice. Stopped 2026-10-28 16:26 Thai | **UNRESOLVED - never ran** | A second, independent reader is still the fix the reviewer asked for (one person chooses the trade and labels the rules). It needs the prompt piped on stdin and one sheet proven end to end before nine are queued |
| 15 | **A stop inside the band**, placed a few dollars under the minor low at the level | D2-1, 2026-04-02: stop 4586 inside the 4550-4600 band, swept at 4580.86, **-1.02 R**; the same idea with the stop beyond the band pays **+1.63 R** and taken on the reclaim **+4.80 R** | **FAILS** | The owner's rule already said it: a level is a band, the stop goes beyond the band. One trade, but the three scorings are of the same bars, so the comparison is clean |
| 16 | **An invalidation written before the level is reached** | D2-1: the plan said losing 4588 meant the level had failed. Price lost it by 5 USD and ran 118 USD the other way; at 20:25 I refused the buy on my own written line | **FAILS as written** | It forbade a sweep-and-reclaim, which is one of the four patterns rule 5 names. A plan may fix the entry and the target in advance; what counts as failure has to be the band, not a number chosen before the sweep |
| 17 | **The picture decides first** (Claude's proposal; the owner said "try it", then "not really my way" - ON HOLD the evening of 10-28, never walked; superseded by the owner's principle, METHOD 2e): label every look TREND / VERTICAL / CHOP / FRESH BREAK / NEWS before advancing; enter only a pullback in a TREND, into a level, on a printed higher low; step 3 bars near a level (`METHOD.md` 2d) | Read backwards on all 12 decisions: the two TREND pullbacks paid or would have (#3 +3.67, D1-1 +1.57 on sight); 7 of the 8 losers were in VERTICAL, CHOP, FRESH BREAK (against it) or NEWS pictures, the eighth (#23) not a TREND either; **but #11 and #17, not TREND pictures, would have won on sight** (+0.82, +0.69). **Labelled after the results, by the reader who took them** | **UNPROVEN** - adopted 2026-10-28 before real day 3 | Ten trades, one reader, hindsight. Under it day 2 would have taken nothing, so the first thing to watch is whether TREND occurs often enough to trade at all (predicted conflict B) |
| 18 | **The owner's setup (METHOD 2e)**: H1 trend gives the side; at a level from the left on that side; 3-5 ZigZag peaks (or two that make an M / W - the owner's M is a buy, W a sell) with MACD and RSI divergence; the structure breaks, the low goes, entry on the retest of the broken low (the broken high for a buy); stop beyond the extreme of the move; target just before the next level; held until stop or target | One example from the owner, worked on the stored bars after the fact: **+1.48 R** (28/10, sell on the retest of the broken 4055 low, stop beyond 4070.76, target above 4030). Nothing walked forward yet | **UNPROVEN** - adopted 2026-10-28, the owner's own method | The first method here that is the owner's, not Claude's. Steps 3-5 are Claude's generalisation of the example; the level and the H1 trend are the two judgements a reader's bias can enter |

**Row 18, day 3 (2026-04-06), the first day walked under it:** one decision (D3-1, no fill - the break ran
through the target before any retest), London `shut`, New York `no-setup`. Read again with the owner: the
London window held the owner's buy - an M on the 4642-4651 support - refused because Claude counted "3 to 5"
literally and read "M" the textbook way (`SHEETS.md`). Verdict unchanged: **UNPROVEN**.

| 19 | **The owner's setup as a bot** (`eye/bot2e.py`, `eye/BOT_SPEC.md`): METHOD 2e applied bar by bar, closed bars only, inside the owner's windows; stop limit orders; reward at least 1:2 (owner) | Runs on 06-07/04 and 20-27/10/2026: **no decision** - H1 gave no side on many bars, step 2 failed on most, and every setup that reached step 7 was under the floor. Found: the count split the 4141-4142 double top of 21-22/10 into one high (spec revision 3) | **UNPROVEN - being built** | A bot that never trades proves nothing either way; the next run needs months, not days |

**Correction, 2026-10-28 evening (`RULES_REVIEW.md` C1 and C3; the rows above are left as written).**
`score.py` started every walked decision's clock on a bar already on the screen, rolled #15 a day forward
(a Friday decision scored on Monday's bars), and gave the on-sight column 72 bars against 48. Re-scored:

- **Row 10**, #15: the fill was **Friday 06/03 20:30**, not 09/03. The very first bar after the decision
  spiked from 5083 to 5126.48 - it filled 5098 and took the stop 5126 **in the same bar**, fell back to
  5074 within 25 minutes, then rose to 5171.65 inside four hours. Still -1.01 R and still **FAILS**; the
  "five minutes later, ran to 5174" was Monday's story.
- **Row 13**: planned -0.378, on sight **-0.217, not -0.124**; the gap is **+0.161, not +0.253**. The three
  no-fills give +3.08 R; on the nine filled trades on sight was worse by 1.15 R. D1-1 was missed by
  **3.37 USD, not 2.57**. Still **UNPROVEN** - weaker than written, and the no-fill part is largely a
  selection effect of limit orders (C2).
- **Row 13 again, later that evening:** held until stop or target (the owner's rule), on sight is **-0.144**,
  the gap **+0.233**, the no-fills **+4.35 R**, and on the nine fills on sight is worse by **1.55 R**
  (`RULES_REVIEW.md` section 7).

**Row 14, 2026-10-28 evening:** the tool works - `codex exec` with the prompt piped on stdin answered
in about a minute, and reviewed the rules read-only (`RULES_REVIEW.md`). The verdict stays: no chart has
been read by a second reader yet.

## Methods inherited from the archived work

**Old data - a record, not a verdict on anything now** (owner, 2026-10-28: nothing in an archive decides
the present). Measured there, kept here so the same ground is not covered twice. Full record:
`docs/archive/README.md`.

| The method | Verdict there |
|---|---|
| Filtering the side by a larger timeframe's lean (the locked H4 rule, R10) | **FAILS** - on the same candidates it did worse than no filter at all |
| The same frame judged with its slope (`h4_trend`) | **FAILS** - -0.625 R a trade; it refused all nine candidates of the profitable day |
| The owner's frame ordering H1 then H4 then D1 | **FAILS as a filter** - -0.205 R a trade on those candidates |
| Targets nearer than the stop | **FAILS** there - the winners paid less than the losers cost |
| Indicators, a knowledge base, weapon catalogues, shadow rules | Stopped and archived 2026-10-28 by the owner; the method here uses none of them |

---

## The rules on trial (owner, 2026-10-28)

*"The rules need something that proves them too - which ones actually work, and which ones are always in
conflict with another rule, so that they push you into bad trades."*

Every decision from here records, at the moment it is made, which of the nine held and which did not, and
which pair pointed opposite ways (`rules` and `conflict` in the ledger; `eye/rules.py` counts them). Two
questions then become counting: does a rule help, and does it fight the others.

**The conflicts I expect, written before the evidence** so the counting judges the prediction rather than
the other way round:

| | The conflict | Why they fight | What I expect |
|---|---|---|---|
| A | **3 (price has run into a level) vs 5 (the structure at the level)** | Arriving at a level is necessary and not sufficient. Rule 3 says "here is a moment"; rule 5 often says "and it is going to break" | The main one. Every loser so far came from letting 3 authorise what 5 refused. If the counting agrees, **rule 3 is a trigger to look, never a reason to trade** |
| B | **4 (trade the fifth leg with it) vs 5 at a counter-trend level** | At a support inside a downtrend the live leg points down, so a bounce trade is against rule 4 while the level invites it | They will mostly agree to refuse, which is right - but together they may refuse so much that the system almost never trades. Watch the count of stand-asides |
| C | **7 (the entry is reachable) vs 9 (the stop beyond the structure)** | A wide structure forces a far stop; keeping R sane needs an entry near it, and by then price has often left | The window these two leave open may be small. If most moments die here, one of them is wrong as written |
| D | **3 vs 7, through 5** | By the time the structure at the level is readable, price has moved away from the entry | Produces no-fills - two of my first nine trades never filled. If this is common, the entry must be placed as the structure forms, not after it is complete |

**What would make a rule guilty:** it is broken on trades that still win, or every trade it authorises alone
loses, or it is on the losing side of the same conflict again and again. A rule that never once decides
anything is also guilty - of not being a rule.

The control, for comparison: **10 decisions that were trades, -3.51 R, -0.351 a decision** - the 7 control
fills at -2.50 R (**-0.357 a fill**), 2 control plans that never filled at 0, and the single trade of the
reset at -1.01 - all taken before these rules existed. Any figure for the control says which denominator it
uses; the two above are the same trades counted two ways. None of them is judged against the rules, because
scoring my own past decisions from memory would make the rules look however I wanted.

---

## What an outside reader found (Codex, 2026-10-28, review of this whole plan)

Asked to find the holes rather than agree, and given the live documents, the ledgers and the tooling. The
findings I accept, with what was done about each:

| What it found | True? | Done |
|---|---|---|
| **The one finding is one trade wide.** Remove the single +3.67 R winner and the "with structure" group makes -1.03 R each - the same as the group against it | **Yes, checked** | `LESSONS.md` now says it that way, as a sceptic would |
| **The control number has no written definition.** "10 trades, -3.51 R" could not be reproduced from the files | **Yes** | It is 7 filled control trades (-2.50 R), plus 2 that never filled, plus the one trade of the reset (-1.01). Defined below |
| **48 bars is 49 in the code** (`LIVE_BARS + 1`) | **Yes** | Fixed |
| **The spec and the code disagree on when the fill clock starts** - METHOD said the cut-off, `score.py` used `decided_at` | **Yes** | METHOD corrected; the decision time is the clock |
| **Nothing logs the waits.** Only trades are recorded, so "fifty trades" could be fifty picked out of an unknown number of walks | **Yes** | **Fixed** - `sessions.csv`, one row per window walked, trade or no trade; written into METHOD 2c as part of the method, not an extra |
| **Nothing enforces the sequential reveal.** `walk.py` accepts any step, so the tooling cannot show that a decision came before the bars that judge it | **Yes** | Not yet fixed - see below |
| **Rules 2,3,4,5,7,8,9 are not operationally defined** - two readers could disagree and both claim to have followed them | **Yes** | Not yet fixed. The honest consequence: the per-rule table measures a reader, not a rule |
| **One person both chooses the trade and labels which rules held** | **Yes** | Not yet fixed, and the attempt failed: the second reader never answered a single sheet (row 14). This is the largest hole still open |
| **5 versus 7/8 is a conflict the predictions missed**: the structure confirms only after the reachable entry has gone, and an earlier order fills before confirmation | **Yes** | Added to the predicted conflicts |
| 50 trades cannot establish +0.15 R; the standard error is about 0.14 R even at a standard deviation of 1 | Yes, and the method already said a hundred shows a shape, not a verdict | - |

**The control, defined.** 7 trades filled under the old method, **-2.50 R, -0.357 a trade**; 2 more never
filled; 3 moments were stood aside. The single trade of the reset (-1.01) is counted separately. Any figure
quoted for the control from now on says which of those it includes.

**The reviewer's verdict on the whole thing:** price and structure alone could work and nothing here shows
it cannot - but under this protocol fifty trades would largely measure the reader's selection and labelling
rather than the method. That is the thing to fix before spending them.

