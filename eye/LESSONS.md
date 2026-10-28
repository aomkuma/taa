# What the ledger supports

Only what the trades show, with the trade numbers that show it. Nothing from a single trade.

## 1. The structure AT the level decides whether the level holds (owner, 2026-10-28)

Asked how you know whether a level will hold or break, the owner: *"the price structure at the level, of
course - the chart pattern together with HH/HL and LH/LL."*

Checked against every filled trade so far, by labelling the last two swing highs and lows in the six hours
before each decision (confirmed swings, three bars either side, nothing after the decision):

| | trades | R total | R a trade |
|---|---:|---:|---:|
| **with** the structure at the level | 4 | +0.57 | **+0.14** |
| **against** the structure at the level | 4 | -4.08 | **-1.02** |

The four taken against it - #5, #13, #15 and #1 - **all lost, every one a full stop, no exception.** The
only winner, #3 at +3.67 R, was with it.

What "with it" means, exactly: buying a support needs **HH and HL together**, and selling a resistance
needs **LH and LL together**. My losing buy #1 had a higher low but a **lower high**: the second low at
4600 was above the 4583 sweep, so I read returning demand, while the high had fallen from 4770 to 4690 -
sellers still in control. The level broke within five minutes and price went 213 USD lower.

**The split is one trade wide.** A reviewer (Codex, 2026-10-28) put the knife in the right place: take
the single +3.67 R winner out of the "with" group and the remaining three make **-1.03 R each - the same
as the four that went against the structure (-1.02)**. So what the eight trades show is four full-stop
losses on one side, four trades on the other side of which three also lost a full stop, and one winner.

Stated honestly: **I noticed a split while looking back at eight trades and then named a rule that
explains them, and one large winner happened to land on the favoured side.** The groups may differ in
other ways, and the same person chose the trades and labelled them afterwards.

It is a hypothesis to test forward. It is not evidence that the rule earns +0.14 R, and this file should
not have implied it was.

**And the split cannot be reproduced from the files** (Codex, `RULES_REVIEW.md` X2): all eight trades carry
`?????????` in the ledgers, and which four were "with" and which "against" is written only in this
paragraph - #5, #13, #15 and #1 against; by elimination #3, #9, #19 and #23 with. The swings behind each
label are not recorded anywhere.

**Why this still says eight when the ledger holds nine fills.** The ninth, D2-1 of 2026-04-02, has
not been labelled with or against the structure, because at the moment of that decision price was not at
the level yet - the plan was written in mid-range and waited for the level to come to it. Labelling it
now, from the bars that followed, is the hindsight this section exists to warn about. It stays eight
until a decision is made at a level with the structure readable at the time.

## 2. The chart's left side has to go back far enough to hold the levels

