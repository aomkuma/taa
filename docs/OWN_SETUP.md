# Setup OWN - the owner's own trade: the moments when gold runs

The owner's goals and principles are in `docs/OWNER_GOALS.md`; the setup's place among the owner's trades in
`docs/OWNER_TRADING.md` ("Setup OWN"). This file holds the method, the hypotheses (written down before any outcome
is computed) and the results, month by month as they finish. Results describe the past, never a promise.

## The learning loop: every run's losers in three kinds (owner, 2026-10-17)

The owner: "learning from the losing trades is the heart of developing a trade"; "combine it with the three
kinds of losers and write it down as the way we learn". After every run (harness, backtest, DEMO), each trade
stopped out before its target is put in one kind (`loser_kinds.py`), and each kind points at its own lever:

| Kind | What happened | What it says | The lever to try next |
|---|---|---|---|
| 1 Wrong way | less than half the way to the target before the stop, and no run to the target afterwards | the side was wrong | the direction screens: the H1 tide, the pullback depth, the session or hour (skip where kind 1 dominates), the location against support / resistance |
| 2 Right way, fell short | at least half the way to the target, then back to the stop; no run afterwards | the target was too far for that moment, or the stop stayed too long at risk | the exit: a nearer target (a smaller tool), a partial profit or the stop to break-even at about 0.5-0.6 of the target, a shorter time stop |
| 3 Right way, entered too early | stopped first, then the target reached from the original entry within 120 minutes | the timing or the stop: the entry's shake-out took the stop | the entry timing (screen 3: wait for the turn, ticks), a better entry price (a pullback limit), or a stop beyond the usual shake-out |

**Never conclude "it is a coin flip"** (owner, 2026-10-17: "that is too easy; find why it loses"). The coin-flip side
is only a yardstick; every report names the concrete reasons its losers lost (from the trades and their charts:
where in the move, the H1 swing and phase, the session phase, the level's quality, the stop against the normal
swing, the spread at that hour, news nearby, what came right before the entry), how many losers each reason
covers, how the winners differed, and the change that attacks the largest reason.

Each kind is always read **against a coin-flip side at the same minutes** (the same stops and targets): a kind is
a finding only where it differs from the coin's split (round 2: 41 / 14 / 45 % for both - no finding). The next
change attacks the kind that is largest *above the coin's*, is written down before it is computed, and is judged
on data it was not found on.

## Data and window

