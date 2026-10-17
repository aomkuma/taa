# News agent - notes (2026-10-17)

Folder: `research/2026-10-18-moments/agents/news/`. Periods: **A** = 2021-09 .. 2023-10 (older design data),
**B** = 2023-11 .. 2026-02 (design), **T** = 2026-03-01 .. 2026-10-14 (the test, once per frozen rule).
Simulation: `lab.py` (`Gold.trade`, the brief's conventions: decide at a bar's close, enter at the next open, buy
at ask + 0.07, stops/targets on bar extremes, the stop first when both, time exit at the close with slippage).
R = USD / (stop + 0.07). The coin's expectation = the average of the rule's side and the opposite side with the
same stop and exit (a single random draw on ~5-19 events is too noisy).

## Calendars (official sources only)

- `gold.releases()` (BLS / BEA / Fed, see `build_calendar.py`): CPI, NFP, PPI, PCE, GDP, FOMC 14:00 ET.
- `extra_releases.csv` (this folder), built 2026-10-17:
  - **MIN** FOMC minutes, 14:00 ET: dates from https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
    ("Minutes: Released ...").
  - **PC** the FOMC press conference, 14:30 ET on every statement day (same page; a press conference after every
    meeting since 2019).
  - **RET** advance retail sales, 08:30 ET: `sources/MARTSreleasedates.xls` from
    https://www.census.gov/retail/marts/www/MARTSreleasedates.xls (linked from
    https://www.census.gov/retail/release_schedule.html; columns = release month, cells = day; post-shutdown
    releases marked ** included as listed; October 2025 N/A).
  - Not added: weekly jobless claims (DOL holiday shifts not sourced; they mostly coincide with other 08:30
    releases), ISM (not an official government source).

## Step 1 - ticks (2025-10 .. 2026-02, 19 releases; `ticks_study.py`)

- FBS's tick spread is a flat 0.39 USD before, during and after every release (no widening in the data; M1's
  `spread` column says 0.23-0.36). Tick rate doubles (4 -> 8-10 a second) for minutes.
- The first impulse peaks at a median ~50-65 s after the release (CPI 50 s, FOMC 60 s, NFP 44 s); the adverse
  move before the peak is small (0.2-3 USD), the peak 7-24 USD.
- Within 10 minutes after the peak price pulls back by a median 8-30 USD (CPI 14 = 60 % of the peak, FOMC 24 and
  NFP 30 = more than the whole impulse). So any stop "beyond the spike" sits inside the next ten minutes' noise.
- Five months of ticks hold only 3 FOMC days: too few to fit anything on ticks; ticks are used to check the M1
  simulation (below).

## Step 2 - explore and a grid (A and B only; `explore.py`, `grid.py`, `rank.py`, `rank2.py`)

Families per event: follow at k = 1..30 minutes, fade at k (stop beyond the extreme since the release + 1 pre),
pullback-then-follow; stops in `pre` units (the pre-release hour's mean 1-minute range, scale-free 2021-2026);
targets 1-3 R or time exits 30/60/120. 85k simulated trades.

- For the 08:30 releases (CPI, NFP, PPI, PCE, RET, GDP) and the minutes, the share of rules positive in both A and
  B is 3-14 %, below the ~25 % of independent coin halves; after dropping each period's two best trades almost
  nothing survives (CPI 5 of 896, NFP 3/952, PPI 6/840, PCE 2/742, RET 2/735, MIN 0/420). The kept ones are
  isolated peaks (e.g. NFP fade at 08:45: +0.28 R in A and B, but its neighbours at 08:40 and 09:00 are
  negative). **Round 10b's "FOMC and PCE continue, CPI reverses" does not hold on A** (2021-09 .. 2023-10, big
  first minute, follow from the next open): PCE 14 releases, continues 29 % at 30 min, -1.31 USD (B: 80 %, +2.70);
  FOMC 14, 36 %, +0.85 at 30 min but -2.68 at 60 (B: 62 %, +3.06 / +6.41); CPI 20, 50 %, -0.08 (B: 42 %, -0.36).
