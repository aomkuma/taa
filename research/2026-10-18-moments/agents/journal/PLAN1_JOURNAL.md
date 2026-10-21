# PLAN-1 trade journal - trade by trade, week by week (from 2026-10-21)

Owner (2026-10-21, about 13:00 Thai): "trade, learn from each winner and loser, keep a trade journal, look for your own
weaknesses - that should make profit. Summing results once over three or five years is not useful."

**How it works:**
- Every PLAN-1 trade in time order, from the first learning week (2025-10-20) on: why it entered, the market around
  it (H1 ATR, the D1 20-day direction, yesterday's high / low), how far it went for and against (best / worst R and
  when), the result and a one-line lesson.
- At each week's end: what the winners share, the weaknesses that repeat, and **one** change, written before the next
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

**The one change for week 2 (written before week 2 is opened, 2026-10-21 13:00 Thai):** London ORB - once a trade has
gone +1 R its way, the stop moves to the entry (break-even). Chosen because it touches the repeat weakness 1 with no new
parameter beyond a common rule; on this week it would have turned #6 from -0.16 to 0 and left the rest unchanged.
