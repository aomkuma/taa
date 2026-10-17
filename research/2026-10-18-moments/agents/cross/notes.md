# Agent "cross" - notes (2026-10-17)

Angle: other markets as the source of direction (indices, the dollar composite, risk-on/off crosses), minutes to
a few hours, H1 at most. Owner update (2026-10-17): trade gold **and the seven majors**; indices/crosses are inputs
only. Design only on 2023-11-01 .. 2026-03-01 (five halves: 23-11, 24-05, 24-11, 25-05, 25-11 [4 months]);
the one test per frozen rule on 2026-03-01 .. 2026-10-14 (index data ends 2026-10-05 23:59 UTC).

Files: `panel.py` (aligned M1 closes of gold + 12 markets, ffill <= 3 min; AUDJPY = AUDUSD x USDJPY; USD
composite of the six majors), `align_check.py` (timestamps: the cross-correlation of 1-min returns peaks at lag 0
for every input, winter and summer, all hours and London/late hours: no clock shift that could fake a lead),
`measure.py` / `measure2.py` (correlations by half), `buckets.py`, `screen.py` / `screen2.py` (episodes,
drift-adjusted), `fxlab.py` (instruments, real costs, the simulator; `check_sim.py`: 0 mismatches vs
`ny_lab.M1.trade` on 400 random gold trades with ny_lab's costs), `design.py` (the trade grid), outputs `out_*.txt`.

Costs (the auditor's): gold entry = spread column + 0.08 + 0.07 slip, stop slip 0.15 (0.20 in 12-17 UTC);
FX: spread column + 0.25 pip, entry slip 0.2 pip, stop slip 0.3 pip. R = P&L / (stop + stop slip).

## Step 1 - what relations exist (design data, corr x100, vol-scaled returns, every 5th minute)

Input's last L minutes -> the target's next H minutes (not the same minutes). Flag = same sign in 5/5 halves.

Gold (`out_measure.txt`, `out_measure2.txt`):
- Equities (US500/JP225/US100, mean of US500+JP225 = "eq") and AUDJPY lead gold **in the same direction**
  (risk-on -> gold up later), all hours: eq L60 -> H60 +4.3 +1.0 +1.3 +2.4 +4.4 (partial after gold's own
  move +4.5 .. +6.1). Strongest in New York 12-17 UTC (AUDJPY L60 H60 +1.6 +1.1 +6.0 +5.1 +10.8) and 17-21 UTC
  (eq L60 H60 +17.4 +1.6 +6.8 +2.6 +0.6 - one half dominates). Tiny: 1-5 % correlation.
- The dollar composite's last 30-60 min -> gold: no stable sign in most cells (consistent with h6: gold and the
  dollar move together in the same minutes, -31 .. -56 corr, and the lead is not there).
- Gold's own: late 17-21 UTC a small reversal at 15 min -> 60 (-3.5, 5/5).
- As episodes (|z| >= 2, drift-adjusted), gold's excess move over 60 min is 0.4-1.5 USD with hit rates 52-56 %:
  below what a 5 USD target / real costs need (7-15 win points over a coin).

Majors (`out_measure2.txt`) - the cleanest structure found, consistent across pairs:
- **London 07-12 UTC: equities up over the last 30-60 min -> the dollar up over the next 30-120 min.**
  EURUSD eq L30 H60 -1.8 -3.3 -3.0 -5.4 -6.3 (partial -3.0 .. -8.7), GBPUSD -1.8 -2.1 -1.0 -4.4 -3.0,
  USDCHF +3.1 +6.8 +6.0 +3.8 +2.6, USDCAD +3.4 +2.9 +0.5 +6.0 +12.4, USDJPY +0.4 +2.9 +3.9 +7.9 +3.6. Same sign
  5/5 halves in five pairs (AUD/NZD not). Note the same-minute sign is the opposite (EURUSD +9 with US500 in the
  same minute), so this is the dollar's later move, not co-movement.
- **17-21 UTC: the sign flips** - equities up -> the dollar down later: USDCHF eq L60 H60 -2.1 -3.7 -7.2 -4.6
  -9.0, US100 similar; GBPUSD/AUDUSD/NZDUSD up, USDCAD down (episodes).
- New York 12-17: AUDUSD/NZDUSD follow equities (+2 .. +5), USDJPY fades big equity moves (episodes).
- Episodes (`out_screen2.txt`, drift-adjusted, before costs): London |eq30| >= 2.5 -> 60 min: USDCHF +4.0 pips,
  EURUSD +3.6, GBPUSD +3.7, USDCAD +2.0 (5/5 halves each; n ~105 = one every ~5.5 trading days); US100_60 >= 2.5:
  EURUSD +4.8, USDCHF +4.7. Costs ~1.3-1.6 pips. Edge ~0.3-0.5 of the pair's 60-minute sd.
- Multiple testing: screen2 ran ~2,300 cells; the London cluster is believable because five pairs agree with one
  economic sign (the dollar), not because one cell is high.

## Step 2 - trades on the design data (`design.py`, `out_design.txt`; real costs)

Grid: London (07-12 UTC) and 17-20 UTC families x 5 pairs + gold x inputs (eq30, eq60, US100_60) x thr 2.0/2.5 x
target/stop (FX 15/15, 20/15, 20/20, 25/20, 15/10 pips; gold 5/5, 8/6, 10/8) x 120/180 min x break-even.
- The **17-20 UTC flip does not trade**: every pair's cells average -0.05 .. -0.10 R (coin -0.12 .. -0.15). Dropped
  (the auditor also warns off the late hours).
- London: EURUSD is the clear best pair (mean of all its cells +0.075 R vs the coin -0.067); GBPUSD/USDCHF/USDCAD
  about 0 on average (coin -0.09 .. -0.11); USDJPY -0.05. Gold in London (equities up -> gold down) +0.03 avg; its
  best cells +0.14 R at 10/8 USD with 4/5 halves - not pursued (stops 6-8 USD are near the account limit and the
  edge is thinner than the FX one).
- The latest half (2025-11 .. 2026-02) was negative in almost every EURUSD cell - the reason is found below.

## Step 3 - why the losers lost (`refine.py`, `losers.py`; London rule trades with their context)

Context at the decision bar, closed bars only. Base: |eq30| >= 2.0, five pairs, 20/15 pips, 120 min (1,051 trades).
1. **The dollar had already moved our way** (the six-major composite without the pair, last 30 min, signed by
   the trade): the top third (usd30 > 0.28 sd) -0.127 R, negative in **5/5 halves**; the lower two thirds +0.05 /
   +0.11. 35 % of the losers vs 27 % of the winners sat there. The rule's premise is that the dollar has *not yet*
   followed the equities; when it already has, we buy the end of the move. -> keep only usd30 <= 0.
2. **Time exits, not stops, dominated** (481 of 1,051 at 20/15): a 20-pip target is about 2 H1 ATRs for EURUSD in
   London (ATR ~8-12 pips), so most trades just drift to the 120-minute bell. -> 15/10 pips (about 1.5 / 1.0
   H1 ATR) cut the time exits from ~50 % to ~30 %.
3. On the 4-pair, |eq30| >= 2.5, 15/10 rule (233 trades): the stopped losers (94) sat in **stretched** pairs - the
   pair's last 60-minute range was > 1.5 x its H1 ATR in 63 % of them (median stopped loser: 21.7-pip hour range
   vs a 10-pip stop); the trades with a calm pair made +0.284 R (5/5 halves) vs +0.005 for stretched ones. The
   cause: a wide last hour means the pair is already moving on its own news (the 10-pip stop is inside its current
   swing) and the equity impulse is not what drives it. -> rng60 <= 1.5 x ATR(H1).