- The 14:00 FOMC statement: the direction since 14:00 has no stable sign (A negative, B positive at every k).
- **The press conference (14:30 ET) stands out**: 32 % of rules positive in both periods (80 of 595 survive the
  trim). `fomc_day.py`: deciding 2-5 minutes into the presser, fading wins in both periods (f30 -12 pre in A, -2
  in B); from **10 minutes in (14:40)** following the move since 14:30 wins in both periods at every horizon and at
  every later decision minute tried (14:40, 14:45, 14:50, 15:00), continuing 59-89 % of the time to +120 min.
- The same rule (follow the first 10 minutes, 2 x ATR10 stop, 2-hour hold) on every other release: negative or
  mixed (CPI -0.27/-0.05 R, NFP +0.26/-0.33, PPI -0.59/-0.34, RET -0.16/-0.60, MIN -0.59/-0.30, FOMC 14:00
  -0.44/-0.12). The effect is specific to the presser, not "news in general".

Cause (a hypothesis, not proven): the statement is read in a minute and is often ambiguous; the chair's answers
reprice the path of rates over the first ~10 minutes (the first minutes overreact and reverse), and once the
reading is set it carries through the afternoon.

## Step 3 - the presser rule on design data (`presser.py`, `candidates.py`)

Every one of 108 plans (decision 14:40 / 14:45 / 14:50 x six stops x six exits) is positive in both A and B, and
every one beats the coin's expectation in both. Hand-checked on ticks (2025-10-29, 2025-12-10, 2026-01-28): the M1
results match the tick paths (entry, adverse extreme, +120-minute exit within 0.1-0.4 USD).

Step-by-step improvement (A + B, 35 presser days, 0.01 lot):

| Step | Rule | Trades | R/trade | USD/trade | Positive | Sum USD | Max DD | Coin R |
|---|---|---|---|---|---|---|---|---|
| 0 | Round 10b: FOMC 14:00 big first minute, follow 30 min (B only) | 16 | n/a (no stop) | +2.69 | 62 % | +43 | | |
| 0b | Same idea at 14:10 (side since 14:00), 2 x ATR10 stop, 2 h | 36 | -0.27 | -1.88 | 28 % | -68 | | +0.22 |
| 1 | Move to the presser: 14:40, side since 14:30, stop 10 pre, 60 min | 35 | +0.87 | +6.48 | 57 % | +227 | 34 | +0.17 |
| 2 | Stop = 2 x the mean 1-min range of the last 10 bars | 35 | +1.13 | +6.54 | 60 % | +229 | 37 | +0.28 |
| 3 | Hold 120 min (**P1**) | 35 | +1.20 | +7.07 | 60 % | +247 | 37 | +0.35 |
| (3') | Hold 180 min (crosses the 17:00 ET daily break in summer) | 35 | +1.52 | +10.38 | 60 % | +363 | 37 | +0.57 |

P1 by period: A 16 trades, +0.84 R, +4.51 USD/trade (gold ~1800); B 19, +1.50 R, +9.22 USD/trade. Without each
period's two best trades: +0.43 / +0.92 R. Losers' kinds A 83/17/0 %, B 29/29/43 % (the opposite side: 100/0/0,
78/22/0) - the presser's losers are mostly wrong-way in A, and in B often "right but too early" (the presser's
whipsaw at 14:40-14:45 takes the stop, e.g. 2025-12-10: stopped at -14.6, +22 two hours later).

## FROZEN RULES (written 2026-10-17 before any test computation)

**P1 - the presser follow (primary):**
- Days: FOMC statement days (federalreserve.gov calendar), press conference 14:30 ET.
- At the close of the 14:39 ET M1 bar: side = sign(close(14:39) - open(14:30)). Enter at the 14:40 bar's open
  (market; buy at ask + 0.07, sell at bid - 0.07).
