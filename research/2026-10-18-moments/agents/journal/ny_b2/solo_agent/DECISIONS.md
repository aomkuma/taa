# The solo exam of the NY-B2 journal - decisions, week by week

Protocol: `PROTOCOL.md`. Code: `solo_lib.py` (loaders, state, exits, rules), `solo_week.py N` (runs week N under the
state in force, appends `ledger.csv` / `weeks.csv`), `solo_review.py N [--apply ...]` (the evidence and the decided
changes, effective from week N+1), `solo_look.py N` (sessions / NY H1 bars of the week), `solo_md.py N` (the week's
tables), `pieces.py gate NAME END` (gates 1 and 2 for a candidate piece). A week = Saturday 00:00 .. Saturday 00:00
UTC, so a week's review sees Friday's closed D1 bar and nothing later.

Three lines are kept: **realized** (the state in force each week), **no-learning** (PROTOCOL.md's start state
unchanged every week; coordinator's requirement of 2026-10-23), **base** (the bot's B2 as is). Accounts: 100 USD at
7.5 % and 300 USD at 3 %, equity sizing, at least 0.01 lot. Note on sizing: at these balances the 0.01-lot minimum
is larger than 7.5 % / 3 % for almost every stop (a 10-42 USD stop is 10-42 USD at 0.01 lot), so both accounts lose
and win the same USD per trade until the 300 account grows; the 100 account is the fragile one.

Interpretation fixed before week 1: the three start rules' forward record is counted from exam week 1 (PROTOCOL:
"exam weeks for the three start rules"). The alternative reading (adding the learning journal's forward record:
near +1.86, news +0.75, vol -1.05) is printed in every review beside it.

## Exam week 1 - 2026-04-20 .. 04-24

D1: Mon 20 Apr 4774->4820 (hi 4828 lo 4737, body +0.29 ATR); Tue 21 Apr 4824->4717 (hi 4833 lo 4668, body -0.72 ATR);
Wed 22 Apr 4725->4739 (body +0.10); Thu 23 Apr 4742->4690 (hi 4754 lo 4664, body -0.39); Fri 24 Apr 4695->4708
(hi 4740 lo 4658, body +0.11). D1 ATR(20) 158 -> 127 (falling).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 20 20:30 | B2 | BUY | M5 | 4824.64 | 42.0 | -0.26 | -0.39 | -0.39 | -0.39 |  |
| Tue 21 20:40 | B2 | BUY | M1 | 4784.62 | 18.4 | -0.63 | -1.00 | -1.00 | -1.00 |  |
| Thu 23 20:41 | B2 | BUY | M1 | 4733.82 | 10.4 | -0.91 | -1.00 | -1.00 | -1.00 |  |
| Thu 23 21:24 | B2 | BUY | M1 | 4729.05 | 10.7 | -0.24 | +0.49 | - | - | news |
| Thu 23 22:18 | B2 | BUY | M1 | 4737.07 | 11.6 | -0.77 | -1.00 | -1.00 | -1.00 |  |
| Fri 24 20:32 | B2 | SELL | M1 | 4692.49 | 13.6 | -0.86 | -1.09 | -1.09 | -1.09 |  |
| Fri 24 22:35 | B2 | SELL | M1 | 4718.30 | 8.5 | -1.00 | -1.01 | - | - | near |

