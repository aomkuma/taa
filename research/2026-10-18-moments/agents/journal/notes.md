# Journal agent - notes (2026-10-17)

Learning like a trader: chart the confluence rule's trades on design data, keep a journal (journal.md), turn the
lessons into a revised rule, check it by half-year against a coin, freeze, one test on 2026-03-01 .. 10-14.

## Files

- `jlib.py` - M1 arrays per instrument, the one-trade simulation (ny_lab.M1.trade with the instrument's slippage),
  the confluence selection loop (one position, at most 2 trades per day and session), the coin (10-20 seeds).
- `build.py` - candidate table (every minute of the three windows x both sides), the confluence parts re-implemented
  from M1 (so they exist before 2025-12 and for FX), plus chart context. Runs under `.venv` (ChartReadFrame).
  `design` = 2023-11-01 .. 2026-02-28; `test` built only after the rule is frozen.
- `verify.py` - build.py vs own_ml_long + own_ml_cr_levels on 2025-12 .. 2026-02.
- `rules.py` - every rule (written here first), `lab.py` - half-year table vs coin, `charts.py` - trade charts.

## Conventions

- Gold sizes in U = price / 4100 USD (ny_lab's scaling; in 2026 U is 0.98-1.29 USD). Target 8 U, stop beyond the
  level by one M1 ATR, 3-10 U, break-even at 0.6 of the target, 60-minute horizon (confluence.py). R = P&L / (stop +
  slippage). Costs as ny_lab (ask/bid + 0.07 slippage).
- Design half-years: 2023-11..04, 2024-05..10, 2024-11..2025-04, 2025-05..08 (4 months), 2025-09..2026-02.
  Charts and journal only on 2025-09 .. 2026-02.

## Rule B0 (baseline, written before running)

confluence.py exactly: H1 tide (H1 EMA20 slope with the side and close beyond EMA50), the nearest level behind the
price (today's / yesterday's / Asian extreme as of 15 min before, round 50, M15 / H1 chart-read level) within 3 M1
ATR and the last 5 minutes' extreme within 1 ATR of it, price action (M1 or M5 hammer, M1 engulfing, sweep and
reclaim), two of three M5 indicators (RSI turning from its side of 50, MACD histogram rising, Stochastic cross);
stop = level - 1 ATR, 3-10 U; target 8 U; break-even at 0.6; 60 min; all three windows.

### B0 result (design, real costs; out_B0.txt)

1150 trades 2023-11 .. 2026-02, win 24%, **-0.140 R/trade**, 0/5 half-years positive; the coin on the same minutes
-0.151 R (10 seeds). Last half-year 2025-09 .. 2026-02: 267 trades, -0.125 R (coin -0.104). Kinds ours 53/4/43 vs
coin 52/4/44 - the rule picks the side like a coin (as on the test window in round 9).

## Round 1 lessons (journal.md, 60 charts of 2025-09 .. 2026-02) -> rules J1..J6, written before running

All on top of B0; the earlier half-years (2023-11 .. 2025-08) were not charted, so they are the check.

- J1 M5 with the trade: the last closed M5 bar's close beyond its EMA20 on the trade's side and the EMA20's last
  change not against the side ((e20 - e20[-1]) * side >= 0).
- J2 H1 structure not against: chart-read H1 structure and "now" structure, signed by side, both >= 0.
- J3 no knife / spike: |ret15| <= 4 M1 ATR and M1 ATR <= 2x its trailing day median (atr_ratio).
- J4 no US release from 15 min before to 15 min after (since_rel > 15 and until_rel > 15).
- J5 stop beyond the sweep: stop price = the farther of (level - 1 ATR) and (the last 15 minutes' extreme - 0.5
  ATR) for the side; 3-10 U as before.
- J6 = J1 + J2 + J3 + J4 + J5 (the trader's revised rule, version 1).

### Round 1 results (design, real costs; out_J1-6.txt) - R/trade, ours vs the coin (10 seeds) on the same minutes

| rule | trades | win % | R/trade | coin R | halves + | note |
|---|---|---|---|---|---|---|
| B0 | 1150 | 24 | -0.140 | -0.151 | 0/5 | baseline |
| J1 M5 with | 472 | 28 | -0.071 | -0.165 | 1/5 | the only lesson clearly above the coin: 3 of 5 halves (2023-11, 2024-11, 2025-09) |
| J2 H1 structure | 823 | 24 | -0.137 | -0.148 | 0/5 | nothing |
| J3 no knife | 830 | 21 | -0.137 | -0.187 | 1/5 | small, mixed |
| J4 no news | 1132 | 23 | -0.141 | -0.150 | 0/5 | nothing (few trades touched) |
| J5 sweep stop | 1111 | 24 | -0.100 | -0.118 | 1/5 | cuts the loss (kind 3 43% -> 34% in 2025-09..02) but the coin gains as much: a cost/stop effect, not side |
| J6 all | 201 | 28 | -0.012 | -0.060 | 3/5 | 0.34 trades/day; halves -0.30 -0.19 +0.32 +0.15 +0.05 |

Ablation next (written before running): J7 = J1 + J5; J8 = J1 + J3 + J5; J9 = J1 + J2 + J5; J10 = J1 + J4 + J5.

### Ablation (out_J7-10.txt)

| rule | trades | win % | R/trade | coin R | halves + | 2025-09..02 ours / coin |
|---|---|---|---|---|---|---|
| J7 = J1 + J5 | 387 | 29 | -0.021 | -0.052 | 3/5 | +0.087 / +0.083 |
| J8 = J1 + J3 + J5 | 300 | 29 | -0.015 | -0.085 | 3/5 | +0.085 / +0.028 |
| J9 = J1 + J2 + J5 | 263 | 30 | +0.001 | -0.104 | 3/5 | +0.069 / -0.008 |
| J10 = J1 + J4 + J5 | 383 | 29 | -0.026 | -0.050 | 3/5 | +0.082 / +0.082 |

The edge over the coin is 0.03-0.10 R and comes mostly from 2024-11..2025-04; on the charted half-year J7 equals
the coin. Most of the loss cut (B0 -0.140 -> J7 -0.021) is the wider stop (cheaper in R) plus M5-with.

## Round 2 - journal of J7's 48 trades of 2025-09 .. 2026-02 (charts/J7), and the numbers (out_analyze_B0.txt)

New losers (journal.md round 2): buying under the 72-hour H1 high / the day high (room < 0.5 tp) after a vertical
run; flat H1 (EMAs tangled, close within ~1 H1 ATR of the EMA50) -> chop; a release 5 min ahead. Winners again:
compression on the level then a break, or a higher low after a sweep, then a break.
Bins of B0's 1150 trades vs the coin (SE ~0.08 R a bin): nothing beyond noise; consistent in both the charted and
the earlier halves only weakly: flat H1 (h1_c_e50 < 0.85) the worst bin (ours -0.249 vs coin -0.188); the trades
*with* 60-min momentum (ret60 > +3 ATR) and at the 4-hour extreme on their side the best (ours -0.003 vs coin
-0.080).

### Rule K (written before running): the trader's trigger - test, higher low, break

Context: H1 tide (B0) and M5 with (J1). Setup (for a buy; mirror for a sell): L = the lowest low of the last 30
M1 bars (the test); the level = B0's nearest level behind the close; the test reached the level zone:
L <= level + 1 ATR and L >= level - 2 ATR (a sweep allowed, not a collapse); a higher low: the lowest low of the
last 5 bars >= L + 0.3 ATR; the trigger: the decision bar closes above the highest high of the 10 bars before it;
the close above the level. Stop = L - 0.5 ATR, 3-10 U. Target 8 U, break-even 0.6, 60 min (as B0). No B0
price-action / indicator conditions (the trigger is the price action).
K2 = K + no release +-15 min + not a flat H1 (h1_c_e50 >= 0.85).

### K result (out_K.txt): no

K 708 trades -0.104 R (coin -0.094); K2 577 -0.104 (coin -0.098). The "test, higher low, break" trigger made
mostly time exits in Asia; dropped.

## Round 3 (after the lead's round 11): W2 / W3 = B0 + H1 leg not against + not flat H1 + pos240 >= 0.5 / 0.75

Reproduced on design (out_W.txt): W2 299 trades +0.011 R (coin -0.116), W3 198 trades +0.055 R (coin -0.070), 3/5
halves +. Account at 0.01 lot (design, gold 2000-5300): W3 worst loss -12.63 USD, longest losing streak 9, max DD
57.5 USD (more than a 50 USD account), average full loss 3 USD (older, cheaper gold). The test (2026-03..10) was run
once by the lead - SEEN.

Charts: charts/W3 (all 90 stopped losers + 30 random winners of 2023-11 .. 2026-02); journal.md round 3.
Causes read off the charts, coded before counting (causes.py):
- C1 spike entry: the decision bar's body >= 1.5 M1 ATR with the side, or the last 3 bars moved >= 3 ATR with it
  (the fill sits at the end of an impulse; the snap-back takes the stop).
- C2 under the 72-hour extreme: the 72-h high (buy) / low (sell) as it stood 15 min before is in front, closer
  than half the target.
- C3 the stop inside the last 15-minute swing (for a buy the stop above the 15-min low).
- C4 stretched: the 60-min move with the side >= 8 ATR.
- C5 a US release within 15 min. C6 late in the window (NY >= +120 m, Asia >= +100 m). C7 fast tape (ATR >= 2x).

### Causes counted (out_causes_W3.txt) - what the eye saw did not hold in the count

| cause | share of stopped losers | share of winners | R with / without |
|---|---|---|---|
| C1 spike entry | 13% | 17% | +0.107 / +0.046 |
| C2 under the 72-h extreme | 13% | 28% | **+0.420** / -0.041 (the opposite of my reading: just under the 72-h high, the breakout came) |
| C3 stop inside the 15-min swing | 92% | 89% | (almost every trade) |
| C4 stretched 60-min move | 17% | 20% | +0.142 / +0.038 |
| C5 release within 15 min | 2% | 6% | n = 8 |
| C6 late in the window | 14% | 15% | -0.034 / +0.074 |
| C7 fast tape | 42% | 40% | -0.059 / +0.127 |

What does separate them is the path right after the entry (W3, 198 design trades):
- winners went at once: their worst dip before the target was a median 0.31 of the stop (0.6 M1 ATR), 90% within
  0.81 of the stop;
- kind 3 losers (39 of 88 full losses, 44%): the pullback before the move resumed was a median 2.0x the stop
  (3.5 ATR) - a real pullback after entering at the end of a push, not a hair-trigger stop hunt; their stops were
  the tightest (1.9 ATR vs 2.4 for winners; the level 0.7 ATR under the entry vs 1.1), and they came earlier in the
  session (median +52 min vs +73);
- kind 1 losers (49, 56%): the push simply stopped (never came within half the target), more often in a fast tape
  (ATR 1.93x its median vs 1.75x) and further below the 72-h extreme (room 0.83 vs 0.46 of the target).
So a W3 trade that is right moves within minutes; one that has not moved is the one that ends in a stop.

### Round 3 changes (written before running; exits.py, design, W3 entries, ours vs the coin)

- X1 time check: at minute k (5 / 10 / 15) after the entry, if the best move so far is under g of the target
  (0.25 / 0.4), exit at that bar's close (market, slippage). Otherwise as W3 (BE 0.6, 60 min).
- X2 entry at the retest: instead of the market, a limit at the level + 0.5 ATR (buy; mirror) valid 10 minutes;
  stop and target unchanged in price (so R per trade changes).
- X3 W3 + only "under the 72-h extreme" (room72 0..0.5 target) or beyond it (a breakout): room72_tp < 0.5.

### Round 3 results (design; out_exits_W3.txt, out_room72.txt), ours vs the coin

| change on W3 | trades | win % | R/trade | halves + | max DD USD | verdict |
|---|---|---|---|---|---|---|
| W3 as is | 198 | 33 | +0.055 | 3/5 | 57.5 | - |
| X1 time check k5..k15, g .25/.4 | 200-204 | 24-31 | +0.003..+0.040 | 2-3/5 | 54-58 | worse: it cuts winners that dip a little first |
| X2 limit at the level + 0.5 / 1 ATR | 137 / 160 | 23 / 27 | -0.042 / +0.019 | 2/5 | 57-62 | worse: the retest fills the losers, misses the runners |
| X3 room72 < 0.5 target | 98 | 38 (coin ~28) | **+0.207** | 4/5 | 21.3 | kept (thresholds 0.25 / 0.75 / 1.0: +0.181 / +0.184 / +0.157) |
| W2 + X3 (< 0.5) | 100 | 38 | **+0.222** | 4/5 | 21.3 | the same trades, simpler (pos240 >= 0.5) |
| B0 + X3 (< 0.5) | 143 | 33 | +0.037 | 4/5 | 38.6 | the room filter needs the H1 filters with it |

Caveat: X3 was chosen after counting W3's design trades (C2 above); it is a design-fitted filter. Its thresholds
are flat from 0.25 to 0.75 and it holds in 4 of 5 half-years, which is the only defence.

## Rule V1 (frozen candidate, written before its charts and before any test run)

V1 = B0 + the H1 ZigZag leg not against the side (cr_H1_leg_dir >= 0) + not a flat H1 (|h1_c_e50| >= 0.85) +
pos240 >= 0.5 + the 72-hour extreme in front (the highest high for a buy / lowest low for a sell of the 4320 M1
bars ending 15 minutes before the decision bar) closer than 0.5 of the target or already behind the price
((front - close) x side < 4 U). Entry, stop (level - 1 ATR, 3-10 U), target 8 U, break-even 0.6, 60 min, one
position, 2 a session: as B0. Real costs (auditor).

### V1 result (design; out_V1.txt): 100 trades (0.17/day), win 38%, +0.222 R, 4/5 halves (-0.169, +0.452, +0.101,
+0.138, +0.289), coin -0.055; worst -11.44 USD, longest losing streak 7, max DD 21.3 USD.

### Round 4 - V1's 40 stopped losers (charts/W3, same entries; journal.md round 4; out_causes_V1.txt)

Concrete causes: kind 3 (15 of 40) mostly entries just after a jump in a fast tape (ATR 2-3x its median): the
snap-back of the jump took a 2-ATR stop, then the move went on (#7 #23 #34 #48 #93); kind 1 (21 of 40) mostly at the
72-h high after a vertical H1 run with H1 rejection wicks (#68 #2 #12) or already through it. Counted on V1's 100:
fast tape (ATR >= 2x day median) R -0.014 (n 39) vs +0.372 (n 61), losers 45% / winners 34% (halves inconsistent:
88/100, 56/25, 17/17, 50/40, 18/33); already beyond the 72-h extreme (room < 0) R -0.043 vs just under it +0.509.

### Rule V2 (written before running): V1 + not a fast tape (atr_ratio < 2)

### V2 result (design; out_V2.txt): 63 trades (0.10/day), win 40%, +0.359 R, 5/5 halves (+0.096 on 3 trades, +0.842,
+0.106, +0.341, +0.228), coin +0.046; worst -9.96, streak 7, max DD 21.3 USD. A second design fit on 100 trades.

## The test, 2026-03-01 .. 10-14 (out_test_gold.txt) - WINDOW ALREADY SEEN (the lead ran W2/W3 on it in round 11;
V1/V2 derive from W3). Run once each, after V1/V2 were written above.

| rule | trades | /day | win % | R/trade | USD 0.01 lot | months + | worst / streak / max DD USD | coin R (win %) | kinds ours / coin |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 431 | 2.66 | 31 | -0.033 | -112.1 | 2/8 | -11.69 / 13 / 187.7 | -0.073 (30) | 53/5/42 / 53/5/42 |
| W3 | 75 | 0.46 | 33 | +0.030 | +34.5 | 6/8 | -11.52 / 6 / 27.2 | -0.064 (31) | 53/12/35 / 49/7/44 |
| V1 | 18 | 0.11 | 50 | +0.294 | +44.1 | 5/6 | -6.98 / 3 / 16.7 | +0.106 (42) | 100/0/0 / 72/0/28 |
| V2 | 15 | 0.09 | 53 | +0.378 | +42.3 | 4/6 | -5.25 / 3 / 14.2 | +0.167 (42) | 100/0/0 / 61/0/39 |

18 and 15 trades: one or two trades change the sign (SE ~0.3 R). The coin is positive on V1's minutes too (+0.106):
the 72-h-extreme moments move far either way, and ours took the right side 8 points more often.

## FX (written before running): FW3 = W3's logic in pips on EURUSD and USDJPY - target 20 pips, stop level - 1 M1
ATR within 7.5-25 pips, break-even 0.6, 120 min; FW3s the same with 15 / 6-19 pips; FV1 = V1's logic (the 72-h
extreme closer than 10 pips) with 20 pips. Costs: the pair's spread column + 0.25 pip, 0.2 pip slippage, 0.3 pip on
stops. Round levels every 50 pips. Same windows (Asia 00-02 UTC, London 08-09:30, NY 08:15-11:15 ET).

