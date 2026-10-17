# Setup OWN - the owner's own trade: the moments when gold runs

The owner's goals and principles are in `docs/OWNER_GOALS.md`; the setup's place among the owner's trades in
`docs/OWNER_TRADING.md` ("Setup OWN"). This file holds the method, the hypotheses (written down before any outcome
is computed) and the results, month by month as they finish. Results describe the past, never a promise.

## Data and window

**The latest six months only (owner, 2026-10-17: "focus on the bot and backtests over the latest 6 months; we
revise the setups every 3-6 months").** Gold (XAUUSD, FBS-Demo) M1 in `data/history` ends 2026-10-14 08:18 UTC,
so the window is **2026-04-14 .. 2026-10-14**, with 20 trading days before it as warm-up for the measures. It
copies the revision cycle: the rules are **fitted on the first three months (2026-04-14 .. 07-14)** and
**judged once on the last three (2026-07-14 .. 10-14)**, untouched until the method is frozen. The next
revision repeats this on the then-latest six months. The five-year store (`data/history_old` + `data/history`,
loader `research/2026-10-18-moments/gold.py`) serves only as background, never as the judge.

## The moments

All clock times DST-aware (zoneinfo), on weekdays:

| Moment | Local time | Note |
|---|---|---|
| Asia | 09:00 Asia/Shanghai (01:00 UTC) | the Asian peak in every year |
| Tokyo | 09:00 Asia/Tokyo | |
| London | 08:00 Europe/London | |
| COMEX | 08:20 America/New_York | gold futures open |
| New York data | 08:30 America/New_York | the release slot |
| New York cash | 09:30 America/New_York | |
| Release | its time (CPI, Employment Situation, PPI, PCE, GDP advance 08:30 ET; FOMC 14:00 ET) | official calendar, `research/2026-10-18-moments/us_releases.csv` |

Moments within 15 minutes of each other on a day are one row with all their tags. Control rows: the same
features at every other half hour of the trading day, for base rates.

## Measures (relative, as of the moment, from closed bars only)

- **Usual run U:** the median, over the previous 20 trading days, of the 30-minute high-low range after this
  moment's clock time. Every distance below is in units of U unless named otherwise.
- **Contraction:** the M5 Bollinger(20) width and ATR(14) as percentiles of the previous 20 trading days of M5
  bars; the 60 minutes before the moment as a share of U. **Squeeze** = BB-width percentile at most 20.
- **The largest timeframe is H1** (owner, 2026-10-17): no H4 or D1 analysis in this setup.
- **Pools:** the previous broker day's high/low (a level everyone sees, read from the bars, not a D1 analysis),
  today's session ranges so far (Asia 00:00-07:00 UTC, London from 07:00 UTC), the previous New York session's
  range (13:00-21:00 UTC), the H1 and M15 chart-read levels (`ChartReadFrame` levels, default parameters), round
  numbers (multiples of 50 USD: at today's prices a multiple of 10 lies within 0.25 U almost always). **At a
  pool** = the nearest pool within 0.25 U of the price.
- **Flow:** the swing structure now (`ChartReadFrame.structure_now`, HH/HL = up, LH/LL = down, the bot's chart-read
  parameters) of H1, else of M15, from the last closed bars; else none. **Clear picture** = H1 and M15 both the
  same way. (Revised 2026-10-17 before any outcome was computed: the market-map states read TRANSITION on H1 in
  65 % of the fit rows and left 70 % without a flow; the structure leaves 16 %.)
- **Pool side:** a pool *ahead* lies in the flow's direction from the price, *behind* against it.
- **Regime:** the 20-day average daily range and that range over the median spread.

## The three playbooks and their exits

| Playbook | Entry (within 30 minutes of the moment, M1 closes) | Stop |
|---|---|---|
| P1 break-and-hold | a close beyond the nearest pool, and the next bar does not close back | beyond the pool's other side + 0.1 U |
| P2 sweep-and-reclaim | price trades beyond a pool, then closes back inside within 5 bars: trade back the other way | beyond the sweep's extreme + 0.1 U |
| P3 with the flow | at the moment, in the flow's direction | beyond the pre-moment hour's range + 0.1 U |

Exits (owner, 2026-10-17: "the profit we aim for is at least 5 pips; work out the risk; focus on scalps, but
when the picture is clear, hold for a short trend run"; gold 1 pip = 1.00 USD, the owner's convention):

- **Target (scalp):** at least 5 USD: half the moment's usual run (0.5 U), never less than 5 USD (= max(5 USD,
  0.5 U)); time stop 60 minutes. At the moments 0.5 U is above 5 USD every time (median target 8.5 USD in the fit
  months); at the control half hours the 5 USD floor decides 23 % of the time.
- **Clear picture -> short trend run:** when the H1 and M15 states both trend the trade's way at the entry, the
  target does not close the trade: the stop moves to lock half the target and then trails 0.5 U behind the best
  price; time stop 180 minutes (owner, 2026-10-17: "we may hold from seconds to many minutes, or 2-3 hours").
  The history is M1, so seconds show only as a target touched within the entry's minute (both the stop and the
  target in one bar still count as the stop).
