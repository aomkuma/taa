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

## Week 3 - 2025-11-03 .. 07 (gold ranges 3,930-4,020; the US shutdown: no 08:30 release all week)

The rules in force: the base PLAN-1 (change 1 deleted), the ATR floor of 12 tracked. `out_liq_w3.txt`. New York is on
winter time from 2025-11-02, so the straddle is at 20:30 Thai.

| Day, time | Piece | Side | Risk | Exit, R | Best / worst | H1 ATR | Liquidity / what happened |
|---|---|---|---|---|---|---|---|
| Mon 07:18 | Asia B2 | SELL | 18.0 | structure -0.56 | +0.04 / -0.58 | 19.3 | sold the break of yesterday's low and the Asia low - never ran |
| Mon 13:20 | London ORB | BUY | 7.1 | time -0.29 | +0.88 / -0.59 | 20.3 | +0.88 R at 14:04, then gave it back |
| Tue 07:05 | Asia B2 | SELL | 8.9 | target +1.13 | +1.13 / -0.90 | 15.9 | stop 0.4 beyond the M15 swing high (not taken) |
| Tue 08:33 | Asia B2 | SELL | 14.3 | structure -0.19 | +0.31 / -0.71 | 15.0 | the morning's second B2 trade |
| Tue 13:19 | London ORB | BUY | 9.4 | time +1.55 | +1.55 / -0.81 | 15.0 | |
| Wed 08:05 | Asia B2 | BUY | 15.0 | structure -0.15 | +0.35 / -0.39 | 17.7 | bought the break of today's open |
| Wed 08:55 | Asia B2 | SELL | 13.3 | structure -0.57 | +0.13 / -0.60 | 17.7 | 50 minutes later the other way: both lost |
| Wed 13:25 | London ORB | BUY | 8.7 | time -0.61 | +0.35 / -0.77 | 15.7 | |
| Thu 13:45 | London ORB | SELL | 5.6 | stop -1.06 | +0.28 / **-4.55** | **10.1** | sold the break of the M15 swing low with a 5.6-USD stop: FAKE, ran -3.82 R on |
| Fri 08:10 | Asia B2 | BUY | 9.8 | time +0.52 | +0.67 / -0.19 | 13.1 | broke the Asia high |
| Fri 13:23 | London ORB | BUY | 5.3 | target +2.00 | +2.32 / -0.22 | 11.8 | broke the Asia high - ran to the target |
| Fri 20:30 | NY straddle | SELL | 8.0 | time -0.37 | +0.37 / -0.65 | 11.4 | the only trigger of the week (no release Mon-Thu: the straddle never fired) |

**The week:** 12 trades, +1.40 R (London ORB 5 trades +1.59, Asia B2 6 trades +0.18, NY straddle 1 trade -0.37).

**What the winners share:** the ORB's and B2's winners bought / sold WITH a break of the Asia range in the session's
direction (Fri: both broke the Asia high and ran; Tue's B2 sold under it). The losers broke smaller things (today's open,
an M15 swing).

**The weaknesses that repeat:**
- **Asia B2 trades twice a morning and flips:** Tue's second trade -0.19, Wed's buy then sell -0.15 / -0.57. Weeks 1-3:
  the second B2 trade of a morning 2 trades, -0.76 R.
- **The ORB in a calm afternoon (ATR 10) took a 5.6-USD stop under a small swing** - a fake that ran -4.55 R.
- **No release, no straddle:** the evening piece is idle when the calendar is empty (this week: the shutdown).

**The rules that cost this week:**
- **The ATR floor of 12:** three trades had an ATR under 12 (Thu ORB -1.06, Fri ORB +2.00, Fri straddle -0.37): the
  floor would have cost +0.57 R this week. Evidence: one week against it, the calm years (1,379 losing trades) for it - kept,
  watched.
- **The ORB's 60-minute exit:** Mon +0.88 R at 14:04 finished -0.29. The break-even candidate (at +1 R) would not have
  changed it (it never reached +1 R): three weeks, +0.16 R.

**The one change for week 4 (decided 2026-10-21 13:12 Thai, checked on weeks 1-3):** Asia B2 takes at most one trade a
morning. On weeks 1-3 it removes 2 trades and adds +0.76 R; nothing else changes.

## Week 4 - 2025-11-10 .. 14 (gold climbs 4,017 -> 4,233, then drops to 4,058 on Friday)

The rules in force: the base, B2 one trade a morning (it took no second trade this week, so it changed nothing).
`out_liq_w4.txt`.

| Day, time | Piece | Side | Risk | Exit, R | Best / worst | H1 ATR | What happened |
|---|---|---|---|---|---|---|---|
| Mon 07:31 | Asia B2 | BUY | **4.1** | structure -0.82 | -0.06 / -0.82 | 14.3 | a 4-USD stop: never above water |
| Mon 13:21 | London ORB | BUY | 4.8 | time +0.49 | **+1.47 at 14:15** / -0.43 | 14.9 | gave back 1 R in the last minutes |
| Tue 08:29 | Asia B2 | BUY | 9.9 | structure -0.19 | +0.38 / -0.19 | 12.0 | |
| Tue 13:19 | London ORB | BUY | 8.4 | stop -1.01 | +0.32 / -1.06 | **11.5** | SLOW (-0.46 at the window's end) |
| Wed 13:21 | London ORB | BUY | 7.5 | time +1.61 | **+1.93** / -0.17 | 12.8 | |
| Thu 13:16 | London ORB | SELL | 7.4 | stop -1.00 | +0.13 / -1.02 | 19.7 | stop 0.4 above yesterday's high = the Asia high (in its sweep zone): SLOW, not swept |
| Thu 20:30 | NY straddle | SELL | 8.0 | time +0.13 | **+1.59 at 20:35** / -0.06 | 16.9 | the release ran 13 USD in 5 minutes, then came all the way back |
| Fri 13:17 | London ORB | SELL | 9.0 | time +1.25 | **+1.62** / -0.24 | 19.2 | |
| Fri 20:30 | NY straddle | BUY | 8.0 | stop -1.01 | +0.68 / -2.15 | 19.1 | SLOW |

**The week:** 9 trades, **-0.55 R** - the first losing week (London ORB 6 trades +1.34, NY straddle 2 trades -0.88, Asia B2
2 trades -1.01). Four weeks: 42 trades, +8.68 R (+0.21 a trade).

**The weakness that repeats - winners give back from their peak:** Mon ORB +1.47 -> +0.49, Wed ORB +1.93 -> +1.61, Fri
ORB +1.62 -> +1.25, Thu straddle +1.59 -> +0.13; week 1 #6 +1.59 -> -0.16. The ORB's 2 R target is rarely reached; its
60-minute exit often hands the run back.

**The check before deciding (`out_tp_w1_4.txt`, weeks 1-4 re-simulated on the ticks):**

| | base | take profit at 1.0 R | at 1.5 R |
|---|---|---|---|
| London ORB, 18 trades | +3.92 R | +2.04 | **+4.67** |
| NY straddle, 12 trades | +4.37 R | +0.34 | +3.34 |

The straddle's runs are worth more than a 1.5 R cap (week 1 had +3.41 / +1.91 / +1.90); the ORB's are not.

**The rules that cost this week:** the ATR floor of 12 would have skipped Tue's ORB (-1.01): it saved +1.01 R (weeks 3-4: net
+0.44 R for the floor). B2's one-a-morning: no effect this week.

**The one change for week 5 (decided 2026-10-21 13:15 Thai, checked on weeks 1-4: +0.75 R):** the London ORB's target is
1.5 R instead of 2 R (out at the target, the stop or 60 minutes, as before). The straddle keeps no target.

## Week 5 - 2025-11-17 .. 21 (gold ranges 4,010-4,110)

The rules in force: B2 one trade a morning, the ORB target 1.5 R. `out_rules_w5.txt`, `out_liq_w5.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H1 ATR | What happened |
|---|---|---|---|---|---|---|---|---|
| Mon 08:50 | Asia B2 | SELL | 7.3 | +0.32 | +0.32 | +1.42 / -0.45 | 28.3 | stop 0.1 above the M15 swing high (not taken) |
| Mon 13:33 | London ORB | BUY | 14.6 | +0.68 | +0.68 | +0.73 / -0.31 | 19.3 | |
| Tue 13:19 | London ORB | SELL | 9.5 | +0.16 | +0.16 | +0.88 / -0.54 | 21.0 | |
| Tue 20:30 | NY straddle | BUY | 8.0 | +1.74 | +1.74 | +2.36 / -0.42 | 18.3 | broke today's open and the M15 swing high |
| Wed 13:20 | London ORB | SELL | 6.7 | +0.53 | +0.53 | +1.01 / -0.58 | 15.8 | |
| Wed 20:30 | NY straddle | BUY | 8.0 | -0.13 | -0.13 | +0.75 / -0.70 | 14.8 | |
| Thu 07:52 | Asia B2 | SELL | 7.7 | -0.58 | -0.58 | +0.15 / -0.78 | 21.6 | **stop 1.5 above the Asia high: swept** |
| Thu 08:15 | Asia B2 | SELL | 13.5 | **+1.77** | **skipped** | **+4.21** / -0.13 | 19.8 | the same sell after the sweep: the real move |
| Thu 13:26 | London ORB | SELL | 14.1 | +0.18 | +0.18 | +0.33 / -0.94 | 22.5 | |
| Thu 20:30 | NY straddle | BUY | 8.0 | -1.34 | -1.34 | +0.70 / -2.92 | 20.9 | SLOW |
| Fri 07:35 | Asia B2 | SELL | 16.8 | +1.04 | +1.04 | +1.48 / -0.43 | 21.4 | |
| Fri 13:16 | London ORB | SELL | 16.5 | +1.01 | +1.01 | +1.40 / -0.19 | 18.6 | |
| Fri 20:30 | NY straddle | BUY | 8.0 | +1.18 | +1.18 | +1.38 / -0.48 | 19.9 | |

**The week:** base 13 trades **+6.55 R**; with the rules in force 12 trades +4.78 R. Five weeks (base): 55 trades,
+15.23 R (+0.28 a trade).

**What the winners share:** all five ORB trades won (small, by the 60-minute exit: none reached 1.5 R, so the new target
changed nothing); the straddle won when it broke a pool (Tue) or ran with the week.

**The lesson of Thursday morning:** the first sell's stop sat 1.5 USD above the Asia high - the sweep took it, then the
same idea ran +4.21 R. A second B2 trade in the SAME direction after a stop-out is a re-entry after the sweep; the losing
second trades of week 3 were a flip to the OTHER side (Wed: buy, then sell 50 minutes later) or a second same-side add
(Tue, -0.19).

**The rules that cost this week:**
- **B2 one trade a morning: cost 1.77 R this week; weeks 4-5 net -1.01 R. DELETED.**
- The ORB target 1.5 R: no effect this week (no ORB trade reached 1.5 R).
- The ATR floor of 12: no trade under 12 this week.

**The one change for week 6 (decided 2026-10-21 13:20 Thai, checked on weeks 1-5):** Asia B2's second trade of a morning
is taken only in the first trade's direction (no flip). On weeks 1-5 it skips one trade (week 3 Wed -0.57) and keeps
the re-entries: +0.57 R against the base.

## Week 6 - 2025-11-24 .. 28 (gold rises 4,055 -> 4,185; the H1 ATR falls from 22 to 8)

The rules in force: the ORB target 1.5 R, B2 no flip. `out_rules_w6.txt`, `out_liq_w6.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H1 ATR | What happened |
|---|---|---|---|---|---|---|---|---|
| Mon 07:34 | Asia B2 | BUY | 7.6 | -0.87 | -0.87 | +0.99 / -0.88 | 21.7 | stop 0.3 under the M15 swing low + round 4060 |
| Mon 08:10 | Asia B2 | SELL | 22.5 | +0.11 | skipped (flip) | +0.68 / -0.09 | 21.4 | the flip: this time it won a little |
| Mon 13:26 | London ORB | BUY | 10.2 | -0.25 | -0.25 | +0.24 / -0.41 | 19.0 | |
| Tue 07:36 | Asia B2 | SELL | 12.3 | +0.27 | +0.27 | +0.77 / -0.41 | 14.8 | |
| Tue 13:23 | London ORB | SELL | 6.4 | +0.56 | +0.56 | +0.98 / -0.12 | 15.3 | |
| Tue 20:30 | NY straddle | BUY | 8.0 | +0.15 | +0.15 | +0.51 / -0.57 | 16.2 | broke yesterday's high and the Asia high - did not run |
| Wed 13:16 | London ORB | SELL | 6.8 | +0.36 | +0.36 | +1.34 / -0.67 | 13.0 | |
| Wed 20:30 | NY straddle | SELL | 8.0 | +1.21 | +1.21 | +1.76 / -0.16 | 12.9 | sold back under yesterday's / the Asia high (a failed break above) |
| Thu 08:05 | Asia B2 | SELL | 6.9 | +1.41 | +1.41 | +2.80 / -0.06 | 12.1 | |
| Thu 13:22 | London ORB | BUY | 8.8 | +0.66 | +0.66 | +0.76 / -0.35 | **10.2** | |
| Fri 07:29 | Asia B2 | BUY | 5.0 | **+3.28** | **+3.28** | +4.00 / -0.17 | **7.9** | broke yesterday's high in a quiet Asia |
| Fri 13:22 | London ORB | BUY | 2.6 | +0.35 | **+1.50** | +1.63 / -0.23 | **10.7** | the 1.5 R target took it |

