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
