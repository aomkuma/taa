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

# Round 2 (2026-10-18): make RUN-A pay, honestly

The lead's brief for round 2: RUN-A (the second leg of a fresh run) to >= +0.15 R a trade net of real costs on
the window (tolerance +0.10), most months positive, 1-3 trades a day, target >= 5 USD. Starting point: A6 -0.031 R
/ -67 USD (478 trades), A7 -0.001 R / +4 USD (517; its stop rule came from F1's window, so not clean). Gross (before
costs) +0.04 .. +0.06 R; the real costs take about 0.10 R a trade. Half the full losers: the run was the END of the
swing; a third: kind 3 (the stop just inside the swing); stale runs lost.

Data: gold M1 to 2026-10-16 20:54 UTC (`rules._m1` overrides `jlib.m1_frame`'s 10-15 cut); design 2023-11-01 ..
2026-02-28 (five half-years, `jlib.HALVES`), the window 2026-03-01 .. 2026-10-16 only once per frozen rule.

## R2 step 1 - "ended vs continued" (written before it is computed; `study.py`, design only)

- Population: every R15 run and every 2.5-ATR run of the catalogue whose first 40 % pullback gives RUN-A's
  count-three turn within 60 minutes (the A3 trigger, no filters, decisions 00-20 UTC weekdays). The decision
  moment = the close of the turn bar (where RUN-A would decide).
- Label from the decision bar, the next 120 minutes: **continued** = a high (low) beyond the run's extreme before
  any low (high) beyond the run's start; **ended** = the start broken first; **neither** = none within 120 min.
  Also each signal's trade on its own (no one-position rule): A7's trade (stop the farther of the pullback extreme
  - 0.3 U and 0.5 x the adaptive timeframe's ATR, 3-10 USD; target 8 U; BE 0.6; 120 min) and its mirror.
- Features at the decision close (closed bars only): (a) the share of the 20-day average daily range (server
  days, Europe/Athens) already used today, the run's size and the move from the day's opposite extreme to the
  run's extreme in ADRs; (b) yesterday's, the last 5 days', the 72-hour and the nearest H1 swing (5-bar fractal,
  confirmed before the run start, last 72 h) level in the run's way: where the run's extreme ended against it, in
  M15 ATRs (+ = beyond); (c) the wave count: 1 + the same-side 1.5-ATR runs that started since the lowest low (highest
  high) of the 8 hours before the run, and that swing's size in ADRs; (d) the acceleration (the last 3 minutes'
  share of the run), the run's speed, a volume climax (the top tick volume of the run's last 3 bars / the 24-h
  median per minute); (e) M5 / M15 RSI(14) and MACD-histogram divergence: the run made a new 3-hour extreme but the
  oscillator's run maximum stayed below its 3-hour maximum; (f) the distance from the H1 EMA20 / EMA50 in H1 ATRs
  (signed by the run's side); (g) the dollar: EURUSD (inverse) made / did not make a new 3-hour extreme with the
  run, its move during the run in its own scale; (h) the session, minutes since the session open; (i) a US
  release inside the run; plus the run's age at the decision and the pullback's depth.
- Read: per feature bin (design quintiles or categories), the shares continued / ended, the trade's R and the
  mirror's, by design half-year. A candidate needs the same sign in >= 4 of 5 half-years (both on the label and on
  the trade's R against the population) before any rule uses it.

### R2 step 1 result (design only; `study.py`, `study_read.py`, `out_study_R15.txt`, `out_study_A25.txt`)

Signals: R15 3,850 design (2,298 window, features only), 2.5-ATR 3,604 (947). From the decision close, within 120
min: R15 continued 60 %, ended 22 %, neither 18 % (2.5 ATR 55 / 25 / 20). **Among the decided, the continued share
is exactly where a random walk puts it** from the decision close's place between the run's start and its extreme
(R15 0.727 vs 0.727 calibrated on p_geo ventiles; by half-year -0.02 .. +0.03; 2.5 ATR 0.688 vs 0.688). The raw
"60 % continue" is geometry (the turn close sits about 70 % of the way up the run), not a side.
(Two bugs fixed before reading: ms vs ns timestamps zeroed the wave count and the H1 swing levels.)

What marks a run that CONTINUES more than the random walk (excess in the continued share, same sign in >= 4/5
half-years in BOTH populations):
- the run's extreme went beyond the 72-hour extreme (R15 +0.041 5/5, 2.5 ATR +0.069 5/5) or beyond any level in
  its way (yesterday's, 5-day, 72-h, H1 swing; R15 +0.052 5/5, 2.5 ATR +0.036 4/5);
- a big run for its volatility: >= ~3.7-4.3 M15 ATRs (R15 +0.066 5/5, 2.5 ATR +0.048 5/5), a big swing from the
  8-hour extreme (2.5 ATR +0.047 5/5), the M15 ATR above its 5-day mean (2.5 ATR +0.049 5/5);
- far beyond the H1 EMA20 (> 1.9 H1 ATR: +0.021 / +0.035, 4-5/5) - stretched runs continue, they do not snap back.
What marks a run that ENDS: only a US release inside the run (R15 109 signals, excess -0.06, trade -0.28 R; too
few to rely on). **The owner's exhaustion signs do NOT mark the end of a run on gold M1**: the share of the
day's average range used (the 0.77-1.0 bin continues MORE, +0.039 4/5), the wave count (4+ pushes +0.016 4/5),
the last 3 minutes' acceleration (no stable sign), a volume climax (none), M5/M15 RSI or MACD divergence (R15
no-divergence +0.029 4/5, 2.5 ATR MACD divergence +0.020 5/5: contradictory), the dollar not confirming (none).
The trades (A7's construction on every signal, no one-position rule): R15 -0.099 (mirror -0.121), 2.5 ATR -0.097
(-0.131). On the "strength" subsets the side's edge over the mirror grows (R15 broke-72h & >= 3.7 ATR: +0.15 R,
cont 0.82) but A7's trade stays negative (-0.04 .. -0.07), with H1 (2023-11..24-04) and H4 (2025-05..08) negative
in every subset. A7's construction (a stop at the pullback, 8 U) does not cash the continuation; step 2 tests
other constructions.

## R2 step 2 - entries, stops and targets with chart tools (written before it is computed; `tools.py`, design)

The owner (via the lead, 2026-10-18): measure targets and entries with chart tools - Fibonacci, channels, zones.
On the R15 RUN-A population (the step-1 signals, design only), each signal simulated on its own:
- **Entries:** MKT = the next open after the count-three turn (A7). LIMxx = a limit at the xx % retracement of the
  run (start -> the running extreme, recomputed each bar from closed bars), live from the bar after the run
  reached R until filled, the start is broken, 120 min after the run's start, or 60 min after the leg's end;
  xx = 38.2, 50, 61.8. A limit buy fills when the bar's low + the real spread reaches it (at the limit, or at the
  open's ask if it gapped through), no entry slippage; a stop touched in the fill bar counts as stopped (unknown
  order, conservative); the target is checked from the next bar.