### FX design results (out_fx_design.txt), R/trade (coin), trades

| rule | EURUSD | USDJPY |
|---|---|---|
| FB0 (B0 in pips, 20) | -0.178 (-0.092), 419 | -0.165 (-0.163), 1365 |
| FW3 (20 pips) | -0.176 (-0.253), 77 | -0.042 (-0.072), 265 |
| FW3s (15 pips) | +0.026 (-0.182), 117, 4/5 halves | -0.097 (-0.177), 308 |
| FV1 (20 pips) | -0.093 (-0.045), 48 | -0.075 (-0.152), 150 |

Every FX variant loses heavily in 2025-05 .. 08 (-0.4 .. -0.8 R) and is near zero elsewhere; none passes on design.
For the record, the two least bad (EURUSD FW3s, USDJPY FW3) are run once on the test window below, frozen as written.

### FX test (out_test_fx.txt; window SEEN): EURUSD FW3s 24 trades, win 12%, -0.480 R, -96.5 pips (coin -0.093);
USDJPY FW3 28 trades, win 21%, +0.009 R, +6.6 pips (coin +0.039). FX: no.

### V1's test losers, read on their charts after the test (charts/V1test; not used to change V1)

7 stops, all kind 1, on 3 days: 2026-05-07 three times at the same 72-h high / round 4750 after a +200 USD vertical H1
run (Asia, London, New York - the level refused each time); 2026-08-12 twice, 30 min after the CPI spike in a fast
tape (ATR 2.5x) under the previous H1 top; 2026-08-14 a sell at the end of a 30 USD waterfall into the 72-h low.

## Verdict and next idea

V1 / V2 are the first versions whose design half-years are mostly positive and whose (already seen) test is
positive, but they trade 0.1 a day and rest on 63-100 design and 15-18 test trades; the two key filters (room to
the 72-h extreme, fast tape) were chosen by counting the design trades, so the clean judge is the data after
2026-10-14. Next (design first): one attempt per 72-h extreme per day (a refused extreme is not retried), skip when
the H1 close is stretched (> ~4.5 H1 ATR over the EMA50) into the extreme, and widen the setup beyond the confluence
entry (E1: the 72-h-extreme approach with the H1 filters + M5 with + at a level, without the PA / 2-of-3 conditions)
to raise the count toward the owner's 3 a day.

### E1 probe (design only, not tested; out_E1.txt): 381 trades (0.64/day), win 34%, +0.096 R, 4/5 halves (+0.085,
-0.033, +0.083, +0.138, +0.225), coin -0.054; worst -11.44, streak 10, max DD 56.3 USD (over a 50 USD account).
