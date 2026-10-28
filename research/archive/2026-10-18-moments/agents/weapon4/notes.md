# weapon4 - a fourth weapon (2026-10-18)

Goal (lead, 2026-10-18; updated the same day): F1 CONF-72 (~0.21 a day) + S2 (~0.1 a day) are the robust weapons
(S1 is unstable at the auditor's costs, so it is not counted). A fourth weapon should add **>= 0.6 trades a day** on
days / moments the others do not trade, at **>= +0.10 R a trade** (target +0.15) net of real costs, positive in most
half-years (design) and months (window).

Rules of the work: design and choose only on data before 2026-03-01 (half-years as `jlib.HALVES`: 2023-11..24-04,
24-05..24-10, 24-11..25-04, 25-05..25-08, 25-09..26-02); each rule written here before it is computed; then one run
per frozen rule on 2026-03-01 .. 2026-10-14. Real costs (BRIEF.md "Real costs").

## The building blocks (`w4lib.py`)

The F1 frame, re-implemented from M1 on any decision timeframe TF (M1 / M5 / M15), any hours, any market, so it can
run outside F1's windows (the journal's candidate tables only hold Asia 00-02, London 07-12, New York 12-17 UTC):

- decide at the close of a TF bar; enter at the next M1 bar's open; simulate on M1 bars (`plib.trade`, real costs);
- tide: the last closed H1 bar's EMA20 slope (3 bars) and close - EMA50 both with the side (as F1);
- levels (as `journal/build.py`): the broker day's low/high and the UTC day's Asia (00-07) low/high as of 15 minutes
  before the decision, yesterday's broker-day low/high, the round number (gold 50), the nearest M15 and H1
  chart-read level (`ChartReadFrame`, no repaint); the nearest level behind the trade is *the level*;
- at the level: within 3 TF-ATRs, the last 5 TF bars' extreme within 1 TF-ATR of it;
- price action: a hammer on the TF bar or on the last closed bar one TF up (M1 -> M5, M5 -> M15, M15 -> H1), an
  engulfing TF bar, or a sweep and reclaim of the level (3 TF bars);
- indicators one TF up (M1 -> M5, M5 -> M15, M15 -> H1): RSI rising and on the far side of 50, MACD histogram
  rising, Stochastic %K crossing %D - 2 of 3;
- stop: the level - 1 TF-ATR, at least 0.5 M15 ATR (the floor), else within [rmin, rmax] U;
- C4: the 72-hour extreme in the trade's way (M1 bars i-4320 .. i-16) closer than 4 U in front, or behind;
  C5: the TF-ATR < 2 x its one-day median;
- units: gold 1 U = price / 4100 USD (as F1); other markets 1 U = the trailing 28-day median M1 ATR / 1.63 (gold's
  design median M1 ATR in U, as `journal/rules.py` for FX);
- exits (F1 v1): target, break-even at 0.6 of the target, a time exit; one position at a time, at most 2 per
  session-day. Sessions for the cap: 0 = 00-07, 1 = 07-12, 2 = 12-20 UTC (New York stop slippage 0.20).

Check first (W0, not a candidate): the builder on gold M1 in F1's wide windows must reproduce F1's design trades.

## Candidates (written 2026-10-18 before any of them is computed)