- Stop = 2 x the mean (high - low) of the ten M1 bars 14:30 .. 14:39, at least the mean 1-minute range of
  13:00 .. 13:59 ET. No target, no break-even.
- Exit at market at the close of the 120th bar (16:39 ET) if not stopped. One trade per FOMC day.
- Losers' kinds against a target of 2 x the stop.

Declared variants (each a separate rule, reported but the verdict rests on P1): **P1_t180** (hold 180),
**P1_k45** (decide at 14:44 close, enter 14:45), **P1_m3** (stop 3 x).

The test window holds 5 presser days (2026-03-18, 04-29, 06-17, 07-29, 09-16): one trade each in March, April,
June, July and September; none in May, August, October.

## Test of P1 (run once: `candidates.py --test P1 P1_t180 P1_k45 P1_m3`)

| Rule | Trades | Positive | USD/trade | Sum USD | R/trade | Coin R | Losers' kinds (ours / opposite side) |
|---|---|---|---|---|---|---|---|
| **P1** | 5 | 40 % | +4.53 | +22.6 | +0.77 | +0.32 | 67/33/0 / 100/0/0 |
| P1_t180 | 5 | 40 % | +0.05 | +0.2 | +0.39 | +0.17 | |
| P1_k45 | 5 | 40 % | +8.79 | +44.0 | +0.96 | +0.61 | |
| P1_m3 | 5 | 40 % | -1.68 | -8.4 | +0.31 | +0.01 | |

P1 month by month: 2026-03-18 sell +59.3 (time); 04-29 sell -13.6 (stop, 21 min); 06-17 buy -33.8 (stop
33.7 - the presser's bars averaged 16.9 USD of range, 27 min); 07-29 buy -14.8 (stop, 76 min); 09-16 sell +25.6
(time). Two of five months positive. Hand-checked on ticks (03-18, 06-17, 07-29): the same exits. The R mean is
lifted by one 5.7 R day; with five trades nothing can be concluded either way.

## Step 4 - the release-minute straddle (ticks `straddle.py`, M1 `straddle_m1.py`, `s2_ticks.py`)

The ticks show the first impulse peaks ~50-65 s after the release with a small adverse move before the peak; the
data reach FBS's feed ~1.2-1.4 s after the release and the first tick jumps 2-8 USD (CPI) - a straddle of stop
orders catches the impulse with that gap as its cost.

- Ticks, 27 releases 2025-10 .. 2026-02, a grid of trigger D x window x target x stop x hold: CPI positive for
  every D (4 releases), the rest mixed; too few to choose on.
- M1 history (A, B) with a worst-case ordering inside the release minute (both triggers in the bar = the wrong side
  first; the bar's adverse extreme after the fill; a 1 USD fill gap), D and S scaled by price / 4000, exit at the
  close of minute 1/2/5/15. **CPI: 36 of 36 plans positive in A and in B; NFP 33 of 36**; PPI 0, RET 0, FOMC 31 %.
  D = 2, S = 8, exit at the minute's close: CPI A +0.90 R (25), B +0.51 (27); NFP A +0.38 (24), B +1.15 (27).
  With a 2 USD gap: CPI +0.69 / +0.43, NFP +0.08 / +0.85; a 3 USD gap (= 6.7 at 4000 in A) breaks A.
- Ticks, design (8 CPI/NFP releases), D = 2, S = 8, exit at +60 s: +1.14 R, +88.9 USD (24.2, -10.9, 0.5, 1.2,
  -2.6, 7.3, 49.0, 20.2); exit at +300 s +0.73 R, +900 s +0.49 R; the opposite side's average with ours +0.24.
  D = 1 was hit once by a pre-release tick 0.11 s after 08:30:00 on the wrong side (2026-02-11): D = 2 avoids it.
- The trend agent's suggestion (FOMC / PCE follow, CPI fade after a big first minute, 1-3 h with a 1 R trail, H1
  agreement; `trend_suggestion.py`): fails on A (PCE -0.56 R, FOMC -0.15), CPI fade fails on B (-0.26); with H1
  agreement 4-12 trades a cell, signs flip between A and B. Not taken to the test.

## FROZEN RULE S2 (written 2026-10-17 before its test)

**S2 - the CPI / NFP release-minute straddle:**
- Days: CPI and NFP releases (BLS calendar, `us_releases.csv`), 08:30:00 ET.
- At 08:30:00 ET (the last tick before it): a buy stop at ask + 2 x (price / 4000) USD and a sell stop at bid -
  2 x (price / 4000) USD, one cancels the other, live until 08:30:59. Neither filled: no trade.
- Stop: 8 x (price / 4000) USD from the fill (filled at market, gaps included). No target.
- Exit at market at 08:31:00 ET (60 s after the release) if not stopped.
- Test on ticks (`s2_ticks.py --test --d 2 --hold 60`), cross-checked on M1 (`straddle_m1.py --test`, D 2, S 8,
  hold 1). Declared variant (reported, not the verdict): S2_h300 (exit at +300 s).
- Losers' kinds against a 5 USD target (the owner's minimum) within the ticks' 15 minutes.

