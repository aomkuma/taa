# Agent "fx" - notes (2026-10-17)

Angle: each major's own price and sessions at H1 scale (analysis on H1 at most), holds of 1-8 hours, targets
15-50 pips. Not the cross agent's London "equities -> dollar" lead (theirs). Design only on 2023-11-01 .. 2026-03-01
(five halves 23H2, 24H1, 24H2, 25H1, 25H2 [4 months]); one test per frozen rule on 2026-03-01 .. 2026-10-14.

Files: `fxlib.py` (pairs, costs, the simulator with target/stop/break-even/trailing, forced exit 20:50 UTC),
`foundations.py` -> `out_foundations.txt`, `lab.py` (session events + context known at the decision),
`grid1.py` (families x exits x filters on design data).

Costs (the auditor's FX costs): ask = bid + spread column (the minute's minimum) + 0.25 pip; 0.2 pip slippage on
entries, stops and time exits; a limit target none. No entries 20:00-23:00 UTC; every position closed by 20:50 UTC
(the 21-22 UTC rollover spreads are 2-5 pips). R = pips / (stop + 0.2). USD at 0.01 lot = pips x 0.10 (xxxUSD),
x 0.10/price (USDCHF, USDCAD), x 10/price (USDJPY).

Disclosure: in the first smoke test of the simulator (EURUSD, London 08-10 continuation, stop 1.5 x H1 ATR, time
exit 16:00 London) the printout included the test-window mean, +0.03 R/trade. It was not used for any choice; every
later script filters the test window out until a rule is frozen below.

## Step 1 - foundations (design halves; `out_foundations.txt`)

A. H1 returns (standardised by hour-of-day sd, within 00-20 UTC):
- EURUSD, GBPUSD, USDCAD: slight mean reversion: lag-1 autocorrelation negative in 5/5 (EUR -0.4..-4.1 %,
  GBP -1.2..-2.8 %) and 4/5 (CAD); VR(4) < 1 in 4-5/5 (0.90-1.01). Tiny.
- USDJPY: the only pair that trends at 1-8 h: VR(2) > 1 in 4/5 (1.02-1.07), ac1 positive in 4/5; VR(8) up to 1.22.
- AUD, NZD, CHF: no stable sign (25H2 strongly mean-reverting for AUD/NZD: VR(8) 0.73-0.78).
B. Hour drift: 1-2 pips an hour at most. Kept (4-5/5 and |t| > 2): USDJPY 07 UTC +2.3 pips (5/5; the yen weakens as
   Europe opens). AUDUSD 01 UTC +1.0 (4/5). Hour 20 UTC: AUD, NZD -0.9, USDCHF -1.1 (bid falling into the rollover
   spread = an artefact, outside our hours anyway). EURUSD 14 UTC +1.2 (5/5, t 1.9) then 15 UTC -0.8 (5/5, t -1.5).
   The USD composite has no hour that holds 5/5 except 07 UTC (+, small).
C. Day of the week: nothing holds (GBPUSD Monday +10 pips 4/5, t 2.2: the only one; not used).
D. Session continuation (sign of the first window x the next window), sign kept in 5/5 halves:
- EURUSD London 08-10 -> 10-16 London: continuation +1.0..+3.5 pips (5/5).
- USDJPY 14-16 -> 16-19 London (through the fix): continuation +0.9..+3.6 (5/5; big first windows 5/5).
- USDJPY / GBPUSD Asia 00-07 UTC -> London 07-12 UTC, big Asia moves: continuation (5/5).
- USDCAD London 08-10 -> 10-16: reversal of big moves (-0.1..-6.9, 5/5); NZDUSD same, small.
- AUDUSD New York 08-09:30 -> 09:30-12 ET: reversal of big moves (5/5); NZDUSD 4/5.
- Gotobi (USDJPY, Tokyo fix 09:55 JST): after the fix 09:55-12:00 JST on gotobi days -7.4 pips mean (4/5) vs +1.4
  other days. Month-end London fix: USDCAD 15-16 London USD down (5/5, n = 53 days), afterwards USD up (4-5/5 in EUR,
  GBP, AUD, CHF) - very small samples.
