# The "runs" agent - effect to cause (2026-10-18)

The owner: "find the forms that come BEFORE price really runs - not only the one example I gave". Earlier rounds
(13-15) went cause to effect (a state or form, then what followed) and found the side at about 50 %. Here the other
way round: first catalogue the real runs, then what the chart looked like before them, against matched random times.

Design 2023-11-01 .. 2026-02-28 (five half-years, `jlib.HALVES`); the window 2026-03-01 .. 2026-10-16 (data to
20:54 UTC) only once per frozen rule.

## Step 1 - the run catalogue (written before it is computed)

- Gold M1 (`gold.bars("M1")`), every bar 2023-11-01 .. 2026-10-16.
- U = price / 4,100 (the bar's open); R = 10 U and 15 U.
- **An up-run from bar i:** s = low[i] (the start). Within 30 minutes (bars whose open time is at most 29 minutes after
  bar i's open) price reaches s + R (a bar's high) while, on the way, (a) no low goes below s (the start stays the
  extreme) and (b) no pullback from the running high exceeds 40 % of R (4 U for R = 10, 6 U for R = 15). The running
  high starts at bar i's close (the high of bar i may precede its low); a bar's low is checked against the running
  high before that bar's high is added (the order inside a bar is unknown; lenient). Down-runs mirrored (s = high[i]).
- **One run, one start:** qualifying starts whose [start, target bar] spans overlap form one run; its start is the
  lowest low (highest high for a down-run), the earliest on a tie.
- **Size and end:** from the start, follow the running extreme until price pulls back more than 40 % of the move so far
  (floor 40 % of R) or 240 minutes pass; size = the extreme - s; duration = minutes from the start bar to the extreme.
- Reported: runs per trading day by half-year, direction split, hours (UTC), session, sizes and durations, how many
  follow another run within 60 minutes (a second leg), how many start within 0-30 minutes of a US release.

## Step 2 - features before the run (written before it is computed)

Two frames:

- **A. A run is coming:** the snapshot at the close of bar s - 5 (all bars closed at least 4-5 minutes before the
  start bar opens; lookbacks up to 120 minutes and H1/M15 context). Controls: 10 random M1 bars per run from the same
  half-year and the same UTC hour (the base rate; they may contain runs). Lift = the runs' share in a feature bin /
  the controls' share (bins = the controls' quintiles for continuous features). Stable = the same sign of (lift - 1)
  in at least 4 of 5 design half-years. The side: among the runs, the share of up-runs per bin of each signed
  feature, by half-year (stable = the same side >= 4 of 5 half-years and the pooled share >= 56 %).
- **B. Which swing extremes launch a run:** every M1 swing low (high) = the lowest low (highest high) of the 5 bars
  before and the 5 after (11-bar fractal). Those that are the start of an up-run (down-run) against those that are
  not. The side is given by the swing (a low -> up). Features from bars up to the swing bar and the confirmation
  bars as a trader would see them at the moment of entry (written with the rule in step 3).

Features (closed bars only; U-scaled or ATR-scaled so they are relative): compression (M1 / M5 BB(20) width per M15
ATR, M1 ATR(14) / its 24-h mean, the range of the last 30 / 60 min per M15 ATR); the 60-min box (height per M15 ATR,
touches of the top / bottom, slope in heights, the close's position in it); higher lows / lower highs on M1 (3-bar
fractals, 60 min) and M5; sweeps and reclaims (a low below the previous 60-min low, Asian low, yesterday's low, then a
close back above, within the last 15 min; mirrored); equal highs / lows; distance to the day's / yesterday's / Asian
high and low and to round numbers (10 and 50 USD) per M15 ATR; the H1 / M15 tide (EMA20 slope over 3 bars + close vs
EMA50) and the H1 / M15 swing structure (the bot's ChartReadFrame confirmed structure: up / down / contracting /
broadening); tick volume (5 / 60 min, 60 min / 24 h); wicks (lower minus upper over 10 bars per M1 ATR); consecutive
closes one way; returns over 5 / 15 / 30 / 60 / 120 min per M15 ATR; distance to the M1 EMA20 per M1 ATR; time of day,
minutes since the session open (Asia 00:00, London 07:00, New York 13:30 UTC in DST-aware ET 09:30), minutes to /
since a US release; the dollar (six USD majors, 5 / 30 min, each per its own median 1-min move) and US500 (5 / 30 min).