Realized: 5 trades (0 won / 5 lost) -4.49 R -> 100 USD account **28.38**, 300 USD account **228.38**. No-learning:
identical. Base: 7 trades -4.67 R -> 36.28 / 236.28. No re-test signal (no strong D1 bar: Tuesday's body 0.72 ATR).

**What the market did.** A falling week inside a big range (4,833 -> 4,658), the D1 ATR shrinking. Tuesday was the
one clear move: Asia -40, a flat London, then NY -84 in two H1 legs (21:00 Thai -40, 23:00 Thai -30, each closing
near its low on 2x volume). Thursday and Friday NY were two-way chop of 20-25 USD bars.

**What we did.** B2 bought four times into the falling week (all with the D1 / H4 structure against: score -2/-3,
the "turn before the big frames turn" that paid in learning) and lost every one; Friday's two sells came after the
week's low as the price bounced. **What a trader would have done**: Tuesday NY, sell the break of the London low
(4,773) or the second leg after 21:00 Thai's -40 bar; Thursday / Friday, stay out of the NY chop.

**Observer's measurement** (the with-the-move trades the week showed, gates on data before 2026-04-25, M1 bars,
0.37 USD cost, the journal's exit shape):

| Candidate | Old years 2023-09..2025-09 | Test half 1 (2025-10..) | Test half 2 (..2026-04-24) | Gates |
|---|---|---|---|---|
| NY cash-open range breakout (09:30-09:45 NY range, first M1 close beyond it) | -0.058 on 494 | -0.197 on 65 | +0.002 on 66 | fail / fail |
| strong NY H1 bar (body >= 0.8 H1 ATR, close in the outer 25 %), next bar with it | -0.038 on 385 | -0.154 on 47 | +0.066 on 47 | fail / fail |
| one-way day at 20:30 Thai (day move >= 0.6 D1 ATR, close in the outer 25 %), with it | +0.034 on 96 | +0.190 on 11 | -0.413 on 12 | fail / pass |

None passes. Tuesday's move is the kind of day that is clear afterwards; the simple with-the-move entries on it have
no edge over three years.

**Review (`solo_review.py 1`).**
- Skip rules (exam forward): vol 0 on 0; near -1.01 on 1 (saved); news +0.49 on 1 (cost). None above +1.0: all kept.
  (Alternative reading: news +1.24 -> it would be deleted; near +0.85, vol -1.05.)
- Exits over all B2 trades: the current exit -5.01 this week, +3.18 over all 105; no candidate beats it by 1.5 R.
- **Pieces: B2's exam-forward realized record is -4.49 R, below -3 R -> B2 is stopped from week 2** (PROTOCOL:
  "a piece is stopped when its exam-forward record falls below -3 R; it can come back only through the gates").
  Its signals stay in the ledger with every exit and rule, as its record. For its return: gate 1 on its own data
  (learning + exam, realistic exit) is +0.083 a trade unfiltered over the learning weeks, below +0.10 already, and
  gate 2 cannot be run (the bot's trades exist only from 2025-10); I will re-check gate 1 on B2's whole record
  each week and write it.
- The re-test piece: no trade yet; stays.
- No shadow started: with B2 stopped, a skip rule on it has nothing to save; the week's lesson is about the missing
  with-the-move piece, which was measured above and failed.

From week 2 the realized line trades the re-test piece only (plus any piece that passes the gates).

## Exam week 2 - 2026-04-27 .. 05-01

D1: Mon 27 Apr 4697->4679 (body -0.14 ATR); Tue 28 Apr 4683->4596 (hi 4701 lo 4555, -0.75); Wed 29 Apr 4598->4542
(lo 4510, -0.48); Thu 30 Apr 4540->4621 (hi 4647, +0.74); Fri 01 May 4630->4616 (hi 4660 lo 4560, -0.12).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 27 20:50 | B2 | SELL | M1 | 4689.74 | 14.1 | -0.47 | +1.04 | - | +1.04 | stopped |
| Mon 27 21:31 | B2 | SELL | M1 | 4686.99 | 10.9 | +0.50 | +0.96 | - | +0.96 | stopped |

Realized: 0 trades -> 100 USD **28.38**, 300 USD **228.38**. No-learning: 2 trades (2 won) +2.00 R -> 53.57 / 253.57.
Base: 2 trades +0.03 R -> 35.07 / 235.07. No re-test (no strong D1 bar: the largest body was 0.75 ATR).

**What the market did.** The fall went on to Wednesday (4,701 -> 4,510; Tuesday's London -70 was the leg), then
Thursday turned up from 4,540 (+0.74 ATR, London +68) and Friday's NY ran +60 after London had dropped 26. NY
reversed London's move on Tue (lows 4,555 held with 17-USD lower wicks on 2x volume), Wed (the 4,510 low at
20:00 Thai, then +17/+8 bars) and Fri. **What we did**: nothing; the stopped B2 sold twice on Monday with the fall
and both paid (+2.00 R under the exit). Stopping B2 cost 2.00 R this week against the no-learning line.
**What a trader would have done**: sell London on Tuesday with the fall; on Wednesday / Friday buy NY's turn of
London's move at the day's extreme.

**Observer's measurement** (gates on data before 2026-05-02):

| Candidate | Old years | Test half 1 | Test half 2 | Gates |
|---|---|---|---|---|
| London breaks the Asia range (first M15 close beyond it 13:00-17:00 Thai, stop the range's middle, out 19:00) | -0.010 on 355 | +0.066 on 30 | +0.063 on 30 | fail / fail |
| NY turns an extended day (day >= 0.6 D1 ATR by 20:00 Thai, an M15 rejection bar at a new extreme 20:00-23:00) | +0.039 on 36 | -0.523 on 5 | +0.441 on 6 | fail / pass |

A bug caught on the way: the first version of both used the Thai hour to cut the server day, which also took the
00:00-04:00 Thai bars at the day's END into "before 20:00" (a look-ahead); the NY-turn candidate then passed both
gates (+0.257 on 28 old). Fixed (`pieces.thai()`: a Thai clock time on the server day, bars closed before it);
it fails. No exam data was involved (gates read data before the week's end only).

**Review.** Rules: vol 0 on 0, near -1.01 on 1, news +0.49 on 1 (all kept). Exits: hold-90 +0.22 vs the current
over the exam weeks, -1.51 over all: no switch. B2 (stopped): +2.00 on 2 since stopped. **B2's return, decided
now before it can pass:** gate 1 on its whole record with the rules in force (half 1 +0.384 on 27, half 2 +0.091 on
27 -> fail by 0.009); gate 2 cannot be run on 2023-25 (the bot's B2 trades exist only from 2025-10), so for B2 alone
gate 2 is replaced by "positive over learning part 1 (2025-10-20 .. 2026-01-16)" - a deviation from PROTOCOL.md,
written before the result is known. No change for week 3.

## Exam week 3 - 2026-05-04 .. 05-08

D1: Mon 04 May 4625->4521 (lo 4501, body -1.02 ATR, a strong down day); Tue 05 May 4520->4555 (+0.34); Wed 06 May
4552->4691 (hi 4723, **+1.37**, a strong up day: Asia +111); Thu 07 May 4690->4695 (hi 4765, +0.04); Fri 08 May
4693->4715 (+0.22).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Tue 05 20:44 | B2 | SELL | M1 | 4572.04 | 13.4 | -0.78 | -1.03 | - | -1.03 | stopped |
| Tue 05 22:41 | B2 | SELL | M1 | 4574.50 | 9.6 | +1.82 | +1.14 | - | +1.14 | stopped |
| Thu 07 14:15 | re-test | BUY |  | 4749.48 | 38.5 | - | -1.01 | -1.01 | -1.01 |  |

Realized: 1 trade (lost) -1.01 R -> **the 100 USD account is blown in week 3 (-10.55: a 38.5 USD stop at the 0.01-lot
minimum)**; 300 USD **189.45**. No-learning: 3 trades (1/2) -0.90 R -> 11.84 / 211.84. Base: 2 trades +1.04 R ->
42.04 / 242.04. (From week 3 the account replay stops a blown account: no more trades, balance carried.)

**What the market did.** Monday fell all day (-26 / -39 / -50 by session) to a strong down bar; Tuesday did not break
its low (4,501; low 4,514), so no re-test sell. Wednesday reversed it in Asia (+111) to a strong up bar; Thursday's
London broke Wednesday's high (4,723) to 4,753, the re-test buy came at 14:15 Thai at 4,749 with the stop under the
re-test swing (38.5 USD) and NY took price back to 4,704: stopped. Thursday-Friday was a 4,682-4,765 range.
**What a trader would have done**: Wednesday's Asia run was the move (no piece trades Asia); on Thursday a trader
buying Wednesday's breakout would have taken profit at the London high, not held into NY.

**Observer's measurement**: the D1 side's pullback bought / sold in NY (a D1 side = the close beyond its 20-day mean
and 5 days moved >= 0.5 ATR; price against the side at 20:00 Thai; the first M15 close beyond the previous bar's
extreme 20:00-22:30): old -0.044 on 148, test +0.077 on 21 / -0.114 on 22 -> fails both gates.

**Review.** Rules unchanged (vol 0 on 0, near -1.01 on 1, news +0.49 on 1). Exits: hold-90 +0.59 over the exam
weeks but -1.13 over all -> no switch. Re-test: -1.01 on 1 (stop at -3). B2 (stopped): +2.12 on 4 since stopped;
its return gate 1: +0.396 on 28 / +0.066 on 28 -> fail. No change for week 4.

## Exam week 4 - 2026-05-11 .. 05-15

D1: Mon 11 May 4685->4735 (+0.49 ATR); Tue 12 May 4741->4713 (hi 4773 lo 4638, -0.27); Wed 13 May 4720->4688 (-0.31);
Thu 14 May 4693->4651 (-0.42); Fri 15 May 4652->4538 (lo 4512, **-1.13**, a strong down day; Asia -94).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 11 22:01 | B2 | SELL | M1 | 4723.36 | 7.6 | -1.00 | -1.00 | - | - | stopped vol |
| Tue 12 21:00 | B2 | SELL | M5 | 4679.16 | 34.0 | -0.19 | +1.00 | - | +1.00 | stopped |
| Wed 13 20:39 | B2 | SELL | M1 | 4675.31 | 19.9 | -0.43 | -1.00 | - | -1.00 | stopped |

Realized: no trade -> 100 USD **-10.55 (blown, week 3)**, 300 USD **189.45**. No-learning: 2 trades (1/1) 0.00 R ->
25.86 / 225.85. Base: 3 trades -1.61 R -> 19.62 / 219.62.

**What the market did.** A drift down from Tuesday's 4,773 high, four days of shrinking ranges (Wed-Thu 50-60 USD), then
Friday's Asia broke it: 07:00-08:00 Thai -22 / -16 on 2x volume, 12:00 Thai -47.5 (the London pre-open) to 4,557 and
4,512 in NY. Second week in a row that the week's biggest move happened in Asia (Wed 6 May +111 from 05:00 Thai in
three +21/+21/+25 H1 bars). **What a trader would have done**: sell Friday's break of the four-day range low
(~4,644) in Asia; join a clean three-bar Asia run.

**Observer's measurement**: the Asia-open run (the first 3 H1 bars move >= 0.25 D1 ATR, 2 of 3 bars that way, the 3rd
closing in the outer 30 %; enter at the 4th bar, stop the 3 bars' middle, out 13:00 Thai): old -0.087 on 51
(2023 -0.268, 2024 -0.225, 2025 +0.076), test +0.181 on 15 / +0.008 on 16 -> fails both. The two recent runs are the
2026 regime (2026 +0.173 on 19), not something the old years show.

**Review.** Rules: vol -1.00 on 1 (saved), near -1.01 on 1, news +0.49 on 1 -> all kept. Exits: hold-90 +0.96 over the
exam weeks, -0.77 over all -> no switch. Re-test -1.01 on 1. B2 since stopped +1.11 on 3 (+2.11 with the skip rules);
return gate 1: +0.408 / +0.038 -> fail. No change for week 5.

## Exam week 5 - 2026-05-18 .. 05-22

D1: Mon 18 May 4545->4563 (lo 4480, +0.17 ATR); Tue 19 May 4571->4482 (lo 4465, -0.86); Wed 20 May 4485->4543
(lo 4453, +0.57); Thu 21 May 4544->4542 (-0.03); Fri 22 May 4545->4507 (-0.37). A 4,453-4,589 range week.

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 18 08:15 | re-test | SELL |  | 4495.72 | 28.4 | - | -1.02 | -1.02 | -1.02 |  |
| Mon 18 21:41 | B2 | SELL | M1 | 4542.28 | 28.4 | -0.07 | -0.07 | - | - | stopped vol near |
| Fri 22 21:05 | B2 | SELL | M5 | 4507.89 | 29.5 | -0.60 | -0.39 | - | - | stopped news |

Realized: 1 trade (lost) -1.02 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **160.54**. No-learning: 1 trade (lost)
-1.02 R -> **its 100 USD account blown this week (-3.05)** / 196.95. Base: 2 trades -0.68 R -> -0.19 (blown) / 199.81.

**What the market did.** After Friday's strong down day the re-test sell came in Asia on Monday (08:15 Thai, 4,496,
below Friday's 4,512 low) - Monday's low 4,480 held and London took price back to 4,567: stopped. The week was a
range: lows 4,480 / 4,465 / 4,453 rejected each time, highs ~4,550-4,590. **What a trader would have done**: after a
strong day that runs into the old lows, wait for the range to show (it did by Monday London) and trade its edges.

**Observer's measurement**: a range's edge rejected (5 D1 bars span < 2.5 ATR; an H1 bar beyond the 5-day high / low
closes back inside with a wick >= 50 % of its range on above-median volume; enter against, stop beyond the wick,
4 hours): old -0.177 on 36, test -0.352 on 5 / +0.223 on 5 -> fails both.

**Review.** Rules: vol -1.07 on 2, near -1.08 on 2, news +0.10 on 2 -> kept. Exits: hold-90 +0.93 / -0.80 -> no.
Re-test -2.03 on 2 (stop at -3). B2 since stopped +0.65 on 5 (+2.11 with the rules); return gate 1 +0.408 / +0.038
-> fail. No change.

## Exam week 6 - 2026-05-25 .. 05-29

D1: Mon 25 May 4550->4570 (+0.19 ATR); Tue 26 May 4571->4506 (-0.63); Wed 27 May 4507->4455 (lo 4401, -0.53); Thu 28 May
4456->4496 (lo **4366**, hi 4516, +0.39: a V day); Fri 29 May 4498->4540 (hi 4595, +0.41).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Tue 26 20:45 | B2 | BUY | M5 | 4527.87 | 28.8 | -0.76 | -0.68 | - | -0.68 | stopped |
| Fri 29 20:49 | B2 | BUY | M1 | 4536.12 | 15.9 | -0.11 | +0.50 | - | - | stopped near |

Realized: no trade -> 100 USD **-10.55 (blown wk 3)**, 300 USD **160.54**. No-learning: 1 trade (lost) -0.68 R ->
-3.05 (blown wk 5) / 177.35. Base: 2 trades -0.87 R -> -0.19 / 176.14.

**What the market did.** Three days down (Tue Asia -44, Wed London -69, Thu Asia -68 to 4,366), then Thursday's NY
turned it: the 19:00 Thai H1 bar +44 (an engulfing close at its high), 21:00 +39 on 2.6x volume, 23:00 +28 - NY
+123 in five hours, and Friday carried on to 4,595. No B2 signal on Thursday. **What a trader would have done**: buy
Thursday's 19:00-20:00 Thai reversal of a three-day fall once the strong NY bar closed (the stop under it, ~20 USD).

**Observer's measurement**: NY reverses a run (2 D1 bars closed one way and the day already >= 0.3 ATR that way; a
19:00-21:00 Thai H1 bar against it with body >= 0.8 H1 ATR closing in its outer 25 %; with it at the next bar, stop
beyond the bar, 3 h): old -0.036 on 17, test +0.290 on 6 / -0.103 on 7 -> fails both. Thursday was a clear
picture afterwards; the rule that would have caught it has no record.

**Review.** Rules: vol -1.07 on 2, near -0.59 on 3, news +0.10 on 2 -> kept. Exits: hold-90 +0.97 / -0.75 -> no.
Re-test -2.03 on 2. B2 since stopped +0.47 on 7 (+1.43 with the rules); return gate 1 +0.408 / +0.014 -> fail.
No change.

## Exam week 7 - 2026-06-01 .. 06-05

D1: Mon 01 Jun 4521->4483 (-0.36 ATR); Tue 02 Jun 4482->4487 (+0.05); Wed 03 Jun 4491->4435 (-0.55); Thu 04 Jun
4432->4476 (+0.45); Fri 05 Jun 4474->4328 (lo 4312, **-1.50**, a strong down day, NY -126).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Tue 02 21:18 | B2 | SELL | M1 | 4494.29 | 20.7 | -0.57 | -0.09 | - | - | stopped news |
| Wed 03 20:45 | B2 | SELL | M5 | 4427.04 | 41.9 | -0.32 | -0.32 | - | -0.32 | stopped |
| Thu 04 21:00 | B2 | SELL | M1 | 4495.82 | 20.3 | +1.46 | +0.95 | - | - | stopped near |
| Fri 05 21:34 | B2 | SELL | M1 | 4349.84 | 21.3 | -0.78 | -1.00 | - | - | stopped vol |

Realized: no trade -> 100 USD **-10.55 (blown wk 3)**, 300 USD **160.54**. No-learning: 1 trade (lost) -0.32 R ->
-3.05 / 164.01. Base: 4 trades -0.21 R -> -0.19 / 163.84.

**What the market did.** A 4,426-4,546 range Mon-Thu (each session alternating), then Friday (the US jobs report,
08:30 New York = 19:30 Thai) broke it: the 19:00 Thai H1 bar -64 closing at its low, 20:00 -41, 22:00 -35 - NY -126 to
4,323. **What a trader would have done**: after the data bar closed at its low, sell with it (stop the bar's middle).

**Observer's measurement**: the 08:30 New York data hour runs (the H1 bar holding 08:30 with body >= 1.5 H1 ATR
closing in its outer 20 %; with it at the next bar, stop the bar's middle, 3 h): old -0.052 on 72 (2023 +0.135,
2024 -0.191, 2025 +0.102), test -0.201 on 7 / +0.038 on 8 -> fails both. Big data bars continue as often as they
reverse.

**Review.** Rules: vol -2.07 on 3 (saved), near +0.36 on 4, news +0.01 on 3 -> kept. Exits: hold-90 +0.51 / -1.21
-> no. Re-test -2.03 on 2. B2 since stopped 0.00 on 9 (+1.11 with the rules); return gate 1 +0.410 / -0.013 ->
fail. No change.

## Exam week 8 - 2026-06-08 .. 06-12

D1: Mon 08 Jun 4321->4329 (+0.08 ATR); Tue 09 Jun 4326->4260 (-0.65); Wed 10 Jun 4255->4069 (**-1.84**); Thu 11 Jun
4063->4212 (lo 4023, **+1.38**); Fri 12 Jun 4209->4217 (+0.07). D1 ATR(20) ~100.

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 08 10:00 | re-test | SELL |  | 4310.49 | 47.6 | - | -0.16 | -0.16 | -0.16 |  |
| Thu 11 05:30 | re-test | SELL |  | 4044.31 | 24.0 | - | -1.00 | -1.00 | -1.00 |  |
| Thu 11 22:21 | B2 | BUY | M1 | 4088.14 | 18.6 | +0.41 | +0.49 | - | - | stopped vol |
| Fri 12 06:00 | re-test | BUY |  | 4243.56 | 37.7 | - | -0.63 | -0.63 | -0.63 |  |

Realized: 3 trades (0 won / 3 lost) -1.79 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **105.36**. No-learning: the
same 3 trades -> -3.05 / 108.82. Base: 1 trade +0.41 R -> -0.19 / 171.44.

**What the market did.** The biggest week so far: Tuesday NY -88 (three -28/-28/-20 H1 bars), Wednesday down in every
session (-49 / -58 / -26 / -53 late) to 4,067, then Thursday a V: Asia swept to 4,023 and the NY afternoon (00:00-04:00
Thai, after 13:00 New York) ran +132 to 4,220. (solo_look now groups by the server day and shows the 00-04 Thai
hours; earlier weeks' tables above showed sessions to 24:00 Thai only, the D1 lines were complete.) The re-test sold
Wednesday's low at 05:30 Thai Thursday - the low of the V - and bought Thursday's high at 06:00 Friday, both stopped;
Monday's sell of Friday's low ran out of time (-0.16).

**What a trader would have done**: sell Tuesday's NY break (4,320) and hold the run to Wednesday; on Thursday, not
sell at the Asia low after a -1.84 day (two strong days in a row = a stretched market).

**Observer's measurement**: the re-test piece through the gates (M15 entry as in retest_week, M1 exits, 0.37 cost):
old +0.249 on 51 (2023 +0.498, 2024 +0.132, 2025 +0.300), test +0.231 on 10 / **-0.099 on 11** -> gate 1 fails.
Its form from 13:00 Thai only (the owner's trading windows; all five exam re-tests came in Asia, 05:30-10:00 Thai):
old +0.108 on 43, test -0.346 / -0.408 -> fails. The old years' edge of the re-test is not in the last 9 months.

**Review.** **The re-test piece's exam record is -3.82 R on 5 (0 won), below -3 R -> stopped from week 9.** Rules: vol
-1.59 on 4, near +0.36 on 4, news +0.01 on 3 -> kept. Exits: hold-90 +0.51 / -1.21 -> no. B2 since stopped +0.49 on 9
(+1.11 with the rules); return gate 1 +0.410 / -0.013 -> fail. **From week 9 no piece is active**: the realized line
trades nothing until a piece passes the gates (or B2 / the re-test pass them again).

## Exam week 9 - 2026-06-15 .. 06-19

D1: Mon 15 Jun 4299->4308 (+0.07 ATR); Tue 16 Jun 4313->4331 (+0.16); Wed 17 Jun 4331->4258 (hi 4382 lo 4219, -0.67);
Thu 18 Jun 4258->4210 (-0.43); Fri 19 Jun 4205->4156 (lo 4122, -0.43).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 15 22:12 | B2 | SELL | M1 | 4350.82 | 13.2 | -0.44 | +1.17 | - | +1.17 | stopped |
| Tue 16 21:17 | B2 | SELL | M1 | 4329.90 | 9.4 | +0.20 | +0.48 | - | - | stopped near news |

Realized: no piece active, no trade -> 100 USD **-10.55 (blown wk 3)**, 300 USD **105.36**. No-learning: 1 trade (won)
+1.17 R -> -3.05 / 124.18. Base: 2 trades -0.24 R -> -0.19 / 167.49.

**What the market did.** Two quiet days (4,280-4,369), then Wednesday's NY afternoon (00:00-04:00 Thai, the Fed
decision hour) -102 to 4,219; Thursday's Asia bounced +50 against it, **London resumed the fall -66**, and Friday's
Asia went on -66 to 4,122. Week 1 (Wed 22 Apr: Asia +42 against Tuesday's fall, then London down) and week 8 (Thu
11 Jun) showed the same shape. **What a trader would have done**: after a strong down day and a counter-bounce in
Asia, sell London when it turns back down; the stop over the Asia high.

**Observer's measurement**: London resumes yesterday - yesterday's D1 body >= 0.6 D1 ATR(20); today's Asia (to 13:00
Thai) went against it; the first M15 bar 13:00-16:00 Thai closing beyond the previous bar's extreme in yesterday's
direction -> enter at the next bar, stop 0.05 ATR beyond the Asia extreme against it; out 19:00 Thai. First run:
old +0.356 on 45, test +0.526 / +0.684 - **too good: a look-ahead**. In summer the D1 bar opens 21:00 UTC but the
day's first M15 bar is 22:00 UTC (the daily break), so `searchsorted(..., "left") - 1` picked TODAY's D1 bar as
"yesterday". Fixed (the bar before the one open at / before the day's first M15 bar, with a check that it closed
before it); the other candidates' D1 lookups were checked (`atr_at`, `d1_side`, `nyrev`, `rangefade`: correct).
After the fix:

| London resumes yesterday | n | R a trade | |
|---|---|---|---|
| old years 2023-09 .. 2025-09 | 88 | **+0.031** (2023 +0.284, 2024 -0.088, 2025 +0.087) | gate 2: same sign -> pass (barely) |
| test half 1 (2025-10 .. 2026-03-13) | 11 | **+0.193** | |
| test half 2 (.. 2026-06-19) | 12 | **+0.357** | gate 1 -> pass |

Hand check (2026-04-22, exam week 1): Tuesday's body -107.4 = -0.79 of the 136.4 ATR; Wednesday's Asia +42; the
13:00-13:15 Thai bar closed below the previous bar's low -> sell 13:15 at 4,762.65 (ticks), stop 4,778.85 (Asia high
4,772 + 6.8), half at +1 R, the rest at 2.5 R: +0.86 (bars +0.86). The exam-period signals so far on ticks: +0.86,
-1.01, +0.08, +1.15, +1.27 (bars: +0.86, -1.02, +0.09, +1.73, +1.26).

**Review.** **New piece "London resumes yesterday" (lonresume) passes gate 1 (+0.193 / +0.357 >= +0.10) and gate 2
(+0.031 > 0) -> it trades from week 10** (ticks, the same exit as the re-test: half at +1 R, the rest's stop to the
entry, the rest to +2.5 R or 19:00 Thai). Caveat written now: gate 2 passes by +0.031 on 88 with 2024 negative; it
will be stopped at -3 R forward like any piece. Rules: vol -1.59 on 4, near +0.84 on 5, news +0.49 on 4 -> kept.
Exits: hold-90 +0.66 / -1.14 -> no. B2 since stopped +2.14 on 18 signals (+2.28 with the rules); return gate 1
+0.410 / +0.025 -> fail.

## Exam week 10 - 2026-06-22 .. 06-26

D1: Mon 22 Jun 4159->4192 (+0.28 ATR); Tue 23 Jun 4192->4109 (-0.71); Wed 24 Jun 4111->3999 (lo 3959, -0.96); Thu 25 Jun
4007->4025 (+0.15); Fri 26 Jun 4029->4081 (+0.45).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 22 20:30 | B2 | SELL | M5 | 4187.03 | 28.8 | -0.05 | -0.08 | - | -0.08 | stopped |
| Tue 23 21:31 | B2 | SELL | M1 | 4128.23 | 17.5 | -0.17 | -0.52 | - | - | stopped vol |
| Thu 25 20:45 | B2 | SELL | M1 | 4011.97 | 18.9 | -0.39 | -1.04 | - | - | stopped vol |
| Thu 25 21:54 | B2 | SELL | M1 | 4014.19 | 7.5 | -1.04 | +0.50 | - | - | stopped vol |
| Fri 26 20:44 | B2 | BUY | M1 | 4059.37 | 16.8 | +1.36 | +1.33 | - | +1.33 | stopped |
| Fri 26 22:45 | B2 | BUY | M5 | 4095.49 | 61.7 | -0.32 | -0.31 | - | - | stopped near |

Realized: lonresume active, no signal (Tuesday's -0.71 day was followed by a falling Asia, not a bounce; Wednesday's
-0.96 too) -> 100 USD **-10.55 (blown wk 3)**, 300 USD **105.36**. No-learning: 2 trades (1/1) +1.24 R -> -3.05 /
144.07. Base: 6 trades -0.61 R -> -0.19 / 150.95.

**What the market did.** Tuesday's Asia -71, Wednesday a trend day (every session down: -36 / -29 / -40) to 3,959,
Thursday's NY turned it (+48) and Friday rose in London and NY (+38 / +39). **What a trader would have done**: sell
Wednesday's NY as the third leg of a trend day; buy Friday's London once Thursday's low held.

**Observer's measurement**: NY joins a trend day (by 19:00 Thai the day moved >= 0.5 ATR with Asia and London both
that way; the first M15 bar 19:00-21:00 closing beyond the previous bar's extreme that way; stop beyond London's
extreme; out 23:00): old +0.057 on 81, test +0.144 on 20 / **-0.010 on 21** -> gate 1 fails.

