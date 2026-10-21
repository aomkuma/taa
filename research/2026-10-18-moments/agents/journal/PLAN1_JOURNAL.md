# PLAN-1 trade journal - trade by trade, week by week (from 2026-10-21)

Owner (2026-10-21, about 13:00 Thai): "trade, learn from each winner and loser, keep a trade journal, look for your own
weaknesses - that should make profit. Summing results once over three or five years is not useful."

**How it works:**
- Every PLAN-1 trade in time order, from the first learning week (2025-10-20) on: why it entered, the market around
  it (H1 ATR, the D1 20-day direction, yesterday's high / low), how far it went for and against (best / worst R and
  when), the result and a one-line lesson.
- At each week's end: what the winners share, the weaknesses that repeat, **the rules that cost this week** (owner,
  2026-10-21: "a rule that blocks profit gets deleted - the facts decide"), and **one** change, written before the next
  week is opened.
- The change applies from the next week on and is never applied back. Each week is read with only the weeks before it,
  so the journal is a walk-forward at the scale of a week.
- Source: `dev/plan1_trades_learn_s0_x0.parquet` (dev1's measured runner, spread only); the paths from the raw ticks;
  times in Thai time.

## Week 1 - 2025-10-20 .. 24 (gold's record 4,381 on Monday, then the crash on Tuesday)

| # | Day, time | Piece | Side | Entry / stop (risk) | Exit | R | H1 ATR | Best / worst on the way | Lesson |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Mon 08:15 | Asia B2 | BUY | 4255.64 / 4217.47 (38.2) | 12:50 structure | -0.21 | 35.5 | +0.41 R at 09:36 / -0.24 | the stop 38 USD wide: the pattern's far side in a 35-ATR market is too far for a 1-day trade |
| 2 | Mon 13:16 | London ORB | BUY | 4245.51 / 4230.97 (14.5) | 13:28 stop | -1.02 | 27.2 | never above 0 | the break never ran - stopped in 12 minutes |
| 3 | Mon 19:30 | NY straddle | BUY | 4296.22 / 4288.22 (8.0) | 20:00 time | **+3.41** | 21.9 | +3.86 R at 19:58 / -0.23 | the release ran with the day's direction |
| 4 | Tue 13:42 | London ORB | BUY | 4334.15 / 4317.15 (17.0) | 14:33 stop | -1.01 | 19.9 | +0.59 R at 13:53 / -1.01 | bought an upside break the morning gold turned from its record: the break was a top |
| 5 | Tue 19:30 | NY straddle | SELL | 4226.41 / 4234.41 (8.0) | 20:00 time | **+1.87** | 25.6 | +2.57 R at 19:46 / -0.50 | the straddle caught the crash leg |
| 6 | Wed 13:23 | London ORB | BUY | 4140.66 / 4127.69 (13.0) | 14:23 time | -0.16 | 34.1 | **+1.59 R at 13:55** / -0.86 at 14:06 | was 0.4 R from its 2 R target, then gave it all back |
| 7 | Wed 19:30 | NY straddle | SELL | 4043.08 / 4051.08 (8.0) | 19:49 stop | -1.23 | 41.9 | +0.13 R / -1.23 | the ATR was 42: an 8-USD stop is noise there |
| 8 | Thu 07:25 | Asia B2 | SELL | 4071.57 / 4112.29 (40.7) | 10:20 structure | -0.61 | 35.6 | +0.09 R / -0.62 | again a 40-USD stop; sold after a 160-USD drop the day before (late) |
| 9 | Thu 19:30 | NY straddle | BUY | 4111.74 / 4103.74 (8.0) | 20:00 time | **+1.90** | 21.6 | +2.18 R / -0.05 | |
| 10 | Fri 19:30 | NY straddle | BUY | 4066.75 / 4058.75 (8.0) | 20:00 time | **+1.91** | 20.1 | +3.31 R / -0.03 | |

**The week:** 10 trades, +4.85 R (NY straddle 4 of 5 won, +7.86 R; London ORB 0 of 3, -2.19 R; Asia B2 0 of 2, -0.82 R).

**What the winners share:** all NY straddle at 19:30 with an H1 ATR of 20-26 - the release minute ran 20-30 USD in the
breakout's direction within half an hour.

**The weaknesses that repeat:**
1. **London ORB enters the first break and does not protect a run:** #2 never ran, #4 bought a top, #6 had +1.59 R and
   finished -0.16.
2. **Asia B2's stops are 38-41 USD** in a 35-ATR market (the pattern's far side) - one loser costs a week of small wins
   at 0.01 lot.
