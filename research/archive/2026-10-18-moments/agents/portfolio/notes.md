# Portfolio agent - notes (2026-10-17)

Job (lead, 2026-10-17): an arsenal of protected gold setups, each with its own entry confirmation, sharing one
protective layer, and a portfolio of them (one position at a time), plus the news straddle S2 on the majors as a
separate calendar slot. Design 2023-11-01 .. 2026-02-28 (five half-years as the journal's), one test per frozen rule
on 2026-03-01 .. 10-14, marked SEEN where the family was already run on that window and NEW where it was not.

## Files

- `plib.py` - data (the journal's wide candidate tables `cand_XAUUSD_wdesign/wtest`, rules.augment), the family
  triggers, a trade loop (jlib's with a per-row exit and an optional trailing stop), the step and account tables.
- `design.py` - per family: baseline -> each protective condition on the family's own trades -> kept layer.
- `portfolio.py` - the portfolio on design (and, after the freeze, the test) + S2 on the majors.
- `out_*.txt` - outputs.

## Conventions (all families; written before any run)

- Gold only for the families (the journal's FX versions of the confluence logic failed on design and test; the
  auditor: M1 FX scalps are not viable at FBS costs). FX enters only through S2 (the news agent's `fx_results`).
- Windows = the journal's wide windows (Asia 00:00-02:00 UTC, London 07:00-12:00 UTC, New York 12:00-17:00 UTC;
  nothing 20-23 UTC). A trigger outside them is not traded (and has no candidate-table row for its features).
- Decide at the M1 bar's close, enter at the next open; real costs (the auditor's: spread column + 0.08, 0.07 entry
  slippage, stop fills 0.15 / New York 0.20) through `jlib.Instr`. U = price / 4100 USD.
- Default exit (every family unless written otherwise): target 8 U, the family's structural stop, break-even at 0.6 of
  the target, 60 minutes. Stop rules for the new triggers: a structural stop closer than 3 U is widened to 3 U; one
  farther than 10 U skips the trade (the account). F1 keeps B0's own rule (outside 3-10 U = no trade).
- One position at a time inside a family, at most 2 trades per session-day (jlib.run).

## The families (triggers and their own confirmation; written before running)

- **F1 CONF** - the journal's B0: H1 tide + at a level + price action + 2 of 3 M5 indicators; stop level - 1 ATR.
- **F2 NYB** - the trend agent's New York range breakout, its step 2: range = the M1 bars opening 08:30-09:29 ET;
  the first M1 close beyond it on a bar opening 09:30-09:59 ET (the first side decides; no second chance); the H1
  trend agrees (the tide). Exit (a) the trend agent's: stop at the range's far side, a 1 R trail from +1 R, 180 min
  (skip when the stop > 10 U); exit (b) default with the stop = the broken edge - 1 ATR. The exit is chosen on the
  design baseline (higher R) before the protective layer.
- **F3 OPEN** - moments P1 break-and-hold at the opens (00:00 UTC, 01:00 UTC, 08:00 London, 08:30 ET, 09:30 ET):
  the pools = the nearest level above / below the close at the open (the candidate table's six kinds: today's
  extreme as of 15 min before, yesterday's, the Asian range, round 50, M15 / H1 chart-read levels); within 30
  minutes the first M1 close beyond one, the next bar's close still beyond -> enter at the bar after; stop = the pool
  - 1 ATR. One trade per open (the first break).
- **F4 SWEEP** - moments P2 sweep-and-reclaim at the same opens: within 30 minutes the first bar whose extreme
  crosses a pool; a close back inside within 5 bars -> trade back the other way at the next open; stop = the sweep's
  extreme + 0.5 ATR.
- **F5 FADE** - S1-style: the H1 and the M15 tide agree (EMA stand-in for S1's market-map states), the decision bar
  is the first M1 close beyond the previous 20 bars' extreme *against* them -> trade with the trend; stop = the
  last 3 bars' extreme + 0.5 ATR. S1's own filter kept: no entries 08:00-12:00 ET.
- **F6 SQZ** (new; the journal's winners: "compression on the level, then a break") - H1 tide, M5 with the trade
  (M5 close beyond its EMA20, the EMA not turning against), the previous 15 bars' high-low <= 3 M1 ATR, the decision
  bar is the first close beyond that box's far side, M5 RSI on the trade's side of 50; stop = the box's other side
  - 0.5 ATR.

## The protective layer (the team's conditions; a menu, the same for every family)

C1 H1 ZigZag leg not against (`cr_H1_leg_dir >= 0`); C2 H1 not flat (`|h1_c_e50| >= 0.85`); C3 `pos240 >= 0.5`;
C4 the 72-h extreme in front closer than 0.5 target or behind (`(front72 - close) x side < 4 U`); C5 not a fast
tape (`atr_ratio < 2`); C6 not late (Asia from 01:40 UTC, New York from 10:15 ET); C7 no US release within 15 min;
C8 the H1 tide with the trade (only for the families without it: OPEN, SWEEP).

**Selection rule (declared before any family is run):** on the family's baseline trades (design), for each
condition: the R of the trades that pass vs those that fail, overall and per half-year, and the share of stopped
losers vs winners that fail it. A condition is **kept** for that family when R(pass) - R(fail) >= 0.10 overall
and R(pass) > R(fail) in at least 4 of the half-years where both sides have >= 5 trades (all of them if fewer than
5 such halves, at least 2). Kept conditions are applied together, in the menu order (step table, the loop re-run
each step). A family enters the portfolio when its protected design result is >= +0.10 R, >= 3/5 half-years
positive and >= 30 trades; otherwise it is reported with its losers' causes and left out.

**Change after F1's first design run (said plainly):** on B0's 1,510 losing baseline trades only C4 met the rule
(C1 / C2 were better in 4 of 5 halves but by 0.05-0.08 R): in an all-losing baseline the conditions separate weakly
one at a time and more in combination (the team's V2). The rule becomes a **forward selection** with the same
criterion: at each step evaluate the conditions not yet taken on the *current* step's trades, add the one that meets
the criterion with the largest R(pass) - R(fail), re-run the loop, repeat until none meets it or fewer than 30
trades would remain. Applied the same way to every family (design data only; the test is untouched).

**Portfolio (declared):** P-A one gold position at a time across the admitted families; when two signal on the
same minute the higher design R wins; each family's own 2-a-session cap. P-B as P-A with one trade per session
(the first). S2 on one major (EURUSD; the seven pairs are one USD bet) as a separate calendar slot at 0.01 lot.

## Design results (out_design.txt, out_portfolio_design.txt) - 2023-11 .. 2026-02, real costs, 0.01 lot

Families' step tables (one position inside a family, 2 a session-day; R = P&L / (stop + stop slippage)):

| family | step | trades (a day) | win % | R/trade | USD | halves + | worst / streak / max DD USD (DD at gold 4100) |
|---|---|---|---|---|---|---|---|
| F1 CONF | baseline B0 (wide windows) | 1510 (2.48) | 23 | -0.150 | -728.6 | 0/5 | -12.8 / 19 / 736.7 |
| | + C4 72-h extreme near/behind | 201 (0.33) | 30 | +0.010 | +27.3 | 3/5 | -11.4 / 11 / 35.9 (58.2) |
| | + C5 not a fast tape | **140 (0.23)** | 32 | **+0.118** | +58.4 | **4/5** | -10.0 / 7 / 30.4 (30.5) |
| F2 NYB (b exit) | baseline: NY range break 09:30-09:59 ET + H1 tide | 216 (0.36) | 27 | -0.057 | +8.1 | 2/5 | -8.6 / 15 / 74.2 |
| | + C1 H1 leg not against | 133 (0.22) | 31 | +0.014 | +59.6 | 2/5 | -6.9 / 10 / 37.3 (60.4) |
| F2a NYB (trend agent's exit) | far-side stop <= 10 U only | 16 (0.03) | - | +0.463 | +48.3 | 4/5 | the stop fits the account on 16 of ~216 days: unusable |
| F3 OPEN (P1 break-and-hold) | baseline | 1276 (2.10) | 23 | -0.112 | -227.1 | 2/5 | -11.7 / 21 / 348.7 |
| | + C4 | **176 (0.29)** | 32 | **+0.127** | +87.8 | 3/5 | -7.9 / 10 / 47.4 (55.3) |
| F4 SWEEP (P2) | baseline (no condition met the rule) | 1441 (2.37) | 18 | -0.202 | -712.9 | 0/5 | - |
| F5 FADE (S1-style) | baseline | 2290 (3.77) | 14 | -0.236 | -1236.4 | 0/5 | - |
| | + C4 | 105 (0.17) | 10 | -0.261 | -64.3 | 0/5 | |
| F6 SQZ (new) | baseline (no condition met the rule) | 1601 (2.63) | 22 | -0.153 | -761.2 | 0/5 | - |
| F7 PULL (new) | baseline | 3000 (4.93) | 21 | -0.111 | -942.1 | 0/5 | - |
| | + C4 | 368 (0.61) | 27 | +0.035 | +33.2 | 3/5 | -11.2 / 10 / 72.2 (125.0) |

The protective layer, counted family by family: **C4 (the 72-hour extreme in front closer than half the target, or
already behind) is the one condition that separates in every family that trades toward an extreme** (F1, F3, F7
5/5 or 4/5 halves; F2 4/5 but below 0.10 R) - its failing trades are 81-99 % of each baseline. After C4, C2 / C3 /
C9 are nearly always true (near the 72-h high the H1 is not flat and price is high in its 4-h range), so they add
nothing. C5 (fast tape) separates only in F1 after C4 (5/5). C1 separates in F2 (and 3/4-3/5 after C4 elsewhere,
below the rule). C6 / C7 never met the rule (C6 was *better* failing in F1 after C4: late trades +0.16 R).

Bull drift check (design): F1 final - ours +0.118, sides permuted (long share 77 % kept) +0.032, always long
+0.015; F3 final - ours +0.127, permuted -0.007, always long +0.086 (F3's shorts lose: 40 trades -0.09 R; longs
+0.19). F1's side choice is worth about 0.09-0.10 R over its drift; F3's about 0.04 over always-long.

Why the failing families lose (their own trades, design):
- F4 SWEEP: the sweep is faded *against* the structure - median H1 leg against (-1), H1 close below its EMA50
  (-0.3 .. -0.6 ATR), pos240 0.22-0.32, the 72-h extreme 6-7 targets away; its wrong-way losers (556 of 1117 stops)
  were more often Asia (47 % vs winners 31 %) with wider stops (2.5 vs 2.0 ATR) in a quieter tape (ATR ratio 1.24 vs
  1.51). No protective condition separates: it is the dip-bought-in-weak-structure loser by construction.
- F5 FADE: buying the first close under a fresh 20-minute low (selling the high) inside an H1 + M15 uptrend: the
  break continues - 71 % of stops wrong way (the coin 71 %), win 14 % for a 2.7:1 target; after C4 the London ones
  (71 trades, -0.55 R) come late in the session (median +179 min); only Asia's first minutes win (25, +0.65 R).
- F6 SQZ: compression-then-break with the trend: 76 % of stops wrong way (coin 76 %) - the break of a tight
  15-minute box falls back into it; winners and losers look the same on every measure (stop 3.8-4.0 ATR, 15/60-min
  push, ATR ratio, room to the 72-h extreme, session). The box break is not the confirmation the charts suggested.
- F2 NYB: break-even after C1; its kind-1 losers came in a faster tape (ATR ratio 2.04 vs 1.81) and with less room
  to the 72-h extreme ... (C5 +0.187 vs -0.185 R after C1 but 2 of 4 halves); kind 3 (46 %) = stops 1.7 ATR inside
  the New York open's noise.
- F7 PULL: break-even after C4: New York -0.070 R (157), Asia +0.341 (65) - the journal's E5 showed this Asia carry
  failing on the test, so it is not taken as a rule.

Portfolio (design): P-A (F3 then F1, one position) 296 trades 0.49 a day, +0.093 R, +120.7 USD, 4/5 halves, worst
-10.0, streak 10, max DD 50.4 USD (56.2 at 4100); F1 inside P-A only +0.039 (F3's trades block some of F1's).
P-B (one a session) 241, +0.092 R, max DD 48.4. P-C (+F2, F7) 644 trades 1.06 a day, +0.037 R, max DD 70.8 (121.6 at
4100), 3/5 halves - the count costs the edge. S2 EURUSD (design B): 54 trades, +1.55 R, +78.5 USD, worst -0.94, max
DD 2.8. P-A + S2: 0.58 a day, +199.3 USD, max DD 32.3 USD, 23 of 28 months positive.

## FROZEN for the one test (written 2026-10-17 before any test number of these rules was computed)

- **F3 OPEN-72** = at the opens 00:00 UTC, 01:00 UTC, 08:00 London, 08:30 ET, 09:30 ET: the nearest level above /
  below the close (today's extreme as of 15 min before, yesterday's, the Asian range, round 50, M15 / H1 chart-read
  levels); within 30 minutes the first M1 close beyond one, the next close still beyond -> enter at the next open
  that way; taken only when the 72-h extreme in front (highest high / lowest low of the 4,320 M1 bars ending 15
  minutes before the decision bar) is closer than 4 U or already behind. Stop the level - 1 M1 ATR (at least 3 U,
  skip above 10 U), target 8 U, break-even at 0.6, 60 minutes.
- **F1 CONF-72** = B0 (H1 tide + at a level + price action + 2 of 3 M5 indicators; stop level - 1 ATR within 3-10 U)
  + the same 72-h condition + not a fast tape (M1 ATR < 2x its day median). B0's exits.
- **P-A** = F3 first, then F1, one gold position at a time, each 2 a session-day; **P-B** = P-A with one trade a
  session. Declared extras (not the verdict): P-C with F2 NYB + C1 and F7 PULL + C4. S2 EURUSD as its own slot (the
  news agent's frozen rule; its test is SEEN).
- What is SEEN on 2026-03-01 .. 10-14: F1's family (B0 / W2 / W3 / V1 / V2 all run on it; this combination is
  new), F3's playbook (moments P1, run on 2026-04-14 .. 10-14 in rounds 1-2; the 72-h filter on it is new), F2 (the
  trend agent's T1 test), S2 (the news agent). **NEW**: F7 PULL (never run on the window).

## The one test, 2026-03-01 .. 10-14 (out_portfolio_test.txt; run once after the freeze above)

| rule | seen? | trades (a day) | win % | R/trade | USD 0.01 lot | months + | worst / streak / max DD USD | coin R / permuted / always long | kinds ours / coin |
|---|---|---|---|---|---|---|---|---|---|
| **F1 CONF-72** | family SEEN, combination new | 34 (0.21) | 44 | **+0.183** | **+52.9** | **6/7** | -8.2 / 4 / 26.7 | +0.088 / +0.026 / -0.018 | 87/0/13 / 60/0/40 |
| F3 OPEN-72 | playbook SEEN, filter new | 18 (0.11) | 28 | -0.281 | -36.0 | 2/7 | -10.4 / 4 / 42.8 | -0.076 / -0.335 / -0.552 | 27/18/55 / 36/13/51 |
| F2 NYB + C1 (extra) | SEEN | 40 (0.25) | 20 | -0.349 | -82.6 | 2/8 | -7.9 / 8 / 106.1 | -0.033 / -0.121 / -0.425 | 36/0/64 / 41/1/57 |
| F7 PULL + C4 (extra) | **NEW** | 34 (0.21) | 35 | +0.049 | +15.6 | 2/7 | -10.5 / 9 / 28.0 | -0.086 / -0.020 / -0.120 | 55/0/45 / 48/3/49 |
| S2 EURUSD | SEEN | 15 (0.09) | - | +0.85 | +11.9 | 7/8 | -0.94 / - / 1.1 | | |
| **P-A** (F3, F1) | mixed | 51 (0.31) | 39 | +0.023 | +17.2 | 4/8 | -10.4 / 6 / 42.5 | | |
| P-B (one a session) | mixed | 42 (0.26) | 38 | +0.012 | +12.0 | 3/8 | -10.4 / 4 / 32.3 | | |
| P-C (+F2, F7) | mixed | 112 (0.69) | 29 | -0.142 | -80.2 | 2/8 | -10.5 / 9 / 122.7 | | |
| P-A + S2 | | 66 (0.41) | | | +29.1 | 4/8 | max DD 42.7; a 50 USD account's lowest 37.0 | | |

Month by month P-A gold / S2 / total: 03 +29.5 / +0.1 / +29.7; 04 -25.8 / +0.9 / -24.9; 05 -10.3 / -1.1 / -11.4;
06 +8.2 / +1.3 / +9.5; 07 +25.9 / +2.6 / +28.5; 08 -16.2 / +2.4 / -13.8; 09 +10.7 / +4.9 / +15.7; 10 -4.9 / +0.7 / -4.1.

Why F3 OPEN-72 lost on the test (its 18 trades, read one by one): 11 stops, 6 of them kind 3 (the target came later
from the entry). 16 of 18 entries were already *through* the 72-h extreme at the open (breakouts to new highs/lows),
and in 2026's faster minutes the same 8 U target and a 3-10 U stop sat at only ~1.5-2 M1 ATR (design 2.4-2.6):
the open's first snap-back took the stop before the move. Asia (00:00-01:07 UTC, the widest spread) 9 trades
-0.54 R carried most of the loss - the design's Asia strength (+0.25 R, 64 trades) did not repeat, as with the
journal's E5. 2026-05-07 (the same 72-h high / round 4750 refusal that stopped V1 three times) appears again.
Why F1 CONF-72 held, and what its losers were: 15 stops, 13 wrong way; 3 on 2026-05-07 (that same refused high,
Asia, London and New York); 3 after a 60-minute run of 10+ ATR into the extreme (07-28, 07-30, 08-14); the stopped
trades had tighter stops than the winners (median 1.6 vs 2.3 M1 ATR) - not a design difference (design 2.6 vs
2.5), so only a lead for fresh data. Its side choice beat the side-permuted coin by 0.16 R and always-long by 0.20.
F2 (NYB) failed again as in the trend agent's test (64 % kind 3: the New York open's noise inside a 1.7-ATR stop).
F7 (NEW) stayed at break-even (+0.035 design, +0.049 test), New York negative both times.

## Verdict

Surviving: **F1 CONF-72** only (design +0.118 R, 4/5 halves, 140 trades; test +0.183 R, 34 trades, 6/7 months, max
DD 27 USD - within a 50 USD account; the family was seen, this combination was not). S2 on EURUSD stays a tiny-risk
calendar slot (max DD ~1-3 USD at 0.01 lot). F3 failed its test; the portfolio P-A is break-even on the test
(+0.023 R) because of F3. Count: F1 about 0.2 a day, + S2 0.1 a day - far below the owner's ~3 a day. No family
other than the confluence entry has shown an edge once protected; the 72-h condition is what made the protected
families positive on design, partly through the 2024-26 bull drift (F3's design result was mostly long drift).

## What fresh data (2026-10-14 on) should judge

1. F1 CONF-72 exactly as frozen (with S2 EURUSD beside it): R a trade vs the side-permuted coin and always-long on
   the same minutes, the months, max DD vs a 50 USD account. Choosing "F1 alone + S2" over P-A is a choice made
   after seeing F3 fail on the test - a new rule, judged only on fresh data.
2. Whether F1's stopped trades keep the tighter stops (< ~2 M1 ATR) and the refused-extreme repeats (one 72-h
   extreme tried in three sessions on one day) - both seen only on the test, not design-backed.
3. F7 PULL + C4 (NEW, break-even both periods) only as a count candidate, New York excluded only if fresh data
   repeats its New York loss.