**Review.** Rules: vol -2.65 on 7 (saving), near +0.53 on 6, news +0.49 on 4 -> kept. Exits: hold-90 +1.26 over the
last 8 exam weeks but -0.25 over all -> not yet (needs both). B2 since stopped +2.01 on 24 signals, +3.52 with the
skip rules; return gate 1 +0.364 / +0.095 -> fail (0.005 short). No change.

## Exam week 11 - 2026-06-29 .. 07-03

D1: Mon 29 Jun 4077->4017 (-0.52 ATR); Tue 30 Jun 4018->4011 (lo 3943, -0.07); Wed 01 Jul 4014->4032 (hi 4116 lo 3960,
+0.16); Thu 02 Jul 4039->4121 (+0.68); Fri 03 Jul 4125->4175 (+0.41).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 29 20:55 | B2 | SELL | M5 | 4031.92 | 21.7 | +0.05 | +0.58 | - | +0.58 | stopped |
| Tue 30 21:20 | B2 | BUY | M1 | 4049.51 | 37.2 | -0.14 | -0.52 | - | - | stopped vol news |
| Wed 01 20:30 | B2 | BUY | M1 | 4047.27 | 35.5 | +1.04 | +1.01 | - | +1.01 | stopped |
| Wed 01 21:35 | B2 | BUY | M5 | 4111.28 | 100.2 | -0.54 | -0.35 | - | - | stopped vol |
| Thu 02 21:57 | B2 | BUY | M1 | 4127.76 | 14.6 | -0.09 | -1.03 | - | -1.03 | stopped |