## Step 1 result - the catalogue (`catalogue.py`, `catalogue.parquet`)

Leg merging (written after the first count, before any feature was read): the first count merged only overlapping
[start, target] spans, so one 50 U leg counted as 4-5 runs; corrected so that every same-side start up to the leg's
end (its first 40 % pullback) belongs to the same run.

| half-year | days | R10 runs | /day | up % | median size U | min to R | R15 runs | /day | up % | median size U |
|---|---|---|---|---|---|---|---|---|---|---|
| 2023-11 .. 2024-04 | 129 | 1267 | 9.8 | 48.9 | 13.7 | 11 | 506 | 3.9 | 50.2 | 20.0 |
| 2024-05 .. 2024-10 | 132 | 1565 | 11.9 | 51.6 | 13.5 | 12 | 558 | 4.2 | 49.5 | 20.4 |
| 2024-11 .. 2025-04 | 128 | 2123 | 16.6 | 51.8 | 13.4 | 10 | 799 | 6.2 | 51.1 | 20.0 |
| 2025-05 .. 2025-08 | 87 | 1369 | 15.7 | 50.1 | 13.1 | 11 | 479 | 5.5 | 51.6 | 19.6 |
| 2025-09 .. 2026-02 | 130 | 5392 | 41.5 | 49.6 | 14.0 | 5 | 2637 | 20.3 | 49.1 | 20.6 |
| window 2026-03 .. 10-16 | 164 | 6606 | 40.3 | 48.8 | 13.7 | 6 | 2939 | 17.9 | 50.8 | 20.4 |

Runs start most at 13-14 UTC (the New York open, 2x the day's mean), 00-01 UTC (Asia) and 05-08 UTC; least at
03-04 and 20-21 UTC. 45-87 % start within 60 minutes of another run's extreme (they cluster). 1.4-9 % start
within 30 minutes after a US release. Charts of 12 random R15 runs (`png/runs15_a.png`): box then break (3), a
V from a sweep of the last low/high (4), a lower high then a spike in a falling market (2), a base / double bottom (3).

## Step 2 results

**Frame A** (`frame_a.py 15 5 [--atr]`, 4,655 design R15 runs, 46,550 controls): the snapshot 5 min before the
start. Matched only by half-year + hour, volatility dominates (M15 ATR top quintile lift 2.4; bottom 0.4). Matched
also by the M15 ATR decile, the stable (5/5) lifts are 1.3-1.6: price below the prior 60-min / day / Asian /
yesterday's low (or above the highs) 1.45-1.56; far from the M15 EMA20 or a 30-60-min move > 1 M15 ATR 1.35-1.40;
the M1 ATR / its day mean, the 30-60-min range and the tick volume 5/60 in the top quintile 1.3-1.36; no bottom
touches in the box 1.32; the M15 swing structure DOWN 1.29. Fewer runs: quiet tick volume (0.66), narrow 30-min
range (0.72), M1 BB width bottom quintile (0.77) - compression is under-represented before runs.
The side among the runs is lopsided (pos60 top -> 73 % down-runs; below the day's old low -> 67 % up-runs; RSI,
EMA20 distance the same way, 5/5 half-years) but **that is the start being the extreme**: the run begins by
reversing the last minutes. From the snapshot itself (the trader's check: which of +5 / -5 U the next open reaches
first), every one of those bins is 46-53 % (base 48.6 %).

**Frame B** (`frame_b.py`, `frame_b_lift.py`; 70,691 design swings = a 10-bar extreme + 3 bars without a new one,
stop 0.3 U beyond, target 5 U): 7.9 % launch an R10 run (3.1 % R15). Launch lifts up to 2-3x (wider bounce, high
ATR, the NY hours, sweeps of the Asian / yesterday's level 1.9-2.0) but the trade vs the mirror (the other side,
same minute, stop and target) is +0.001 R overall; the largest stable edges are +-0.04 .. 0.07 R: fading a
fresh day extreme loses to the mirror in 5/5 half-years (-0.042 .. -0.074 R); buying a swing low while the close
is above yesterday's high / the Asian high +0.04 .. 0.06 (4-5/5).

**After a run** (`after_run.py`, `second_leg.py`): at the bar a run reaches R, the next +5 U goes the run's way
45-50 % (R15: 45-49 % in 5/5 design halves, a slight snap back; window 50 %); at the leg's first 40 % pullback
50-52 %. The next run after the pullback is on the same side 60-65 % in every half-year (window 62-63 %), but a
trade in the run's way from the pullback (stop beyond the run's start) is -0.02 .. -0.10 R (mirror -0.03 .. -0.22).