**W1 - F1 at the hours it skips (gold M1).** F1 exactly as frozen (+ the 0.5 M15-ATR floor; 8 U target, BE 0.6, 60
minutes; stop 3-10 U before the floor), entries 02:00-07:00 and 17:00-20:00 UTC (F1's windows: 00-02, 07-17). Pass
on design: R >= +0.10 and positive in >= 4 of 5 halves (3 of 5 if a half has < 10 trades).

**W2 - F1 on M5 (the owner's adaptive timeframe).** The frame with TF = M5, 00:00-20:00 UTC weekdays: M5 ATR, PA on
M5 / M15, 2 of 3 on M15, levels as above, stop the level - 1 M5 ATR (floor 0.5 M15 ATR) within 4-16 U, C4 < 4 U,
C5 on the M5 ATR (one-day median = 288 bars). Exits: target T, BE 0.6 of T, time exit H. The grid, chosen on design
only: T in {8, 12, 16} U x H in {120, 180} minutes. Choice: pass (R >= +0.10, >= 4/5 halves), then the most trades,
then the higher R. Reported apart: the trades on minutes / days F1-M1 does not trade.

**W3 - the 72-hour logic on other markets.** (a) the M1 frame (W1's rule, all of 00-20 UTC for XAUAUD; the US cash
hours 13:30-20:00 UTC for US100 / US30 / US500; JP225 00:00-06:00 + 13:30-20:00 UTC) and (b) the M5 frame (W2 with
T = 12 U, H = 180), 1 U by the market's own ATR (above), costs: the spread column + 0.35 x the design median spread on
entry, slippage 0.30 x (entries) / 0.65 x (stops) the design median spread (gold's ratios: 0.08 / 0.07 / 0.15 of
0.23). (c) FX majors (EURUSD, GBPUSD, USDJPY, AUDUSD) on the M15 frame (PA on M15 / H1, 2 of 3 on H1), 07-20 UTC,
target 20 U ... (U by ATR) - only if (a)/(b) show the logic travels at all. Note: the owner trades gold and the FX
majors; indices / XAUAUD would be a new market for the owner (BRIEF: other markets as inputs only) - reported as
evidence of the logic, and as a candidate only with that caveat.

**W4 - other edge levels (gold M1, F1's confluence, 00-20 UTC).** C4 replaced by (a) the 24-hour extreme (M1 bars
i-1440 .. i-16) < 4 U in front or behind, (b) the 5-day extreme (i-7200 .. i-16). Reported: the trades each adds
beyond F1 + W1. (Known: `shadow/c4_rejected.py` found no profitable subgroup of the C4-rejected signals inside F1's
windows, the 24-hour extreme among them; W4a mostly re-asks that, W4b is new.)

The pass bar for the weapon as a whole: >= 0.6 trades a day on the window from rules that each passed design.

## Results so far (design only)

W0: the builder reproduces F1 on design exactly (255 signal rows, 139 trades, +0.111 R, +57.9 USD, the same minutes
and sides as `portfolio/family_signals` + C4 + C5 + the floor).

W1 (`w1_design.py`): **fails design** - 62 trades (0.10 a day), +0.094 R, halves 2/5 (-0.57(3) -0.01(16) +0.39(14)
-0.38(10) +0.31(19)); 02-07 UTC 44 trades +0.083, 17-20 18 trades +0.120. Coin -0.185 R (win 20 % vs ours 27 %).
F1 + W1 together (00-20 UTC): 199 trades, 0.33 a day, +0.106 R, 3/5 halves. The hours F1 skips add only 0.10 a day:
C4 (near the 72-h extreme) is what keeps F1 rare, not its windows.

W2 (`w2_design.py`): **fails design** - every cell negative: T8 -0.128 / -0.132 R, T12 -0.068 / -0.063, T16 -0.080
/ -0.070 (216-228 trades, 0.36 a day, 1-2/5 halves). T12 H180 vs the coin: -0.063 vs -0.066 R, win 29 vs 27 %,
kinds 84/7/9 vs 85/7/8 - the M5 confluence near the 72-h extreme picks the side no better than a coin.

## More candidates (written 2026-10-18 before they are computed)

**W5 - F1 relaxed (gold M1, 00-20 UTC).** F1's frame with C4 + C5 + the level stop (3-10 U + floor), 8 U, BE 0.6, 60
min, but (a) without the indicators (PA only), (b) without the PA (2 of 3 only), (c) without both (tide + at a level
+ C4 + C5). Each with one attempt-free selection as F1 (2 per session-day). Pass as above; choose the most trades
among passing. Reported: trades on days without F1.

**W6 - the retest of a broken 72-hour extreme (gold M1, 00-20 UTC).** X = the 72-hour extreme as it stood before the
last two hours (M1 bars i-4320 .. i-121, highs for a BUY). The break: a high in bars i-120 .. i-1 above X + 0.5 U.
The retest: the decision bar's low within 1 M1 ATR of X (low <= X + 1 ATR) and its close above X; the H1 tide with
the side; C5. Stop X - 1 M1 ATR from the fill (3-10 U, floor 0.5 M15 ATR), 8 U, BE 0.6, 60 min; one attempt per X a
day; 2 per session-day.

W3a (`w3_design.py`, the M1 frame on other markets, C4 < 4 U): **fails on every market** - US100 61 trades -0.158 R
(gross +0.022), US30 50 -0.204 (gross +0.005), US500 90 -0.222 (gross +0.082), JP225 158 -0.166 (gross +0.104), XAUAUD
277 -0.576 (gross +0.067; its spread is ~2 U: 8 U = 6.2 AUD vs a 1.65 AUD spread + 0.5). Without C4 all are worse
(-0.17 .. -0.65 R, 0/5 halves). The side beats the coin by +3 .. +9 win points on US30 / JP225 / US500, but the gross
edge (+0.00 .. +0.10 R) is below the indices' costs (~0.2 R at an ATR-scaled 8 U). The logic does not travel at
the M1 scale. W3b (the M5 frame on the indices) is not run: W2 showed the M5 frame has no side information on gold
itself.

W5 (`w5_design.py`, F1 relaxed, gold M1 00-20 UTC): **fails the written pass rule** - W5a PA only 635 trades (1.04 a
day) -0.024 R, 2/5 halves (-0.15 -0.14 +0.05 -0.04 +0.10); W5b 2 of 3 only 261 (0.43) +0.012, 3/5; W5c neither 693
(1.14) -0.012, 2/5 (-0.16 -0.10 +0.09 -0.03 +0.07). Each beats its coin by ~4.4 win points (~+0.10 R: coin -0.11 ..
-0.14 R); the halves rise from 2023-24 to 2025-26, as costs in R fell (gold doubled, the spread stayed ~0.23 USD).

**A second design criterion, declared after seeing W5's halves (said plainly):** the brief notes that older
half-years cost about twice as much in R. D2 = gross R (no costs) >= +0.10 in >= 4 of 5 halves AND net R >= +0.10
on the latest half (2025-09 .. 2026-02, costs like today's). Applied to every candidate so far (`gross_check.py`),
not only to W5. A rule chosen by D2 is labelled as such in the window run.

D2 check (`gross_check.py`): **only W5a passes D2** (gross +0.11 +0.10 +0.20 +0.14 +0.21; net latest half +0.10). F1
itself: gross +0.45 +0.15 +0.17 +0.27 +0.23, net latest +0.09 (ours - coin +0.22 .. +0.31 in every half). W1 gross
2/5 >= 0.10; W5b 3/5; W5c 4/5 but net latest +0.07; W2 and W3a far off (W2 gross -0.37 .. +0.33; indices gross <=
+0.10 in most halves).

### Why W5a's losers lost (`w5_losers.py`, design 635 trades, net -0.024, gross +0.143; stopped kinds 58/5/37 vs the
coin 64/5/31)

- **The level kind decides most of it.** At a round number (gold's 50s) 104 trades +0.321 R, win 40 %, 5/5 halves
  (buys +0.41 / 78, sells +0.05 / 26); at the M15 chart-read level 383 trades -0.105 (2/5), at the H1 read 121
  -0.110 (2/5); today's / Asia's low few. Run alone, the round-level signals: 160 trades +0.236 R vs the coin
  -0.089 (win 36 vs 27 %). F1's own design trades: round 22 trades **+0.569 R**, M15 80 +0.068, H1 30 +0.019 - F1's
  edge sits mostly at round numbers.
- The other separations are smaller or few: C4 0-2 U +0.108 (4/5) vs 2-4 U -0.039 and behind -0.063; 00-02 UTC
  +0.137, 17-20 UTC -0.225 (44); ATR ratio 0.8-1.2 +0.089 vs > 1.2 negative; spread <= 0.15 ATR positive.
- Where the losers were: 504 of the 635 trades sat at an M15 / H1 chart-read level (the swing-pivot levels that
  the owner's chart tools also found to hold like placebos); the wrong-way share there 60-61 % vs 44 % at the round
  number. The stopped losers' too-early share (37 %) says the stop (1 M1 ATR beyond the level) is inside the normal
  swing for a third of them.

## R-series - the round number (written 2026-10-18 after the level-kind table above, before any of it is computed)

The level-kind result came from a breakdown of W5a's design trades (13 features x ~5 buckets), so it may be luck.
Placebo test first, then rules:
- Frame (`build(..., kinds=["round"], round_offset=o)`): gold M1, 00-20 UTC; the level = the multiple of 50 (+ o)
  just below the close for a BUY (above for a SELL); H1 tide; at the level (within 3 M1 ATR, the last 5 bars'
  extreme within 1 ATR of it); price action (M1 / M5 hammer, engulfing, sweep and reclaim); C4 < 4 U; C5; stop the
  level - 1 ATR (3-10 U, floor 0.5 M15 ATR); 8 U, BE 0.6, 60 min.
- **R0 placebo:** o = 0 (true round: xx00 / xx50) vs o = 10, 20, 25, 30, 40 (the same grid shifted). Roundness is
  real only if o = 0 beats every placebo offset in R (net and gross) and in halves.
- **R1:** o = 0 without C4 (does the round number need the 72-h extreme?), and with C4 < 8 U.
- **R2:** xx00 only vs xx50 only (step 100 vs the 50s between).
- If R0 holds: the candidate W7 = the R0 frame at o = 0 with the C4 choice from R1 (chosen by D2 then the most
  trades), frozen before the window.

### R0 / R1 / R2 results (`r0_placebo.py`, `out_r0.txt`; design)

| C4 | o = 0 (xx00 / xx50) | placebo o = 10 / 20 / 25 / 30 / 40 |
|---|---|---|
| < 4 U | 41 trades (0.07/d), win 51 %, **+0.536 R** net (gross +0.686, coin -0.026), halves +0.54 +0.71 +0.55 -0.25 +0.63 | -0.055 / -0.033 / -0.257 / -0.203 / +0.137 |
| < 8 U | 65 (0.11/d), +0.291 (coin +0.133), 3/5 gross >= .10 | -0.125 / +0.116 / -0.203 / -0.136 / -0.063 |
| none | 397 (0.65/d), -0.001 (gross +0.116, coin -0.097), net -0.17 -0.10 -0.19 +0.15 +0.09 | -0.090 / -0.037 / -0.121 / -0.106 / -0.119 |

R2 (C4 < 4): xx00 20 trades +0.765, xx50 21 +0.317 - both positive. **R0 holds:** the true round grid beats every
placebo grid in all three C4 settings (by 3-4 placebo sd); the quarter levels (xx25 / xx75) are the worst. Gold's
50s are real levels; the chart-read swing levels are not. But the round edge is large only near the 72-h extreme
(0.07-0.11 a day on design); without C4 it is ~0 net (+0.09 R over the placebos and the coin).
Count note: the no-C4 round frame trades 204 times in 2025-09 .. 2026-02 (1.6 a day) vs 36-71 a half before - at
4000+ gold with 1.7 USD M1 ATRs, price sits within 3 ATRs of a 50 much more often.

R1 detail (`r_losers.py`, the round frame without C4, 397 design trades): the edge is entirely **beyond** the 72-h
extreme - c4u <= 0 (price already through the 3-day extreme, back on a 50 just behind it): 30 trades, win 53 %,
**+0.541 R** (4/5 halves); c4u 0-4 U 8 trades +0.229; 4-8 U -0.084; 8-16 U -0.178; 16-32 -0.025; > 32 -0.015.
Same by time since the extreme: made within the last 30 min +0.475 (36), every later bucket -0.10 .. -0.03.
Everything else (side, xx00 / xx50, hour, ATR ratio, H1 strength, stop size) ~0 without that.
W2's M5 trades by level kind (`w2_kinds.py`): the round level is no better than the others on M5 (-0.01 .. -0.11
R) - the round number works with an M1 stop just beyond it, not with an M5 one. So it will not carry FX at the
M5 / M15 scale.

## W8 - W5a with F1 v2's exits (written before it is computed)

F1 v2 (in the bot) = the regime exit RM3 (M15 ATR >= 1.3 x its median over the last 288 M15 bars: the level runner
`shadow/level_runner.runner`, BE 0.6 x 8 U, a broken level in front lifts the stop behind it, then 1 M15 ATR trail,
180 min) else 8 U + BE 0.6 + 60 min with the 10-bar scratch (out at bar 10's close if the best is < 2 U and the
close is against). W8 = W5a's entries (F1 without the 2-of-3 vote, 00-20 UTC) with these exits. Also reported:
W7 = the round frame with C4 < 4 U (R0 o = 0) and W7b = C4 behind only (c4u <= 0), each with v1 and v2 exits. Pass:
D2, then count.

### W8 / W7 results (`w8_design.py`, design)

| rule | trades (/day) | win (coin) | net R | gross R | D2 | beyond F1 (/day, R) |
|---|---|---|---|---|---|---|
| F1 v1 (reference) | 139 (0.23) | 32 (24) | +0.111 | +0.224 | fail (latest +0.09) | - |
| F1 v2 (reference) | 139 (0.23) | 38 (25) | +0.188 | +0.358 | PASS | - |
| W5a v1 | 635 (1.04) | 27 (23) | -0.024 | +0.161 | PASS | 576 (0.95), -0.030; halves -0.18 -0.18 +0.07 -0.07 **+0.12** |
| W8 = W5a v2 | 659 (1.08) | 29 (23) | -0.072 | +0.137 | fail | 594 (0.98), -0.079 |
| W7 round C4 < 4 v1 | 41 (0.07) | 51 (29) | +0.536 | +0.686 | PASS | 13 (0.02), +0.501 |
| W7 round C4 < 4 v2 | 41 (0.07) | 59 (33) | +0.639 | +0.793 | PASS | 13 (0.02), +0.575 |
| W7b round behind v1 / v2 | 30 (0.05) | 53 / 57 | +0.541 / +0.778 | +0.71 / +0.96 | PASS | 9 (0.01) |

The v2 exits help F1 but hurt W5a's extra entries. The round frames are F1's best trades (28 of W7's 41 are F1's
own minutes or inside an F1 trade): a quality lever for F1, not a new source of trades.

## W9 - W5a without 17-20 UTC (written after W5a's hour table; the cause is another agent's measurement)

The cross agent measured gold's own late reversal: 17-21 UTC, the last 15 min -> the next 60 min correlate -3.5
(5/5 halves) - a continuation entry there fights it; W5a's 17-20 UTC trades were -0.225 R (44, 84 % wrong way).
W9 = W5a with entries 00:00-17:00 UTC only (F1's own windows end at 17:00 too). Pass: D2.

W9 result (design): 591 trades (0.97/d), net -0.009, gross +0.20 +0.12 +0.21 +0.18 +0.20 (5/5 >= .10), net latest
half +0.08 -> **fails D2 as written** (by 0.02 in the latest half; W5a passed by 0.00). Not frozen. W5a and W9 are
the same rule within noise; W9 is reported only as a design line.

## FROZEN for the window (2026-10-18, before any window number of these rules is computed)

**W5a "F1-wide"** (gold XAUUSD, M1): on every weekday M1 close from 00:00 to 19:59 UTC (entry time = the next bar's
open, 00:00 .. 20:00 UTC):
1. H1 tide with the side (last closed H1 bar: EMA20 above its value 3 bars before and close above EMA50 for a BUY;
   the mirror for a SELL);
2. at a level: the nearest of today's broker-day low, yesterday's low, the UTC day's Asia (00-07) low (the first and
   third as of 15 minutes before), the round 50 below, the nearest M15 and H1 chart-read level below (highs / above
   for a SELL); within 3 M1 ATR of the close, and the last 5 bars' low within 1 ATR of it;
3. price action: an M1 or M5 hammer, an M1 engulfing bar, or a sweep and reclaim of the level;
4. NO indicator vote (the difference from F1);
5. C4: the 72-hour extreme in the trade's way (M1 bars i-4320 .. i-16) less than 4 U in front, or behind; C5: M1
   ATR < 2 x its one-day median;
6. stop = the level - 1 M1 ATR from the fill, 3-10 U (else no trade), then at least 0.5 M15 ATR; target 8 U,
   break-even at 0.6 of the target, out after 60 minutes; one position at a time, at most 2 a session-day
   (sessions 00-07, 07-12, 12-20 UTC).
Costs: the auditor's real costs. Design: 635 trades, 1.04 a day, net -0.024 R, gross +0.161 (5/5 halves >= +0.10),
net 2025-09 .. 2026-02 +0.10 (D2). Chosen by D2, a criterion declared after seeing W5's halves.

**W7 "round-72"** (gold M1, for the record - an F1 quality lever, ~0.07 a day): the same frame with the round 50
(xx00 / xx50) as the only level, the PA, C4 < 4 U, C5, the stop / exits of W5a (v1). Design 41 trades, +0.536 R,
4/5 halves (o = 0 vs placebo grids -0.26 .. +0.14).

The window run (`window_run.py`): month by month, trades a day, win %, R, USD at 0.01 lot, worst loss, streak, max
DD, the losers' kinds vs the coin (20 seeds), the losers by level kind / C4 distance / hour, and the overlap with F1
v2 (`shadow/f1_v2_window_trades.csv`), S2 (CPI / NFP times) and S1 (`shadow/overlap.py`'s construction).


## THE WINDOW RUN (2026-03-01 .. 2026-10-14, once per frozen rule; `window_run.py`, `out_window.txt`)

(The first run crashed after the monthly table in the overlap code - a timestamp type error; fixed and re-run with
the rule untouched; the numbers above the crash were identical.)

| rule | trades (/day) | win (coin) | R (coin) | USD 0.01 lot | months + | worst / streak / max DD | kinds ours / coin |
|---|---|---|---|---|---|---|---|
| **W5a F1-wide** | 164 (1.01) | 36 % (30) | **+0.027** (-0.075 +- 0.080) | +40.1 | 4/8 | -10.93 / 14 / 79.4 | 61/7/32 / 55/5/39 |
| W7 round-72 | 22 (0.14) | 50 % (36) | **+0.331** (+0.030 +- 0.167) | +56.4 | 5/7 | -8.72 / 4 / 19.4 | 83/0/17 / 60/0/40 |

W5a by month (n, R, USD): 03 14 +0.41 +48.1 | 04 18 +0.04 +3.0 | 05 25 +0.04 +14.9 | 06 19 -0.05 -7.0 | 07 25 -0.06
-3.5 | 08 30 -0.04 -20.5 | 09 27 -0.17 -17.7 | 10 6 +0.82 +22.9. Gross +0.132 R, costs -0.106 R.
W5a overlap: 21 of its 164 are F1 v2's own minutes; none inside an S1 trade or within 30 min of a CPI / NFP release;
on days without F1 or S2 77 trades (0.48 a day) +0.048 R +26.5 USD; not F1's 143 (0.88 a day) +0.014 R; weekdays
with any trade F1 + S2 41 of 162 -> + W5a 80 (+ S1 86). six-loss check: avg stop 6.19 USD -> 37 USD (fits 50).
W7 overlap: 17 of its 22 are F1 v2's own trades; 5 new (0.03 a day, +0.198 R).
**Verdict W5a: fails** (+0.027 R < +0.10; 4/8 months). The count is there (1.0 a day, 0.48 on days without F1/S2),
the edge is not: +5.5 win points over the coin, about half of what gold's costs need at these sizes.

Why W5a's window losers lost (buckets, n / R / stopped kinds): at the M15 / H1 chart-read levels 106 trades -0.02 /
-0.03 R vs the round 50 58 trades +0.11; 17-20 UTC 12 trades -0.58 (75 % wrong way - the late reversal the cross agent
measured; W9 would have cut them, but W9 was not frozen); the 72-h extreme made 2-24 h before 23 trades -0.32 (an
old extreme price came back to); Aug-Sep 57 trades -0.10 R (W5a's sells 54 % of the window; a two-way phase).
The wrong-way share is above the coin's (61 vs 55 %): the extra entries at swing-pivot levels pick the side no better
than a coin; their only edge is C4's drift, which the costs (0.106 R) take.

### Diagnostic after the window (no rule chosen; `window_diag.py`): F1's edge is the round number

F1's own frozen trades split by whether the round frame (xx00 / xx50 the level, at it, PA) fires on the same minute:

| | at a round 50 | not at a round 50 |
|---|---|---|
| F1 v1 design | 22 trades, **+0.569 R**, halves +0.54 +0.95 +0.95 +0.50 +0.11 | 117, +0.024 (-0.04 +0.10 -0.13 +0.13 +0.09) |
| F1 v2 design | 22, **+0.881** | 117, +0.057 |
| F1 v1 window | 17, **+0.399**, +48.9 USD, win 53 % | 17, -0.004, +2.0 USD, win 35 % |
| F1 v2 window | 17, **+0.547**, +72.5 USD, win 65 % | 18, -0.089, -9.4 USD, win 33 % |

Out of sample, F1's whole profit came from its round-number half; the other half is break-even in both periods.
The C4 + round combination is the edge; C4 alone or the round number alone are worth ~+0.1 R over a coin, below
gold's costs.

## R-X - round-72 on other markets (written 2026-10-18 before it is computed)

The round number at the 72-h extreme is the one combination with a large edge on gold (design +0.54 R, window +0.33,
placebo grids -0.26 .. +0.14). Round numbers are a market-wide habit (orders and stops cluster at big figures), so
the same rule should work on other markets if the cause is real - and each market adds its own count.
- Frame: W7 exactly (M1, H1 tide, the round level only, at it, PA, C4 < 4 U, C5, stop the level - 1 M1 ATR 3-10 U +
  the 0.5 M15-ATR floor, 8 U, BE 0.6, 60 min; 1 U = the market's 28-day median M1 ATR / 1.63; real costs as W3).
- Rounds (about 30-45 M1 ATRs apart, a figure traders quote): EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF 0.0050
  (the big and the half figure); USDJPY 0.50; US500 50; US100 250; US30 250; JP225 500; XAUAUD 50.
- Hours: FX 00-20 UTC; US indices 13:30-20:00; JP225 00-06 + 13:30-20:00; XAUAUD 00-20.
- Placebo per market: offsets 0.2 / 0.4 / 0.5 / 0.6 / 0.8 of the step. Pass (design, per market and pooled): the
  true grid beats the placebo mean by >= 0.15 R gross, net R >= +0.10, positive in >= 3 of the halves that have >= 5
  trades. The markets that pass, together, form the candidate W10 (one position per market, frozen with this list).


### R-X results (`rx_design.py`, `out_rx_design.txt`, design; `build_round_multi` reproduces build(kinds=round) on gold:
76 / 128 signals identical)

| market | true grid: trades (/d), net R, gross R, coin | placebo mean net / gross | gross over placebo | verdict |
|---|---|---|---|---|
| XAUUSD | 41 (0.07), **+0.536**, +0.686, -0.026 | -0.082 / +0.056 | +0.630 | PASS |
| USDJPY | 129 (0.21), +0.044, +0.208, -0.090 | -0.253 / -0.031 | +0.239 | fail (net) |
| JP225 | 58 (0.10), -0.180, +0.188, -0.295 | -0.301 / -0.016 | +0.204 | fail |
| US500 | 24 (0.04), -0.217, +0.127, -0.322 | -0.309 / -0.025 | +0.152 | fail |
| EURUSD / GBPUSD | 68 / 88, -0.209 / -0.129, gross +0.09 / +0.08 | -0.33 / -0.24 | +0.11 / +0.11 | fail |
| AUDUSD / USDCAD | 71 / 75, -0.52 / -0.50, gross +0.03 / +0.10 | | +0.10 / +0.10 | fail |
| NZDUSD / USDCHF | 85 / 62, -0.68 / -0.35 | | -0.11 / +0.03 | fail |
| US100 / US30 / XAUAUD | 25 / 21 / 101, +0.07 / -0.17 / -0.46 | | -0.12 / -0.15 / -0.01 | fail |

Pooled without gold: 807 trades (1.33 a day), -0.295 R. Round grids beat their placebos gross in 7 of 12 markets
(round numbers are real levels elsewhere too), but at the M1 scale the costs are 0.2-0.7 R (the coins) against a
gross edge of +0.1-0.2: only gold's spread (~0.03 of its M15 range today) is cheap enough. And the effect does not
survive a larger timeframe (W2 on M5), so a bigger scale cannot pay the FX / index costs either. R-X: no.

### W6 result (`w6_design.py`, design): fails - 706 trades (1.16 a day), -0.058 R, 1/5 halves (latest half -0.01),
coin -0.206 (win 24 vs 20 %, +4.1 pts), kinds 65/4/31 vs 69/4/28. The retest of a broken 72-h extreme has the same
~+4-point C4 drift as W5 and nothing more.

## Verdict (2026-10-18)

No fourth weapon passes. Every count source tested (F1 at other hours, F1 on M5, F1 on indices / XAUAUD, F1 relaxed,
the 72-h-break retest, round-72 on 12 other markets) carries at most C4's drift (+4-6 win points over a coin, ~+0.10
R) - below gold's costs at these sizes except in the cheapest half-year. The one frozen count candidate, W5a
(1.0 a day), made +0.027 R on the window. The one strong effect found - the round 50 at the 72-hour extreme - is
real (placebo grids, design and window, F1's own trades split) but rare (0.07-0.14 a day) and mostly inside F1.


# Follow-up: the round number (owner, 2026-10-18) - written before any of it is computed

Q1 - COUNT from the same cause (`q1_anchors.py`, design). The round frame (W7: gold M1 00-20 UTC, H1 tide, the round
level only, at it, PA, C5, stop the level - 1 ATR 3-10 U + floor, 8 U, BE 0.6, 60 min) with C4's anchor replaced by:
- A72 the 72-hour extreme (W7, the reference); A24 the 24-hour extreme (M1 bars i-1440 .. i-16); AW the 5-day
  extreme (i-7200 .. i-16); AS the current session's extreme (sessions 00-07 / 07-12 / 12-20 UTC, bars from the
  session's start to i-16; none in the first 30 minutes); AY yesterday's broker-day high / low;
- proximity as C4: the anchor in the trade's way closer than 4 U in front, or already behind.
- Levels: the round 50 grid (placebos: offsets 10 / 20 / 25 / 30 / 40) and the round 100 grid separately (placebos
  20 / 40 / 60 / 80; offset 50 = the xx50s, shown apart).
- Reported per anchor: trades / day, net / gross R, halves, the coin, the placebo mean, and the trades not near the
  72-h extreme (what the anchor adds beyond W7 / F1).
- Pass: >= +0.15 R net, gross over the placebo mean >= +0.15, >= 3 of the halves with >= 5 trades positive; the
  aim 0.4 a day on the trades beyond C4-72. Several anchors may be OR-ed only if each passes alone.

Q2 - ENTRY by a limit at the round 50 (`q2_limit.py`, design). Arming at an M1 close (00-20 UTC) when the H1 tide is
with the side, C4 (72 h) holds, C5 holds, and price is above the round 50 below (BUY) within 3 M1 ATR and has not
touched it in the last 5 bars (an approach, not a test in progress). The order: BUY limit at the round + the arming
bar's spread (fills when the bid touches the round: the bar's low + its spread <= the limit; a bar opening below
fills at its open's ask); SELL limit at the round (fills when the bid high >= it). Valid 60 bars, one order per round
level, side and day; cancelled when price moves 8 U away from the level first. Stop the round - 1 ATR (ATR at
arming; 3-10 U from the fill, floor 0.5 M15 ATR), 8 U, BE 0.6, 60 min from the fill; no entry slippage (a limit),
stop slippage as before; in the fill bar only the stop is checked. Compared with W7 (the market entry after PA):
trades / day, R, and the trades W7 does not take. Also L2: the same with the anchor A24 if Q1 shows A24 passes.

Q3 - QUALITY (`q3_quality.py`, design; the window split of F1 by the round was already SEEN in window_diag.py, so a
window run of these forms is not clean and is labelled so):
- F1R-a: F1 only when the round frame fires on the same minute (round level within 3 ATR, tested, PA);
- F1R-b: F1 only when its own nearest level is the round 50 (level_kind round);
- F1R-c: F1 only when a round 50 lies between its stop and its entry;
- T1 tilt: F1 as is, full size when F1R-a holds, half size otherwise.
Choice: the form with the higher design net R in >= 4/5 halves; the tilt judged on USD, R-sum per unit of average
risk, and max DD vs F1 as is (v1 and v2 exits).

Q4 - USDJPY round-72 with the Q2 limit entry (only if time).


## Q1 results (`q1_anchors.py`, `out_q1.txt`, `q1_union.py`; design)

Round 50 grid, anchor within 4 U in front or behind:

| anchor | trades (/d) | win (coin) | net / gross R | coin R | placebo mean net / gross | halves | not near the 72-h extreme | pass |
|---|---|---|---|---|---|---|---|---|
| A72 (W7) | 41 (0.07) | 51 (29) | +0.536 / +0.686 | -0.026 | -0.082 / +0.056 | +.54 +.71 +.55 -.25 +.63 | 0 | yes |
| A24 | 60 (0.10) | 47 (35) | +0.396 / +0.502 | +0.073 | -0.118 / +0.015 | +.03 +.46 +.12 -.25 +.66 | 20, +0.145 | yes |
| AW (5 days) | 36 (0.06) | 53 (33) | +0.556 / +0.648 | +0.071 | -0.081 / +0.051 | | 0 | yes |
| **AS (session)** | **112 (0.18)** | 40 (30) | **+0.300** / +0.464 | -0.018 | -0.087 / +0.037 | +.30 +.37 -.01 +.13 +.41 | **72 (0.12), +0.191** | yes |
| AY (yesterday) | 198 (0.33) | 35 (31) | +0.083 / +0.174 | -0.037 | -0.094 / +0.020 | | 160, -0.010 | no |

Round 100 grid: higher R on fewer trades (A72 20 trades +0.765; AS 51 +0.321; AY 95 +0.148), but the xx50 grid
(offset 50) is itself positive (+0.24 .. +0.32): the 50s are real levels too, so the 100s are not a separate edge; by
the written rule only AS passes on the 100 grid. Kept: the round 50 grid.

**The edge is "a round 50 at a FRESH extreme", not the 72-hour extreme as such**: the session's running extreme (as
of 15 minutes before) works as well per trade and fires on twice the minutes; yesterday's high / low does not.
W11 = the round 50 frame with any passing anchor (A72 | A24 | AW | AS) - in practice AS plus a few early-session A72 /
A24 cases: 113 trades (0.19 a day), win 40 % (coin 30), net **+0.306 R**, gross +0.469, halves +0.30 +0.37 -0.01
+0.25 +0.41, D2 PASS, worst -13.34 USD, streak 5, max DD 25.0 USD; kinds 72/10/18 vs the coin 68/5/26. Beyond F1:
86 trades (0.14 a day), +0.235 R (latest half 50 trades, +0.38). Count by half: 0.08 / 0.12 / 0.16 / 0.09 / **0.45
a day** - at 4000+ gold a 50 is crossed far more often. v2 exits +0.310 (no better; v1 kept).

## FROZEN for the window: W11 "round-50 at a fresh extreme" (2026-10-18)

Gold M1, entries 00:00-20:00 UTC weekdays. At an M1 close: H1 tide with the side; the level = the multiple of 50 just
below the close (BUY; just above for a SELL); at it: within 3 M1 ATR and the last 5 bars' low within 1 ATR of it;
price action (M1 / M5 hammer, M1 engulfing, sweep and reclaim of the 50); C5 (M1 ATR < 2 x its one-day median); an
anchor in the trade's way within 4 U in front or already behind, any of: the 72-h extreme (M1 bars i-4320 .. i-16),
the 24-h extreme (i-1440 .. i-16), the 5-day extreme (i-7200 .. i-16), the current session's running extreme
(sessions 00-07 / 07-12 / 12-20 UTC, from its start to i-16, not in its first 30 minutes). Stop the 50 - 1 M1 ATR
from the fill, 3-10 U (else no trade), at least 0.5 M15 ATR; target 8 U, BE at 0.6 of it, 60 minutes; one position at
a time, 2 a session-day. Real costs.

Q2 clarification (before computing): with a limit fill at the round, the stop 1 ATR beyond it is ~2 U from the fill,
so the written "3-10 U from the fill" would refuse almost every order. Stops under 3 U are widened to 3 U (as
`portfolio/plib._stop` did); over 10 U no order. Everything else as written.


## Q2 results (`q2_limit.py`, `out_q2.txt`; design) - the limit at the round FAILS

| anchors | true grid: trades (/d), win, R | placebo grids R (10 / 20 / 25 / 30 / 40) |
|---|---|---|
| L1 A72 | 47 (0.08), 19 %, **-0.191** | -0.030 / +0.411 / -0.109 / +0.043 / -0.169 |
| L2 A24 | 68 (0.11), 19 %, **-0.161** | -0.102 / +0.233 / -0.160 / -0.194 / -0.246 |
| L3 W11 anchors | 130 (0.21), 19 %, **-0.156** | -0.179 / +0.011 / -0.162 / -0.206 / -0.307 |

A resting order at the 50 loses and is no better than the placebo grids. Why: it fills on every touch, including the
touches that go straight through (the turn-zone study: 81-86 % of approaches go through a level); the market entry
in W7 / W11 waits for the 50 to be tested AND for price action (a hammer, an engulfing, a sweep and reclaim) - that
confirmation is where the round number's edge shows. Win 19 % vs W11's 40 %; the stopped losers 57-63 % wrong way.
No window run (failed design).

## Q3 results (`q3_quality.py`; design clean; the window SEEN in window_diag.py - not clean)

| form | design v1: n, R, DD, halves | design v2: R, DD | window v1: n, R, USD, DD | window v2: R, USD, DD |
|---|---|---|---|---|
| F1 as is | 139, +0.111, 31.2, +.11 +.22 -.01 +.17 +.09 | +0.188, 28.8 | 34, +0.198, +50.8, 21.4 | +0.219, +63.1, 33.4 |
| F1R-a (round frame fires) | 28, +0.570, 12.6, +.54 +.52 +1.09 -.00 +.52 | +0.825, 10.3 | 17, +0.399, +48.9, 16.9 | +0.547, +72.5, 19.1 |
| **F1R-b (nearest level is the 50)** | 26, **+0.590**, 12.6, 5/5 | **+0.864**, 10.3 | 15, **+0.432**, +46.9, 10.5 | **+0.600**, +70.5, 12.7 |
| F1R-c (a 50 between stop and entry) | 29, +0.564, 16.7 | +0.777, 14.3 | 16, +0.342, +40.5, 16.9 | +0.500, +64.2, 19.1 |
| T1 tilt (1 at the round, 0.5 else) | R/unit +0.173, +52.8 USD, DD 20.1 (USD/DD 2.63 vs 1.86) | +0.282, +96.4, DD 17.8 (5.43 vs 3.89) | +0.265, +49.9, DD 18.8 (2.65 vs 2.37) | +0.326, +67.8, DD 26.2 (2.58 vs 1.89) |

Design choice (the written rule: the highest net R with >= 4/5 halves): **F1R-b** - F1 only when its own nearest
level is the round 50: same USD as F1 on about 45 % of the trades, a third of the drawdown. The tilt keeps F1's count
and USD and cuts the drawdown (USD / DD +40 % design, +12-37 % window).

## THE WINDOW RUN of W11 (`q_window.py`, `out_q_window.txt`; once, frozen above)

W11: 77 trades (**0.48 a day**), win 40 % (coin 31 +- ; R -0.025 +- 0.137, edge **+9.4 pts**), **R +0.149**,
**+96.2 USD** at 0.01 lot, months+ 6/8, worst -10.90 USD, streak 8, max DD 40.1 USD, avg stop loss 5.81 -> 6 in a
row 34.9 USD (fits 50). Kinds 55/0/45 vs the coin 53/0/47.
By month (n, R, USD): 03 8 +0.21 +12.3 | 04 15 -0.26 -12.9 | 05 17 +0.45 +47.1 | 06 14 +0.34 +26.6 | 07 8 +0.49
+22.7 | 08 6 -0.04 +0.6 | 09 7 -0.08 +8.6 | 10 2 -1.00 -8.8.
Overlap: 17 are F1 v2's own trades; none inside an S1 trade; 1 within 30 min of a CPI / NFP release. Not F1's: 60
(**0.37 a day**), +0.086 R, +49.6 USD. On days without F1 or S2: 47 (0.29 a day), +0.099 R, +40.9 USD. Weekdays
with any trade: F1 + S2 41 of 162 -> + W11 79 (+ S1 89).
Parts: near the 72-h extreme (= W7) 22 trades +0.331 R +56.4 USD; the session / 24-h / week anchors only 55 trades
+0.076 R +39.8 USD.
Why W11's losers lost (31 stopped, 55 % wrong way, 45 % too early - like the coin, so the losers are the stop's
size against the move, not the side): 07-12 UTC 27 trades -0.17 R (London: the 50 tested early in the session,
when the session extreme is only an hour old and price runs back through it); 17-20 UTC 7 trades -0.35 (all wrong
way - the late reversal again); April 15 trades -0.26 (a fast, two-way month); sells 48 trades +0.04 vs buys 29
+0.33; a calm tape (ATR ratio <= 1.2) 24 trades -0.05 vs 53 +0.24.
**Verdict W11: passes the brief's tolerance (+0.10) on the window as a whole (+0.149, 6/8 months), not the owner's
+0.15 bar on the trades it adds beyond F1 (+0.086 R, 0.37 a day) - short of the 0.4 a day / +0.15 R aim.**

## Q4 (`q4_usdjpy.py`; design) - fails

USDJPY round-72 with the limit entry: A72 96 trades -0.358 R (placebo grids -0.19 .. -0.29), W11 anchors 299
(0.49 a day) -0.415 (placebos -0.26 .. -0.31). Worse than the placebos: a resting order at a round number gets run
through (Q2's cause, stronger on USDJPY). The market entry after PA (R-X) was +0.044. No.

# W11 follow-up - two loser causes (owner approved, 2026-10-18) - written before computing (`q5_design.py`)

Base: W11 as frozen. Variants (design only; each alone, then combined):
- a: no entries 17:00-20:00 UTC (the late reversal).
- b1: the session-extreme anchor (AS) counts only if that extreme was made >= 60 minutes before the decision, in
  London (07-12 UTC) only; b2: the same everywhere. "Age" = minutes from the bar that set the session's running
  extreme (as read at i-16) to the decision bar. The other anchors (72-h, 24-h, 5-day) are unchanged.
- a+b1, a+b2.
- c (optional, reported for completeness, chosen only if a / b do not get there): ATR ratio > 1.2; c+a, c+a+b2.
Reported: trades / day, R, halves, the placebo grids (offsets 10 / 20 / 25 / 30 / 40 with the same variant), and the
trades beyond F1 (not F1's minute, not inside an F1 trade). Freeze rule: the variant with the highest beyond-F1 R
that beats W11's beyond-F1 design figure (+0.235 R, 86 trades, 0.14 a day) while keeping >= 2/3 of that count
(>= 58 trades); ties -> more trades. If none, no window run.

## W11 follow-up results (`q5_design.py`, `out_q5_design.txt`; design)

| variant | all: n (/d), net R, halves + | placebo mean | beyond F1: n (/d), net R | max DD | freeze rule |
|---|---|---|---|---|---|
| W11 | 113 (0.19), +0.306, 4/5 | -0.088 | 86 (0.14), +0.235 | 25.0 | reference |
| a no 17-20 | 101 (0.17), +0.269, 4/5 | -0.089 | 74 (0.12), +0.173 | 25.0 | no (R) |
| **b1 London AS >= 60 min** | 100 (0.16), **+0.337**, 4/5 | -0.082 | **73 (0.12), +0.265** (halves -.36 +.48 -.37 +.75 +.46) | 21.4 | **yes** |
| b2 AS >= 60 min everywhere | 80 (0.13), +0.393, 4/5 | -0.078 | 53 (0.09), +0.322 | 20.1 | no (count < 58) |
| a+b1 | 88 (0.14), +0.298 | -0.083 | 61 (0.10), +0.195 | 21.2 | no (R) |
| a+b2 | 70 (0.12), +0.342 | -0.083 | 43 (0.07), +0.224 | 19.9 | no |
| c ATR ratio > 1.2 | 71 (0.12), +0.241 | -0.088 | 48 (0.08), +0.072 | 30.0 | no |
| c+a / c+a+b2 | 67 / 52, +0.250 / +0.339 | | 44 / 29, +0.070 / +0.136 | | no |

Skipping 17-20 UTC does not help on design (its trades were not the problem there; the window's 7 were). The busy
tape (c) cuts the beyond-F1 part to ~0. A young session extreme in London is the cause that holds: b1 lifts the
beyond-F1 R from +0.235 to +0.265 for 13 fewer trades. Still far from the 0.3 a day aim on design (0.12; the latest
half 43 beyond-F1 trades, ~0.34 a day).

## FROZEN: W11-b1 (2026-10-18) - W11 exactly, except that the session-extreme anchor does not count in London
(entries 07:00-11:59 UTC) when that extreme was set less than 60 minutes before the decision (the 72-h / 24-h / 5-day
anchors unchanged). One window run; the window was already seen once for W11, so this run is less clean.

### W11-b1 window run (`q5_design.py window b1`, `out_q5_window.txt`; window seen once before for W11 - less clean)

67 trades (0.41 a day), win 42 % (coin 30 %, R -0.078 +- 0.107; edge +12.1 pts), **R +0.166**, **+89.7 USD**, months+
6/8 (03 +12.9, 04 -16.3, 05 +34.9, 06 +26.6, 07 +26.4, 08 +5.5, 09 +8.6, 10 -8.8), worst -8.90 USD, streak 8, max DD
37.6 USD (6 average losses 34.4 USD: fits 50). Overlap: 17 = F1 v2's own trades, none inside S1, 1 near a CPI / NFP
release. Beyond F1: 50 trades (**0.31 a day**), **+0.097 R**, +43.2 USD; on days without F1 / S2 39 (0.24 a day) +0.084.
Weekdays with any trade: 41 -> 71. vs W11: 10 fewer trades (London 27 -> 17), R +0.149 -> +0.166, beyond-F1 +0.086 ->
+0.097. Losers: London 07-12 still 17 trades -0.29 R (70 % wrong way); 17-20 UTC 7 trades -0.35 (all wrong way); April
14 trades -0.30; calm tape (ATR ratio <= 1.2) 20 trades -0.11 vs 47 +0.28; sells +0.07 vs buys +0.30.
**Verdict: the whole rule clears +0.15 R; the part beyond F1 (+0.097 R at 0.31 a day) meets the count aim but not
the +0.15 R aim.**
