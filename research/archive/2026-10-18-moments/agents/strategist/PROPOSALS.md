# Row 60 - larger-time-frame trades for the CALM gold - written before computing (2026-10-21 12:54 Thai, `date -u` 05:54)

**The protocol is row 58's:**
- LEARN 2021-09-01 .. 2023-09-30 freezes the settings into `lt60_frozen.json`; TEST 2023-10-01 .. 2025-09-30 is read
  once;
- calm trades only (vol16_old's H1 ATR < 12 at the decision);
- the ticks from `D:/taa-data`; the spread only, slippage 0;
- the bars are MT5's own D1 / H4 / H1 (`gold.bars`), each used only from the next bar's open;
- **the pass:** TEST >= +0.10 on >= 60 trades with the 95 % range above 0, and LEARN >= +0.10;
- 3 candidates x 3 settings = 9.

**The trade:**
- The entry is at the first tick at / after the deciding bar's close (within 5 minutes).
- **A new simulator, `lsim`,** holds through the daily break and the weekend (tsim exits at a 30-minute gap):
  - the stop at the first tick at / beyond it, filled at that tick (gaps included);
  - the target as a limit at its level;
  - the time exit at the last tick before the time limit;
  - R = pnl / the stop distance.
- **The D1 trend** = the sign of (the last complete D1 close - the D1 close 20 bars before it).
- One trade per candidate per server day: the first signal. Each trade is taken alone.

**The candidates:**
1. **PDB, the previous day's break held:**
   - On server day d, the first H1 close above the previous server day's high (in an up trend), or below its low (in
     a down trend).
   - Stop distance = max(the entry - the H1 bar's low, 10 USD) for a buy; mirrored for a sell.
   - Time limit: the end of the next trading day (the next day's close).
   - Settings: target 1.5 R / 2 R / none.
2. **H4PB, the H4 pullback to a level everyone sees, in the D1 trend:**
   - The levels: PDH, PDL and the week's open (the first H1 open of the server week).
   - In an up trend, an H4 bar that opens above a level, trades down to it and closes back above it -> buy. Mirrored
     in a down trend.
   - Stop distance = max(the entry - the H4 bar's low, 10 USD).
   - Time limit: 48 hours.
   - Settings: target 1.5 R / 2 R / none.
3. **DON20, the 20-day high / low break:**
   - The first H1 close above the highest high (or below the lowest low) of the last 20 complete D1 bars.
   - Stop distance = max(1.0 x the D1 ATR(14), 10 USD).
   - Time limit: 48 hours.
   - Settings: target 1 R / 2 R / none.
# Row 60 - the results (LEARN 12:55-12:56 Thai, frozen; TEST read once 12:57-12:59 Thai)

**How it was checked:**
- **`lsim`** (the long-hold tick simulator) and the guard: `test_lt60.py`, 10 hand-worked tests.
  - The checks: the buy target and stop; the sell priced on the ask; the time exit at the last tick before the limit;
    no exit at a weekend gap, and a gap filled at the gapped price; a late fill refused; the trend exactly 20 D1 bars
    back; a bar complete at min(the next open, its open + its period); TEST needs the frozen file; no tick day at /
    after the phase end; the choice uses calm trades.
- **Planted bugs:** 11 of 11 caught (`out_plant_lt60.txt`), after three tests were added for the first-round misses:
  the late-fill check, the trend's bar count, and the end-day refusal.
- **The order:** LEARN wrote `lt60_frozen.json` before TEST ran. TEST printed only the frozen cells.
- Nothing from 2026-04-18 on was read: TEST ends 2025-09-30.

## LEARN (2021-09 .. 2023-09, calm trades; `out_lt60_learn.txt`)

| Candidate | Trades | Target 1.5 R (1 R for DON20) | Target 2 R | Time only | Median stop (USD) |
|---|---|---|---|---|---|
| PDB | 248 | **-0.162** | -0.184 | -0.222 | 10.0 |
| H4PB | 254 | -0.163 | -0.165 | **-0.124** | 10.0 |
| DON20 | 117 | -0.140 | **-0.131** | -0.150 | 23.5 |

Every cell is negative. The frozen cells are in bold.

## TEST, read once (2023-10 .. 2025-09; `out_lt60_test.txt`)

| Frozen cell | LEARN | TEST trades | TEST R (95 % range) | 2023-24 | 2024-25 | USD at 0.01 lot | Verdict |
|---|---|---|---|---|---|---|---|
| PDB, target 1.5 R | -0.162 | 204 | +0.064 (-0.100 .. +0.224) | +0.024 | +0.103 | +197.7 | FAIL |
| H4PB, time only | -0.124 | 200 | **+0.265 (+0.012 .. +0.526)** | +0.150 | +0.405 | +661.0 | FAIL (LEARN < +0.10) |
| DON20, target 2 R | -0.131 | 95 | **+0.228 (+0.071 .. +0.394)** | +0.246 | +0.213 | +622.5 | FAIL (LEARN < +0.10) |

**By the pass line, all three FAIL:** LEARN is negative for each. H4PB and DON20 pass every TEST condition.

## Why the sign flipped: the side (`lt60_sides.py`, descriptive, after the TEST read; `out_lt60_sides.txt`)

| Cell | LEARN buys | LEARN sells | TEST buys | TEST sells |
|---|---|---|---|---|
| PDB | 125, -0.111 | 123, -0.214 | 168, +0.153 | 36, -0.353 |
| H4PB | 132, -0.173 | 122, -0.072 | 150, +0.374 | 50, -0.063 |
| DON20 | 61, -0.172 | 56, -0.086 | 83, +0.262 | 12, -0.001 |

- **The TEST profit is the buys of 2023-25.** The D1 trend was mostly up then, so most signals were buys: 168 of
  PDB's 204, 150 of H4PB's 200, 83 of DON20's 95.
- **The sells lost or were flat in both halves.**
- **In LEARN (2021-23), with buys and sells near even, both sides lost.**
- These larger-time-frame trend trades are therefore not a calm-gold tool. They are a **trending-gold** tool. They paid
  when the D1 trend persisted, whatever the H1 ATR, and lost when the trend kept turning.

## What it means
- **"Calm" (H1 ATR < 12) is the wrong split for these trades.** The state that matters is the D1 trend's persistence.
  It was absent in 2021-23 and present in 2023-25.
- **A candidate for the next round** (a hypothesis, not run; it would need the protocol again with a new split): gate
  DON20 / H4PB by a D1 persistence reading known at the time. For example, the 20-day efficiency or the share of the
  last 60 D1 closes above their 50-day mean.
  - LEARN on 2021-23 would have to show the gate standing aside there. A gate fitted after seeing this table needs a
    period neither half has seen. Today, that is only the exam months, which is the measurer's read.
- **For the owner, in his terms:** in quiet gold, these short trades lose both ways because the spread eats them. The
  longer trades follow the big trend, and paid only when gold trended for months (2023-25).
- **The honest summary of rows 58 and 60:** no rule found here earns in quiet, sideways gold.

## Files (row 60)
- `lt60.py` + `test_lt60.py` + `plant_lt60.py`
- `lt60_sides.py`
- `lt60_frozen.json`
- outputs: `out_lt60_learn.txt`, `out_lt60_test.txt`, `out_lt60_sides.txt`, `out_plant_lt60.txt`, `lt60_learn.parquet`,
  `lt60_test.parquet`

# Row 58 - setups for the CALM gold (H1 ATR < 12) - written before computing (2026-10-21 12:46 Thai, `date -u` 05:46)

**The data:**
- the whole-day ticks `D:/taa-data/ticks/XAUUSD`; M1 via `gold.bars(before=2025-10-01)`;
- the costs: the tick spread only, slippage 0;
- **LEARN** 2021-09-01 .. 2023-09-30 and **TEST** 2023-10-01 .. 2025-09-30;
- only trades whose H1 ATR(14) at the decision is < 12 (vol16_old's ATR: the H1 store, the last closed bar).

**The guard:** `calm58.py learn` builds events only before 2023-10-01, and writes the chosen settings to
`calm58_frozen.json`. `calm58.py test` refuses to run without that file, and reads TEST once. Every candidate is
simulated by `tsim.grid` on the ticks. Each trade is taken alone.

**The five candidates:**
1. **ORB_FADE:**
   - The events are PLAN-1's London ORB (vol16_old's loop: the range 06:00-06:14 UTC, skip if > 1.5 H, the first M1
     close beyond it 06:15-07:14).
   - Taken the OTHER way at the same tick. d = the rule's stop distance from its own fill (to the range's other side).
   - The settings: (i) stop d, target 1 d; (ii) stop d, target 0.5 d; (iii) stop 1.5 d, target 1 d. All out at 60
     minutes.
2. **STR_FADE:**
   - The events are PLAN-1's NY 08:30 straddle (`ns1_ticks.straddle`'s trigger: the reference tick before 08:30:00,
     ±2 USD, live 60 s).
   - Taken the OTHER way at the trigger tick.
   - The settings: (i) stop 8, no target, out at 08:30 + 30 min (the exact mirror); (ii) stop 8, target 8; (iii)
     stop 4, target 4.
3. **ASIA_FADE:**
   - The Asia range is the M1 high / low of 00:00-07:00 Thai (17:00-24:00 UTC of the day before).
   - In London's first hour (08:00-09:00 London time), after an M1 bar trades beyond an edge, the first M1 close back
     inside the range fades it, entered at the next tick.
   - Stop = the excursion's extreme beyond the edge + b x H, with H = the H1 ATR. Target = the range's middle. Out 60
     minutes after the entry. One trade a day (the first).
   - The settings: b = 0.1 / 0.25 / 0.5.
4. **RC_CALM** (rows 10 / 23):
   - The events are `streams.py`'s RC: the reclaim of PDH / PDL / ASH / ASL, all hours.
   - The stop as the rule (0.25 H past the break's extreme); out at 120 minutes.
   - The settings: the target 2 R (the rule) / 1 R / 0.5 R.
5. **RT_OPP_CALM** (rows 25 / 43):
   - The events are `streams.py`'s RT (the break / retest / turn), taken back into the range; all hours, out at 120
     minutes.
   - The settings: (i) stop d, target 1 d (#43); (ii) stop d, target 0.5 d; (iii) stop 1.5 d, target 1 d.

**The choice:**
- Per candidate, the setting with the best LEARN R (calm trades) is frozen; all three are reported.
- TEST is read once.
- **Pass:** TEST R >= +0.10 on >= 100 trades, with the 95 % range above 0, and LEARN >= +0.10.
- **Parity:** the ORB and straddle event loops on their own rule side (setting "same, x1, the rule's target") against
  `vol16_old.parquet` per year: LEARN years in the learn run, TEST years in the test run.
- **Settings tried:** 5 x 3 = 15.
# Row 58 - the results (LEARN 12:47-12:49 Thai, frozen; TEST read once 12:50-12:52 Thai)

**How it was checked:**
- **The guard** (`test_calm58.py`, 6 tests; `plant_calm58.py`, 8 of 8 planted bugs caught; `out_plant_calm58.txt`):
  - TEST refuses to run without the frozen file;
  - no tick day at / after the phase's end is opened (checked before any path is built);
  - the ASIA_FADE event: the close back inside, the same bar, the excursion's extreme, the hour limit;
  - the choice uses calm trades only, and the best R.
- **The parity of the rule side with `vol16_old.parquet`, per year:**
  - every year has the same trade count;
  - the ORB R differs by at most 0.002 (tsim against check_plan1.manage); the straddle R is equal.
- **The order:** LEARN wrote `calm58_frozen.json` before TEST ran. TEST's own run printed only the frozen settings.
  The other TEST settings in `out_calm58_risk.txt` were computed by the same run and are descriptive only.

## LEARN (2021-09 .. 2023-09, calm trades; `out_calm58_learn.txt`)

| Candidate | Setting | Trades | R (95 % range) | Median risk (USD) |
|---|---|---|---|---|
| ORB_FADE | i stop d, target d | 517 | -0.235 (-0.310 .. -0.162) | 2.24 |
| ORB_FADE | ii stop d, target 0.5 d | 517 | -0.210 | 2.24 |
| ORB_FADE | **iii stop 1.5 d, target d** | 517 | **-0.125** | 3.36 |
| (the ORB itself, the rule side) | | 517 | -0.178 | 2.24 |
| STR_FADE | i stop 8, no target | 181 | -0.175 | 8 |
| STR_FADE | **ii stop 8, target 8** | 181 | **-0.170** | 8 |
| STR_FADE | iii stop 4, target 4 | 181 | -0.333 | 4 |
| (the straddle itself) | | 181 | -0.016 | 8 |
| ASIA_FADE | b 0.10 / 0.25 / **0.50** | 259 | -0.277 / -0.164 / **-0.106** | 1.83 / 2.37 / 3.20 |
| RC_CALM | target 2 R / **1 R** / 0.5 R | 723 | -0.047 / **-0.044** / -0.083 | 4.10 |
| RT_OPP_CALM | i / ii / **iii** | 545 | -0.073 / -0.078 / **-0.038** | 3.63 / 3.63 / 5.45 |

The frozen settings (in bold) were the best LEARN R of each candidate. Every one is already below the LEARN line of
+0.10.

## TEST, read once (2023-10 .. 2025-09, calm trades; `out_calm58_test.txt`)

| Candidate (frozen) | LEARN | TEST trades | TEST R (95 % range) | 2023-24 | 2024-25 | USD at 0.01 lot | Verdict |
|---|---|---|---|---|---|---|---|
| ORB_FADE iii | -0.125 (517) | 468 | -0.107 (-0.166 .. -0.050) | -0.165 | -0.043 | -164.2 | FAIL |
| STR_FADE ii | -0.170 (181) | 191 | -0.101 (-0.209 .. +0.009) | -0.187 | +0.005 | -153.7 | FAIL |
| ASIA_FADE b 0.50 | -0.106 (259) | 173 | -0.159 (-0.288 .. -0.025) | -0.139 | -0.188 | -112.5 | FAIL |
| RC_CALM 1 R | -0.044 (723) | 604 | -0.127 (-0.190 .. -0.059) | -0.124 | -0.130 | -436.8 | FAIL |
| RT_OPP_CALM iii | -0.038 (545) | 442 | -0.120 (-0.184 .. -0.058) | -0.137 | -0.099 | -443.2 | FAIL |

**All five FAIL.**

## What it shows
- **In calm gold, both sides of the same event lose.**
  - The 13:00 ORB lost as a break (-0.178 in LEARN) and lost faded (-0.125 .. -0.235).
  - The straddle lost as itself (-0.016 LEARN, -0.093 TEST) and lost faded (-0.170 / -0.101).
  - So the opposite side, the wider stop and the nearer target were all tried. They change the size of the loss, not
    its sign: these events carry no direction in calm gold.
- **The trades are small against the cost.** The median risk is 1.8-5.4 USD in LEARN against a 0.2-0.3 USD spread.
  - One round trip costs about 4-17 % of R before any direction.
  - The widest stops lost least within every candidate (ORB_FADE iii, ASIA_FADE b 0.50, RT_OPP_CALM iii).
- **The fades of breaks at the levels everyone sees (RC, RT_opp) are the nearest to 0 in LEARN** (-0.044 / -0.038).
  But they lose -0.12 .. -0.13 in TEST: the same "the present only" story as rows 43-45.

## What to stop, and what is left
- **Stop:** fading or following these session-open and level events in calm gold with stops of a few USD. Five
  transformations with three settings each lost in both halves.
- **What is left for a calm-gold tool** (hypotheses only, not run):
  - **Larger time frames**, so the trade is many spreads wide. For example, H1 / H4 levels with stops of 10+ USD and
    holds of hours, where the spread is under 3 % of R.
  - **Standing aside in calm gold** as the tool itself: the measured fact is that nothing here paid. The system would
    trade VOL-16's band and the present only, and stay flat otherwise ("trades less, not never" taken to its end).
- **Question to the measurer and the owner:** is standing aside an acceptable calm-gold "tool", or should the next
  round try the larger-time-frame idea under the same LEARN / TEST protocol?

## Files (row 58)
- `calm58.py` + `test_calm58.py` + `plant_calm58.py`
- `calm58_frozen.json`
- outputs: `out_calm58_learn.txt`, `out_calm58_test.txt`, `out_calm58_risk.txt`, `out_plant_calm58.txt`,
  `calm58_learn.parquet`, `calm58_test.parquet`

# Row 57 - the walk-forward of the PROCESS (London 13:00 ORB, NY 08:30 straddle) - written before computing (2026-10-21 12:36 Thai, `date -u` 05:36)

Owner: "backtest, prove, use, and keep learning the market".

**The trades:** PLAN-1's rules on the ticks, slippage 0, every weekday 2021-09-01 .. 2026-04-17. Nothing from
2026-04-18 on is loaded.
- They are simulated by the measurer's own code: `check_plan1`'s ORB rule as in `vol16_old.py`, and
  `ns1_ticks.straddle`.
- The ticks come from `D:/taa-data/ticks/XAUUSD` before 2025-10-01 and from `data/ticks/XAUUSD` after.
- Each trade is tagged with the ATR(14) of the last closed H1 bar at its decision (vol16_old's ATR).
- **The parity checks before the folds are read:**
  - on P1 / P2: the ORB 59 / 60 at +0.214 / +0.123, the straddle 41 / 59 at +0.467 / +0.119;
  - on 2021-09 .. 2025-09: `vol16_old.parquet`'s yearly numbers.

**The folds:**
- The trading quarters start 2022-10-01, 2023-01-01, .. 2026-04-01; the last one is cut at 2026-04-17.
- Each fold chooses on the trades that **exited before** its start and **entered at / after** its start minus 12
  months, then trades its 3 months.
- No fold sees its own trading months.
- Each piece is chosen separately.

**The choices:**
- **(a) the band:**
  - The candidates are built from the quartiles q25 / q50 / q75 of the fit trades' ATR: the 4 quartile bands, the 3
    adjacent pairs, the 2 adjacent triples, and all 4. That is 10 bands.
  - The outer edges are open: the lowest band has no floor, the highest no ceiling.
  - The chosen band has the best fit R among the bands with >= 20 fit trades. A tie goes to more trades.
  - If the best is < +0.10, or no band qualifies, the piece stands aside for that quarter.
  - The band's edges are frozen as numbers for the quarter.
- **(b) VOL-16:**
  - (b1) the fixed band 12 <= ATR < 16, traded only when its fit R is >= +0.10 on >= 20 fit trades, else stand aside;
  - (b0) the band always, as a reference.
- **(c) always on.**

**Reported:**
- each fold's choice, the fit R and trades, and the out-of-sample trades and R per piece;
- the chained out-of-sample result 2022-10 .. 2026-04-17 (both pieces pooled, and per piece), with the 95 % bootstrap
  range;
- per year (Oct .. Sep).

**The pass for the process (a):** chained R >= +0.10, the 95 % range above 0, and no year below -0.10.
# Row 57 - the results (measured 2026-10-21 12:38-12:41 Thai)

**How it was checked:**
- **The trades are the measurer's rule code**, built in `wf_process.py build` (`out_wf_build.txt`). Its parity:
  - with `vol16_old.parquet`: all 10 piece-years (2020-21 .. 2024-25) have the same trades and R to 3 decimals;
  - on P1 / P2: the ORB 59 / 60 trades at +0.213 / +0.124 against the row-45 ticks' +0.214 / +0.123 (the same
    counts). The 0.001 differences come from `check_plan1.manage` against `tsim`; I did not chase them;
  - the straddle 41 / 59 at +0.467 / +0.119, equal.
- **The fold logic** (`test_wf_process.py`, 9 hand-worked tests; `plant_wf_process.py`, 11 of 11 planted bugs caught
  after one test was added for the 20-trade minimum; `out_plant_wf_process.txt`). Two of the bugs tested that a fold
  never sees its own trading months:
  - a fit trade that is still open at the start is excluded;
  - a fit window that leaks one day into its trading months is caught.
- **Nothing from 2026-04-18 on was loaded:** `gold.bars(before=)` is asserted, and the tick reader refuses exam days.

## The chained out-of-sample result, 2022-10 .. 2026-04-17 (`out_wf_process.txt`)

| Process | Pieces | Trades | R (95 % range) | USD at 0.01 lot | 2022-23 | 2023-24 | 2024-25 | 2025-26 (to 04-17) |
|---|---|---|---|---|---|---|---|---|
| **(a) the chosen band** | both | 237 | **+0.029 (-0.104 .. +0.167)** | +188.5 | -0.060 (38) | -0.287 (15) | -0.420 (12) | +0.108 (172) |
| (a) | ORB | 134 | +0.132 (-0.036 .. +0.306) | +274.4 | - | - | -0.364 (11) | +0.176 (123) |
| (a) | straddle | 103 | -0.104 (-0.314 .. +0.111) | -85.9 | -0.060 (38) | -0.287 (15) | -1.031 (1) | -0.064 (49) |
| (b1) VOL-16 when its fit qualified | both | 13 | +0.274 (-0.389 .. +1.016) | +14.6 | - | - | - | +0.274 (13) |
| (b0) VOL-16 always | both | 80 | +0.228 (+0.010 .. +0.442) | +138.4 | - | +0.111 (3) | -0.066 (33) | +0.457 (44) |
| (c) always on | both | 1300 | -0.036 (-0.092 .. +0.019) | +128.5 | -0.099 (346) | -0.094 (356) | -0.055 (360) | +0.174 (238) |

**The pass for the process (a): FAIL.**
- The chained R is +0.029 (the line: >= +0.10).
- The 95 % range starts at -0.104 (the line: above 0).
- The worst year is 2024-25 at -0.420 on 12 trades (the line: no year below -0.10).

**What the folds show** (each fold, `out_wf_folds.csv`):
- **The ORB process stood aside correctly for two years.** From 2022-10 to 2024-07 no band reached +0.10 on its past
  12 months. Always-on was between -0.242 and +0.068 a quarter, and negative in 6 of the 8 quarters.
- **The ORB's chosen bands then did not carry forward:**
  - from 2024-10 to 2025-07 they were the low-ATR bands (< 3.5-4.8 USD), and they took 11 trades at -0.364;
  - from 2025-10 they followed the rising ATR ([9.25, inf), then [13.52, inf)) and paid: +0.201 on 62 and +0.165 on
    56.
  - So the process followed the present one quarter late. In this period it paid only once the present had begun.
- **The straddle process lost:**
  - its winning band in the past 12 months was a narrow ATR slice of 22-39 trades (e.g. [3.12, 3.68)), and the next
    quarter did not repeat it (-0.484, -0.407, -0.261);
  - in 2026-01 it chose [16.07, inf) and lost -0.080 on 47, while always-on made +0.031 and the 12-16 band +0.818
    on 8.
- **VOL-16 used as the rule chose itself** (b1) in only 3 piece-quarters (13 trades): its band was nearly empty before
  2025 (0-3 fit trades a year).

**VOL-16 always (b0)** has +0.228 on 80, the range above 0. That band was frozen with P1 / P2 in view, and 44 of its 80
trades fall in 2025-10 .. 2026-04 (nearly all P1 / P2), so it is not out of sample here.
- Before the present it had only 36 trades (2023-25: 3 at +0.111, 33 at -0.066).
- The exam months (the measurer's row 55) are its honest read.

## What it means
1. **A 12-month band chosen on the past is not a reliable process for these two pieces.**
   - It stands aside well when nothing pays, but it picks narrow bands that do not repeat.
   - It switches on only after the present has shown itself in its own 12-month window.
2. **For the ORB, (a)'s value was almost all in 2025-10 .. 2026-04** (+0.176 on 123). That is the same present-only
   edge as before.
3. **The straddle has no band its past 12 months can find.** Its present edge (+0.209 always-on in 2025-26) is not
   reached by choosing on ATR.
4. **A next try, not run:** a process with fewer, wider choices may hold better than narrow slices of 22-39 trades.
   For example: on, or stand aside, by the piece's own last-12-month R. That is SW-type persistence at the quarter
   scale, and it should be written before it is computed.

## Files (row 57)
- `wf_process.py` + `test_wf_process.py` + `plant_wf_process.py`
- outputs: `out_wf_build.txt`, `out_wf_process.txt`, `out_wf_folds.csv`, `out_plant_wf_process.txt`,
  `wf_trades.parquet`, `wf_oos.parquet`

# Exam runner for #43 RT_opp and #23 RC_win - built 2026-10-21 11:44-11:48 Thai (`date -u` 04:44-04:48)

`exam43.py` writes the frozen definitions at its top.
- The default reads the learning parts only. `--exam` (THE MEASURER ONLY) reads 2026-04-18 .. 2026-10-17.
- I have not run `--exam`, and no exam data was loaded. The guard is tested with fake readers only.

**With the switch off, the learning results reproduce `states_events.parquet` (row 45) trade for trade on the ticks:**
- RT_opp: 41 / 46 trades, the same entries, max |dR| 0;
- RC_win: 19 / 22 trades, the same entries, max |dR| 0.

| Stream | Part | Trades | R | Win | USD at 0.01 lot | Worst | Losing streak | Max DD (USD) |
|---|---|---|---|---|---|---|---|---|
| RT_opp | P1 | 41 | +0.261 | 0.71 | +188.31 | -18.58 | 2 | 36.85 |
| RT_opp | P2 | 46 | +0.255 | 0.67 | +436.42 | -92.37 | 3 | 107.34 |
| RC_win | P1 | 19 | +0.311 | 0.58 | +59.26 | -19.69 | 4 | 66.37 |
| RC_win | P2 | 22 | +0.313 | 0.50 | +312.91 | -35.13 | 3 | 53.81 |

The week-by-week table is in `out_exam43_learn.txt`. Tests: `test_exam43.py`, 10 pass. Planted bugs:
`plant_exam43.py`, 13 of 13 caught after one test was added (the exit-order sort).

# Row 52 - do the leads pay while gold-ETF holdings grow? - written before computing (2026-10-20 19:37 Thai, `date -u` 12:37)

**Data** (public; downloaded read-only into `strategist/etf/` at 19:35-19:38 Thai):
- the SPDR Gold Shares (GLD) historical archive:
  `https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en`, daily "Tonnes of Gold",
  2004-11-18 .. 2026-10-19;
- the SPDR Gold MiniShares (GLDM) archive (`product=gldm`), 2018-06-26 .. 2026-10-19;
- iShares IAU is not used: its site gives no plain historical file.
- The venv has no openpyxl, so the .xlsx files are read by a stdlib reader (`xlsx_min.py`, tested).

**The series:** the daily tonnes of GLD + GLDM (the sum on the dates both report). Holdings of day D are taken as
public only from the **next weekday after D at 16:00 New York**. That is a full day later than the file's date, the
cautious side. The task's "the next day" is met or exceeded.

**The readings** (each the latest value public before the entry; a "day" is a reporting day of the series):

| # | Reading | Definition |
|---|---|---|
| 1 | ch20 | tonnes / tonnes 20 days earlier - 1 |
| 2 | ch60 | tonnes / tonnes 60 days earlier - 1 |
| 3 | up20 | the number of days among the last 20 whose tonnes rose from the day before |
| 4 | vs52 | tonnes / the highest tonnes of the last 260 days (this one included) - 1 |

**Protocol** (as rows 50-51):
- Every reading is "on" when higher.
- The forms: monthly (the value known at the start of the month) and rolling (known at the entry).
- The threshold is chosen on the trades before 2026-01-16 (the summed R of ORB + RC_win + RT_opp,
  `regime50_trades.parquet`) and read once on P2.
- Reported: the month table; April-May 2025 against 2025-11 .. 2026-04; the public holdings after 2026-04, described
  only.
- Then one combined note (size + ETF + positioning) and a recommended monitor.
# Row 52 - the results (measured 2026-10-20 19:39-19:40 Thai)

**Sources** (downloaded 19:35-19:38 Thai into `strategist/etf/`):
- the GLD archive, `https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en`, linked
  as "Historical Archive (XLSX)" on `https://www.spdrgoldshares.com/usa/historical-data/`: 5,512 days,
  2004-11-18 .. 2026-10-19;
- the GLDM archive (`product=gldm`): 2018-06-26 .. 2026-10-19;
- joined from 2019-06: 1,856 days.
- iShares IAU is not used: no plain historical file was found.

**How it was checked** (`test_etf52.py`, 5 tests; `plant_etf52.py`, 10 of 10 planted bugs caught after one test was
added for a 19-day shift that a flat series hid; `out_plant_etf52.txt`):
- the publication time (the next weekday, 16:00 New York, in winter and summer, Friday to Monday);
- ch20 exactly 20 days back;
- up20 with a missing first difference;
- vs52 including the day itself, with a minimum history;
- the stdlib xlsx reader: shared strings, empty cells, cell positions.

The run asserts that the publication times rise.

## Month by month: GLD + GLDM holdings known at the start of each month (`out_etf52.txt`)

| Month | Tonnes | 20-day change | 60-day change | Up-days of 20 | vs 52-week high | Leads R (trades) |
|---|---|---|---|---|---|---|
| 2022-04 / 05 | 1174.5 / 1183.4 | +0.045 / +0.008 | +0.118 / +0.084 | 14 / 9 | -0.001 / -0.009 | -0.093 / -0.105 |
| 2024-09 .. 11 | 965-1000 | +0.016 .. +0.019 | +0.037 .. +0.053 | 11 | -0.022 .. -0.004 | -0.017 / +0.045 / +0.010 |
| 2025-03 | 1023.5 | +0.048 | +0.038 | 14 | -0.001 | -0.402 (47) |
| **2025-04** | 1064.0 | +0.040 | +0.084 | 15 | 0.000 | -0.001 (45) |
| **2025-05** | 1084.8 | +0.018 | +0.111 | 10 | -0.011 | -0.062 (40) |
| 2025-07 .. 09 | 1103-1121 | +0.008 .. +0.030 | +0.022 .. +0.041 | 8-13 | -0.002 .. -0.001 | -0.280 / -0.134 / -0.090 |
| 2025-10 | 1181.3 | +0.044 | +0.078 | 12 | 0.000 | +0.018 (45) |
| **2025-11** | 1218.0 | +0.026 | +0.104 | 11 | -0.016 | **+0.267 (38)** |
| **2025-12** | 1222.0 | +0.007 | +0.060 | 12 | -0.013 | **+0.396 (49)** |
| 2026-01 | 1254.6 | +0.022 | +0.058 | 12 | 0.000 | -0.067 (41) |
| **2026-02** | 1280.9 | +0.021 | +0.053 | 12 | -0.002 | **+0.220 (38)** |
| **2026-03** | 1299.6 | +0.012 | +0.064 | 11 | 0.000 | **+0.331 (45)** |
| **2026-04** | 1246.0 | -0.044 | -0.006 | 4 | -0.044 | **+0.274 (22)** |

- The ETF holdings did grow through the paying stretch: 1120.9 t at the start of 2025-09, 1299.6 t at the start of
  2026-03 (+16 %).
- **But the same inflows came before, with losing leads:**
  - 2022-04 / 05: 60-day change +0.118 / +0.084;
  - 2025-03 .. 05: 20-day change +0.048 / +0.040, 60-day change up to +0.111, 14-15 up-days of 20.
- **And April 2026 paid (+0.274) while the holdings fell:** 20-day change -0.044, 4 up-days of 20.

## The switches (on when higher; chosen on 2021-09 .. P1; read once on P2; always on, P2: 128 trades, +0.203, summed +26.0)

| Reading, form | On when | 2021-09 .. 2025-09: on, summed R | Share on 2025-04 / 05 | Share on 2025-10 .. 2026-04 | P2: on, R, summed |
|---|---|---|---|---|---|
| ch20, monthly / rolling | > 0.048 / > 0.068 | 0 (never on) | 0 / 0 | all 0 | 0 |
| **ch60, monthly** | > 0.0497 | 280, -9.0 | **1.00 / 1.00** | 1, 1, 1, 1, 1, 1, 0 | 106, +0.189, +20.0 |
| ch60, rolling | > 0.0409 | 434, -28.0 | 1.00 / 0.60 | 1, 1, 1, 0.68, 1, 0.24, 0 | 60, +0.166, +10.0 |
| up20, monthly / rolling | > 15 / > 16 | 0 (never on) | 0 / 0 | all 0 | 0 |
| vs52, monthly | > -0.0006 | 45, -0.0 | 1.00 / 0 | 1, 0, 0, 1, 0, 1, 0 | 68, +0.171, +11.6 |
| vs52, rolling | > 0 | 0 (never on) | 0 / 0 | all 0 | 0 |

**The ETF holdings do not separate April-May 2025 from the present.** The one switch that is on in the present (ch60
monthly) is also on in April-May 2025. It lost -9.0 R on 280 trades in 2021-09 .. 2025-09, and on P2 it does not beat
always-on.

## The public holdings after the learning data (month ends; described only, no price data of ours)

| Month end | 2026-03 | 2026-04 | 2026-05 | 2026-06 | 2026-07 | 2026-08 | 2026-09 | 2026-10 (to the 19th) |
|---|---|---|---|---|---|---|---|---|
| Tonnes | 1247.2 | 1245.1 | 1240.3 | 1215.7 | 1218.4 | 1265.9 | 1284.4 | 1292.4 |
| 60-day change | -0.000 | -0.027 | -0.033 | -0.028 | -0.020 | +0.024 | +0.059 | +0.059 |

Outflows ran from 2026-03 to 2026-07, and inflows from 2026-08 (back to 0.8 % below the 52-week high).

# The combined note: what the facts say about why the present pays (rows 45-52)

| What was measured | April-May 2025 (leads -0.001 / -0.062) | 2025-11 .. 2026-04 (leads +0.22 .. +0.40, except 2026-01 -0.067) | Separates them? |
|---|---|---|---|
| Size: daily range / H1 ATR / NY 30+ share (row 50) | 73.8-75.9 / 12.8-16.3 / 0.36-0.76 | 67-157 / 15-32 / 0.80-1.00 | only by a hair (the fitted lines sit on April-May 2025's values) |
| Speculative futures length: managed money (row 51) | 175k -> 121k, percentile 0.48 -> 0.02 | 92k-160k and falling, percentile 0.02-0.48 | no (low in both) |
| ETF holdings: GLD + GLDM (row 52) | strong inflows (60-day +0.084 / +0.111) | inflows to 2026-03, outflows in 2026-04 | no (inflows in both) |
| The trend efficiency, the release jump (row 50) | - | - | no |
| The stream's own recent result, SW-20 (rows 45 / 47) | on for 1-42 % of the O1 / O2 events | on for 70-100 % of the P1 / P2 events | yes, after about 20 trades; it failed the 2021-23 test alone (row 47) |

**What the facts say:**
1. **The present pays in a large gold**, and every paying month was large. But large is not enough: April-May 2025 was
   as large and did not pay.
2. **No outside flow reading tells the two apart.**
   - Speculative length fell in both.
   - ETF holdings rose in both, and fell in April 2026, which paid.
   - So the "persistent flow" story, as measured by COT managed money and the two SPDR ETFs, does not explain why the
     leads pay now.
3. **The one difference the data shows is persistence:**
   - in 2025, the size came as one shock: the H1 ATR went 16.3 (April) to 10.0 (June) and 7.1-7.8 by July-August;
   - from 2025-10 the size held for seven months in a row (H1 ATR 14.8-31.8).
   - This is an observation after the fact, not a tested reading. A "size held for N months" switch would also turn on
     late: after the first paying months.

**The recommended monitor** (none of it fitted without P1 in view; the exam months are its first honest read, which is
the measurer's):
1. **A size floor** (row 50): the 20-day share of weekdays with a 30+ USD NY move (08:30-12:30 NY) > 0.75, and the
   20-day median H1 ATR > about 11 USD. Below it the leads stand aside at once.
2. **SW-20, the stream's own shadow result:** above the floor, trade a lead only while its last 20 paper trades pay.
   This catches a change of character at the same size, such as April-May 2025.
3. **Logged as context, not used to gate:**
   - the ETF 60-day change and managed-money length;
   - neither separated the paying months, but both are public, cheap, and could show a new kind of market.

**Today, from public figures only:**
- ETF holdings are rising again (1292.4 t, 60-day change +5.9 %).
- Managed money is falling (107.1k, percentile 0.46).
- Neither changes the monitor's verdict, which needs the size readings of the exam months, and I do not load those.

## Files (row 52)
- `etf52.py` + `test_etf52.py` + `plant_etf52.py`
- `xlsx_min.py` (the stdlib xlsx reader, tested in `test_etf52.py`)
- the archives: `etf/gld_archive.xlsx`, `etf/gldm_archive.xlsx`
- outputs: `out_etf52.txt`, `out_etf52_switch.csv`, `out_etf52_daily.csv`, `out_plant_etf52.txt`,
  `etf52_trades.parquet`

# Row 51 - do the leads pay while a persistent speculative flow drives gold? - written before computing (2026-10-20 19:30 Thai, `date -u` 12:30)

**Data** (public; downloaded read-only into `strategist/cftc/`):
- The CFTC disaggregated futures-only Commitments of Traders, COMEX gold (code 088691), 2020-2026
  (`https://www.cftc.gov/files/dea/history/fut_disagg_txt_YYYY.zip`). The columns used: managed money long / short,
  and the open interest.
- **When each report is known:**
  - Normally: the Friday of the report's week, 15:30 New York time.
  - When a US federal holiday falls between the report date and that Friday, or on the Friday: the next Monday,
    15:30 New York time. The CFTC 2026 schedule shows exactly these Monday releases ("delayed release date due to a
    federal holiday").
  - The executive closures of 2024-12-24, 2025-12-24 and 2025-12-26 count as holidays, which is the cautious side.
  - **The 2025 shutdown:** the reports of 2025-09-30 .. 2026-01-13 use the "new publish date" of CFTC press release
    9138-25 (`cftc/pr_9138-25.html`). For example, the 2025-09-30 report became known on 2025-11-19, and the
    2025-12-16 report on 2026-01-06. Where another notice gave an earlier date, the later one is used.
- Gold's price comes from our M1 / D1 store, 2021-09 .. 2026-04-17 only. The positioning after that is described from
  the CFTC file alone; our exam-period prices are not loaded.

**The readings** (each the latest value published before the entry):

| # | Reading | Definition |
|---|---|---|
| 1 | mm_net | managed money long - short (contracts) |
| 2 | mm_oi | mm_net / the open interest |
| 3 | d4 | mm_net minus mm_net 4 reports earlier |
| 4 | d13 | mm_net minus mm_net 13 reports earlier |
| 5 | pct52 | mm_net's percentile among the last 52 reports, this one included; >= 26 reports |
| 6 | dist52 | the last complete D1 close / the highest D1 high of the 260 D1 bars up to it, minus 1 (0 = at the 52-week high) |

**Protocol** (as row 50):
- Every reading is "on" when higher (> the threshold).
- **Monthly form:** the value known at the end of the previous calendar month. **Rolling form:** the value known at
  the entry.
- The threshold is chosen on the trades before 2026-01-16 to maximise the summed R of the three leads (ORB + RC_win +
  RT_opp; `regime50_trades.parquet`); a tie goes to the lowest threshold. It is read once on P2.
- Reported: the month table; whether each switch separates April-May 2025 (off) from 2025-11 .. 2026-04 (on); and the
  public positioning in 2026-08 .. 10, described only.
- Caveat: P1 is inside the fit, as in row 50.
# Row 51 - the results (measured 2026-10-20 19:31-19:33 Thai)

**Sources:**
- The CFTC historical disaggregated futures files, `https://www.cftc.gov/files/dea/history/fut_disagg_txt_2020.zip`
  .. `_2026.zip`, downloaded 2026-10-20 19:27-19:29 Thai into `strategist/cftc/`. COMEX gold is code 088691; there are
  354 weekly reports, 2020-01-07 .. 2026-10-13.
- CFTC press release 9138-25 (`https://www.cftc.gov/PressRoom/PressReleases/9138-25`, saved as
  `cftc/pr_9138-25.html`): the post-shutdown publish dates.
- The CFTC 2026 release schedule (`https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm`):
  Monday releases in federal-holiday weeks.

**How the alignment was checked** (`test_cot51.py`, 5 hand-worked tests; `plant_cot51.py`, 9 of 9 planted bugs caught,
`out_plant_cot51.txt`):
- the Friday 15:30 New York release in summer and in winter time;
- the holiday weeks moved to Monday (Thanksgiving 2024; Juneteenth 2026, as the CFTC schedule shows);
- the shutdown table (the 2025-09-30 report known on 2025-11-19, the 2025-12-16 one on 2026-01-06);
- a value is used only once published (published at exactly t counts; the next one does not);
- the 52-report percentile.

The bugs caught: the shutdown table ignored; holidays ignored; known on the report's Tuesday; 15:30 dropped; 15:30 read
as UTC; one report ahead; a report published at t excluded; `<` for `<=`; the current report left out of its own
percentile.

**The run also checks:**
- the publication times rise strictly with the report dates;
- 40 reports were published more than 6 days after their date: the holiday weeks and the 17 shutdown reports.

## Month by month: positioning known at the start of each month (`out_cot51.txt`)

The managed-money net long (contracts) and its 52-report percentile, with the three leads:

| Month | MM net | Net / OI | 4-wk change | 13-wk change | Percentile 52 | Gold vs its 52-wk high | Leads R (trades) |
|---|---|---|---|---|---|---|---|
| 2024-09 | 200,291 | 0.384 | +47,927 | +51,463 | 1.00 | -0.004 | -0.017 (53) |
| 2024-10 | 219,029 | 0.388 | +18,738 | +60,827 | 1.00 | -0.019 | +0.045 (54) |
| 2025-02 | 210,540 | 0.365 | +44,371 | +15,367 | 0.92 | -0.002 | -0.290 (48) |
| 2025-03 | 179,812 | 0.351 | -30,728 | +522 | 0.58 | -0.027 | -0.402 (47) |
| **2025-04** | 174,732 | 0.342 | -5,080 | +9,235 | 0.48 | -0.001 | -0.001 (45) |
| **2025-05** | 120,902 | 0.260 | -53,830 | -94,967 | 0.02 | -0.060 | -0.062 (40) |
| 2025-09 | 141,917 | 0.320 | +7,661 | +31,101 | 0.35 | -0.015 | -0.090 (50) |
| 2025-10 | 160,549 | 0.304 | +18,632 | +35,421 | 0.48 | -0.003 | +0.018 (45) |
| **2025-11** | 160,549 (the shutdown: no new report known) | 0.304 | +18,632 | +35,421 | 0.48 | -0.081 | **+0.267 (38)** |
| **2025-12** | 108,310 | 0.223 | -50,661 | -28,417 | 0.10 | -0.036 | **+0.396 (49)** |
| 2026-01 | 123,548 | 0.286 | +19,461 | -39,971 | 0.29 | -0.046 | -0.067 (41) |
| **2026-02** | 118,159 | 0.242 | -7,881 | +14,000 | 0.25 | -0.039 | **+0.220 (38)** |
| **2026-03** | 95,974 | 0.228 | -22,185 | -13,335 | 0.10 | -0.074 | **+0.331 (45)** |
| **2026-04** | 91,621 | 0.227 | -4,353 | -44,649 | 0.02 | -0.167 | **+0.274 (22)** |

**The finding is the opposite of the hypothesis.** While the leads paid (2025-11 .. 2026-04), managed money was net
long but **shrinking**:
- 160.5k (the 2025-09-23 report) fell to 92.2k (2025-10-21), and stayed 90-137k through P2;
- its 52-report percentile at the start of each paying month was 0.02-0.48;
- its peaks came in 2024-09 / 10 and 2025-02 (200-219k, percentile 0.92-1.00), when the leads lost or were flat.

Whatever drove gold from 2025-10 is not visible as rising managed-money (speculative futures) length. In the CFTC data,
the speculators were reducing.

## The switches (protocol of row 50; `out_cot51_switch.csv`)

**As pre-registered (on when higher):**
- **No positioning reading switches on in any month of 2025-11 .. 2026-04.** P2 has 0 trades on for every reading and
  form.
- Fitted on 2021-09 .. P1, the best was mostly "never trade". Only the MM net / net-OI peaks (2024-09 .. 11) gave
  +2.4 / +4.9 R on 54 / 46 trades.
- Gold near its 52-week high (dist52) never switches on either.

**Post-hoc, written after the month table: on when LOWER.** This is a description, not a lead:

| Reading, form | Switch on when | 2021-09 .. 2025-09: on, summed R | Share on, 2025-04 / 05 | Share on, 2025-11 .. 2026-04 | P2: on, R, summed |
|---|---|---|---|---|---|
| pct52, monthly | < 0.135 | 347, -5.5 | 0 / 1.00 | 0, 1.00, 0, 0, 1.00, 1.00 | 67, +0.312, +20.9 |
| pct52, rolling | < 0.115 | 291, +3.5 | 0.51 / 1.00 | 0.13, 0.63, 0, 0.71, 0.38, 1.00 | 66, +0.250, +16.5 |
| dist52, rolling | < -0.159 | 167, +4.7 | 0 / 0 | 0, 0, 0, 0.05, 0.33, 0.23 | 22, +0.530, +11.7 |

Low positioning was also there in May 2025 (percentile 0.02), when the leads lost. So low positioning does not separate
April-May 2025 from the present any better than size did.

## What it says about now (2026-08 .. 10; public CFTC figures only, no price data of ours)

| Report date (published) | MM net | Net / OI | 4-wk change | Percentile 52 |
|---|---|---|---|---|
| 2026-08-04 (08-07) | 130,766 | 0.352 | +14,605 | 0.77 |
| 2026-08-25 (08-28) | 144,747 | 0.338 | +24,952 | 0.90 |
| 2026-09-22 (09-25) | 127,389 | 0.309 | -17,358 | 0.75 |
| 2026-10-13 (10-16) | 107,089 | 0.270 | -26,027 | 0.46 |

- Managed money built length from June to late August 2026 (to 144.7k, the 90th percentile of its year). Since then it
  has fallen by 37.7k in seven weeks.
- **By this study, that fall is not a regime-end signal.** The paying months had falling, low positioning. The measured
  monitors stay the size floor and SW-20 (row 50).

## What it means
- The hypothesis "the leads pay while a persistent speculative (managed-money) flow drives gold" is **contradicted** by
  the CFTC data: speculative length fell as the leads began to pay.
- The outside research names ETF inflows and other buyers. The COT managed-money series cannot stand in for them. If
  the flow is to be measured, it needs an ETF-holdings series (for example the published daily GLD tonnage), aligned to
  its own publication time.
- I have not downloaded that series; it is a question for the measurer.

## Files (row 51)
- `cot51.py` + `test_cot51.py` + `plant_cot51.py`
- the CFTC data and the press release: `cftc/`
- outputs: `out_cot51.txt`, `out_cot51_switch.csv`, `out_cot51_reports.csv`, `out_plant_cot51.txt`,
  `cot51_trades.parquet`

# Row 50 - the case for "the present regime": what changed in gold around 2025-10 - written before computing (2026-10-20 19:18 Thai, `date -u` 12:18)

Measured only; no rule is built. Data: 2021-09-01 .. 2026-04-17, never later. M1 comes from `gold.bars`, with the
index cast to nanoseconds (the NS-2 unit trap). D1 is MT5's own. The release ticks come from `data/ticks_old` (release
days to 2025-09) and `data/ticks` (from 2025-10).

**The readings** (each computed per calendar month, and as a rolling value known at the start of each day):

| # | Reading | Definition |
|---|---|---|
| 1 | dr | the median D1 range (high - low, USD) |
| 2 | atr | the median MT5 ATR(14) of the H1 bars built from M1 (USD) |
| 3 | jump | on the 08:30-ET release days: the largest abs(mid - the last mid before 08:30:00) within 08:30:00 .. 08:31:00 (USD) |
| 4 | spr_atr | the median M1 spread (spread x 0.01 + 0.08) / the H1 ATR(14), over the M1 bars |
| 5 | ny30 | the share of weekdays whose M1 range from 08:30 to 12:30 New York time is >= 30 USD |
| 6 | eff | the D1 20-day efficiency (abs(the net change) / the sum of the abs daily changes), the median |

**The leads' result per trade:** ORB + RC_win + RT_opp, summed. The sources:
- 2021-09 .. 2023-10-17: `sw20_trades.parquet` (M1);
- 2023-10-18 .. 2025-10-17: `states_events.parquet` (M1);
- P1 / P2: the same file (ticks).

**The switch rule tried for each reading** ("trade the leads only while X > threshold"; "<" for spr_atr):
- **Monthly:** X of the previous complete calendar month decides every trade of this month.
- **Rolling:** X over the last 20 weekdays (the jump: the last 5 release days) up to the day before the entry.
- **The threshold** is chosen on the trades before 2026-01-16 (2021-09 .. 2025-09 + P1). The candidates are every
  value the reading took on the fit days. The score is the summed R of the switched-on fit trades. On a tie, the
  lowest threshold wins (">"), or the highest ("<").
- **It is read once on P2:** the trades switched on, their R and summed R, against always-on.
- **"In time":**
  - the first month from which the monthly switch stays on through P1;
  - the first day the rolling switch is on in 2025-09 .. 2025-12;
  - both against the month the leads started paying (2025-10).
- **Caveat, stated now:** the fit includes P1, the paying months. So the threshold is chosen knowing where the change
  came. A fit on 2021-09 .. 2025-09 alone sees no paying stretch.
# Row 50 - the results (measured 2026-10-20 19:20-19:21 Thai)

**How the numbers were checked:**
- **The helpers in `regime50.py`** (the release jump, the threshold choice, the rolling value strictly before the day):
  4 hand-worked tests pass (`test_regime50.py`).
- **Planted bugs** (`out_plant_regime50.txt`): 8 of 9 caught.
  - The miss is an equivalent mutant: letting NaN candidates into the threshold choice cannot change the choice,
    because a comparison with NaN is never on.
- **No exam data was loaded:**
  - `gold.bars(before=2026-04-18)` is asserted, and the release days at / after 2026-04-18 are skipped.
  - The M1 index is cast to nanoseconds, so the NS-2 unit trap cannot recur.
- **The leads' trades are the measured files:** `sw20_trades.parquet` (to 2023-10-17) and `states_events.parquet`
  (from 2023-10-18). Always on, P2 gives 128 trades at +0.203 R. That equals ORB 60 + RC_win 22 + RT_opp 46 from row 45.
- **Also measured:** the SW-20 switch's own planted-bug run (`out_plant_sw20.txt`) now catches 7 of 7. Three tests
  were added after the first round: fewer records than N, a missing result taking a place, and only the last N.

## Month by month (`regime50.py`, `out_regime50.txt`)

Gold's readings, and the three leads together (ORB + RC_win + RT_opp; R per trade, summed R):

| Month | Daily range | H1 ATR | 08:30 jump (days) | Spread / ATR | NY 30+ share | D1 eff20 | Trades | R | Sum |
|---|---|---|---|---|---|---|---|---|---|
| 2021-09 .. 2023-12 (28 months) | 13.9-34.5 | 2.7-6.5 | 2.1-11.0 | 0.048-0.131 | 0.00-0.18 | 0.07-0.51 | 37-58 / month | 23 of 28 months < 0 | -170.9 in all |
| 2024-01 | 19.7 | 4.1 | 7.36 (5) | 0.083 | 0.05 | 0.10 | 51 | -0.081 | -4.1 |
| 2024-04 | 40.4 | 8.1 | 6.33 (5) | 0.042 | 0.23 | 0.51 | 52 | -0.183 | -9.5 |
| 2024-08 | 34.2 | 6.3 | 7.41 (4) | 0.054 | 0.27 | 0.17 | 56 | -0.185 | -10.4 |
| 2025-01 | 29.5 | 5.7 | 6.67 (5) | 0.053 | 0.05 | 0.28 | 55 | -0.148 | -8.2 |
| 2025-02 | 41.0 | 7.7 | 5.64 (4) | 0.038 | 0.20 | 0.50 | 48 | -0.290 | -13.9 |
| 2025-03 | 35.3 | 7.2 | 5.61 (4) | 0.039 | 0.19 | 0.22 | 47 | -0.402 | -18.9 |
| **2025-04** | **73.8** | **16.3** | 5.84 (4) | **0.018** | **0.76** | 0.32 | 45 | -0.001 | -0.0 |
| 2025-05 | 75.9 | 12.8 | 5.07 (4) | 0.023 | 0.36 | 0.09 | 40 | -0.062 | -2.5 |
| 2025-06 | 47.3 | 10.0 | 6.55 (4) | 0.027 | 0.43 | 0.09 | 48 | -0.033 | -1.6 |
| 2025-07 | 45.3 | 7.8 | 3.01 (5) | 0.034 | 0.30 | 0.08 | 50 | -0.280 | -14.0 |
| 2025-08 | 36.7 | 7.1 | 11.38 (4) | 0.039 | 0.19 | 0.09 | 48 | -0.134 | -6.4 |
| 2025-09 | 53.2 | 9.6 | 9.86 (4) | 0.031 | 0.50 | 0.63 | 50 | -0.090 | -4.5 |
| **2025-10** | **100.3** | **19.2** | 31.97 (1) | **0.017** | **0.87** | 0.59 | 45 | +0.018 | +0.8 |
| 2025-11 | 75.0 | 15.1 | 12.89 (2) | 0.022 | 0.80 | 0.05 | 38 | +0.267 | +10.2 |
| 2025-12 | 66.7 | 14.8 | 5.85 (3) | 0.024 | 0.91 | 0.38 | 49 | +0.396 | +19.4 |
| 2026-01 | 92.6 | 18.3 | 12.79 (4) | 0.018 | 0.95 | 0.36 | 41 | -0.067 | -2.8 |
| 2026-02 | 140.4 | 27.0 | 22.43 (4) | 0.014 | 1.00 | 0.12 | 38 | +0.220 | +8.3 |
| 2026-03 | 157.1 | 31.8 | 8.58 (4) | 0.011 | 1.00 | 0.15 | 45 | +0.331 | +14.9 |
| 2026-04 (to 17th) | 105.8 | 23.6 | 4.80 (3) | 0.016 | 1.00 | 0.23 | 22 | +0.274 | +6.0 |

- The first row condenses the full table in `out_regime50.txt`. Its 28-month sum and its count of months below zero
  were added from that table.
- The 08:30 jump in 2025-10 / 11 rests on 1 / 2 release days: the US data delays of October-November 2025.

**What changed:**
- **The size of everything.** From 2025-10:
  - the daily range is about 67-157 USD (before 2025-04: at most 41);
  - the H1 ATR is 15-32 USD (at most 8.1);
  - the spread is 1-2 % of the H1 ATR (3.8-13 %);
  - on 80-100 % of weekdays the 4 New York hours from 08:30 move 30+ USD. Before 2025-04 that was at most 27 %.
- **But size alone was there in 2025-04 / 05,** and the leads did not pay then (-0.001 / -0.062):
  - the daily range was 73.8 / 75.9;
  - the H1 ATR was 16.3 / 12.8;
  - the NY 30+ share was 0.76 in April.
- **Neither the trend efficiency nor the release jump** separates the periods. The jump is noisy, with 1-5 days a
  month.

## The switch per reading (threshold chosen on 2021-09 .. P1, read once on P2; `out_regime50.txt`, `out_regime50_months.txt`)

Always on: fit 2578 trades, summed R -252.9; P2 128 trades, +0.203, summed +26.0.

| Reading, form | Switch on when | Fit: trades on, summed R | Of which 2021-09 .. 2025-09 | On in 2025-10 / 11 (share of trades) | P2: trades on, R, summed |
|---|---|---|---|---|---|
| Daily range, monthly | > 73.8 | 135, +28.0 | 48, -1.6 | 0 / 1.00 | 105, +0.279, +29.3 |
| Daily range, rolling 20 days | > 61.5 | 184, +35.1 | 68, +3.0 | 0.53 / 1.00 | 128, +0.203, +26.0 |
| H1 ATR, monthly | > 12.8 | 145, +27.6 | 40, -2.5 | 0 / 1.00 | 128, +0.203, +26.0 |
| H1 ATR, rolling | > 10.8 | 212, +36.1 | 75, +1.1 | 0.71 / 1.00 | 128, +0.203, +26.0 |
| 08:30 jump, monthly | > 12.25 | 136, +32.2 | 49, +2.6 | 0 / 1.00 | 83, +0.280, +23.2 |
| 08:30 jump, rolling 5 days | > 11.2 | 164, +24.4 | 82, -1.1 | 0.18 / 1.00 | 85, +0.143, +12.2 |
| Spread / ATR, monthly | < 0.0225 | 127, +27.1 | 40, -2.5 | 0 / 1.00 | 105, +0.279, +29.3 |
| Spread / ATR, rolling | < 0.0271 | 212, +36.1 | 75, +1.1 | 0.71 / 1.00 | 128, +0.203, +26.0 |
| **NY 30+ share, monthly** | **> 0.762** | **105, +30.1** | **0, 0.0** | **0 / 1.00** | **128, +0.203, +26.0** |
| **NY 30+ share, rolling 20 days** | **> 0.75** | **116, +32.3** | **0, 0.0** | **0.24 / 1.00** | **128, +0.203, +26.0** |
| D1 eff20, monthly / rolling | > 0.58 / > 0.64 | 83, +10.9 / 4, +3.3 | 0 / 0 | - | 0 trades |

- **Every size reading switches on in time:** on in 2025-11, the first paying month (+0.267). The rolling forms are
  partly on in 2025-10, which was flat (+0.018).
- **On P2 none beats always-on by much.** P2 was all "present", so the switches stay on (summed +26.0 .. +29.3). The
  monthly range / spread forms skip the second half of January (-0.067) and gain +3.3 R.
- **The NY 30+ share is the only reading that was never on in 2021-09 .. 2025-09** and on in every month from 2025-11.
  But its chosen threshold, 0.762, sits exactly at April 2025's 0.76:
  - the switch is "on" because April 2025 is excluded by a hair;
  - the range / ATR switches put their lines at April-May 2025 too (> 73.8 = April's range; > 12.8 = May's ATR).
  - **The threshold choice learned to exclude April-May 2025.** It was not shown a rule that knew it in advance.
- **This was fitted with P1 in view** (stated beforehand). A fit on 2021-09 .. 2025-09 alone has no paying stretch to
  find; its best choice is never to trade.

## What it means for a monitoring rule ("when does the present regime end")

1. **Size is necessary, not sufficient, in this sample.** Every paying month had:
   - a daily range >= 67;
   - an H1 ATR >= 14.8;
   - an NY 30+ share >= 0.80;
   - a spread under 2.4 % of the ATR.

   April-May 2025 had the size without the pay. A size floor can say "not the present". It cannot say "the present".
2. **Today's distance from the line** (2026-04, the last learning month): daily range 105.8, H1 ATR 23.6, NY 30+ share
   1.00. These are 1.3-1.8x above the fitted lines (73.8 / 12.8 / 0.76).
   - The present regime ends, by these readings, when the 20-day NY 30+ share falls below about 0.75, or the 20-day
     H1 ATR below about 11 USD.
   - The rolling forms react within days. The monthly forms take up to one month.
3. **The monitor I would propose** (for the measurer and the owner; not built):
   - a size floor (the NY 30+ share over 20 days > 0.75, which also needs the rolling H1 ATR > about 11) **and** the
     SW-20 own result;
   - the floor stands the leads aside at once when gold shrinks;
   - SW-20 catches a change of character at the same size, like April-May 2025, after about 20 trades.
   - Both lines were set with P1 in view, so the exam months (2026-04-18 on) are their first honest read, and that is
     for the measurer only.
4. **The cause is not answered by these readings.** Size went up 2-4x, and the leads (fading failed breaks, the 13:00
   ORB) began to pay only after the size had stayed high for months. The trend efficiency and the release jump do not
   mark it. A question for the owner, as a hypothesis to test: what did the market do differently after 2025-10 (the
   participants, the news flow, the central-bank buying)?

## Files (row 50)
- `regime50.py` + `test_regime50.py` + `plant_regime50.py`
- `regime50_months.py`
- outputs: `out_regime50.txt`, `out_regime50_switch.csv`, `out_regime50_months.txt`, `out_plant_regime50.txt`,
  `regime50_daily.parquet`, `regime50_trades.parquet`
- SW-20 code (finished and run by the measurer): `streams.py`, `sw20.py`, `test_sw20.py`, `plant_sw20.py`,
  `out_plant_sw20.txt`

# SW-20 on the unseen years - how it is built, written before computing (2026-10-20 17:42 Thai, `date -u` 10:42)

The rule and the pass line are the measurer's (`precursors/notes.md`, "SW-20"). They are followed as written.

**A data fact found before computing:** the old store's M1 starts on **2021-09-01**, not 2020-09; its D1 does start in
2020-09. The overlap with the main store was checked: 30,022 M1 bars in 2023-09-01 .. 2023-10-02, with 0 bars in one
store only and 0 differences in open / high / low / close / spread.
- Y1 (2020-10-18 .. 2021-10-18) therefore has M1 for only 2021-09-01 .. 2021-10-17, about 7 weeks.
- In those weeks the paper record is still warming up. Y1 is reported as it falls out, and is marked as too short to
  judge.
- Nothing else replaces M1: M15 would change the rules.

**The build** (`sw20.py`):
- The streams are built from `gold.bars("M1", before=2023-10-21)`. The event loops are those of `states_events.py`,
  moved into a function `streams.build(m)` that takes the bars as an argument.
- Costs: M1 spread x 0.01 + 0.08, slippage 0.
- **The equivalence check before the run:** `streams.build` on the main store 2023-09 .. 2024-10 must reproduce
  `states_events.parquet`'s O1 events and their M1 R exactly.
- **The switch** (`sw20.switch_ok`): a trade is real when at least 20 of the stream's earlier paper trades have exited
  strictly before its entry and the mean R of the last 20 of them (by exit time) is > 0.
- Each year is read once.
# Row 45 - what was there when the leads paid - written before computing (2026-10-20 17:08 Thai, `date -u` 10:08)

**The question** (owner: "a result that only works in some periods is normal; the system's job is to see which period
we are in now"): the leads #22 (the 13:00-Thai ORB), #23 (the reclaim) and #43 (RT_25 opp) pay in P1 / P2 and lose
in O1 / O2. What reading, known before each entry, separates the paying periods from the losing ones?

**The streams** (rules exactly as before; every period O1 2023-10-18 .. 2024-10-17, O2 .. 2025-10-17, P1, P2):
- **ORB:** PLAN-1's London piece (range 06:00-06:14 UTC, skip if > 1.5 H1 ATR, the first M1 close beyond 06:15-07:14,
  stop the other side, 2 R, 60 min).
- **RC_win / RC_all:** `reclaim.py`'s events in the owner's windows (the lead #23) and at all hours (more trades).
- **RT_opp:** `rt_old.py`'s events, the other way, the stop at the rule's distance, a 1 R target, 120 min.
- **Costs:** the tick bid / ask for P1 / P2 (`tsim.grid`, slippage 0); the M1 spread (spread x 0.01 + 0.08) for O1 /
  O2 (`m1sim.py`, slippage a parameter defaulting to 0, stop at its price or the gapped open). The M1 result for P1 /
  P2 is printed beside the ticks as a check.

**The readings** (all from bars complete before the entry; D1 / H4 are MT5's own bars, available at open + 1 day /
+ 4 h; H1 and the spread from M1):

| # | Reading | Definition |
|---|---|---|
| 1 | rng60 | the mean range of the last 5 D1 bars, as a percentile among the last 60 D1 ranges |
| 2 | season | ADR20 / the median D1 range of the last 120 D1 bars |
| 3 | eff_d1 | D1 20-bar efficiency: abs(close - close 20 bars back) / the sum of abs(close changes) |
| 4 | adx_d1 | MT5 ADX(14) on D1 |
| 5 | eff_h4 | H4 30-bar efficiency |
| 6 | adx_h4 | MT5 ADX(14) on H4 |
| 7 | fail20 | the share of the level breaks (reclaim.py's breaks of PDH / PDL / ASH / ASL) of the last 20 server days that failed (an M5 close back inside by 0.1 H within 24 M5 bars), counting only breaks whose outcome was settled before the entry; >= 10 breaks |
| 8 | sess10 | the M1 range of the 6 h before the entry / the mean range of the same 6-h clock window on the previous 10 weekdays |
| 9 | spr_atr | the median M1 spread (USD) of the last 60 M1 bars / the H1 ATR(14) |
| 10 | since_big | hours since the last H1 bar whose range >= 2.5 x the H1 ATR(14) of the bar before it |
| 11 | used | the server day's range so far / ADR20 |
| 12 | own20 | the stream's own mean R over its last 20 trades that exited before this entry |

**The split rules:**
- **Terciles** per stream and reading, cut at the O1 + P1 terciles; trades and R per part in each tercile.
- **One threshold per stream and reading, chosen on O1 + P1 only:**
  - the candidates are the 20th, 30th .. 80th percentiles of the reading on that stream's O1 + P1 events, keeping
    the trades >= or < the cut (14 rules);
  - a rule is eligible when it keeps >= 30 % of the O1 trades and >= 30 % of the P1 trades;
  - the score is min(kept R in O1, kept R in P1);
  - the best is then read once on O2 + P2.
- **A lead:** the kept trades have P1 and P2 > 0 and O1 and O2 >= 0. The goal stays >= +0.15 in P1 / P2.
- **Settings tried:** 4 streams x 12 readings x 14 = 672 rules. With that many, a lead from one cell is a hypothesis
  for the measurer, not a result.
# Row 45 - the results (measured 2026-10-20 17:11-17:19 Thai)

**How the numbers were checked:**
- **`m1sim.py`** (the M1 simulator, spread only, slippage a parameter defaulting to 0): 6 hand-worked tests
  (`test_m1sim.py`); 8 of 8 planted bugs caught (`out_plant_m1sim.txt`).
- **`readings.py`:** 8 hand-worked tests (`test_readings.py`); 9 of 9 planted bugs caught after two tests were added
  for the first-round misses (ties in the percentile; the ATR of the bar before; the last big bar)
  (`out_plant_readings.txt`).
- **The availability of MT5's D1 bars:** 676 D1 bars against the M1 server days. Their high / low differ by 0.00, and
  no bar's last M1 minute ends after its availability.
- **A look-ahead run:** 40 random events had all 12 readings recomputed from data cut at the entry. Result: 0
  differences.
  - The first run found 4. `since_big` counted a forming H1 bar when the data ended inside it.
  - Fixed: an H1 bar now counts from the end of its hour.
- **The streams reproduce the earlier numbers on the ticks:**
  - the ORB: +0.214 / +0.123, as row 39;
  - RT_opp: +0.261 / +0.255, as row 39;
  - RC_win: +0.311 / +0.313 (+0.312 / +0.310 with 0.07 slippage).
  - M1 for P1 / P2 sits within 0.001-0.021 of the ticks.
- **No exam data was loaded.** `slib.m1` and `readings.load_mt5` filter before 2026-04-18, and `tsim` refuses exam
  days.

## The streams, spread only (P1 / P2 on the ticks, O1 / O2 on M1)

| Stream | O1 R (trades) | O2 | P1 | P2 |
|---|---|---|---|---|
| ORB | -0.088 (250) | -0.079 (252) | +0.214 (59) | +0.123 (60) |
| RC_win (#23) | -0.139 (96) | -0.219 (97) | +0.311 (19) | +0.313 (22) |
| RC_all | -0.147 (339) | -0.169 (312) | +0.008 (65) | +0.110 (68) |
| RT_opp (#43) | -0.178 (241) | -0.130 (231) | +0.261 (41) | +0.255 (46) |

With the spread only, the older years stay negative.

## One threshold per reading, chosen on O1 + P1, read once on O2 + P2 (`states.py`, `out_states.txt`)

R (trades) of the kept trades. **No reading is a lead:** none keeps P1 and P2 > 0 with O1 and O2 >= 0. The terciles of
every reading per part are in `out_states.txt`.

**ORB**

| Reading | Kept (chosen on O1 + P1) | O1 | O2 | P1 | P2 |
|---|---|---|---|---|---|
| rng60 | < 0.533 | +0.103 (98) | -0.089 (104) | +0.163 (23) | -0.514 (12) |
| season | < 1.32 | -0.027 (167) | -0.159 (187) | +0.216 (18) | -1.009 (3) |
| eff_d1 | >= 0.25 | -0.020 (95) | -0.109 (111) | +0.030 (29) | -0.194 (22) |
| adx_d1 | < 32.8 | -0.056 (136) | -0.017 (125) | +0.322 (18) | +0.278 (22) |
| eff_h4 | < 0.24 | +0.023 (148) | -0.070 (145) | +0.248 (37) | +0.007 (39) |
| adx_h4 | < 25.6 | +0.002 (103) | +0.115 (83) | +0.207 (21) | -0.028 (24) |
| fail20 | < 0.647 | -0.050 (97) | -0.003 (94) | +0.239 (54) | +0.007 (45) |
| sess10 | >= 0.913 | -0.031 (123) | -0.102 (127) | +0.230 (32) | +0.048 (25) |
| spr_atr | < 0.0945 | -0.099 (188) | -0.074 (250) | +0.214 (59) | +0.123 (60) |
| since_big | >= 39.4 | -0.039 (93) | -0.029 (118) | +0.158 (31) | -0.014 (22) |
| used | < 0.558 | -0.051 (216) | -0.115 (152) | +0.301 (31) | +0.236 (36) |
| own20 | < 0.156 | -0.077 (219) | -0.102 (193) | +0.455 (20) | +0.058 (27) |

**RC_win (#23)**

| Reading | Kept | O1 | O2 | P1 | P2 |
|---|---|---|---|---|---|
| rng60 | < 0.733 | -0.088 (63) | -0.205 (68) | +0.340 (13) | +0.525 (9) |
| season | < 1.32 | -0.107 (62) | -0.190 (76) | +0.155 (7) | -0.031 (1) |
| eff_d1 | < 0.186 | -0.062 (50) | -0.223 (53) | +0.363 (7) | +0.219 (13) |
| adx_d1 | >= 33.6 | -0.053 (34) | -0.069 (45) | +0.338 (12) | +0.129 (14) |
| eff_h4 | < 0.132 | -0.094 (50) | -0.346 (30) | +0.299 (7) | +0.258 (10) |
| adx_h4 | >= 27.7 | -0.114 (49) | -0.169 (62) | +0.053 (9) | +0.272 (13) |
| fail20 | < 0.63 | +0.047 (29) | -0.211 (23) | +0.232 (16) | +0.398 (14) |
| sess10 | >= 1.02 | -0.048 (49) | -0.218 (49) | +0.795 (9) | +0.221 (13) |
| spr_atr | < 0.076 | -0.052 (61) | -0.214 (93) | +0.311 (19) | +0.313 (22) |
| since_big | >= 18 | -0.019 (34) | -0.195 (62) | +0.269 (12) | +0.376 (8) |
| used | >= 0.661 | -0.092 (38) | -0.389 (39) | -0.018 (8) | +0.210 (10) |
| own20 | >= -0.322 | -0.038 (65) | -0.309 (72) | +0.311 (19) | +0.313 (22) |

**RC_all** (the reclaim at all hours; more trades)

| Reading | Kept | O1 | O2 | P1 | P2 |
|---|---|---|---|---|---|
| rng60 | < 0.517 | -0.080 (132) | -0.132 (136) | +0.040 (26) | -0.007 (13) |
| season | >= 1.09 | -0.135 (261) | -0.151 (162) | +0.020 (62) | +0.110 (68) |
| eff_d1 | >= 0.0582 | -0.098 (270) | -0.178 (252) | -0.012 (53) | +0.017 (56) |
| adx_d1 | < 34.8 | -0.101 (215) | -0.156 (162) | +0.169 (25) | +0.368 (29) |
| eff_h4 | < 0.228 | -0.109 (207) | -0.102 (177) | +0.179 (35) | -0.031 (43) |
| adx_h4 | >= 31.1 | -0.082 (132) | -0.279 (159) | -0.039 (30) | +0.192 (31) |
| fail20 | < 0.643 | +0.018 (104) | -0.149 (95) | -0.044 (57) | +0.036 (50) |
| sess10 | >= 1.01 | -0.055 (168) | -0.131 (156) | -0.004 (33) | -0.038 (30) |
| spr_atr | < 0.0656 | -0.126 (137) | -0.156 (289) | +0.008 (65) | +0.110 (68) |
| since_big | < 19.5 | -0.101 (177) | -0.146 (115) | +0.090 (25) | -0.013 (34) |
| used | >= 0.477 | -0.118 (189) | -0.221 (202) | -0.042 (53) | +0.047 (41) |
| own20 | < -0.0337 | -0.101 (209) | -0.141 (251) | -0.040 (27) | -0.068 (21) |

**RT_opp (#43)**

| Reading | Kept | O1 | O2 | P1 | P2 |
|---|---|---|---|---|---|
| rng60 | < 0.467 | -0.035 (89) | -0.075 (86) | +0.408 (20) | -0.079 (5) |
| season | >= 1.28 | -0.121 (86) | -0.190 (58) | +0.149 (29) | +0.255 (46) |
| eff_d1 | >= 0.0579 | -0.108 (189) | -0.093 (189) | +0.287 (36) | +0.177 (38) |
| adx_d1 | < 39.3 | -0.136 (174) | -0.170 (122) | +0.373 (22) | +0.214 (25) |
| eff_h4 | < 0.199 | -0.117 (122) | -0.098 (105) | +0.289 (19) | +0.436 (25) |
| adx_h4 | < 28 | -0.118 (124) | -0.142 (82) | +0.219 (17) | +0.441 (24) |
| fail20 | < 0.657 | -0.138 (96) | -0.127 (95) | +0.291 (40) | +0.328 (35) |
| sess10 | >= 0.822 | -0.139 (193) | -0.106 (183) | +0.246 (32) | +0.180 (35) |
| spr_atr | < 0.0656 | +0.030 (100) | -0.131 (212) | +0.261 (41) | +0.255 (46) |
| since_big | < 25.4 | -0.130 (151) | -0.133 (109) | +0.486 (18) | +0.166 (26) |
| used | >= 0.469 | -0.110 (139) | -0.114 (155) | +0.337 (30) | +0.265 (34) |
| own20 | >= -0.324 | -0.222 (176) | -0.113 (203) | +0.261 (41) | +0.255 (46) |

**What the splits show:**
- **In O1 / O2 almost every state of every reading loses** (`states_count.py`):
  - 26 of the 287 older-year tercile cells are > 0;
  - one tercile is > 0 in both O1 and O2: the ORB's sess10 middle tercile, +0.063 / +0.016. It is -0.096 in P1;
  - no tercile is > 0 in all four parts.
- **Some readings only tag the period, not a state within it:**
  - **spr_atr** (the spread / H1 ATR): every P1 / P2 trade sits in the lowest tercile.
    - Older trades in that same low-cost state still lose: RT_opp O2 -0.150 (169), RC_all O2 -0.171 (231).
    - So the cost against volatility is not why the older years lose.
  - **season** (ADR20 / its 120-day median): P2 has no trade in the low tercile.
  - **fail20** (the trailing failed-break share): P1 has no trade in the high tercile.
- **fail20 points the counter-intuitive way:**
  - The two fades of failed breaks (RC, RT_opp) pay in P1 / P2 when *fewer* recent breaks failed (the low tercile:
    RT_opp +0.385 / +0.328).
  - In O1 / O2 they lose in every tercile.
- **Even the best ORB rules are not leads:**
  - `adx_h4 < 25.6`: O1 +0.002, O2 +0.115, P1 +0.207, but P2 -0.028.
  - `adx_d1 < 32.8`: P1 +0.322, P2 +0.278, but O1 -0.056, O2 -0.017.
  - These two are the nearest to a lead. With 672 rules tried, I read them as noise until a new test shows otherwise.

## Quarter by quarter: the paying state is a time block, not a value of any reading (`states_quarters.py`)

The quarter's R (trades); the H1 ATR is the quarter's median in USD.

| Quarter | ORB | RC_all | RT_opp | H1 ATR |
|---|---|---|---|---|
| 2023-Q4 | -0.318 (49) | -0.349 (69) | -0.309 (47) | 3.2-3.8 |
| 2024-Q1 | -0.105 (61) | -0.091 (82) | -0.217 (60) | 3.0-3.5 |
| 2024-Q2 | -0.109 (64) | -0.084 (88) | -0.080 (54) | 5.4-5.5 |
| 2024-Q3 | +0.096 (64) | -0.087 (83) | -0.217 (68) | 4.8-5.0 |
| 2024-Q4 | +0.146 (63) | -0.133 (85) | -0.057 (58) | 5.5-5.8 |
| 2025-Q1 | -0.394 (62) | -0.172 (74) | -0.164 (70) | 5.9-6.5 |
| 2025-Q2 | +0.182 (64) | -0.240 (64) | -0.241 (48) | 10.9-11.9 |
| 2025-Q3 | -0.236 (62) | -0.150 (91) | -0.055 (54) | 7.0-7.6 |
| **2025-Q4** | **+0.203 (62)** | -0.030 (69) | **+0.276 (50)** | 15.0-15.7 |
| **2026-Q1** | **+0.125 (58)** | +0.057 (65) | **+0.209 (43)** | 25.8-26.6 |

- **The reclaim and RT_opp paid only from 2025-10 on.** RC_win: +0.199 / +0.186 in 2025-Q4 / 2026-Q1, negative in
  every earlier quarter.
- **The ORB is more mixed in the older years:** it paid in 2024-Q3, 2024-Q4 and 2025-Q2.
- **Across quarters, the quarter's R follows the absolute H1 ATR** (correlation +0.44 ORB, +0.73 RC_all, +0.78
  RT_opp).
  - Row 39 showed that the H1 ATR at the trade does not separate within the periods. For example, RT_opp with an
    H1 ATR of 10-15 USD: O2 -0.006, P1 +0.341.
  - 2025-Q2 had an H1 ATR of about 11-12 USD (April 2025) and RC / RT lost there.
  - So it is not "volatility above X". It is what gold has done since about October 2025.

## The plainest present-detector: the stream's own shadow result (`states_switch.py`; written after steps 2-3, a follow-up)

The rule: every event is simulated whether it is traded or not (a shadow trade). The stream is traded only while the
mean R of its last N shadow trades that exited before the entry is > 0. Every cell is printed and none is chosen.

**The summed R per part** (a stand-aside counts as 0):

| Stream | Always | own20 > 0 | own40 > 0 | own60 > 0 |
|---|---|---|---|---|
| ORB | -22.0 / -19.8 / +12.6 / +7.4 | -8.7 / +3.8 / +11.6 / +5.1 | -9.4 / +3.1 / +8.4 / +0.5 | -4.8 / -2.5 / +7.2 / +7.4 |
| RC_win | -13.4 / -21.2 / +5.9 / +6.9 | -2.9 / -1.0 / +3.7 / +6.9 | -5.1 / -0.7 / +0.8 / +6.9 | -3.3 / -2.9 / 0.0 / +5.7 |
| RT_opp | -42.9 / -29.9 / +10.7 / +11.7 | -1.2 / -10.2 / +9.7 / +11.7 | +0.7 / +1.6 / +10.3 / +11.7 | 0.0 / -13.6 / +11.3 / +11.7 |
| **The three together** | **-78.2 / -71.0 / +29.2 / +26.0** | **-12.8 / -7.4 / +25.1 / +23.8** | **-13.7 / +4.0 / +19.5 / +19.1** | **-8.1 / -19.0 / +18.5 / +24.9** |

(each cell: O1 / O2 / P1 / P2)

- **The trades it keeps still lose on average in the older years.**
  - RT_opp own20: O1 -0.035 (33 trades, 14 % of the events), O2 -0.192 (53, 23 %).
  - So by the per-trade criterion it is not a lead. Only RT_opp own40 meets it: O1 +0.177 (4), O2 +0.035 (47),
    P1 +0.323 (32), P2 +0.255 (46). That is 1 of 12 cells, with 4 trades in O1.
- **At the level of the system, it is the owner's "trade less in an unsuitable phase":**
  - with all three N, it cuts the older years' summed loss of the three leads from -78 / -71 R to -8 .. -14 / -19 ..
    +4 R;
  - it keeps 63-96 % of the P1 / P2 summed R;
  - it keeps 0-51 % of the older events per stream;
  - in P1 / P2 it keeps 63-100 % of the ORB and RT_opp events, but less of the reclaim's (RC_win 0-100 %, RC_all
    22-63 %).
- **The cost is the lag:** own40 / own60 miss part of P1, where the trailing window still held 2025-Q3's losses.

## The ranked proposals after row 45

1. **The shadow-result switch as the system's present-detector, for every piece.**
   - Owner's terms: "see which period we are in now". Every piece keeps trading on paper. It trades for real only
     while its own last N paper trades pay.
   - Why: no market reading separated the periods (672 rules). The pieces' own results do, with a lag.
   - Who: the measurer, on PLAN-1's three pieces and the RT_opp / reclaim merge (dev2's V3-2 entry 3), walk-forward
     over O1 .. P2.
     - N is fixed before the run: one value, e.g. 20, the fastest. N = 40 was the only cell to meet the per-trade
       criterion, so it must not be chosen for that reason.
     - The older years need the Asia B2 detector run on 2023-25 (row 39, question 3).
   - Pass: the summed R of the older years >= 0, and >= +0.15 per traded trade in P1 / P2.
2. **Report the summed R per period, not only R per trade, for any rule with a stand-aside.**
   - A filter that trades 14 % of the old events at -0.035 R is a large gain over trading them all at -0.178. The
     per-trade criterion hides that.
3. **Do not add the readings of row 45 to PLAN-1 or to the leads.**
   - None turns the older years to >= 0.
   - The nearest (ORB adx_h4 < 25.6; ORB adx_d1 < 32.8) each fail one part. Both were picked from 672 rules.

## What to stop doing (row 45)
- **Searching single market readings for the leads' season.** Twelve readings (range, season, D1 / H4 efficiency, ADX,
  failed breaks, the session range, the cost against volatility, the time since a big bar, the day's range used) do not
  separate the older years. The P1 / P2 edge sits in a time block (2025-10 on), not in a reading's value.
- **Cost as the explanation for the older years.** Trades with the same low cost against volatility still lose there.

## Questions to the measurer (row 45)
1. **May the system run every piece on paper and trade only while its own recent result pays** (proposal 1)? It needs
   no market theory. Its cost is a lag of about N trades at each change of phase.
2. **Is the target the older years' summed R >= 0** (a stand-aside counts as 0), or R per traded trade >= 0? They give
   different verdicts on proposal 1.
3. **Why gold changed in about 2025-10 is not answered here.** The H1 ATR alone does not explain it: 2025-Q2 was
   volatile and lost. Does the owner have a market reading for it?

## Files (row 45)
| Topic | Scripts | Outputs |
|---|---|---|
| The M1 simulator, spread only | `m1sim.py` + `test_m1sim.py` + `plant_m1sim.py` | `out_plant_m1sim.txt` |
| The readings | `readings.py` + `test_readings.py` + `plant_readings.py` | `out_plant_readings.txt` |
| The events and trades | `states_events.py` | `out_states_events.txt`, `states_events.parquet`, `states_breaks.parquet` |
| The checks, terciles and thresholds | `states.py`, `states_count.py` | `out_states.txt`, `out_states_choice.csv`, `out_states_count.txt`, `states_readings.parquet` |
| Quarter by quarter | `states_quarters.py` | `out_states_quarters.txt` |
| The shadow-result switch | `states_switch.py` | `out_states_switch.txt` |


# Row 39 - written before computing (2026-10-20 12:58 Thai, `date -u` 05:58)

**Part 1, the transformations** (`transform.py`, simulator `tsim.py`; tests `test_tsim.py` 14 hand-worked, planted bugs
`plant_tsim.py` 12 of 12 caught). Families: #16 SR break (its best setting), #17 B2, #18 A and B1, #20 W, #13 the M1
pullback, #14 the M15-structure pullback, #25 break and retest, #28 FOLLOW 15m and FOLLOW 2R/30m, #41 D2 (08:30 + 10:00).
The grid per family: the side {same, opp} x the stop {x1, x1.5, x2} x the target {orig, x0.75, x0.5, 1R0 (a target at 1 x
the rule's own stop distance)} = 24 cells, 264 in all. Each trade alone from the rule's entries (the one-at-a-time view
beside it). Costs: the tick spread, slippage 0. A lead = >= +0.15 R in both parts, seen after the run.

**Part 2, the state weights per piece** (`state_weights.py`): the pieces Asia B2 (W, Asia window), London 13:00 ORB, NY
08:30 straddle 30 min, re-simulated spread-only. The states read from the bars complete before the entry: (a) the D1
20-day efficiency terciles (0.116 / 0.264, as regime.py); (b) the D1 ATR14 against its 100-day median (>= 1.25 high);
(c) the ADR20 season: the 20-day mean daily range against its 120-day median, terciles from P1's weekdays; (d) the H4
volatility: the H4 ATR14's percentile among the last 120 H4 bars (< 33 low, > 67 high); (e) the D1 structure from
2-bar fractal swings (up = a higher high and a higher low, down = both lower, else mixed), and the trade's side with /
against it. The rule: per piece and reading, weight 0.5 in a state where the piece's P1 R < 0 on >= 8 trades, else 1;
judged on P2, and on O1 / O2 where the piece has older trades (the London ORB only: dev/d1_trades.parquet, M1).

# Row 39 - the results (measured 2026-10-20 12:58-13:25 Thai)

**How the numbers were checked:**
- **`tsim.py`:** 14 hand-worked tests pass (`test_tsim.py`). All 12 planted bugs were caught (`out_plant_tsim.txt`).
- **Each family's own cell, at its own 0.07 USD slippage, reproduces the stored R:**
  - SR16 and W_20: exactly.
  - D2: +0.280 / +0.214, against +0.279 / +0.214 stored.
  - B2: -0.025 / -0.009, against -0.026 / -0.014. 4 / 6 trades have no tick within 5 minutes.
- **An independent plain tick loop** (`recheck_transform.py`) agrees with the simulator on the exit kind, the exit time
  and the pnl:
  - 400 of 400 sampled rows (`out_recheck_transform.txt`);
  - 4,524 of 4,524 rows of RT_25 (every cell) and D2.
- **The lead re-derived on M1** (`rt_old.py`, mlib costs): +0.259 / +0.228. The ticks give +0.262 / +0.227.
- **No exam data was loaded.** `tsim.day_ticks` refuses 2026-04-18 onward, and `slib.m1` stops before it.

## Part 1 - the transformations

264 cells. Outputs: `out_transform.txt`, `out_lead_checks.txt`.

| Family (row) | The rule, spread only, P1 / P2 (trades) | The best cell, P1 / P2 | The opposite side x1, P1 / P2 | Verdict |
|---|---|---|---|---|
| SR16 level break (#16) | -0.049 / +0.144 (150 / 153) | same x1 orig (the rule itself) | -0.061 / -0.109 | no cell is positive in both parts; every transform keeps P1 < 0 |
| B2 (#17) | -0.018 / -0.004 (348 / 342) | same x1.5 1R0: +0.005 / +0.008 | -0.145 / -0.059 | no direction either way |
| A (#18) | -0.029 / -0.038 (517 / 559) | same x2 orig: -0.016 / -0.025 | -0.158 / -0.045 | as B2 |
| B1 (#18) | -0.030 / -0.070 (378 / 359) | same x2 0.5: +0.007 / +0.002 | -0.221 / -0.092 | as B2 |
| W (#20) | -0.018 / +0.040 (115 / 109) | same x1.5 0.5: +0.012 / +0.028 | -0.084 / -0.152 | as B2 |
| M1 pullback (#13) | -0.082 / -0.011 (1863 / 1159) | same x2 0.75: -0.044 / -0.004 | -0.110 / -0.151 | all 24 cells < 0 (pooled) |
| M15 pullback (#14) | -0.091 / -0.263 (337 / 161) | opp x1.5 0.75: -0.026 / +0.072 | -0.046 / +0.045 | the sign flips |
| Break and retest (#25) | -0.218 / -0.380 (41 / 46) | **opp x1 0.5: +0.261 / +0.255** | **+0.262 / +0.227** | **LEAD** (7 cells) |
| FOLLOW 15m (#28) | +0.058 / -0.120 (47 / 65) | opp x1 orig: -0.209 / +0.168 | -0.209 / +0.168 | the sign flips in every cell |
| FOLLOW 2R/30m (#28) | +0.013 / -0.054 | same x1.5 0.75: +0.056 / +0.045 | -0.149 / -0.037 | below the goal |
| D2, 08:30 + 10:00 (#41) | +0.284 / +0.219 (94 / 109) | the rule itself | **-0.317 / -0.530** | 6 "lead" cells, all resting on one trade |

**What it shows:**
- **The opposite side rescues only a rule whose entry carries a direction.**
  - The retest was right 24 % of the time, so its reverse is right 66 % of the time.
  - The B2 / A / B1 / W micro-pattern streams lose on both sides. There is no direction to reverse: R1 of the review,
    now measured from the other side.
  - The data-minute straddle reversed loses -0.317 / -0.530. The release minute's direction is real.
- **A wider stop pulls R towards 0 but creates no edge:**
  - B2: -0.018 / -0.004 at x1, -0.004 / -0.005 at x2;
  - the M1 pullback: -0.082 / -0.011 at x1, -0.042 / -0.008 at x2.
- **A nearer target raises the win % but hardly moves R.** B2 wins 39 % at the rule's target and 42 % at 1R0, and its R
  moves by at most 0.03.
- **D2's "lead" cells are not leads.** Without its one best trade, P2 is -0.035 (x1) and -0.008 (x1.5). That trade is
  the 2026-01-29 10:00 NY crash sell, +27.6 R.

**The lead: the break-and-retest entries taken back into the range (RT_25 opp).**
- **The best cell is x0.5 (a 1 R target):**
  - +0.261 / +0.255 R, 41 / 46 trades, 71 % / 67 % winners;
  - without the best 3 trades: +0.202 / +0.203;
  - weeks positive: 9 of 13 / 10 of 13;
  - pooled: +0.258 (95 % range +0.08..+0.44);
  - one position at a time: +0.242 / +0.227.
- **Most of it lies outside the owner's windows:**

  | | P1 R (trades) | P2 R (trades) |
  |---|---|---|
  | Outside the owner's windows | +0.397 (24) | +0.294 (28) |
  | Inside the owner's windows | +0.068 (17) | +0.194 (18) |

- **It is partly #23 again.** 37 of its 87 entries have a reclaim.py trade on the same level within 60 minutes.
- **It holds in the present only.** `rt_old.py` on M1, with the heavier mlib costs:

  | Side | O1 R (trades) | O2 R (trades) | P1 R (trades) | P2 R (trades) |
  |---|---|---|---|---|
  | Opposite, x0.5 | -0.203 (241) | -0.150 (231) | +0.260 (41) | +0.273 (47) |
  | Same (the retest itself) | +0.027 (241) | +0.007 (231) | -0.308 (41) | -0.294 (47) |

  - The paying side flipped between the periods. This is the same regime story as #22 and #23.
  - The H1 ATR level does not explain the flip:

    | H1 ATR | O2 R (trades) | P1 R (trades) |
    |---|---|---|
    | 10-15 USD | -0.006 (37) | +0.341 (18) |
    | 15-25 USD | -0.324 (15) | +0.254 (21) |

- **A trailing side switch** (`side_switch.py`, written before it was computed): at each event, take the side whose
  last N events paid more; 1 R target; M1.

  | N | O1 | O2 | P1 | P2 |
  |---|---|---|---|---|
  | 20 | +0.009 | -0.118 | +0.211 | +0.273 |
  | 40 | +0.010 | -0.042 | +0.162 | +0.273 |

  - The switch took the opposite side in 98-100 % of P1 / P2 and in 3-31 % of O1 / O2.
  - It keeps most of P1 / P2 and removes most of the old loss.

## Part 2 - the state weights per piece

Script `state_weights.py`; output `out_state_weights.txt`.

**The pieces, spread only:**

| Piece | P1 R (trades) | P2 R (trades) |
|---|---|---|
| Asia B2 | +0.081 (41) | +0.186 (38) |
| London ORB | +0.214 (59) | +0.123 (60) |
| NY straddle | +0.467 (41) | +0.119 (59) |
| The plan | +0.249 (141) | +0.137 (157) |

- The pieces never overlap, so "alone" and "one position at a time" give the same numbers.
- PLAN-1's mechanism weights: +0.338 / +0.188. The measurer's +0.341 / +0.191 agrees.
- The ORB in the older years (the developer's M1 trades): O1 -0.083 (250 trades), O2 -0.066 (252).

**Weights chosen on P1 only** (0.5 where the piece's P1 R < 0 on >= 8 trades), then read on P2:

| Reading | P1 (in sample) | P2 |
|---|---|---|
| none | +0.249 | +0.137 |
| D1 efficiency (trend) | +0.277 | +0.141 |
| D1 volatility | +0.268 | +0.132 |
| ADR20 season | +0.263 | +0.130 |
| H4 volatility | +0.261 | +0.140 |
| D1 structure | +0.249 | +0.137 (no P1 cell qualified) |
| side with / against the D1 structure | +0.307 | +0.135 |

- **No P1-chosen reading moves P2 by more than +0.004.**
- **The cells are 2-34 trades.** That is far too few to tell a +0.15 difference (`power.py`).

**The mechanism weights, cut by cut:**

| Cut | P1 | P2 | O1 | O2 | What it shows |
|---|---|---|---|---|---|
| Asia B2 in a trend | -0.070 (23) | -0.006 (10) | - | - | same sign in both parts |
| London ORB in a trend | +0.030 | -0.210 | -0.013 | -0.098 | the one cut the older years support: the ORB never pays in a trend |
| NY straddle in a trend | +0.860 (23) | +0.262 (22) | - | - | same sign in both parts |
| NY straddle, sideways + mixed | about -0.03 (18) | +0.033 (37) | - | - | same sign in both parts |

**The ORB loses in O1 / O2 in almost every state:**
- sideways is positive in 3 of 4 periods: +0.243 / +0.464 / -0.087 / +0.124;
- the low season, where most of O1 / O2 sits: -0.012 / -0.153;
- no reading turns the older years positive. The ORB's present-only nature is not a state these readings see.

## The ranked proposals after row 39

1. **Keep PLAN-1 as frozen, with the mechanism weights.**
   - None of the five new readings beats the D1 efficiency on P2.
   - Each mechanism cut has the same sign in both parts.
   - The exam judges it. Do not add state readings: the cells are too small to choose them (R2).
2. **The failed retest traded back into the range (RT_25 opp, 1 R target), merged with #23, the reclaim.**
   - Who: dev2, entry 3 "the fake break at a range edge".
   - The test: the union of both event sets (the close back inside; the failed retest turn); dev2's box edges plus the
     levels everyone sees; a 1 R target; two stop settings (the mirrored distance, and the break's extreme + 0.25 H); on
     the ticks; the owner's windows reported apart from the other hours.
   - Pass: >= +0.15 in both parts with >= 30 trades each, in the windows the owner allows (question 1).
3. **A trailing side switch for the level-break events** (`side_switch.py`): take the side of the last 20-40 events.
   - The owner's "live in the present" in its plainest form: the side of a broken level flips with the regime, and the
     trailing result sees the flip without a fixed threshold.
   - Who: the measurer, as a walk-forward over O1 .. P2, on the ticks where they exist.
   - Pass: >= 0 in O1 / O2 and >= +0.15 in P1 / P2.
   - The first check (M1): +0.009 / -0.118 / +0.211 / +0.273 (N 20). It was written before it was computed but after
     the lead was seen.
4. **The earlier proposals:**
   - #3 (the base rate before the break-and-retest), #6 (the 08:30 straddle only) and #7 (tight patterns) stand.
   - #1, #4 and #5 are taken up in PLAN-1, CHECKLIST rows 40-41 and the judging protocol.

## What to stop doing (row 39)

- **Transforming the micro-pattern streams** (B2, A, B1, W, the pullbacks).
  - The opposite side is negative in every cell (pooled); the same side lies between -0.06 and +0.05 in every cell.
  - Done; do not retry with other multipliers.
- **D2 at 10:00 NY.** Without the one crash trade it is negative in P2. The 08:30 half is already in PLAN-1.
- **Fading the release** (the straddle reversed): -0.317 / -0.530.
- **FOLLOW in any form.** It flips in every cell.
- **More state readings for PLAN-1's weights before the exam read.** There are too few trades per cell.

## Questions to the measurer (row 39)

1. **RT_25 opp pays mostly outside the owner's windows** (+0.397 / +0.294 outside, +0.068 / +0.194 inside). May a
   reclaim trade be taken outside the windows? If the windows rule stands, the lead is too weak: 35 trades, about +0.13.
2. **Every lead so far is present-only.** #22, #23 and RT_25 opp lose in O1 / O2, and the absolute volatility does not
   separate the periods. Is the owner content with a rule judged on the present plus a trailing switch (proposal 3),
   reviewed every 3-6 months, or must a rule also hold in 2023-25?
3. **Asia B2 in the older years.** Its older-year check needs the first developer's detector run on 2023-25 (M1 only).
   Is it worth asking for?

# The strategist's review and proposals (2026-10-19, written 23:30-23:50 Thai by `date -u`)

**Scope.** This is a review only. Nothing here is a frozen rule.
- Every number below comes from a script in this folder; its output is the `out_*.txt` of the same name.
- **The exam was not loaded.** `slib.py` reads the M1 store with a row filter that stops before 2026-04-18, reads ticks
  only for earlier days, and asserts this.
- **How the checks were run:**
  - The quick checks use M1 bars with the team's M1 cost model (`mlib.py`; 5 hand-worked tests in `test_mlib.py`,
    "5 passed in 0.71s").
  - The two leads were re-run on the real ticks (`orb_ticks.py`), and the ticks agree with M1 within 0.01 R.
  - Three trades were traced by hand against the bars (`out_trace.txt`).
- **"Older years"** means the pre-exam history: O1 = 2023-10-18 .. 2024-10-17, O2 = 2024-10-18 .. 2025-10-17. I used
  it only as a label of the regime, never to choose a setting (question 1 below).

## 1. Why it does not pay yet: the five most likely reasons, ranked

**R1. The entry trigger carries no information about direction at its scale, and context filters cannot add it.**
- **The measurement** (`struct_split.py`): every B2 (P3, 690 trades) and W (P4, 224) trade was split at its decision
  into with / against / mixed for:
  - the H1 and M15 swing structure;
  - the 4-hour move;
  - the day so far;
  - the H4 EMA-50 tide.
- **No split is steady.** Examples, R in P1 / P2:
  - B2 with the H1 structure: -0.017 / -0.060;
  - B2 against it: -0.019 / -0.094;
  - B2 with H1 and M15 both: -0.042 / +0.147 (32 / 26 trades);
  - W with the H4 tide: -0.024 / +0.197;
  - "H1 against and the 4-hour move against": +0.228 / -0.160, which flips sign between the parts.
- **The team's own results agree:**
  - the 82-reading model has AUC 0.503;
  - the 72 cells of P3 found nothing steady;
  - the exits Xa / Xb / Xab all land at -0.03 to -0.04.
- **What differs in my checks:** the shapes that were positive in both parts are anchored on a time and on the
  liquidity everyone sees (the 13:00 Thai opening range; a level everyone sees, broken and then reclaimed). None is
  anchored on an M1 / M5 micro-pattern.

**R2. The pass bar cannot see +0.15 R with these trade counts, while each extra setting makes a false lead more likely.**
- **The measurement** (`power.py`): bootstrap from the real R distributions (SD 0.80-0.83 R).
- A rule whose true edge is **+0.15 R passes "both parts >= +0.15" only 23-25 % of the time**, at any trade count.
  - At a true +0.20 it passes 45 % with 60 trades a part and 76 % with 350.
- A rule with no edge passes 0.6-0.7 % of the time at 60 trades a part.
  - With 300 settings tried, the chance of at least one false pass is **0.84-0.86**.
- To exclude 0 at a true +0.15, a part needs about 110-116 trades; 224-237 trades give 80 % power.
- **So the team throws away real moderate edges about 3 times in 4**, and will sooner or later freeze a lucky cell.
  This is one reason the trail looks like "everything fails".

**R3. The market changed regime under the data: the leads found in P1 / P2 lose in 2023-25.**

The two learning parts are themselves two different markets (`orb_season.py`):

| | O1 | O2 | P1 | P2 |
|---|---|---|---|---|
| ADR20, median (USD) | 30 | 43 | 84 | 172 |
| H1 ATR, median (USD) | 4.8 | 7.8 | 16.0 | 27.7 |

- **The 13:00 Thai opening-range break** (`orb_sens.py`, counted by `orb_count.py`):
  - positive in **18 of 18 settings in P1 and 17 of 18 in P2** (the one exception is -0.006);
  - positive in **1 of 18 in O1** (+0.001) **and 0 of 18 in O2**.
- **The reclaim in the owner's windows** (`reclaim.py`, `reclaim.py old`):
  - +0.308 / +0.311 R in P1 / P2;
  - **-0.160 / -0.242** in O1 / O2.
- **Costs explain only part of it.** Cost per R for the opening-range break was 0.20 R in O1 and 0.04 R in P2. Before
  costs its R was still only +0.07 / +0.01 in O1 / O2.
- **What it means:**
  - "Both parts" asks one rule to hold across a 2 x change in volatility, and the exam is a third regime.
  - The owner's own principle ("live in the present; revise every 3-6 months") fits the data better than a timeless
    rule does.
  - Every frozen rule therefore needs a stated season reading, and the older years can label it present-only but cannot
    vet it.

**R4. The break-and-retest of a horizontal level, as V3-2 is about to build it, starts from a losing base rate.**
- **The measurement** (`retest.py`), on the levels everyone sees:
  - the previous day's high and low;
  - the Asian range's high and low (07:00-13:00 Thai).
- **The rule:** after the break, the retest, and the M5 turn, trade with the break; the stop 0.25 H1 ATR past the
  retest's extreme; the target 2 R; at most 120 minutes.
- **The result:** **-0.221 / -0.390 R, 24 % / 23 % winners** (41 / 47 trades). Half the trades hit the stop.
- **The broken level is mostly reclaimed.** The reclaim side is the one that paid in P1 / P2: all hours -0.005 /
  +0.112, and +0.31 / +0.31 in the owner's windows (`reclaim.py`).
- Trade 4's own level was a rising trendline and every TF up to H1 was LH / LL. Those conditions must be measured
  against this base rate, not assumed.

**R5. Checked and cleared: these are not the reason now.**

| Item | Measured | Script |
|---|---|---|
| Costs | the cost of one trade is 1.2-4.7 % of R (W, B2, the opening-range break, the reclaim); 3 x the demo spread would cost at most 0.08 R | `costs.py` |
| R against USD | corr(risk, R) = -0.054 .. +0.027 in all four cells; USD swings come from a few wide-risk trades | `rusd.py` |
| The Asia window as a buy-side drift | W in Asia: sells +0.184 R in P1; buys +0.178 and sells +0.188 in P2 - both sides pay | `drift.py` |
| The size of the hourly drift | the Asia block 07-09 Thai: +2.28 / +6.84 USD a weekday (mean / SE 1.1 / 1.3) - too small to trade alone | `drift.py` |

**Hypotheses I have not measured:**
- The owner's real-account spread, and the fills at the release second (question 2).
- **An outside source I must flag** (Ed Steer via Money Metals / FXStreet, 2026-07-12/13): "gold up 12.9 % in Asian
  hours, down 15 % in North American hours in H1 2026". It overlaps the exam period, so no rule may be designed on it.

## 2. Proposals, ranked (each one goes through the measurer)

Every proposal also needs the owner's acceptance (DEV2_PROMPT "Acceptance"): 12 rule-picked trades drawn per rule (6
winners, 6 losers) for the owner to accept or reject before any result counts.

| # | Proposal | Quick check (P1 / P2) | Who | Pass bar |
|---|---|---|---|---|
| 1 | The opening-range break at 13:00 Thai | ticks +0.206 / +0.120 R, 59 / 60 trades (0.94 a weekday); grid cells > 0: 18 of 18 in P1, 17 of 18 in P2 | dev1 (needs no swings) | both parts >= +0.15 on the ticks with >= 55 trades each, and >= 15 of 18 neighbours > 0 in both |
| 2 | The reclaim of a level everyone sees, in the owner's windows | ticks +0.312 / +0.310 R, 19 / 22 trades | dev2 (entry 3, the fake break at a range edge) | both >= +0.15 with >= 30 trades each, after adding dev2's box edges |
| 3 | The base rate before the break-and-retest rule | -0.221 / -0.390 R on horizontal levels | dev2 (entry 1) | the aligned subset >= +0.15 in both parts and >= 0.3 R above the base rate; otherwise route those events to #2 |
| 4 | A season reading in every frozen rule, re-fitted monthly | grid cells > 0: 1 / 0 of 18 in O1 / O2, 18 / 17 of 18 in P1 / P2 | the measurer + dev1 | the out-of-sample months pooled >= +0.15 |
| 5 | The judging protocol | `power.py` | the measurer | (a process change) |
| 6 | The NY window: stand aside, except a straddle at the data minute | the 08:30 straddle +0.459 / +0.114 R (41 / 59); with +1 USD cost +0.368 / -0.031 | dev1 (owns the news detector A1) | both >= +0.15 at +0.5 USD release slippage |
| 7 | Prefer tight patterns (a small risk in entry-TF ATRs) | the lowest tercile beat the highest in all 4 cells | dev1, in P5 | the kept trades >= +0.15 in both, judged on the same candidates |

### 1. The opening-range break at 13:00 Thai (the owner's "London 13-14", on the Thai clock)
- **The idea:** the first 15 minutes after 13:00 Thai set a range; trade the first M1 close beyond it.
- **Why it should work (hypothesis):**
  - 06:00 UTC is when the Shanghai afternoon session (SGE 13:30 Beijing, about 12:30 Thai) and Europe's early desks
    overlap. New participation arrives, and the first break carries.
  - The London-clock open (08:00 London) loses in every period for the same rule (L15 k2 X60: -0.119 / -0.039 / -0.116
    / -0.229). That matches the measurer's B2 split, where the Thai-clock hour pays and London's clock does not. Two
    independent rule families point at the same hour.
  - Outside, the closest practice is the London / Asian-range breakout (MQL5 blog "London Breakout on Gold: 3.7 Years of
    Backtests"; TradingView "GOLD Asian Range Breakout Signals"). These are unverified retail claims, used here as
    hypotheses only.
- **The quick check:**
  - On M1 (`opens.py`, `out_opens.txt`), with the rules written before: +0.205 / +0.129 R, 54 % / 53 % winners, +113.5
    / +192.3 USD at 0.01 lot.
  - On the ticks (`orb_ticks.py`): +0.206 / +0.120 R.
  - The grid (`orb_sens.py`: L 10 / 15 / 30 minutes, the target 1.5 / 2 / 3 R, out after 60 / 120 minutes) has 18 of
    18 cells positive in P1 and 17 of 18 in P2. P1 ranges +0.001 .. +0.391, P2 -0.006 .. +0.181.
  - It loses in O1 / O2 (R3): it is present-only.
- **The exact test:**
  - On the ticks, P1 / P2, every weekday.
  - The range is the high / low of the M1 bars 06:00-06:14 UTC; skip the day if the range is above 1.5 x the H1
    ATR(14).
  - Entry at the first M1 close beyond the range between 06:15 and 07:15 UTC, at the first tick after that bar's close.
  - The stop at the range's other side; the target 2 R; out after 60 minutes; one trade a day.
  - Then **one** change, written before it is run: no trade when the owner's next H1 level (`zones.levels_at`) in the
    break's way is closer than 2 R ("target the next zone").
  - Report the weekly table, the grid as the robustness table, and the 12 drawn trades.
- **The pass bar:** as in the table. As it stands it fails, because P2 is +0.120.

### 2. The reclaim of a level everyone sees, in the owner's windows (the fake break at the range edge)
- **The idea:** the previous day's high / low or the Asian range edge breaks (an M5 close 0.1 H past it). Within 2
  hours price closes back inside by 0.1 H. Trade back into the range.
  - The stop goes 0.25 H past the break's extreme; the target 2 R; at most 120 minutes.
- **Why it should work:**
  - Stops cluster just past the levels everyone sees (Osler, NY Fed 2003, already in the notes). A break that cannot hold
    beyond them has used up that fuel.
  - OWNER_GOALS: breaks fail 65-74 % of the time.
  - The owner's own playbook ("sweep and reclaim") says the same.
- **The quick check:** ticks +0.312 / +0.310 R (19 / 22 trades, 0.3 a weekday). All hours -0.005 / +0.112 (65 / 68).
  Outside the windows -0.135 / +0.017. Negative in O1 / O2 (R3).
- **The exact test:** dev2's V3-2 entry 3 with these levels plus its own range-box edges and the x2+ H1 levels, to raise
  the count. Only in the owner's windows; on the ticks; one position at a time; the 12 drawn trades.

### 3. Measure the base rate before building the break-and-retest (V3-2 entry 1)
- **The idea:** report V3-2's retest entry side by side with the horizontal base rate (`retest.py`: -0.221 / -0.390
  R). Then split it by the owner's conditions:
  - LH / LL (HH / HL) on every TF up to H1;
  - a trendline, not a horizontal level;
  - the first lower high after the failed retest.
- **Why:** R4. Without those conditions the retest is mostly reclaimed. The owner's trade 4 had all of them.
- **The pass bar:** as in the table.

### 4. A season reading in every frozen rule, and a monthly re-fit (the owner's "live in the present")
- **The idea:**
  - Each candidate names, before its run, the season it is for: e.g. H1 ATR(14) at the decision >= 12 USD, or ADR20
    >= 60 USD (P1's medians are 16.0 and 84).
  - Outside that season it stands aside ("trades less, not never").
  - A fixed, small menu (#1, #2, Asia B2 / P5, #6) is chosen month by month by its trailing two months.
  - Only the out-of-sample months are judged.
- **Why:** R3. Every lead so far is present-only, so the system's skill must be to know the present.
- **The test:** the walk-forward over P1 + P2 (`precursors/wf.py` exists), with O1 / O2 reported as a label.
- **The pass bar:** the out-of-sample months pooled >= +0.15 with >= 100 trades.

### 5. The judging protocol (the measurer)
- At most 5 hypotheses a round, each written before it is run, with the number of settings tried.
- Report the pooled P1 + P2 mean with its 95 % range, and the per-part sign.
- Require a positive grid neighbourhood (as in `orb_sens.py`).
- No "lead" from a cell under 40 trades, or from a split of a one-position stream. Judge a filter on the same
  candidates.
- **Aim the design at a true +0.25 R**, so that the fixed +0.15 bar is passed reliably (at 125-350 trades a part it passes 56-77 % of
  the time at a true +0.20 and 97-100 % at +0.30; `power.py`).

### 6. The NY window: stand aside, except a straddle at the data minute
- **What was measured in P1:**
  - every NY family loses in P1: W -0.090, the first leg followed -0.258, faded -0.132, the opening-range break -0.089,
    the retest -0.566;
  - P2 is mixed;
  - the developer: 10:00-10:30 NY is the worst bucket.
- **The idea:** the market shows the side at the data minute; a straddle takes whichever side moves.
- **The quick check** (`news_follow.py`): the S2 straddle on every 08:30 NY minute, held 30 minutes: +0.459 / +0.114 R
  (41 / 59). With +1 USD release slippage: +0.368 / -0.031. At 10:00 NY, P2 rests on a few large wins (22 % winners).
  Fragile to the costs.
- **The test:** on the ticks, every 08:30 and 10:00 NY minute, with the release-second spreads; extra slippage 0 / 0.5 /
  1 / 2 USD; held 15 / 30 minutes.

### 7. Prefer tight patterns (a small risk in entry-TF ATRs) - a small lead, for P5
- **The quick check** (`rusd.py`), lowest against highest tercile of risk in entry-TF ATRs:

  | | P1 | P2 |
  |---|---|---|
  | B2, lowest tercile | +0.013 | +0.079 |
  | B2, highest tercile | -0.092 | -0.031 |
  | W, lowest tercile | +0.211 | +0.095 |
  | W, highest tercile | -0.121 | -0.037 |

  The same order in all 4 cells.
- **The test:** on P5's catches, a cap at P1's lower-tercile cut (about 4 entry-TF ATRs), judged on the same
  candidates.

## 3. What to stop doing
1. **Adding context filters to the M1 / M5 micro-pattern stream** (B2 / W). This review found 13 splits with nothing
   steady; the developer's P3 had 72 cells; the 82-reading model gave AUC 0.503. M1 entries are negative in every B2
   variant.
2. **Reading "leads" from small cells or from splits of a one-position stream** (the developer's own P3 finding: the
   replacement trades).
3. **More symmetric 5 / 10-USD first-passage direction studies at clock moments.** They have been done many times, and
   they ask a question the leads above do not depend on.
4. **Treating costs and R against USD as open causes.** Both were measured small (R5).
5. **The NY-open pattern trades as they are.** Keep the window by standing aside or by #6, until an NY-specific
   mechanism is shown.
6. **The 1-minute follow-the-news rule** (`news_follow.py` FOLLOW): +0.046 / -0.128 at 15 minutes, worse with costs.
   Not worth a developer's time.
7. **Designing on outside sources that cover 2026-04 .. 2026-10.** They leak the exam.

## 4. Questions to the measurer
1. **The older history.** May 2023-10 .. 2025-10 be read as a regime label before the exam? I read it only for the
   opening-range break and the reclaim, and chose nothing from it.
2. **The owner's real account.** The XAUUSD spread at 07:00 and 13:00 Thai and at 08:30 NY, and the slippage on stop
   orders at a release.
3. **The 08:30 NY data minute** (19:30 / 20:30 Thai) comes before the NY open window. Does the owner count releases as a
   window (OWNER_GOALS lists them as moments)?
4. **The 13:00 Thai opening range.** Is the first 15-minute range of 13:00 Thai what the owner means by "London 13-14"?
   That is the acceptance question for #1.

## 5. Files (this folder)
| Topic | Scripts | Outputs |
|---|---|---|
| Shared helpers | `slib.py`, `mlib.py` + `test_mlib.py` | |
| Power of the pass bar | `power.py` | `out_power.txt` |
| R against USD | `rusd.py` | `out_rusd.txt` |
| Hourly drift | `drift.py` | `out_drift.txt` |
| With / against the structure | `struct_split.py` | `out_struct_split.txt` |
| News continuation | `news_follow.py` | `out_news_follow.txt` |
| The window opens | `opens.py` | `out_opens.txt` |
| The opening-range grid and seasons | `orb_sens.py`, `orb_season.py` | `out_orb_sens.txt`, `out_orb_season.txt` |
| Tick re-runs | `orb_ticks.py` | `out_orb_ticks.txt` |
| The grid count | `orb_count.py` | `out_orb_count.txt` |
| Break and retest | `retest.py` | `out_retest.txt` |
| Reclaim | `reclaim.py` | `out_reclaim.txt`, `out_reclaim_old.txt` |
| Costs | `costs.py` | `out_costs.txt` |
| The hand trace | | `out_trace.txt` |
| Trade lists | | `*_trades.parquet` |
| Row 39: the tick simulator | `tsim.py` + `test_tsim.py` + `plant_tsim.py` | `out_plant_tsim.txt` |
| Row 39: the transformations | `transform.py`, `lead_checks.py`, `recheck_transform.py` | `out_transform.txt`, `out_lead_checks.txt`, `out_recheck_transform.txt`, `transform_trades.parquet` |
| Row 39: the lead in the older years, the side switch | `rt_old.py`, `side_switch.py` | `out_rt_old.txt`, `out_side_switch.txt`, `rt_old_trades.parquet` |
| Row 39: the state weights | `state_weights.py` | `out_state_weights.txt`, `state_weights_trades.parquet` |