Realized: lonresume no signal (Monday's -0.52 was under 0.6 ATR; Thursday's +0.68 was followed by a rising Asia) ->
100 USD **-10.55 (blown wk 3)**, 300 USD **105.36**. No-learning: 3 trades (2/1) +0.57 R -> -3.05 / 177.69. Base:
5 trades +0.31 R -> -0.19 / 128.00.

**What the market did.** The low of the move (3,943 Tue, 3,960 Wed) was made in Asia two days running and London
reversed it both times (+56, +57); Thursday and Friday rose (NY +53, Asia +46) to 4,195. **What a trader would have
done**: buy London's turn of a falling Asia at the bottom of a two-week fall.

**Observer's measurement**: London reverses Asia (Asia >= 0.25 ATR one way; the first London M15 bar closing beyond
the previous bar's extreme against it; stop beyond the Asia extreme; out 19:00): old **-0.134 on 171** (2024 -0.164,
2025 -0.144), test +0.077 / +0.050 -> fails both. Without "yesterday was a strong bar the other way" London's
reversal of Asia loses on the old years - the condition that makes lonresume is the strong day before.

**Review.** **The exit switches to hold-90** (the realistic exit with the time limit at 90 minutes instead of 120):
over the last 8 exam weeks it beat the current exit by **+1.68 R** (+1.28 vs -0.40, all B2 signals unfiltered) and
over all 141 B2 trades before the week's end it is **+0.54** better (+5.44 vs +4.90) -> both protocol conditions
met; from week 12 (it applies to B2's record and its return gate; the active piece keeps its own exit). Rules: vol
-3.51 on 9 (saving), near +0.53 on 6, news -0.03 on 5 -> kept. B2 since stopped +1.72 on 29 signals, +4.09 with the
skip rules; its return gate 1 under hold-90: see the next review.

## Exam week 12 - 2026-07-06 .. 07-10

D1: Mon 06 Jul 4180->4164 (-0.14 ATR); Tue 07 Jul 4165->4105 (-0.51); Wed 08 Jul 4105->4079 (lo 4022, -0.22); Thu 09 Jul
4074->4124 (+0.45); Fri 10 Jul 4125->4119 (-0.05). A 4,022-4,203 range.

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current: hold-90) | realized | no-learning (120 min) | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 06 20:59 | B2 | SELL | M1 | 4139.55 | 11.6 | +0.21 | -0.65 | - | -1.01 | stopped |
| Tue 07 21:42 | B2 | SELL | M1 | 4144.64 | 15.8 | -0.18 | +0.27 | - | +0.05 | stopped |
| Thu 09 20:55 | B2 | SELL | M1 | 4118.79 | 11.5 | -1.00 | -1.00 | - | -1.00 | stopped |

Realized: lonresume no signal -> 100 USD **-10.55 (blown wk 3)**, 300 USD **105.36**. No-learning: 3 trades (1/2)
-1.96 R -> -3.05 / 155.24. Base: 3 trades -0.97 R -> -0.19 / 116.08.

**What the market did.** A range week with alternating sessions: Tuesday Asia -41 / London +33 / late -40; Wednesday
Asia +23 against Tuesday's fall, then London -66 (lonresume's shape, but Tuesday's body was 0.51 ATR, under its 0.6:
no signal - the threshold stays, it was not fitted on this week); Thursday up in London and NY. **What a trader would
have done**: little - a range between 4,022 and 4,203; fade its edges or stay out.

**Review.** No new candidate this week (the one clear move was lonresume's shape below its threshold; changing the
threshold on the week that missed it would be fitting). Rules: vol -3.51 on 9, near +0.53 on 6, news -0.03 on 5 ->
kept. Exits: hold-90 (current) +0.53 over the last 8 weeks; no candidate beats it. B2 since stopped +0.34 on 32
signals (+2.71 with the rules); return gate 1 (hold-90) +0.302 / +0.004 -> fail. No change.

## Exam week 13 - 2026-07-13 .. 07-17