- All of these are 1-7 pips over 2-6 hours against a round trip of ~1.5-1.9 pips and an hourly sd of ~8-15 pips.
  Alone they are thin; they set the side to test in step 2.

## Step 2 - session families, every pair, design (`grid1.py`, `ana1.py`, `out_ana1.txt`)

Seven families (London 08-10 -> 16, Asia 00-07 -> 12 UTC, into the fix 14-16 -> 19 London, New York 08-09:30 ->
12 ET, Tokyo 09-10 -> 13 JST, the day 00-12 -> 16 UTC, London 07-08 -> 12), continuation and fade, stops 1/1.5/2 x
H1 ATR(24), time exit / 1.5R / 2.5R targets, |move| filters 0-1.5 ATR, with/against the H1 trend: 10,584 cells.
- Gross R is 0.00-0.07 a trade for every family pooled over the pairs; costs are 0.08-0.16 R a trade at 1-2 ATR
  stops (a round trip of 1.5-1.9 pips vs an H1 ATR of 7-20 pips). Net: every family pooled is negative
  (-0.04 .. -0.17 R). No cell is positive in 5/5 halves with R >= 0.10. => time-of-day continuation/fade alone is
  far too thin; the strongest pooled gross edge is the New York fade (+0.04-0.07 R).

## Step 3 - the New York reversal: it lives on US release days (`nyfade.py`, `relfade.py`, `reltrades.py`)

- Fading the 08:00 -> 10:00 ET move: on 08:30 release days (CPI, NFP, PPI, PCE, GDP from `gold.releases()`, 112
  days) the price comes back +0.25 ATR by 14 ET pooled over 7 pairs (4/5 halves; 25H1 ~0); on the other 490 days
  -0.00 (nothing). Cause: the release overshoots, liquidity providers fade it once the burst ends. USDJPY's path is
  the weakest (it continues on non-release days - the trending pair of step 1).