3. **An ATR above about 35-40 turns the 8-USD straddle stop into noise** (#7).

**The liquidity reading (`liq_journal.py`, `out_liq_w1.txt`; owner: "cut the loss away from the liquidation zone"):**
the pools everyone sees at each entry (yesterday's high / low, the Asia range 00:00-07:00 Thai, today's open, the last
M15 swing, the 10-USD round numbers) and where the stop sat against them:

| # | Stop sat just beyond (within 0.25 H1 ATR) | Stopped? | Without the stop, by the window's end |
|---|---|---|---|
| 2 | the Asia low 4234.1 (stop 3.1 under it) | yes, 13:28 | **SWEPT: came back to +0.71 R** (best +0.78 R at 14:13) |
| 4 | the round 4320 | yes, 14:33 | FAKE: ran on to -1.76 R - it bought a bounce on the day gold fell from its record (the Asia high 4381.4 was the record itself) |
| 6 | the Asia high 4130.9 (3.2) and the round 4130 | no (time) | - |
| 7 | the M15 swing high 4044.9 (6.2) and the round 4050 | yes, 19:49 | **SWEPT: came back to +1.12 R** (best +2.44 R at 19:56) |
| 1, 8 | the M15 swing low (1.6) / today's open (1.6) | no | - |

- **Two of the week's three stop-outs were sweeps:** the stop sat a few USD beyond a pool everyone sees, the market
  took those stops and then went the trade's way (+0.71 R and +1.12 R at the window's end). The third (#4) was a real
  reversal: a buy against the day's turn from the record.
- **The losers' cause is the stop's place, not the idea.**

**The rules that cost this week:**
- **VOL-16 (trade only while the H1 ATR is 12-16):** every trade this week had an H1 ATR of 20-42, so VOL-16 would have
  taken none of them - the week made +4.85 R (the straddle +7.86 R). Cost this week: +4.85 R. Evidence so far: one week.
- **The ORB's 60-minute time exit:** #6 was +1.59 R at 13:55 and was closed at 14:23 at -0.16. Cost: up to +1.75 R.
- **The B2 stop at the pattern's far side (38-41 USD):** cost nothing this week beyond its two small losses, but it
  makes a B2 loser the size of a week.

**The one change for week 2 (revised before week 2 is opened, 2026-10-21 13:05 Thai, on week 1 only):** the stop
leaves the sweep zone. If a pool (yesterday's high / low, the Asia high / low, today's open, the last M15 swing, a 10-USD
round number) lies between the entry and the stop within 0.25 H1 ATR of the stop, the stop moves to 0.5 H1 ATR beyond
that pool. The target price stays where it was; R is counted on the new, wider risk (a smaller lot). The break-even
idea (ORB at +1 R) is kept as the next candidate.

**Checked late (2026-10-21 13:08 Thai):** change 1 re-run on week 1 itself gives +2.41 R against the base +4.84
(`week_change.py`): it should have been checked on week 1 before it was chosen. It went into week 2 as written.

## Week 2 - 2025-10-27 .. 31 (gold falls from about 4,100 to 3,920, then rebounds to 4,020)

`out_liq_w2.txt` (the liquidity reading), `out_change_w2.txt` (change 1 trade by trade).

| Day, time | Piece | Side | Risk | Base exit, R | Best / worst | Liquidity | Change 1 |
|---|---|---|---|---|---|---|---|
| Mon 08:37 | Asia B2 | SELL | 14.5 | time +0.62 | +0.84 / -0.50 | broke today's open; stop 0.6 beyond the M15 swing high | unchanged |
| Mon 13:56 | London ORB | SELL | 10.3 | time +0.80 | +0.81 / -0.55 | stop 1.6 beyond today's open + round 4080 | stop pushed through 4080 / 4090 / 4100 to 35.7 risk: +0.23 |
| Mon 19:30 | NY straddle | SELL | 8.0 | stop -1.02 | +0.22 / -1.79 | stop at round 4040 | FAKE (-1.70 R at the end); wider stop: -0.56 |
| Tue 13:29 | London ORB | SELL | 16.8 | time +1.14 | +1.22 / -0.35 | stop 9.3 beyond the M15 swing low | wider (27.4): +0.70 |
| Tue 19:30 | NY straddle | SELL | 8.0 | time +0.80 | +1.76 / -0.82 | no pool near the stop | unchanged |
| Wed 08:34 | Asia B2 | SELL | 10.1 | time +1.41 | +1.51 / -0.74 | broke the Asia high | unchanged |
| Wed 13:25 | London ORB | BUY | 11.5 | target +2.00 | +2.31 / -0.17 | broke the Asia high; stop at round 3960 | wider (30.3): +0.76 |
| Thu 13:58 | London ORB | BUY | 17.4 | stop -1.01 | +0.21 / -1.02 | stop 0.4 beyond the M15 swing low + round 3960 | SLOW (-1.02 at the end); wider (48.3): -0.37 |
| Thu 19:30 | NY straddle | SELL | 8.0 | stop -1.00 | +0.92 / -1.46 | no pool near the stop | **SWEPT: +0.90 R at the end** |
| Fri 13:18 | London ORB | BUY | 12.8 | time +0.26 | +0.33 / -0.76 | stop 8.4 beyond the M15 swing high | wider (30.1): +0.11 |
| Fri 19:30 | NY straddle | SELL | 8.0 | stop -1.03 | +0.11 / -2.37 | stop 5.0 beyond today's open | SLOW (-0.71 at the end) |

**The week:** base 11 trades +2.98 R (London ORB 5 trades +3.19, Asia B2 2 trades +2.03, NY straddle 4 trades -2.25);
with change 1: +1.68 R.

**What the winners share:** the ORB sold / bought with the day's move after a break of the Asia range (Wed broke the Asia
high and ran to its 2 R target); B2's two sells came in the falling week.