- **Stops:** P = the pullback extreme - 0.3 U (MKT only); F = the next fib level beyond the entry (38.2 -> 61.8, 50
  -> 78.6, 61.8 -> 100) - 0.3 U; S = the run's start - 0.3 U; each at least 0.5 x the adaptive timeframe's ATR and
  3 USD (no upper bound: the owner relaxed it; the worst loss is reported).
- **Targets** (each floored at 5 USD from the entry): T8 = 8 U; X = the run's extreme (the running extreme at the
  fill); E1.272 / E1.618 = the fib extension of the run from its start; ABCD1.0 / 1.272 / 1.618 = the pullback's
  extreme + k x the run (MKT only: the pullback is known at the turn); CH = the channel: the parallel through the
  run's extreme of the line through the run's start and the pullback's extreme, at the entry bar (MKT only); Z =
  the nearest opposing zone or level in front >= 5 USD away (the app's M15 / H1 demand-supply zones,
  `market_map.zones_at`, and the M15 / H1 ChartReadFrame levels; none in front within 5 .. 60 USD -> no trade).
- Exits: break-even at 0.6 of the target, 120 min from the fill, real costs (jlib).
- Filters to test with them: the step-1 strength markers (the run broke the 72-hour extreme; size >= 3.7 M15 ATR);
  "the pullback held inside the run's channel" (the pullback extreme stays above the run's regression channel -
  the M1 closes' least-squares line from the start to the extreme, its lower band at the largest low residual -
  extended to the pullback bar); "the pullback held a zone" (a demand zone, M15 or H1, within 0.25 M15 ATR of the
  pullback extreme -> the stop also beyond that zone).
- Reported per tool: the share of entries where the tool's own target is >= 5 USD, the target's hit rate vs T8 on
  the same entries, R, USD, the losers' kinds (does kind 2 shrink?), by design half-year.

## R2 step 2b - the owner's Fibonacci grid (written before it is computed; `fibgrid.py`, design)

