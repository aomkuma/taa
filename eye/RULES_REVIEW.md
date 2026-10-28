# Weaknesses in the nine rules - a review, 2026-10-28

The owner asked for the holes in the current rules, found together with Codex. Two readers worked apart:
**Claude's findings were written and committed to this file before Codex's answer was opened**, so the
second list could not shape the first. Codex ran read-only (`codex exec --sandbox read-only`, prompt piped
on stdin - the fix for `TRIED.md` row 14) on the live files.

## 1. Claude's findings (written before reading Codex)

| # | Weakness | Evidence | How much it matters |
|---|---|---|---|
| C1 | **`score.py` starts the clock on the wrong bar, and for #15 on the wrong day.** `decided_at` is the `Now` label of `walk.py` - the open time of the last bar *already seen*. `decided()` treats it as the first bar to score from, so every walked decision includes one bar the reader had already seen. Worse: when that label is earlier than the sampled cut-off (#15: decided 20:25, cut-off 20:30) the code adds a day | #15 was decided Friday 06/03 20:25 and scored from **Saturday 07/03 20:25** - its fill, `09/03 05:05`, is Monday morning, outside a 2-hour fill window. Re-scored from the first unseen bar (Friday 20:30): planned **-1.01** (unchanged by coincidence), on sight **-1.01, not +0.99**. D1-1 on sight +1.00, not +1.08 | **Largest.** The on-sight column falls from -1.49 R (-0.124 a trade) to **-3.57 R (-0.298)** against planned -4.53 (-0.378). The gap that justified rule 7's 4 USD cap shrinks from **+0.253 to +0.080 R a trade**, and #15 - one of the five differences in `LESSONS.md` 4 - was never a difference |
| C2 | **"All three unfilled plans would have won" is mostly mechanical.** A limit that never fills is, by construction, one where price left in the planned direction without coming back. Unfilled limits are selected for winning on sight; filled ones are selected against | `LESSONS.md` 4. After C1 the whole remaining gap (+0.080) is those three trades | The cap is fitted to three points: **4 USD sits just above the largest miss, 3.85.** It is a hypothesis built from the selection effect of limit orders, not evidence that market entries pay |
| C3 | **The two columns get different time.** On sight resolves over `FILL_BARS + LIVE_BARS` = 72 bars (6 h) from the decision; planned gets 48 bars (4 h) from the fill | `score.py` `score()`. D1-1's target came at 22:40, 7 h 45 after the decision - on sight it was closed at 6 h in profit; planned would have closed at 4 h | Biases the comparison toward the on-sight column. Small in R, but it is in the one comparison rule 7 rests on |
| C4 | **Rules 1 and 6 can never decide anything.** `walk.py` always draws H1 above M5; `score.py` always exits on M5 | `rules.py`: both are `+` on every judged trade, by construction | By the owner's own test ("a rule that never once decides anything is guilty - of not being a rule") they are protocol, not rules. **There are seven decision rules, not nine** |
| C5 | **Rules 5 and 7 together permit one shape only.** HH + HL at a support means price has already made a higher high off the level - at least one full M5 swing away. In April's market an M5 swing is tens of USD, far beyond 4. So the only entry both rules allow is the *second* test: the higher low coming back into the level after the higher high | The one window where all nine held (01/04 New York, 19:50) was exactly that - a second retest. 02/04 London died for exactly the opposite reason: structure complete with the level 50 USD behind | Sharper than predicted conflict D: not "sometimes they fight" but **"the rule set is one setup"** - break-and-retest / second test. Anything else is refused by logic, so `shut` will dominate in fast markets |
| C6 | **The 4 USD cap is in dollars while the risk ranges 7x.** Control stops were 7-13 USD; a stop beyond the 4550-4600 band is 57 | `ledger_control.csv`, `LESSONS.md` 5 | 4 USD is **0.3-0.6 R** on a February trade and **0.07 R** on the April band trade. The same rule means different things in different markets. Stated as a fraction of the planned risk it would not |
| C7 | **Rule 9's target contradicts the owner's band rule.** Rule 9: "the target is a full leg away - the next level from the left". The owner's standing rule: the target goes *before* the line. Rule 9 also offers two targets (a leg, or a level) and lets the reader pick | D1-1 used a leg (77); D2-1 used the shelf itself, 4698 - price reached **4699.44, 1.44 USD to spare**. The +1.63 and +4.80 counterfactuals in `LESSONS.md` 5 stand on that 1.44 | A target before the band would have been hit sooner, so the lesson survives - but the rule as written invites targets at the line, where one dollar decides the trade |
| C8 | **The "+4.80 on the reclaim" uses a stop chosen after the sweep was seen.** Stop 4576 "beyond the sweep" needs the sweep low (4580.86) to be known | `LESSONS.md` 5, third row | The beyond-the-band stop (4548) is pre-definable and clean; the reclaim row is hindsight and should not be quoted as a number the rule earns |
| C9 | **The walking step is coarser than the opportunity.** The handoff walks in steps of 12 bars (60 min); `LESSONS.md` 6 measured the catch window at about 20 minutes, at the level | `HANDOFF.md` "Where it resumes"; `sessions.csv` steps 2-5 per window | A 20-minute window seen once an hour is missed about two times in three **by the protocol, not the rules**. Some `shut` and `open-missed` may be the step size. The step is not recorded per look |
| C10 | **`reach` counts a window the docs say is excluded, and `shut` is labelled after the reveal.** `score.py summary` counts 01/04 New York (marked contaminated, excluded) as the one `open-missed`. And `shut` - "a real move happened" - can only be written once the move is known | `sessions.csv` row 3; `score.py` `windows()` | Clean count is **5 windows: 2 shut, 0 open-missed, 2 open-taken, 1 no-setup**. The same reader who did not trade the window decides whether it was the rules' fault or nobody's |
| C11 | **Ids collide.** `ledger.csv` id `1` (the reset trade), `ledger_control.csv` id `1` (a moment stood aside) and `moments.csv` id `1` are three things; `score.py` finds the reset trade's clock through the moment's id | `score.py` `start_of()` | Works today by accident; "#1" in `LESSONS.md` is ambiguous |