D1: Mon 13 Jul 4091->4001 (-0.87 ATR); Tue 14 Jul 4002->4052 (hi 4104, +0.49); Wed 15 Jul 4053->4061 (+0.08); Thu 16 Jul
4061->3976 (-0.84); Fri 17 Jul 3978->4017 (lo 3960, +0.38).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Tue 14 13:30 | lonresume | SELL |  | 4022.95 | 16.3 | - | -0.52 | -0.52 | - |  |
| Tue 14 20:40 | B2 | BUY | M1 | 4086.74 | 15.6 | -0.74 | -1.00 | - | -1.00 | stopped |
| Tue 14 22:05 | B2 | BUY | M5 | 4089.02 | 23.0 | -0.94 | -1.00 | - | -1.00 | stopped |
| Thu 16 22:25 | B2 | BUY | M5 | 4007.99 | 23.4 | -0.88 | -1.01 | - | -1.01 | stopped |
| Fri 17 13:45 | lonresume | SELL |  | 3996.21 | 17.5 | - | +0.12 | +0.12 | - |  |

Realized: 2 trades (1 won / 1 lost) -0.41 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **98.88**. No-learning:
3 trades (0/3) -3.01 R -> -3.05 / **92.90**. Base: 3 trades -2.56 R -> -0.19 / 62.19. **The realized 300 USD
account is now above the no-learning one (98.88 vs 92.90)** - by not trading B2.

**What the market did.** Monday's NY -63 to a -0.87 day; Tuesday's Asia +30 and NY +30 (to 4,104) recovered it; then
Thursday's NY -46 to another -0.84 day and Friday's NY swept 3,960 and closed up. lonresume sold Tuesday's London
after the Asia bounce (London went flat, NY up: out at 19:00 -0.52) and Friday's London (+0.12, time). B2 bought
three times into the falls (-3.01 under the 120-min exit).

**What a trader would have done**: sell the NY session's breaks on Monday and Thursday (NY was the leg both times),
buy Friday's NY sweep of 3,960.

**Review.** lonresume forward -0.41 on 2. Rules: vol -3.51 on 9, near +0.53 on 6, news -0.03 on 5 -> kept. Exits:
hold-90 still best (-1.99 over the last 8 weeks vs -3.91 for the old exit). B2 since stopped -2.67 on 35 signals
(-0.30 with the rules); return gate 1 +0.271 / -0.066 -> fail. Halfway: the realized line has traded 8 times in 13
weeks (5 B2 in week 1, 3 re-tests, 2 lonresume after week 9). No change.

## Exam week 14 - 2026-07-20 .. 07-24

D1: Mon 20 Jul 3998->4008 (+0.10 ATR); Tue 21 Jul 4008->4078 (+0.71); Wed 22 Jul 4078->4129 (hi 4166, +0.52); Thu 23 Jul
4120->4048 (-0.77); Fri 24 Jul 4049->4053 (+0.05).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 20 20:32 | B2 | BUY | M1 | 4013.54 | 7.0 | -0.72 | -1.03 | - | -1.03 | stopped |
| Mon 20 21:40 | B2 | BUY | M1 | 4009.97 | 12.3 | -0.35 | +0.59 | - | +0.16 | stopped |
| Tue 21 20:45 | B2 | SELL | M5 | 4046.44 | 20.4 | -0.97 | -1.02 | - | -1.02 | stopped |
| Wed 22 21:27 | B2 | SELL | M1 | 4145.96 | 13.5 | -0.53 | -1.01 | - | - | stopped news |
| Thu 23 21:38 | B2 | BUY | M1 | 4059.82 | 20.3 | -0.43 | -0.55 | - | -0.57 | stopped |

Realized: lonresume no signal (Tuesday's +0.71 was followed by a rising Asia; Thursday's -0.77 by a falling one) ->
100 USD **-10.55 (blown wk 3)**, 300 USD **98.88**. No-learning: 4 trades (1/3) -2.46 R -> -3.05 / **55.19**. Base:
5 trades -3.00 R -> -0.19 / 17.14.

**What the market did.** Asia led two up days (Tuesday +53, Wednesday +53 to 4,142), London paused both times, and
Thursday's London and NY fell -39 / -34. B2 sold Tuesday's rise and bought Thursday's fall (against the session's
move each time). **What a trader would have done**: buy Wednesday's Asia as the follow-through of Tuesday's strong
close; sell Thursday's London when it broke Wednesday's Asia low.

**Observer's measurement**: Asia follows a strong day (yesterday's body >= 0.6 ATR closing in its outer 30 %; today's
first two H1 bars close beyond yesterday's close its way; enter at the 3rd bar, stop beyond the two bars, out 13:00
Thai): old **-0.104 on 53** (2024 +0.246, 2025 -0.590), test +0.094 / +0.090 -> fails both.

**Review.** Rules: vol -3.51 on 9, near +0.53 on 6, news **-1.03 on 6** (now saving) -> kept. Exits: hold-90 stays
best (last 8 weeks -4.86 vs -7.19). **B2 since it was stopped: -5.69 R on 40 signals under hold-90 (-2.31 with the
skip rules)**; over all 145 B2 trades every exit is now below zero (hold-90 -1.97, the realistic -3.54); return gate
1 +0.274 / -0.132 -> fail. No change.

## Exam week 15 - 2026-07-27 .. 07-31

D1: Mon 27 Jul 4090->4076 (-0.14 ATR); Tue 28 Jul 4081->4028 (-0.58); Wed 29 Jul 4027->4065 (lo 3996, hi 4116, +0.44);
Thu 30 Jul 4073->4101 (+0.32); Fri 31 Jul 4103->4047 (-0.66).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Thu 30 20:55 | B2 | BUY | M1 | 4102.76 | 29.8 | -0.10 | -0.29 | - | - | stopped vol |
| Fri 31 22:12 | B2 | SELL | M1 | 4043.24 | 8.0 | -1.02 | -1.01 | - | -1.01 | stopped |

Realized: lonresume no signal (no day >= 0.6 ATR before a counter-Asia) -> 100 USD **-10.55 (blown wk 3)**, 300 USD
**98.88**. No-learning: 1 trade (lost) -1.01 R -> -3.05 / 47.13. Base: 2 trades -1.13 R -> -0.19 / 5.91.

**What the market did.** A 3,996-4,120 range: Tuesday down in Asia / London, Wednesday's NY afternoon +38 (to 4,116),
Thursday's Asia -40 reversed by London +44 and NY +33, Friday down in every session (-29 / -21 / -10). Each session
pattern this week was one already measured (London reverses Asia: old -0.134; NY joins a trend day: fails gate 1).
**What a trader would have done**: range trading between ~4,000 and ~4,120, or nothing.

**Review.** No new candidate (the shapes were measured in weeks 10-11). Rules: vol -3.81 on 10, near +0.53 on 6,
news -1.03 on 6 -> kept. Exits: hold-90 stays. B2 since stopped -7.00 on 42 signals (-3.32 with the rules); return
gate 1 +0.274 / -0.155 -> fail. No change.

## Exam week 16 - 2026-08-03 .. 08-07

D1: Mon 03 Aug 4076->4055 (-0.24 ATR); Tue 04 Aug 4051->4077 (+0.30); Wed 05 Aug 4078->4244 (**+1.96**: Asia +83, London
+28, NY +53); Thu 06 Aug 4249->4242 (hi 4304, -0.09); Fri 07 Aug 4237->4341 (hi 4372, **+1.18**).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 03 22:47 | B2 | BUY | M1 | 4039.23 | 9.3 | -0.18 | -0.42 | - | -0.42 | stopped |
| Thu 06 07:00 | re-test | BUY |  | 4278.52 | 21.8 | - | +0.50 | - | +0.50 | stopped |

Realized: lonresume no signal (Wednesday's +1.96 was followed by a rising Asia) -> 100 USD **-10.55 (blown wk 3)**,
300 USD **98.88**. No-learning: 2 trades (1/1) +0.07 R -> -3.05 / 54.03. Base: 1 trade -0.18 R -> -0.19 / 4.25.

**What the market did.** The break of the month-long 3,943-4,203 box: Wednesday was a trend day up in every session
(+83 / +28 / +53, 4,065 -> 4,268), Thursday held it (4,223-4,304) and Friday went on +104 (Asia +42, London +43) to
4,372. The re-test (stopped) bought Thursday's Asia re-test of Wednesday's high: +0.50. **What a trader would have
done**: buy the breakout of the box on Wednesday and hold it into Friday.

**Observer's measurement**: a D1 box breaks (the last 10 D1 bars span < 2.5 ATR; the first H1 close beyond their
high / low; with it, stop 0.3 ATR, out 8 h): old **-0.174 on 36**, test +0.570 / -0.303 -> fails both. Box breaks
fail as often as they run on gold's record.

**Review.** Rules: vol -3.81 on 10, near +0.53 on 6, news -1.03 on 6 -> kept. Exits: hold-90 stays. The re-test since
stopped +0.50 on 1. B2 since stopped -7.42 on 43 (-3.75 with the rules); gate 1 +0.279 / -0.178 -> fail. No change.

## Exam week 17 - 2026-08-10 .. 08-14