- **Risk (the stop), measured:** besides the playbook's own invalidation (the table's stop), the stop at the
  70th / 80th / 90th percentile of the adverse excursion that the fit window's winners (trades that reached the
  target) took before the target, per playbook, in units of U. The fit months choose among the four; the judged
  months test the choice once. Reported in USD at 0.01 lot as well.

One position at a time; fills as the engine (next bar's open, a BUY at the ask, stops and targets on bar
highs/lows with a SELL's on the ask, both in one bar = the stop) with 7 points of slippage each way
(`research/2026-10-17-s1/s1_funnel.py`). The first harness pass (`moments.py`) also records the original exit
(target 0.5 U, the invalidation stop) for reference.

## Hypotheses (fixed 2026-10-17, before any outcome is computed)

- **H1:** squeeze, at a pool ahead (the flow's side) -> P1 in the flow's direction pays after costs, and more than
  at the same moments without a squeeze.
- **H2:** squeeze, at a pool behind -> P2 (the sweep against the flow, then back with it) pays after costs.
- **H3:** no squeeze and no pool within 0.25 U -> no playbook pays after costs (stand aside).
- **H4:** the paying playbooks' R grows with the 20-day range over the spread.

## The selector (how the system chooses in the present)

- Context cell = moment group (Asia: Tokyo and Asia opens; London; New York: COMEX, data, cash and the releases)
  x squeeze (yes/no) x pool side (ahead / behind / none / no flow): 24 cells. (Revised 2026-10-17 before any
  outcome: the five-year grid had 432 cells for 327 fit moments; the regime barely moves within three months and
  U already scales every distance; the flow is in the pool side and in each playbook's direction.)
- The fit months check themselves before the judged months are touched: each fit month is predicted from the
  other two (leave one month out).
- For each cell and playbook: the mean R shrunk toward the playbook's mean in the window (empirical Bayes,
  weight 20 trades, as `app/advisory/calibration.py`); the cell trades its best playbook only when that mean
  minus one standard error clears +0.05 R; otherwise it stands aside.
- Fitted on the window's first three months; the live bot re-fits at each revision (every 3-6 months, the
  owner's cycle) on the then-latest three months.

## Gate to the engine

On the three judged months (2026-07-14 .. 10-14), in the engine backtest (`app.cli backtest`): at least +0.15 R
a trade (tolerance +0.10), at least one trade a day on average, at least two of the three months positive.
Below it: report the gap, add candidate causes and try again - with each new rule written down here first.

## The release calendar (2026-10-17)

`research/2026-10-18-moments/us_releases.csv`, built by `build_calendar.py` from the BLS, BEA and Federal Reserve
archives: 301 releases 2021-09 .. 2026-10 (CPI, Employment Situation, PPI and PCE 60 each, GDP advance 20, FOMC
41). Check (`check_calendar.py`): gold's range in the first 5 minutes after a release over its usual range at
that clock time on the previous 20 weekdays, median by event: FOMC 9.5x, CPI 5.1x, NFP 4.8x, GDP 2.5x, PPI 2.2x,
PCE 2.0x; no release on a weekend. Five rows have no bars: three Good Fridays (2023-04-07, 2024-03-29,
2026-04-03, gold closed) and the two after the data ends. Weak rows (below 1x) are PCE/PPI days the market did
not care about, not wrong dates. Uncertain times (outside the window): 2025-12-05 PCE (neither 08:30 nor 10:00
spikes), 2025-12-23 GDP (1.6x at 08:30, 2.5x at 10:00).

## Results

### Round 1 - fit months 2026-04-14 .. 07-14 (65 trading days; the judged months not read)

Harness: `moments.py` (5,479 rows: 659 moments, the rest control half hours; 9,669 playbook entries),
`exits.py`, `select_fit.py`. R net of spread and 7 points of slippage each way; USD at 0.01 lot.

The measured stop (the adverse excursion the winners took before the target, units of U) is about the same for all
three playbooks: q70 0.37-0.38, q80 0.49-0.50, q90 0.70-0.74 U (645-1,198 winners).

| Moments, every entry, one at a time | Stop | Trades | R/trade | Win % | USD/trade | Trades/day |
|---|---|---|---|---|---|---|
| P1 break-and-hold | q70 (~6.8 USD) | 170 | +0.034 | 44 | +0.56 | 2.6 |
| P2 sweep-and-reclaim | q70 (~6.5 USD) | 188 | +0.085 | 46 | +0.83 | 2.9 |
| P3 with the flow | q90 (~11 USD) | 256 | -0.044 | 53 | -0.64 | 3.9 |
| The invalidation stops (table above) | S0 | | P1 -0.021, P2 -0.013, P3 -0.055 | | | |

- **The moments beat ordinary times:** at the control half hours the same playbooks lose (P2 -0.14 R over 386
  entries with no squeeze and no pool near; P1/P2/P3 about -0.03 to -0.10 by range tertile, 1,000+ entries each).
- **H1-H4 not supported** (fit months): H1 squeeze + pool ahead -> P1 with the flow: moments +1.10 R but 6 trades,
  controls -0.23 (44); H2 squeeze + pool behind -> P2: -0.18 (9) / -0.06 (48); H3 (nothing pays without squeeze and
  pool) holds at the controls (all negative) but not at the moments (P2 +0.27, 41, se 0.20); H4: no consistent
  rise with the range over the spread.
- **The selector fails:** each fit month predicted from the other two: **-0.309 R over 48 trades (0.74 a day)**; the
  24 cells are too thin (8-25 trades) and the cells it picks flip from month to month.
- **Pieces positive in all three fit months** (searched over session x playbook x flow and the pool kind, so
  mined, not proven): P2 at the New York cash open (09:30 ET) +0.22 / +0.34 / +0.11 R (36 trades, q70 stop);
  P1 through the previous New York session's high or low at the control half hours +0.32 / +0.13 / +0.19 (69).
  Asia P2 against the flow is positive in all three months only with the q80 stop (+0.21, 28): dropped (the stop
  would be chosen per piece).

### OWN v1 - frozen 2026-10-17 before the judged months are read

- **R-a, New York cash open:** at 09:30 ET on weekdays, P2 sweep-and-reclaim of the nearest pool within 30 minutes
  (back inside within 5 bars), entry at the next bar's open.
- **R-b, the previous New York session's range:** at every half hour 00:30-20:30 UTC (the moments included), P1
  break-and-hold when the pool broken is the previous New York session's high or low (13:00-21:00 UTC of the
  previous weekday).
- Both: stop 0.38 U from the entry (the fit winners' q70), target at least 5 USD (max(5 USD, 0.5 U)), time stop 60
  minutes; in a clear picture the target locks half of itself and trails 0.5 U, time stop 180 minutes; one
  position at a time (the earlier entry wins); fills and costs as above.
- Judged once on 2026-07-14 .. 10-14 against the gate (at least +0.15 R a trade with a tolerance of +0.10, at least one trade a day, two of three
  months positive).

**Verdict: fails** (`judge_v1.py`). Fit months: 109 trades, +0.229 R (se 0.113), +148 USD at 0.01 lot, 1.68 a
day, 3/3 months positive. **Judged months: 141 trades, -0.155 R (se 0.098), win 35 %, -109 USD at 0.01 lot,
2.14 a day, 1/3 months positive** (R-a -0.133 over 45, R-b -0.166 over 96). Month by month (R-a / R-b): 07-14
-0.400 (17) / -0.016 (33); 08-14 +0.251 (13) / +0.012 (17); 09-14 -0.163 (15) / -0.338 (46). Pieces mined from
three months did not carry into the next three.

### H5 - the present picks the playbook (written 2026-10-17 before it is computed)

The owner's principle "live in the present" as a rule: on each trading day, for each moment group (Asia, London,
New York) x playbook (P1, P2, P3), the mean R of its entries over the previous 20 trading days (q70 stop 0.38 U,
the exits above, entries that closed before the day), shrunk toward zero with weight 20 (n x mean / (n + 20));
the day trades the cells above +0.05 R, at a moment the playbook with the higher shrunk mean, one position at a
time. Walk-forward over all six months (each day predicted only from earlier days; the first 20 days are
warm-up). H5 holds if this beats both trading every moment entry and its own cells' inverse (the cells it skips).

**Verdict: not supported** (`h5_present.py`, 2026-05-12 .. 10-13, 111 trading days, one position at a time):

| Moments, walk-forward | Trades | R/trade (se) | Win % | USD at 0.01 lot | Trades/day | Months positive |
|---|---|---|---|---|---|---|
| H5: the present picks the playbook | 266 | -0.013 (0.077) | 42 | +40.0 | 2.40 | 2/6 |
| Every moment entry, all playbooks | 711 | -0.039 (0.047) | 41 | -128.6 | 6.41 | 1/6 |
| The cells H5 skips | 605 | -0.040 (0.051) | 40 | -114.7 | 5.45 | 3/6 |
| Every P1 entry | 292 | +0.004 (0.070) | 43 | +66.7 | 2.63 | 4/6 |
| Every P2 entry | 328 | -0.046 (0.064) | 41 | -68.5 | 2.95 | 2/6 |
| Every P3 entry | 434 | -0.076 (0.064) | 38 | -199.2 | 3.91 | 3/6 |

H5 month by month (R / USD): 04-14 -0.491 (9) / -26.6; 05-14 -0.134 (61) / -26.3; 06-14 -0.206 (26) / -28.5;
07-14 +0.116 (91) / +87.0; 08-14 +0.087 (62) / +39.0; 09-14 -0.092 (17) / -4.7. (USD can be positive while R is
negative: R weighs every trade alike, USD weighs the larger stops more.)

**Where round 1 leaves Setup OWN:** over the latest six months, none of the three playbooks has an edge at the
moments once costs are paid (P1 +0.004, P2 -0.046, P3 -0.076 R); choosing among them by fixed context cells,
by pieces mined from three months, or by the last 20 days' results does not create one. The costs are about
0.06 R a trade (spread 0.23 + 2 x 0.07 USD slippage against a stop of about 6.5 USD), so before costs the entries
are close to a coin flip at a 1.3 : 1 reward-to-risk. The moments do run (the largest 30-minute ranges of the
day), but these mechanical entries do not catch the direction. Next levers, not yet tried: the entry trigger itself
(the size of the first minutes' reaction, displacement candles, tick volume), and the owner's own reading of
these moments as rules (docs/OWNER_TRADING.md).

### Round 2 - learn from the losers (owner, 2026-10-17)

The owner: "learning from the losing trades is the heart of developing a trade; catch the timing and the
signals"; "the Asian market, mostly 07-09 Thai, often makes a small fake move before going the big way; New York
is volatile at the open and 1-2 hours after - check it"; "learn from the real losers rather than one human's
opinion". Scripts: `owner_habits.py`, `losers.py` (the latest six months, every moment entry of round 1, q70 stop).

**The owner's habits, measured** (2026-04-14 .. 10-14):

- *Asia fakes first:* the first leg of 0.1 / 0.2 / 0.3 x R from the start's open (R = the start's usual 2-hour
  range, about 30 USD at 07:00 Thai) ends on the other side of the open two hours later in 38-46 % / 34-38 % /
  23-30 % of the Asian starts (07:00-09:00 Thai), against 42 % / 36 % / 29 % for every half-hour start of the day:
  **the Asian first leg fakes as often as any other time's, not more.** It varies by month (0.2 R: 26 % in April,
  45-48 % in July-August). The first 0.1 R comes within 1-2 minutes of 07:00 and 08:00 Thai.