The owner's chart: a fib grid from the latest swing low (0) to the PREVIOUS swing high (100), levels 23.6 / 38.2 /
50 / 61.8 / 78.6 / 88.1 / 100, on the adaptive timeframe's ZigZag swings (MT5 ZigZag 12/5/3, ChartReadFrame
pivots, known from their confirmation bar); mirrored for a high after a previous low. From the grid's confirmation,
for 48 bars of that timeframe: each level's first touch from either side (the bar's high / low reaches it from
below / above); "held" = price then moves 0.5 x the timeframe's ATR away from the level on the side it came from
before closing 0.25 ATR through it (the bar's close). The placebo: the same test at random levels drawn uniformly
between the grid's 15 % and 95 % (away from the fib levels by at least 3 % of the grid), the same number per grid.
A level is "real" only if its hold rate beats the placebo's in >= 4 of 5 half-years.

### R2 step 2 result (design; `tools.py`, `tools_design.csv`, `tools_long_design.parquet`)

Every signal on its own (no one-position rule), design 2023-11 .. 2026-02, real costs, BE 0.6, 120 min. Market
entries: 3,850 turn signals; limits: every R15 run (fills LIM38.2 4,234, LIM50 3,716, LIM61.8 3,133).

| entry | stop | target | n | own target >= 5 USD | win % | R | halves + |
|---|---|---|---|---|---|---|---|
| MKT | P (A7) | T8 | 3850 | 78 % | 32 | -0.093 | 0/5 |
| MKT | P | X / CH / E1.272 / ABCD1.0 / Z | 3850 (Z 1425) | 49 / 84 / 85 / 92 / 37 % | 21-31 | -0.109 .. -0.120 | 0/5 |
| MKT | S (the start) | T8 / E1.272 / CH | 3850 | | 41 / 33 / 34 | -0.033 / -0.040 / -0.041 | 0/5 |
| MKT | F (next fib) | T8 | 3850 | | 35 | -0.082 | 0/5 |
| MKT | Z (the zone held) | T8 | 2368 | | 36 | -0.084 | 0/5 |
| LIM38.2 | S | T8 / E1.272 | 4234 | 81 / 100 % | 42 / 32 | -0.030 / -0.015 | 0/5, 1/5 |
| LIM50 | S | T8 / E1.272 | 3716 | | 40 / 27 | -0.032 / -0.017 | 1/5 |
| LIM61.8 | S (= F) | T8 / E1.272 / E1.618 / Z | 3133 (Z 1722) | | 37 / 21 / 14 / 30 | -0.052 / -0.023 / -0.016 / -0.035 | 0-2/5 |

- The fixed 8 U target hits most often everywhere (32-42 %); every chart-tool target (the run's extreme, the
  extensions, AB=CD, the channel, the zone in front) hits less and pays no more: their R is equal or worse. Z (the
  next opposing zone / chart-read level) finds a target >= 5 USD in only 37-49 % of the entries (the rest: no room
  or none within 60 USD) and is worse than T8 on the same entries in 4 of 5 entry forms.
- Kind 2 (fell short) is 3-7 % of the stopped losers with every target: not the problem the targets could fix.
- What changed R: the stop. Beyond the run's start (S, median 10-13 USD) every form is -0.015 .. -0.048 instead of
  -0.08 .. -0.13 (costs per R fall from about 0.09 to 0.03). Before costs that is about zero: the population has no
  side to cash, whatever the tool.
- Filters: the zone held (MKT, 2,368) no better (-0.048 with S/T8); the pullback inside the run's channel (225) -0.001
  .. +0.031 with S, 3/5 halves - too few, unstable; the run broke the 72-h extreme (634) -0.04 .. +0.03, 1-2/5; **a
  big run (>= 3.7 M15 ATR) with a deep limit**: LIM61.8 / S / E1.618 509 trades +0.083 R, 4/5 halves (H3 -0.125),
  E1.272 +0.053 4/5; with the 72-h break too (154) +0.077, 5/5. This is the step-1 marker (big runs continue more
  than a random walk) cashed by an entry deep in the pullback with the stop beyond the start.

## R2 step 2c - the deep-limit family (written before it is computed; `deep.py`, design only)

To see whether the big-run deep-limit result is a region or a peak: every R15 design run, a trailing limit at f
= 50 / 61.8 / 78.6 % of the run, the stop beyond the start (start - 0.3 U, at least 0.5 adaptive ATR and 3 USD),
the target at k = 1.0 (the extreme) / 1.272 / 1.618 / 2.0 x the run from its start (at least 5 USD), BE 0.6 or
none, 120 or 240 min; by the run's size at the fill in M15 ATRs (>= 0 / 3 / 3.7 / 4.5 / 5.5) and by half-year. A
choice needs a region (neighbouring f / k / thresholds also positive) and >= 4/5 half-years.

### R2 step 2c result (`deep.py`, `deep_design.csv`)

The deep-limit result is a **peak, not a region**: at size >= 3.7 M15 ATR, f = 61.8 % is +0.04 .. +0.09 R for every
target k (4/5 half-years), but f = 50 % is -0.006 .. -0.033 and f = 78.6 % -0.04 .. +0.01 at the same threshold;
at f = 61.8 the thresholds 3.0 / 4.5 give +0.02 .. +0.04 (3/5) and 5.5 is negative. With about 500 trades the
standard error of a mean R is about 0.045, and about 15 cells were looked at: +0.083 is what the best of 15
noise cells looks like. Not chosen as it stands.

The direct check of the step-1 marker as a trade (`levers.py` check, MKT at the turn, stop beyond the start,
target = the run's extreme, no BE, 120 min, before / after costs): R15 all -0.010 / -0.054; big (>= 3.7 ATR)
+0.037 / -0.011; broke the 72-h extreme +0.039 / -0.006; both +0.048 / +0.002 (4/5 half-years gross +); 2.5 ATR
broke-72h +0.053 gross in 5/5 half-years, net -0.005. **The continuation marker is real but worth about +0.04 ..
+0.05 R before costs** - the same size as RUN-A's side over the coin in round 1; the costs take it.

### R2 step 3 - RUN-A's own levers (design; `levers.py`, `out_levers_R15.txt`, `out_levers_A25.txt`)

Each turn signal on its own; stops P (A7: the pullback - 0.3 U, >= 0.5 adaptive ATR, 3-10 USD) or S (beyond the
start); exits T8 + BE 0.6 (120 min), the extreme without BE, or a trailing stop (armed at 0.3 / 0.5 x the run,
trailing by as much, 240 min). R15, best rows: all -0.034 (S_T8); A6's filters (tide, no chase, fresh) S_T8 -0.012
(2/5); strong (big or broke 72 h) S_trail50 +0.007; big & broke-72h S_T8 +0.013 (3/5), S_trail50 +0.021; fresh &
big & broke-72h S_trail50 +0.039 (231 trades, 3/5). 2.5 ATR: big & broke-72h S_T8 +0.013 (479, 4/5); fresh & big &
broke-72h S_trail50 +0.050 (299, 3/5). Every A7-stop (P) row is negative. **No lever or combination reaches
+0.10 R on design**; the strong-run subsets with a stop beyond the start are about break-even (-0.01 .. +0.05), and
the newest half-year (2025-09 .. 2026-02, the window's volatility) is their best (+0.03 .. +0.26).

### R2 step 2b result - the owner's Fibonacci grid (`fibgrid.py`, `out_fibgrid.txt`, design)

| TF | fib touches | placebo touches | held (fib levels) | held (placebo) | levels beating the placebo in >= 4/5 halves |
|---|---|---|---|---|---|
| M5, every grid | 34,083 | 30,431 | 0.516 .. 0.541 | 0.514 .. 0.538 (same distance) | 61.8 only, +0.007 |
| M15, every grid | 11,094 | 9,986 | 0.529 .. 0.575 | 0.548 .. 0.562 | none |
| M5 / M15 while the adaptive TF | 2,916 / 1,925 | 2,580 / 1,685 | 0.489 .. 0.589 | 0.534 .. 0.598 | none (61.8 on M5 -0.069, 100 on M15 -0.069) |

Every fib level holds as often as a random level at the same place in the grid (differences -0.07 .. +0.03, mostly
within +-0.015 on thousands of touches), from below (resistance) and from above (support) alike. The 100 % level
(the previous swing high / low, also the owner's horizontal zone) holds LESS than random levels on M15 (-0.023, and
-0.069 when M15 is the trading timeframe): prior swings get run through. On design gold M5 / M15 the grid is not a
map of where price turns, so it cannot place entries or targets better than any other price.

**The owner's trend line (written before it is computed; `trendline.py`, design):** on M5 / M15 / M30 ZigZag(12, 5,
3) pivots, a rising line through a swing low and the next higher low (falling through a high and a lower high),
known from the second pivot's confirmation; its first touch from price's side within 48 bars; held = 0.5 ATR away
before a close 0.25 ATR through. Placebo: the same line shifted towards price by a random 0.5 .. 1.5 ATR. The
owner's confluence: touches where a level of the fib grid (the first swing low = 0, the swing high before it = 100)
is within 0.25 ATR of the line, against touches without.

**Trend-line result (`out_trendline.txt`):** the owner's line holds as often as the same line shifted off the swings:
M5 0.493 vs 0.487 (2,873 touches, +0.006, 4/5), M15 0.513 vs 0.522 (-0.009), M30 0.530 vs 0.542 (-0.011). With a
fib level within 0.25 ATR (the owner's confluence): M5 0.502 vs 0.491, M15 0.545 vs 0.551, M30 0.541 vs 0.571 - no
better than the line alone or than the placebo. On design data neither the fib grid nor the trend line nor their
confluence marks where gold M5-M30 turns; the confluence entry was therefore not built into a rule (it would rest
on a level that holds no better than chance).

## R2 step 4 - candidates on design, one position at a time (`rules2.py`, `out_rules2_design.txt`)

Written before computed (design only):
- **A9** = the RUN-A trigger (R15 run, its first 40 % pullback, count three + the turn, void at the start or 60 min;
  decisions 00-20 UTC weekdays) on a STRONG run only: the run's size >= 3.7 x the M15 ATR(14) at its start AND its
  extreme beyond the 72-hour extreme before the run; the decision within 120 min of the run's start. Entry at the
  next M1 open; stop beyond the run's start (start - 0.3 U; at least 0.5 x the adaptive timeframe's ATR and 3 USD,
  no upper bound); target 8 U; break-even at 0.6; 120 min.
- **A10** = A9 with a trailing exit: armed once the trade is 0.5 x the run's size in profit, then the stop trails
  the best price by 0.5 x the run's size (never below the entry); 240 min; no fixed target.
- **D1** = the deep limit: an R15 run; a buy (sell) limit at its 61.8 % retracement (start -> the running extreme,
  from closed bars), live from the bar after the run reached R until filled, the start broken, 120 min after the
  start or 60 min after the leg's end; fills 00-20 UTC weekdays only; the run's size at the fill >= 3.7 M15 ATR;
  stop beyond the start (as A9); target the 1.618 extension of the run from its start (at least 5 USD); BE 0.6;
  120 min.

| rule | trades (/day) | win % | R | USD 0.01 | before costs | coin R | halves (R) | worst / streak / max DD USD |
|---|---|---|---|---|---|---|---|---|
| A9 | 231 (0.38) | 44 | +0.012 | +43 | +0.082 | -0.020 | -0.05 / -0.00 / +0.03 / -0.04 / +0.10 | -32.8 / 6 / 77 |
| A10 | 223 (0.37) | 50 (pnl > 0) | +0.029 | +20 | +0.084 | -0.016 | +0.01 / -0.04 / +0.10 / -0.10 / +0.14 | -84.2 / 5 / 215 |
| D1 | 453 (0.75) | 8 | +0.085 | +361 | +0.140 | -0.012 | +0.09 / +0.15 / -0.15 / +0.16 / +0.17 | -102.4 / 10 / 181 |

The worst losses are the stop beyond the start in the wildest runs (2025-10 .. 2026-02: runs of 85-266 USD, stops
30-102 USD at 0.01 lot). D1 is mostly time exits (204 of 453; win 8 %, stop 200): it is "buy deep in a big run's
pullback, risk to the start, hold two hours". Its drift after the fill (`deep` check: the close 120 min later
minus the entry, in run sizes): +0.042 at f = 61.8 % in all five half-years (+0.020 .. +0.071, 509 fills), but
-0.002 / -0.004 / -0.005 at 38.2 / 50 / 78.6 % - a hump at 61.8, about 2 standard errors, after four levels were
looked at. Disclosed as a design peak.

## FROZEN for the window (2026-10-18, before any round-2 rule touched the window)

A9, A10 and D1 exactly as written above (rules2.py RULES2), each run once on 2026-03-01 .. 2026-10-16, reported
month by month with the coin (10 seeds) and before costs. A9 / A10 are new rules in the RUN-A family whose window
was seen in round 1 (A4 .. A8); their new parts (the strength filter, the stop beyond the start, the trail) were
chosen on design only. D1's family (limits in the pullback) was never run on the window.

## The window runs of the frozen rules (2026-10-18, each once; `out_rules2_window.txt`, `out_D1_fixed.txt`)

| rule | trades (/day) | win % | R | USD 0.01 | before costs | coin R (sd) | months + (USD) | worst / streak / max DD | losers 1/2/3 (coin) |
|---|---|---|---|---|---|---|---|---|---|
| A9 | 87 (0.53) | 38 | **-0.058** | **-193.0** | -0.028 | -0.079 (0.046) | 2/8 | -99.4 / 6 / 219 | 71/14/14 (80/3/17) |
| A10 | 87 (0.53) | 49 (pnl > 0) | **-0.009** | **-59.5** | +0.012 | -0.131 (0.078) | 5/8 | -99.4 / 6 / 173 | 74/17/9 (77/15/8) |
| D1 | 184 (1.12) | 5 | **-0.097** | **-169.5** | -0.089 | -0.099 (0.072) | 3/8 | -52.1 / 10 / 375 | 94/2/4 (95/1/4) |

Months (R, USD): A9 03 -0.12 -85 | 04 +0.02 +13 | 05 -0.01 -26 | 06 +0.05 +14 | 07 -0.03 -45 | 08 -0.14 -37 | 09 -0.06
-4 | 10 -0.21 -23. A10 03 +0.11 +6 | 04 +0.07 +10 | 05 -0.11 -73 | 06 +0.53 +135 | 07 +0.00 -56 | 08 -0.06 +34 | 09
+0.03 +10 | 10 -0.54 -126. D1 03 +0.20 +33 | 04 -0.26 -83 | 05 -0.18 -51 | 06 -0.13 -30 | 07 +0.24 +102 | 08 -0.45
-138 | 09 +0.11 +56 | 10 -0.37 -58.

**A bug in D1 found on its window charts and fixed (the rule unchanged):** the limit's running extreme took the start
bar's own high (low), which can precede the start inside that bar (2026-07-02 12:30 NFP bar: a "down-run" from the
spike's high got the bar's low as its extreme, size 59 instead of 21). Fixed in tools.py / deep.py / rules2.py
(`simlib.run_x0`: the start bar gives only its close, as the catalogue does). D1's first window run with the bug:
187 trades, -0.096 R, -160.6 USD (coin -0.040); after the fix: the table above. Design moved by +0.001 R (the deep
grid unchanged in substance), so the step-2c reading stands.