D1: Mon 10 Aug 4339->4389 (+0.54 ATR); Tue 11 Aug 4389->4368 (hi 4435, -0.24); Wed 12 Aug 4372->4407 (+0.40); Thu 13 Aug
4406->4349 (hi 4450, -0.64); Fri 14 Aug 4353->4376 (lo 4311, +0.26).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 10 21:55 | B2 | SELL | M1 | 4342.93 | 9.4 | -1.00 | -1.00 | - | -1.00 | stopped |
| Tue 11 02:00 | re-test | BUY |  | 4378.84 | 18.1 | - | +1.15 | - | +1.15 | stopped |
| Tue 11 20:46 | B2 | BUY | M1 | 4402.58 | 14.4 | -0.94 | -1.02 | - | - | stopped vol |
| Wed 12 22:48 | B2 | SELL | M1 | 4416.28 | 12.2 | -0.67 | +1.05 | - | - | stopped vol |
| Thu 13 21:00 | B2 | SELL | M5 | 4372.77 | 30.7 | +0.02 | +0.24 | - | - | stopped vol |

Realized: lonresume no signal -> 100 USD **-10.55 (blown wk 3)**, 300 USD **98.88**. No-learning: 2 trades (1/1)
+0.15 R -> -3.05 / 65.40. Base: 4 trades -2.60 R -> **its 300 USD account blown this week (-5.13)**.

**What the market did.** After the breakout, a 4,311-4,450 range above the old box: no session ran more than 36 USD.
The re-test (stopped) bought Friday's strong day's high on Tuesday 02:00 Thai (+1.15). **What a trader would have
done**: hold Friday's breakout longs or wait; nothing new to start in a post-breakout range.

**The re-test's return, checked** (it has +1.64 on 2 since it was stopped): the gates on its bar form pass (old +0.249
on 51; test +0.119 / +0.177). But reading its code for the gate, its cutoff is one day later than its docstring
("the next server day, until 23:00 Thai": `normalize() + 1 day 23 h` is the day after), and on ticks it does not
even hold that long (`ticks()` loads only the entry's UTC day and the day before: the trade is closed at the last
tick of that UTC day, "data end"). As documented (the next server day, out 23:00 Thai) it gives: old **+0.307 on 50**,
test +0.385 / **+0.072** -> gate 1 fails. **Decision: the re-test stays stopped** - its pass rests on a holding
period it does not trade with. (The no-learning line keeps retest_week.py exactly as it was.)

**Review.** Rules: vol -3.53 on 13, near +0.53 on 6, news -1.03 on 6 -> kept. Exits: hold-90 stays. B2 since stopped
-8.15 on 47 (-4.75 with the rules); return gate 1 +0.279 / -0.199 -> fail. No change.

## Exam week 18 - 2026-08-17 .. 08-21

D1: Mon 17 Aug 4373->4416 (+0.47 ATR); Tue 18 Aug 4417->4334 (-0.91); Wed 19 Aug 4342->4524 (**+1.98**: NY +128); Thu
20 Aug 4522->4520 (lo 4451, -0.03); Fri 21 Aug 4520->4605 (hi 4632, +0.88).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 17 20:57 | B2 | BUY | M1 | 4408.90 | 25.0 | +0.24 | +0.55 | - | - | stopped near |
| Mon 17 22:23 | B2 | BUY | M1 | 4423.73 | 10.2 | +0.30 | -0.08 | - | -0.45 | stopped |
| Tue 18 20:31 | B2 | SELL | M1 | 4384.02 | 13.9 | -1.02 | -1.02 | - | -1.02 | stopped |
| Tue 18 22:00 | B2 | SELL | M5 | 4366.54 | 42.0 | +0.49 | +0.05 | - | +0.06 | stopped |
| Thu 20 13:15 | lonresume | BUY |  | 4493.09 | 20.0 | - | -1.03 | **-1.03** | - |  |
| Thu 20 20:44 | B2 | BUY | M1 | 4486.87 | 18.3 | +0.70 | +1.38 | - | +1.38 | stopped |
| Thu 20 22:30 | re-test | BUY |  | 4532.66 | 22.1 | - | -1.02 | - | -1.02 | stopped |
| Fri 21 22:42 | B2 | BUY | M1 | 4608.78 | 9.8 | +0.14 | +1.52 | - | - | stopped vol |

Realized: 1 trade (lost) -1.03 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **78.24**. No-learning: 5 trades (2/3)
-1.05 R -> -3.05 / 51.89. Base: 6 trades +0.85 R -> blown (wk 17).

**What the market did.** Tuesday fell (NY -32, late -30) to 4,329, then Wednesday's NY ran +128 in the US hours
(+31 more after) to 4,524 - the second +1.9 ATR day in three weeks, both up. Thursday's Asia gave back -41 and London
-14 more (to 4,465) before NY bought it (+43); Friday rose in every session to 4,632. lonresume bought Thursday's
London on the counter-Asia and was stopped under 4,473 before NY's rise. **What a trader would have done**: buy
Wednesday's NY breakout of 4,436; buy Thursday's dip later (NY, not London).

**Review.**
- **Skip rule "near a zone line" deleted from week 19**: its exam-forward record is **+1.08 R on 7** (the trades it
  skipped won more than +1.0 R in total; the learning journal's forward +1.86 would make +2.94). It applies to B2,
  which is stopped: the change matters for B2's record and its return gate.
- vol -2.01 on 14 (saving), news -1.03 on 6 -> kept. Exits: hold-90 stays (last 8 weeks -6.98 vs -8.78).
- lonresume forward -1.44 on 3 (stop at -3). The re-test (stopped) +0.62 on 3 since. B2 since stopped -5.75 on 53;
  return gate 1 +0.308 / -0.223 -> fail.

## Exam week 19 - 2026-08-24 .. 08-28

D1: Mon 24 Aug 4610->4651 (+0.41 ATR); Tue 25 Aug 4656->4660 (hi 4697, +0.04); Wed 26 Aug 4661->4593 (-0.67); Thu 27 Aug
4604->4601 (-0.03); Fri 28 Aug 4602->4454 (**-1.48**: NY -114).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 24 20:45 | B2 | SELL | M1 | 4658.66 | 23.1 | -0.60 | -0.63 | - | - | stopped vol |
| Mon 24 22:49 | B2 | SELL | M1 | 4652.15 | 28.1 | -0.21 | +0.01 | - | - | stopped vol |
| Tue 25 21:13 | B2 | BUY | M1 | 4625.83 | 21.4 | +0.30 | +1.23 | - | - | stopped vol news |
| Tue 25 22:34 | B2 | BUY | M1 | 4650.12 | 21.2 | -0.10 | -0.50 | - | - | stopped vol |
| Wed 26 20:34 | B2 | BUY | M1 | 4617.43 | 20.3 | +0.05 | -1.08 | - | -1.08 | stopped |
| Wed 26 22:35 | B2 | BUY | M1 | 4598.52 | 10.1 | -0.24 | +0.49 | - | +0.49 | stopped |
| Thu 27 14:00 | lonresume | SELL |  | 4600.24 | 47.8 | - | +0.03 | **+0.03** | - |  |
| Thu 27 20:41 | B2 | SELL | M1 | 4572.77 | 21.2 | -0.53 | -1.05 | - | -1.05 | stopped |
| Fri 28 20:47 | B2 | BUY | M1 | 4608.64 | 15.6 | -1.03 | +1.00 | - | +1.00 | stopped |

Realized: 1 trade (won, +0.03) -> 100 USD **-10.55 (blown wk 3)**, 300 USD **79.88**. No-learning: 4 trades (2/2)
-0.64 R -> -3.05 / 28.17. Base: 8 trades -2.35 R -> blown (wk 17).

**What the market did.** A 4,565-4,697 top for four days (the H1 vol over 1.1x its median most of Monday-Tuesday:
the vol rule skipped 4 B2 signals), Wednesday drifted down in every session, then Friday's 10:00 New York H1 bar
(21:00 Thai) swept up to 4,632 and reversed with a 46-USD lower wick on 2.4x volume, and the next two bars fell -52 /
-45: NY -114, the day -1.48 ATR to 4,445. lonresume sold Thursday's London after Wednesday's -0.67 day (Asia had
bounced +3; the stop over the Asia high was 47.8 USD) and ran out of time at +0.03.

**What a trader would have done**: sell Friday's failed high at 10:00 New York once the 21:00 Thai bar closed back
below 4,600 (or the 22:00 bar's continuation). This is the strong-NY-bar continuation measured in week 1 (h1mom:
old -0.038) - the NY-bar shapes keep failing the gates on gold's record, so no new measurement this week.

**Review.** Rules: vol -1.90 on 18, news +0.20 on 7 -> kept. Exits: hold-90 stays (last 8 weeks -8.00, the best).
lonresume -1.40 on 4 (stop at -3). B2 since stopped -6.28 on 61 (-5.07 with the rules); return gate 1 +0.243 /
-0.146 -> fail. No change.

## Exam week 20 - 2026-08-31 .. 09-04

D1: Mon 31 Aug 4446->4448 (+0.02 ATR); Tue 01 Sep 4454->4329 (**-1.19**: London -66); Wed 02 Sep 4331->4389 (lo 4282,
+0.54); Thu 03 Sep 4391->4473 (hi 4511, +0.78); Fri 04 Sep 4476->4431 (lo 4365, -0.42).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 31 08:15 | re-test | SELL |  | 4443.67 | 33.4 | - | +0.50 | - | +0.50 | stopped |
| Mon 31 20:36 | B2 | SELL | M1 | 4437.21 | 11.6 | +0.70 | +0.85 | - | - | stopped vol |
| Wed 02 08:00 | re-test | SELL |  | 4315.65 | 24.1 | - | +0.50 | - | +0.50 | stopped |
| Wed 02 21:46 | B2 | SELL | M1 | 4381.49 | 16.9 | +0.92 | +0.64 | - | - | stopped vol |
| Thu 03 21:41 | B2 | SELL | M1 | 4466.73 | 14.7 | -0.97 | -1.00 | - | - | stopped vol |
| Fri 04 14:15 | lonresume | BUY |  | 4468.00 | 13.3 | - | +0.50 | **+0.50** | - |  |

Realized: 1 trade (won) +0.50 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **86.50**. No-learning: 2 trades (2/0)
+1.00 R -> -3.05 / 56.87. Base: 3 trades +0.65 R -> blown (wk 17).

**What the market did.** Friday's -1.48 day was re-tested on Monday's Asia (the re-test sold it: +0.50 at the time
limit... half at +1 R, the rest out at entry); Tuesday's London broke down -66 to a -1.19 day; Wednesday's Asia made
the low (4,282) and NY / Thursday reversed it (+36, +40, +42) to 4,511; Friday's NY swept down to 4,365 and closed
4,431. lonresume bought Friday's London after Thursday's +0.78 day and a slightly lower Asia: half at +1 R, the rest
at the entry (+0.50) as NY swept down.

**What a trader would have done**: sell Tuesday's London break (4,424); buy Wednesday's NY recovery above 4,336.

**Review.** The re-test (stopped) has +1.62 R on 5 since it was stopped; its gates again: the documented form old
+0.307 on 50, test +0.395 / **+0.016**; the code's form +0.177 / **+0.084** -> both fail gate 1; stays stopped.
Rules: vol -1.41 on 21 (still saving), news +0.20 on 7 -> kept. Exits: no candidate +1.5 better over 8 weeks.
lonresume -0.90 on 5. B2 since stopped -5.80 on 64; gate 1 fails. No change.

## Exam week 21 - 2026-09-07 .. 09-11

D1: Mon 07 Sep 4422->4406 (-0.15 ATR); Tue 08 Sep 4413->4354 (-0.56); Wed 09 Sep 4357->4400 (+0.40); Thu 10 Sep 4405->4317
(-0.82); Fri 11 Sep 4322->4348 (lo 4292, +0.25).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Thu 10 20:39 | B2 | BUY | M1 | 4371.14 | 30.5 | -0.30 | -0.41 | - | -0.06 | stopped |
| Fri 11 13:45 | lonresume | SELL |  | 4350.63 | 15.6 | - | +1.04 | **+1.04** | - |  |
| Fri 11 20:48 | B2 | BUY | M1 | 4400.44 | 21.0 | -0.78 | -1.02 | - | - | stopped vol |

Realized: 1 trade (won) +1.04 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **102.82** (back above its start).
No-learning: 1 trade (lost) -0.06 R -> -3.05 / 54.98. Base: 2 trades -1.07 R -> blown (wk 17).

**What the market did.** A 4,292-4,443 range drifting down: Wednesday's Asia +41, Thursday's Asia +26 then London -57
and the NY afternoon -47 to a -0.82 day; Friday's Asia bounced +24 against it and London turned down (lonresume sold
13:45 Thai at 4,350.63: half at +1 R, the rest stopped at 2.5 R... out +1.04), then NY swept 4,292 and closed up.
**What a trader would have done**: the same London sell on Friday; buy NY's sweep of 4,292.