**The week:** base 12 trades +7.23 R; rules 11 trades **+8.27 R**. Six weeks (base) 67 trades +22.46 R; the rules in force
since week 4 add +0.14 (w4) -1.77 (w5) +1.04 (w6).

**What the winners share:** 10 of 12 trades finished above 0; the ORB's 1.5 R target paid on Friday; the B2 buys / sells
WITH the week's rise after breaking yesterday's high (Fri) paid the most.

**The rules that cost this week:**
- **The ATR floor of 12:** three trades had an ATR under 12 (Thu ORB 10.2 +0.66, Fri B2 7.9 +3.28, Fri ORB 10.7 +1.50 with
  the rules): the floor would have skipped **+5.44 R**. Weeks 3-6: it cost +0.57, saved +1.01, 0, cost +5.44 - **net -5.00 R.
  DELETED** (owner: a rule that blocks profit goes). The counter-evidence is the calm years 2021-25 (ORB / straddle lost
  on 1,379 trades with an ATR under 12) - those were a different, smaller gold (the daily range 20-40 USD, not 70-150):
  in the present a low-ATR hour is a pause inside a large market, not a calm gold. Watched in the journal.
- B2 no flip: skipped Mon's +0.11 (week 6 cost 0.11; weeks 1-6 net +0.46).
- The ORB 1.5 R target: +1.15 R this week (Fri); weeks 5-6 +1.15.

**The one change for week 7:** the ATR floor is deleted (above); nothing new is added this week.

## Week 7 - 2025-12-01 .. 05 (gold 4,220 -> 4,236 in a 4,180-4,265 range; the H1 ATR falls from 18 to 8)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate. `out_rules_w7.txt`, `out_liq_w7.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H1 ATR | What happened |
|---|---|---|---|---|---|---|---|---|
| Mon 07:24 | Asia B2 | SELL | 6.6 | -0.97 | -0.97 | +0.02 / -0.97 | 16.3 | sold right after price broke yesterday's high; stop 0.3 above the M15 swing high (sweep zone) |
| Mon 07:55 | Asia B2 | BUY | 15.0 | -0.56 | skipped (flip) | +0.05 / -0.59 | 16.3 | the flip, with the break |
| Mon 08:28 | Asia B2 | BUY | 16.2 | +0.92 | skipped (flip) | +1.30 / -0.02 | 16.9 | the re-entry with the break paid |
| Mon 13:24 | London ORB | SELL | 7.2 | -1.01 | -1.01 | -0.02 / -1.97 | 18.1 | sold back into the Asia range; stop at round 4230 - SLOW |
| Mon 20:30 | NY straddle | BUY | 8.0 | -1.00 | -1.00 | +0.63 / -1.54 | 16.9 | broke the M15 swing high, ran +0.63, then a FAKE |
| Tue 13:16 | London ORB | SELL | 2.9 | +2.00 | +1.50 | **+6.76** / -0.30 | 13.5 | broke the Asia low and ran 6.8 R - the target cut it |
| Wed 13:24 | London ORB | BUY | 4.8 | -1.01 | -1.01 | +0.15 / -1.26 | 15.6 | no pool broken; stop at round 4210 - SLOW |
| Wed 20:30 | NY straddle | BUY | 8.0 | +1.79 | +1.79 | +1.96 / -0.75 | 10.5 | broke the Asia high and the swing high |
| Thu 13:35 | London ORB | BUY | 7.5 | +0.63 | +0.63 | +1.10 / -0.37 | 14.1 | broke the M15 swing high |
| Thu 20:30 | NY straddle | SELL | 8.0 | -0.90 | -0.90 | +0.45 / -0.92 | 11.7 | no pool broken; time exit |
| Fri 13:25 | London ORB | BUY | 10.9 | -0.19 | -0.19 | +0.10 / -0.53 | **9.3** | no pool broken; time exit |
| Fri 20:30 | NY straddle | BUY | 8.0 | -0.20 | -0.20 | +0.36 / -0.77 | **8.2** | time exit |

**The week:** base 12 trades -0.50 R; rules 10 trades -1.35 R. Seven weeks (base) 79 trades +21.96 R (+0.28 R a trade).

**What the winners share:** each broke a pool in its direction (Tue the Asia low, Wed NY the Asia high, Thu the M15 swing
high, Mon 08:28 yesterday's high). The losers mostly broke none (Wed / Fri ORB, Thu NY) or faded a fresh break (Mon 07:24
sold just after yesterday's high was taken, Mon 13:24 sold back into the Asia range).

**Checked on weeks 1-7, the ORB by its entry's place:** a pool broken in the 15 minutes before: 17 trades +7.04 R (+0.41 a
trade); none broken: 16 trades +1.55 R (+0.10). On weeks 1-6 alone the no-pool ORBs made +2.75 R on 14 trades, so a filter
that skips them would have blocked profit - **not adopted**, watched.

**The rules that cost this week:**
- The ORB 1.5 R target: cost 0.50 R (Tue ran to +6.76 R). Weeks 5-7: +5.31 against +4.66 - it still pays (+0.65), stays.
- B2 no flip: cost 0.36 R (Mon: the first B2 faded the break, the flips went with it). Weeks 1-7 net +0.10 - stays, watched;
  if it costs again next week it goes.
- No ATR gate: the trades under 12 (Wed NY +1.79, Thu NY -0.90, Fri ORB -0.19, Fri NY -0.20) net +0.50 - the floor's
  deletion was right again.

**The one change for week 8:** none - no candidate passed the check on the prior weeks.

## Week 8 - 2025-12-08 .. 12 (gold 4,205 -> 4,340, a quiet start then Friday's rise; the H1 ATR 10-15)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate. `out_rules_w8.txt`, `out_liq_w8.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H1 ATR | What happened |
|---|---|---|---|---|---|---|---|---|
| Mon 07:37 | Asia B2 | BUY | 11.6 | -0.47 | -0.47 | +0.24 / -0.47 | 14.0 | broke the Asia high and today's open, no follow-through |
| Mon 08:16 | Asia B2 | BUY | 6.7 | -0.53 | -0.53 | +0.48 / -0.64 | 14.2 | same break; stop in the sweep zone of today's open and the M15 swing low |
| Tue 07:59 | Asia B2 | SELL | 4.2 | -1.00 | -1.00 | +0.23 / -1.00 | 11.5 | stop 2.6 beyond today's open (its sweep zone) - SLOW |
| Tue 13:33 | London ORB | BUY | 10.8 | -0.11 | -0.11 | +0.46 / -0.45 | 10.3 | no pool broken; time exit |
| Tue 20:30 | NY straddle | SELL | 8.0 | -0.25 | -0.25 | +0.46 / -0.50 | 9.8 | time exit |
| Wed 13:17 | London ORB | SELL | 3.7 | +0.24 | +0.24 | +1.27 / -0.42 | 9.9 | reached +1.27 R, gave it back to the time exit |
| Thu 13:27 | London ORB | BUY | 10.5 | -0.22 | -0.22 | +0.06 / -0.40 | 15.2 | no pool broken; time exit |
| Thu 20:30 | NY straddle | BUY | 8.0 | +0.62 | +0.62 | +0.90 / -0.85 | 11.9 | |
| Fri 13:29 | London ORB | BUY | 5.2 | +0.74 | +0.74 | +1.38 / -0.47 | 14.1 | reached +1.38 R, half given back |
| Fri 20:30 | NY straddle | BUY | 8.0 | +0.33 | +0.33 | +0.96 / -0.76 | 11.5 | broke the M15 swing high in Friday's rise |

**The week:** base 10 trades -0.65 R; rules the same (no rule acted). Eight weeks (base) 89 trades +21.31 R (+0.24 R a
trade): Asia B2 27 trades +4.52 (+0.17), London ORB 37 +9.23 (+0.25), NY straddle 25 +7.56 (+0.30).

**What happened:** a small-move week - only one stop-out (Tue B2); seven of ten trades ended on time with less than 1 R
either way. The three B2 losses all had their stop just beyond today's open or a round number (the sweep zone).

**Checked on weeks 1-7, the ORB target (same entry, stop, 60-minute exit):**

| Target | Weeks 1-7 (33 trades) | Week 8 |
|---|---|---|
| 0.75 R | +6.19 | +1.17 |
| 1.0 R | +7.82 | +1.67 |
| 1.25 R | +9.87 | +2.17 |
| **1.5 R (in force)** | **+9.98** | +0.66 |
| 2.0 R | +8.58 | +0.66 |
| none | +9.51 | +0.66 |

1.25 R would have paid +1.51 more this week, but on weeks 1-7 it equals 1.5 R (+9.87 vs +9.98): choosing it from one week
is fitting to that week - **not changed**. 1.25-1.5 is a flat top, so either is safe; watched.

**The rules that cost this week:** none acted (no B2 flip, no ORB reached 1.5 R; no ATR gate).

**The one change for week 9:** none.