The test window holds CPI 2026-03-11, 04-10, 05-12, 06-10, 07-14, 08-12, 09-11 and NFP 03-06, 04-03, 05-08,
06-05, 07-02, 08-07, 09-04, 10-02 (CPI 10-14 at 12:30 UTC is after the data's end): up to 15 trades.

## Test of S2 (run once, 2026-10-17)

14 trades (NFP 2026-04-03 was Good Friday: no ticks). Ticks, D = 2, S = 8, exit at +60 s:

| Month | Trades | USD (0.01 lot) |
|---|---|---|
| 2026-03 | 2 | +13.0 (NFP +19.5, CPI -6.5) |
| 2026-04 | 1 | +10.7 |
| 2026-05 | 2 | -8.9 (NFP -2.3, CPI -6.6) |
| 2026-06 | 2 | +30.7 |
| 2026-07 | 2 | +100.8 (NFP +44.6, CPI +56.2) |
| 2026-08 | 2 | +11.9 (NFP +22.4, CPI -10.6 stop) |
| 2026-09 | 2 | -26.2 (NFP +8.7, CPI -34.9: the stop gapped 26 USD past its level) |
| 2026-10 | 1 | +12.0 |
| **All** | **14** | **+144.1; +10.29 a trade; 64 % positive; +1.23 R (nominal stop); 6 of 8 months positive** |

- The opposite side on the same ticks: -0.08 R (ours +1.23). Losers' kinds: ours 2 stopped, both kind 3 (the 5 USD
  target was reached after the stop - whipsaws); the opposite side 67/33/0 (wrong way).
- Exit at +300 s (declared variant): +167.8 USD, +1.44 R, same months positive/negative.
- M1 cross-check (worst-case ordering, 1 USD gap): +255.5 USD, 9 of 14 positive (5 counted as whipsaw losses).
- Hand-checked on ticks: 2026-07-14 (buy filled 0.44 s at 4032.99, 4090.4 at +60 s), 2026-09-04 (the feed froze
  8 s and reopened 61 USD lower: the sell stop filled 59 USD past its level, still +8.7), 2026-09-11 (buy at 1.05 s,
  the release then reversed through the stop with a gap: -34.9).
- History on M1 (worst case): CPI + NFP 2021-09 .. 2026-02 positive in 8 of 10 half-years (2021H2 -0.14 R,
  2022H1 -0.16, then +2.35, +0.63, +0.04, +1.41, +0.52, +0.36, +0.76, +2.15); months positive A 14/25, B 23/28.