## Step 3 - rules (written before they are computed; `rules.py`)

Common: gold M1, jlib.Instr real costs (spread column + 0.08, entry slippage 0.07, stop 0.15 / NY 0.20), entry at
the next M1 open, the stop beyond the structure 3-10 U (U = price / 4,100) else no trade, break-even at 0.6 of the
target, one position at a time, decisions 00:00-20:00 UTC weekdays. Design first (variants A0-A3, B0-B2 are a
design exploration; one of each family is then frozen and run once on the window).

**RUN-A, the second leg** (the next run is the same side 60-65 %; the owner's "buy the pullback in the trend,
stop beyond the structure"): a catalogued run (R10 for A0/A1, R15 for A2/A3) has made its first 40 % pullback (the
leg-end bar). From there, the pullback's extreme counts once 3 M1 bars have not exceeded it and a close goes
beyond the high (low) of the bar that made it (count three + the turn); void if the pullback passes the run's
start or 60 minutes pass. Entry in the run's way at the next open; stop = the pullback extreme - 0.3 U; target =
the run's extreme (retest; at least 5 U) for A0/A2, 8 U for A1/A3; 120 minutes.

**RUN-B, a fresh day extreme is not faded** (fading it loses to the mirror in 5/5 half-years; runs are
over-represented after level breaks): a swing low (10-bar low + 3 bars without a new low) that made a new UTC-day
low (after 06:00 UTC), and at the third bar's close price is still below the old day low (no reclaim) -> SELL at
the next open (highs mirrored -> BUY). Stop: B0/B1 above the bounce's high (the swing bar to the decision bar) +
0.3 U; B2 the old day low + 0.5 M15 ATR. Target 8 U (B0, B2) or 5 U (B1); 120 minutes.

### Step 3 design results (real costs, one position; coin = 10 seeds on the same minutes)

| rule | trades (/day) | win % | R | USD 0.01 | coin R | halves + | losers 1/2/3 (coin) |
|---|---|---|---|---|---|---|---|
| A0 R10 retest | 5144 (8.5) | 31 | -0.140 | -2973 | -0.140 | 0/5 | 59/5/37 (57/4/38) |
| A1 R10 8 U | 5141 (8.5) | 28 | -0.125 | -2474 | -0.137 | 0/5 | 62/5/33 (61/5/34) |
| A2 R15 retest | 2477 (4.1) | 28 | -0.136 | -1670 | -0.142 | 0/5 | 62/5/33 (60/4/36) |
| A3 R15 8 U | 2594 (4.3) | 29 | -0.107 | -1270 | -0.127 | 0/5 | 60/5/35 (57/5/38) |
| B0 bounce stop 8 U | 276 (0.45) | 22 | -0.228 | -172 | -0.134 | 1/5 | 64/5/31 (63/6/31) |
| B1 bounce stop 5 U | 278 (0.46) | 30 | -0.228 | -171 | -0.198 | 1/5 | 49/2/49 (50/4/46) |
| B2 level stop 8 U | 439 (0.72) | 26 | -0.132 | -196 | -0.158 | 0/5 | 67/9/24 (65/7/28) |