4. **The pair itself had already moved our way** (own30 > 0.5 sd): 31 trades at -0.138 R vs +0.165 - the same
   "late" cause as (1), for the pair alone. -> own30 <= 0.5.
5. At the 4-hour extreme our way (pos > 0.85): -0.08 (19 trades) - mostly covered by (4). H1 trend against or
   with the trade: no difference (+0.11 vs +0.14). Hour 10 UTC weak (-0.37 on 25) - no cause, not used.
   USDJPY: weakest pair in every step, its sign held only in the correlation; dropped from the basket.

## Step table (design data 2023-11 .. 2026-02, five halves; `out_steps.txt`, `out_steps2.txt`)

R a trade (net of real FX costs), periods = the five halves (trades). Coin = random side on the same minutes.

| step | rule | n | /day | win % (coin) | R (coin) | halves R | max DD USD | streak |
|---|---|---|---|---|---|---|---|---|
| s0 | 5 pairs, \|eq30\|>=2.0, 20/15, 120 m | 1051 | 1.73 | 22 (20) | +0.011 (-0.080) | -0.12 +0.03 +0.10 +0.07 -0.13 | 57.2 | 15 |
| s1 | + the dollar not yet moved (usd30<=0) | 626 | 1.03 | 23 (20) | +0.055 (-0.082) | +0.03 +0.10 +0.04 +0.16 -0.15 | 32.1 | 12 |
| s1b | + 4 pairs (no USDJPY) | 482 | 0.79 | 20 (17) | +0.074 (-0.083) | +0.05 +0.08 +0.07 +0.18 -0.10 | 22.7 | 10 |
| s2 | + 15/10 pips | 490 | 0.81 | 27 (21) | +0.064 (-0.153) | -0.05 +0.06 +0.14 +0.18 -0.12 | 16.4 | 9 |
| s4 | + \|eq30\|>=2.5 | 233 | 0.38 | 30 (22) | +0.125 (-0.137) | +0.22 +0.18 +0.04 +0.16 +0.05 | 10.2 | 12 |
| s6 | + the pair not yet moved (own30<=0.5) | 202 | 0.33 | 31 (23) | +0.165 (-0.110) | +0.26 +0.21 +0.08 +0.15 +0.18 | 9.7 | 10 |
| s7 | + the pair not stretched (rng60<=1.5 ATR) | 88 | 0.14 | 36 (26) | +0.325 (-0.025) | +0.46 +0.52 +0.17 +0.28 +0.37 | 5.6 | 6 |

