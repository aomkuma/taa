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