Out-of-sample check of the step-1 markers (descriptive, after the three window runs, no rule changed from it): the
continuation excess on the window - R15 broke-72h +0.053 (225, held), big >= 3.7 ATR +0.018 (237, weaker), both
+0.057 (75); 2.5 ATR: all signals +0.020 and every marker +0.019 .. +0.024 (no difference). The 72-hour break kept
its sign; the size marker did not carry.

### Why the window losers lost (A9 / A10 / D1; charts `png/R2_A10w_stops.png`, `_wins.png`, `R2_D1w_stops.png`)

- **The stop beyond the start is huge in this window.** A9/A10's median stop was 24.8 USD (design 13.4; the six
  largest 54-99 USD): a "big" run (>= 3.7 M15 ATR) here is 30-100 USD. Against A9's 8 U target (~9 USD) the payoff
  was 0.35 : 1, so the 14 full stops (-1 R each, up to -99 USD) outweighed 33 wins. A10's trail (scaled with the
  run) paid more per win (median reference 21 USD) and came out at -0.009 R, the best of the three, but the USD sum
  is dominated by a few 50-100 USD stops (October: two of them, -126 USD).
- **Break-even by noise:** A9's BE exits rose to 36 % of trades (design 24 %): +0.6 x 8 U = about 5 USD is less
  than one M15 ATR (7-14 USD in the window), so the noise moved the stop to the entry and back.