- *New York is volatile at the open and 1-2 hours after:* **confirmed.** The median 15-minute range is 1.3-2.0x the
  day's median from 19:15 to 22:15 Thai (08:15-11:15 ET), the peak 15.0 USD (2.0x) at 20:30 Thai, the cash open;
  Asia 07:00-09:00 Thai is 1.2-1.5x; 03:00-06:00 Thai is the quietest (0.5-0.7x).

**The losers** (1,254 moment entries, 717 losers = 57 %): the median loser is stopped 8 minutes after the
entry, 41 % within 5 minutes; 26-29 % of the losers were right on direction (the target reached within 60
minutes of the entry, after the stop). What the losers share at the entry, first three months | last three:

| At the entry | Trades | Win % | R/trade |
|---|---|---|---|
| Entered flat (within 0.1 U of the moment's open) | 348 / 341 | 40 / 40 | -0.059 / -0.058 |
| Already 0.1-0.3 U the trade's way from the moment's open | 71 / 84 | 54 / 54 | **+0.248 / +0.226** |
| Chased beyond 0.3 U | 104 / 110 | 36 / 39 | -0.125 / -0.100 |
| London open (14:00 Thai) | 118 / 109 | 31 / 34 | -0.311 / -0.196 |
| 10 minutes or more after the moment | 100 / 90 | 36 / 37 | -0.144 / -0.141 |
| With the flow (swing structure) | 407 / 400 | 39 / 41 | -0.069 / -0.034 |

The 0.1-0.3 U band is P1's: break-and-hold at Asia +0.378 (26) / +0.474 (26), at New York +0.291 (23) / +0.418
(26), win 54-65 %; P2 gains nothing from it. Losers mostly entered flat (no push yet: the moment's whipsaw stops
them) or chased (the push already spent).

### OWN v2 - written 2026-10-17 before the earlier six months (2025-10-14 .. 2026-04-14) are computed

Both halves of the latest six months shaped v2, so they cannot judge it. The untouched six months before them
judge it once (a background window, but the only data v2 has not seen).

- **Moments:** Asia (Tokyo 09:00 JST and Shanghai 09:00 CST: 07:00 and 08:00 Thai) and New York (COMEX/data
  08:20-08:30 ET and the cash open 09:30 ET). Not London.
- **Entry:** P1 break-and-hold of the nearest pool within 30 minutes of the moment, taken only when the entry
  price (the fill) lies 0.1-0.3 U beyond the moment's open in the trade's direction.
- **Exits:** stop 0.38 U from the entry; target at least 5 USD (max(5 USD, 0.5 U)); time stop 60 minutes; in a clear picture
  the trend hold (lock half the target, trail 0.5 U, 180 minutes). One position at a time.
- **Gate (as above):** at least +0.15 R a trade (tolerance +0.10), months mostly positive; the trade count is
  reported against the one-a-day goal.

**Verdict: fails** (`judge_v2.py`). Latest six months (where it was found): 95 trades, +0.398 R (se 0.120), win
60 %, +254.6 USD at 0.01 lot, 0.73 a day, 6/6 months positive. **Earlier six months (untouched): 70 trades,
+0.035 R (se 0.162), win 41 %, -10.9 USD, 0.54 a day, 2/6 months positive** (Asia +0.064 over 34, New York +0.007
over 36). The second pattern mined from many cuts that shrank to about zero on new data.

### The three kinds of losers (owner, 2026-10-17; `loser_kinds.py`)

For every trade stopped before its target: **1 wrong way** (less than half the way to the target before the stop,
no run to the target afterwards); **2 right way, fell short** (at least half the way, then back to the stop, no
run afterwards); **3 right way, entered too early** (stopped, then the target reached from the original entry
within 120 minutes of the entry).

| Stopped losers | Trades stopped | 1 wrong way | 2 fell short | 3 too early | Too early: stop that survived | Too early: worst point after |
|---|---|---|---|---|---|---|
| Round 1, every moment entry (latest six months) | 710 of 1,254 | 41 % | 14 % (got 0.73 of the target) | 45 % | 1.77x (10.75 vs 5.55 USD) | 17 min |
| The same minutes with a coin-flip side | 718 of 1,254 | 40 % | 13 % | 47 % | 1.72x | 16 min |
| Control half hours (1,500 sampled) | 896 of 1,500 | 44 % | 12 % | 44 % | 1.79x | 18 min |
| OWN v2, latest six months | 35 of 95 | 49 % | 17 % | 34 % | 1.79x | 16 min |
| OWN v2, earlier six months | 39 of 70 | 33 % | 21 % | 46 % | 1.73x | 14 min |

**The split of our losers equals a coin flip's**: the entries choose the side no better than chance, and "too
early" (45 %) is what a random path does after a stop of 0.38 U (a 1.8x wider stop was tried in round 1, q90:
no better). Kind 2 got about 0.6-0.75 of the target before turning.

