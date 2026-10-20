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