**The test window is 2026-03-01 onward** (owner, 2026-10-17: "I always stress: test in the latest six months,
that is from 2026-03-01"): every result from round 8 on is reported on 2026-03-01 .. 2026-10-14 (the data's end),
month by month; rules, weights and cuts are learned only from data before 2026-03-01. Rounds 1-7 used 2026-04-14
(six months back from the data's end) and older windows - superseded; their test numbers start six weeks late.

Rounds 1-7 (superseded window): **The latest six months only (owner, 2026-10-17: "focus on the bot and backtests over the latest 6 months; we
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

### Round 3 - a learned signal (owner, 2026-10-17: "do whatever you think will make the setup profitable")

Written before any result. Instead of cutting one condition at a time, a gradient-boosted model (LightGBM, a
separate research venv `data/venv-research`, never imported by the app) learns from every measure together when
price runs **+5 USD before the stop**.

- **Candidates:** every minute in the active windows (Asia 00:00-02:00 UTC = 07:00-09:00 Thai; London
  08:00-09:30 London; New York 08:15-11:15 ET, the volatile hours measured above), weekdays, both sides.
- **Label:** entry at the minute's open (a BUY at the ask), target +5 USD (a limit, no slippage), stop 4, 6 or 8
  USD (7 points of slippage), 30-minute time limit; both in one bar = the stop.
- **Features at the previous bar's close only:** gold's returns over 1-60 minutes, ranges, the position in the
  last hour's / today's range, distances to today's, yesterday's and the Asian high/low and round 50s, the last
  bar's body and wicks, tick volume against its hour, the spread, the dollar composite's returns (six majors),
  M15/H1 EMA position and slope, the 20-day range, minutes since the session's start and to / since a release,
  the weekday; directional ones signed by the side.
- **Judging:** train on the earlier six months (2025-10-14 .. 2026-04-14), test on the latest six month by month;
  and a monthly re-fit on the previous six months (the owner's revision cycle). The probability threshold and the
  stop are chosen inside the training window (its last two months as validation), never on the test. One
  position at a time. Reported: +5 USD hit rate, R and USD per trade, trades a day, months positive, and the
  losers' three kinds.

**Results** (`ml_dataset.py`, `ml_train.py`; 100,610 active minutes 2025-10-14 .. 2026-10-14; the long variant
`--long` 296,554 from 2023-11):

| Model (test: 2026-04-14 .. 10-14) | Stop chosen | Trades | Hit +5 USD | Base hit | Need | R/trade | USD (0.01 lot) | Months + | Test AUC |
|---|---|---|---|---|---|---|---|---|---|
| Fixed, fitted on 4 months (2025-10 .. 2026-02) | 8 USD | 711 | 57.2 % | 51 % | 62 % | -0.027 | -152.0 | 3/7 | 0.537 |
| Monthly re-fit, 4 months | 8 (mostly) | 489 | 57.5 % | 51 % | 62 % | -0.023 | -88.0 | 1/7 | 0.53-0.56 |
| Fixed, fitted on 2023-11 .. 2026-02 | 6 USD | 304 | 53.6 % | 47 % | 55 % | -0.019 | -35.0 | 4/7 | 0.544 |
| Monthly re-fit, expanding from 2023-11 | 6-8 | 297 | 58.2 % | | | -0.033 | -67.6 | 3/7 | 0.536-0.578 |

The model reads new data a little better than chance in every month (AUC 0.53-0.58, the latest months the
highest) and lifts the +5 USD hit rate by about 6 points, short of the 7-11 points the target/stop geometry and the
costs need. The features it uses most: the 20-day range, minutes into the session, ATR, the H1 EMA position and
slope, today's range against the 20-day range, the distances to yesterday's high/low and the Asian range.

**Is 5 USD too far?** (owner, 2026-10-17: "gold runs 70-100 USD a day"). No: over the active minutes of the latest
six months price runs 5 USD one way or the other within 5 minutes 40 % of the time, within 15 minutes 79 %, within
30 minutes 94 % (the daily range's median 82.5 USD). The hard part is the side. A side at random reaches +5 USD
before a 4 / 6 / 8 USD stop in 39.7 / 49.2 / 55.0 % of the minutes; break-even after the costs needs 44.9 / 54.8 /
61.7 %. A signal therefore has to pick the side right about 5-7 points more often than a coin.

### Round 4 - the arsenal (owner, 2026-10-17: "a full arsenal, pick the right tool for the moment")

Eleven tools (target / stop USD: 3/3, 3/5, 5/4, 5/6, 5/8, 8/6, 8/8, 10/8, 10/12 within 60 minutes, 15/10 and 20/12
within 120); a LightGBM model per tool (win / stop / time-out) gives each minute's expected USD per tool; in each
session the first minute whose best tool clears the session's cut (chosen on validation for about one trade a
session-day), at most two a session, one at a time. Train 2023-11 .. 2026-02, validation 2026-02-14 .. 04-14, test
the latest six months (`ml_arsenal.py`).

**Verdict: no edge.** Test: 122 trades (0.93 a day), win 35 %, +0.30 USD a trade, +37.0 USD at 0.01 lot, 4/7 months
positive (Asia -21.2 over 71, London +40.0 over 2, New York +18.2 over 49); the validation lost (-98.4 USD). The
model expected +3.5 USD a trade and got +0.3: over-confident, and it picked almost only the large tools (20/12: 85,
15/10: 30), the 2024-26 rally's drift in its training.

### Gold's ticks (2026-10-17)

`download_ticks.py`, read-only from the FBS demo terminal (owner's go-ahead): 273 weekdays 2025-10-01 ..
2026-10-16, about 300-400 thousand ticks a day (854 MB, `data/ticks/XAUUSD`); 2026-04-03 (Good Friday) empty.
`tick_features.py`: at each candidate minute, from the ticks before it: ticks in the last 10 / 60 seconds and
against the hour's rate, the up/down tick imbalance, mid returns over 5 / 15 / 30 / 60 seconds, the spread and its
widening, the last tick's age (median 55 ticks in 10 seconds, 331 in a minute; spread median 0.36 USD).

### Round 5 - the triple screen, H1 at most (owner, 2026-10-17: "do you use the triple screen? H1 at most, then
scalp with that trend; find the entry timing in that trend") - written before it is computed

- **Screen 1 (tide, H1):** the trade's side is H1's trend: the H1 EMA(20) rising over 3 bars and the close above
  EMA(50) for a buy (mirrored for a sell); variant B adds the close above EMA(20).
- **Screen 2 (wave against it):** a pullback against the tide: the M15 RSI(14) below 40 / 45 / 50 for a buy (above
  60 / 55 / 50 for a sell), or the price in the lower 30 % / 50 % of the last 60 minutes' range; or no screen 2.
- **Screen 3 (entry timing, M1 and ticks):** the pullback turning back the tide's way: the last M1 bar closed the
  trade's way; or the last 15 seconds' ticks moved the trade's way with more up- than down-ticks in the last
  minute (mirrored); or the last 3 M1 bars net the trade's way; or none.
- **Exits:** a tool from 5/4, 5/6, 8/6, 10/8 (target / stop USD).
- In the active windows (Asia, London, New York), at most two trades a session-day, one at a time.
- The variant is chosen on the earlier six months (2025-10-14 .. 2026-04-14, total USD with at least one trade a
  day, its neighbours shown) and **tested once on the latest six months** (the owner: "test only the latest six
  months").

**Verdict on the chosen variant: fails** (`triple_screen.py`). H1 trend A + M15 RSI below 50 + the ticks turning,
tool 10/8: earlier six months 354 trades (2.79 a day), +0.27 USD a trade, +94.9 USD, 5/7 months positive; **latest six
months 375 trades (2.86 a day), win 36 %, -0.51 USD a trade, -190.3 USD, 2/7 months positive** (Asia -85.6, London
-121.7, New York +17.0). Only 10 of 192 variants were positive on the earlier six months.

**But the deep pullback held in both windows:** every variant with the M15 RSI below 40 among the best:

| Variant (screen 1 / 2 / 3 / tool) | Earlier six months | Latest six months |
|---|---|---|
| A / RSI < 40 / ticks / 10-8 | 151 trades, +49.9 USD | 122 trades (0.93 a day), win 39 %, +0.68 USD a trade, +83.1 USD, 5/7 months |
| A / RSI < 40 / none / 10-8 | 160 trades, +26.4 USD | 132 trades (1.01 a day), win 39 %, +0.54 USD a trade, +70.8 USD, 6/7 months |
| B / RSI < 40 / bar / 8-6 | 136 trades, +43.2 USD | 87 trades (0.66 a day), win 43 %, +0.60 USD a trade, +52.4 USD, 5/7 months |
| A / RSI < 40 / bar / 8-6 | 169 trades, +19.6 USD | 142 trades (1.08 a day), +0.13 USD a trade, +18.3 USD, 3/7 months |

Averaged over the variants, RSI < 40 lost least on the earlier six months too (-0.16 USD a trade against -0.28 to
-0.89 for the other screen-2 choices). The latest six months were seen for this family, so it is judged next on
older data it has not seen.

### Round 5b - the deep pullback on untouched older data (written before it is computed)

- **Family:** screen 1 A (the H1 EMA(20) rising, the close above EMA(50)), screen 2 the M15 RSI(14) below 40 (above
  60 for a sell), screen 3 none or the last M1 bar the trade's way; tools 10/8 and 8/6; the active windows, at most
  two trades a session-day, one at a time.
- **Judged on 2023-11-01 .. 2025-10-14** (four half-years; gold M1 only, no ticks there), with the tools in fixed USD
  and scaled by the price (x price / 4,100: 10 USD at 4,100 is about 6 USD at 2,400). The family passes if most
  half-years are positive with the price-scaled tools.
- Its losers in three kinds on every window, against the coin.

**Verdict: fails** (`deep_pullback.py`). Screen 3 none, tool 10/8 scaled by the price, by half-year: 2023-11 ..
2024-04 -27.2 USD (121 trades, -0.055 R); 2024-04 .. 10 -25.5 (131, -0.039 R); 2024-10 .. 2025-04 +51.7 (128,
+0.066 R); 2025-04 .. 10 -31.1 (117, -0.029 R): 1 of 4 positive. The other seven variants (fixed / scaled, 10/8 or
8/6, bar or none) give the same picture: only 2024-10 .. 2025-04 positive in all eight, -0.13 to +0.11 R a trade
elsewhere. In the quiet years most trades end at the 60-minute limit (target first 6-31 %).
The losers in three kinds equal a coin-flip side's in every window (2023-11 .. 2024-04: wrong way 78 / 79 %,
fell short 9 / 9 %, too early 12 / 12 %; latest six months 60 / 59 %, 16 / 8 %, 25 / 32 %).

### Where five rounds leave Setup OWN (2026-10-17)

| Round | Idea | Where it was found | Untouched data |
|---|---|---|---|
| 1 | Three playbooks at the moments, context cells | - | -0.31 R (selector), -0.155 R (v1) |
| 2 | Losers' traits: P1 after a 0.1-0.3 U push (v2); London against the flow (v3) | +0.40 / +0.14 R | +0.035 / +0.039 R |
| 2 | Draw to yesterday's high/low; the dollar leads gold | - | no more than a placebo; flips sign |
| 3 | A learned signal for +5 USD (62 features) | AUC 0.53-0.58 | -0.02 to -0.03 R |
| 4 | The arsenal (11 tools, the best per minute) | validation -98 USD | +0.30 USD a trade, 4/7 months |
| 5 | The triple screen, H1 at most, ticks for timing | +94.9 USD | -190.3 USD; the deep pullback +83 / +71 USD, but 1 of 4 older half-years positive |

Every direction signal built from gold's own prices (M1 bars, ticks, H1/M15 trend, levels, the dollar, the
calendar) picks the side about as well as a coin once it meets data it was not found on; the losers' three kinds
match the coin's every time. What the data does show: the moments are real (New York 1.3-2.0x the day's
15-minute range for three hours; 5 USD comes within 15 minutes 79 % of the time), the costs are about 0.3 USD a
trade (6 % of a 5 USD target), and a learned model sees a little (AUC 0.53-0.58) but not enough to pay the costs.

### Round 6 - an indicator score (owner, 2026-10-17: "bring in MACD, RSI, anything, as weighted scores") - written before it is computed

- **Votes** (+1 the trade's way, -1 against, 0 neutral), on M1, M5, M15 and H1 (closed bars, H1 at most): MACD(12,26,9)
  histogram sign and its slope; RSI(14) above / below 50 and leaving 30 / 70; Stochastic(14,3) %K above / below 50
  and %K crossing %D; Bollinger(20,2) %B above / below 0.5 and outside the bands; EMA(20) against EMA(50); the close
  against EMA(20); ADX(14) above 20 with +DI against -DI; CCI(20) sign; the 10-bar rate of change. 52 votes.
- **Weights** learned by an L2 logistic regression on the earlier six months' first four months (2025-10-14 ..
  2026-02-14); the tool (5/4, 5/6, 8/6, 10/8) and the score cut chosen on 2026-02-14 .. 04-14 (at least one trade a
  day); the equal-weight sum of the votes is reported beside it. **Tested once on the latest six months.**
- The weights are printed (what the data trusts), and the losers in three kinds against the coin.

**Verdict: fails** (`indicator_score.py`). Chosen on validation: tool 8/6, the top 10 % of scores (validation +46.0
USD, 201 trades). **Test, latest six months: 631 trades (4.82 a day), win 40 % (the tool's base 38 %), -0.14 USD a
trade, -89.0 USD at 0.01 lot, 2/7 months positive**; Asia -169.0 (219), London -55.8 (167), New York +135.8 (245,
+0.55 USD a trade, 4/7 months). Equal weights (at least 29 of 52 votes): -153.0 USD, 1/7 months.
What the weights trust: **for** the M15 CCI (+0.19), M15 MACD histogram (+0.145), the H1 close above EMA(20)
(+0.145), the H1 rate of change (+0.134); **against** the price above the M15 / H1 middle Bollinger band (-0.219 /
-0.111) and an RSI turn out of 30 / 70 on M15 / H1 / M5 (-0.17 / -0.10 / -0.10): momentum with the trend while the
price sits low in its band - the deep pullback's shape again, and again not enough after costs.
New York is the one session on the plus side in rounds 1, 2 (P1 ours +0.131 against -0.156 for the opposite), 5
(the chosen triple screen +17.0) and 6 (+135.8); never yet on data it was not found on.

### Round 7 - New York, with the H1 trend, on the M15 pullback; adjusted through the losers (owner, 2026-10-17: "adjust it; a setup is never profitable the first time it is written")

- **Development data:** the four older half-years 2023-11 .. 2025-10 (M1; targets and stops scaled by the price /
  4,100) and the earlier six months 2025-10-14 .. 2026-04-14 (fixed USD, ticks available). **The latest six months
  test only the final version, once.**
- **Start (iteration 0):** New York 08:15-11:15 ET; screen 1 the H1 EMA(20) rising and the close above EMA(50)
  (mirrored); screen 2 the M15 RSI(14) below 45 (above 55); tool 8/6 USD; 60 minutes; at most two trades a
  session-day, one at a time.
- **Each iteration** changes one thing, chosen by the losers' kind that stands above a coin-flip side at the same
  minutes (the learning loop above), written here before it is computed, and kept only if it improves most
  development half-years.

USD at 0.01 lot (trades, R a trade); kinds = stopped losers' wrong way / fell short / too early, ours and the coin's:

| It. | Change (the kind behind it) | 2023-11 .. 04 | 2024-04 .. 10 | 2024-10 .. 2025-04 | 2025-04 .. 10 | Earlier six | Kept? |
|---|---|---|---|---|---|---|---|
| 0 | the start | -38.9 (103, -0.133) | +8.1 (115, +0.023) | -11.7 (110, -0.026) | -90.5 (87, -0.206) | -20.4 (119, -0.028) | kind 2 above the coin in three windows (21/9, 19/13, 12/9 %) |
| 1 | stop to the entry at 0.6 of the target (kind 2) | -46.1 (103, -0.149) | +29.8 (117, +0.072) | +17.1 (114, +0.035) | -71.1 (88, -0.157) | -7.2 (119, -0.010) | **yes**: 4/5 better |
| 2 | a nearer target, 6/6 (kind 2) | -46.0 (106, -0.151) | +3.7 (120, +0.009) | +0.7 (116, -0.001) | -92.5 (90, -0.201) | -64.5 (120, -0.089) | no: 4/5 worse |

(Iterations 1 and 2 were fixed in `ny_lab.py` before they ran; their lines here were written after, as the doc edit
had failed.) After iteration 1 the stopped losers are mostly kind 1: ours / coin 81/72, 49/49, 51/57, 67/76,
42/30 % - wrong way above the coin in 2023-11 .. 04 and the earlier six months.

- **Iteration 3 (kind 1, the direction):** as 1, with a stronger tide: the H1 EMA(20) slope above the median of
  the development rows' rising slopes.
- **Iteration 4 (kind 1, the direction):** as 1, with the pullback turning: the last M1 bar closed the trade's way.

| It. | Change | 2023-11 .. 04 | 2024-04 .. 10 | 2024-10 .. 2025-04 | 2025-04 .. 10 | Earlier six | Kept? |
|---|---|---|---|---|---|---|---|
| 3 | stronger tide (H1 slope > 0.3233 ATR) | -38.3 (42, -0.292) | +26.9 (49, +0.156) | +13.1 (44, +0.067) | -22.7 (31, -0.164) | -62.2 (44, -0.233) | no: 2/5 better, 0.34 a day |
| 4 | the last M1 bar turned | -48.9 (103, -0.160) | +14.8 (118, +0.038) | -0.6 (113, -0.003) | -102.3 (90, -0.218) | +37.0 (119, +0.051) | no: 1/5 better |

The two losing windows stay losing whatever the trigger (wrong way 71-88 % of their stopped losers): a phase that
does not suit the setup (the owner's principle: in an unsuitable phase a setup trades less).

- **Iteration 5 (kind 1, the phase):** as 1, traded only while the setup's own shadow trades (every iteration-1
  trade, taken or not) that closed in the previous 28 calendar days sum above zero; the shadow keeps running.

| It. | Change | 2023-11 .. 04 | 2024-04 .. 10 | 2024-10 .. 2025-04 | 2025-04 .. 10 | Earlier six | Kept? |
|---|---|---|---|---|---|---|---|
| 5 | trade only while its own last 28 days paid | -20.2 (20, -0.324) | +7.9 (85, +0.027) | -14.7 (52, -0.066) | -38.5 (35, -0.217) | -6.2 (50, -0.020) | no: worse a trade in 4/5 (it loses less only by trading less) |

The exit change helped; the direction changes did not. With entries that pick the side like a coin, no exit
makes money after costs - the direction must come from somewhere. The only signal found so far is the learned
model's (round 3, AUC 0.53-0.58).

- **Iteration 6 (kind 1, the direction from the model):** as 1, taken only when a LightGBM model (round 3's
  features, all sessions, label: tool 8/6 wins) fitted on everything before the window (walk-forward, from
  2023-11) scores the minute at or above the median score of the rule's own rows in its training data.
  2023-11 .. 04 has no earlier data and is skipped.

| It. | Change | 2023-11 .. 04 | 2024-04 .. 10 | 2024-10 .. 2025-04 | 2025-04 .. 10 | Earlier six | Kept? |
|---|---|---|---|---|---|---|---|
| 6 | the model's score as a direction screen (`ny_ml.py`) | skipped | +29.3 (116, +0.072) | -1.1 (107, -0.005) | -81.9 (86, -0.186) | -7.2 (119, -0.010) | no: it removes almost nothing and changes nothing |

- **Iteration 7 (kind 3 and the owner's "price swings eat the stop before the real run; use price action"):** in
  New York, with the H1 tide (screen 1 A) and the M15 pullback (RSI < 45): the last three M1 bars took out the
  lowest low of the 15 bars before them (a stop hunt), and the last bar closed back above that low (reclaimed);
  mirrored for a sell. Entry at the next bar's open; **the stop beyond the swept extreme plus one M1 ATR(14)**
  (the noise), the target 1.5 x that risk, the stop to the entry at 0.6 of the target, 60 minutes; the risk kept
  within 3-12 USD (price-scaled in the older windows).

| It. | Change | 2023-11 .. 04 | 2024-04 .. 10 | 2024-10 .. 2025-04 | 2025-04 .. 10 | Earlier six | Kept? |
|---|---|---|---|---|---|---|---|
| 7 | stop hunt + reclaim, stop beyond the sweep + 1 ATR, 1.5 R | -46.6 (80, -0.227) | -56.1 (94, -0.168) | -33.1 (94, -0.113) | -101.8 (67, -0.333) | -116.8 (84, -0.246) | no: worse everywhere; wrong way 50-78 % |

- **Iteration 8 (the owner: "wave ABCDE too; it likes to swing"):** in New York with the H1 tide (screen 1 A): on M5
  (the bot's chart-read ZigZag, default parameters) the last confirmed swings are a correction against the tide -
  for a buy a high, A a low, B a lower high, C a low below A (A-B-C down) - and the M5 close has just broken back
  above B (the correction over, the tide resuming); mirrored for a sell. Entry at the next M1 open; the stop below
  C minus half an M5 ATR(14); the target 1.5 x the risk; the stop to the entry at 0.6 of the target; 60 minutes; the
  risk within 3-12 USD (price-scaled in the older windows).

Iteration 8 gave 9 signals in 2.5 years with the bot's ZigZag (depth 12: C is confirmed about an hour late) and 24
with depth 5 (`ny_abc.py --depth 5`; -2.2 / +9.6 / +14.4 / +4.7 / -10.1 USD on 8 / 4 / 4 / 2 / 2 trades): too few to
judge; not kept.

- **Iteration 9 (the owner: "avoid the first half hour of the volatility so M1 / M5 show the direction"):** as 1, no
  entries in the 30 minutes after 08:30 ET and after 09:30 ET (19:30-20:00 and 20:30-21:00 Thai in summer).
- **Iteration 10 (the owner: "count three after the signal, check it again, then enter"):** as 1, a signal at
  minute t is entered only if the rule still holds, the same side, at t + 3 minutes; the entry at that minute.
- **Iteration 11:** 9 and 10 together.

| It. | Change | 2023-11 .. 04 | 2024-04 .. 10 | 2024-10 .. 2025-04 | 2025-04 .. 10 | Earlier six | Kept? |
|---|---|---|---|---|---|---|---|
| 9 | no entries 30 min after 08:30 / 09:30 ET | -10.5 (66, -0.058) | +7.0 (81, +0.025) | +1.2 (79, +0.000) | -48.6 (67, -0.144) | -122.9 (98, -0.207) | no: 2/5 better |
| 10 | count 3, re-check, then enter | -41.7 (74, -0.183) | -46.3 (86, -0.151) | -13.6 (83, -0.045) | +11.8 (59, +0.036) | +8.4 (82, +0.017) | no: 3/5 better but -81.4 USD in all against iteration 1's -77.5 |
| 11 | 9 + 10 | -6.1 (33, -0.065) | -34.3 (56, -0.175) | -24.7 (51, -0.117) | -2.2 (36, -0.010) | -40.2 (46, -0.144) | no |

Round 7 so far: the exit change (iteration 1, break-even at 0.6 of the target) is the only one kept; the New York
setup stays about -0.03 R a trade over the development windows (iteration 1: -77.5 USD on 541 trades), and its
stopped losers split like a coin's.

### Round 9 - confluence at the entry: support / resistance + price action + indicators together (owner, 2026-10-17) - written before it is computed

The owner: "at the entry you must check that support / resistance, price action and the chosen indicators agree;
what are you entering on now, and why does it lose so much?" Until now the three were tested one at a time, never
required together; round 7's entry was only the H1 tide + an M15 RSI pullback, taken at the first such minute -
the side right about as often as a coin. Round 9 requires all of them at the same minute; rules fixed here, no
fitting; **tested on 2026-03-01 .. 2026-10-14**, all three sessions, month by month, the losers in three kinds.

For a buy (a sell mirrored):
- **Tide (H1):** the H1 EMA(20) rising over 3 bars and the close above EMA(50).
- **Support:** the nearest level below the price - today's low, yesterday's low, the Asian low, a round 50, an H1 or
  M15 chart-read level (the bot's ZigZag) - lies within 3 M1 ATR(14) of the close, and the last 5 M1 bars' low came
  within 1 ATR of it (price is at the level now).
- **Price action at the level** (any one): the last M1 or M5 bar a hammer / pin bar (lower wick at least half the
  bar's range, the close in its upper third); a bullish engulfing on M1 (the close above the previous bar's open,
  the previous bar bearish); or the last 3 M1 bars' low went below the level and the last close is back above it.
- **Indicators** (at least two of three): the M5 RSI(14) rising and below 50; the M5 MACD histogram rising; the M5
  Stochastic %K crossing above %D.
- **Exit:** target 8 USD, stop beyond the level: the level minus 1 M1 ATR, kept within 3-10 USD; the stop to the
  entry at 0.6 of the target; 60 minutes; one trade at a time, at most two a session-day.

**Result** (`confluence.py`, 2026-03-01 .. 10-14). Funnel (minute x side rows): 125,576 -> H1 tide 53,998 -> at a
level 17,498 -> price action 9,929 -> indicators 1,931 -> stop 3-10 USD 1,385. **425 trades (2.61 a day), win 30 %,
-0.20 USD a trade (-0.032 R), -84.1 USD at 0.01 lot, 2/8 months positive**; Asia -60.4 (194), London -37.4 (68), New
York +13.7 (163). A coin-flip side on the same signals: -73.3 USD; the losers' kinds 51 / 3 / 46 % against the
coin's 50 / 4 / 46 %. **Fails: the confluence picks the side like a coin.**
A first run showed -55.9 USD against the coin's -109.1; checking trades one by one found two faults, fixed
before the result above: today's and the Asian high / low included the bars just before the entry (a "level"
that was the last bar's own extreme - price making a new high, not testing a resistance), and float32 distances
let a rounding difference of 0.01 count as a sweep. Now the day's and the Asian range count only as they stood
15 minutes before, every price is float64 from the bars, and a sweep must pass the level by 0.1 ATR. Checked trades
(entry, stop, target against the bars) at the round 50s 4150 and 4600 and an M15 level matched the rule.

### Round 10 - where does gold's own price carry direction at all? (`foundations.py`)

- **Drift by hour (Thai), six half-years 2023-11 .. 2026-10:** no hour keeps its sign in all six (18:00 Thai: -2.7,
  -0.4, +3.9, -0.2, +4.6, +4.4 bp; t-statistics mostly within +-2).
- **Continuation or reversal, by session and half-year:** the variance ratio at 5 / 15 / 60 minutes 0.84-1.21,
  mostly 0.94-1.03 (1.00 = a random walk); the correlation of one k-minute return with the next -0.19 .. +0.12,
  mostly within +-0.06, with no sign holding everywhere; New York reverses slightly at 5 minutes (VR 0.94 in four
  of six half-years) - far below the 0.3-0.4 USD a trade the costs take.

**Gold's own minute-scale price is close to a random walk in every session and half-year.** That is why every
entry built from it - trend, levels, candles, indicators, ticks, learned weights - picks the side like a coin
once it meets data it was not chosen on.

### Round 10b - the news: does the first minute after a release continue? (`news_follow.py`)

The first minute's move after a US release (the official calendar) is the market's reading of the surprise.
Big first moves (at least 3x the hour's 1-minute range), signed by their direction, the next 30 minutes:

| Release | 2023-11 .. 2026-02 | Test 2026-03 .. 10 |
|---|---|---|
| FOMC (14:00 ET) | 16: continues 62 %, +3.04 USD | 3: 67 %, +27.22 |
| PCE | 10: 80 %, +2.69 | 4: 100 %, +16.75 |
| CPI | 24: 42 %, -0.26 | 5: 0 %, -33.58 (all five reversed) |
| NFP | 21: 38 %, -2.16 | 6: 83 %, +10.67 |
| PPI | 14: 36 %, -2.76 | 1: 100 %, +18.23 |
| All big first moves | 85: 48 %, -0.17 | 19: 63 %, +3.31 |

The first thing with a cause that keeps its sign across both periods: **FOMC and PCE continue, CPI reverses**;
NFP and PPI flip. The samples are small (14-29 releases each in three years), and these releases come about three
times a month - a weapon for the news, not a source of three trades a day.

### Research team (owner, 2026-10-17: "open subagents to brainstorm, work until it is profitable, without
waiting for me"; "cut losses -> break even -> profit -> sustainable profit")

Brief: `research/2026-10-18-moments/agents/BRIEF.md`; each agent's rules, notes and results in its own folder.

**Trend agent** (`agents/trend/`, notes.md, test.py). Foundations on 2021-10 .. 2026-02 (nine half-years): variance
ratios at 60 / 120 / 240 minutes 0.97-1.20 (a faint trend tilt only at 4 hours), H1 lag-1 autocorrelation -0.05 ..
+0.05, the session's first 15-60 minutes agree with the next 1-3 hours 46-54 % with the sign flipping; 6,720
opening-range-breakout cells negative without a filter. Best rule (T1, frozen before the test): the New York
08:30-09:29 ET range, the first M1 close beyond it on a bar opening 09:30-09:59 ET, the H1 trend agreeing, the range
below 0.35 x the 20-day range; the stop at the range's far side, a 1 R trail from +1 R, 180 minutes, one a day.

| Step | Design R/trade (halves +) | Test trades | Test R/trade | Test USD |
|---|---|---|---|---|
| Every breakout, trailing exit | +0.009 (5/9) | 149 | -0.164 | -735 |
| + H1 trend agrees | +0.086 (7/9) | 79 | -0.132 | -216 |
| + the breakout by 10:00 ET | +0.124 (8/9) | 62 | -0.072 | -62 |
| + range < 0.35 x 20-day range (T1) | +0.168 (9/9) | 52 | -0.066 | -39.3 |

Test 2026-03 .. 10 month by month (T1): +97.0, +48.9, -110.0, -14.2, -8.7, -16.3, -34.4, -1.6 USD (2/8 positive,
0.32 a day). A coin-flip side on the same entries: -0.016 +- 0.135 R; ours beats 36 % of the draws. **Stage: the
filters cut the loss a trade (-0.164 -> -0.066 R) but by removing bad days, not by choosing the side** (the coin
improved alike). About 0.12 R of the design result was gold's 2024-26 bull drift. Trades hand-checked against the
bars (five) and the vectorised simulator against the loop simulator (300 trades).

**News agent** (`agents/news/`, notes.md with every rule frozen before its test, a journal and charts).

**S2 - the CPI / NFP release-minute straddle (the first rule to pass its test).** At 08:30:00 ET on CPI and NFP
days (the last tick before): a buy stop at the ask + 2 x (price / 4,000) USD and a sell stop at the bid - 2 x
(price / 4,000), one cancels the other, live until 08:30:59; the stop 8 x (price / 4,000) USD from the fill (at
market, gaps included); no target; exit at market at 08:31:00. The cause: the data reach the FBS feed about 1.2-1.4 s
after the release and the first impulse peaks at about 50-65 s.

| S2 | Trades | Result |
|---|---|---|
| Gold M1 2021-09 .. 2026-02, worst-case fill order | CPI 52, NFP 51 | CPI +0.90 / +0.51 R (2021-23 / 2023-26), NFP +0.38 / +1.15 R; 8 of 10 half-years positive; 36/36 (CPI) and 33/36 (NFP) neighbouring plans positive in both periods |
| Gold ticks 2025-10 .. 2026-02 (design) | 8 | +1.14 R, +88.9 USD |
| **Test, gold ticks 2026-03 .. 10-14 (once)** | **14** | **+144.1 USD at 0.01 lot, +10.29 a trade, 64 % positive, +1.23 R, 6 of 8 months**; the opposite side -0.08 R; exit at +300 s (declared variant) +167.8 USD |
| Test, the seven USD majors (M1, scaled by each pair's daily range) | 15 each | +0.58 .. +0.93 R per pair (one USD bet per release, not seven) |

Month by month (gold): 03 +13.0, 04 +10.7, 05 -8.9, 06 +30.7, 07 +100.8, 08 +11.9, 09 -26.2, 10 +12.0 USD. The lead
re-checked three releases on the raw ticks: 2026-07-14 CPI BUY filled 4032.92 at +0.44 s, 4087.89 at +60 s, +55.0
USD; 2026-09-11 CPI stopped at +1.7 s, -34.7; 2026-05-08 NFP -2.2 (the agent's numbers with slippage: +56.2, -34.9,
-2.3). **Open risk - the fills at the release second:** the tick feed shows a flat 0.37-0.39 spread through every
release; a real account's spread and stop-order slippage there are likely worse. The edge survives about 2 USD of
extra cost a fill on gold history, breaks 2021-23 at 3 USD (about -0.2 R a trade for each extra USD a side); stop
exits gapped up to 4 R. Two trades a month on gold.

**P1 - follow the FOMC press conference:** side = sign(the 14:39 ET close - the 14:30 open), enter at 14:40, the stop
2 x the mean range of the 14:30-14:39 bars (at least the 13:00-13:59 mean), exit at 16:39. Design: all 108
neighbouring plans positive in 2021-23 and 2023-26 (16 trades +0.84 R, 19 trades +1.50 R; the coin +0.38 / +0.32).
Test: 5 trades, +22.6 USD, +0.77 R (2 of 5 positive) - unproven.

Did not hold: the direction after the first minute of the 08:30 releases (follow or fade: 3-14 % of rules positive
in both periods, at or below chance), round 10b's "FOMC / PCE continue, CPI reverses" (flips on 2021-23), FOMC
minutes, retail sales, PPI, the statement minute.

**Auditor** (`agents/auditor/`, notes.md). **The harness is not why the setups fail:** the simulator, the stored
labels (3,000 rows, 0 mismatches), the features and the chart-read levels have no look-ahead and no result-changing
bug (minor: float touches, a bar opening beyond the stop fills at the stop, the ATR's true range missing |previous
close - low| - median ratio 1.000, an arbitrary side when both pass in one minute). Simulating the same trades on
real ticks with realistic fills moves results by -0.07 .. +0.04 USD a trade (about +-0.01 R): confluence test -84.1
-> -73.6 USD, triple screen -190.3 -> -217.0. **Costs:** the M1 spread column is the minute's minimum (100 % of 359k
minutes); a market entry pays about +0.08 USD more; real entry spread Asia 0.39, London / New York 0.29-0.30 (since
2026-04), 20-24 UTC 0.37-0.45; stop fills slip 0.15 on average (New York 0.20); a real round trip about 0.43 USD at
0.01 lot. **What a setup needs (gold):** 3/3 needs 14.6 win-rate points over a coin for +0.15 R, 5/4 11.5, 8/6 9.6,
10/8 9.1, 15/10 7.8, 20/12 7.0 (LightGBM's +6 points fell short of all). **FX majors:** the spread is 0.5-1.2 of the
median M1 range (gold 0.07-0.09) - M1 scalps not viable at FBS standard costs; 10/8 pips needs 12.9 points, 20/15
9.7. A raw account (if offered: a review quotes gold 0.10 raw vs 0.30 standard, not verified with FBS) saves about
0.03 R a trade at 8/6 - not enough for a coin-like signal. Data: gold M1 clean (1.80 M bars from 2021-09, old and
new stores identical where they overlap), DST correct, 330 spike bars are real news moves; ticks 101 M, none out of
order; FX majors clean.

**News agent, round 2 - S2 under bad fills** (`agents/news/` notes "Round 2", `fills.py`, `m1_stress.py`). Fills
modelled at the first tick L seconds after the trigger, the spread widened to X USD from the release to +5 s
(decaying by +15 s; a wide quote can fire a stop), 0.07 slippage on top. On the ticks the entry fills a mean 1-2 USD
(median 0.4-0.7) past the trigger whatever the latency: the first jump sets the cost. R a trade, exit at +60 s:

| D (trigger USD) | Latency | Design 8 releases, X = 0 / 2 / 4 USD | Test 14 releases, X = 0 / 2 / 4 |
|---|---|---|---|
| 2 (frozen) | 0 s | +1.17 / +1.19 / -0.17 | +1.23 / +1.21 / +0.65 |
| 2 | 1.5 s | +1.11 / +1.01 / -0.31 | +0.82 / +0.70 / +0.08 |
| 3 | 0 s | +1.16 / +1.13 / +1.06 | +1.17 / +1.07 / +0.72 |
| 3 | 1.5 s | +1.12 / +1.04 / +0.92 | +0.82 / +0.75 / +0.69 |

Gold M1 2021-09 .. 2026-02 (2021-23 / 2023-26), D 3 with X = 4: fill gap 1 USD +0.52 / +0.59 R, 2 USD +0.39 / +0.46,
3 USD +0.19 / +0.34, 4 USD -0.40 / -0.05. **The frozen S2 (D 2) breaks at a release spread of about 4 USD or a fill
gap of about 4 USD; D 3 is the robust setting** (chosen on the design rows' robustness; its test numbers were seen in
the same table: +136 USD, +1.17 R against D 2's +144). Exiting at +300 s is worse than +60 s in every design cell.
More releases with the same straddle (official calendars added: JOLTS from BLS, weekly claims from the DOL rule
and OPM holidays; ISM's calendar is behind a login): share of 72 plans positive in both design periods CPI 54 %,
NFP 38 %, FOMC 7 %, claims / GDP / JOLTS / minutes / PCE / PPI / retail sales 0 % - nothing new frozen. The
confirmation idea (the CPI fakes) cannot be designed yet: 8 pre-2026-03 tick releases, and the test's fakes were
seen; it needs releases from 2026-10 on. **News on gold: about 2.6 trades a month (S2 1.9, P1 0.7); test 19 trades,
+166.7 USD.** The deciding unknown: the real spread and stop fills at the release second on the owner's account.

**Interim (2026-10-17 21:15 Thai): four agents stopped by the usage limit (resets 00:30 Thai); their notes so far.**

- **Cross** (`agents/cross/notes.md`; clocks checked: the 1-minute cross-correlation peaks at lag 0 for every
  input). Gold: equities and AUDJPY lead gold the same way (risk-on -> gold up later) but tiny (1-5 % correlation);
  episodes 0.4-1.5 USD over 60 minutes, hit 52-56 % - below the costs. **The majors: London 07-12 UTC, equities up
  over the last 30-60 minutes -> the dollar up over the next 30-120 minutes, the same sign in 5 of 5 half-years
  in five pairs** (EURUSD -1.8 .. -6.3, USDCHF +2.6 .. +6.8, USDCAD, USDJPY, GBPUSD; the same-minute sign is the
  opposite, so this is a later move, not co-movement); 17-21 UTC the sign flips. Episodes (|equities 30 min| >=
  2.5 sd, drift-adjusted, before costs): USDCHF +4.0, EURUSD +3.6, GBPUSD +3.7 pips over 60 minutes, one every
  ~5.5 trading days; costs ~1.3-1.6 pips. Not yet a frozen rule or a test.
- **Reversion** (`agents/reversion/notes.md`): the stretch-fade with the H1 trend and a limit entry is a coin
  (edge +0.015 R over it, 3.65 a day); wider geometry (10/10 ATR, 240 min) cuts the loss (-0.108 -> -0.010 R) by
  costs, not side. Round-number bounces with resting limits are worse than placebo levels (Osler's stop clusters
  beyond round numbers); the break-through version (4b) was running.
- **Journal** (`agents/journal/`, journal.md, charts): from charts of the confluence trades (2025-09 .. 2026-02),
  lessons tried one at a time: only "M5 with the trade" beat the coin in 3 of 5 half-years; combinations J7-J10
  cut the loss from -0.140 to about -0.02 .. +0.00 R, with an edge over the coin of 0.03-0.10 R carried mostly by
  one half-year. New losers in the charts: buying under the 72-hour high after a vertical run, a flat H1 (chop), a
  release 5 minutes ahead; winners: compression on the level then a break, or a higher low after a sweep, then a
  break - written as rule K (not yet run).
- **FX longer horizon**: had only run its foundations.

**S2 against the account (50-100 USD, 4-6 losses in a row):** on the test S2's worst trade was -34.9 USD at 0.01 lot
(a release gap), the maximum drawdown 44.5 USD, the longest losing streak 2: on gold at 0.01 lot one release gap
can take 35-70 % of a 50-100 USD account. On the USD majors S2's stop is about 9 pips (about 0.9 USD at 0.01 lot):
the same weapon fits the account there.

### Round 11 - why the losers lose (lead, 2026-10-17; `why_losers.py`)

The journal agent's baseline B0 (H1 tide + at a level + price action + two of three M5 indicators; gold; the
design data 2023-11 .. 2026-02, five half-years, 1,150 trades, -0.140 R), each trade checked against concrete
situations at the entry: the share of the stopped losers (627) and of the winners (271) in it, and R with / without
it in every half-year.

| Situation at the entry | Losers in it | Winners in it | R with / without | Worse in |
|---|---|---|---|---|
| The H1 leg runs against the trade | 32 % | 27 % | -0.238 / -0.098 | 4 of 5 half-years |
| A flat H1 (the close within 0.85 ATR of EMA(50)): chop | 21 % | 16 % | -0.240 / -0.114 | 4 of 5 |
| Asia session | 38 % | 29 % | -0.199 / -0.106 | 3 of 5 |
| No room (the next level < half the target) | 35 % | 31 % | -0.178 / -0.119 | 2 of 5 |
| **Price in the upper half of its 4-hour range (with strength)** | 26 % | 35 % | **-0.035 / -0.180** | **better in 5 of 5** |
| Chasing (1 h run >= 4 ATR, at the 4-h extreme) | 11 % | 16 % | -0.034 / -0.154 | better in 5 of 5 |
| Falling knife, news within 15 min, a stop inside the swing, a volatility spike, far from the level | - | - | no consistent difference | |

**The losers are mostly dips bought in weak structure**: the H1 leg against the trade, a flat H1, price low in its
4-hour range; trading with strength (high in the 4-hour range, even after a run) is better in every half-year.

| Step (design data) | Trades | R/trade | Half-years + | By half-year |
|---|---|---|---|---|
| B0 | 1,150 (2.2 a day) | -0.140 | 0/5 | -0.242 -0.134 -0.030 -0.181 -0.125 |
| W1 = no H1 leg against, no flat H1 | 655 (1.3) | -0.062 | 2/5 | -0.287 +0.026 +0.025 -0.153 -0.013 |
| **W2 = W1 + the upper half of the 4-hour range** | 264 (0.5) | **+0.004** | 3/5 | -0.071 +0.076 +0.042 -0.123 +0.014 |
| W3 = W1 + the upper quarter | 171 (0.3) | +0.084 | 2/5 | -0.022 +0.245 -0.025 -0.112 +0.167 |
| W4 = W2 + not Asia | 201 | +0.023 | 3/5 | |

Stage on the design data: break even (W2). The worst single loss 12.63 USD at 0.01 lot.

**Frozen for the one test (2026-03-01 .. 10-13), written before it is run:** W2 = B0 (the journal agent's
`rules.py` B0, its costs and exits: target 8 U, the stop beyond the level by one M1 ATR, 3-10 U, break-even at 0.6
of the target, 60 minutes, two a session-day) taken only when the H1 leg is not against the trade
(`cr_H1_leg_dir >= 0`), H1 is not flat (`|h1_c_e50| >= 0.85`) and price is in the upper half of its 4-hour range
the trade's way (`pos240 >= 0.5`). Declared variant: W3 (`pos240 >= 0.75`).

**The one test** (`w2_test.py`; the filters applied to the signals before the selection loop; on the design data
this gives W2 299 trades +0.011 R, W3 198 trades +0.055 R, consistent with the table above):

| 2026-03-01 .. 10-13 | Trades (a day) | Win % | R/trade | USD at 0.01 lot | Months + | Worst | Max DD | Longest losing streak |
|---|---|---|---|---|---|---|---|---|
| B0 | 431 (2.66) | 31 | -0.033 | -112.1 | 2/8 | -11.69 | 187.7 | 13 |
| **W2 (frozen)** | 121 (0.75) | 31 | **-0.002** | **+8.1** | 4/8 | -11.52 | 82.5 | 9 |
| W3 (declared) | 75 (0.46) | 33 | **+0.030** | **+34.5** | **6/8** | -11.52 | 27.2 | 6 |

W2 by month: +35.7, -27.1, -29.9, +23.5, +16.9, +25.4, -4.1, -32.4 USD; W3: +29.1, +1.8, -8.6, +16.5, +10.5, +3.8,
+3.0, -21.6. By session (W2): Asia 46 trades -0.269 R (-56.0 USD), London 14 -0.315 (-24.3), New York 61 +0.271
(+88.4). **Stage reached on the test: break even (W2), a small profit (W3)** - the filters taken from the losers held
on data they were not made from (B0 -112 USD -> W2 +8, W3 +34.5; the drawdown 188 -> 83 / 27 USD).
Not yet fixed: New York's strength on the test is not in the design data (W2 design: London +0.078, New York +0.014,
Asia -0.050 R), so it stays a lead, not a rule. Asia has a design-side reason (negative in the last three design
half-years, -0.05 / -0.64 / -0.39 R; the widest spread, 0.39 USD) and lost again on the test; dropping it (W4, design
+0.023 R) is the next candidate - but the test window has now been seen, so it needs fresh data (2026-10-14 on).
For the account: the worst trade 11.5 USD and a 6-9 trade losing streak at 0.01 lot - a 50 USD account would take
about 45-55 USD of drawdown at W2's worst (82.5 USD): **W3 fits a 50-100 USD account (max DD 27 USD), W2 only 100 USD.**

**S2 on the USD majors against the account** (the news agent's `fx_results.parquet`, M1 with the worst-case fill
order, costs: the spread column + 0.2 pip a side; USD a pip at 0.01 lot about 0.10, USDJPY 0.067, USDCHF 0.12,
USDCAD 0.073): 2023-11 .. 2026-02, 54 trades a pair: +31 .. +93 USD a pair, the worst trade -0.67 .. -1.19 USD, the
maximum drawdown 2.0-3.6 USD, losing streaks at most 3. Test 2026-03 .. 10, 15 trades a pair: +7.8 .. +13.2 USD a pair,
worst -1.19, max DD 1.0-2.6. **At 0.01 lot the risk is tiny against a 50-100 USD account** (room for a larger lot);
the caveats stay: no FX ticks (the release-second fill on a real account is unmeasured; on EURUSD the edge is gone at
about 5-6 pips of extra fill cost), and the seven pairs are one USD bet per release, not seven.

**Cross agent - final** (`agents/cross/notes.md`, `steps.py`, `out_test_*.txt`). The London lead turned into a rule on
EURUSD, GBPUSD, USDCHF, USDCAD (a weekday M1 close 07:00-11:59 UTC; equity score = the mean of US500 and JP225
vol-scaled 30-minute moves >= 2.5, silent 60 minutes after; equities up -> the dollar up; target 15 / stop 10
pips, 120 minutes), filters taken from the design losers: X4 the dollar composite not yet moved the trade's way, X6
+ the pair not yet moved, X7 + the pair not stretched. Design (step table, 2023-11 .. 2026-02): +0.011 R (1,051
trades) -> X6 +0.165 R (202) -> X7 +0.325 R (88), positive in 5 of 5 half-years. **Test 2026-03 .. 10: X4 132 trades,
win 12 % (the coin 19 %), -0.329 R, -46.4 USD at 0.01 lot, 2/8 months; X6 -0.332 R; X7 36 trades, -0.309 R.**
Every pair lost (EURUSD -0.40, GBPUSD -0.38, USDCHF -0.34, USDCAD -0.18 R). Losers 78 % wrong way.
**Why it lost:** the dollar's coupling with equities changed in 2026 - the same-minute correlation of EURUSD with
equities in London was 10-27 in the design quarters and about +40 in 2026 Q1-Q2: equity jumps now move the dollar
at once ("risk-on, dollar down"; test signals had already seen a dollar move of about -2.0 sd against -1.2 in the
design), and the rule's bet on the dollar's later move the other way met a move that kept going. By quarter the
sign had already flipped in 2 of 9 design quarters (2024 Q4, 2025 Q3) - the half-year view hid it. The four pairs
were one bet (a failed signal stopped four legs together: a 14-trade losing streak); equity-up signals the worst
(-0.47 R vs -0.16). Next idea (needs unseen data): choose the side by the coupling regime measured on the past 20
days (weak coupling: bet on the later reversal; strong: follow equities), one pair per signal.

**Journal agent - final** (`agents/journal/`: notes.md, journal.md, about 250 charts of which about 110 read by eye;
real costs; B0 rebuilt from M1 for any symbol and checked against round 9: 431 test trades -0.033 R vs 425 -0.032).
Causes of the losers, counted: B0 - dips bought while the M5 was still falling (19 of 34 charted stopped losers, 2
of 18 winners); stops inside the swept range (kind 3). W3 - the eye's "spike entries" did not survive the count;
what separates them is the first minutes: kind 3 losers (44 % of full losses) pulled back about 2x the stop before
the move resumed - they entered at the end of a push with the tightest stops (1.9 vs 2.4 ATR); kind 1 losers (56 %)
- the push died, more often in a fast tape and far from the 72-hour extreme; being just under the 72-hour extreme
was a *winner's* mark (28 % of winners, 13 % of losers). V1's losers: the snap-back of a jump in a fast tape;
buying the 72-hour high after a vertical H1 run with H1 rejection wicks (e.g. `charts/W3/068.png`, checked by the
lead: a buy at 2684 under the H1 high after a vertical run, stopped at 2681, then 2668). Rejected: early exits at
minute 5-15, a limit entry at the retest, rule K, H1-structure / news / knife filters.

**V1** = W2 + the 72-hour extreme in front of the trade closer than half the target, or already behind the price
(the extreme = the highest high for a buy over the 4,320 M1 bars ending 15 minutes before the decision bar;
`(front - close) x side < 4 U`). **V2** = V1 + not a fast tape (M1 ATR < 2x its day median).

| Gold, real costs | Design trades (a day) | Design R | Coin R | Half-years + | Test trades | Test R | Test USD (0.01 lot) | Months + | Worst / streak / max DD (USD) |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 1,150 (2.2) | -0.140 | -0.151 | 0/5 | 431 | -0.033 | -112.1 | 2/8 | -11.7 / 13 / 187.7 |
| W3 | 198 (0.4) | +0.055 | -0.070 | 3/5 | 75 | +0.030 | +34.5 | 6/8 | -11.5 / 6 / 27.2 |
| **V1** | 100 (0.17) | **+0.222** | -0.055 | 4/5 | 18 | **+0.294** | **+44.1** | 5/6 | -7.0 / 3 / 16.7 |
| **V2** | 63 (0.10) | **+0.359** | +0.046 | 5/5 | 15 | **+0.378** | **+42.3** | 4/6 | -5.3 / 3 / 14.2 |

**Stage: profit on the design data and on the test, above the +0.15 R target - but the test window was already seen
(V1 / V2 derive from W3), the samples are tiny (15-18 test trades, standard error about 0.3 R) and they trade about
0.1 a day.** Six average losses in a row about 30 USD: fits a 50 and a 100 USD account. V1's seven test losses were all
wrong way, on three days: 2026-05-07 (the same 72-hour high / round 4750 refused three times after a +200 USD
vertical H1 run), 2026-08-12 (two trades 30 minutes after the CPI spike in a fast tape), 2026-08-14 (a sell at the end
of a 30 USD fall into the 72-hour low). FX with this logic (EURUSD, USDJPY, 15-20 pips): no design variant passes.

**Journal agent, round 5 - raising the count** (`agents/journal/notes.md` round 5, `out_r5_*.txt`, `out_test_r5.txt`).
Full sessions built (London 07-12 UTC, New York 12-17 UTC, Asia 00-02 UTC; nothing 20-23 UTC). Design 2023-11 ..
2026-02: V2 on the full sessions 102 trades (0.17 a day), +0.208 R, 4/5 half-years, max DD 21-25 USD (at today's
price); looser entries E2 (no B0 confirmation) +0.009 .. +0.093 R with DD 54-67 USD (96-120 at today's price); E5
(E2 + just under the 72-hour extreme + not late + no release within 15 min) +0.18 .. +0.20 R, 0.25-0.36 a day.
Counted causes: the owner-suggested "one attempt per 72-hour extreme" and "H1 not stretched" did not separate losers
from winners (15 / 18 %, 20 / 19 %); the added hours carried more losers (London 07-10 UTC -0.20 .. -0.27 R); 93 % of
E2's losers lacked B0's confirmation (the few with it made +0.36 R); price already through the 72-hour extreme
-0.007 vs just under +0.186 R; late in the window -0.197 vs +0.137 (all 5 half-years); a release within 15 minutes:
all full losses. **Test (seen): E5 38 trades -0.124 R, E5s1 25 trades -0.075 - fail** (37 of 38 had no B0
confirmation; the design's Asia carry did not repeat). **V2 on the full sessions: 25 trades (0.15 a day), win 44 %,
+0.170 R, +43.9 USD at 0.01 lot, 5/7 months; worst -6.4, streak 3, max DD 15.5 USD.** The count cannot be raised
toward 3 a day within this family without losing the edge; more trades must come from separate setups with their
own confirmation.

**FX agent - final** (`agents/fx/notes.md`, `cand.py`, `out_rf_test.txt`). Foundations per pair (2023-11 .. 2026-02):
hour-to-hour returns near a random walk (EURUSD, GBPUSD, USDCAD revert slightly, lag-1 negative 5/5; USDJPY the only
trending pair, VR(2 h) > 1 in 4/5, VR(8 h) up to 1.22); drift by hour at most 1-2 pips (USDJPY +2.3 at 07 UTC 5/5);
session effects that kept their sign are 1-7 pips; seven session families as trades make 0.00-0.07 R before costs
against costs of 0.08-0.16 R a trade (a round trip of 1.5-1.9 pips vs an H1 ATR of 7-20 pips) - **time of day alone
cannot pay FX costs.** The one effect with a cause: **on 08:30 ET US release days, fading the 08:00 -> 10:00 ET move**
gains +0.25 ATR by 14:00 ET (112 days, 4/5 half-years); on other days nothing. Rule RF (frozen before the test):
release days only, six pairs (not USDJPY), the 08:00-10:00 move >= 1 H1 ATR(24), pulled back > 10 % of the range
by 10:00, at most 25 % of it before 08:30; enter against it after 10:00 ET; the stop 1 ATR beyond the 08:00-10:00
extreme (skip if > 4 USD at 0.01 lot); exit at 14:00 ET; at most 3 pairs a day. Design step table: fade every day
-0.047 R (4,205) -> release days +0.042 -> ... -> RF +0.258 R (162 trades, 60 % win, max DD 17.7 USD). The decision
minute was a knife edge (09:45 / 10:00 / 10:15 / 10:30 ET: +0.12 / +0.28 / +0.13 / +0.05 R). **Test 2026-03 .. 10: 33
trades on 16 days, win 58 %, -43.7 pips, -2.84 USD, -0.067 R (before costs -0.009), 3/7 months** - fails; the coin
-0.121 R, 48 %. Account: worst -3.28 USD, worst day -6.60, streak 6, max DD 8.7 - fits 50 USD. **Why the nine stopped
losers lost:** 4 - a new USD move started at the 10:00 ET entry (10:00 is itself a release slot: 2026-06-25 PCE day
three pairs stopped in 5-6 minutes; 2026-03-13 JOLTS at 10:00, USDCAD ran 45 pips); 3 - a steady trend day, not a
spike (2026-07-15 PPI: a climb 08:30-14:00 the pre-release filter cannot see); 2 - stops too tight on AUD / NZD
(10 pips, price back at the entry by 13:00). Winners: one spike at 08:30 and a range by 10:00.

**Portfolio agent - final** (`agents/portfolio/notes.md`, `out_design.txt`, `out_portfolio_*.txt`). The protective menu
(C1 H1 leg not against, C2 H1 not flat, C3 pos240 >= 0.5, C4 the 72-hour extreme in front within half the target or
behind, C5 no fast tape, C6 not late, C7 no release +-15 min, C8 the H1 tide, C9 M5 with) applied by forward
selection (keep a condition if it adds >= 0.10 R in >= 4/5 half-years) to seven entry families on the full-session
candidates, design 2023-11 .. 2026-02. **C4 is the one condition that separates in every family that trades toward
an extreme** (with it, C2 / C3 / C9 are nearly always true). Families: F1 confluence (B0) -0.150 -> +C4 +C5 +0.118 R
(140 trades, 0.23 a day, 4/5, max DD 30 USD); F3 session-open break-and-hold -0.112 -> +C4 +0.127 (3/5; mostly long
drift: always-long +0.086); F2 NY range breakout +0.014 (break even); F7 B0's confirmation without the level +0.035
(0.61 a day, DD 72); F4 sweep-and-reclaim, F5 the S1-style fade, F6 compression breakout fail (why: F4 fades sweeps
against the structure - the H1 leg against, below EMA50, pos240 0.22-0.32, the 72-hour extreme 6-7 targets away;
F5 buys the first close under a fresh low in an uptrend and the break keeps going, 14 % wins; F6's breaks fall back
into the box). Test 2026-03 .. 10 (run once):

| Rule | Seen? | Trades (a day) | Win % | R/trade | USD (0.01 lot) | Months + | Max DD |
|---|---|---|---|---|---|---|---|
| **F1 CONF-72** = B0 + C4 + not a fast tape | family seen, combination new | 34 (0.21) | 44 | **+0.183** | **+52.9** | **6/7** | 26.7 (streak 4, worst -8.2) |
| F3 OPEN-72 | playbook seen | 18 (0.11) | 28 | -0.281 | -36.0 | 2/7 | 42.8 |
| F2 NY breakout | seen | 40 | 20 | -0.349 | -82.6 | 2/8 | 106 |
| F7 PULL + C4 | new | 34 | 35 | +0.049 | +15.6 | 2/7 | 28.0 |
| S2 on EURUSD | seen | 15 | - | +0.85 | +11.9 | 7/8 | 1.1 |
| P-A (F3 then F1, one gold position) + S2 | mixed | 66 (0.41) | - | - | +29.1 | 4/8 | 42.7 |
| P-C (adds F2, F7) + S2 | mixed | 127 (0.78) | - | - | -68.3 | 2/8 | 111 |

F1's test losers: three on 2026-05-07 at the same refused 72-hour high near 4750 (Asia, London, New York); three
after a 60-minute run of 10+ ATR into the extreme; stopped trades had tighter stops than winners (1.6 vs 2.3 M1 ATR -
seen only on the test, a lead). F3 failed because 16 of its 18 trades entered already through the 72-hour extreme
and 2026's faster minutes put the 8 U target and stop at only 1.5-2 M1 ATR. **Verdict: the protected setups cannot
reach about 3 trades a day; F1 CONF-72 (about 0.2 a day) and S2 on the majors (about 0.1 a day at tiny risk) are the
two weapons with an edge in both periods.** Fresh data from 2026-10-14 on should judge F1 + S2 exactly as frozen
(choosing them over P-A came after seeing F3 fail).

**FX agent, round 2 - fixing RF's loser groups** (`agents/fx/notes.md` round 2, `cal10.py` -> `cal10.csv`: Census New
Home Sales 45 dates, Construction Spending 45, Factory Orders 48 at 10:00 ET from census.gov 2023-2026, BLS JOLTS
61; ISM behind a login, Conference Board / Michigan no official dated archive; the Oct-Dec 2025 shutdown releases
missing). Each change on design (2023-11 .. 2026-02) moved RF by at most +-0.03 R: skip 10:00-release days +0.246
R; **decide at 10:15 on those days (RF-C) +0.287 R** (155 trades, max DD 18.5 USD); a spike-share filter +0.223
(DD 17.7 -> 11.7, streak 10 -> 7); break-even / partial at +1 R +0.252 / +0.225; an AUD/NZD stop floor +0.255;
dropping AUD/NZD +0.288. The design's largest loser groups: stops after 20+ minutes on spike days (the move resumed)
and about 30 time exits below zero. On the seen test none turns positive: RF-C 32 trades, win 56 %, -0.027 R, -1.0
USD (the coin -0.087 R, 41 %); 2026-06-25 alone (three stops 5-6 minutes after the 10:00 entry, no 10:00 release on
any official calendar sourced) cost -6.6 USD, more than the whole loss. By pair (seen): USDCHF +0.61 R, EURUSD
+0.13, GBPUSD -0.58. Fresh data to judge RF-C: every 08:30 ET release day from 2026-10-14 on; at ~5.8 trades a month
and an R standard deviation ~1.0, about 12 months (~70 trades) for a standard error of ~0.12 R.

### Round 12 - "count three on M1, check again, then enter" (owner, 2026-10-18) - written before it is computed

The owner, on two losers (charts `shadow/f1_2026-04-08.png`, `shadow/s2_2026-08-12.png`, `_ticks.png`): F1
2026-04-08 07:03 Thai BUY bought the top of a vertical 35 USD push at the Asian open after a vertical H1 run and was
stopped in one minute (price then fell to 4790); S2 CPI 2026-08-12 bought the first second's spike to 4433, was
stopped as price fell to 4382 within 8 s, then price climbed back above 4430 within 5 minutes (a fake first
impulse). "Count three after the signal on M1, check the signal again, then enter."

- **F1-C3a:** F1 CONF-72's signal (the decision at bar e-1's close) is entered only if, after the three M1 bars e,
  e+1, e+2, the close of e+2 is at or beyond the signal close the trade's way and none of the three bars touched the
  planned stop; entry at bar e+3's open, the same stop price, the risk recomputed (3-10 U, else skipped), target 8 U,
  B0's other exits. **F1-C3b:** C3a + the three bars held the level (no low below it for a buy).
- **S2-C3** (gold M1, CPI and NFP): after the release bar and the next two closed (08:30, 08:31, 08:32 ET), side =
  the sign of close(08:32) - open(08:30) when its size is at least 3 x (price / 4,000) USD and the 08:32 bar closed
  the same way; entry at 08:33's open; the stop beyond the three bars' opposite extreme (at least 4, at most 12 x
  price / 4,000; beyond that, no trade); target 8 x price / 4,000; exit after 15 minutes. **S2-C3x:** no target,
  exit after 30 minutes.
- Design: F1 on 2023-11 .. 2026-02 (five half-years), S2 on 2021-09 .. 2026-02 (CPI + NFP, M1, the auditor's costs);
  then the window 2026-03-01 .. 10-14 (seen for F1 / S2's family) and the fresh days from 2026-10-14.

**Result** (`shadow/count3.py`, `shadow/no_chase.py`):

| F1 variant | Design trades | Design R | Half-years + | Window trades | Window R | Window USD | Max DD |
|---|---|---|---|---|---|---|---|
| F1 CONF-72 as frozen | 140 | +0.118 | 4/5 | 34 | +0.183 | +52.9 | 26.7 |
| F1-C3a (count three, check again) | 77 | -0.039 | 3/5 | 17 | +0.249 | +31.5 | 15.1 |
| F1-C3b (C3a + the level held) | 71 | -0.046 | 3/5 | 13 | +0.389 | +38.6 | 15.1 |
| F1 + no run of >= 4 ATR with the trade in the last 15 min | 110 | +0.034 | 3/5 | 24 | +0.141 | +21.1 | 19.7 |
| **F1 + no run of >= 8 ATR with the trade in the last 60 min (no chase)** | 114 | **+0.180** | **5/5** | 26 | **+0.245** | +41.2 | 32.0 |

**Counting three hurts F1 on the design data** (-0.04 R against +0.12): it skips the immediate stop-outs like
2026-04-08 but enters the survivors three bars later at a worse price with a wider stop and the same 8 U target;
on the seen window it raises R a trade but halves the trades. Not kept. **The cause of 2026-04-08 - chasing the end of
a long run - does hold as a filter: no entry after a run of 8 ATR or more with the trade over the last 60 minutes**
(design +0.180 R, 5/5 half-years; the window +0.245 R on 26 trades; chosen among four variants on the design data
alone). S2-C3 (entry at 08:33 ET in the 3-minute direction): only 12 releases in five years qualify - after CPI / NFP
the three-minute swing is usually wider than 12 x price / 4,000, so the stop does not fit the account (2021-23: 4
trades -0.523 R; 2023-26: 7 trades -0.004 R; 2026-08-12 itself skipped for that reason) - too few to judge.

**Correction (2026-10-18):** the no-chase filter above measures the run in M1 ATR, which swells inside a spike; it
would *not* have blocked 2026-04-08 (that signal: ret60 = 5.7 M1 ATR with an M1 ATR of 6.6 USD - a 38 USD run). What
the system saw then: the round 4850 reclaimed (sweep + reclaim), MACD and Stochastic agreeing, H1 4.1 ATR above its
EMA50, the 72-hour high 4828.65 already behind, the fast-tape ratio 1.986 (just under 2.0), 3 minutes into the Asian
window, the H1 leg against (-1), and an 8 USD stop = 1.2 M1 ATR. Every F1 check measures strength, so in a vertical
spike all of them light up at its top - a mechanical panic buy (the owner: "it had already run that far - why buy?").

**Round 12b - "already run too far", measured with a yardstick that does not swell (written before it is computed):**
X1 = F1 + the last 60 minutes' run with the trade (ret60 x M1 ATR, in USD) below 1.5 H1 ATR; X2 = F1 + the close
within 3 M15 ATR of the M15 EMA(20) the trade's way; X3 = F1 + a stop of at least 1.5 M1 ATR. Design first (five
half-years), then the seen window.

| F1 variant (`shadow/too_far.py`) | Design trades | Design R | Half-years + | Max DD | Window trades | Window R | Window USD | Blocks 04-08? |
|---|---|---|---|---|---|---|---|---|
| F1 as frozen | 140 | +0.118 | 4/5 | 30.4 | 34 | +0.183 | +52.9 | no |
| X1 60-min run < 1.5 H1 ATR | 119 | +0.147 | 4/5 | 22.3 | 28 | +0.270 | +54.7 | no (that run was 0.98 H1 ATR: the H1 ATR was 38 USD) |
| **X2 within 3 M15 ATR of the M15 EMA(20)** | 128 | +0.098 | **5/5** | 25.1 | 29 | +0.188 | +48.4 | **yes** (3.72) |
| X3 stop >= 1.5 M1 ATR | 136 | +0.078 | 3/5 | 26.9 | 31 | +0.285 | +66.4 | yes (1.21) - but worse on design |
| X1 + X2 | 110 | +0.131 | 4/5 | 26.0 | 24 | +0.241 | +45.2 | yes |

The owner (2026-10-18): "this alone makes no sense - no wonder everything ended in losses." The lesson behind it:
the rules were assembled from strength signals and statistical filters without a trader's basic no-go checks first
(do not buy the top of a vertical run; buy value, not extension; no stop inside one bar's normal swing).

### Round 13 - the owner's own setup, rebuilt from the owner's words (2026-10-18) - written before it is computed

The owner: "this one trade alone does not match the setup I described"; "you must buy before it breaks, or after it
spikes, wait for the moment; and if it has run very far, that setup is void - find a new one." (docs/OWNER_TRADING.md:
buy the pullback to structure in the trend, the stop beyond the structure, the target before the next resistance; no
chase - sell / buy the retest; in a range, the edges after the reclaim.) Every earlier rule's entries are judged
against this first; the numbers second.

**OWN-RT, the retest after the break** (a BUY; a SELL mirrored), gold, M1 entries, 00:00-20:00 UTC:
1. The tide: H1 EMA(20) rising over 3 bars and the H1 close above EMA(50) (the largest timeframe H1).
2. The break: an M5 close above the highest high of the previous 24 M5 bars (2 hours): the level L = that high.
3. Void (never enter): price runs more than 2.5 M15 ATR(14) beyond L before it comes back to retest; an M5 close
   below L - 0.5 M5 ATR (the break failed); no retest within 120 minutes.
4. The retest: an M1 low within 0.25 M5 ATR of L (or below it, but no M5 close below L - 0.5 M5 ATR).
5. The trigger: after the retest touch, the first M1 close above the previous M1 bar's high (the dip turns up).
6. Entry at the next M1 open; the stop below the lowest low since the retest touch minus 0.5 M5 ATR (beyond the
   structure); the stop must be 3-10 U (U = price / 4,100 USD) or no trade.
7. The target: the impulse high since the break minus 0.1 M5 ATR (before the resistance); at least 1 R or no trade.
   The stop to the entry at 0.6 of the target; time exit after 180 minutes. One position at a time; each break used once.

Design 2023-11 .. 2026-02 (five half-years), then 2026-03-01 .. 2026-10-16 (new as a rule), the real costs
(`agents/journal/jlib.py`), the losers in three kinds against the coin, and charts of the trades checked by eye
against the owner's description before the numbers are read.

**OWN-RT result** (`shadow/own_retest.py`): design 317 trades, -0.121 R, -101 USD (the coin side -0.051); 2026-03 ..
10-16 148 trades, -0.164 R, -144 USD. **The charts (`shadow/rt/`) show the code did not do what the owner said, in two
ways:** (1) it entered on the first M1 close above the previous bar while the pullback was still falling, the stop
under a low that was not yet a higher low - the dip went on through the stop and then the run resumed (e.g. a BUY
2026-08-05 19:49 Thai at 4196 stopped at 4188, then 4240); (2) it counted as a "retest" a full reclaim of the level -
price back inside the old range, a failed break that should be void (a SELL 2026-03-04 13:38 Thai).

**OWN-RT2 (written before it is computed; the window 2026-03 .. 10-16 has now been seen for this family):** as OWN-RT,
and (a) void the moment an M1 close goes back beyond L by more than 0.25 M5 ATR (the break failed); (b) the owner's
"count three" in its place: after the retest touch, the pullback's extreme counts as a higher low (a lower high for
a sell) only once three M1 bars in a row have closed without a new extreme; the entry needs, after that, a close above
the high of the bar that made the low; the stop below that low minus 0.5 M5 ATR.

**OWN-RT2 result:** design 149 trades, win 23 %, -0.259 R, -109.6 USD (the coin -0.138; every half-year negative);
2026-03 .. 10-16 (seen) 71 trades, +0.014 R, +24.9 USD (the coin -0.067), max DD 44.5. Most breaks were voided as
failed (3,328 of 7,267 on the design data): gold's 2-hour breaks fall back more often than they hold.

**Every F1 CONF-72 trade on 2026-03 .. 10-14, its cause, and the other side** (`shadow/f1_losers.py`, the list in
`shadow/f1_test_losers.csv`; `shadow/f1_logic.py`). The owner: "list every loser and why; would the other side
scalp at a profit?" and "were the winners guesses, or logical entries with statistical support?"
- **The 16 full losers by cause:** chasing (the last hour's run >= 1 H1 ATR or the close >= 3 M15 ATR above the M15
  EMA20) 8 (04-08, 05-07 08:49, 05-29, 06-03, 07-28, 07-30, 08-14, 09-14 16:45); the stop inside the normal swing
  (< 1.5 M1 ATR) 4 (04-29 19:34, 05-07 15:06, 05-07 19:42, 09-28); the H1 leg against 1 (04-29 19:55); entries that
  fit the logic 2 (06-18 23:56 late in New York; 08-12 21:19 two hours after CPI in a fast tape). Repeated attempts at
  the same place: 05-07 three times at the refused 72-hour high, 04-29 twice in 20 minutes, 09-14 again 25 minutes
  after a win.
- **The other side does not pay:** reversing every F1 signal, design 2023-11 .. 2026-02: same exits -0.252 R (-130
  USD), scalp 5 USD / same stop 30 min -0.272, scalp 5 / 5 -0.282, scalp 3 / 3 15 min -0.298; the window -0.04 ..
  -0.21 R. Most losers went the other way (the mirror would have won 11 of 16), but the winners go strongly our way,
  so the mirror of all signals loses.
- **The winners were not "any side wins in a big swing":** in neither period would the other side, with the same
  target and stop, also have won (design 0 of 45 winners, window 0 of 16). Of the window's 16 winners, 6 fit the
  owner's logic, 9 were chases, 1 had a stop inside the swing.
- **Logic against the numbers:** the window - logic-fit entries 9 trades, 67 % win, +0.685 R, +41.2 USD; chases 18,
  +0.170 R; stops in the swing 5, -0.396 R. The design data - logic-fit 70 trades +0.116 R, chases 52 +0.098 R: on
  the larger sample the split does not yet show the logic carrying the result. F1's side choice beats shuffled sides
  on the design data (+0.118 against +0.032 R, the portfolio agent) - modest support.

### Round 14 - the chart-state statistics, triple screen + compression (owner, 2026-10-18) - written before it is computed

The owner: "knowing at the entry which trade will go the wrong way is your job: collect the statistics of what the
chart looks like on every timeframe by the triple screen, and on the trading timeframe whether this form means price
is about to run - with the compression, a run in the near future." A table of chart states and what followed:

- **Points:** every M5 close 00:00-20:00 UTC, gold, design 2023-11 .. 2026-02, the window 2026-03 .. 10-16.
- **The state (all from closed bars):** H1 tide (EMA20 rising over 3 bars and the close above EMA50 = up; the mirror
  = down; else mixed); M15 tide (the same on M15); M5 position against the M15 EMA20 (pullback: the close on the
  other side of the M15 EMA20 from the H1 tide, within 1 M15 ATR; extended: more than 2 M15 ATR beyond it the tide's
  way; else neutral); M5 compression (the Bollinger(20) width percentile over the previous 288 M5 bars: <= 20 squeeze,
  >= 80 wide, else normal); the session (Asia 00-07, London 07-12, New York 12-20 UTC).
- **What followed (from the M5 close's mid price; 5 USD scaled by price / 4,100):** whether price ran 5 USD either
  way within 30 minutes ("a run"); which side reached 5 first within 60 minutes; the median move against before +5.
- **Selection:** a state counts when it has at least 80 design points and its "the H1 tide's side reaches +5 first"
  (or the other side) is at least 58 % in at least 4 of 5 half-years. The chosen states are then traded (TP 5 / SL 5
  scaled, entry at the next M1 open, real costs, 60 minutes) on the design data and once on the window.

**Round 14 result** (`shadow/chart_states.py`, `chart_states_trade.py`; 143,483 design points, 38,772 in the window;
a first run of the table counted the points with no 5 USD run as "the tide's side did not get there first" - fixed
before the numbers below; and a column named `squeeze` collided with pandas' DataFrame.squeeze in the trade script -
fixed):
- **Whether price runs 5 USD is not the problem:** within 60 minutes it does from 67-87 % of the design points and
  93-98 % of the window's (gold's M15 ATR in 2026: median 8.7 USD).
- **Compression does not mean a bigger run soon - the opposite:** a 5 USD run within 30 minutes after a squeeze
  (BB width <= 20th percentile) 43 %, normal 52 %, wide 72 % (design); the median range over 30 / 60 / 120 / 240
  minutes is smaller after a squeeze than after a normal width in both periods (e.g. 240 min: 20.0 vs 21.0 USD design,
  33.2 vs 32.7 window - equal). Volatility clusters: wide stays wide.
- **Which side gets there first: about 50 % whatever the triple-screen state** - the H1 tide's side first (among
  the points with a run): M15 against / mixed / with 0.519 / 0.514 / 0.488; pullback / neutral / extended 0.504 / 0.502
  / 0.505; squeeze / normal / wide 0.491 / 0.504 / 0.509; Asia / London / New York 0.506 / 0.497 / 0.504.
- **Only three states passed the selection** (H1 and M15 disagreeing on a pullback: the M15 side first 58-64 % in 4-5
  of 5 half-years); traded (TP 5 / SL 5, real costs, 60 min): design 498 trades -0.020 R (-23 USD), the window 178
  trades -0.077 R (-74.9 USD). Not usable.

The coarse chart state (three timeframes' trend + compression + session) predicts how much price moves, not which
way it goes first.

### Round 15 - the owner's chart forms on M1 (2026-10-18) - written before it is computed

The owner's example (MT5 M1, 2026-10-16 22:45-23:50 server time = 19:45-20:50 UTC; our data matches it): price held
a box of about 4166-4169.5 for an hour, tested its top at least three times, then broke out of the bottom to 4163.
"There are also sideways-up, sideways-down, and the ones that run 3 ATR out and snap back."

- **Box break:** at each M1 close, the box = the high / low of the previous W bars (W = 30 or 60) when its height is
  at most 1 M15 ATR(14); a break = the first M1 close beyond an edge by 0.1 of the height (the previous close inside).
  Touches: M1 swing extremes (the extreme of 5 bars) within 15 % of the height from an edge, at least 5 bars apart.
  The box's slope: the regression slope of the closes over W, in heights: above +0.5 sideways-up, below -0.5
  sideways-down, else flat.
- **3-ATR run:** the first M1 close at least 3 M1 ATR(14) beyond the M1 EMA(20); the side to measure is the snap back.
- **What followed:** from the next M1 open's mid price, which reached 5 USD (x price / 4,100) first within 60
  minutes - the break's direction (or the snap back) or the other; by touches, slope, session, H1 tide; by half-year.
- A form counts when its side reaches 5 first in at least 56 % of the cases in at least 4 of 5 design half-years
  (n >= 100); those are then traded with real costs (TP 5 / SL 5, and the box's other edge as the stop) on the
  design data and the window.

**Round 15 result** (`shadow/forms.py`): the break direction / the snap back reached 5 USD first, among cases with a
run (design | window):
- Box breaks, all: 49.7 % (6,292) | 49.9 % (2,265). 3+ touches on the broken edge 48.3 % | 49.8 %; 3+ touches on the
  other edge (the owner's example: tops tested, then the bottom broke) 51.2 % | 53.1 % (by half-year 52.5 / 48.2 /
  50.7 / 56.9 / 50.0); sideways-down boxes 53.6 % (730) | 53.8 % (353); sideways-up 48.5 | 50.2; with / against the H1
  tide 50.5 / 49.5 | 48.4 / 51.8.
- 3-ATR runs (the first M1 close >= 3 M1 ATR from the M1 EMA20), the snap back: 50.3 % (10,318) | 51.0 % (3,302); every
  half-year 49.1-51.8 %.
- None reaches the bar (56 % in 4 of 5 half-years). Taken alone, these forms do not tell the side; the leanings
  (sideways-down boxes, 3+ tests of the other edge) are 1-4 points.

The owner: "that was only an example - find the other forms that come before price really runs." -> the run
catalogue (effect to cause), next.

### Round 16 - trading the range (sideways), the owner's trade-1 style (2026-10-18) - written before it is computed

The owner: "can our system trade sideways?" The bot has the pieces (the market map's range box, the chart read's
sweep-and-reclaim, S1's fade of false breaks) but no setup that trades inside a range as the owner did in trade 1
(buy the bottom, sell the top; after a false break, enter on the close back inside, the stop beyond the sweep).
- **The range:** the high / low of the previous 24 or 48 M5 bars (2 or 4 hours) with a height of 10-30 USD (x price /
  4,100) and at least 2 earlier tests of the edge in play (M5 highs / lows within 15 % of the height from it).
- **R1 edge fade:** an M1 bar trades within 10 % of the height of an edge (inside the range) and the next M1 close
  turns back (below the previous bar's low at the top / above its high at the bottom): enter toward the middle;
  the stop beyond the edge by 0.2 of the height (3-10 USD, else no trade); target 5 USD (x price / 4,100), at most to
  the range's middle; 60 minutes.
- **R2 false break (trade 1's improvement):** an M1 bar trades beyond an edge, then within 5 bars an M1 close comes
  back inside by at least 0.1 of the height: enter back toward the middle; the stop beyond the sweep's extreme plus
  0.25 M5 ATR (3-10 USD); target 5 USD / the middle as R1.
- Design 2023-11 .. 2026-02 by half-year, then the window 2026-03 .. 10-16; real costs; one position at a time; the
  losers' causes.

**First, crude result - parked (owner: "finish the earlier work first, sideways comes next")** (`shadow/range_trade.py`):
R1 design 6,378 trades -0.107 R, window 1,619 -0.100 R; R2 design 4,345 -0.167 R, window 1,521 -0.151 R; negative in
every half-year and month. The count (about 12 a day) shows the code takes every overlapping 2-4 hour window as a new
range - not the owner's one clear range after a run; to be redone properly (one range at a time, defined after a
run, with the owner's entries) when the owner calls it.

**F1: too early? a wider stop? (owner, 2026-10-18; `shadow/too_early.py`, `shadow/wider_stop.py`).** Stopped losers:
design 61 = wrong way 35, fell short 3, too early 23; the window 15 = 13 / 0 / 2; 47 % of the window's stopped
within 5 minutes. The stop in M15 ATR(14), the window: < 0.5 -> 12 trades, 17 % win, -0.473 R, -24.9 USD; 0.5-0.75 ->
12, 58 %, +0.445 R; 0.75-1.0 -> 8, 62 %, +0.671 R (design: < 0.5 -> 20 trades +0.184 R - not confirmed there).
Widening every stop (same target): design x1.5 +0.086 R (+73.2 USD), x2 +0.068 R (+91.8 USD) against x1 +0.118
(+58.4); the window x1.5 +0.088 R (+54.0), x2 +0.043 R (+42.8, max DD 39.1, six average losses 37.4 USD) against x1
+0.183 R (+52.9, max DD 26.7); with the account's 10 USD cap x2 turns the window negative (-10.4 USD). A wider stop wins
more often (44 -> 50 %) but loses more per loss: no help, and it does not fit a 50 USD account.

**A stop floor instead (owner: "do what you said, and widen the SL"; `shadow/stop_floor.py`):** the stop raised to at
least a share of the M15 ATR(14) only where it was tighter, no account cap. Design (target 8 U): floor 0 -> +0.118 R,
+58.4 USD, max DD 30.4; 0.5 -> +0.111, +57.9, 31.2; **0.75 -> +0.116, +68.6, 21.9**; 1.0 -> +0.094, +67.0, 28.1 (keeping the
target/stop ratio: 0.75 -> +0.110, 5/5 half-years). Latest six months: floor 0 -> 34 trades +0.183 R, +52.9 USD, DD
26.7, 6/7 months; **0.5 -> +0.198 R, +50.8, DD 21.4, 5/7**; **0.75 -> +0.212 R, +43.1, DD 26.8, 4/7**; 1.0 -> +0.170, +35.8, DD
45.1. A floor at 0.5-0.75 M15 ATR keeps the result about where it was (R a trade slightly up, the total about level
or lower, months less even); 1.0 and more costs money. F1 + a 0.5 M15-ATR stop floor is the widened version kept.

**Reversion agent - final** (`agents/reversion/notes.md`). Limit entries and stretch-fades fail: the frozen REV-A
(H1-trend stretch-fade with a 1-ATR limit, 4/4 ATR, 120 min; design +0.013 R, REV-B +0.171) lost -0.379 R on the
window (59 trades, -163 USD; the coin -0.147), REV-B -0.332 (29 trades). On the window the design's loser marks
turned into winner marks (low half of the 4-hour range, M15 against, London, a flat H1) - gold fell from ~5,000 to
~4,100 with wide swings and dips bought in an H1 uptrend were mostly the start of the next leg down. **Three loser
marks kept their sign in both periods: the last bar against the trade by >= 1 ATR, a 15-bar leg against by >= 4 ATR,
the first fall off a fresh 4-hour extreme**; the 12:00-15:30 ET afternoon was the worst slot. Round numbers: price
breaks through them more than it bounces (beats placebo levels in 8-9 of 10 comparisons) but too little to pay the
costs (-0.065 .. -0.15 R gold; FX 30/30 pips about -0.005 R).

### Round 8 - every measure in one weighted model (owner, 2026-10-17: "zigzag, momentum, which ones are not in the weights yet?") - written before it is computed

What the earlier weights left out: the ZigZag swing structure (the indicator score had none; round 3's model had
only the H1/M15 EMAs), the ticks (only the triple screen's timing), and the levels and the session clock (in
round 3's model, not in the score). Round 8 puts them all into one LightGBM: round 3's 62 features, the 52
indicator votes of round 6, the ZigZag structure on M5 / M15 / H1 (the bot's chart read: the structure now, the
open leg's size in ATR and its retrace, the legs since the structure changed; signed by the side) and the tick
features (from 2025-10 only; missing before). Fitted on 2023-11 .. 2026-02-14; the tool (5/4, 5/6, 8/6, 10/8), the
score cut and the session filter chosen on 2026-02-14 .. 04-14; **tested once on the latest six months**, with the
stop to the entry at 0.6 of the target (iteration 1's exit). The losers in three kinds against the coin.