- **What the stopped trades looked like** (12 A10 stop charts): the run was the end of its swing - a V or a
  rounded top right after (2026-04-01 Asia-open rally, 05-18 / 05-27 / 07-14 / 09-01 sells into a V bottom); a
  one-bar spike counted as the run (04-15 01:02 spike to 4870, 10-02 12:25 release spike) that faded back to its
  start; one spike stop then the target (08-11, kind 3). The winners (12 charts) were second legs inside a staircase
  trend with lower highs / higher lows on M15-H1 (03-13, 06-10, 06-24 sells; 09-03 buy) - the same picture as round
  1. Asia-open runs (22-02 UTC) held 43 % of A10's window stops (26 trades, -0.038 R), but on design the same group
  was A9/A10's best (+0.058 / +0.175), so the session is not a cause to act on.
- **D1 (the deep limit):** 93 of 184 trades stopped, 94 % kind 1 (wrong way): the 61.8 % retracement in the window
  was mostly the first half of a full reversal (2026-06-17 18:57 UTC: a buy at 61.8 % of a 62 USD spike up inside a
  160 USD fall, stopped 10 min later; 08-13 / 08-31 buys after Asia-open spikes that faded; 10-08 a sell into a V). The design hump at 61.8 % (all five half-years +0.020 .. +0.071 run
  sizes of drift) did not repeat: the window drift was negative.
