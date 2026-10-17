# Agent "trend" - notes (2026-10-17)

Angle: gold's minute-scale returns are a random walk, so look at longer intraday horizons (holds up to 2-3 h,
H1 the largest timeframe) and at regime (trend days vs range days). Design only on data before 2026-03-01
(2021-10 .. 2026-02, nine half-years); one test per frozen rule on 2026-03-01 .. 2026-10-14.

Files: `lab.py` (M1 arrays, session opens, a loop trade simulator), `sim.py` (the same simulator vectorised;
cross-checked against the loop on 300 random trades x 3 exit modes: 0 mismatches in USD, minutes and the losers'
kinds), `foundations.py`, `events.py` / `orb_grid.py` / `probe*.py` (opening-range breakouts), `events2.py` /
`probe3.py` (prior-range breakouts), `trendday.py`, `nycont*.py` (New York continuation), `test.py` (the one test).
Outputs: `out_*.txt`.

Conventions: the brief's (decide at a bar's close, fill at the next open, BUY at ask + 0.07, SELL at bid - 0.07,
a SELL's stop/target on the ask, stop before target in one bar, a stop pays 0.07, a time exit at the close with
slippage). One stricter detail: a bar that *opens* through the stop exits at its open (a gap).
R = USD / (stop distance + 0.07).

## Step 1 - where is there continuation at all? (`foundations.py`, design data)

- Variance ratios of vol-scaled returns, nine half-years: VR(30 min) 0.97-1.04, VR(60) 0.98-1.07,
  VR(120) 0.98-1.20, VR(240) 0.97-1.18 (8 of 9 halves above 1 at 240 min, mean about 1.06). The lag-1
  correlation of consecutive 120/240-minute returns -0.05 .. +0.13, no sign held everywhere.
  => at 1-4 hours gold is still close to a random walk, with at most a faint trend tilt at 4 hours.
- H1 returns: lag-1 autocorrelation -0.05 .. +0.05; after a big hour (|z| > 1.5) the next hour -0.07 .. +0.07 sd.
  The last 4 hours' direction -> the next 2 hours: correlation -0.03 .. +0.07. Nothing usable on its own.
- Session opens, the first 15/30/60 minutes -> the next 60/120/180: agreement 46-54 %, the sign of the mean
  continuation flips between half-years in every session. The first hour's range vs its 20-day mean and the
  first hour's close position do not separate continuation days stably.

## Step 2 - opening-range breakouts, every session (`orb_grid.py`, 6,720 cells)

Events: each session open (Asia 00:00 UTC, London 08:00 London, NY 08:30 and 09:30 ET), range = the first
15/30/60 minutes, the first M1 close beyond it within 120 minutes, entry next open. Stops: range mid, far side,
0.10/0.15 ADR; exits: 1-3R targets, 2R + break-even, trailing 1R; holds 120/180 min; ten context filters.

- Every session, every range length, no filter: negative (baseline stop mid, 2R, 180 min: Asia -0.10 .. -0.26 R,
  London -0.09 .. -0.16, NY 08:30 -0.01 .. -0.09, NY 09:30 -0.05 .. -0.09). Asia's small ranges make the costs
  ~0.15 R alone.
- Asia and London: nothing positive in most halves under any stop/exit/filter. The prior-range breakouts
  (Asia range broken in London, London morning broken in NY, the 22-24 UTC range broken in Asia, 07:00-08:30 ET
  broken at 08:30): all negative or coin-like (`out_probe3.txt`).
- One pocket: **New York, the 08:30-09:30 ET range, broken in the H1 trend's direction soon after 09:30 ET**
  (the US equity open), stop at the range's far side, a trailing exit. Its neighbourhood is positive in most
  halves (`out_probe1.txt`): far-side stop with any of the trailing exits and 1R/2R targets (+0.06 .. +0.15 R).
  The same rule on the 08:30 15/30-minute ranges or at 09:30 is near 0 or negative - the cause looks specific:
  the equity open breaking the release hour's range with the trend already running.