**Review.** lonresume forward **+0.14 on 6** (3 won, 2 lost, 1 flat). Rules: vol -2.43 on 22, news +0.20 on 7 ->
kept. Exits: the old realistic exit +0.63 over the last 8 weeks vs hold-90, -0.50 over all -> no switch. B2 since
stopped -7.22 on 66; gate 1 fails. No change.

## Exam week 22 - 2026-09-14 .. 09-18

D1: Mon 14 Sep 4339->4298 (-0.38 ATR); Tue 15 Sep 4300->4293 (-0.07); Wed 16 Sep 4295->4263 (lo 4235, -0.30); Thu 17 Sep
4260->4342 (+0.78); Fri 18 Sep 4343->4378 (hi 4400, +0.33).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Tue 15 20:37 | B2 | BUY | M1 | 4293.65 | 10.5 | -0.91 | -1.00 | - | -1.00 | stopped |
| Tue 15 22:12 | B2 | BUY | M1 | 4285.84 | 12.2 | +0.29 | +0.67 | - | +0.84 | stopped |
| Fri 18 21:30 | B2 | SELL | M1 | 4342.87 | 14.4 | -0.86 | -1.00 | - | - | stopped news |

Realized: lonresume no signal (Thursday's +0.78 was followed by a rising Asia) -> 100 USD **-10.55 (blown wk 3)**,
300 USD **102.82**. No-learning: 2 trades (1/1) -0.16 R -> -3.05 / 54.77. Base: 3 trades -1.48 R -> blown (wk 17).

**What the market did.** Monday's London -50; Tuesday flat; Wednesday's NY afternoon (the Fed hour, 01:00 Thai) swung
from 4,368 to 4,235 (-84 late), and Thursday reversed it in Asia and London (+44 / +45) - the third Fed-hour swing of
the exam (weeks 9, 22; week 8's Thursday +132 too) followed by a move the next day. Friday's Asia +35 to 4,400.
**What a trader would have done**: stand aside through the Fed hour; buy Thursday's Asia once the post-Fed low held.

**Review.** No candidate (the Fed-hour days are 3 in 22 weeks - too few for the gates' two halves). Rules: vol -2.43
on 22, news -0.80 on 8 -> kept. Exits: the old realistic exit +1.26 over the last 8 weeks vs hold-90 but -0.32 over all
-> no switch (both conditions needed). lonresume +0.14 on 6. B2 since stopped -8.56 on 69; gate 1 fails. No change.

## Exam week 23 - 2026-09-21 .. 09-25

D1: Mon 21 Sep 4381->4343 (-0.36 ATR); Tue 22 Sep 4348->4358 (+0.10); Wed 23 Sep 4363->4289 (-0.72); Thu 24 Sep 4293->4273
(lo 4244, -0.20); Fri 25 Sep 4274->4285 (+0.11).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Tue 22 20:30 | B2 | SELL | M1 | 4330.48 | 13.0 | -0.79 | -1.00 | - | - | stopped vol |
| Tue 22 21:35 | B2 | SELL | M1 | 4324.92 | 13.6 | -0.83 | -1.00 | - | - | stopped vol |
| Tue 22 22:44 | B2 | SELL | M1 | 4327.55 | 13.7 | -0.27 | -1.01 | - | - | stopped vol |
| Thu 24 20:58 | B2 | SELL | M1 | 4265.32 | 11.8 | +0.95 | +1.15 | - | +0.84 | stopped |

Realized: lonresume no signal (Wednesday's -0.72 was followed by a falling Asia) -> 100 USD **-10.55 (blown wk 3)**,
300 USD **102.82**. No-learning: 1 trade (won) +0.84 R -> -3.05 / 64.74. Base: 4 trades -0.93 R -> blown (wk 17).

**What the market did.** A slow grind down, 4,383 -> 4,244, no session over 36 USD; Wednesday fell in every session
(-29 / -25 / -25). The vol rule skipped Tuesday's three B2 sells (all lost: it saved 3.01 R this week, -5.44 on 25
in the exam). **What a trader would have done**: sell rallies in a slow downtrend, small; or nothing.

**Review.** Rules: **vol -5.44 on 25** (the one rule that keeps saving, as in the learning journal), news -0.80 on 8
-> kept. Exits: no switch. lonresume +0.14 on 6. B2 since stopped -10.42 on 73 (-4.65 with the rules); gate 1
+0.224 / -0.123 -> fail. No change.

## Exam week 24 - 2026-09-28 .. 10-02

D1: Mon 28 Sep 4272->4114 (**-1.66 ATR**: Asia -93); Tue 29 Sep 4121->4180 (+0.59); Wed 30 Sep 4184->4159 (-0.25); Thu 01
Oct 4160->4177 (+0.18); Fri 02 Oct 4175->4139 (hi 4229, -0.40).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 28 20:45 | B2 | BUY | M1 | 4151.32 | 15.7 | -0.95 | -1.02 | - | - | stopped |
| Tue 29 14:00 | lonresume | SELL |  | 4140.35 | 12.7 | - | -1.01 | **-1.01** | - |  |
| Wed 30 13:15 | lonresume | BUY |  | 4183.43 | 22.6 | - | +0.14 | **+0.14** | - |  |
| Wed 30 21:24 | B2 | SELL | M1 | 4174.02 | 11.8 | -0.13 | +1.26 | - | - | stopped news |
| Wed 30 22:07 | B2 | SELL | M1 | 4161.95 | 15.6 | +0.14 | +0.40 | - | +0.44 | stopped |
| Thu 01 21:02 | B2 | SELL | M1 | 4155.94 | 17.1 | -0.41 | -1.00 | - | - | stopped news |

Realized: 2 trades (1 won / 1 lost) -0.87 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **93.14**. No-learning:
1 trade (won) +0.44 R -> -3.05 / 71.63. Base: 4 trades -1.36 R -> blown (wk 17).

**What the market did.** Monday's Asia -93 (the fourth week whose biggest move was in Asia) to a -1.66 day; Tuesday
did not break its low (4,113 vs 4,111: no re-test) and bounced all day (+18 / +14 / +35 late); the rest of the week
was a 4,125-4,229 range. lonresume sold Tuesday's London after the Asia bounce - but the bounce went on (-1.01) -
and bought Wednesday's London after Tuesday's up day (+0.14: half at 1 R... out at the time limit near the entry).

**What a trader would have done**: after a -1.66 day that stops on a round number (4,111-4,113 twice), expect a
bounce, not a continuation; then range-trade 4,125-4,229.

**Review.** lonresume forward **-0.73 on 8** (3 won, 3 lost, 2 near flat; stop at -3). Rules: vol -5.44 on 25, news
-0.55 on 10 -> kept. Exits: no switch. B2 since stopped -10.78 on 77; gate 1 fails. No change.

## Exam week 25 - 2026-10-05 .. 10-09

D1: Mon 05 Oct 4143->4141 (-0.02 ATR); Tue 06 Oct 4144->4164 (+0.22); Wed 07 Oct 4166->4107 (lo 4066, -0.67); Thu 08 Oct
4112->4133 (+0.24); Fri 09 Oct 4132->4191 (hi 4208, +0.70; Asia +61).

**A data hole.** The stored M15 and H1 bars stop at 2026-10-05 08:45 UTC (and M5 at 10-06 16:05) while M1, D1, H4 and
the ticks go on. The bot's exam B2 run has **no trade this week** (its levels come from H1), and my first run of the
week also had none (lonresume reads M15). Since a missing bar is not a market event, before writing the week I
removed its empty row from weeks.csv (no ledger rows had been written) and re-ran it with M15 / H1 filled from M1
where the files have no bar (`pieces.bars`, UTC-aligned, left-labelled; checked against the stored 08:30 / 08:45
bars). B2 cannot be rebuilt (it is the bot's run), so the base and no-learning lines have no B2 this week by data,
not by market. The re-test (no-learning line) is unaffected: no strong D1 bar before or in the week.

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Thu 08 13:30 | lonresume | SELL |  | 4116.04 | 31.7 | - | -0.28 | **-0.28** | - |  |

Realized: 1 trade (lost) -0.28 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **84.38**. No-learning: no trade ->
-3.05 / 71.63. Base: no trade (blown wk 17).

**What the market did.** A 4,066-4,208 range: Tuesday's London +54 reversed Asia's -24; Wednesday fell in every
session to 4,066; Thursday sat in a 40-USD range (lonresume sold London after Asia's +6 bounce against Wednesday:
out at 19:00, -0.28); Friday's Asia ran +61 to 4,208 (the fifth exam week with its biggest move in Asia).
**What a trader would have done**: little; buy Friday's Asia breakout above 4,184.

**Review.** lonresume forward **-1.00 on 9** (stop at -3). Rules: vol -5.44 on 25, news -0.55 on 10 -> kept. Exits: no
switch. B2 since stopped -10.78 on 77; gate 1 fails. No change for the last week.

## Exam week 26 - 2026-10-12 .. 10-16

D1: (Monday 12 Oct has no stored D1 bar; its H1: Asia +2, London -23, NY -4) Tue 13 Oct 4174->4160 (-0.17 ATR); Wed 14 Oct
4161->4103 (lo 4073, -0.72); Thu 15 Oct 4104->4169 (+0.78); Fri 16 Oct 4170->4164 (-0.08). The bot's B2 trades are
back this week (the H1 hole is over).

| Thai time | piece | side | TF | entry | stop USD | base R | exit R (current) | realized | no-learning | skipped by |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 12 21:16 | B2 | SELL | M1 | 4167.97 | 7.9 | -0.20 | +0.49 | - | - | stopped news |
| Tue 13 21:00 | B2 | SELL | M5 | 4169.01 | 22.5 | +0.42 | +0.33 | - | +0.43 | stopped |
| Thu 15 13:15 | lonresume | SELL |  | 4132.90 | 32.9 | - | -0.38 | **-0.38** | - |  |
| Thu 15 21:40 | B2 | BUY | M1 | 4163.98 | 19.7 | -0.44 | -0.92 | - | -1.00 | stopped |
| Fri 16 21:23 | B2 | BUY | M1 | 4195.17 | 14.6 | -0.74 | -1.00 | - | - | stopped news |

Realized: 1 trade (lost) -0.38 R -> 100 USD **-10.55 (blown wk 3)**, 300 USD **71.99**. No-learning: 2 trades (1/1)
-0.57 R -> -3.05 / 61.56. Base: 4 trades -0.96 R -> blown (wk 17).

**What the market did.** A 4,073-4,217 range. Wednesday's NY -56 to 4,073 (-0.72 day); Thursday's Asia bounced +34
against it, lonresume sold London at 4,132.90 with the stop over the Asia high (32.9 USD) - London and NY went
sideways and the NY afternoon rose +22: -0.38 at 19:00 Thai. **What a trader would have done**: range-trade
4,073-4,217 or stand aside.

**Final review (nothing applies after the last week).** lonresume forward **-1.38 on 10** (4 won, 6 lost). vol -5.44
on 25 (saved), news -1.06 on 12 (saved). B2 since stopped -11.88 on 81 signals under hold-90 (-5.86 with the skip
rules); every exit over the 88 exam B2 signals is below zero (base -24.19, realistic -17.19, hold-90 -14.62).

## The end of the solo exam (26 weeks, 2026-04-20 .. 10-16)

| Line | Trades | Won / lost | R | R a trade | Weeks won / lost | 100 USD account | 300 USD account | Worst drawdown (100 / 300) |
|---|---|---|---|---|---|---|---|---|
| **Realized** (my decisions) | 20 | 5 / 15 | **-9.68** | -0.484 | 3 / 9 | blown wk 3 (-10.55) | **71.99** | 110.55 / 228.01 USD |
| **No-learning** (start state unchanged) | 57 | 22 / 35 | **-12.64** | -0.222 | 9 / 16 | blown wk 5 (-3.05) | **61.56** (low 12.57 on 08-27) | 103.05 / 287.43 USD |
| **Base** (the bot's B2 as is) | 88 | - | **-24.19** | -0.275 | 6 / 19 | blown wk 5 (-0.19) | blown wk 17 (-5.13) | 100.19 / 305.13 USD |

By piece (realized): B2 5 trades -4.49 (week 1, then stopped); re-test 5 trades -3.82 (weeks 3-8, then stopped);
lonresume 10 trades -1.38 (weeks 13-26). What the stopped pieces did afterwards: B2 -11.88 on 81 signals (hold-90,
unfiltered) / -5.86 with the skip rules; the re-test +1.62 on 5.

Decisions and what they did:

| After week | Decision | Evidence | Afterwards |
|---|---|---|---|
| 1 | B2 stopped (PROTOCOL: piece below -3 R) | realized -4.49 on 5 | B2's next 25 weeks: -11.88 on 81 (the exit in force at the time), -5.86 with the skip rules (the no-learning line's B2 in weeks 2-26: -5.96 on 42) |
| 2 | B2's return gate defined (gate 2 -> "positive on learning part 1", B2 has no 2023-25 trades) | - | never used: gate 1 failed every week (half 2 from +0.091 to -0.223) |
| 8 | re-test stopped | -3.82 on 5 (0 won) | +1.62 on 5 while stopped |
| 9 | lonresume adopted | gate 1 +0.193 / +0.357, gate 2 +0.031 on 88 (after a look-ahead fix) | -1.38 on 10 (4 won) |
| 11 | exit -> hold-90 | +1.68 over 8 weeks, +0.54 over all B2 trades | B2 stopped, so no realized effect; over weeks 12-26 hold-90 -13.60 vs the realistic exit -13.91 on B2's 52 signals |
| 17 | the re-test kept stopped although its code-form passed the gates | code form +0.119 / +0.177 rested on a one-day-too-long cutoff it does not trade with on ticks; documented form +0.385 / +0.072 | +0.62 more on 3 (weeks 18-20) |
| 18 | skip rule "near a zone line" deleted | +1.08 on 7 forward | B2 stopped: no realized effect |

Candidates measured and failed (gates on data before each week's end, M1 bars, 0.37 USD cost): NY cash-open range
breakout, strong NY H1 bar, one-way day at 20:30, London breaks Asia, NY turns an extended day, D1-side pullback in
NY, Asia-open run, range-edge rejection, NY reverses a run, 08:30 data-hour run, NY joins a trend day, London reverses
Asia, Asia follows a strong day, D1 box breakout, the re-test from 13:00 Thai, the re-test as documented. Seventeen
candidates, one adopted (lonresume) - and it lost forward.

Written for the record (details in the final report): before exam week 1, listing the section headings of
`journal/PLAN1_JOURNAL.md` (to find the NY-B2 sections) showed the headings of that file's PLAN-1 exam weeks, which
carry coarse gold prices of exam weeks 1-7 (e.g. "gold falls 4,830 -> 4,680", "4,540 -> 4,740 -> 4,700", "gold falls
4,540 -> 4,430"). I did not read those sections. Every decision above follows a protocol threshold or a gate run on
data before the week's end; the candidate ideas came from each week's own bars.