(USD of the older half-years at their price: U = 0.5 USD in 2023-24.) Every variant within about 0.02 R of its
coin except B0/B1 (worse). **The charts of A3** (`png/A3_design.png`, 12 random trades): the winners were second
legs inside a running H1 trend (2024-09-12, 2025-05-15, 2025-11-21, 2026-02-04); the losers and break-evens were
(a) a run that was the last leg of a bigger swing - a V bottom / double top right after it (2023-12-21 double top,
2025-01-06 and 2025-04-04 sells into the final low), (b) ranges where the "run" was one swing of a box
(2025-04-30, 2025-05-12, 2025-12-17), (c) one spike stop (2026-01-28, -12.6 USD in a 5,300 market).
**A3's losers by context** (`causes.py A3`, mirror = the other side on the same minute): the H1 tide against the
run -0.129 R (mirror -0.111) vs with it -0.083 (mirror -0.208; 4/5 halves the side ahead); the close > 1.75 M15
ATR beyond the M15 EMA20 the run's way (chasing) -0.170; the stop < 0.64 M15 ATR (inside the normal swing) -0.111
.. -0.149 vs 0.64-0.82 ATR -0.026; 60 % of the stopped losers are kind 1 (wrong way: the run was over), 35 % kind 3.

**A4 (written before it is computed)** = A3 + three changes against the largest loser groups: (a) the H1 tide
(EMA20 slope over 3 bars + the close vs EMA50) agrees with the run; (b) at the decision close, price is at most
1.75 M15 ATR beyond the M15 EMA20 in the run's way (no chase); (c) the stop = the farther of (the pullback extreme
- 0.3 U) and (the entry - 0.6 M15 ATR), still 3-10 U (beyond the normal swing).

**A4 design result:** 1029 trades (1.69/day), win 31 %, -0.088 R, -387 USD at 0.01 lot (coin -0.110); halves
-0.07 / -0.17 / -0.04 / -0.25 / -0.04; losers 68/5/26 (coin 67/5/28). Step table A3 -> A4: -0.107 -> -0.088 R,
-1,270 -> -387 USD (fewer trades, the wider stop cut kind 3 from 35 % to 26 %); the coin improved as much
(-0.127 -> -0.110): a loss cut, not a side.
Neither the dollar's nor US500's move during the run (`run_dollar.py`: 73-77 % of runs have the dollar the fitting
way) nor the run's size / speed sorts A3 / A4's second legs stably.

## The lead's additions (2026-10-18)

**ATR-relative runs** (R = 1.5 / 2.5 x the M15 ATR(14) known at the start; same 30 min, 40 % pullback): their
frequency is flat by month (1.5 ATR: 20-25 a weekday in every month 2023-11 .. 2026-10; 2.5 ATR: 5.6-8.4), while
the U-scaled runs follow volatility (R15: 1.1 a day in 2024-02, 49 in 2026-02, 8.9 in 2026-10; M15 ATR median 1.4
-> 14.5 -> 6.7 USD). Window 2026-03 .. 10-16: 1.5 ATR 22.5 a weekday (median 17.4 USD, 11 min to R), 2.5 ATR 6.7
a weekday (median 27.7 USD, 19 min to R), 49-51 % up; by weekday 2.5 ATR Mon 5.3, Tue 7.2, Wed 6.9, Thu 6.5, Fri 6.5.
Hours (2.5 ATR, window, per 100 days): 00-01 UTC 90/72, 05 UTC 49, 12-13 UTC 87/71, 22-23 UTC 32/34; 03-04 and
15-17 UTC under 10.

**The adaptive entry timeframe** (`adaptive.py`: the smallest of M1 / M5 / M15 / M30 with ATR(14) >= 5 USD, else
M30): 2023-11 .. 2025-03 M30 77-99 % of the minutes (its ATR 2-5 USD: the 5 USD target was more than a whole M30
bar then); 2025-04/05 M15; 2025-10 .. 2026-01 M5 / M15; 2026-02 / 03 M5 54-63 % (M1 24 %); 2026-04 .. 06 M5 / M15
about half each; 2026-07 .. 10 M15 57-67 %.