**What I expect from Codex, written before opening it:** it will repeat C5 (rules 5 vs 7), will probably
find the horizon asymmetry (C3), may or may not catch the day-roll bug (C1) since it needs the moments
file and a careful read of `decided()`; and it will add points about the definitions of "leg" and
"level" that are already in the known review table.

## 2. Codex's findings (opened after section 1 was committed, 0ecf0fe)

The first run stopped at its first finding - correctly, because **my prompt said `ledger_control.csv` had
10 rows and it has 12** (9 trades and 3 stand-asides; the "10 control trades" are those 9 plus the reset
trade in `ledger.csv`). The prompt was corrected and the run repeated. The log shows it did not open this
file. Its full answer is summarised here; what it found that section 1 did not is marked **new**.

| # | Codex's finding | Against section 1 |
|---|---|---|
| X1 | **`shut` records a refused move, not a lost trade.** No entry, stop or target is written for the 02/04 Asia sell, so "148 USD" says nothing about what a rule-compliant trade would have earned - and `shut` can make the method look worse than any measured trade does | **New.** Extends C10 |
| X2 | **The structure split in `LESSONS.md` 1 cannot be reproduced from the CSVs** - all eight trades carry `?????????`; which four were "with" lives only in prose | **New.** The only rule with evidence has none in the record |
| X3 | Rule 7 against 5 and 9 at 02/04 London: confirmation came 50 USD from the level, stop 59, target 56 | Same as C5, and predicted conflict C - C5 adds that 5 and 7 together allow only the second test |
| X4 | Rule 9's target ("a full leg" or "the next level") lets a reader admit or veto the same setup | Same as C7 |
| X5 | Rule 2 has no minimum age or test count; "earlier days built" depends on how far left the reader looks | Already in the known review table (rules not defined); X5 adds the case: it is what refused the 148 USD sell |
| X6 | Rules 4 and 5 can be counted at different swing scales and then reinforce or contradict each other | Known (no definitions) |
| X7 | Rule 3 is a trigger to look, not a rule - TRIED's own conflict A says so | Close to C4: by the owner's test it decides nothing alone |
| X8 | **The on-sight column resolves over 72 bars, not 48**, and it keeps the planned stop, so R is measured on a different unit | Same as C3. Did **not** find C1 (the clock / day roll): it checked that +0.253 was reproducible from the stored fields, not that the fields were right |
| X9 | Rule 8's "while the idea is still intact" turns on an invalidation the same reader picks | Known as TRIED row 16 |
| X10-11 | Rules 1 and 6 are display and protocol, not rules | Same as C4 |
| X12 | `reach` is self-assigned and outcome-aware | Same as C10 |

