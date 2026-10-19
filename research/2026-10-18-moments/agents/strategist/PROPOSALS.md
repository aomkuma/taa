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