**Are we on the wrong side of the big players?** The exact opposite of each trade (same minutes, stops and
targets, scalp exits), R per trade ours / opposite / coin flip:

| Entries | Trades | Ours | Opposite | Coin flip | Ours first / last 3 months | Opposite first / last |
|---|---|---|---|---|---|---|
| P1 Asia | 153 | +0.054 | -0.067 | -0.026 | +0.040 / +0.068 | -0.027 / -0.108 |
| P1 New York | 147 | +0.131 | -0.156 | +0.017 | +0.176 / +0.096 | -0.129 / -0.177 |
| P2 Asia | 152 | +0.075 | -0.083 | -0.094 | +0.036 / +0.115 | -0.218 / +0.058 |
| P2 New York | 165 | -0.019 | -0.090 | -0.148 | +0.109 / -0.131 | -0.177 / -0.014 |
| **P1 London** | 45 | -0.470 | **+0.210** | -0.266 | -0.627 / -0.236 | +0.356 / -0.010 |
| **P3 London (with the flow)** | 107 | -0.286 | **+0.154** | -0.019 | -0.267 / -0.307 | **+0.119 / +0.192** |
| P3 Asia / New York | 205 / 205 | -0.155 / -0.024 | -0.082 / -0.069 | | | |
| Control half hours P1 / P2 / P3 | 600 each | -0.121 / -0.099 / -0.032 | -0.096 / -0.041 / -0.154 | | | |