Caveats: (1) the tick feed shows a flat 0.39 spread through every release - a real account's spread and stop-order
fills at the release second may be worse; each extra 1 USD of slippage a side costs ~0.2 R a trade. (2) The tails
are fat in both directions: stop exits gapped up to 4 R. (3) 14 test trades.

## Combined news weapon (P1 + S2) on the test window

| Month | P1 | S2 | Both |
|---|---|---|---|
| 2026-03 | +59.3 | +13.0 | +72.3 |
| 2026-04 | -13.6 | +10.7 | -2.9 |
| 2026-05 | - | -8.9 | -8.9 |
| 2026-06 | -33.8 | +30.7 | -3.1 |
| 2026-07 | -14.8 | +100.8 | +86.0 |
| 2026-08 | - | +11.9 | +11.9 |
| 2026-09 | +25.6 | -26.2 | -0.6 |
| 2026-10 (to the 14th) | - | +12.0 | +12.0 |
| All | 5 trades, +22.6, +0.77 R | 14, +144.1, +1.23 R | 19, +166.7, +1.11 R; 4 of 8 months positive |

About 2.4 trades a month (S2 two, P1 0.6). S2 alone: 6 of 8 months positive.

## Verdict and next (2026-10-17)

- S2 (the CPI / NFP release-minute straddle) is the first rule in this research with a mechanical cause (the data
  surprise moves gold in the first minute; a straddle does not have to guess the side) that was positive on
  2021-2026 M1 history under a worst-case ordering, on the design ticks, and on the one test (+1.23 R, 6 of 8
  months). Its open risk is execution at the release second, not direction.
- P1 (the presser follow) is consistent in design (every one of 108 neighbouring plans positive in both
  2021-23 and 2023-26) but its test has five trades (+0.77 R, 2 of 5 positive): unproven either way.
- Not kept: the 08:30 releases' direction after the first minute (follow or fade: coin-like on 2021-23 vs
  2023-26), the minutes, retail sales, PPI, the FOMC statement minute, round 10b's FOMC/PCE continue - CPI reverse
  (flips on 2021-23), and the trend agent's trailing + H1 version of it.
- Next: (1) the same straddle on other first-tier releases where the first minute has a surprise (PPI and retail
  sales failed on M1; try the ISM / JOLTS 10:00 releases if an official dated source is found); (2) D and the exit
  second chosen on ticks once more releases have ticks (only 8 design releases now); (3) ECB press conferences as
  an out-of-family test of P1 (the ECB site did not give historical dates to WebFetch).

## Step 5 - the frozen rules on the USD majors (owner, 2026-10-17; `fx.py`)

Translated before any FX number was computed (fx.py docstring): S2's D / S / gap scale by the pair's median daily
range over gold's (2023-11 .. 2026-02, gold at 4000 = 48.7 USD): EURUSD D 2.3 / S 9.2 / gap 1.1 pips, GBPUSD
2.9 / 11.6 / 1.5, USDJPY 4.4 / 17.6 / 2.2, AUDUSD 1.9 / 7.6 / 1.0, USDCHF 2.0 / 7.9 / 1.0, USDCAD 2.3 / 9.0 / 1.1,
NZDUSD 1.8 / 7.1 / 0.9. P1 unchanged (unit-free). Costs: the bar's spread + 0.2 pip a side. M1 only (no FX
ticks), S2 with the worst-case ordering. FX M1 starts 2023-09, so: B = 2023-11 .. 2026-02 (never fitted on FX),
T = 2026-03-01 .. 10-14.