**Codex's three changes:** (1) freeze a decision record at **every step** before advancing - price, side or
no trade, the level band, the swing points, each rule pass/fail, entry/stop/target/invalidation - never
revised after later bars; (2) replace `reach` with a candidate trade priced **before** the window's later
bars are revealed, so `shut` gets a number; (3) score the on-sight column on the same 4-hour clock, and add
a fixed-dollar-risk result beside R.

**My expectation against what came** (written in section 1 before opening): C5 repeated - yes (X3); C3
found - yes (X8); C1 missed - **it was missed**; definitions of "leg" and "level" - yes (X5, X6). What I did
not expect: X1 and X2, both real.

## 3. What was corrected the same evening

| Finding | Done |
|---|---|
| C1, C3 | `score.py`: the clock starts at the first bar not yet on the screen (`Now` + 5 min), no day roll unless the walk went past midnight; the on-sight column gets 48 bars. Every trade re-scored. Changed: #15 fill Friday 06/03 20:30 (was Monday 09/03), on sight -1.01 (was +0.99); D1-1 missed by 3.37 (was 2.57), on sight +1.57 (was +1.08); #23 on sight -0.61 (was -1.01, the extra 2 hours reached its stop). **Planned unchanged at -4.53 R (-0.378). On sight -2.60 R, -0.217 a trade (was -0.124). Gap +0.161 (was +0.253)** - not the +0.080 estimated in C1, which still had the 72-bar horizon. The three no-fills give +3.08 R; on the nine fills on sight was worse by 1.15 R |
| C10 | `score.py summary` leaves out windows marked excluded: 5 windows, 0 `open-missed` |
| X2 | `LESSONS.md` 1 now names the four "with" trades and says the labels are not in the record |
| Numbers | corrected in `LESSONS.md` 4 and 6, `TRIED.md` (a dated note under the table; rows left as written), `SHEETS.md` (a note under the D1-1 score), `sessions.csv` row 3, `METHOD.md` rule 7, `START_HERE.md`, `HANDOFF.md` |

**Not changed, because they change the rules and the rules are the owner's to direct:** C5, C6, C7, C9, X1
and Codex's changes (1) and (2). They are the agenda.

## 4. Every entry picture, read again (owner's question, 2026-10-28 17:00 Thai)

The owner, after looking at every chart in `eye/`: *"the price structure was not one to enter at all - how
do we fix it?"* Read from the decision charts (deleted from the tree at the owner's word, 10-28; in git at 937f75a: `eye/walk/001_054`, `013_042`, `015_000`,
`2026-04-01_0700_096`, `2026-04-02_1930_000`) and the two sampling sheets (`eye/sheets/claude_01`,
`claude_02`, nine hours of M5 only). **Hindsight: the outcome of every trade was known while labelling.**

| # | side | the picture at the decision | label | R (on sight) |
|---|---|---|---|---:|
| 1 (reset) | BUY 4615 | H1 fell 5590 -> 4600 in three days; M5 a staircase down, every high lower, no HH | VERTICAL / down | -1.01 |
| 5 | BUY 5058 | a 5030-5065 chop, bought near its top | CHOP | -1.03 |
| 9 | SELL 5033 | a 5005-5040 chop | CHOP | -1.04 |
| 13 | SELL 5370 | a week's 5150-5250 range left by a weekend gap to 5390, the pullback holding a higher low | FRESH BREAK, sold against it | -1.03 |
| 15 | SELL 5098 | price 5083 near a 5055-5065 floor held since the day before; the next bar was 20:30 Thai on the first Friday of March - the usual US jobs slot (my reading of the date; no calendar in the repo) - and moved 43 USD in five minutes | NEWS | -1.01 |
| 19 | BUY 5016 | a vertical drop to 4975 and a V back in 30 minutes, bought straight after the long bar | VERTICAL | -1.03 |
| 23 | SELL 4557 | a top, a distribution, a breakdown swept to 4535, sold on the retest; only one lower high | not TREND (nearest to acceptable) | -1.03 |
| D2-1 | BUY 4605 | 4800 -> 4555 with lower highs 4700, 4650; bought before any HH | down TREND, bought against it | -1.02 |
| **3** | BUY 4902 | a clear up staircase, higher lows, bought on the pullback to the base of the surge | **TREND pullback** | **+3.67** |
| **D1-1** | BUY 4707 | H1 recovering from 4100; M5 a new HH at 4747 and the pullback into the broken 4700-4720 | **TREND pullback** | no fill (**+1.57**) |
| 11 | SELL 5201 | a run up, a top at 5210, then flat at 5190 | CHOP | no fill (+0.82) |
| 17 | SELL 5206 | a double top at 5220 and a slow bleed; highs not cleanly lower | not TREND | no fill (+0.69) |