Not opposite everywhere: at Asia and New York our side beats the opposite. **At the London open we are on the
wrong side**: going with the H1/M15 flow there and following fresh breaks lose, the opposite pays (with the flow
the opposite is positive in both halves). London runs the stops behind the Asian move and turns.

### OWN v3 - London against the flow, written 2026-10-17 before the earlier six months are computed

- At 08:00 London (14:00 Thai in summer, 15:00 in winter) on weekdays, a flow defined (H1 swing structure now,
  else M15): enter at the open of the moment's bar **against** the flow.
- Stop 0.38 U from the entry; target at least 5 USD (max(5 USD, 0.5 U)); time stop 60 minutes; no trend hold (the
  clear picture is the flow being faded).
- Judged once on 2025-10-14 .. 2026-04-14 (untouched) against the gate.

**Verdict: fails** (`judge_v3.py`). Latest six months (where it was found): 107 trades, +0.142 R (se 0.111),
+75.6 USD at 0.01 lot, 0.82 a day, 5/6 months positive. **Earlier six months: 106 trades, +0.039 R (se 0.114),
+66.4 USD, 1/6 months positive** (one month, 2026-03, +102.7 USD; the other five -1.4 to -12.8 USD each). The
third rule found in the latest six months that faded on the earlier six.

### Smart money's draw on liquidity (written 2026-10-17 before it was computed; `draw_liquidity.py`)