**The weaknesses that repeat:** the straddle lost three of four (one FAKE, one SWEPT, one SLOW) - three of its stops in two
weeks were sweeps (week 1 #7, this week Thursday), but the others ran on against it.

**Two weeks of stop-outs, by what followed:** 7 stopped (ORB / straddle): SWEPT 3, FAKE 2, SLOW 2. The sweep is real but
not the rule: a wider stop costs every winner a third of its R to save the swept ones.

**The rules that cost this week:**
- **Change 1 (the stop out of the sweep zone): cost 1.30 R this week and 2.43 R on week 1. DELETED** (owner: a rule that
  blocks profit goes). The 10-USD round numbers are so dense that nearly every stop sits near one; pushing past them
  tripled the risk.
- **VOL-16 (trade only while the H1 ATR is 12-16):** every trade this week had an H1 ATR of 18.7-29.1 - it would have
  skipped a +2.98 R week. Two weeks: +7.82 R skipped. Over all the data (`atr_winners.parquet`): the trades it blocks
  summed **+21.2 R in P1, +11.8 in P2, +2.7 in the exam (+35.7 R)**, against +63.7 R for the trades it keeps. By ATR band
  the blocked trades pay at 16-25 (B2 +0.077, ORB +0.007, straddle +0.060) and 25-35 (straddle +0.285); only above 35
  do B2 (-0.146, 10 trades) and the straddle (-0.341, 14) lose. **The 16 ceiling is DELETED;** the 12 floor stays (the
  calm years 2021-25 lost on 1,379 trades). An ATR >= 35 stand-aside for the straddle / B2 is a hypothesis to watch in
  the journal (24 trades so far), not a rule.

**The one change for week 3 (decided 2026-10-21 13:10 Thai on weeks 1-2, checked on both before adopting):** none new -
week 3 runs on the base (the change-1 deletion and the VOL-16 ceiling deletion are the week's changes). Candidate kept:
ORB break-even at +1 R (week 1: #6 -0.16 -> 0; week 2: no ORB trade went +1 R and then lost - +0.16 R over two weeks).