**Frame A on the ATR-relative runs** (`frame_a.py 2.5 5 --atr`, `1.5 5 --atr`; with the forms on the adaptive
timeframe, `ad_*`): the same picture with smaller lifts. Before 2.5-ATR runs (5/5 half-years): tick volume 5/60 top
quintile 1.30, a sweep of the Asian low/high 1.34 (n 129), below the prior 60-min / day low 1.24-1.29, a wide
30-min range 1.25, M1 ATR / day mean 1.25; fewer runs after quiet tick volume (0.83), a narrow M1 BB (0.84), a
narrow 30-min range (0.85). The owner's box forms on the adaptive timeframe (box height = compression, top /
bottom touches, slope, Bollinger width) are 0.94-1.14 - no more frequent before runs than at random times. The
side among the runs is again the anchor (the close at the bottom of the adaptive box -> 58 % up-runs; top 40 %),
and the trader's check from the snapshot is 43-53 % in every bin; the most lopsided, 5/5: a sweep and reclaim of
the Asian low -> -5 U first 55-57 % (the reclaim fails), consistent with frame B and RUN-B.

**A5 (written before it is computed)** = A4 on the 2.5-ATR runs (volatility-relative second legs) instead of R15.

**A5 design result:** 855 trades (1.41/day), win 26 %, -0.137 R (coin -0.157), every half-year negative. Worse
than A4: not chosen.

## FROZEN for the one window run (2026-10-18, before the window is simulated)

- **RUN-A = A4** exactly as written above (R15 runs; the second leg after the first 40 % pullback, count three +
  the turn; H1 tide with the run; no chase (<= 1.75 M15 ATR beyond the M15 EMA20); stop the farther of the
  pullback extreme - 0.3 U and 0.6 M15 ATR, 3-10 U; target 8 U; break-even at 0.6; 120 min).
- **RUN-B = B2** exactly as written above (a new UTC-day extreme after 06:00 whose count-three bounce does not
  reclaim the old extreme -> with the break; stop the old extreme + 0.5 M15 ATR, 3-10 U; target 8 U; BE 0.6; 120 min).
- Disclosure: `after_run.py` and `second_leg.py` (exploration, before RUN-A was written) printed one descriptive
  window row each (the next-run side and a stop-at-the-start second-leg trade, -0.02 .. -0.06 R on the window);
  RUN-A's entry, filters and exits differ, but its family was glimpsed on the window. RUN-B's family was not.

## The one window run (2026-10-18)

A bug found right after the first window run: RUN-A did not enforce the written decision hours (00-20 UTC weekdays);
37 of its 595 window trades (53 of 1,029 design) were at 20-24 UTC or Sunday. Fixed to the written rule and rerun
(the rule unchanged); both runs reported. First (buggy) run: 595 trades, -0.029 R, -100.1 USD, coin -0.100.

**A4 as written (hours enforced), window 2026-03-01 .. 10-16:** 558 trades (3.38/day), win 33 %, **-0.037 R**,
**-85.2 USD** at 0.01 lot; the coin (10 seeds) -0.102 (sd 0.048), the mirror -0.175: the side beats the coin by
+0.065 R. Months (R, USD): 03 -0.01 +17 | 04 -0.04 -42 | 05 -0.08 -25 | 06 +0.04 +39 | 07 -0.12 -47 | 08 +0.20 +86 |
09 -0.09 -54 | 10 -0.40 -58 (28 trades); 3/8 months positive. Worst loss -11.40 USD, longest losing streak 11, max
DD 144.6 USD (more than a 100 USD account), 6 average stopped losses 39.9 USD. Losers 1/2/3 56/10/35 % (coin
56/7/37). Before costs (`P.gross()`): +0.063 R window, +0.042 design -> the real costs take about 0.10 R a trade.
Design with the hours enforced: 976 trades, -0.094 R (coin -0.127).

**B2, window:** 108 trades (0.65/day), win 30 %, -0.020 R, -51.4 USD (coin -0.038, sd 0.063; mirror -0.062);
months 03 +0.38 (5) | 04 -0.31 (18) | 05 +0.09 | 06 -0.08 | 07 -0.08 | 08 +0.03 | 09 +0.09 | 10 +0.09 (4); worst
-10.86, streak 12, max DD 80.5 USD. Gross +0.036 R. Indistinguishable from the coin.

