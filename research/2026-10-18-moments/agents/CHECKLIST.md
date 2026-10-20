# The checklist of methods tried (Setup OWN, gold) - kept current

Owner (2026-10-20, about 12:25 Thai): "if the result is a loss and you say it doesn't work, I don't want you to stop -
keep finding ways; tick the trade that doesn't work as failed in a checklist, find a new way, and keep adding to the
checklist, to see which kind trades profitably in the long run."

**The goal (fixed):** >= +0.15 R a trade after costs in both learning parts (P1 2025-10-18 .. 2026-01-15, P2 2026-01-16
.. 2026-04-17), about 2-3 trades a day, then one exam read (2026-04-18 .. 2026-10-17).

**Also reported:** the pooled P1 + P2 mean with its 95 % range.

**Verdicts:**

| Verdict | Meaning |
|---|---|
| PASS | the goal is met in both parts with enough trades (>= 30 a part) |
| PARTIAL | positive in both parts, below the goal or with too few trades - a lead to build on |
| FAIL | negative, or a sign that flips between the parts - kept with its lesson, never retried as it was |
| OPEN | being built or measured |

Sources: `precursors/notes.md`, `DEV_LOG.md`s, `strategist/PROPOSALS.md`, `audit2/AUDIT.md`.

| # | Method | P1 R | P2 R | Trades P1 / P2 | Verdict | The lesson |
|---|---|---|---|---|---|---|
| 1 | LV3: with every larger TF, sell the bounce into an earlier level (learning 12 months / exam) | +0.013 | exam -0.139 | 66 / 95 | FAIL | its components measured at chance; the exam lost |
| 2 | V2b: the library of researched pictures, the same core codes | -0.021 | exam -0.169 | 221 / 187 | FAIL | the same full picture almost never repeats |
| 3 | V2s: the same M5 + M1 situation | -0.020 | exam -0.085 | 445 / 278 | FAIL | a lean in the next half hour, but trades lose after costs |
| 4 | V2e: 28 entry variants on V2s (a dip limit, an M1 turn, a stop order) | all < 0 | - | - | FAIL | the entry form did not rescue a sideless signal |
| 5 | The present library (clock-sampled moments) | -0.077 | exam -0.073 | - | FAIL | - |
| 6 | Every layer together, a probability model | side-blind exam -0.003 | with the side +0.052 | 629 / 267 | FAIL | below the goal; the 82 readings had an AUC of about 0.50 |
| 7 | The owner's cut: 2-3 a day, the heavy / wrong-way losers out | -0.068 | -0.082 | - | FAIL | cutting losers after the fact does not make an edge |
| 8 | In fast, out fast: 10 USD, holds of 15-120 min (2023-24 / 2025-26) | -0.084 .. -0.107 | -0.027 .. +0.048 | - | FAIL | - |
| 9 | M15: 10 USD in 3-4 bars (the aligned phase / + an M5 pullback) | -0.043 / +0.005 | -0.065 / -0.089 | 4.4-5.5 / 1.5-2.5 a day | FAIL | - |
| 10 | Inside a range: fade its edges | -0.046 .. -0.155 | -0.013 .. +0.047 | - | FAIL | - |
| 11 | The surrender rule (no run -> out) on aligned M15 entries | +0.116 | < 0 | - | FAIL | it helped P1 only |
| 12 | The side by the phase (a phase switch) | +0.097 | -0.132 | - | FAIL | the phase's meaning flipped between the parts |
| 13 | The M1 pullback in the H1 / H4 trend, the fast turn, 3 R | -0.099 | -0.032 | 18-29 a day | FAIL | the H1 / H4 swing reading lags; far too many trades |
| 14 | The same with the trend from M15's current structure, active hours | -0.101 | -0.268 | 5.3 / 2.4 a day | FAIL | the losers sat in choppy M15 and right after V turns |
| 15 | No stop loss | - | - | - | FAIL | a 22-50 USD account is wiped on the first trade |
| 16 | The level break with the volume (sell support / buy resistance), 36 settings | best -0.058 | +0.144 | 150 / 153 | FAIL | the levels were made by the move itself, not real S/R; 61 % of the losers went the wrong way |
| 17 | B2: chart patterns at the owner's H1 levels, waiting for the structure, all day | -0.026 | -0.014 | 352 / 348 | FAIL | the M1 / M5 micro-swing patterns carry no direction; about 90 % of the losers came from the entry |
| 18 | The same entered at the breakout (A), or with the pullback stop (B1) | -0.047 / -0.043 | -0.045 / -0.082 | - | FAIL | waiting helps a little; the tight stop is worse |
| 19 | B2 + the exit changes (the pattern's invalidation, break-even + trail) / no late entry / sweep-turn with M5 | -0.024 .. -0.048 | -0.037 .. +0.078 | - | FAIL | the exits were not the problem |
| 20 | B2 only in the owner's windows (Asia + London + NY open + 2 h) | -0.024 | +0.036 | 115 / 109 | FAIL | NY lost (-0.090 / -0.066); NY 10:00-10:30 the worst |
| 21 | B2, Asia 07:00-09:00 Thai only | +0.074 | +0.182 | 41 / 38 | PARTIAL | positive in both, but +0.004 by decision time: fragile |
| 22 | The 13:00-Thai opening-range break (strategist) | +0.206 | +0.120 | 59 / 60 | PARTIAL | positive in 18 / 18 and 17 / 18 settings in P1 / P2, but lost in 2023-25 (a regime) |
| 23 | The reclaim of a level everyone sees, in the owner's windows (strategist) | +0.312 | +0.310 | 19 / 22 | PARTIAL | too few trades; lost in 2023-25 |
| 24 | The NY 08:30 data-minute straddle, 30 min (strategist) | +0.459 | +0.114 | 41 / 59 | PARTIAL | fragile to the release slippage (+1 USD: +0.368 / -0.031) |
| 25 | Break and retest of a level everyone sees (strategist) | -0.221 | -0.390 | 41 / 47 | FAIL | the broken level is usually reclaimed (-> #23) |
| 26 | At a window's open in the M15-H1 (EMA proxy) direction, a 3-5 USD stop | 10 first in 0.10-0.38 | - | - | FAIL | the entry must be the entry TF's own turn, with the stop at its extreme |
| 27 | An EMA20 / last-candle / 3-day D1 bias for the day's side | closed its way 0.48 | 0.54 | 58 / 56 days | FAIL | the side needs real structure (H1 -> D1), not these proxies |
| 28 | The NY 1-minute follow-the-news rule (strategist) | +0.046 | -0.128 | - | FAIL | - |
| 36 | The daily plan: Asia B2 + London 13:00 ORB + NY 08:30 straddle (30 min), one position at a time (`precursors/combo.py`) | +0.241 (+0.06..+0.42) | +0.133 (-0.05..+0.31) | 141 / 157 (2.2-2.4 a day) | PARTIAL | pooled +0.184 (+0.06..+0.31), the first combination whose pooled range excludes 0; with +1 USD release slippage +0.215 / +0.078 |
| 37 | #36 weighted by the market state (`precursors/regime.py`): the range pieces (Asia B2, London ORB) pay in sideways / mixed D1 states and lose in a trend; the breakout piece (NY straddle) pays in a trend. Half weight where a piece is out of its state | weights from P1: +0.280; by mechanism: +0.329 | +0.143 / +0.184 | same | PARTIAL / PASS by number | the mechanism weights were chosen after seeing both parts, so the exam decides; with +1 USD release slippage, by mechanism +0.301 / +0.130 |

| 40 | D1: the 13:00-Thai ORB core / + no H1 level within 2 R (D1L) / + the season ADR20 >= 63.3 (S) / D1L+S (dev1; 0.07 slip) | +0.206 / +0.086 / +0.250 / +0.306 | +0.120 / +0.604 / +0.120 / +0.604 | 59-60 / 21-16 / 53-60 / 16-16 | PARTIAL | the core misses only in P2; D1L+S passes on 16 trades a part (too few); older years O1 / O2 core -0.083 / -0.066; sells +0.488 / +0.179 against buys +0.050 / +0.058 (a lead); 3 grid cells >= +0.15 in both, seen after the run (leads) |
| 41 | D2: the straddle at 08:30 + 10:00 NY, 30 min (+0.5 USD slip) | +0.221 | +0.125 | 94 / 109 | FAIL | P2 rests on one crash trade (2026-01-29 10:00 NY, +27.5 R); without it -0.128. 08:30 alone +0.360 / +0.237, 10:00 alone +0.113 / +0.033. The NY open itself (09:30) loses (-0.208 / -0.289); after the open the first 30 min go against the straddle, the second with it |
| 42 | The transformations of 11 FAIL families, 264 cells: the opposite side, the stop x1.5 / x2, the target x0.75 / x0.5 / 1 x the stop (strategist, row 39; spread only) | best per family <= +0.012 except #25 | - | 41-1863 a part | FAIL | the opposite side only helps a rule whose entry picks a direction; a wider stop pulls R to 0, a nearer target lifts win % but not R; the straddle reversed loses heavily (-0.317 / -0.530), so the release minute's direction is real |
| 43 | The break-and-retest traded the other way, back into the range, 1 R target (RT_25 opp; strategist) | +0.261 | +0.255 | 41 / 46 | PARTIAL (lead) | seen after the run; the measurer's tick loop re-derives 85 / 87 trades exactly (+0.260 / +0.240 without the family's break exit); mostly outside the windows (outside +0.397 / +0.294, inside +0.068 / +0.194); 37 of 87 overlap #23; lost in 2023-25 (-0.203 / -0.150) |
| 44 | State weights per PLAN-1 piece from five more readings (D1 volatility, ADR20, H4 percentile, D1 structure, side vs D1), chosen on P1 | - | P2 +0.130 .. +0.141 vs +0.137 unweighted | 141 / 157 | FAIL | cells of 2-34 trades are too small to choose weights; keep PLAN-1's mechanism weights; the ORB-in-a-trend cut is the only one the older years confirm |
| 45 | When the leads (#22 ORB, #23 reclaim, #43 RT_opp) pay: 12 readings known before entry (range / season / D1-H4 efficiency and ADX / trailing failed breaks / session range / spread / time since a big bar / the stream's own trailing R), 672 rules chosen on O1 + P1, read on O2 + P2 (strategist) | - | - | O1-P2 | FAIL | no market reading separates; the leads pay as a block of time from about 2025-10; only the stream's own trailing paper result sees it (with a lag): the three leads' summed R O1 / O2 / P1 / P2 -78 / -71 / +29 / +26 -> with N = 20 -13 / -7 / +25 / +24 (re-derived by the measurer exactly) - a lead for a walk-forward with N fixed in advance |
| 46 | **PLAN-1, the one exam read** (2026-04-18 .. 2026-10-17; `dev/plan1.py --exam`, read by the measurer 2026-10-20 17:35 Thai; spread only, slippage 0) | P1 +0.249 / P2 +0.137 | **exam +0.129** (-0.007..+0.265) unweighted; by mechanism +0.117; from P1 +0.126 | exam 330 (2.54 a weekday) | PARTIAL | positive out of sample (+344.87 USD at 0.01 lot, max DD 108.12, worst -34.72, streak 7), below the goal. The pieces: NY straddle +0.285 (holds: +0.467 / +0.119 / +0.285), Asia B2 +0.105, London ORB +0.023 (fading: +0.213 / +0.124 / +0.023). The state weights did not help (Asia B2 in a trend +0.376 in the exam, negative in P1): state weights from one or two parts do not carry. Re-derived by the measurer: London 122 / 122, NY 101 / 101 exactly, B2 108 trades 0 faults |
| 47 | SW-20, the own-result switch (real trade only while the last 20 paper trades' mean R > 0; N fixed before), judged on years no switch study had seen: ORB + RC_win + RT_opp, 2021-09 .. 2023-10 on M1 | always Y2 -0.116 / Y3 -0.079 | switched Y2 -0.073 (175, -12.8 R) / Y3 -0.041 (215, -8.8 R) | 1292 events, 390 traded | FAIL | the switch halves the loss but the leads lose in those years whatever the recent record says; on PLAN-1's pieces it lowers every period (P1 +0.249 -> +0.205, exam +0.129 -> +0.100). The M1 store starts 2021-09, not 2020-09: Y1 holds 1.5 months. Re-derived by the measurer: its switch equals mine on 1292 / 1292 trades; the streams reproduce O1 exactly |

**In progress (OPEN):**

| # | Method | Who | What it adds |
|---|---|---|---|
| 29 | V3 (V3-1 the swings / structure done and measured 2026-10-20; V3-2 next): the owner's framework - the side from H1 -> D1 structure, the M15-H1 trend, the entry TF M1 / M5 / M15 by volatility, the pullback turn at a level, the stop at the turn, the owner's windows (NY to + 4 h) | dev2 | the owner's own reading, on trade-size swings |
| 30 | The owner's playbook: break and retest (against #25's base rate), the aligned consolidation, the fake break at a range edge (= #23), the fake first leg at an open | dev2 | - |
| 31 | The opening-range break refined: the H1-level change, a season reading, the older years | dev1 (D1) | done -> row 40 |
| 32 | The data-minute straddle at 08:30 / 10:00 NY, slippage 0-2 USD, per 30-min bucket | dev1 (D2) | done -> row 41 |
| 33 | The owner's pattern set on trade-size swings (M / W, triple tops, H&S, channels, A-B-C-D-E, bases), tight patterns | dev1 (P5) | - |
| 34 | A daily plan combining the PARTIAL pieces in their own windows (Asia B2 / reclaim, London ORB, NY straddle) | the measurer | done -> rows 36-37 |
| 38 | PLAN-1 frozen for the one exam read (below): needs an exam-capable runner of the three pieces | dev1 (restarted 12:46 Thai), the measurer reads | the measurer's own tick re-derivation `precursors/check_plan1.py` reproduces London 119 / 119 and NY 100 / 100 (4 stale stops in `news_follow_trades.parquet`), B2 79 trades 0 faults |
| 39 | The transformations of every FAIL, and the state weights per piece in more states | the strategist | done -> rows 42-44 |

## PLAN-1 - frozen for the one exam read (2026-10-20 12:29 Thai)
- **Asia:** the first developer's B2 at the owner's H1 levels, entries 07:00-09:00 Thai
  (`dev/p4_trades.py` variant W, the Asia window, by entry time).
- **London:** the 13:00-Thai opening-range break. The range is 06:00-06:14 UTC, the day is skipped if the range is
  wider than 1.5 H1 ATR, the entry is the first M1 close beyond it 06:15-07:15 UTC, the stop at the other side, the
  target 2 R, out after 60 minutes (`strategist/orb_ticks.py`).
- **NY:** the straddle at 08:30:00 New York - a buy stop at the ask + 2, a sell stop at the bid - 2, held 30 minutes
  (`strategist/news_follow.py` "STRADDLE 30m").
- **The weights, by the D1 state before the entry** (the 20-day efficiency with P1's terciles 0.116 / 0.264): half the
  risk for Asia B2 and London ORB in a "trend" state, half for the NY straddle in a "sideways" / "mixed" state, full
  otherwise.
- **The second variant,** declared now: the weights from P1 only (Asia B2 half in a trend; the NY straddle half in
  sideways / mixed for slippage 0, sideways only with +1 USD).
- **One position at a time;** the exam is read once.
- **Costs: the spread only** (owner, 2026-10-20 12:30 Thai: slippage dropped as uncontrollable). Spread-only on the
  learning parts: unweighted +0.252 / +0.140, weighted by the state +0.341 / +0.191 (from the trades' own risk, the
  0.07 entry slippage added back).