Side branches: ATR stops 1.5/1.0 or 2.0/1.5 instead of 15/10 (+0.062 / +0.065, no better); 180 min (+0.035,
worse); s7 at thr 2.0 +0.143 (204 trades, halves +0.00 .. +0.31); s7 with 20/15 +0.242; s7 with all five pairs
+0.309 (109); s7 with EURUSD + GBPUSD only +0.644 on 39 trades (too few; over-selected - not frozen).
Account at 0.01 lot: a 10-pip stop = about 1.0-1.3 USD (USDCHF about 1.25 USD, USDCAD about 0.75 USD); worst
single loss 1.33 USD; 6 average losses about 5.4 USD = fits a 50 USD account (11 %) and a 100 USD one.
Caveats: s6/s7 filters were picked from the design losers (one look each, with a stated cause); s7 keeps only
~3 signals a month. The coin also improves with the filters (-0.137 -> -0.025), i.e. part of s7's gain is calmer
pairs costing less in R; the edge over the coin still grows (+0.26 -> +0.35).

## FROZEN RULES - written before the test (2026-10-17)

Common: signal at the close of an M1 bar between 07:00 and 11:59 UTC on a weekday: eq30 = mean of the vol-scaled
30-minute log returns of US500 and JP225 (close t-30 -> close t, divided by the std of the previous 1,440 M1 log
returns x sqrt(30), clipped +-6). Fire when |eq30| >= thr, then silent 60 minutes. Side: equities up -> the dollar
up (sell EURUSD / GBPUSD, buy USDCHF / USDCAD); equities down -> the mirror. Each pair traded on its own, one
position per pair at a time. Entry at the next M1 open, target / stop in pips, 120-minute time exit, no
break-even. Costs: spread column + 0.25 pip, 0.2 pip entry slip, 0.3 pip stop slip. 0.01 lot.

