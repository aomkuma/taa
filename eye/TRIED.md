# What we have tried, and whether it worked

One row per method, added the day it is tried, with the evidence and a verdict. A row is never rewritten;
when a verdict changes, the change is written underneath with its date and what changed it.

**Verdicts.** `WORKS` - measured, forward, on enough trades to mean something. `FAILS` - measured and it
lost, or it cannot work mechanically. `UNPROVEN` - adopted on reasoning or on a handful of trades, still
owes its forward evidence. `UNRESOLVED` - measured twice with opposite answers.

The bar everything is judged against: **+0.15 R a trade after costs**, and the number the archived system
left behind: **-0.115 R a trade**, where the direction was right 53.8 % of the time and the winners paid
+0.643 R against losers at -1.00 R.

---

## The eye work, from 2026-10-28

| # | The method | What the evidence was | Verdict | The lesson |
|---|---|---|---|---|
| 1 | **Decide at a clock-sampled moment**: sample by the calendar, read the chart, decide there | 12 moments, 9 trades, 7 fills, 1 win, **-0.360 R a fill**. The owner, looking at the sheets: 90 % were not spots worth watching | **FAILS** | A sampled bar is not a decision. Trading 8 of 12 moments is itself the signal that the moments were wrong |
| 2 | **One frame only**: judge from 110 M5 bars, nine hours | Every "level" named was a shelf built that morning. At moment #13 I sold into a market that had just broken a week-long ceiling with nothing above it; the trade that was there paid **+7.1 R in the direction I sold** | **FAILS** | Nine hours cannot contain a level. The missing thing was not skill, it was the left of the chart |
| 3 | **Two frames, read top first**: H1 three weeks for the levels, M5 33 hours for the entry | Adopted after #2. One trade taken under it so far (lost, for a reason row 6 explains) | **UNPROVEN** | - |
| 4 | **Levels from the left**: only shelves earlier days built, never one that formed minutes ago | Both of the clean winners in the whole record (#3 +3.67 R, and the 14/08 hand-read +1.62 R) were at such a level; the four full-stop losers were at shelves hours old | **UNPROVEN** | Measured only backwards so far |
| 5 | **Wait at the moment**: advance a few bars at a time until the picture is worth trading, or the session ends with nothing | At #13 trading on arrival meant buying a base that broke 40 USD within half an hour; waiting 210 minutes found a real setup instead. But that setup then lost, for reason 6 | **UNPROVEN** | Waiting removes bad trades. It does not by itself make the remaining one good |
| 6 | **The structure AT the level** (owner): buying a support needs **HH and HL together**, selling a resistance needs **LH and LL**, with a named pattern on top | Labelled on all 8 filled trades from the swings in the six hours before each decision: **with it, 4 trades, +0.14 R each; against it, 4 trades, -1.02 R each - all four a full stop, no exception** | **UNPROVEN, and the most promising thing measured** | The split is clean and it was measured backwards on 8 trades, with the "with" side resting on one winner. The next fifty decide it |
| 7 | **Tight stop at the structure, target a full leg away** | The one winner paid +3.67 R, which the archived system never did; across 6 fills the best move in my favour had a median of **3.73 R** and 5 of 6 went past 1 R | **UNPROVEN** | The geometry is right in shape; what kills it is being stopped before the move |
| 8 | **Widen the stop to survive the sweep** | On 2 trades: a stop wide enough to survive costs 4-7x the risk and pays +0.3 to +0.5 R, so **not worth it**. On 6 trades: the median best move was 3.73 R, so surviving **is** worth it | **UNRESOLVED** | I wrote a confident conclusion from each sample and they contradict. Nothing decides this under about thirty trades |
| 9 | **A limit inside the level being faded** (sell limit above price into resistance) | #13: the order could only fill if price rose through the level - it filled at the moment the idea was failing, and the stop went five minutes later | **FAILS** | Before every order: *does this fill when the idea is right, or when it is wrong?* |
| 10 | **Sell the first bounce into a shelf that just broke** | #15: filled 5098, stop 5126 hit **five minutes later**, price ran to 5174 | **FAILS** | After a long run down, the first bounce can be the reversal. Selling it needs the bounce to show exhaustion, not just a level overhead |
| 11 | **Buy a support while the trend is violently down**, on a sweep and a higher low | #1 of the reset: a week-long shelf, a sweep to 4583, a 180 USD bounce, a higher low at 4600 - and the level broke five minutes after the fill, price 213 USD lower | **FAILS** | A 180 USD bounce inside an 18 %-in-three-days collapse is a breath, not demand. And the high was still falling: row 6 would have refused it |

## Methods inherited from the archived work

Measured there, kept here so the same ground is not covered twice. Full record:
`docs/archive/README.md`.

| The method | Verdict there |
|---|---|
| Filtering the side by a larger timeframe's lean (the locked H4 rule, R10) | **FAILS** - on the same candidates it made -0.165 R a trade against **-0.115 for no filter at all** |
| The same frame judged with its slope (`h4_trend`) | **FAILS** - -0.625 R a trade; it refused all nine candidates of the profitable day |
| The owner's frame ordering H1 then H4 then D1 | **FAILS as a filter** - -0.205 R a trade on those candidates |
| Targets nearer than the stop | **FAILS** - 53.8 % right and still -0.115 R a trade, because winners paid +0.643 against losers at -1.00 |
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

The control, for comparison: **10 trades, -3.51 R, -0.351 a trade**, taken before these rules existed. None
of them is judged against the rules, because scoring my own past decisions from memory would make the rules
look however I wanted.

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
| **Nothing logs the waits.** Only trades are recorded, so "fifty trades" could be fifty picked out of an unknown number of walks | **Yes** | Not yet fixed - see below |
| **Nothing enforces the sequential reveal.** `walk.py` accepts any step, so the tooling cannot show that a decision came before the bars that judge it | **Yes** | Not yet fixed - see below |
| **Rules 2,3,4,5,7,8,9 are not operationally defined** - two readers could disagree and both claim to have followed them | **Yes** | Not yet fixed. The honest consequence: the per-rule table measures a reader, not a rule |
| **One person both chooses the trade and labels which rules held** | **Yes** | Not yet fixed. A second reader, blind to the outcome, could label from the decision-time chart |
| **5 versus 7/8 is a conflict the predictions missed**: the structure confirms only after the reachable entry has gone, and an earlier order fills before confirmation | **Yes** | Added to the predicted conflicts |
| 50 trades cannot establish +0.15 R; the standard error is about 0.14 R even at a standard deviation of 1 | Yes, and the method already said a hundred shows a shape, not a verdict | - |

**The control, defined.** 7 trades filled under the old method, **-2.50 R, -0.357 a trade**; 2 more never
filled; 3 moments were stood aside. The single trade of the reset (-1.01) is counted separately. Any figure
quoted for the control from now on says which of those it includes.

**The reviewer's verdict on the whole thing:** price and structure alone could work and nothing here shows
it cannot - but under this protocol fifty trades would largely measure the reader's selection and labelling
rather than the method. That is the thing to fix before spending them.