| Rule | Pair | B trades | B R/trade | B pips/trade | T trades | T R/trade | T pips/trade | T positive |
|---|---|---|---|---|---|---|---|---|
| S2 | EURUSD | 54 | +1.55 | +14.5 | 15 | +0.85 | +7.9 | 60 % |
| S2 | GBPUSD | 54 | +1.45 | +17.2 | 15 | +0.73 | +8.7 | 67 % |
| S2 | USDJPY | 54 | +1.14 | +20.4 | 15 | +0.58 | +10.3 | 60 % |
| S2 | AUDUSD | 54 | +1.28 | +10.0 | 15 | +0.93 | +7.3 | 60 % |
| S2 | USDCHF | 54 | +1.35 | +10.9 | 15 | +0.90 | +7.4 | 60 % |
| S2 | USDCAD | 54 | +0.85 | +7.8 | 15 | +0.85 | +7.8 | 47 % |
| S2 | NZDUSD | 54 | +1.11 | +8.1 | 15 | +0.72 | +5.2 | 60 % |
| P1 | 7 pairs pooled | 133 | +0.11 (opposite side -0.22) | | 35 | +0.76 (opposite -0.33) | | 49 % |

- S2 is positive on every major in both periods; test months (R summed over the seven pairs): 03 -0.4, 04 +2.2,
  05 -4.4, 06 +4.4, 07 +30.6, 08 +14.4, 09 +27.8, 10 +8.7 (6 of 8). The seven pairs are one USD bet per release,
  not seven independent ones.
- The M1 spread column does not widen at the release bar (EURUSD 0.8 pip, as on any minute); a real release
  second is wider. Fill-gap sensitivity (EURUSD B / T): 1.1 pips +1.55 / +0.85 R, 3.4 pips +1.39 / +0.67, 5.7 pips
  +0.12 / -0.33 (USDJPY 6.6 pips +0.99 / +0.37; AUDUSD 2.9 pips +1.11 / +0.27). So the edge holds to a ~3-pip
  extra cost on the majors and is gone by ~5-6 pips.
- P1 on FX: in B it picks the side better than the opposite on 6 of 7 pairs, but only USDJPY (+0.64 R) and
  USDCHF (+0.57) are clearly positive; AUDUSD and USDCAD lose (-0.25, -0.26).

## Trade journal - the test trades' charts (`charts.py`, charts/s2_test.png, charts/p1_test.png)

S2 (gold ticks, -20 s .. +180 s):
- Winners (03-06, 04-10, 06-10, 07-02, 07-14, 08-07, 10-02 NFP/CPI) look alike: one clean jump in the first 1-2
  seconds, no tick back through the trigger, the trend running 20-60 s. On 07-02, 07-14, 08-07 the move kept going
  to +180 s; the +60 s exit left money there (the declared +300 s variant: +168 vs +144 USD).
- Losers: 03-11 and 05-12 CPI - a small first impulse (3-5 USD) that hit the 2-USD trigger and faded; 08-12 CPI -
  up 12 USD then a 50-USD reversal inside 10 s; 09-11 CPI - a 1-second up tick, then the feed jumped 40 USD lower
  (the stop filled 26 USD past its level). Four of the five losers are CPI (the fifth, NFP 05-08, -2.3): in 2026 the CPI first tick was twice a fake
  (two-sided release). NFP in the test: 7 trades, 6 positive, +110 USD; CPI 7 trades, 3 positive, +34 USD.
  History does not single CPI out (M1 worst case: CPI A +0.90 / B +0.51, NFP +0.38 / +1.15), so no rule change
  from seven trades.
- Idea to design (on pre-2026-03 data only, not yet done): a confirmation - a fill only when the first 2-3 seconds
  hold beyond the trigger (the losers' first impulse was small or flipped within seconds).

P1 (gold M1, 14:00 .. 17:00 ET):
- Winners 03-18 and 09-16: the presser's first ten minutes continued the statement's direction (both down) and the
  afternoon trended. Losers 04-29, 06-17, 07-29: the first ten minutes bounced against a large statement move, or
  (07-29) ran on and then reversed 60 USD.
- The eye's lesson "follow only when the presser agrees with the statement" is **wrong on the design data**:
  2021-26, agreeing 16 trades +0.56 R, disagreeing 19 +1.74 R (A 0.58 vs 0.99; B 0.54 vs 2.57). Five charts are
  not a sample; the rule stays as frozen.