- Against the coin on the same minutes the side was ahead in A9 (+0.02 R) and A10 (+0.12 R, sd 0.08), level in D1:
  the direction still beats a coin a little in the RUN-A family; the stop geometry and the costs decide the sign.

## R2 step 5 - all step-1 features together (written before it is computed; `ended_ml.py`, design only)

LightGBM (300 trees, 15 leaves, conservative) on every step-1 feature plus the geometry p_geo, predicting
continued vs ended (the decided signals), walk-forward over the design half-years (train H1..Hk, test Hk+1, k = 2..4),
against a logistic model on p_geo alone. Read: the AUC of each, the AUC inside p_geo quintiles (information beyond
the geometry) and the continued share where the model is most above / below the geometry. If the model adds less
than about 0.03 AUC over the geometry, the "ended" group is not predictable from these features.

**Step 5 result (`out_ended_ml.txt`):** the model ranks continued vs ended WORSE than the geometry alone in all six
walk-forward folds (R15 AUC 0.731 / 0.768 / 0.782 vs geometry 0.768 / 0.783 / 0.803; 2.5 ATR 0.723 / 0.709 / 0.748 vs
0.763 / 0.729 / 0.777); where it is most above the geometry the runs continued LESS than the geometry expects
(0.64-0.68 vs 0.66-0.71). Together the 42 features (ADR used, levels, waves, acceleration, volume, RSI / MACD
divergence, EMA distance, the dollar, session, release, age, depth) carry no out-of-sample information about whether
a run has ended. **The "ended" losers are the random walk's share at the entry's place in the run, not a
recognisable pattern.**