- Side permutation (same entries, sides shuffled, long share kept): ours +0.150 vs the permuted 0.023 +- 0.048
  (p 0.007); the delay <= 120 family +0.086 vs -0.002 +- 0.037 (p 0.007). A coin side: 0.002 +- 0.050.
  But the always-long side on the same entries made +0.116 (gold's bull drift); our shorts only +0.03.
- The H1 trend is what carries it: without it -0.063 R (1/9 halves), with it +0.086 (7/9) on all breakouts.

## Step 3 - trend days / continuation into New York (`trendday.py`, `nycont_grid.py`)

- The day's move so far (from 00:00 UTC, in ADR units) -> the next 2-3 hours, by checkpoint hour: around the NY
  morning (13 UTC) +3 % ADR in 8/9 halves; Asia / London hours flip.
- As a trade at NY checkpoints (09:30-11:00 ET; |move| >= 0/0.2/0.3/0.5 ADR, H1, at the day's extreme, beyond
  the 08:30 range; stops 0.10-0.20 ADR): baseline -0.03 .. -0.11 R; the best cells +0.06 .. +0.10 R with 7-8/9
  halves - weaker than the breakout and fragile. Not taken further.

## Step 4 - the step table for the NY breakout (design, `out_probe4.txt`, `out_probe5.txt`)

Stop at the range's far side, trailing exit (from +1R the stop trails 1R behind the best price), 180 minutes.

| Step | N (4.4 yrs) | R/trade | win % | USD/trade | halves + |
|---|---|---|---|---|---|
| 0 every first close beyond the 08:30-09:30 ET range (by 11:30), time exit only | 1056 | +0.004 | 47 | +0.12 | 5/9 |
| 0b + trailing exit | 1056 | +0.009 | 50 | +0.07 | 5/9 |
| 1 + the H1 trend agrees | 505 | +0.086 | 52 | +0.59 | 7/9 |
| 2 + the breakout by 10:00 ET | 389 | +0.124 | 53 | +1.16 | 8/9 |
| 3 + the range < 0.35 x ADR20 | 260 | +0.168 | 53 | +1.30 | 9/9 |
| (alt: step 1 + by 09:45 ET, no range cap) | 314 | +0.150 | 54 | +1.35 | 9/9 |

Rejected: skip the 08:30 release days (better mean, worse halves - 7/9); ranges < 0.30 / 0.25 ADR (higher
means, fewer halves positive).
Weak spot: the halves 2024-03 .. 2025-08 are only +0.01 .. +0.13 R; the strength is 2021-2023 and 2025-09+.
R spread: sd 1.05 R a trade, so ~50 trades in the test give a standard error of ~0.15 R.

## FROZEN RULE T1 - written before the test (2026-10-17)

"NY range breakout with the H1 trend" (one trade a day at most):
1. The range: the high and the low of the M1 bars opening 08:30 .. 09:29 New York time (DST-aware).
2. The trigger: the first M1 bar opening 09:30 .. 09:59 ET whose close is above the range high (BUY) or below the
   range low (SELL); the first of the two that happens decides. None by 09:59 -> no trade.
3. The H1 trend agrees: on the last completed H1 bar (UTC hours) before the decision, EMA20 of H1 closes above its
   value 3 bars before and the H1 close above EMA50 (BUY); EMA20 below its value 3 bars before and the close below
   EMA50 (SELL). Otherwise no trade (no second chance that day).
4. The range < 0.35 x ADR20 (the mean UTC-day high-low of the previous 20 weekdays).
5. Entry at the next M1 bar's open. Stop at the range's far side (a BUY's at the range low on the bid, a SELL's
   at the range high on the ask). No fixed target. Once the best move reaches 1R (R = the distance from the fill
   to the stop), the stop trails 1R behind the best price, updated at each M1 close. Exit at the latest at the
   close of the 180th minute.
6. The losers' kinds use a reference target of 2R.

## FROZEN RULE T0 (secondary, the step-3 alternative) - written before the test

As T1, but the trigger window 09:30 .. 09:44 ET and no range cap (rule 4 dropped).

The test (`test.py --test`) also reports the step table (0 .. 3) on the test window, month by month, the coin
side (300 draws: mean and spread; and its losers' kinds) and the side-permutation null.

## THE TEST (run once, 2026-10-17; `out_test.txt`) - 2026-03-01 .. 2026-10-14

| Step (same rules as the design table) | N | /day | R/trade | win % | USD (0.01 lot) | months + | coin R (300 draws) | ours beats coin |
|---|---|---|---|---|---|---|---|---|
| 0 every breakout, time exit | 149 | 0.92 | -0.120 | 36 | -657.8 | 2/8 | -0.057 +- 0.074 | 20 % |
| 0b + trailing exit | 149 | 0.92 | -0.164 | 39 | -735.1 | 2/8 | -0.046 +- 0.069 | 5 % |
| 1 + H1 trend agrees | 79 | 0.49 | -0.132 | 37 | -216.2 | 1/8 | -0.028 +- 0.106 | 18 % |
| 2 + by 10:00 ET | 62 | 0.38 | -0.072 | 42 | -61.5 | 3/8 | -0.002 +- 0.116 | 28 % |
| **3 = T1** + range < 0.35 ADR | **52** | **0.32** | **-0.066** | **44** | **-39.3** | **2/8** | -0.016 +- 0.135 | 36 % |
| **T0** (H1 + by 09:45, no cap) | **52** | **0.32** | **-0.053** | **44** | **+8.5** | **2/7** | 0.000 +- 0.125 | 34 % |

T1 by month (N, win %, USD, R): 03: 7, 57 %, +97.0, +0.69 | 04: 5, 80 %, +48.9, +0.43 | 05: 8, 25 %, -110.0, -0.53 |
06: 6, 50 %, -14.2, -0.11 | 07: 10, 50 %, -8.7, -0.22 | 08: 11, 36 %, -16.3, -0.10 | 09: 4, 25 %, -34.4, -0.53 |
10: 1, 0 %, -1.6, -0.07.
Losers' kinds (reference target 2R): T1 95/0/5 % of 20 stopped vs the coin 97/0/3 %; T0 95/0/5 vs 97/0/3.
(With the trail starting at +1R, kind 2 cannot occur by construction - a trade that reached 1R is trailed, not
stopped at the initial stop - so the kinds carry little information for this exit.)
Two test trades rechecked by hand against the bars and the loop simulator (2026-04-27 SELL +10.21 trail exit,
2026-07-22 BUY +12.36 time exit): match.

**Verdict: fails.** Out of sample the rule picks the side like a coin (it beats only 34-36 % of coin draws); the
nine positive design half-years were the best of ~7,000 correlated cells, and the permutation p of 0.007 did not
account for that search. In the test the plain NY breakout was clearly worse than in the design (step 0: -0.12 R
vs +0.004 R; longs -0.22 R): in 2026's high volatility the 09:30 breakouts of the 08:30 range reversed more often
than they ran.
What did carry over: each filter step cut the loss per trade on the test too (step 0b -0.164 R -> 1: -0.132 ->
2: -0.072 -> 3: -0.066; USD -735 -> -39 for 149 -> 52 trades). Most of that is fewer trades on the worse days, not
a better side (the coin on the same entries also improves, -0.046 -> -0.016 R), so it is a loss cut (stage 1),
not an edge.