**Why A4's losers lost** (`losers.py`, `pullback.py`, charts `png/A4_window_losers.png` / `_winners.png`):
- 47 % (design) / 55 % (window) of the full losers: **the run was the end of the swing** - its start was broken
  within 120 minutes of the entry (a V or a double top / bottom right after the run); only 18-19 % of the winners.
  Charts: 2026-03-05 buy under a double top, 05-26 / 06-22 / 09-15 sells into a V bottom, 10-08 buy at a top.
- 27 % / 35 %: kind 3 - stopped by a dip just beyond the pullback low, then the target came (the stop inside the
  swing: 05-15, 06-18, 07-21 charts).
- Stale runs: an entry 115-280 minutes after the run's start lost -0.230 R on design, 0/5 half-years positive (the
  leg extends up to 240 min, so the "second leg" can be hours old; chart 07-08: a sell 4 hours after an 85 USD run).
- Not causes (the same share among losers and winners, both periods): the M15 structure / tide against, the entry
  near the day's extreme, US releases, the session (London 17-23 % of losers vs 14-18 % of winners).
- What did not predict the V on design: the pullback's speed, tick volume, largest bar; the run's size in ATR
  (small runs V 50 %, big 16 %, but R flat).

**A6 (written before it is computed; a new rule - the A4 family's window is already seen):** A4 + the entry within
120 minutes of the run's start (no stale runs: live in the present).

**A6 design:** 795 trades (1.31/day), win 32 %, -0.070 R, -305 USD (coin -0.121); halves -0.03 / -0.17 / -0.06 /
-0.16 / -0.03.
**A6 window (one run):** 478 trades (2.90/day), win 34 %, **-0.031 R, -67.3 USD** at 0.01 lot; coin -0.118 (sd
0.043), mirror -0.168; months 03 +0.01 +20 | 04 -0.00 -21 | 05 -0.16 -55 | 06 +0.06 +38 | 07 -0.06 -16 | 08 +0.16 +62
| 09 -0.10 -57 | 10 -0.45 -37 (18); 3/8 months positive; worst -11.40 USD, streak 12, max DD 163 USD, 6 avg losses
41.1 USD; losers 55/9/35 (coin 57/7/36). Sessions: New York +0.017 R (+55 USD, 240 trades), Asia -0.028, London
-0.172 (-98 USD) - but on design London was not worse (A4 -0.075 vs NY -0.089), so not a cause to act on.
Exits on A6's design entries (8 U / BE 0.6 / 120 min vs 12-20 U, with / without BE, 180 min): every one -0.086 ..
-0.113 R - bigger targets do not help.

Step table (RUN-A, R / USD at 0.01 lot): design A3 -0.107 / -1,270 -> A4 -0.094 / -394 -> A6 -0.070 / -305;
window A4 -0.037 / -85 -> A6 -0.031 / -67. The coin on the same minutes: design -0.127 / -0.127 / -0.121, window
-0.102 / -0.118. RUN-A's side beats the coin in every period (+0.02 .. +0.09 R) and the mirror by 0.06-0.14 R; before
costs it is +0.04 (design) / +0.06 (window) R; the real costs (about 0.10 R a trade at a 5-7 USD stop) take it.

## Verdict (2026-10-18)

- What comes before a real run on gold M1 is **activity and broken levels, not a quiet box**: rising tick volume,
  a wide last 30-60 minutes, M1 ATR above its day mean, price beyond the last hour's / the day's / the Asian /
  yesterday's extreme, price stretched from the M15 EMA20 (lifts 1.2-1.6 beyond the hour and the ATR level, every
  half-year). Compression and the owner's box forms (on M1 and on the adaptive timeframe) are as frequent or rarer
  before runs than at random times. Runs cluster.
- These forms say **when**, not **which way**. The run's side looks predictable when it is measured from its start
  (65-73 %), but that is the start being the turning point; at any moment a trader can act on, every form measured
  leaves +5 / -5 at 43-57 %, mostly 47-53 %.
- The one rule family with a side better than the coin in every period - the second leg of a fresh run in the H1
  tide (RUN-A) - is about +0.06 R before costs and -0.03 R after them on the window. Half its stopped losers are
  runs that were the end of the swing (a V / double top right after), a third are stops just inside the swing.