**A11 (written after the window runs of A9 / A10 / D1 and the window check of the markers - a window-informed
rule, disclosed; its window result is NOT out-of-sample):** A10 without the size condition: R15 RUN-A trigger, the
run's extreme beyond the 72-hour extreme, the decision within 120 min of the run's start, the stop beyond the start
(>= 0.5 adaptive ATR, >= 3 USD), the trailing exit armed at 0.5 x the run and trailing by 0.5 x the run, 240 min.
Design (from `levers.py`, each signal alone): 481 signals, +0.080 R, 4/5 half-years (+0.11 / +0.00 / +0.06 / -0.10 /
+0.20). Why it is tried: the 72-hour break was the one step-1 marker whose continuation excess held on the window
(+0.053), the size marker did not.

**A11 window run (window-informed, NOT out-of-sample; `out_A11.txt`):** 196 trades (1.19/day), 53 % closed in
profit, **+0.091 R, +298.5 USD** at 0.01 lot; before costs +0.113; coin -0.047 (sd 0.065); months 03 +0.67 +310 (22) |
04 +0.30 +85 | 05 +0.00 -60 | 06 +0.11 +83 | 07 -0.12 -77 | 08 +0.09 +81 | 09 +0.08 +22 | 10 -0.61 -146 (13); worst
-99.4 USD, streak 8, max DD 221.8 USD, median stop 19.3 USD. Without March: 174 trades about +0.02 R, -12 USD. Design
(one position): 403 trades, +0.051 R, halves -0.01 / -0.02 / +0.05 / -0.04 / +0.17 (2/5) - only the newest half-year
carries it. Four trades checked by hand (entry, stop, trail, exit): identical.

## R2 step 6 - the untouched older sample as a holdout (written before it is computed; `oldcheck.py`)

Gold M1 2021-09 .. 2023-10 (the TS store) was never used in this folder. The R15 catalogue, the turn trigger, the
72-hour break and the adaptive ATR rebuilt for it with the same code; A9, A10, A11 and D1 exactly as frozen,
2021-10-01 .. 2023-10-31, real costs (the spread column there is 0.21-0.33 USD at prices 1,800-1,950, so costs are
about twice as heavy in R as today: read the before-costs R too), against the coin. This is the one clean test A11
can get.

### R2 step 6 result - the older sample 2021-10 .. 2023-10 (`out_oldcheck.txt`; 2,203 R15 runs, 1,913 turn signals)

| rule | trades (/day) | R | USD 0.01 | before costs | coin R (sd) | half-years (R) | worst / max DD | stop median |
|---|---|---|---|---|---|---|---|---|
| A9 | 203 (0.37) | -0.073 | -58.8 | -0.013 | -0.045 (0.032) | -0.07 / -0.00 / -0.12 / -0.10 | -15.5 / 77 | 7.8 |
| A10 | 194 (0.36) | -0.092 | -123.9 | -0.033 | -0.029 (0.041) | +0.04 / -0.18 / -0.11 / -0.16 | -15.8 / 180 | 7.7 |
| A11 | 296 (0.55) | **-0.032** | -77.2 | +0.041 | -0.033 (0.055) | +0.02 / +0.05 / -0.12 / -0.10 | -15.8 / 171 | 6.7 |
| D1 | 360 (0.66) | -0.130 | -191.5 | -0.092 | -0.067 (0.053) | -0.02 / -0.15 / -0.37 / -0.01 | -9.2 / 216 | 4.1 |

A11's one clean test: -0.032 R, the coin's level. D1 fails again (the 61.8 % hump was noise).

**The side against its mirror by half-year (`regime.py`, `out_regime.txt`; A11, the same trades with the other
side):** 2021-10 +0.21, 2022-05 +0.17, 2022-11 -0.05, 2023-05 -0.06 | 2023-11 +0.22, 2024-05 +0.07, 2024-11 +0.25,
2025-05 +0.00, 2025-09 +0.20 | window +0.20. The side beats the mirror in 7 of 10 half-years (about +0.06 R of gross
edge for the side on average), but the rule's own R is positive only where the stop beyond the run's start is wide
(2025-09 .. 2026-10: median stop 19-20 USD, costs about 0.02 R): +0.17 and +0.09. Where the stop is 6-12 USD (2021-25)
the costs (0.04-0.08 R) eat the same edge: -0.12 .. +0.05.