Where yesterday's broker-day high (PDH) and low (PDL) are both untaken and the price lies between them (moments
and control half hours, both windows), does the rest of the day take the nearer one first more often than chance?
Baselines: a driftless random walk, p = (price - PDL) / (PDH - PDL), and a placebo: real gold paths of 20 other
days from the same clock time, scaled to the day's U (the same end-of-day cutoff, levels that mean nothing).

| Hit PDH first, among days with a hit | Earlier: p / placebo / actual | Latest: p / placebo / actual |
|---|---|---|
| Price in the lowest quarter (PDL near) | 0.181 / 0.093 / 0.094 (36 days) | 0.163 / 0.113 / 0.045 (50 days) |
| 0.25-0.5 | 0.380 / 0.283 / 0.352 | 0.369 / 0.299 / 0.255 |
| 0.5-0.75 | 0.620 / 0.606 / 0.772 | 0.625 / 0.644 / 0.639 |
| Highest quarter (PDH near) | 0.839 / 0.871 / 0.932 (46 days) | 0.838 / 0.874 / 0.922 (42 days) |
| All | 0.531 / 0.490 / 0.584 | 0.485 / 0.463 / 0.441 |

The pull to the nearer level that the random walk misses is mostly the placebo's too (the cutoff and gold's
paths); beyond the placebo only near PDH, +0.05-0.06 in both windows on 42-46 days (weak), and the windows'
trends (earlier up, latest down) move the middle rows. **No stable draw on yesterday's extremes.**