## Week 9 - 2025-12-15 .. 19 (gold 4,300-4,375 sideways after the previous Friday's rise; the H4 ATR contracting all week)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate. New journal field from this week: the H4 ATR's change
over the last 24 h (owner 2026-10-21: "is it the larger timeframe's ATR falling?"). `out_rules_w9.txt`, `out_liq_w9.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H4 ATR 24 h | What happened |
|---|---|---|---|---|---|---|---|---|
| Mon 13:47 | London ORB | BUY | 7.4 | -1.01 | -1.01 | +0.02 / -1.83 | +28% | bought the top of Asia's gap-up; stop in the M15 swing low's sweep zone |
| Tue 13:22 | London ORB | BUY | 6.1 | -0.41 | -0.41 | +0.57 / -0.85 | -4% | no pool broken; stop 2.7 beyond yesterday's low |
| Tue 20:30 | NY straddle | BUY | 8.0 | +1.11 | +1.11 | +1.13 / -0.55 | -3% | |
| Wed 08:35 | Asia B2 | BUY | 11.4 | -0.29 | -0.29 | +0.47 / -0.34 | -4% | |
| Wed 13:23 | London ORB | SELL | 6.3 | +1.54 | +1.50 | +1.66 / -0.38 | -11% | sold back under yesterday's high (a failed break) |
| Wed 20:30 | NY straddle | BUY | 8.0 | +1.48 | +1.48 | +1.74 / -0.06 | -9% | broke the M15 swing high |
| Thu 13:34 | London ORB | BUY | 5.3 | -1.02 | -1.02 | +0.32 / -1.14 | -4% | no pool broken - SWEPT (back to +0.04 at the end) |
| Thu 20:30 | NY straddle | BUY | 8.0 | +0.85 | +0.85 | +1.65 / -0.61 | -5% | |
| Fri 07:11 | Asia B2 | SELL | 6.2 | +1.41 | +1.41 | +1.59 / -0.31 | -7% | broke today's open and the swing low |
| Fri 08:17 | Asia B2 | BUY | 8.6 | -1.04 | skipped (flip) | -0.01 / -1.04 | -7% | the flip: stop in the Asia low's sweep zone |
| Fri 08:29 | Asia B2 | SELL | 16.6 | -0.73 | -0.73 | +0.14 / -0.97 | -7% | |
| Fri 13:16 | London ORB | BUY | 4.3 | -1.03 | -1.03 | +0.19 / -1.62 | -1% | no pool broken |

**The week:** base 12 trades +0.87 R; rules 11 trades **+1.88 R**. Nine weeks (base) 101 trades +22.18 R (+0.22 a trade).

**What happened:** the NY straddle won all three; the ORB lost four of five - three of them broke no pool while the H4 ATR
was contracting.

**Checked on weeks 1-9, the ORB by the pool break and the H4 ATR (the owner's question):**

| ORB | H4 ATR contracting | H4 ATR expanding |
|---|---|---|
| a pool broken | 12 trades **+8.17** (+0.68) | 8 trades -0.36 |
| no pool broken | 12 trades **-2.08** (-0.17) | 10 trades +1.58 |

The NY straddle and Asia B2 show no such loss (straddle no pool + contracting 7 trades +0.35; B2 no pool + contracting
+1.87). Skipping the ORB without a pool break in a contracting H4: weeks 1-6 it would have cost 0.68, weeks 7-9 saved 2.76
- net +2.08 R on weeks 1-9. It follows the owner's principle (an unsuitable phase = only the surest signals, not none).

**The rules that cost this week:**
- B2 no flip: saved 1.04 R (Fri). Weeks 1-9 net +1.14 - stays.
- The ORB 1.5 R target: cost 0.04 (Wed). Weeks 5-9 still ahead.

**The one change for week 10 (from 2025-12-22, decided 2026-10-21 13:55 Thai):** when the H4 ATR contracted over the
last 24 h (closed H4 bars), the London ORB enters only if its 15 minutes before the decision broke a pool (yesterday's
high / low, the Asia high / low, today's open, the last M15 swing) in its direction. In `rules_week.py`.

## Week 10 - 2025-12-22 .. 26 (gold breaks to records 4,340 -> 4,525; Thu 25 closed for Christmas)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, and from this week the ORB in a contracting H4 needs a
pool break. `out_rules_w10.txt`, `out_liq_w10.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H4 ATR 24 h | What happened |
|---|---|---|---|---|---|---|---|---|
| Mon 13:17 | London ORB | BUY | 6.6 | +2.00 | skipped (new rule) | +2.27 / -0.83 | -2% | no pool in the last 15 minutes - Asia had already run 50 USD above yesterday's high / the Asia high (4,356) |
| Tue 13:51 | London ORB | BUY | 9.7 | +0.99 | +0.99 | +1.08 / -0.08 | +1% | |
| Wed 07:09 | Asia B2 | BUY | 13.5 | +0.01 | +0.01 | +0.41 / -0.37 | +10% | |
| Wed 08:25 | Asia B2 | BUY | 35.4 | -1.00 | -1.00 | +0.03 / -1.00 | +10% | a 35-USD risk at a record high |
| Wed 13:18 | London ORB | SELL | 6.9 | -1.01 | -1.01 | 0.00 / -1.77 | +24% | stop in today's open's sweep zone |
| Fri 07:10 | Asia B2 | BUY | 28.1 | +0.24 | +0.24 | +1.00 / -0.39 | +1% | |
| Fri 13:17 | London ORB | BUY | 5.7 | -1.01 | skipped (new rule) | +0.90 / -1.12 | -1% | SWEPT at round 4510 |
| Fri 20:30 | NY straddle | BUY | 8.0 | +0.62 | +0.62 | +1.04 / -0.63 | -3% | |

**The week:** base 8 trades +0.83 R; rules 6 trades -0.16 R. Ten weeks (base) 109 trades +23.01 R (+0.21 a trade).

**The rules that cost this week:**
- **The new ORB rule (contracting H4 + no pool):** skipped Mon +2.00 and Fri -1.01 - cost 0.99 R in its first week.
  Monday's lesson: "no pool broken in 15 minutes" also happens when price is ALREADY beyond every pool (a runaway to a
  record: the Asia session had taken yesterday's high by 50 USD). That is the opposite of a stuck market. Candidate
  refinement (checked next week on weeks 1-10 before any change): a price beyond the Asia range on the trade's side counts
  as a broken pool. The rule stays one more week; if it costs again it goes.
- B2 no flip, the 1.5 R target: did not act.

**The one change for week 11:** none yet (the refinement above is checked first).

**Checked after week 10 (weeks 1-10), the refinement:** of the 14 ORB trades the rule skips, the 6 already beyond the Asia
range on their side made -0.15 R, the 8 inside it -0.94 R. Re-admitting the "beyond" ones gains nothing - **not
adopted**. The rule as it stands skipped 14 trades for -1.09 R over weeks 1-10 (it saves 1.09 R net) - it stays.

## The account from week 11 (owner 2026-10-21: "start from 100 USD plus the profit we have made")

From now on every week also carries the account: `account.py` replays the rules-in-force trades from week 1 with 100 USD,
7.5 % of the current equity a trade (the owner's preset), at least 0.01 lot, in 0.01 steps (gold: 0.01 lot = 1 USD per
1-USD move). Weeks 1-10: 100.00 -> **283.12 USD** (worst trade -35.53, the deepest fall -37 %). At a 100-USD start the
0.01 minimum lot sets the risk (a 10-USD stop = 10 % of the account), so a week's R and its USD can differ (week 1: +4.84 R
but -4.23 USD: the losers had the wider stops).

## Week 11 - 2025-12-29 .. 2026-01-02 (gold falls from its record 4,550 to 4,275, then 4,375; Thu 1 Jan closed)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break.
`out_rules_w11.txt`, `out_liq_w11.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H4 ATR 24 h | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 07:27 | Asia B2 | SELL | 38.8 | -0.43 | -0.43 | +0.40 / -0.43 | +1% | 0.01 | -16.58 | 266.54 |
| Mon 13:27 | London ORB | SELL | 12.5 | +2.00 | +1.50 | **+4.19** / -0.12 | +1% | 0.01 | +18.71 | 285.24 |
| Mon 20:30 | NY straddle | SELL | 8.0 | +3.45 | +3.45 | +5.26 / -0.73 | +15% | 0.02 | +55.22 | 340.46 |
| Tue 13:16 | London ORB | SELL | 6.0 | +2.00 | +1.50 | +2.17 / -0.30 | +36% | 0.04 | +36.00 | 376.46 |
| Tue 20:30 | NY straddle | SELL | 8.0 | +0.34 | +0.34 | +1.86 / -0.06 | +24% | 0.03 | +8.10 | 384.56 |
| Wed 13:19 | London ORB | BUY | 27.5 | +1.03 | +1.03 | +1.11 / -0.16 | +19% | 0.01 | +28.29 | 412.85 |
| Wed 20:30 | NY straddle | SELL | 8.0 | -1.02 | -1.02 | -0.01 / -2.80 | +20% | 0.03 | -24.48 | 388.37 |
| Fri 13:17 | London ORB | SELL | 7.2 | -0.25 | skipped (new rule) | +0.15 / -0.93 | -17% | | | |
| Fri 20:30 | NY straddle | BUY | 8.0 | -1.04 | -1.04 | +0.11 / -1.86 | -17% | 0.03 | -24.87 | 363.50 |

**The week:** base 9 trades +6.08 R; rules 8 trades **+5.33 R, +80.39 USD**. Account **283.12 -> 363.50 USD**. Eleven weeks
(base) 118 trades +29.09 R; rules +26.78 R.

**What happened:** a year-end sell-off with the H4 ATR expanding (+15 to +36 %) - the ORB and the straddle sold with it.
The week's best trades broke no pool in their 15 minutes: price was already running away (the week-10 lesson again).

**The rules that cost this week:**
- The ORB 1.5 R target: cost 1.00 R (Mon ran to +4.19, Tue to +2.17). Since week 5 it is now -0.39 R net. Checked on
  weeks 1-10 by the H4 ATR: 1.5 R is the best target in both states (contracting: 1.0 +5.88, 1.5 +6.63, 2.0 +7.07,
  none +6.15; expanding: 1.0 +1.13, **1.5 +2.50**, 2.0 +1.20, none +2.25; all: 1.5 +9.13, none +8.39) - stays; watched.
- The ORB pool rule (contracting H4): saved 0.25 (Fri). Since week 10: -0.74 R net (cost 0.99, saved 0.25); weeks 1-11
  net it saves 1.34 - stays one more week.

**The one change for week 12:** none.

## Week 12 - 2026-01-05 .. 09 (gold 4,400 -> 4,470, a range week; the H4 ATR contracting mid-week)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break.
`out_rules_w12.txt`, `out_liq_w12.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H4 ATR 24 h | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 13:26 | London ORB | BUY | 14.4 | -0.43 | -0.43 | +0.04 / -0.65 | +8% | 0.01 | -6.25 | 357.25 |
| Mon 20:30 | NY straddle | BUY | 8.0 | +1.79 | +1.79 | +1.83 / -0.81 | +7% | 0.03 | +42.96 | 400.21 |
| Tue 13:26 | London ORB | BUY | 8.7 | +0.27 | skipped (pool rule) | +1.16 / -0.28 | -20% | | | |
| Wed 13:18 | London ORB | BUY | 7.1 | -1.00 | skipped (pool rule) | +0.04 / -2.62 | -8% | | | |
| Wed 20:30 | NY straddle | BUY | 8.0 | +1.02 | +1.02 | +1.05 / -0.81 | -17% | 0.03 | +24.54 | 424.75 |
| Thu 07:16 | Asia B2 | BUY | 6.9 | -0.68 | -0.68 | +0.01 / -0.68 | -12% | 0.04 | -18.72 | 406.03 |
| Thu 08:06 | Asia B2 | BUY | 11.8 | -0.29 | -0.29 | +0.38 / -0.44 | -12% | 0.02 | -6.92 | 399.11 |
| Thu 08:41 | Asia B2 | SELL | 10.8 | +0.11 | skipped (flip) | +0.71 / -0.08 | -12% | | | |
| Thu 13:32 | London ORB | BUY | 15.2 | +0.10 | +0.10 | +0.56 / -0.08 | -9% | 0.01 | +1.48 | 400.59 |
| Thu 20:30 | NY straddle | SELL | 8.0 | +0.99 | +0.99 | +1.25 / -0.51 | 0% | 0.03 | +23.85 | 424.44 |
| Fri 07:21 | Asia B2 | SELL | 7.2 | +0.70 | +0.70 | +1.31 / -0.18 | +5% | 0.04 | +20.08 | 444.52 |
| Fri 08:06 | Asia B2 | SELL | 10.8 | -0.43 | -0.43 | +0.38 / -0.51 | +5% | 0.03 | -13.98 | 430.54 |
| Fri 13:27 | London ORB | BUY | 5.5 | -0.37 | -0.37 | +1.06 / -0.51 | +3% | 0.05 | -10.10 | 420.44 |
| Fri 20:30 | NY straddle | SELL | 8.0 | -1.04 | -1.04 | +1.17 / -2.92 | -1% | 0.03 | -25.05 | 395.39 |