**What it shows, and what it does not.** The two TREND pullbacks are the two best outcomes in the record.
Seven of eight losers sit in a picture with a name for why not. But #11 and #17 are not TREND pictures and
would have won on sight, so "not TREND" is not the same as "loses". Twelve trades, one reader, labelled
after the results. `METHOD.md` 2d was built on this table; the owner set it aside as not their way, and the
work holds to their principle instead - structure + divergence + counting the peaks (`METHOD.md` 2e).

## 5. Review of METHOD 2e and its tools (2026-10-28 evening) - Claude's half, written before Codex's was opened

The owner asked for what was written today to be reviewed again and checked by an agent. Codex runs
read-only on the same files in parallel; this half is committed first.

| # | Finding | Evidence | Fix |
|---|---|---|---|
| M1 | **[CODE] `score.py` fills every SELL as a sell limit (`high >= entry`) and every BUY as a buy limit.** 2e's entry is a *break*: a sell stop under price. Scored as written, a 2e sell would fill on the first bar whose high is above the entry - at once, before price ever broke down | `score.py` `score()`: `hit = first[(first.low <= entry) if buy else (first.high >= entry)]` | Fill when price trades **through the entry from the side it was on at the decision**: entry under the price on the screen fills on `low <= entry`, entry above it on `high >= entry` - right for limits and stops alike. **Must be fixed before day 3** |
| M2 | **[MISLEADING] The live documents still say the setup is open.** HANDOFF's prompt for the next session and "Where it resumes" step 1 tell it to ask the three questions; HANDOFF's "The principle" paragraph says the oscillator call is "not yet made"; START_HERE says how divergence is read is "not yet written" and that day 3 waits for it; CLAUDE.md says the details are "the owner's to state - ask" | the files as they stand | Rewrite them to: the setup is answered (2e), day 3 is next |
| M3 | **[OWNER-FIDELITY] Three things in 2e are mine, not the owner's, and are not all marked:** "one oscillator diverging is a divergence; both is a stronger one"; "hidden divergence is not part of this"; "a buy at support in an H1 down trend is not this setup" (it follows from the owner's "at support when the buy side has the edge", but the words are mine) | 2e, the divergence paragraph and "What Claude understands" | Mark each as Claude's reading |
| M4 | **[CONSISTENCY] The timeframe the 3-5 peaks are counted on is not stated.** The owner gave the entry timeframe (M5-M15); the example has 3 peaks on M15 and 4 on M5 | 2e, the example's table | Write it as open, or as "the entry timeframe" marked as Claude's reading |
| M5 | **[CONSISTENCY] `TRIED.md` has no row for the owner's method** - the method now being run has no verdict line | `TRIED.md` | Add row 18, UNPROVEN |
| M6 | **[CONSISTENCY] The nine rules and 2e.** Rule 9's target ("a full leg away, the next level") differs from 2e's ("just before the opposite level"); 2e says it wins where they contradict, but the ledger's `rules` column would still judge a 2e trade by rule 9. Rule 7's 4 USD cap is compatible: the entry is at the market on the break | METHOD bottom; `rules.py` | The `steps` column (2e action 2) is what a 2e trade is judged by; say so |
| M7 | **[CODE] `walk.py`'s dashed ZigZag leg can start from an older pivot than MT5 shows.** `zigzag_pivots` leaves out a pivot until `backstep` bars have printed after the opposite candidate, so in the last few bars the dashed leg may start one pivot early | `chart_read.py` `zigzag_pivots`: `if s + backstep < n: out.append(...)` | Compare with MT5 live on day 3; not a look-ahead (it shows less, never more) |
| M8 | **[CODE] Holding without a limit scans to the end of the stored data**, and a trade still open there is closed at the last close and marked `open (data ends)` - right, but it must not be counted as a result | `score.py` `resolve()` | Exclude `open (data ends)` from the totals |
| M9 | **Checked: the H1 picture behind the owner's example fits "what Claude understands".** Over the three weeks before it the H1 highs fell 4217 -> 4200 -> 4198 -> 4155 -> 4142 -> 4034 -> 4029.83 and price went 4144 -> 4049; the top 4070.76 sat in the 4066-4073 band of the 07/10 and 14/10 lows - a resistance from the left. **But** the rally 3989 -> 4070 had broken the H1 lower high 4034, so whether H1 was still "down" at the entry is a judgement - the place where a reader's bias enters | H1 ZigZag 12/5/3 on the stored bars | Nothing to change; it is the judgement 2e already names |