### H6 - the dollar leads gold (written 2026-10-17 before it is computed)

The big money's flow shows first in the dollar (six USD majors, M1), gold follows. At every moment of both
windows, the dollar's move over the first k = 1, 2, 3 minutes (each pair's return over its median absolute
1-minute return of the previous five days x sqrt(k), signed as USD up, averaged) against gold's own first k
minutes; outcome: gold's move over the next 30 and 60 minutes from the close of minute k, in U. H6 holds if gold
goes against the dollar's first move (gold up when the dollar falls) more than chance in both windows, and more
than gold's own first move predicts - most of all when the two disagree (gold has not followed yet).

**Verdict: not supported** (`h6_dollar.py`, 641 / 659 moments). Gold moves with the dollar within the same
minutes (correlation of the first 2 minutes -0.46 earlier, -0.84 latest), so there is little left to follow; what
follows flips sign between the windows. Gold's next 60 minutes signed by the dollar's first 2 minutes, strong
moves only: earlier -0.071 U (hit 0.50, 321), latest +0.121 U (hit 0.54, 330); when gold had not yet followed:
earlier -0.294 U (hit 0.44, 97), latest +0.274 U (hit 0.65, 71). Gold's own first move: +0.102 / +0.038 U.

### The owner's test of a signal (2026-10-17)

"If the setup is sure of a signal, then once it enters, price must run at least 5 USD, possibly closed within
seconds or minutes." From now on a signal is judged first by **how often price runs 5 USD its way before the
stop**, and how fast. Round 1 and 2's entries do that 41-54 % of the time with a stop of about 6.5 USD, as often as
a coin-flip side at the same minutes.