**The week:** base 14 trades +0.73 R; rules 11 trades **+1.35 R, +31.89 USD**. Account **363.50 -> 395.39 USD**. Twelve
weeks (base) 132 trades +29.82 R; rules +28.13 R.

**What happened:** the NY straddle carried the week (+2.76 R on four); Friday's (the US jobs report) whipsawed: +1.17 R at
once, then -2.92 R (FAKE). The B2 buys of Thursday both had their stop in a sweep zone (today's open; the Asia low).

**The rules that cost this week:**
- The ORB pool rule: saved 0.73 R (skipped Tue +0.27, Wed -1.00). Since week 10: -0.01 R net (about even); weeks 1-12 it
  saves 2.07 R - stays.
- B2 no flip: cost 0.11 R (Thu). Weeks 1-12 net +1.03 - stays.
- The ORB 1.5 R target: did not act.

**The one change for week 13:** none.

## Week 13 - 2026-01-12 .. 16 (gold to new records 4,560 -> 4,640, then 4,590; the end of learning part 1)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break.
`out_rules_w13.txt`, `out_liq_w13.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H4 ATR 24 h | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 07:17 | Asia B2 | BUY | 21.5 | +1.24 | +1.24 | +2.06 / -0.02 | -9% | 0.01 | +26.58 | 421.97 |
| Mon 13:16 | London ORB | SELL | 9.7 | -1.01 | -1.01 | +0.10 / -1.51 | +4% | 0.03 | -29.19 | 392.78 |
| Mon 20:30 | NY straddle | BUY | 8.0 | +1.03 | +1.03 | +1.58 / -0.19 | +11% | 0.03 | +24.66 | 417.44 |
| Tue 13:19 | London ORB | SELL | 4.3 | +2.00 | +1.50 | +3.29 / -0.75 | +1% | 0.07 | +44.73 | 462.17 |
| Tue 20:30 | NY straddle | BUY | 8.0 | +0.90 | +0.90 | +2.11 / -0.11 | -1% | 0.04 | +28.80 | 490.97 |
| Wed 13:59 | London ORB | BUY | 18.2 | -0.22 | -0.22 | +0.16 / -0.28 | +10% | 0.02 | -7.84 | 483.13 |
| Wed 20:30 | NY straddle | SELL | 8.0 | -0.79 | -0.79 | +0.69 / -0.96 | -4% | 0.04 | -25.16 | 457.97 |
| Thu 13:20 | London ORB | BUY | 15.6 | +0.20 | +0.20 | +0.27 / -0.57 | -14% | 0.02 | +6.26 | 464.23 |
| Thu 20:30 | NY straddle | SELL | 8.0 | +1.88 | +1.88 | +2.63 / -0.22 | -2% | 0.04 | +60.24 | 524.47 |
| Fri 13:41 | London ORB | SELL | 9.1 | -1.00 | skipped (pool rule) | +0.95 / -1.01 | -5% | | | |
| Fri 20:30 | NY straddle | BUY | 8.0 | +1.55 | +1.55 | +1.69 / -0.54 | -8% | 0.04 | +49.60 | 574.07 |

**The week:** base 11 trades +5.79 R; rules 10 trades **+6.29 R, +178.68 USD**. Account **395.39 -> 574.07 USD**.
Thirteen weeks (base) 143 trades +35.61 R; rules +34.42 R.

**What happened:** the NY straddle won four of five (+4.57 R) - every US open this week ran 1.6-2.6 R within 30 minutes.
The ORB was mixed: its losers sold into a market at records (Mon) or broke no pool (Fri, skipped).

**The rules that cost this week:**
- The ORB pool rule: saved 1.00 R (Fri). Since week 10: +0.99 R; weeks 1-13 it saves 3.07 R - stays.
- The ORB 1.5 R target: cost 0.50 (Tue ran to +3.29). Since week 5 it is -0.89 R. Re-checked on weeks 1-12: 1.0 +10.41,
  **1.5 +11.48**, 2.0 +11.62, 3.0 +10.89, none +9.84 - 1.5 and 2.0 are equal, both beat no target; stays.
- B2 no flip: did not act.

**The one change for week 14:** none.

## Week 14 - 2026-01-19 .. 23 (learning part 2 begins; gold surges 4,670 -> 4,935, the H1 ATR up to 37)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break.
`out_rules_w14.txt`, `out_liq_w14.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H4 ATR 24 h | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 13:24 | London ORB | BUY | 5.3 | -1.02 | -1.02 | +1.34 / -1.57 | +24% | 0.08 | -43.12 | 530.95 |
| Tue 08:35 | Asia B2 | BUY | 15.8 | +2.18 | +2.18 | +2.70 / -0.57 | -7% | 0.02 | +68.76 | 599.71 |
| Tue 13:39 | London ORB | SELL | 9.9 | -1.00 | skipped (pool rule) | +0.13 / -1.54 | -14% | | | |
| Tue 20:30 | NY straddle | BUY | 8.0 | +1.93 | +1.93 | +2.08 / -0.80 | -9% | 0.05 | +77.20 | 676.91 |
| Wed 13:23 | London ORB | BUY | 15.7 | -1.00 | -1.00 | +0.53 / -3.02 | +13% | 0.03 | -47.37 | 629.54 |
| Wed 20:30 | NY straddle | BUY | 8.0 | +1.12 | +1.12 | +1.24 / -0.39 | +3% | 0.05 | +44.95 | 674.49 |
| Thu 13:23 | London ORB | BUY | 10.3 | +0.64 | +0.64 | +1.04 / -0.51 | +37% | 0.04 | +26.32 | 700.81 |
| Thu 20:30 | NY straddle | SELL | 8.0 | +0.44 | +0.44 | +1.85 / -0.14 | +51% | 0.06 | +21.36 | 722.17 |
| Fri 20:30 | NY straddle | BUY | 8.0 | +0.63 | +0.63 | +0.85 / -0.83 | +4% | 0.06 | +30.12 | 752.29 |

**The week:** base 9 trades +3.91 R; rules 8 trades **+4.91 R, +178.22 USD**. Account **574.07 -> 752.29 USD** (the worst
trade so far: Wed's ORB, -47.37 USD). Fourteen weeks (base) 152 trades +39.52 R; rules +39.33 R.

**What happened:** the NY straddle won all five (+4.56 R). The ORB's two losers were FAKEs in a violent market (Mon ran
+1.34 R first, Wed fell to -3.02 R) - both with the H4 ATR expanding.

**Checked on weeks 1-13, the ORB stop against the H1 ATR (were the FAKEs too tight?):** stop under 0.3 H1 ATR 5 trades
+5.32 R; 0.3-0.5: 23 trades -3.05; 0.5-0.75: 20 trades +6.47; above: 12 trades +2.86. No order (the tightest paid most) -
no rule.

**The rules that cost this week:** the ORB pool rule saved 1.00 R (Tue). Since week 10: +1.99 R. The 1.5 R target and
B2 no flip did not act.

**The one change for week 15:** none.

## Week 15 - 2026-01-26 .. 30 (the blow-off: gold 5,080 -> 5,590 on Thursday, then a crash to 5,025 on Friday; the H1 ATR 27 -> 110)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break.
`out_rules_w15.txt`, `out_liq_w15.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H1 ATR | H4 ATR 24 h | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mon 13:38 | London ORB | BUY | 15.4 | +0.54 | +1.50 | +1.84 / -0.58 | 26.6 | -10% | 0.03 | +69.48 | 821.77 |
| Mon 20:30 | NY straddle | SELL | 8.0 | +0.11 | +0.11 | +1.84 / -0.84 | 27.1 | -9% | 0.07 | +5.88 | 827.65 |
| Tue 13:25 | London ORB | BUY | 11.1 | -0.04 | -0.04 | +0.63 / -0.80 | 38.5 | +10% | 0.05 | -2.45 | 825.20 |
| Wed 13:20 | London ORB | BUY | 12.7 | -1.00 | -1.00 | +1.30 / -1.03 | 30.5 | +15% | 0.04 | -50.92 | 774.28 |
| Wed 20:30 | NY straddle | BUY | 8.0 | -1.01 | -1.01 | +0.16 / -3.42 | 28.0 | +11% | 0.07 | -56.35 | 717.93 |
| Thu 13:22 | London ORB | BUY | 29.5 | -1.00 | -1.00 | +0.12 / -1.29 | 62.2 | +22% | 0.01 | -29.58 | 688.35 |
| Thu 20:30 | NY straddle | SELL | 8.0 | -1.02 | -1.02 | +2.09 / -1.72 | 60.7 | +35% | 0.06 | -48.84 | 639.51 |
| Fri 13:17 | London ORB | SELL | 32.9 | -0.04 | -0.04 | +1.46 / -0.78 | 110.6 | +78% | 0.01 | -1.46 | 638.05 |
| Fri 20:30 | NY straddle | SELL | 8.0 | -1.01 | -1.01 | **+3.99** / -3.01 | 95.6 | +87% | 0.05 | -40.40 | 597.65 |

**The week:** base 9 trades -4.48 R; rules 9 trades **-3.52 R, -154.64 USD**. Account **752.29 -> 597.65 USD** (-21 %; the
worst trade so far: Wed's straddle, -56.35 USD). Fifteen weeks (base) 161 trades +35.04 R; rules +35.81 R.

**What happened:** a market three to eight times its usual size. The straddle's fixed 8-USD stop was 0.08-0.3 H1 ATR -
noise: Thursday's ran +2.09 R first and Friday's +3.99 R, both were swept (SWEPT: back above 0 by the end) and stopped.
No ORB / straddle stop sat beyond a pool; the stops were simply inside the noise.

**Checked on weeks 1-14, the straddle's stop = max(8 USD, k x H1 ATR) (it changes only the days the ATR is above 32):**

| Stop | Weeks 1-14 (46 trades) | Week 15 |
|---|---|---|
| 8 USD (in force) | +24.82 | -2.93 |
| max(8, 0.25 H1 ATR) | +25.04 | -1.48 |
| max(8, 0.4 H1 ATR) | +24.60 | -0.54 |
| max(8, 0.6 H1 ATR) | +19.19 | -0.69 |

0.25 costs nothing on the prior weeks (it touches one trade there) and is the smallest step; 0.4 would suit week 15 best,
but choosing it from this week alone is fitting to it.

**The rules that cost this week:** the ORB 1.5 R target paid +0.96 (Mon). The pool rule did not act (the H4 expanding).

**The one change for week 16 (from 2026-02-02, decided 2026-10-21 17:15 Thai):** the NY straddle's stop is
max(8 USD, 0.25 x H1 ATR) from the fill. In `rules_week.py` (R and the account's risk on the new stop).

## Week 16 - 2026-02-02 .. 06 (after the crash: gold 4,500 -> 5,050 -> 4,850; the H1 ATR 37-135)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break, and
new this week the straddle's stop max(8 USD, 0.25 H1 ATR). `out_rules_w16.txt`, `out_liq_w16.txt`.

| Day, time | Piece | Side | Base risk | Base R | Rules R | Best / worst (base) | H1 ATR | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 13:21 | London ORB | SELL | 66.1 | -0.47 | **+1.50** | +1.59 / -0.81 | 135.5 | 0.01 | +99.14 | 696.79 |
| Mon 20:30 | NY straddle | SELL | 8.0 (rules 31.3) | **+3.87** | +0.99 | +8.45 / -0.60 | 125.2 | 0.01 | +30.94 | 727.73 |
| Tue 13:18 | London ORB | BUY | 36.0 | +0.97 | +0.97 | +1.15 / -0.13 | 72.1 | 0.01 | +34.93 | 762.66 |
| Tue 20:30 | NY straddle | BUY | 8.0 (14.6) | -1.00 | -1.01 | +1.77 / -1.98 | 58.4 | 0.03 | -44.19 | 718.47 |
| Wed 07:19 | Asia B2 | BUY | 58.2 | +0.91 | +0.91 | +0.98 / -0.48 | 48.5 | 0.01 | +52.88 | 771.35 |
| Wed 13:16 | London ORB | SELL | 29.6 | -1.00 | -1.00 | +0.05 / -1.00 | 49.4 | 0.01 | -29.63 | 741.72 |
| Wed 20:30 | NY straddle | BUY | 8.0 (9.2) | -1.00 | -1.00 | +1.48 / -2.29 | 36.8 | 0.06 | -55.20 | 686.52 |
| Thu 13:27 | London ORB | BUY | 45.2 | +0.29 | skipped (pool rule) | +0.38 / -0.55 | 68.1 | | | |
| Thu 20:30 | NY straddle | SELL | 8.0 (15.5) | -1.74 | -1.00 | +3.45 / -2.53 | 62.0 | 0.03 | -46.62 | 639.90 |
| Fri 13:18 | London ORB | SELL | 39.6 | +0.39 | skipped (pool rule) | +0.94 / -0.14 | 63.6 | | | |
| Fri 20:30 | NY straddle | BUY | 8.0 (14.2) | +2.18 | +1.23 | +3.30 / -0.06 | 56.8 | 0.03 | +52.38 | 692.28 |

**The week:** base 11 trades +3.39 R; rules 9 trades **+1.58 R, +94.62 USD**. Account **597.65 -> 692.28 USD**. Sixteen
weeks (base) 172 trades +38.43 R; rules +37.39 R. Mon's ORB: a 66-USD stop at the 0.01 minimum lot = 11 % of the account.

**The rules that cost this week:**
- **The wider straddle stop (new this week): cost 3.10 R** (the straddles +2.31 base, -0.79 with it). Why: risk is a fixed
  share of the account, so a wider stop shrinks every winner in R (Mon +3.87 -> +0.99) while the sweeps still reached the
  wider stops (Tue, Wed, Thu stopped either way). Weeks 1-16 together: +0.22 (1-14) +1.45 (15) -3.10 (16) = **-1.43 R.
  DELETED** - one week of evidence chose it, the next week undid it.
- The ORB 1.5 R target: paid +1.97 (Mon). The ORB pool rule: cost 0.68 (Thu +0.29, Fri +0.39). Since week 10: +1.31 R net.

**The one change for week 17:** the straddle's stop goes back to 8 USD (the deletion above); nothing new.

## Week 17 - 2026-02-09 .. 13 (gold settles 4,960-5,075; the H1 ATR 20-45)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break; the
straddle's stop back at 8 USD. `out_rules_w17.txt`, `out_liq_w17.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H1 ATR | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 08:36 | Asia B2 | SELL | 35.3 | -0.10 | -0.10 | +0.81 / -0.41 | 33.9 | 0.01 | -3.70 | 688.58 |
| Mon 13:16 | London ORB | SELL | 14.6 | +1.26 | skipped (pool rule) | +1.50 / -0.62 | 33.7 | | | |
| Mon 20:30 | NY straddle | BUY | 8.0 | -1.01 | -1.01 | +1.00 / -1.47 | 36.8 | 0.06 | -48.54 | 640.04 |
| Tue 07:36 | Asia B2 | SELL | 21.2 | +0.10 | +0.10 | +0.91 / -0.29 | 31.6 | 0.02 | +4.24 | 644.28 |
| Tue 13:18 | London ORB | SELL | 12.2 | +0.19 | skipped (pool rule) | +1.18 / -0.50 | 29.7 | | | |
| Tue 20:30 | NY straddle | BUY | 8.0 | +1.34 | +1.34 | +2.33 / -0.05 | 28.5 | 0.06 | +64.56 | 708.84 |
| Wed 07:17 | Asia B2 | SELL | 15.5 | -0.83 | -0.83 | +0.04 / -0.87 | 27.5 | 0.03 | -38.76 | 670.08 |
| Wed 08:33 | Asia B2 | SELL | 15.1 | -0.51 | -0.51 | -0.02 / -0.55 | 27.4 | 0.03 | -23.22 | 646.86 |
| Wed 13:17 | London ORB | BUY | 8.8 | +0.67 | +0.67 | +1.28 / -0.70 | 22.8 | 0.05 | +29.35 | 676.21 |
| Wed 20:30 | NY straddle | SELL | 8.0 | +0.84 | +0.84 | **+6.54** / -0.07 | 25.9 | 0.06 | +40.38 | 716.59 |
| Thu 07:12 | Asia B2 | SELL | 16.7 | +0.15 | +0.15 | +0.40 / -0.72 | 36.6 | 0.03 | +7.26 | 723.85 |
| Thu 08:38 | Asia B2 | BUY | 17.4 | -0.33 | skipped (flip) | +0.15 / -0.36 | 36.1 | | | |
| Thu 13:25 | London ORB | SELL | 14.4 | +0.17 | +0.17 | +0.99 / -0.33 | 24.1 | 0.03 | +7.44 | 731.29 |
| Thu 20:30 | NY straddle | SELL | 8.0 | -1.00 | -1.00 | -0.05 / -2.90 | 20.0 | 0.06 | -48.24 | 683.05 |
| Fri 08:49 | Asia B2 | BUY | 23.3 | -0.49 | -0.49 | +0.11 / -0.60 | 42.1 | 0.02 | -23.02 | 660.03 |
| Fri 13:35 | London ORB | BUY | 16.0 | +0.69 | +0.69 | +0.90 / -0.69 | 45.1 | 0.03 | +33.00 | 693.03 |
| Fri 20:30 | NY straddle | BUY | 8.0 | +1.61 | +1.61 | +3.28 / -0.47 | 29.1 | 0.06 | +77.28 | 770.31 |

**The week:** base 17 trades +2.73 R; rules 14 trades **+1.61 R, +78.03 USD**. Account **692.28 -> 770.31 USD**.
Seventeen weeks (base) 189 trades +41.16 R; rules +39.00 R.

**What happened:** Asia B2 lost five of seven small (-2.01 R): in this market its stops (15-35 USD) were inside the
morning's noise. Wednesday's straddle reached +6.54 R in its first minute and gave most of it back by 09:00 New York.

**The rules that cost this week:**
- **The ORB pool rule: cost 1.45 R** (Mon +1.26, Tue +0.19), the second week in a row. Since week 10 (in force): -0.14 R.
  Checked on weeks 1-17: the 23 trades it skips sum -1.94 R (it still saves 1.94); by the H1 ATR: up to 15 -0.84 (10),
  15-25 -3.23 (9), 25-40 +1.45 (2), above 40 +0.68 (2). The four it cost in the big market are too few for a rule - it
  stays, watched; if week 18 costs again it goes.
- B2 no flip: saved 0.33 (Thu). The 1.5 R target: did not act.

**The one change for week 18:** none.

## Week 18 - 2026-02-16 .. 20 (gold 4,890-5,035, back and forth; Mon a US holiday)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break.
`out_rules_w18.txt`, `out_liq_w18.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | H1 ATR | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 07:04 | Asia B2 | SELL | 25.8 | -0.35 | -0.35 | +0.02 / -0.56 | 30.1 | 0.02 | -18.08 | 752.23 |
| Mon 13:18 | London ORB | SELL | 8.2 | -1.03 | -1.03 | -0.05 / -2.30 | 27.8 | 0.06 | -50.52 | 701.71 |
| Mon 20:30 | NY straddle | BUY | 8.0 | +0.06 | +0.06 | +0.24 / -0.91 | 21.2 | 0.06 | +3.00 | 704.71 |
| Tue 07:45 | Asia B2 | SELL | 31.8 | +2.84 | +2.84 | +3.49 / -0.03 | 14.0 | 0.01 | +90.20 | 794.91 |
| Tue 13:16 | London ORB | SELL | 7.0 | -1.01 | skipped (pool rule) | +0.03 / -3.89 | 25.1 | | | |
| Tue 20:30 | NY straddle | BUY | 8.0 | -1.00 | -1.00 | +0.27 / **-6.51** | 29.0 | 0.07 | -56.14 | 738.77 |
| Wed 13:18 | London ORB | SELL | 8.6 | -1.00 | -1.00 | -0.01 / -1.98 | 22.8 | 0.06 | -51.60 | 687.17 |
| Wed 20:30 | NY straddle | BUY | 8.0 | -1.01 | -1.01 | +1.28 / -1.21 | 18.3 | 0.06 | -48.60 | 638.57 |
| Thu 08:46 | Asia B2 | BUY | 11.0 | -0.47 | -0.47 | +0.49 / -0.54 | 19.9 | 0.04 | -20.72 | 617.85 |
| Thu 13:20 | London ORB | BUY | 3.8 | +2.00 | +1.50 | **+5.70** / -0.82 | 15.4 | 0.12 | +67.86 | 685.71 |
| Thu 20:30 | NY straddle | SELL | 8.0 | -1.02 | -1.02 | +1.10 / -2.22 | 16.3 | 0.06 | -48.78 | 636.93 |
| Fri 07:12 | Asia B2 | BUY | 11.9 | +1.47 | +1.47 | +1.52 / -0.79 | 20.8 | 0.04 | +70.24 | 707.17 |
| Fri 13:22 | London ORB | BUY | 9.3 | -0.57 | skipped (pool rule) | +0.95 / -0.87 | 17.8 | | | |
| Fri 20:30 | NY straddle | BUY | 8.0 | -1.00 | -1.00 | +2.15 / -1.65 | 18.9 | 0.06 | -48.18 | 658.99 |

**The week:** base 14 trades -2.09 R; rules 12 trades **-1.01 R, -111.32 USD**. Account **770.31 -> 658.99 USD**.
Eighteen weeks (base) 203 trades +39.07 R; rules +37.99 R.

**What happened:** the straddle's worst week - four stops in a row (Tue-Fri), three of them FAKEs that ran the other way
(Tue to -6.51 R). Asia B2 carried the week (+3.49 R). Checked on weeks 1-18 with the bot's calendar tags: the straddle
made +0.37 a trade on days without a release (53 trades) and +0.18 with one (12) - "no release" is not why it lost; no rule.

**The rules that cost this week:**
- The ORB pool rule: saved 1.58 R (Tue -1.01, Fri -0.57). Since week 10: +1.44 R - stays.
- The ORB 1.5 R target: cost 0.50 (Thu ran to +5.70). B2 no flip: did not act.

**The one change for week 19:** none.

## Week 19 - 2026-02-23 .. 27 (gold climbs 5,150 -> 5,235; the H1 ATR 15-28)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break.
`out_rules_w19.txt`, `out_liq_w19.txt` (the full table of trades, lots and the account is in `account.py 2026-02-28 2026-02-23`).

| Piece | Trades (rules) | Rules R | Notes |
|---|---|---|---|
| Asia B2 | 5 (+1 skipped) | +1.24 | Fri +1.21 at its target; the skipped flip (Thu) made +0.43 |
| London ORB | 3 (+1 skipped) | +4.50 | all three at the 1.5 R target; Fri's skipped one was a FAKE (-1.01) |
| NY straddle | 4 | +0.98 | Tue's FAKE ran to -5.94 R (stopped at -1.08, a gap) |

**The week:** base 14 trades +5.62 R; rules 12 trades **+6.74 R, +333.55 USD**. Account **658.99 -> 992.54 USD** (the worst
trade so far: Tue's straddle, -60.27 USD). Nineteen weeks (base) 217 trades +44.69 R; rules +44.73 R - the rules now lead.

**The rules that cost this week:**
- The ORB 1.5 R target: +0.53 (Tue +1.36; Mon -0.50, Thu -0.33).
- The ORB pool rule: saved 1.01 (Fri). Since week 10: +2.45 R.
- B2 no flip: cost 0.43 (Thu). Weeks 1-19 net +0.93.

**The one change for week 20:** none.

## Weeks 20-26 - 2026-03-02 .. 04-17 (the end of learning part 2)

The rules in force: the ORB target 1.5 R, B2 no flip, no ATR gate, the ORB in a contracting H4 needs a pool break. Each
week's trades are in `out_rules_w20.txt` .. `out_rules_w26.txt` and `out_liq_w20.txt` .. `out_liq_w26.txt`. From week 21 the
NY straddle is at 19:30 Thai (US summer time). Run one week at a time (out of memory beside dev1's parity runs, retried).

| Week | Dates | Base trades | Base R | Rules trades | Rules R | USD | Account | Pool rule | 1.5 R target |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 03-02 .. 06 | 10 | -0.02 | 9 | +0.49 | -12.91 | 979.63 | saved 1.00 | -0.50 |
| 21 | 03-09 .. 13 | 11 | +1.24 | 7 | -1.45 | -113.04 | 866.59 | **cost 3.33** | +0.64 |
| 22 | 03-16 .. 20 | 9 | +1.04 | 9 | +0.54 | -2.83 | 863.75 | - | -0.50 |
| 23 | 03-23 .. 27 | 13 | -0.02 | 12 | +0.48 | -44.38 | 819.38 | saved 1.00 | -0.50 |
| 24 | 03-30 .. 04-03 | 12 | +3.87 | 9 | +3.91 | +253.71 | 1,073.09 | saved 0.54 | -0.50 |
| 25 | 04-06 .. 10 | 12 | +2.62 | 12 | +2.62 | +196.48 | 1,269.57 | - | - |
| 26 | 04-13 .. 17 | 14 | +3.12 | 12 | +5.17 | +441.41 | 1,710.98 | saved 1.06 | +0.99 |

**Weeks 20-26:** base +11.85 R, rules +11.76 R. B2 no flip acted once (week 24, a 0.00 trade).

**What happened:** weeks 20-23 the straddle stopped 13 times in 17 (the market in a range after February's crash); the
ORB carried them. Weeks 24-26 everything ran: the straddle +9.12 R, the account +891.60 USD. Week 21 was the pool rule's
worst (it skipped two ORBs that reached 2 R); weeks 1-26 it still saves +2.73 R (the 24 trades it skips sum -2.73 R).
No candidate change was found that also held on the prior weeks, so the rules stayed as they were from week 17 on.

## Twenty-six weeks (learning parts 1 + 2), the result

| | Trades | R | R a trade | Account (100 USD, 7.5 % a trade, min 0.01 lot) |
|---|---|---|---|---|
| Base (PLAN-1 as tested) | 298 | +56.54 | +0.190 | - |
| **Rules in force each week** | 265 | **+56.49** | **+0.213** | **100 -> 1,710.98 USD** (deepest fall -37 %, weeks 1-2; worst trade -121.80 USD) |

## Frozen for the exam (2026-10-21 19:15 Thai, before any exam reading of these rules)

The rules that go to the exam (2026-04-18 .. 2026-10-17, read once) and to the old years (2021-09 .. 2025-09, read once):
1. Asia B2 07-09 Thai at the owner's H1 levels as PLAN-1; its second trade of a morning only in the first's direction.
2. London ORB 13:00 Thai, 15-minute range on M1, stop at the range's other side, **target 1.5 R**, out after 60 minutes;
   **when the H4 ATR(14) changed by < +0.5 % over the last 6 closed H4 bars, it enters only if the 15 minutes before the
   decision broke a pool** (yesterday's high / low, the Asia high / low, today's open, the last M15 swing) in its direction.
3. NY 08:30 straddle every weekday: ±2 USD, stop 8 USD, out at 08:30 + 30 minutes, no target.
4. No ATR gate. One position at a time. Costs: the tick spread; slippage 0.
5. The account: 100 USD, 7.5 % of the equity a trade, at least 0.01 lot.
The reading: week by week as here, the total R a trade against the goal (+0.15), and the account. Pass = the exam's
rules R a trade >= +0.15. A fail is not fixed on the exam: any change is learned forward (from 2026-10-19).

## The exam of the frozen rules (read once, 2026-10-21 19:00 Thai; `exam_frozen.py --exam`, `out_exam_frozen.txt`)

| | Trades | R | R a trade |
|---|---|---|---|
| Base (PLAN-1 as tested) | 330 | +42.48 | +0.129 |
| **The frozen rules** | 282 | **+41.83** | **+0.148** |
| - Asia B2 | 97 | +13.58 | +0.140 |
| - London ORB | 84 | -0.49 | -0.006 |
| - NY straddle | 101 | +28.74 | +0.285 |

**Verdict: FAIL by 0.002** against the pre-registered +0.15 (the journal's rules lifted the plan from +0.129 to +0.148).
Each rule on the exam: B2 no flip **+2.24 R** (held), the ORB 1.5 R target **+1.66 R** (held), the ORB pool rule
**-4.55 R** on 37 trades (did not hold - on the exam the ORB days it skipped won). Not fixed on the exam: any change is
learned forward.

**The account (7.5 % a trade, min 0.01 lot):** from 100 USD -> 792.10 USD, but it fell to 22.05 USD in week 3 (-97 %; the
worst trade -243.04 USD later on); continued from the learning parts' 1,710.98 USD -> 11,548.03 USD (deepest fall -55 %).
26 weeks: 15 up, 11 down.

**What the exam says:** the NY straddle carries the plan in every period (learning +0.262, exam +0.285); Asia B2 is
small-positive; the London ORB is the piece that did not carry over (learning +0.168, exam +0.020 base, -0.006 with the rules). The old years are the second exam
(next, through the bot's tick backtest once Asia B2 is in the lane, so one engine reads all of it).

**The owner's bar (2026-10-21 ~19:30 Thai, said after this exam was read):** "0.10-0.15 R a trade is fine, as long as it is
profitable" - against that bar the frozen rules' exam (+0.148 on 282, positive) passes; against the pre-registered +0.15
it missed by 0.002. Both are recorded. The old years (2021-09 .. 2025-09) are already known to lose for every piece
(CHECKLIST 56 / 57 / 59: Asia B2 -0.115 on 834, the ORB / straddle always-on -0.036 on 1,300): the plan pays only in the
present's large gold. The next work is the switch: how large gold must be (a slow, days-long measure) for the plan to pay.

## The regime switch (frozen 2026-10-21 19:45 Thai; `regime_switch.py`, `out_regime_switch.txt`)

PLAN-1 trades only while **the D1 ATR(20) of the closed D1 bars is >= 60 USD**. Chosen on 2,312 trades of 2021-09 ..
2026-04 (the old years and the learning parts): by D1 ATR(20) <20 -0.280, 20-30 -0.122, 30-40 -0.139, 40-50 -0.081,
50-60 +0.013, **60-80 +0.203, >80 +0.136**. Outside the present the only old months at >= 60 (2025-04 .. 06, the tariff
months) made +0.112 on 98 trades. The learning parts and the exam never fell below 60 (their lowest 60.1 / 75.9 - only
the D1 size of the exam was read, not its trades), so the switch changes no result so far: it is the safety switch for
a calmer gold. **On 2026-10-18 the D1 ATR(20) was 75.9 and falling** - watched daily in the forward journal.

# Phase 2: the exam weeks journaled forward (owner 2026-10-21 ~20:30 Thai: "we adapt as we go, even live")

The exam (2026-04-18 .. 10-17) was read once with the rules frozen at week 26 (+0.148). From here its weeks are journaled
like weeks 1-26: each change is decided on the prior weeks only and applied to the next week. This is LEARNING, not proof
(the exam's totals are already known); the proof of the adapting process is the DEMO forward. The account from week 27:
**300 USD, 3 % a trade, at least 0.01 lot** (owner 2026-10-21). Run with `PLAN1_TRADES=plan1_trades_exam_s0_x0.parquet`
and `PLAN1_ACCOUNT=2026-04-18,300,3`.

## Week 27 - 2026-04-20 .. 24 (gold falls 4,830 -> 4,680; the H1 ATR 12-23)

The rules in force: the ORB target 1.5 R, B2 no flip, the ORB pool rule, the D1 ATR(20) >= 60 switch (on: 76-100).

| Day, time | Piece | Side | Base R | Rules R | Best / worst | Lots | Risk | USD | Account |
|---|---|---|---|---|---|---|---|---|---|
| Mon 13:27 | London ORB | SELL | -1.03 | -1.03 | +0.03 / -2.30 | 0.01 | 3.1% | -9.66 | 290.34 |
| Mon 19:30 | NY straddle | BUY | -1.02 | -1.02 | +0.20 / -1.10 | 0.01 | 2.8% | -8.15 | 282.19 |
| Tue 07:11 | Asia B2 | BUY | -0.80 | -0.80 | +0.17 / -0.80 | 0.01 | 3.4% | -7.73 | 274.46 |
| Tue 08:50 | Asia B2 | SELL | +0.83 | skipped (flip) | +1.35 / -0.06 | | | | |
| Tue 13:52 | London ORB | SELL | -1.01 | -1.01 | +0.14 / -1.15 | 0.01 | 5.6% | -15.64 | 258.82 |
| Tue 19:30 | NY straddle | SELL | -1.03 | -1.03 | +1.44 / -1.50 | 0.01 | 3.1% | -8.23 | 250.59 |
| Wed 14:01 | London ORB | BUY | -0.74 | -0.74 | +0.25 / -0.93 | 0.01 | 4.3% | -8.01 | 242.58 |
| Wed 19:30 | NY straddle | SELL | +0.80 | +0.80 | +0.97 / -0.45 | 0.01 | 3.3% | +6.39 | 248.97 |
| Thu 07:08 | Asia B2 | SELL | -1.01 | -1.01 | **+2.47** / -1.01 | 0.01 | 4.0% | -10.10 | 238.87 |
| Thu 08:22 | Asia B2 | SELL | -0.25 | -0.25 | +0.20 / -0.25 | 0.01 | 9.7% | -5.78 | 233.09 |
| Thu 08:55 | Asia B2 | SELL | +0.56 | +0.56 | +0.86 / -0.12 | 0.01 | 13.2% | +17.30 | 250.39 |
| Thu 13:16 | London ORB | SELL | -1.02 | -1.02 | +0.33 / -1.41 | 0.01 | 3.1% | -7.98 | 242.41 |
| Thu 19:30 | NY straddle | BUY | +0.54 | +0.54 | +0.93 / -0.53 | 0.01 | 3.3% | +4.34 | 246.75 |
| Fri 07:30 | Asia B2 | BUY | -0.61 | -0.61 | +0.25 / -0.75 | 0.01 | 8.1% | -12.21 | 234.54 |
| Fri 13:16 | London ORB | SELL | +0.05 | +1.50 | +1.62 / -0.21 | 0.01 | 3.4% | +11.95 | 246.49 |

**The week:** base 15 trades -5.72 R; rules 14 trades **-5.11 R, -53.51 USD**. Account **300.00 -> 246.49 USD** (-18 %).
At 300 USD every trade is at the 0.01 minimum lot: B2's wide stops reached 8-13 % of the account.

**What happened:** a falling week; the ORB's sells were stopped at round numbers / yesterday's low (sweep zones) and the
moves came after. Thu's first B2 reached +2.47 R and fell back to its stop.

**Checked on weeks 1-26, a B2 target (the same stop, exit at the base exit if not reached):** base +10.38 R; 1.0 R +3.89;
1.5 R +7.87; 2.0 R +9.68 - every target is worse on the prior weeks (week 27 alone would favour 2.0 R: +1.74 vs -1.27).
Not adopted (`b2_target_check.py`).

**The rules that cost this week:** B2 no flip cost 0.83 (Tue); the 1.5 R target paid +1.45 (Fri). The pool rule did not
act. **The one change for week 28:** none.

## Week 28 - 2026-04-27 .. 05-01 (gold falls 4,700 -> 4,560, then 4,600)

`out_rules_w28.txt`, `out_liq_w28.txt`, `out_acct_w28.txt` (every trade with its lots, risk and the account).

| Piece | Rules trades | Rules R | Notes |
|---|---|---|---|
| Asia B2 | 3 (+1 skipped) | -0.85 | the skipped flip (Tue 08:54) made +1.08 |
| London ORB | 4 (+1 skipped) | +1.20 | Thu at the 1.5 R target (it ran +3.32); the pool rule skipped Fri +0.80 |
| NY straddle | 5 | +1.37 | Tue's FAKE (-2.81 at worst) stopped at -1.04 |

**The week:** base 14 trades +4.07 R; rules 12 trades **+1.70 R, +12.08 USD**. Account **246.49 -> 258.57 USD**.

**The rules that cost this week:** B2 no flip **cost 1.08** (the second week in a row after 0.83) - weeks 1-28 it is now
**-0.98 R net: DELETED from week 29**. The pool rule cost 0.80 (weeks 1-28 it still saves 1.93 R - stays). The 1.5 R
target cost 0.50 (Thu).

**The one change for week 29:** the no-flip rule is deleted (a second B2 of the morning may go either way again).

## Week 29 - 2026-05-04 .. 08 (gold 4,540 -> 4,740 -> 4,700)

`out_rules_w29.txt`, `out_liq_w29.txt`, `out_acct_w29.txt`. Rules: base 13 trades -1.43 R; rules 10 trades **-2.33 R,
-36.52 USD**; account **258.57 -> 222.05 USD** (-26 % from 300). Asia B2 -1.25 (four trades, no flip rule now), the ORB
-1.08 (Fri: a 21.8-USD stop at the 0.01 lot = 8.7 % of the account), the straddle +0.01.

**The rules that cost this week:** the pool rule skipped three ORBs (-1.00, -0.11, +2.00): cost 0.89; weeks 1-29 it still
saves 1.04 R. The deletion bar used from here on, the same as for no flip: **a rule goes when its net over all prior
weeks turns negative.** The 1.5 R target did not act. **The one change for week 30:** none.

## Week 30 - 2026-05-11 .. 15

`out_rules_w30.txt`, `out_liq_w30.txt`, `out_acct_w30.txt`. Base 14 trades -0.46 R; rules 12 trades **-1.89 R, +7.40 USD**
(a B2 winner at the 0.01 lot carried 18.9 % of the account); account **222.05 -> 229.46 USD**. The straddle lost four of
five (-3.41 R); Asia B2 +0.02; the ORB +0.50.

**The rules that cost this week:** the pool rule skipped two ORB winners (+0.31, +0.62): cost 0.93; weeks 1-30 net
**+0.11 R** (about even). The 1.5 R target cost 0.50. **The one change for week 31:** none.

## Week 31 - 2026-05-18 .. 22

`out_rules_w31.txt`, `out_liq_w31.txt`, `out_acct_w31.txt`. Base 10 trades -1.95 R; rules 7 trades **+0.02 R, -3.70 USD**;
account **229.46 -> 225.76 USD**. The straddle +1.31 (Mon +2.32), Asia B2 -1.14, the ORB -0.14.

**The rules that cost this week:** the pool rule saved 1.97 R (skipped -1.01, -1.02, +0.06); weeks 1-31 net +2.08 R.
**The one change for week 32:** none.

## Week 32 - 2026-05-25 .. 29

`out_rules_w32.txt`, `out_liq_w32.txt`, `out_acct_w32.txt`. Base 10 trades +1.48 R; rules 8 trades **+2.67 R, +6.77 USD**;
account **225.76 -> 232.53 USD** (the straddle's +5.63 on Thu came at 0.01 lot: +45 USD; the losers were the same size).
The straddle +3.16, the ORB -0.57, Asia B2 +0.08.

**The rules that cost this week:** the pool rule saved 1.18 (weeks 1-32 net +3.26 R). The 1.5 R target paid +0.01.
**The one change for week 33:** none.

## The losers of weeks 27-32 studied (owner 2026-10-21 ~21:05 Thai: "if we learn from the journal, the numbers should differ")

Weeks 29-32 equalled the frozen run to the cent: the only change (no flip deleted) never acted, and the weekly reading had
become a rule-cost check only. Two ideas from the losers, each checked on weeks 1-26 first (`out_be_check.txt`,
`out_piece_momentum.txt`; base R, before the journal rules):

| Idea (from the losers) | Weeks 1-26 | Weeks 27-32 | Verdict |
|---|---|---|---|
| none (base) | +56.54 | -4.01 | |
| Break-even: the stop to the entry after +0.5 / 0.75 / 1.0 / 1.5 R (many losers first ran +1 R) | +30.44 / +39.00 / +47.58 / +53.16 | -4.84 / -1.85 / -2.81 / -3.10 | worse on 1-26 at every level - not adopted |
| A piece trades only if its last N weeks summed > 0 (N = 2 / 3 / 4 / 6 / 8) | +42.86 / +42.24 / +43.36 / +47.06 / +43.49 | -2.97 / -6.37 / -7.24 / -2.49 / -0.19 | worse on 1-26 for every N - not adopted |

**The lesson:** the plan's profit comes from the few trades that run far (+3 to +8 R). Every cut tried - a break-even, a
target on B2, standing a piece aside after losing weeks - removes more of those runs than it saves on the losers. The
losing weeks are the price of the runs; the learning so far says: keep the full stop, keep every piece trading, size so
the account survives the streaks.

## Week 33 - 2026-06-01 .. 05 (gold falls 4,540 -> 4,430; the H1 ATR 12-20) - weekly reports again (owner 2026-10-21)

The rules in force: the ORB target 1.5 R, the ORB pool rule, the D1 ATR(20) >= 60 switch (on). `out_rules_w33.txt`,
`out_liq_w33.txt`, `out_acct_w33.txt`.

| Day, time | Piece | Side | Risk | Base R | Rules R | Best / worst | Stop's place | Lots | USD | Account |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon 08:01 | Asia B2 | SELL | 6.9 | +1.25 | +1.25 | +1.26 / -0.39 | round 4540 | 0.01 | +8.61 | 241.14 |
| Mon 08:56 | Asia B2 | SELL | 6.8 | -1.02 | -1.02 | +0.49 / -1.02 | round 4530 | 0.01 | -6.94 | 234.20 |
| Mon 13:17 | London ORB | SELL | 6.7 | +0.70 | +1.50 | +1.71 / -0.46 | | 0.01 | +9.99 | 244.19 |
| Mon 19:30 | NY straddle | SELL | 8.0 | +0.06 | +0.06 | +0.68 / -0.92 | round 4510 | 0.01 | +0.46 | 244.65 |
| Tue 08:47 | Asia B2 | SELL | 12.1 | -0.31 | -0.31 | +1.20 / -0.37 | round 4490 | 0.01 | -3.79 | 240.86 |
| Tue 13:22 | London ORB | BUY | 11.4 | +0.81 | +0.81 | +1.16 / -0.19 | round 4520 | 0.01 | +9.22 | 250.08 |
| Tue 19:30 | NY straddle | SELL | 8.0 | +1.54 | +1.54 | +1.70 / -0.83 | | 0.01 | +12.34 | 262.42 |
| Wed 13:18 | London ORB | BUY | 11.4 | -1.02 | skipped (pool rule) | +0.35 / -1.13 | round 4460 | | | |
| Wed 19:30 | NY straddle | BUY | 8.0 | +0.64 | +0.64 | +1.52 / -0.86 | round 4450 | 0.01 | +5.16 | 267.58 |
| Thu 07:23 | Asia B2 | SELL | 16.0 | -0.30 | -0.30 | +0.38 / -0.33 | Asia high, swing high | 0.01 | -4.84 | 262.74 |
| Thu 13:22 | London ORB | SELL | 9.2 | +0.21 | +0.21 | +0.59 / -0.99 | | 0.01 | +1.97 | 264.71 |
| Thu 19:30 | NY straddle | BUY | 8.0 | +0.31 | +0.31 | +1.18 / -0.57 | yesterday's high | 0.01 | +2.49 | 267.20 |
| Fri 07:17 | Asia B2 | SELL | 13.7 | -1.02 | -1.02 | +0.12 / -1.02 | swing low | 0.01 | -13.95 | 253.25 |
| Fri 08:00 | Asia B2 | SELL | 8.0 | -1.03 | -1.03 | +0.75 / -1.03 | swing high | 0.01 | -8.30 | 244.95 |
| Fri 13:17 | London ORB | SELL | 10.1 | -1.00 | -1.00 | +0.35 / -3.16 | round 4440 (FAKE) | 0.01 | -10.17 | 234.78 |
| Fri 19:30 | NY straddle | SELL | 8.0 | **+6.09** | **+6.09** | +6.30 / -0.66 | Asia low, round 4460 | 0.01 | +48.71 | 283.49 |

**The week:** base 16 trades +5.91 R; rules 15 trades **+7.73 R, +50.96 USD**. Account **232.53 -> 283.49 USD**.

**What the winners share:** the straddle won all five (+8.64 R); Friday's ran +6.30 R in 30 minutes. The ORB's winners
broke the M15 swing in their direction.

**What the losers share:** Asia B2 lost four of six (-2.43 R), every loser with its stop just beyond a pool or a round
number. **Checked on weeks 1-32:** 89 of 103 B2 trades have their stop in a sweep zone (+0.054 a trade) against 14 without
(+0.162) - nearly all B2 stops sit there, so it does not separate the losers; skipping them would cut +4.82 R. Not adopted
(`b2_sweep_check.py`).

**The rules that cost this week:** the pool rule saved 1.02 (weeks 1-33 net +4.28 R); the 1.5 R target paid +0.80 (net
since week 5 +2.96 R). **The one change for week 34:** none.

# Phase 3: the exam weeks with the learning walk-forward (owner 2026-10-21/22: "learning that leaves the numbers equal to the cent is not learning")

Phases 1-2 changed a rule only when it beat the old one over every week since October 2025: the old two-way market kept
every new idea out, and the exam weeks matched the frozen run to the cent. From here (`wf_learn.py`, `context.py`,
`variants.parquet`) **every week each lever takes the option that made the most R over the previous 8 weeks** (a tie
keeps the current one), applied to the next week only: the ORB (target 1.0 / 1.5 / 2.0 R / none x the pool rule on /
off), the straddle's stop (6 / 8 / 10 / 12 USD), Asia B2 (every trade / only with the previous week's direction / only
with the D1 trend). Account: 300 USD, 3 % a trade, min 0.01 lot. Restarted at exam week 1; compared with the frozen run.

## Exam week 1 (2026-04-20 .. 24) - learned: the ORB without a target (+12.69 vs +12.26 R over weeks 19-26), the straddle stop 6 USD (+4.96 vs +4.15)

15 trades **-5.30 R, -44.99 USD** (frozen: 14 trades -5.11 R, -53.51 USD); account **300 -> 255.01 USD**. B2 traded both
ways (the flip on Tue made +0.83); the 6-USD straddle stop turned Wed +0.80 into +1.06 and Thu +0.54 into +0.72; the ORB
without a target lost Fri's +1.50 (it ended +0.05).

## Exam week 2 (2026-04-27 .. 05-01) - learned: the ORB back to 1.5 R (+5.46 vs +5.05 over 8 weeks), Asia B2 only with the previous week's direction (+0.71 vs -0.43)

11 trades **+5.34 R, +42.34 USD** (frozen: 12 trades +1.70 R, +12.08 USD); account **255.01 -> 297.35 USD** (frozen
258.57). The previous week fell, so B2 took only sells: it skipped Mon's buy (-0.44) and Tue's buy (-1.00) and kept Tue's
sell (+1.08) and Wed's (+0.59). The 6-USD straddle stop: Mon +0.92 (8 USD: +0.69), Wed +2.02 (+1.51), Fri +1.61 (+1.21).
Two weeks: 26 trades +0.04 R (frozen -3.41 R); 297.35 USD (frozen 258.57).

## Exam week 3 (2026-05-04 .. 08) - learned: the ORB without a target and without the pool rule (+6.16 vs +4.71 over 8 weeks)

12 trades **-1.37 R, -23.48 USD** (frozen: 10 trades -2.33 R, -36.52 USD); account **297.35 -> 273.87 USD** (frozen
222.05). The pool rule off took Tue (-1.00), Wed (-0.11) and Thu (+2.24 without a target: it ran past 2 R) = +1.13. B2 with
the previous (falling) week sold three times into this week's rise (-1.95) and skipped Wed's buy (+0.70) - the lever lags
a turning week. Three weeks: 38 trades -1.33 R (frozen -5.74); 273.87 USD (frozen 222.05).

## Exam week 4 (2026-05-11 .. 15) - learned: the ORB pool rule back on (no target; +3.01 vs +2.34), Asia B2 only with the D1 trend (+0.58 vs +0.36)

8 trades **-2.01 R, -14.50 USD** (frozen: 12 trades -1.89 R, +7.40 USD); account **273.87 -> 259.37 USD** (frozen
229.46). B2 with the D1 trend skipped four sells (Mon -0.53, -0.20; Tue +0.97; Wed +0.63 = +0.87 missed) and took Thu's two
(-0.85). The straddle lost three of five at the 6-USD stop. Four weeks: 46 trades -3.34 R (frozen -7.63); 259.37 USD
(frozen 229.46). The levers switch often (B2: all -> previous week -> D1 trend in four weeks): 8 weeks is a short memory.

## Exam week 5 (2026-05-18 .. 22) - learned: the ORB pool rule off again (+2.76 vs +2.50), the straddle stop 10 USD (+7.85 vs +7.83), B2 back to the previous week's direction (+0.36 vs -0.27)

8 trades **-0.94 R, -10.17 USD** (frozen: 7 trades +0.02 R, -3.70 USD); account **259.37 -> 249.20 USD** (frozen 225.76).
The pool rule off took three ORB losers / flats (-1.01, -1.02, +0.06 = -1.97); B2 with the previous week skipped two
buys (-0.05, -1.02). Five weeks: 54 trades -4.28 R (frozen -7.61); 249.20 USD (frozen 225.76).

**A lesson about the learner itself:** in five weeks the levers switched 9 times, the straddle on a margin of 0.02 R and
the ORB's pool rule back and forth every week - chasing noise. **From exam week 6 a lever switches only when the new
option beats the current one by at least 1.0 R over the 8 weeks** (decided now, applied forward; `wf_learn.py` MARGIN).

## Exam week 6 (2026-05-25 .. 29) - learned (on the 1.0 R margin): the ORB back to 1.5 R with the pool rule (-0.83 vs -3.30 over 8 weeks), the straddle stop 6 USD (+15.05 vs +9.52)

7 trades **+4.33 R, +9.76 USD** (frozen: 8 trades +2.67 R, +6.77 USD); account **249.20 -> 258.96 USD** (frozen 232.53).
Thursday's straddle made +7.50 R at the 6-USD stop (+45.02 USD; at 8 USD +5.63 R). B2 with the previous (rising) week
skipped Tue's sell (+0.08). Six weeks: 61 trades +0.05 R (frozen -4.94); 258.96 USD (frozen 232.53).

## Exam week 7 (2026-06-01 .. 05) - no lever cleared the 1.0 R margin; no change

15 trades **+4.52 R, +14.42 USD** (frozen: 15 trades +7.73 R, +50.96 USD); account **258.96 -> 273.38 USD** (frozen
283.49 - the frozen account is ahead again). The 6-USD straddle stop cost this week: three trades the 8-USD stop kept
(Mon +0.06, Tue +1.54, Wed +0.64) were stopped at 6 (-1.00, -1.05, -1.05); Friday's +6.09 became +8.12 R for the same
48.71 USD. Seven weeks: 76 trades +4.58 R (frozen +2.79); 273.38 USD (frozen 283.49). In R the learner leads, in USD it
trails: a tighter stop wins R on the winners and loses more often.

## Exam week 8 (2026-06-08 .. 12) - the learner now scores in USD at one 0.01 lot (decided after week 7); learned: the straddle stop 10 USD (+138.99 vs +98.27 USD over 8 weeks)

10 trades **+1.11 R, +26.58 USD** (frozen: 13 trades +3.94 R, +71.84 USD); account **273.38 -> 299.96 USD** (frozen
355.33). B2 with the previous (falling) week skipped three buys that won (+0.60, +1.54, +0.32 = +2.46 R missed; the frozen
B2 made +2.93). Eight weeks: 86 trades +5.69 R (frozen +6.73); **299.96 USD (frozen 355.33)**. The B2 trend filter now
costs more than it saves since it was chosen in week 2 - the margin keeps it from switching back (it must beat by 10 USD).

## Exam week 9 (2026-06-15 .. 19) - learned: Asia B2 back to every trade (+26.43 vs -1.57 USD over 8 weeks)

8 trades **-3.41 R, -37.37 USD** (frozen: 8 trades -3.14 R, -33.50 USD); account **299.96 -> 262.59 USD** (frozen 321.83).
The same trades as the frozen run; the 10-USD straddle stop made the two straddle losers 10 USD each (8 at 8 USD). The
frozen comparator at 300 USD / 3 % is now in `out_frozen_300.txt` (week by week). Nine weeks: 94 trades +2.28 R (frozen
+3.59); 262.59 USD (frozen 321.83).

## Exam week 10 (2026-06-22 .. 26) - no change

8 trades **+3.81 R, +63.29 USD** (frozen: 8 trades +4.65 R, +65.24 USD); account **262.59 -> 325.88 USD** (frozen 387.07).
The same trades; the 10-USD straddle stop gave the same USD as 8 USD (Thu +2.61 R = +26.07). B2 at the 0.01 lot carried
11 % of the account on Monday's +0.93 R (+32.84 USD). Ten weeks: 102 trades +6.08 R (frozen +8.24); 325.88 USD (frozen
387.07).

## Exam week 11 (2026-06-29 .. 07-03) - no change

8 trades **+4.01 R, +48.33 USD** (frozen: 8 trades +4.99 R, +48.33 USD); account **325.88 -> 374.20 USD** (frozen 435.40).
Thursday's straddle +4.46 R at 10 USD (+5.57 R at 8) - the same 44.56 USD. The pool rule skipped Friday's ORB (+0.38).
Eleven weeks: 110 trades +10.09 R (+0.092 a trade; frozen +13.23); 374.20 USD (frozen 435.40). From week 8 on the two
runs take the same trades; the gap is weeks 1-8's lever choices.

## Exam week 12 (2026-07-06 .. 10) - no change

5 trades **-1.30 R, -10.68 USD** (frozen: 5 trades -1.37 R, -10.68 USD); account **374.20 -> 363.52 USD** (frozen 424.72).
A quiet week: no Asia B2 trade, the straddle out flat twice on time; the pool rule skipped Mon (+0.22) and Fri (-1.08).
Twelve weeks: 115 trades +8.79 R (frozen +11.86); 363.52 USD (frozen 424.72).