- **X4** (= s4): pairs EURUSD, GBPUSD, USDCHF, USDCAD; thr 2.5; skip when the dollar composite without the pair
  (EURUSD, GBPUSD, AUDUSD, NZDUSD inverted; USDJPY, USDCHF, USDCAD) has moved the trade's way over the last 30 min
  (vol-scaled, > 0); target 15 / stop 10 pips.
- **X6** (= s6): X4 + skip when the pair's own vol-scaled 30-minute move in the trade's direction > 0.5.
- **X7** (= s7, the primary): X6 + skip when the pair's high-low range over the last 60 M1 bars > 1.5 x its
  ATR14 on H1 (last closed H1 bar).

The test: `steps.py --test X4 | X6 | X7`, once each, 2026-03-01 .. 2026-10-14 (index data to 2026-10-05).

## THE TEST (2026-03-01 .. 2026-10-14; indices to 10-05), run once per frozen rule (`out_test_X4/X6/X7.txt`)

| rule | n | /day | win % (coin) | R (coin) | edge vs coin | USD @0.01 | months + | worst | streak | max DD |
|---|---|---|---|---|---|---|---|---|---|---|
| X4 | 132 | 0.84 | 12 (19) | -0.329 (-0.211) | -0.118 R, -7 win pts | -46.4 | 2/8 | -1.32 | 14 | 50.2 |
| X6 | 129 | 0.82 | 12 (20) | -0.332 (-0.180) | -0.152 R, -8 pts | -46.2 | 1/8 | -1.32 | 14 | 48.9 |
| X7 | 36 | 0.23 | 11 (28) | -0.309 (-0.004) | -0.305 R, -17 pts | -12.8 | 1/7 | -1.32 | 7 | 14.0 |

X4 by month (R / USD): 03 -0.48 / -20.5 (39 trades), 04 -0.19 / -3.4, 05 -0.63 / -16.7, 06 -0.63 / -5.2,
07 +0.14 / +0.5, 08 -0.25 / -1.6, 09 +0.04 / +1.5, 10 -0.39 / -1.0. Every pair lost (EURUSD -0.40, GBPUSD -0.38,
USDCHF -0.34, USDCAD -0.18). Losers' kinds X4: 78/14/8 % vs the coin 76/12/12 % - kind 1 (wrong way) dominates.
**Verdict: FAILED.** The rule picked the wrong side more often than a random side.

## Why it lost (post-test diagnosis - not a new rule; `post_test.py`, `losers.py X4 test_X4`)

1. **The regime changed: the dollar and equities became tightly coupled in the same minutes.** EURUSD vs equities,
   same-minute correlation in London: 10-27 in every design quarter (and -9 .. +2 in 2025 Q2-Q4) vs **+40 in 2026
   Q1-Q2** and +24 in Q3. When equities jump the dollar now falls with them at once, hard: the test signals' usd30
   averaged about -2.0 sd (design about -1.2); the stopped losers -2.2. The rule bets on the dollar's *later*
   catch-up the other way (a delayed reversal of that co-move), and in 2026 the co-move continued instead.
2. The quarter-level relation was less stable than the half-years showed: eq30 -> the dollar's next 60 min had the
   wrong sign in 2 of 9 design quarters (2024 Q4, 2025 Q3) and is about zero or wrong in 2026 Q1/Q3.
3. **The basket did not diversify**: the four pairs move as one dollar - 34 signals x 4 pairs; when a signal
   failed all four stopped together (-1.00 R on 4 legs, e.g. 03-03 11:00, 03-05, 03-23, 03-31, 04-07 08:00), so a
   losing signal cost ~4.4 USD and the streak hit 14 trades.
4. Equity-up signals (sell EUR/GBP, buy USD) lost most (-0.47 R, 72 trades) vs equity-down (-0.16, 60).
5. Signals fired twice as often (5 a month vs 2) in this more volatile period (March: 10 signals).
Next idea (needs fresh data to test): make the side conditional on the coupling regime measured on the past
20 days (same-minute correlation of the pair with equities) - fade the co-move only while the coupling is weak,
follow the equities' direction (continuation) while it is strong - and trade one pair per signal (EURUSD), not four.