- Trades (design, all 7 pairs, net with the auditor's costs):

| step | change | n | win % | gross R | net R | net R by half 23H2/24H1/24H2/25H1/25H2 |
|---|---|---|---|---|---|---|
| V0 | every day, fade 08-10 ET move at 10:00, stop 2 ATR, exit 14 ET | 4205 | 46 | +0.024 | -0.047 | -0.00/-0.02/-0.11/-0.04/-0.07 |
| V1 | release days only | 784 | 50 | +0.110 | +0.042 | +0.09/+0.06/+0.03/+0.00/+0.03 |
| V2 | + the move >= 1 ATR | 477 | 53 | +0.169 | +0.098 | +0.11/+0.12/+0.07/+0.01/+0.30 |
| V3 | + stop beyond the 08-10 extreme + 0.5 ATR (>= 1 ATR) | 477 | 48 | +0.291 | +0.144 | +0.25/-0.06/+0.12/+0.09/+0.52 |
| V4 | V3 + target 50 % retrace | 477 | 57 | +0.165 | +0.059 | (worse: cuts the winners) |
| V5 | V3, exit 16 ET | 476 | 45 | +0.284 | +0.130 | (no better) |
| V6 | V3 with a 3 ATR stop | 477 | 54 | +0.112 | +0.067 | (worse) |

## Step 4 - why V3's losers lose (`rel_losers.py`, `out_rel_losers.txt`, design)

V3: 477 trades, net +0.144 R, coin side on the same events and stops -0.018 R, the opposite side -0.261 R. Win 48 %
vs the coin 39 %. Losers 249 = 192 stopped + 57 time exits below zero. Stopped kinds 86/10/4 (coin 90/7/2): wrong
way dominates, as for the coin. Median time to the stop 38 minutes. Concrete groups:
1. **Fading a move that has not stalled** - the 10:00 close within 10 % of the range from the extreme: 160 trades,
   -0.095 R, 59 % stopped, negative in 4/5 halves (the rest: +0.16..+0.36 R). Same picture from the last 30
   minutes: still running > 0.5 ATR into 10:00 -> 212 trades, -0.059 R, 57 % stopped. The largest reason.
2. Very large moves (> 5 ATR, 59 trades, -0.31 R): a real repricing; but only 3 halves have any - not acted on.
3. CPI days -0.19 R (135 trades) vs NFP +0.26, PPI +0.15, PCE +0.23, GDP +0.76: by event type - small samples per
   type, not acted on (would be fitting).
4. Tuesday -0.09 R (72): not acted on (no cause).
5. Worst day -16.4 USD at 0.01 lot: up to 7 pairs fade the same USD move on one day (4.4 trades a release day).
Changes to test (written before the run, `rel2.py`): V7 skip no-stall, V8 wait up to 11:00 ET for a 15 % pullback
from the running extreme, V8b without USDJPY (step 1 reason), V8c at most 3 pairs a day (the largest moves).

## Step 5 - results of the loser-driven changes (`rel2.py`, `out_rel2.txt`, design)

| step | change | n | win % (coin) | gross R | net R | coin R | net by half | USD 0.01 | worst day / maxDD USD |
|---|---|---|---|---|---|---|---|---|---|
| V3 | (from step 3) | 477 | 48 (39) | +0.291 | +0.144 | -0.018 | +0.25/-0.06/+0.12/+0.09/+0.52 | +114.6 | -16.4 / - |
| V7 | V3, skip if no stall (10:00 close within 10 % of the range from the extreme) | 317 | 56 (38) | +0.390 | +0.265 | -0.116 | +0.53/-0.03/+0.18/+0.23/+0.36 | +148.1 | -16.4 / 27.1 |
| V8 | V3, wait to 11:00 for a 15 % pullback | 453 | 52 (40) | +0.301 | +0.180 | -0.100 | +0.40/-0.02/+0.11/+0.04/+0.47 | +123.3 | -16.4 / 40.1 |
| V8b | V8 without USDJPY | 395 | 51 (37) | +0.329 | +0.198 | -0.138 | | +120.0 | -13.3 / 44.0 |
| V8c | V8b, max 3 pairs a day (largest move) | 261 | 50 (38) | +0.251 | +0.116 | -0.177 | | +30.1 | -7.9 / 42.3 |

- Skipping the no-stall fades (V7) is the change that works: +0.12 R a trade over V3 and the drawdown falls. Waiting
  for a pullback (V8) is weaker than simply skipping: the moves that stall only after 10:00 are the repricings.
- Capping by the largest move (V8c) picks exactly the repricing days: worse. A cap must not use the move's size.
- The account: 7 pairs fading one USD move on the same day = one bet in 7 pieces (worst day -16.4 USD); the cap
  by cost order (cheapest spreads first) is tested next (V7c), USDJPY dropped for the step-1 reason (V7b).

V7b / V7c / V7d (`rel2.py --v7`, `out_rel2_v7.txt`): without USDJPY +0.283 R (279 trades, 4/5 halves), max 3 pairs
a day cheapest-first +0.223 (210, worst day -7.0 USD, but maxDD 31 USD Aug 2024 - Jan 2025, and one GBPUSD stop of
55 pips = 5.5 USD > the account's limit), max 2 a day +0.153.

## Step 6 - sensitivity (`sens.py`, `out_sens.txt`, V7b, one parameter at a time, design)

stall 5/10/15/20/30 %: +0.22/+0.28/+0.27/+0.29/+0.08; exit 13/14/15/16 ET: +0.29/+0.28/+0.23/+0.26; stop extra
0.25/0.5/1.0 ATR: +0.30/+0.28/+0.24 (1.0: 5/5 halves); move >= 0.5/1/1.5 ATR: +0.21/+0.28/+0.31. **The decision time
is the knife edge**: 09:45 +0.12, 10:00 +0.28, 10:15 +0.13, 10:30 +0.05 ET (all positive; 10:00 is the peak, and the
10:00 ET US releases fall there). Expect the test below the design figure.

## Step 7 - charts of real trades (`charts.py`, `charts/rel_V7b_losers.png`, `charts/rel_V7b_winners.png`)

Winners: one burst at 08:30 (a spike of 20-40 pips in minutes), the price already sitting in a range by 10:00, then
back toward the pre-release level by 11:00-14:00. Losers: (a) a staircase trend - the move began before the release
or kept grinding from 08:30 to 10:00 (USDCAD 2024-09-06 NFP, EURUSD 2024-01-25 GDP, GBPUSD 2024-12-20 rising since
07:00, USDCHF 2025-03-28); the 10:00 pause was a flag, not a top; (b) stops of 6-10 pips (AUD/NZD/CHF) inside the
normal 10:00-14:00 noise (AUDUSD 2025-08-29, NZDUSD 2025-07-16 stopped, then the full reversal: right idea, stop
too tight).
Measured (design, V7b trades by the share of the 08-10 move made before the release, 08:00 -> 08:30):
<= 0: 118 trades +0.52 R (5/5 halves); 0-0.25: 98, +0.20; 0.25-0.5: 40, +0.03; > 0.5: 23, -0.14. => the reversal
belongs to the release's own overshoot; a move already flowing before the release is a trend and continues.

| step | change | n | win % | net R | halves + | net by half | USD | worst / worst day | streak | maxDD | 6 avg losses |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V7b | V7 without USDJPY | 279 | 55 | +0.283 | 4/5 | +0.59/-0.07/+0.19/+0.23/+0.49 | +134.5 | -3.96 / -13.3 | 11 | 34.5 | 8.2 |
| V9 | + pre-release share of the move <= 25 % | 216 | 57 | +0.376 | 5/5 | +0.63/+0.04/+0.21/+0.33/+0.93 | +128.6 | -3.96 / -13.3 | 10 | 22.7 | 8.2 |
| V10 | + stop extra 1.0 ATR (the tight-stop losers) | 216 | 61 | +0.308 | 5/5 | +0.46/+0.12/+0.20/+0.27/+0.66 | +139.4 | -4.58 / -15.2 | 10 | 22.1 | 9.0 |
| V11 | + skip stops worth > 4 USD at 0.01 lot | 191 | 62 | +0.323 | 5/5 | +0.48/+0.11/+0.20/+0.28/+0.74 | +119.6 | -3.25 / -15.2 | 7 | 17.3 | 8.8 |
| RF | + at most 3 pairs a day, cheapest spread first | 162 | 60 | +0.258 | 5/5 | +0.36/+0.01/+0.15/+0.42/+0.51 | +83.0 | -3.25 / -7.6 | 10 | 17.7 | 8.9 |

RF design: coin side on the same events and stops -0.033 R, win 49 % (ours 60 %: +11 points). Stopped losers'
kinds (no target: the reference is 1R) ours 74/24/3 vs coin 85/12/4: fewer wrong-way, more "went +0.5R, came back"
(the exit is the next lever - not touched before the test). ~5.8 trades a month (release days only).

## FROZEN RULE "RF" (2026-10-17, before any test-window run of it; code `cand.py`, `rule(..., pre_max=0.25,
extra=1.0, usd_cap=4.0, cap=3)`)

- Days: US 08:30 ET release days (CPI, NFP, PPI, PCE, GDP; `gold.releases()`, known in advance).
- Pairs: EURUSD, GBPUSD, AUDUSD, USDCHF, USDCAD, NZDUSD (not USDJPY).
- Move = bid close of the M1 bar ending 10:00 ET - open of the 08:00 ET bar; range = high/low of 08:00-10:00 ET.
- Trade only if |move| >= 1 x H1 ATR(24, completed hours); the 10:00 close is > 10 % of the range back from the
  move's extreme; the pre-release drift (close 08:30 - open 08:00) is <= 25 % of the move (same sign share).
- Side: against the move, decided at the 10:00 ET close, market fill at the next bar's open.
- Stop: the move's 08-10 extreme + 1.0 x ATR beyond it (distance from the decision close, at least 1 ATR); skip
  if the stop is worth > 4 USD at 0.01 lot. No target, no break-even. Time exit at the close of the bar ending
  14:00 ET.
- At most 3 pairs a day, in the order EURUSD, GBPUSD, AUDUSD, USDCHF, USDCAD, NZDUSD. One position per pair.
- Costs: spread column + 0.25 pip on the ask, 0.2 pip slippage on entry, stop and time exit.
Test once on 2026-03-01 .. 2026-10-14 (`cand.py --test`).

## THE TEST of RF (run once, 2026-10-17; `cand.py --test`, `out_rf_test.txt`, `rf_test.parquet`)

| month | trades | days | win % | pips | USD 0.01 | R/trade | coin R |
|---|---|---|---|---|---|---|---|
| 2026-03 | 2 | 2 | 50 | -44.1 | -3.22 | -0.483 | -0.483 |
| 2026-04 | 5 | 3 | 60 | -7.7 | -0.10 | +0.056 | +0.313 |
| 2026-05 | 4 | 2 | 100 | +12.1 | +1.23 | +0.217 | +0.088 |
| 2026-06 | 3 | 1 | 0 | -61.8 | -6.60 | -1.000 | -0.024 |
| 2026-07 | 9 | 3 | 67 | +42.9 | +4.76 | +0.069 | -0.270 |
| 2026-08 | 6 | 3 | 17 | -12.6 | -1.26 | -0.183 | -0.268 |
| 2026-09 | 4 | 2 | 100 | +27.6 | +2.35 | +0.275 | -0.212 |
| 2026-10 (to 10-14) | 0 | 0 | - | - | - | - | - |
| **total** | **33** | **16** | **58** | **-43.7** | **-2.84** | **-0.067** (gross -0.009) | -0.121 (win 48 %) |

Per pair: EURUSD 11 trades +0.105 R (+2.93 USD), USDCHF 5 +0.370 (+5.12), USDCAD 5 -0.001 (-1.36), AUDUSD 5
-0.330 (-2.27), GBPUSD 5 -0.575 (-7.23), NZDUSD 2 -0.337. 0.20 trades a weekday (release days only). Exits: 24 time,
9 stops; stopped kinds ours 100/0/0 (coin 88/12/0). Account: worst trade -3.28 USD, worst day -6.60, longest losing
streak 6, max drawdown 8.7 USD, 6 average losses 9.9 USD (fits 50 and 100 USD).
Hand check: EURUSD 2026-07-14 SELL recomputed from raw bars (move 44.9 pips, pre-share 0.16, back 0.18, stop 22.2,
+26.65 pips) - identical.

**Verdict: RF fails its test** (-0.067 R a trade, -2.84 USD; 3 of 7 months positive). The design's gross +0.35 R
became gross -0.01 R. It still picked the side better than the coin (win 58 % vs 48 %, +0.05 R), but wins were small
time exits and the losses full stops.

Why the 9 stopped losers lost (charts `charts/rf_test_losers.png`):
1. **A fresh USD move started exactly at the 10:00 ET entry** - 2026-06-25 (PCE day): EURUSD, GBPUSD, USDCHF all
   stopped within 5-6 minutes (-6.60 USD, the month's whole loss); 2026-03-13 (PCE, and JOLTS at 10:00 ET that day):
   USDCAD rallied from 10:00 to the 44.9-pip stop. 4 of 9 stops. The 10:00 ET slot is itself a release slot (JOLTS,
   ISM, sentiment...) and our calendar has no 10:00 events except JOLTS.
2. **A grinding trend day, not a spike** - 2026-07-15 (PPI): EURUSD, GBPUSD, AUDUSD rose steadily from 08:30 to
   14:00 with no burst; the pre-release filter passes these (no drift before 08:30) but the move was a flow. 3 stops.
3. **Tight stops on AUD/NZD** - 2026-08-26 (PCE): 10-pip stops; both stopped in the continuing down-grind, then the
   price came back to the entry by 13:00. 2 stops.
Winners: small time exits (+2..+29 pips) on days with a spike at 08:30 and a range by 10:00 (07-02, 07-14, 09-04).

After the test (a NEW rule, designed after seeing the test; design data only, not tested): RF2 = confirm the stall
through 10:15 (skip if 10:00-10:15 makes a new extreme, else enter 10:15): design +0.234 R (4/5 halves) vs RF +0.258
- no improvement on design, not adopted. RF trades on JOLTS days in design: none (the 03-13 overlap is a
shutdown-shifted schedule).