- Next idea: attack the largest loser group directly at the run level - label every R15 / 2.5-ATR run as "continued"
  (a new extreme beyond the run within 2 h) or "ended" (its start broken first) and compare what was there at the
  extreme: the share of the day's average range already used, an H1 swing level or yesterday's / the week's extreme
  at the extreme, the dollar not confirming the last push, the run's acceleration (the last 3 minutes' share of the
  run). If something marks "ended" stably, RUN-A skips those runs (and a fade could use them).

## The lead's stop rule (2026-10-18): the stop in the trading timeframe's ATR

F1 on the window: stops < 0.5 x M15 ATR lost (-0.47 R, 12 trades), 0.5-1.0 won. Owner: size the stop beyond the
swing of the timeframe in use (at least about 0.5 of its ATR, beyond the structure), 3-10 USD at 0.01 lot, else skip.
The rules' stops are now also reported in units of the adaptive timeframe's ATR(14) (`adaptive.py`); reruns of the
frozen A4 / A6 / B2 are the same deterministic runs (no new test).

**A7 (written before it is computed; a new rule, the RUN-A family's window already seen):** A6, but the stop = the
farther of (the pullback extreme - 0.3 U) and (the entry - 0.5 x the ATR(14) of the adaptive timeframe in use at
the decision), and it must be 3-10 USD (not U) or no trade (A4 / A6 used 0.6 M15 ATR and 3-10 U).

**A7 design:** 718 trades (1.18/day), win 31 %, -0.092 R, -294 USD (coin -0.107); halves -0.18 / -0.03 / -0.13 /
-0.20 / -0.05 - worse than A6 on design.
**A7 window (one run):** 517 trades (3.13/day), win 32 %, **-0.001 R, +4.0 USD** at 0.01 lot; coin -0.118 (sd
0.030); months 03 -0.03 -33 | 04 +0.01 -9 | 05 -0.21 -53 | 06 +0.12 +64 | 07 -0.02 +7 | 08 +0.27 +85 | 09 -0.09 -50
| 10 -0.11 -7; 3/8 months positive in USD; worst -10.11 USD, losing streak 11, max DD 143.4 USD, 6 avg losses 34.2
USD; losers 51/6/43 (coin 51/5/44); median stop 5.52 USD = 0.75 x the trading-timeframe ATR (M5 74 % of trades,
M1 11 %, M15 15 %). Caveat: the stop rule came from F1's window result (the lead), so A7's window is not a clean
out-of-sample test; on design A7 is no better than A6.

R by the stop in trading-timeframe ATRs (`trades_*`): below 0.5 ATR - design A4 80 trades, win 15 %, -0.41 R; B2
77 trades, -0.28 R (the window had almost none: A4's 0.6 M15 ATR floor) - the tight stop loses, as F1 showed. Above
0.5 no clean order: 0.75-1.0 ATR is the window's best bucket (+0.06 R in A4 / A6 / A7, B2 +0.24) but on design
-0.08 .. -0.15; 1.0-1.5 ATR the design's best (-0.01) and the window's worst (-0.05 .. -0.10).

Account check (0.01 lot): every RUN-A version's 6 average stopped losses is 31-41 USD (fits 50 and 100 USD), but
the window's max drawdowns are 143-163 USD and the losing streaks 11-12 - more than a 100 USD account holds.

**A8 (written before it is computed; the owner relaxed the account limit, 2026-10-18):** A7 without the 10 USD
upper bound on the stop (the stop as the structure / 0.5 trading-timeframe ATR needs; at least 3 USD).
**A8 design:** 934 trades (1.54/day), win 35 %, -0.066 R, -253 USD (coin -0.092), every half-year negative; worst
-43.55 USD. **A8 window (one run):** 630 trades (3.82/day), win 35 %, -0.023 R, **-191.9 USD** (coin -0.091); 03
-0.05 -126 (163 trades: the March volatility, stops up to ~40 USD) | 04 -0.02 -50 | 05 -0.24 -82 | 06 +0.07 +11 |
07 -0.05 +6 | 08 +0.26 +117 | 09 -0.10 -70 | 10 -0.07 +1; worst -37.15 USD, streak 12, max DD 328 USD. Lifting the
cap adds big-stop trades in the wild months; R a touch better than A7 on design, USD worse on the window.