Nine hours of M5 showed no level older than a morning, so every "level" was a shelf built minutes earlier.
On that chart I sold into a market that had just broken a week-long ceiling with nothing above it
(moment #13: the trade that was there paid +7.1 R in the direction I sold). The chart is now H1 over three
weeks above M5 over 33 hours, read top first.

## 3. A sampled moment is where I sit down, not where I trade

At moment #13, trading at the sampled bar meant buying a base that broke 40 USD within half an hour.
Waiting 210 minutes produced a real setup instead. At moment #1, the sampled bar had price in open space
between levels - 140 USD from the nearest - and the answer was to wait, not to hunt.

## 4. Waiting for a better price cost more than every losing trade (measured 2026-10-28)

The owner, after the first real-day trade missed its entry by 2.57 USD and the market ran through the
target: *"if price is really going to run the way we expect, it may never reach the spot we see - because
it is obvious and everyone sees it. We may have to leave some room."*

Every trade so far, scored twice: once at the entry I planned, and once at the price that was on the screen
when the decision was made, with the same stop and target.

| | R total | R a trade |
|---|---:|---:|
| the entries I planned | -4.53 | **-0.378** |
| taken at the price I saw | -2.60 | **-0.217** |

**Corrected 2026-10-28 (`RULES_REVIEW.md` C1, C3).** This table first said -1.49 and -0.124, a gap of
+0.253. Two faults in `score.py` made it: the clock started on a bar the reader had already seen, and for
#15 it rolled a whole day forward, scoring a Friday decision against Monday's bars; and the on-sight column
got 6 hours to resolve against the planned column's 4. Re-scored with both fixed, every trade:

**+0.161 R a trade**, and all of it - more than all of it - comes from the trades the plan never got into:

| # | planned | on sight | missed by |
|---|---:|---:|---:|
| D1-1 | no fill, 0 | **+1.57** | 3.37 |
| 11 | no fill, 0 | **+0.82** | 3.85 |
| 17 | no fill, 0 | **+0.69** | 3.82 |
| 3 | +3.67 | +2.02 | - |
| 23 | -1.03 | -0.61 | - |
| 15 | -1.01 | -1.01 | - (was +0.99: the Monday bars) |

The three no-fills add **+3.08 R**; on the **nine filled trades, taking them at the price on the screen
was worse by 1.15 R** - the one winner shrinks more than the one time-closed loser saves.

**All three unfilled plans would have won - and that is close to true by construction.** A limit that
never fills is one where price left in the planned direction without coming back, so unfilled limits are
selected for winning on sight (`RULES_REVIEW.md` C2). The losers lost about the same either way. The
distances missed were **3.37, 3.85 and 3.82 USD** - D1-1 was 2.57 when measured from a bar already on the
screen - and the 4 USD cap sits just above the largest of three.

**Not a clean comparison**, and the file should say so: entering worse means a wider stop, so R per unit
shrinks - which is why the one winner falls from +3.67 to +2.02. Twelve trades, and three of the five
differences are the same kind of event. What it supports is a rule to test forward, not a conclusion.

**The rule now under test:** an order goes no further than **4 USD** from the price on the screen. Further
than that and the trade is taken at the market or not at all. Both columns are kept on every trade from
here (`at_decision_r`, `missed_by`), so the next fifty decide it.

## 5. The stop went inside the band, and that alone turned a winner into a loser (2026-04-02)

The owner's standing rule, from long before this folder existed: **a level is a band, not a line - the
target goes before the line and the stop goes beyond the band.** On real day 2 I wrote the plan myself and
then broke it.

The level was the 4550-4600 band that 31/03 built. The plan, written at 19:25 before advancing: buy
4600-4610, **stop 4586**, target 4698. 4586 is two dollars under a minor low and **inside the band**.
Price filled at 19:55, swept to **4580.86 at 20:20** - five dollars past the stop - and then ran to
**4699.44 at 21:40**, through the target.

The same idea, the same entry, the same target, scored three ways from the M5 bars:

| the stop | risk | result |
|---|---:|---|
| 4586, inside the band (what I wrote) | 19 | stopped at 20:20, **-1.02 R** |
| 4548, beyond the band | 57 | target at 21:40, **+1.63 R** |
| 4576, beyond the sweep, entering 4597 after the reclaim | 21 | target at 21:40, **+4.80 R** |

Nothing about the read was wrong. The level was right, the direction was right, the target was right and
it paid inside two hours. **Only the line I was willing to be wrong at was wrong**, and it cost the whole
trade.

The second half is worse. At 20:25, with price back at 4597 above the floor, I refused to buy because my
own written invalidation said that losing 4588 meant the level had failed. **The pattern I refused - a
sweep that closed back - is one of the four rule 5 names as the thing to look for.** I wrote an
invalidation that forbids a setup my own rules call valid.

Two trades now, not one, so this is still a handful: reset #1 bought a sweep-and-higher-low with the stop
beyond the sweep and lost anyway, because the high was falling. D2-1 refused the same shape and it paid.
What they agree on is narrower and worth carrying forward: **the invalidation line belongs outside the
band, and whether the setup is taken at all is rule 5's business, not the stop's.**

## 6. The window in which the method can act is narrow - and sometimes it is shut

Not a result about whether the rules are right. A result about **when they can be used at all**, which no
number in the ledger shows, because a window that produces nothing leaves no row there. Three cases, from
the six windows of the two real days (`sessions.csv` is the denominator):

| | what the market did | what the method could do |
|---|---|---|
| **01/04 New York** | broke 4700-4720, retested it at 19:50 and ran to 4788 | **Catchable** - every one of the nine rules held at the retest. The window was about **twenty minutes** wide, and it was AT the level. An hour later price was 16-19 USD above it and rule 7 shut the door |
| **02/04 Asia** | a triple top at 4798-4800 failed and price fell 148 USD in an hour | **Shut.** Rule 2 will not call an overnight ceiling a level, rule 4 refuses a sell against a live up leg, and rule 5 had no lower low - all three highs were equal. Then it went vertical with no retest |
| **02/04 London** | swept the 4550-4600 band and reclaimed, completing rule 5 in full | **Open, then shut by geometry.** By the time the structure completed, the level was 50 USD behind price and the nearest resistance gave under 1 R against a proper stop (conflict C) |

So of the six windows walked, **four produced no trade** - and they are not the same kind of nothing.
One, 01/04 Asia, simply had nothing in it and refusing cost nothing. In **two** the market made a move of
more than a hundred dollars that the rules could not take. In one the rules did authorise a trade and I
was not there for it.

The 01/04 New York case says the rules do find real trades; the other two say the finding has to happen
**at the level, within about a twenty-minute window**, or it is not a trade at all.

Six windows is a handful and this is an observation, not a verdict. What it changes now is what gets
recorded: `sessions.csv` has a **`reach`** column, and every window is marked `no-setup`, `shut`,
`open-missed` or `open-taken` (defined in METHOD 2c), so that after thirty windows this is counting rather
than impression. The standing so far: **2 `shut`, 1 `open-missed`, 2 `open-taken`, 1 `no-setup`** - but the one `open-missed` is 01/04 New York, the window marked excluded, so the count that belongs in the denominator is **5 windows: 2 `shut`, 0 `open-missed`, 2 `open-taken`, 1 `no-setup`** (corrected 2026-10-28, `RULES_REVIEW.md` C10; `score.py summary` now leaves excluded windows out). And `shut` is written after the move is seen and with no priced trade behind it, so it records a move the rules refused, not what a trade there would have earned (`RULES_REVIEW.md` X1).