## 6. Codex's half of the 2e review, and what was done (2026-10-28 evening)

Opened after section 5 was committed (666e692). Codex ran read-only with the prompt on stdin; its log shows
it did not open this file or the archive. What it found, against section 5:

| # | Codex's finding | Against section 5 | Done |
|---|---|---|---|
| K1 | **[MISLEADING]** HANDOFF and START_HERE still say the owner's answers are awaited and tell the next session to ask | Same as M2 | HANDOFF rewritten; START_HERE and CLAUDE.md say the setup is answered and is not to be asked again |
| K2 | **[OWNER-FIDELITY]** Claude's interpretations read as the owner's: the "adds nothing" sentence changed the divergence wording; the principle says "MACD, RSI **or price**"; steps 3-5 and "What Claude understands" add detail the owner did not give | Wider than M3 | The sentence matches the table; divergence is "MACD or RSI against price"; steps 3-5 are labelled Claude's generalisation of the example; Claude's readings in the divergence paragraph and the H1 inference are labelled |
| K3 | **[CONSISTENCY]** Section 4 still prescribed the 4-hour close and called it open | **New** - section 5 missed it | The 48-bar rule is struck through and marked superseded; the fill-through rule added |
| K4 | **[CONSISTENCY]** Entry on M5-M15 against "enter on M5, exit on M5" and an M5-only scorer | **New** | Written: rule 6 stands for reading; a fixed stop and target are scored on M5, the finest frame shown, whichever frame the trade was read on |
| K5 | **[CONSISTENCY]** Rule 4's "three or four legs, trade the fifth" not reconciled with 2e | **New** (M6 covered rules 7 and 9 only) | Written: 2e replaces rule 4's count and entry, and rule 9's target and stop; rules 1-3, 5-8 stand |
| K6 | **[CONSISTENCY]** The action table said "ready once the two open answers are in" under a line saying nothing is open | **New** | Fixed: ready once the `steps` column and the fill fix are done |
| K7 | **[CODE]** A trade open when the stored bars end gets an R | Same as M8 | Now `open`, blank R, left out of every total and of `rules.py`, scored again when there are more bars |
| K8 | **[CODE]** `at_decision_r` and the planned trade start at different times, so the gap is not entry price alone | Partly C3 | Noted; the column's meaning stands as "the same idea taken at the price on the screen" |

**Codex did not find M1** - every sell filled as a sell limit, so 2e's entry on the break (a sell stop
under price) would have filled before the break. It checked that `LIVE_BARS = None` reached both paths,
not which way an order fills. **Fixed:** an order fills when price trades through the entry from the side
it was on. Shown on the owner's example: an order placed at 08:15 Thai filled at 08:20 under the old rule,
with price never under 4055, and at 08:30 - the bar that broke it - under the new one. The twelve stored
trades re-score identically (fill, no-fill and miss distance, all twelve).

**Section 5 found what Codex did not: M1, M4 (the counting timeframe - now written as the entry timeframe,
Claude's reading), M5 (TRIED row 18 - added), M9 (the H1 check). Codex found K3-K6, which section 5 did
not.** Two readers apart caught nine faults neither caught alone.

**Still to do:** the `steps` column (METHOD 2e row 2); MACD and RSI against the owner's MT5.