## Step table - RUN-A, round 1 -> round 2 (R a trade / USD at 0.01 lot)

| rule | the change | design R | window R / USD | window coin | window before costs | 2021-23 R (before costs) |
|---|---|---|---|---|---|---|
| A4 | round 1 frozen (tide, no chase, 0.6 M15 ATR stop) | -0.094 | -0.037 / -85 | -0.102 | +0.063 | - |
| A6 | + entry within 120 min of the run | -0.070 | -0.031 / -67 | -0.118 | - | - |
| A7 | + stop >= 0.5 adaptive ATR, 3-10 USD (not clean) | -0.092 | -0.001 / +4 | -0.118 | - | - |
| A8 | A7 without the 10 USD cap | -0.066 | -0.023 / -192 | -0.091 | - | - |
| A9 | strong runs (>= 3.7 ATR, broke 72 h), stop beyond the start, 8 U | +0.012 | -0.058 / -193 | -0.079 | -0.028 | -0.073 (-0.013) |
| A10 | A9 + trail 0.5 x run, 240 min | +0.029 | -0.009 / -60 | -0.131 | +0.012 | -0.092 (-0.033) |
| D1 | deep limit 61.8 %, big runs, 1.618 ext. | +0.086 | -0.097 / -170 | -0.099 | -0.089 | -0.130 (-0.092) |
| A11 | A10 without the size test (window-informed) | +0.051 | +0.091 / +299 (not OOS) | -0.047 | +0.113 | -0.032 (+0.041) |

## Verdict, round 2 (2026-10-18)

- **RUN-A does not reach +0.15 R** (nor the +0.10 tolerance) in any form that was tested cleanly. The best clean
  window numbers: A7 -0.001 R (its stop rule came from F1's window) and A10 -0.009 R / -60 USD; the best number of
  all, A11 +0.091 R / +299 USD, is window-informed, rests on March (+310 USD of +299), and its one clean test (the
  older sample) is -0.032 R, the coin's level.
- **Why the losers lose, concretely:** (1) the "ended" runs (a V / double top right after the run) are exactly as
  frequent as a random walk predicts from where the entry sits inside the run - 42 features and a walk-forward
  LightGBM found nothing that tells them apart beforehand (the owner's exhaustion signs - the day's range used, the
  5th wave, divergence, a climax bar, the dollar - included); (2) with the stop at the pullback (A4-A8) the costs are
  about 0.10 R a trade and kind 3 (a dip just through the pullback, then the target) is a third of the losers, the
  same share as the coin's; (3) with the stop beyond the run's start (A9-A11) the costs fall to 0.02-0.05 R, but the
  stop is 20-100 USD in the window's big runs, and the trades the stop catches are the run-was-the-end cases (Asia-
  open rallies that rounded over, release spikes that faded, sells into a V bottom) - each one worth 3-10 small wins.
- **What the chart tools add: nothing measurable on gold M1-M30.** Fib retracement levels (23.6-100 %, the owner's
  grid from the last swing low to the previous high) hold as often as random levels at the same place (34,083 /
  11,094 touches on M5 / M15); the prior swing (100 %) holds LESS; the owner's rising trend line holds as often as the
  same line shifted off the swings, with or without a fib level in confluence; the zone / chart-read target in front
  finds room >= 5 USD in only 37-49 % of the entries and pays no more than 8 U; fib extensions, AB=CD and channel
  targets hit less often than 8 U for no better R; kind 2 (fell short) is only 3-7 % of the stopped losers, so
  smarter targets have little to fix.
- **What is real but small:** the run-scale side. Runs that broke the 72-hour extreme continue about 5 points more
  often than the random walk (design 5/5 half-years, window +0.053); RUN-A's side beats its mirror in 7 of 10
  half-years 2021-2026 (about +0.06 R gross). It turns into profit only when costs are a small share of the stop
  (the wide-stop regime of 2025-09 .. 2026-10).
- **Next ideas (not tested here):** (a) use RUN-A's two robust parts - "with a run that broke the 72-hour extreme"
  and "the side of a fresh run" - as context votes for F1 / S2 instead of a standalone setup; (b) if RUN-A stays on
  its own, run it only in the wide-stop regime (the stop beyond the start >= about 15 USD, costs <= 0.03 R) as a
  forward (paper) test of A11 - no claim beyond the measured past; (c) an H1-scale version (runs of 2.5 H1 ATR,
  targets 20-40 USD) to push the costs under 0.02 R in every regime - the gross edge measured here (+0.04-0.06 R)
  says even that would land near +0.03 .. +0.05 R, not +0.15.
