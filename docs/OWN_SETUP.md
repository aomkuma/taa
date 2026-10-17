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
