# Precursors - the chart before gold really runs, on six timeframes (owner, 2026-10-18)

The owner: "research the runs of the price chart on M1, M5, M15, M30, H1, H4, every timeframe related; collect the
statistics and the forms of price before a run, keep them as pictures to learn that this chart form has a chance to
run; then see which structure the larger timeframe has and how the smaller timeframe runs. Filter: M1 runs at least
5-10 points within 15 minutes, at 07:00, 08:00, 09:00 onward, 13:00, 14:00 onward, 19:00, 19:30, 20:30, 21:00, 22:00
onward (Thai time)." Then: "when we see a chart that matches the statistics that it will run, we may enter before it
runs" - this research comes first; Setup OWN V2 (faster entries from the kept forms, "exit on the timeframe you
entered") is built only from what passes here.

Agreed with the owner (2026-10-18) before anything was computed:
- Gold (XAUUSD) first; the majors later.
- A run: at least **10 U** (main) or **5 U** (floor) one way **within 15 minutes**; U = price / 4,100 (1 U = 1 USD at
  4,100; the owner's pip = 1 USD), so older years keep the same relative size.
- The times are market events, DST-aware (their Thai clock in summer): Tokyo 09:00 (07:00 TH), China 09:00 (08:00
  TH), Asia 09:00-12:00 TH, Frankfurt 08:00 Europe/Berlin (13:00 TH summer), London 08:00-12:00 Europe/London (14:00-
  18:00 TH summer), New York 08:00 / 08:30 / 09:30 / 10:00 ET (19:00 / 19:30 / 20:30 / 21:00 TH summer) and 11:00-14:00
  ET (22:00-01:00 TH summer). A single time = -5 .. +30 minutes around it.

## Written before it is computed (2026-10-18)

**Data.** Gold M1 (`gold.bars("M1")`). Design 2023-11-01 .. 2026-02-28 in the five half-years of `jlib.HALVES`
(2023-11, 2024-05, 2024-11, 2025-05 (four months), 2025-09). The window 2026-03-01 .. 2026-10-16 is read once, after
the kept forms are frozen below this file's "FROZEN" line. The older 2021-10 .. 2023-10 stays untouched as a spare
holdout.

**Timeframes.** M5, M15, M30, H1 resampled from M1 on UTC boundaries; H4 on the broker's server-day boundaries
(Europe/Athens, as MT5 draws it). A bar is usable at a decision only once it has closed.

**The run catalogue (effect).** An up-run starts at M1 bar i (s = low[i]) when within 15 minutes (bars opening at most
14 minutes after bar i) a high reaches s + X and no low goes below s first (the running high starts at bar i's close,
as the runs agent's catalogue). Down-runs mirrored. Overlapping same-side starts are one run (its start the extreme);
the run is followed until a pullback of 40 % of the move (floor 40 % of X) or 120 minutes: size, minutes to X,
duration. X = 10 U and 5 U.

**Decision points (the trader's moment).** Every M1 close inside the focus windows (weekdays). The decision is at the
bar's close; anything later is the future. Labels from the next bar's open (e):
- `next_up` / `next_dn`: a catalogued X-run of that side starts within the next 15 minutes (its start bar t+1 .. t+15);
- `first`: which of e + X / e - X price touches first within 60 minutes (+1 / -1; 0 none; both in one bar dropped);
- `mae`: for a following run, how far price went against e before the run's start (the stop an early entry needs).

**The chart state at each decision (closed bars only), per timeframe M1 / M5 / M15 / M30 / H1 / H4:**
- tide: EMA20 above its value three bars back and the close above EMA50 = up (mirror down, else mixed);
- structure: 7-bar fractal swings (3 each side, known 3 bars later); the last two highs and lows: HH+HL up, LH+LL
  down, LH+HL contracting, HH+LL broadening;
- leg: the latest confirmed swing is a low = an up leg (a high = down); with the structure = impulse, against it =
  correction; the leg's retracement of the previous swing;
- position: the close in the last 20 bars' range (0 .. 1);
- volatility: ATR(14) and Bollinger(20) width as percentiles of the last 120 bars;
- breakout: a close beyond the previous 20 bars' high / low within the last 3 bars;
- stretch and momentum: (close - EMA20) / ATR, the last 3 bars' move / ATR.
- M1 / M5 local forms: a 30-minute box (range <= 1 M15 ATR) and its break; a sweep of the last 60 minutes' low / high
  reclaimed by the close within 15 minutes; a staircase (three rising M1 swing lows / falling highs); a spike bar (range
  >= 2.5 M1 ATR); tick volume 5 / 60 minutes.
- levels: beyond today's server-day / the Asian / yesterday's high or low, the 72-hour extreme, the round 50, each in M15
  ATRs; minutes to / since a US release.
- across timeframes: the tide sum of H4 + H1 + M30 + M15; the nested state (H4 structure, H1 leg against / with it,
  M15 leg, M5 turn).

**What is read (design only, by half-year).**
1. *Does the form come before runs?* P(an X-run starts within 15 minutes | form) / the same probability expected from
   the same half-year, focus window and M15-ATR decile (the lift).
2. *Which way?* For a form with a side, the share of `first` going the form's way (and of `next_up` among runs).
3. *The larger timeframe -> the smaller timeframe's run:* for each H4 / H1 state, the chance of a run, its side
   against the H4 / H1 trend, size, speed, MAE, second leg.
4. Combinations (two and three forms across timeframes) searched the same way; the same search on labels shuffled
   within each half-year gives the number that pass by chance.

**Keep a form when** (all on design): n >= 100; the run lift >= 1.3 in at least 4 of 5 half-years; and, to be used for
a side, its side first >= 56 % in at least 4 of 5 half-years. The kept list is frozen here before the window is read
once (month by month). Pictures: for each kept or leading form, multi-timeframe charts (H4 .. M1 in one image, the
decision marked, the future shaded) of cases that ran AND cases that did not.

## Results so far (design 2023-11 .. 2026-02, X = 10 U; `analyze.py`, `withtrend.py`, out_*.txt)

Data checks: 636,560 decision minutes (499,814 design, 724 days); every timeframe state is older than the decision
(age >= 0); the windows move with DST (London 14:00 TH in July, 15:00 in January); one run label checked by hand.

- **When:** the window decides most. Share of minutes followed by a 10 U run starting within 15 minutes: NY 09:30
  ET (20:30 TH) 0.58, NY 08:00 / 08:30 / 10:00 ET 0.38-0.42, Asia 08:00 TH 0.24, Frankfurt 0.14, Tokyo 0.12, NY
  11-14 ET 0.15, London 08-12 0.10, Asia 09-12 TH 0.08 (H5 2025-09 .. 26-02 about twice the older halves).
- **Beyond the window and the volatility (M15-ATR decile):** only two single states raise the chance >= 1.3x in 4/5
  halves - a new low of the server day (lift 1.52) and a down spike bar (1.51); a break up out of a 30-minute box
  comes before runs LESS often (0.75).
- **Which way:** no single state sends +10 / -10 first its way >= 56 % in 4/5 halves; the best pooled 0.53 (a new
  day high/low, a > 2 ATR 60-minute move: continuation by 3 points).
- **The larger timeframe:** the first run to start goes with the H4 / H1 / M30 / M15 structure 49-51 % (drift
  0.50). A first count of "runs with the H4 structure 57-66 %" was an artefact (minutes with runs on both sides
  counted as "with") - corrected in `withtrend.py`. The next run goes AGAINST the M1 / M5 tide 56-61 %: the start
  must come after the decision, so a run against the last minutes' move is the one that can still start (the
  turning-point artefact again), not a side a trader can take. The adverse move before a run from an entry 1-15
  minutes earlier: median 3.4-3.8 U, 75 % 6.3-7.2 U, 90 % 10.6-12.7 U.

## Written before it is computed: once it starts, does it run? (`cont.py`)

From each decision close (ref), the first touch of ref +- K U (K = 3, then 2) within 30 minutes is the start (its side
given by the move). From the bar after the touch, within 60 minutes: ref + 10 U before back at ref (A), or before
ref - K (B). Random walk: A = K / 10, B = 2K / (10 + K). Read by window, half-year, the larger timeframes' structure /
tide relative to the start's side, a box / day-level break / 72-h extreme / sweep before it, the ATR and Bollinger
percentiles, a release just out. A state counts when it beats the random walk by >= 0.05 in 4/5 halves.

## The owner's method (2026-10-18, replaces the lift / combination reading above)

The owner: "the research is not to predict the result: look at the whole chart with every indicator and keep
statistical evidence - this form runs, this one fakes. Keep the price sets of each timeframe, looking back as far as
is sensible, as pictures; when the backtest or live trading runs, compare the price set of that moment with the
evidence and weigh whether it will run yet, which way and how far." And: "keep every case; cases that repeat with
more than 80 % similarity count as one set - the more often a set is seen, the more reliable that structure; then
compare the trigger with the stored data every time."

The combination search (`combo.py`) was stopped unfinished; `cont.py` (start then run or fake) is folded into the
library's labels below.

## The evidence library - written before it is built (`library.py`, `cluster.py`)

**Cases:** every focus-window decision minute (the windows above). The library is built from design cases only
(2023-11 .. 2026-02); the window's cases (2026-03 .. 10-16) are stored as queries for the later backtest and never
join the library before it.

**The price set of a case:** per timeframe the last L closed bars - H4 60, H1 72, M30 64, M15 64, M5 72, M1 90 (the
picture's panels) - the close path as 24 points (linear interpolation over the bars), z-normalised (the shape).

**Its states (74 categorical features, each counted once):** per timeframe - tide (3), structure (5), leg (3), RSI(14)
zone (< 30, 30-45, 45-55, 55-70, > 70), MACD(12, 26, 9) histogram sign x rising (4), Stochastic(14, 3, 3) zone (< 20,
20-80, > 80) x %K above %D (6), Bollinger(20, 2) position (below, lower half, upper half, above; 4), ADX(14) (< 20; >= 20
with +DI above / below -DI; 3), ATR(14) percentile of the last 120 bars (thirds), the close in the last 20 bars'
range (thirds), the path's height in that timeframe's ATR (< 3, 3-6, 6-10, > 10); and once - the server day's high /
low broken, the 72-hour extreme, the Asian range broken, yesterday's range broken (3 each), a 30-minute box (2), a
sweep of the 60-minute low / high reclaimed (3), within 0.25 M15 ATR of a round 50 (2), a US release within 30 min
before / after (3).

**Similarity of two cases** = 0.7 x the mean over the six timeframes of the correlation of their shapes + 0.3 x the
share of the 74 states that are equal (1.0 = identical). **One set** = similarity >= 0.80: cases are taken in time
order; each joins the most similar set's first case (its leader) when that similarity is >= 0.80, else it starts a
new set.

**Labels (what followed, from the decision close `ref`):** the first 10 U run (15 minutes, the catalogue) to start
within 15 minutes - its side, minutes until it starts, size, the move against before it; the same for 5 U; the first
+-3 U move within 30 minutes and then 10 U on that side before back at ref (ran) or back at ref first (faked) within 60
minutes; the largest move up / down within 15 and 60 minutes. The owner's classes: **ran up / ran down** (a 10 U run
starts within 15 minutes), else **faked up / faked down** (3 U out, back to ref before 10), **flat** (no 3 U move
in 30 minutes), **drift** (out 3, neither 10 nor back within 60).

**Counting:** consecutive minutes are almost the same picture, so a set's frequency is counted in **episodes** - its
cases at least 60 minutes apart - and its outcome shares weight each episode equally. Reliability = episodes (and days).

**Use later (the backtest, not now):** at a trigger, the sets whose leader is >= 0.80 similar to the moment give the
weights - ran up / down, faked, flat, how far, the move against first - each set weighted by its episodes.

**Support and resistance of the larger timeframes (owner, 2026-10-18: "up or down, look at where the form happens
against support / resistance - at an important level it weighs more; the levels come from the larger timeframes, e.g.
trading M1 / M5, look at M15 / M30 / H1"), added to the states before anything is built:** for M15, M30, H1 and H4,
the confirmed fractal swings (3 bars each side) of the last 384 / 192 / 240 / 180 bars (4 / 4 / 10 / 30 days) are the
levels; swings within 0.25 of that timeframe's ATR merge into one level whose importance is the number of swings in
it (1, 2, 3+). Per timeframe, two states: **where** - broke up (a level between that timeframe's close three bars back
and the price now, the price above it), broke down (mirror), at support (the nearest level below within 0.3 ATR), at
resistance (the nearest above within 0.3 ATR), between; and **how important** the nearest level within 0.3 ATR is (none,
1, 2, 3+). 8 more states (82 in all). The library's statistics are also read by these states, so the evidence says
how much a form at an important level adds.

## Revised by the owner (2026-10-18): the cases are snaps at the owner's times, not every minute

"The points we snap are the times I gave at the start: when it is 07:00 the system snaps the chart of each timeframe
from 07:00 back to the edge of what is visible, and keeps it." The per-minute library build was stopped unfinished.

**Snaps (written before anything is built; DST-aware, Thai clock in summer):** Tokyo / Asia 07:00, 08:00 and hourly
09:00 .. 12:00 Asia/Bangkok; Frankfurt 08:00 Europe/Berlin (13:00 TH summer); London 08:00 .. 12:00 Europe/London hourly
(14:00 .. 18:00 TH); New York 08:00, 08:30, 09:30, 10:00 (19:00, 19:30, 20:30, 21:00 TH) and 11:00 .. 14:00 hourly
(22:00 .. 01:00 TH) - 20 a day. A snap is the chart at that second: the M1 bar that closes at it (opened one minute
before) must exist, else the snap is skipped (market closed). Snaps falling on the same minute (DST weeks) are one case
with both names.

**What a snap keeps:** per timeframe the last **120 closed bars** (about one MT5 screen at the default zoom), the
close path as 40 points (z-normalised shape), the 82 states above (the path-height state now in design tertiles per
timeframe, as 120 bars are longer than the earlier lookbacks), and the M1 forms / levels / release state.

**What followed (from the snap's price):** the first catalogued 10 U and 5 U run (15-minute definition) starting
within 30 minutes after the snap (side, minutes to its start, size, the move against before it); +-10 U and +-5 U
first within 60 minutes; the largest move up / down within 15, 30 and 60 minutes; the first +-3 U within 30 minutes
then 10 U before back at the snap price (ran) or back first (faked). Classes: ran up / ran down (a 10 U run starts
within 30 minutes), slow up / slow down (3 U then 10 U, not inside 15 minutes), faked up / faked down, flat (no 3 U in
30 minutes), drift.

**Sets:** similarity as written (0.7 shape + 0.3 states, six timeframes); in time order, a snap joins the most similar
set's leader at >= 0.80, else starts a set. Snaps of the same day can share a set (19:00 and 19:30 see nearly the same
H4 / H1): a set's reliability is counted in **distinct days** as well as snaps. Design snaps (2023-11 .. 2026-02) only;
the window's snaps (2026-03 .. 10-16) are kept as queries for the backtest.

## The library - first results (design snaps 2023-11 .. 2026-02; `snaps.py`, `cluster.py`, `evidence.py`, `bigtf.py`)

15,200 snaps (11,937 design on 725 days; 3,263 window kept unread as queries). Classes over all design snaps (30 / 60
minutes after the snap): faked up 0.17, faked down 0.17, flat 0.15, ran down 0.15, ran up 0.14, drift 0.10, slow up
0.06, slow down 0.05.

**By the snap time (a 10 U run starting within 30 minutes, up + down):** NY 09:30 (20:30 TH) 0.78; NY 10:00 0.66; NY
08:00 / 08:30 0.56-0.58; NY 11:00 0.41; China 08:00 TH 0.39; Frankfurt / London 08:00 0.23; Tokyo 07:00 TH 0.21
(flat 0.31); Asia 11:00 TH 0.08 (flat 0.43). Up and down about equal at every time.

**Sets at >= 0.80 similarity:**
- All six timeframes together almost never repeat: 10,167 sets from 11,937 snaps; 95 % of the snaps have no earlier
  snap on another day at >= 0.80 (the nearest earlier snap's similarity: median 0.74, 90th percentile 0.82).
- By layer (the owner's "larger timeframe -> smaller"): H4 + H1 1,825 sets (most repeat only inside one day - six H4 bars
  a day), M30 + M15 5,674, M5 + M1 8,090. The evidence a trigger finds (earlier snaps, other days, >= 0.80): H4 + H1 none
  for 56 % / >= 5 days for 18 %; M30 + M15 53 % / 25 %; M5 + M1 59 % / 20 %.
- By eye (`png/sets/`): the members of a set do look alike in its layer (setup set 121, 54 days: M30 / M15 a staircase up
  after one impulse, a pause, then up again at the snap) - and their outcomes differ (faked up 0.41, ran 0.27, flat 0.07).
- The most frequent sets mostly mirror the base: median |up - down| 0.065 (H4 + H1), 0.08 (M30 + M15), 0.12 (M5 + M1).
  Among 82 trigger sets seen on >= 10 days, 12 lean by >= 0.30 (about 2-3 expected by chance at their sizes; the sets
  were picked after the fact). The clearest: **trigger set 125** (62 snaps, 56 days): M5 spikes up from a flat base to a
  new high and M1 makes its first dip from the top -> ran / slow down 0.32 vs up 0.13, the same lean in 2023, 2024, 2025
  and Jan-Feb 2026. A candidate, not a rule: the window judges it.

**The larger timeframes (`out_bigtf.txt`):**
- The H4 / H1 / M15 structure (up, down, contracting, broadening) and their pairs: runs 0.25-0.37, up and down within a
  few points everywhere, no lean that keeps its sign by year.
- Support / resistance: **a close back through a level - "broke down" through an M15 / M30 / H1 level within the last 3
  bars of that timeframe - comes before more runs (0.35-0.38 vs 0.28 between levels) and more UP than down (0.28-0.30 vs
  0.18-0.19); H1: up - down +0.06 / +0.04 / +0.16 / +0.13 by year (4 of 4).** "Broke up" leans down only weakly (0.16-0.19
  vs 0.20-0.24, mixed by year): a bull-market asymmetry (dips through levels bought) to be checked on the window, where
  gold fell.
- **At an important level price runs LESS within 30 minutes, it stalls:** at an H4 level touched 3+ times runs 0.20-0.23
  vs 0.31 between levels, flat 0.22 vs 0.15 (H1 3+: 0.23 / 0.23; M15 3+: 0.23 / 0.20). At an important level the form
  is followed by a pause more often, not by a bigger run.

## Revised by the owner (2026-10-18): "similar" means the same formation, not the same candles

"Similar does not mean identical down to the candles: it means the formation - how many peaks and troughs and how they
lie, how the indicators move - that is what being consistent or alike means." The 40-point shape correlation is
replaced by a **formation fingerprint**, written before it is computed (`fingerprint.py`):

Per timeframe, on its 120 visible bars, swings from an ATR ZigZag (a reversal of 1.5 x that timeframe's ATR(14) from
the running extreme confirms a peak / trough, known at the confirming bar), and 20 attributes:
1. how many confirmed swings in the window (0-2, 3-5, 6-9, 10+); 2. the current leg (after a peak = down, after a trough
= up); 3-4. the last three peaks: the newest vs the one before and that vs the one before it (higher / equal within
0.25 ATR / lower) - 3 x 3; 5-6. the same for the troughs; 7. the current leg's size against the previous leg (< 0.5,
0.5-1, > 1); 8. the previous leg against the one before it (same buckets); 9. where the close is: above the last peak,
below the last trough, else the upper / middle / lower third between them; 10. the net move over the window in ATR
(< -6, -6..-2, -2..2, 2..6, > 6); 11. RSI(14) zone; 12. RSI rising or falling over 3 bars; 13. divergence at the last two
peaks (price higher, RSI lower) or troughs (price lower, RSI higher), else none; 14. MACD histogram sign x rising; 15.
the MACD line above / below zero; 16. a MACD / signal cross in the last 3 bars (up / down / none); 17. Stochastic zone x
%K above %D; 18. the EMA20 / EMA50 stack (close > EMA20 > EMA50, the reverse, mixed) and the EMA20 slope; 19. Bollinger:
the position (4) and squeeze (width percentile < 0.2) / expanding (width up 3 bars) / normal; 20. ADX: < 20, >= 20
rising, >= 20 falling, x the DI that leads.
Plus, unchanged: support / resistance location and importance of M15 .. H4, and the global states (day / Asian /
yesterday's / 72-h breaks, box, sweep, round 50, release).
**Similarity** = the share of all attributes that are equal (each timeframe weighs the same); one set = >= 0.80, as
before; evidence counted in distinct days; the same reads (sets, evidence a trigger finds, pictures).
Calibration before any outcome was read: with 1.5 ATR every timeframe had 10+ swings in its 120 bars (H4: a swing every
~6 bars), not the peaks a trader counts on a screen; the ZigZag reversal is 3.0 x ATR(14) instead.

**Fingerprint result (design, `cluster_fp.py`, `out_cluster_fp.txt`):** with 20 attributes per timeframe (136 in all)
an 80 % match almost never happens: all six timeframes - 99 % of triggers find no earlier day; by layer 63-76 % none,
4-5 % >= 5 days; leaning sets (|up - down| >= 0.25, >= 10 days) 0-3 per layer vs 0-2 with shuffled outcomes. Exact
equality of fine codes (RSI 5 zones, Stochastic 6, Bollinger 12, ADX 5) is too strict for "the same formation".

**The core formation (written before it is computed; `cluster_fp.py core`):** 8 attributes per timeframe - the swing
count, the current leg, the newest peak against the one before, the newest trough against the one before, where the
close is (above the last peak, below the last trough, upper or lower half between), RSI rising / falling, the MACD
histogram sign x rising, the EMA20 / EMA50 stack (bull / bear / mixed) - plus the support / resistance location of M15 ..
H4. Same reads.

**Core-formation result (design; `out_cluster_core.txt`, `out_lean.txt`, `out_runprob.txt`):**
- Evidence a trigger finds (earlier snaps on other days at >= 0.80): M5 + M1 (16 attributes) none 4 %, >= 5 days 84 %,
  >= 20 days 58 %; M30 + M15 (18) 11 % / 63 % / 30 %; H4 + H1 (18) 12 % / 57 % / 20 %; all six together (52) 75 % / 4 % / 0 %.
  1,355 / 2,394 / 1,545 sets per layer.
- **Which way, from the snap price (the trader's view):** sets seen on >= 30 days whose +-10 U (or +-5 U) first leans with
  |z| >= 2.5: context 0 of 14 (chance 0.1-0.4), setup 1 of 31 (0.3-0.4), trigger 1 of 80 (0.8) - as many as shuffled
  outcomes give. One exception: the side of a start that ran on (3 U then 10 U) leans in 5 trigger sets vs 0.8 by chance.
- **Will it run, beyond the snap's time (outcomes shuffled within each time):** H4 + H1 sets 4 of 14 with |z| >= 3 (chance
  0.0; e.g. set 332: a 10 U run 0.39 vs 0.25 expected from its times; set 54: 0.21 vs 0.31); M30 + M15 1 of 31 (set 453:
  0.52 vs 0.35); M5 + M1 0 of 80 for the run, 6 of 80 for the largest 30-minute move (0.9). The context sets gather the
  same weeks (H4 changes six times a day), so part of this is the volatility regime of those weeks.

## Setup OWN V2 - the bot uses the library (owner: "mainly for the bot; the bot and the backtest first") - written before it is computed (`v2.py`)

**The library as the bot sees it (walk-forward):** at each snap, every EARLIER snap on an earlier day is in the library
with its outcome (the bot adds each snap and fills its outcome after 60 minutes). Matching per layer (core formation,
H4+H1 / M30+M15 / M5+M1): the earlier snaps with >= 0.80 of the attributes equal (every match, not only set leaders).
- **Run weight** = the base for this snap time (the share of earlier snaps at the same time followed by a 10 U run
  within 30 minutes) + for each layer with >= 10 matches, w x (the matches' run share - the base of their own times),
  w = n / (n + 30).
- **Side after the start (trigger layer, >= 10 matches):** among the matches, the share whose first 3 U ran on to 10 U up
  vs down; when they differ by >= 0.10, only that side is taken.

**The trade (gold, real costs `jlib`, one position at a time):** at a snap with run weight >= theta, a buy stop at the
snap price + 3 U and a sell stop at - 3 U (one cancels the other), live 30 minutes; the side is the one price breaks to.
A buy fills at the ask (max of the level and the bar's open ask) + 0.07, a sell at the bid - 0.07. **The entry
timeframe** = the smallest of M1 / M5 / M15 / M30 whose ATR(14) at the snap is >= 5 USD (else M30), and the exit lives on
it (owner: "exit on the timeframe you entered"): target max(5 USD, k_tp x its ATR), stop max(3 USD, k_sl x its ATR),
break-even at 0.6 of the target, time stop 6 bars of that timeframe. Stop slippage 0.15 (New York 0.20).

**Variants (design 2023-11 .. 2026-02 chooses; the window 2026-03 .. 10-16 once with the chosen one):**
- B0: every snap (no weight) - what the straddle does alone;
- B1: run weight from the time only (no formation) >= theta;
- B2: run weight with the formation layers >= theta;
- B3: B2 + the side filter.
theta in {0.30, 0.40, 0.50}; k_tp in {0.75, 1.0, 1.5}; k_sl in {0.75, 1.0}. Chosen: the best design R a trade among
B2 / B3 cells with >= 0.5 trades a day, if it beats B1 at the same theta (else the library adds nothing and that is the
finding). Reported: trades a day by session, win %, R, USD at 0.01 lot, months, worst loss / streak / max DD, the
losers' kinds, the entry timeframe used by month.

**V2 design result (`out_v2_design.txt`, `v2_design.csv`):** every cell negative. Straddle at every snap (B0) -0.067 ..
-0.095 R (10-11 a day); the time weight (B1) and the library weight (B2 / B3) cut the loss to -0.034 .. -0.10 R and the
library adds at most 0.004 R over the time alone (B3 vs B1, theta 0.50, k_tp 0.75, k_sl 1.0: -0.034 vs -0.038 R,
1,794 vs 1,786 trades, 2.5 a day). Stopped losers 58-80 % kind 1 (the start faded: the wrong way). By the rule
written above, the chosen cell is **B3 theta 0.50, k_tp 0.75, k_sl 1.0**; it runs once on the window, with **B1 at the
same cell as the comparator** (declared here before either is run).

**V2 window run (once, 2026-03-01 .. 10-16; `out_v2_window.txt`):**
- **B3 (the library) theta 0.50, k_tp 0.75, k_sl 1.0:** 1,212 trades (about 7.4 a weekday), win 43.6 %, **-0.017 R, -194.3
  USD** at 0.01 lot, worst -14.2, max DD 346 USD; months 03 +0.05 | 04 -0.05 | 05 -0.06 | 06 -0.08 | 07 +0.06 | 08 -0.01 |
  09 -0.06 | 10 +0.04; stopped losers 44 % wrong way, 5 % fell short, **51 % too early** (stopped, then the target came).
- **B1 (time only), same cell:** 582 trades (3.5 a weekday), win 43.8 %, **+0.003 R, -27.1 USD**, max DD 158; 03 +0.01 | 04
  +0.01 | 05 +0.01 | 06 -0.18 | 07 +0.09 | 08 +0.06 | 09 +0.05 | 10 -0.06; losers 34 / 4 / 62 %.
- Verdict: V2 as written does not reach the goal (+0.15 R). The formation library adds nothing over the time of day on
  design (+0.004 R) and costs on the window (it lets in twice the trades, the extra ones losing). Why the losers lost:
  in the window most stops are kind 3 - the 1-ATR stop of the entry timeframe sits inside the shake-out after the 3 U
  start (the target came after the stop); on design the start faded (kind 1, 58-70 %).

## Why V2's window trades lost - traced to the moment (owner: "analyse to the core what it measured at the real moment"; `v2_losers.py`, `audit.py`, `out_v2_losers*.txt`, `png/audit/`, `png/v2_losers/`)

1,212 B3 window trades: 519 targets, 418 stops, 246 break-even, 29 time exits. Each trade traced: the bot's inputs at
the snap, the entry in the move, the stop, the 120 minutes after.

1. **The measuring tool compared the wrong pictures.** The core fingerprint reads only the right edge of each timeframe
   (the last peak / trough, the current leg, where the close is, the indicators' direction now). By eye (`png/audit`):
   the 2026-08-27 14:00 losing buy (M30 / M15 falling, bouncing and falling again in a choppy swing) matched 2026-03-16
   17:00 at 100 % - a clean staircase decline. So the evidence averaged unlike charts, and it shows in the trades: the
   run weight does not rank them (R by weight band -0.10 / -0.03 / +0.11 / -0.02, no order), and where the trigger
   layer's side evidence agreed with the trade by >= 0.10 the trades lost most (82 trades, -0.169 R). Trades with few
   matches (<= 30) lost more (-0.07 / -0.14 R) than those with > 100 (+0.02 / +0.05).
2. **The trade's geometry:** the cell chosen on design has the target at 0.75 and the stop at 1.0 entry-TF ATR - every
   target is smaller than its stop (median 5.1 vs 6.8 USD); with costs it needs about 60 % wins among decided trades and
   got 55 %.
3. **The start is a fixed 3 U, not relative:** when 3 U is under 0.4 of the entry timeframe's ATR the start is inside the
   normal swing - -0.12 R (<= 0.3 ATR, 68 trades) and -0.06 R (0.3-0.4, 266); 0.5-0.7 ATR +0.01 R. 98 % of the stopped
   trades later traded through the straddle's other side (the start was one swing of a wider oscillation around the
   snap price), and half of those then reached the target (kind 3).
4. **A quiet hour before:** when the 60 minutes before the entry spanned <= 1.5 stops, -0.26 / -0.38 R (106 trades);
   > 3 stops +0.03 R. Breaking the prior 60-minute high / low did NOT help (-0.08 R vs -0.00 inside the range) - the eye's
   first reading of the loser charts (entries at the top of a box) was not borne out by the numbers.
5. **Creeping starts lose, strong starts win:** a trigger bar >= 1 entry-TF ATR in 24 % of the winners, 10 % of the stops.
6. **Times and entry timeframes:** NY 13:00 ET -97 USD, Asia 09:00 TH -69, NY 08:00 -48, London 08-11 negative; Asia 08:00
   TH +94, Frankfurt +81, NY 10:00 +49. Entry on M15 -0.075 R (378 trades), M5 +0.00, M1 +0.03, M30 +0.11 (41).

Points 2-6 were read on the window, so any rule built from them is window-informed: it is checked on design first, and
its window result is not a clean test. Next, in this order: (a) a matcher that compares the whole visible formation (the
ZigZag line of peaks and troughs across the 120 bars, and the indicators' paths), checked by eye before any trade; (b)
the start relative to the entry timeframe's ATR; (c) a target at least as large as the stop; (d) skip a quiet hour.

## LV - with the trend of every timeframe, sell the bounce into an earlier level (owner, 2026-10-18) - written before it is computed (`lvl.py`)

The owner's reading of 2026-09-02 (all timeframes falling; the bounces stopped at earlier levels - under the 07:18 /
07:44 peaks, then at the 07:02 low broken at 08:00 - and the fall resumed): "wait for price to hit a level, then sell
from there"; "put it into the code so it is used correctly". Mirrored for buys.

- **Moments:** every M1 close inside the owner's focus windows (as `plib.WINDOWS`), weekdays; gold; real costs (`jlib`).
- **The trend of every timeframe:** H4, H1 and M15 each down = EMA20 below EMA50 and EMA50 lower than three bars earlier
  (closed bars); all three down -> sells only; all up -> buys only; else nothing.
- **The entry timeframe** (owner's adaptive rule): the smallest of M1 / M5 / M15 whose ATR(14) >= 5 USD (else M15); its
  ATR = A.
- **Swings and levels:** M5 ZigZag (reversal 2 x M5 ATR(14), a swing known at its confirming bar), the last 8 hours.
  The bounce starts at the latest confirmed trough T (sells); price is in the up-leg from T and at least 1 A above it.
  The levels: every earlier swing of those 8 hours (a peak - type A - or a trough that price has since broken - type B)
  that lies above the price; L = the nearest one above. A level is used once.
- **Entry, two forms measured:** (a) LIMIT - a sell limit at L - k x A (k = 0.25 / 0.5), filled when the bid reaches it;
  (b) STALL - an entry-timeframe bar whose high came within k x A of L closes down (close < open, close < L): sell at
  the next M1 open. Void when an M1 close goes above L + 0.25 A first.
- **Exits on the entry timeframe:** stop L + 0.25 A, at least 3 USD and 0.5 A from the entry; target T1 = 1 x the stop
  distance, T2 = back to T (the bounce's start), T15 = 1.5 x the stop; each at least 5 USD; break-even at 0.6 of the
  target; time stop 12 bars of the entry timeframe; one position at a time.
- **Read on design (2023-11 .. 2026-02) by half-year:** trades a day, win %, R, USD at 0.01 lot, the losers' kinds; how
  often price turned short of / at / through L; the same entries at a placebo level (L shifted by a random 1-3 A) to see
  whether the level itself matters. One cell (form, k, target) is chosen on design and run once on the window.
- Pictures of 12 random design cases (M1 + M5 with T, L, the entry, stop, target) are checked by eye before any result is
  trusted.
Clarified before anything was computed (code review, 2026-10-18): "a level is used once" = once per bounce (the pair
of the bounce's start T and the level); a later bounce from a new start may test the same level again. The limit
order lives 60 minutes of clock time (not 60 bars).

**The test window moves (owner, 2026-10-18, confirmed): the latest six months from the current day = 2026-04-18 ..
2026-10-16.** LV's design = 2023-11-01 .. 2026-04-17 (the five half-years + H6 = 2026-03-01 .. 04-17, never read for LV
before). Selection rule, written before the design grid is read: **the real-level cell (form, k, target) with the best
design R a trade** runs once on the window; its placebo twin is reported next to it. A placebo bug was found and fixed
before this run (a new random level every minute broke "once per bounce"; test added, the old code fails it). Every
losing window trade is then traced with the pictures the bot saw (owner: "analyse every losing trade down to the
picture the bot really saw, not only the final number").

**A rule deviation found in the code and fixed (2026-10-18, from the design losers' journal):** LV chose the entry
timeframe from M1 / M5 / M15 only and fell back to M15; the owner's rule is the smallest of M1 / M5 / M15 / M30 whose
ATR covers 5 USD (H1 the largest). In quiet 2023-24 gold LV entered on M15 with an ATR of 1-2.5 USD while the stop
floor (3 USD) and the target floor (5 USD) were 2 and 3-5 of that ATR - not "exit on the timeframe you entered". Fixed
(M30 added; fallback M30), tests updated; every LV number before this line is void.

## LV2 - LV made to match the owner's rules, and a stop learned from the data (2026-10-18) - written before it is computed (`lvl2.py`)

An audit of LV against everything the owner has said found five deviations besides M30 (levels from M5 instead of the
larger timeframes; the bounce start from M5 whatever the entry timeframe; no exit on an entry-TF close through the
level; fixed trend timeframes even above an M30 entry; the level's importance unused) and fixed numbers of my own (a
3 USD stop floor, a 0.25 ATR stop / void buffer). The owner: "the losses from a narrow stop - adjust it from the real
data; I don't want the numbers too fixed." LV2:

- **Entry timeframe (ETF):** the smallest of M1 / M5 / M15 / M30 whose ATR(14) >= 5 USD, else M30; A = its ATR.
- **Trend:** every timeframe above the ETF up to H4 (from M5, M15, M30, H1, H4) agrees: EMA20 below EMA50 and EMA50 lower
  than three bars earlier (sells; mirrored for buys).
- **The bounce:** the latest confirmed swing of the ETF's own ZigZag (2 x its ATR) is a trough T (sells) and price is at
  least 1 A above it.
- **Levels from the larger timeframes:** the ZigZag swings (2 x that timeframe's ATR) of the timeframes above the ETF among
  M15 / M30 / H1 (ETF M30: H1), each over its last 120 bars (one screen), made before T. Swings within 0.25 of the larger
  timeframe's ATR merge into one zone (price = their mean; importance = how many swings, + whether an H1 swing is in it).
  L = the nearest zone above the price. Variant "important": only zones with >= 2 swings or an H1 swing.
- **Entry:** the stall as before (an ETF bar within k x A of L closes down and below L; k = 0.25 / 0.5), sell at the next
  M1 open. A pair (T, L) fires at its first stall; if a position is open then, that signal is skipped.
- **The stop learned from the data (walk-forward):** for every earlier signal whose outcome is already known at the moment
  (it reached the target, or its time ran out, before this decision), the overshoot = how far price went beyond L, in A,
  before it reached the target. b = the p-th percentile (p = 70 / 80 / 90) of the overshoot of the earlier signals that
  reached the target (at least 30 of them, else no trade). Stop = L + b x A, at least 0.5 A from the entry. A close beyond
  L + b x A before the entry voids the level.
- **Exits on the ETF:** target T2 (back to T) or T1 (= the stop distance), at least 5 USD; an ETF bar closing beyond L ->
  out at the next M1 open; break-even at 0.6 of the target; 12 ETF bars.
- Design 2023-11-01 .. 2026-04-17 chooses (form is stall only now - the limit lost in every half-year; k; target; p;
  all / important levels) by the best design R a trade; the window 2026-04-18 .. 2026-10-16 once; then every losing window
  trade traced with the bot's pictures.
Clarified in the code review before anything was computed: the level timeframes' swings are the swings a trader sees
on that chart - 5-bar fractals (2 bars each side, known 2 bars later) - not a 2-ATR ZigZag, which on M15 / H1 keeps only
large swings (on 2026-09-02 it would drop the 07:02 low 4316 and the 07:18 / 07:44 peaks the owner pointed at). The
bounce start T stays the entry timeframe's 2-ATR ZigZag trough. The outcome that teaches the stop: back to T (T2, at
least 5 USD) within 12 ETF bars, for every target variant.

## The owner's requirements -> code -> test (the checklist every version is re-checked against; 2026-10-18)

The owner: "analyse and synthesise my requirements into results, re-check that the code works as required, that nothing
conflicts, and what should fit the facts of the price chart - until all is correct; then run the bot's backtest, look
at the results and make each entry better, finding the timing inside my windows."

| # | Requirement (owner) | Where in LV2 | Test |
|---|---|---|---|
| R1 | gold; the focus windows (07:00, 08:00, 09:00+, 13:00, 14:00+, 19:00, 19:30, 20:30, 21:00, 22:00+ Thai), DST-aware | `plib.WINDOWS` -> decision minutes | test_windows |
| R2 | entry TF = the smallest of M1 / M5 / M15 / M30 whose ATR >= 5 USD; H1 the largest | `lvl.entry_tf` | TestEntryTimeframe |
| R3 | target >= 5 USD; exit on the entry TF (target / stop / time / a close against) | `trades`, `manage` | TestManage2, test_plan |
| R4 | the larger timeframes' trend agrees | `trend_tfs`, `setup_at` | test_trend_tfs, test_setup_* |
| R5 | levels from the larger TFs (M15 / M30 / H1), as seen on those charts; important levels weigh more | `level_tfs`, fractals, `merge_zones`, `level_in_front` | test_level_tfs, test_zones, test_level_in_front |
| R6 | wait for price to reach the level, enter the trend's way (limit vs stall measured: stall kept) | `stall` | TestVoidAndStall |
| R7 | the stop from the real data, not fixed | `outcome`, `learned_buffer` (walk-forward) | test_outcome, test_learned_buffer |
| R8 | everything relative (only the 5 USD target floor fixed) | Params: ATR multiples, percentiles | review |
| R9 | learn from the losers: each loser traced with the pictures the bot saw; adapt forward with rules written in advance | `lvl_losers.py` | eye check |
| R10 | the test window = the latest six months (2026-04-18 ..); design before it | `main` | review |
| R11 | tests first; prove the tests catch broken code; an independent re-derivation | test_lvl2.py, mutants, check | - |
| R12 | real costs; one position at a time | `Market` (jlib costs), `trades` busy | TestManage2 |

**LV2 design (2023-11-01 .. 2026-04-17, `out_lvl2_design.txt`):** every cell negative, -0.045 .. -0.100 R, 0.8-1.25 trades
a weekday. By exit (k 0.5, all levels, T1, p80; 769 trades): target 187 (+0.995 R), a close through the level 302
(-0.48 R), stop 90, break-even 108, time 82 (+0.20). Only 35 % of the traded signals went back to their start within 12
bars; 20 % of the close-exits did, and their overshoot (median 1.52 A) passed the learned stop (1.22 A): the close exit
cuts losses, it does not throw winners away. Price that reaches these levels goes through more often than it turns.
**Chosen by the rule (best design R): k 0.5, all levels, T1, p 80 (-0.045 R)** - run once on the window.

**A zone bug found in the losers' journal and fixed (2026-10-18), after the one window run of the chosen cell:** swings
merged by chaining (each within tol of its neighbour), so dense M15 / M30 / H1 swings formed bands tens of USD wide whose
mean was used as "the level" (zones of 10-57 swings); one swing seen on M15, M30 and H1 was counted three times. Fixed:
a zone is at most tol wide; importance = the finest level timeframe's swings in it. Tests added (the old code fails
them). The window result of the buggy version (262 trades, -0.072 R, -143.7 USD) is void; the corrected version is
re-chosen on design and run on the window - a second look at the window, disclosed, caused by a bug fix, not a tuning.

**Layer 4 (the independent re-derivation) caught a bug (2026-10-18):** 11 of 40 design trades had a different bounce start
- all on an M15 / M30 entry: those timeframes are both entry and level timeframes, and LV2 kept only their fractals, so
the bounce start came from a fractal, not from the entry TF's ZigZag as the rule says. Fixed (two swing sets per
timeframe), test added. The design grid above is void; rerun.

**LV2 proven before the design grid (owner: "if the code is not proven 100 %, don't run the learning period"):**
the independent re-derivation on three short slices with identical data - 2025-09/10 (all levels, T1, p90),
2024-05..08 quiet gold (important, T2, p80), 2026-01..04 volatile gold (all, T2, p70); entry TFs M1 / M5 / M15 / M30 and
both sides covered - every decision minute gave the same signals (119 / 117 / 320, none missed, none extra) and every
trade matched (16 / 15 / 94); 20 tests pass; 9 deliberately broken versions are all caught; the owner's 2026-09-02 case
holds; pictures checked by eye (levels at visible earlier swing zones, entries after a stall bar, stops beyond the level
by the learned buffer). Seen in the pictures (a matter of design, not a bug): at p70 the learned buffer is tiny (most
winners never went beyond the level), so the stop sits inside the poke through the level ("shaken out").

## Learning log (owner, 2026-10-18: "tell me how each round of learning changes things")

| Round | Learned (evidence) | Changed | Result after |
|---|---|---|---|
| 1 | the time of day decides how often gold runs (NY 09:30 78 % vs Asia 11:00 8 %); single chart states give the side 47-53 % | from predicting to an evidence library (the owner's direction) | - |
| 2 | six-timeframe pictures at 80 % never repeat (95 % of snaps without a match) | match per layer (H4+H1 / M30+M15 / M5+M1) | evidence for 18-25 % of triggers |
| 3 | the owner: similar = the same formation; 20 attributes a TF too strict | the core formation, 8 attributes a TF | evidence for 84 % of triggers (M5+M1) |
| 4 | V2 lost; the loser trace showed the matcher compared only the chart's right edge | stopped V2; LV from the owner's 2026-09-02 reading | - |
| 5 | LV limit at the level lost every half-year (levels run through); the stall about break-even | the stall form only | - |
| 6 | the design losers' journal: the entry TF rule missed M30; five more deviations from the owner's rules | M30 back; LV2 (levels from the larger TFs, start on the entry TF, close exit, trend from every larger TF, importance) | - |
| 7 | the owner: the stop from the data, not fixed | the learned stop (walk-forward percentile of winners' overshoot) | - |
| 8 | five-layer check: three bugs (microsecond times, chained zones, the start from fractals) | fixed; proven 100 % on three slices | - |
| 9 | pictures: at p70 the stop sits inside the poke (30 % of winners given up by definition) | the design run chooses p from 70 / 80 / 90 | design: p90 best (-0.032 R; p70 -0.094) |
| 10 | the four losers against the library: 1 and 3 (the owner would not take them) had evidence against / none | every trade records its library evidence (R13) | - |
| 11 | the owner: the M1 legs were not complete; one M1 bar has no weight; 3-5 legs, the last peak lower | LV3: the pause's legs on M1 as the entry | proven on slices (signals and trades 100 %) |
| 12 | eye check: the legs were counted from before the start's extreme | the exact minute of the extreme | test + checker |
| 13 | the owner: test the foundations first; the indicators were not MT5's, the library's levels chained, four more bugs (notes "The foundation") | foundation.py; every building block tested with planted bugs; the library rebuilt; learning on the latest 12 months | the walk-forward run next |
| 14 | LV3's walk-forward lost the exam; each component alone (trend, pullback, levels, the signal) measures at chance against a no-effect baseline | LV3 stops; every component is proven twice (code, premise) before assembly | exam -0.139 R |
| 15 | F1 CONF-72's components: only C4 (the 72-hour extreme) carries direction, and its sign flips with the market phase; no daily phase measure separates | - | - |
| 16 | V2b (the library by core codes) proven 408 / 408 but lost; the owner: the matched pictures do not look alike | the same picture redefined with the owner (outline, size, last leg, position, way, structure, break, pullback, smoothness, thirds) | learning -0.021 R, exam -0.169 R |
| 17 | the same picture rarely repeats within a year; a midnight look-ahead in the evidence (an hour-earlier snap as evidence) | evidence only from episodes >= 7 days before; the library to three years plus every 10 U run start | - |
| 18 | swings too few on 1.5-3.9 % of readings; the same picture repeats for 0.0-0.1 % of snaps (none three times); the same M5 + M1 situation leans the right way for the next half hour (edge +0.18 / +0.12, checked four ways) but the run starts after a 5-6 USD dip | the zoom; V2s trades the situation's lean; V2e waits for the dip | V2s learning -0.020 R, exam -0.085 R; V2e negative on learning |

## LV3 - the owner's "legs" as the entry (2026-10-18) - written before it is computed (`lvl3.py`)

The owner on LV2's losers (2026-03-09 09:29 sell): "the legs are not complete - it saw one long red bar engulf the green
and sold, but an M1 bar has no weight"; "there must be at least 3-5 legs; I count about 5 peaks on M1 with the 5th
lower; after price has moved a lot for its own timeframe there is a pause to choose the way; certainly sold too early";
"I can't say it definitively - you have more data; take my view as guidance and synthesise it into the trade."
Learning-log round 11. LV3 = LV2's context (the larger timeframes' trend, the entry timeframe, the levels from M15 / M30
/ H1, the learned stop, the exits on the entry TF) with the stall bar replaced by the pause's legs on M1:

- **The pause's peaks (sells; mirrored):** the M1 ZigZag swings (reversal s x M1 ATR(14), known at the confirming bar)
  made since the bounce's start T (the entry TF's ZigZag trough).
- **Entry (sell):** at the M1 close that confirms a new peak, when the pause has >= N peaks, that newest peak is LOWER
  than the highest peak of the pause, and the highest peak reached the level zone (>= L - k x A). Sell at the next M1 open.
  A run through every earlier peak makes the newest peak the highest - no entry - so the count restarts by itself.
  Once per (entry TF, T, L, side), the first qualifying peak.
- **The data chooses** (design 2023-11 .. 2026-04-17): s in {1.5, 2.0}; N in {3, 4, 5, "adaptive" = 3 when the move into T
  was < 5 A of the entry TF, else 5}; target T1 / T2; p in {80, 90}; k = 0.5, all levels. Best design R a trade -> the
  window 2026-04-18 .. 10-16 once. Five-layer proof before the design grid runs (owner: no learning run before the code is
  proven).
Clarified in the code review before anything was computed: "a run through every earlier peak restarts the count" is
implemented as: the pause = the peaks from the latest highest one on (that peak counts as leg 1). On 2026-03-09 the
peaks 5087.4, 5086.2, 5082.6, 5082.5, 5079.9 (1.5 M1 ATR swings) are a five-leg pause; the 09:14 run to 5095.3 starts a
new one, so LV2's 09:29 sell is not an LV3 entry.

| R13 | every trade records its library evidence - per layer the earlier snaps >= 80 % alike (days, best similarity) and what followed them (with / against / faked / flat); "no evidence" explicit (owner, 2026-10-18: "so it is not a random entry without a structure matching the library; compare every trade") | `evidence_journal.py` on every LV3 trade | test_evidence_journal |

## LV3 walk-forward - learning and testing in one run (owner, 2026-10-18: "do it") - written before it is computed (`wf.py`)

The owner asked whether to learn then test, or learn and test in the same run. The stop and the pattern library
already learn walk-forward; now the choice of LV3's settings does too, as the owner's "re-tune every 3-6 months":
- All 32 cells (s 1.5 / 2.0 x N 3 / 4 / 5 / adaptive x T1 / T2 x p 80 / 90; k 0.5, all levels) are simulated over the
  whole history, each its own one-position sequence.
- **At the start of each month** (first 2024-05), the cell with the best mean R a trade over the trades of the previous
  six months (at least 20 trades; else the previous month's cell stays; none before the first) is chosen for that month.
- The month's trades are that cell's trades opening in the month; a trade is skipped when the previous trade (of any
  cell) is still open.
- Reported: by month (cell, trades, win %, R, USD), and the two parts 2024-05 .. 2026-04-17 and 2026-04-18 .. 10-16 (the
  six-month exam) - both are out-of-sample for the settings; my own rule-structure decisions used only data before
  2026-04-18. The per-cell window results are not read; only the walk-forward result is.

## The foundation - every building block tested before any learning run (owner, 2026-10-18)

The owner: "did you test the indicators first? it wastes my time ... once we test, the only thing that may be wrong is
that the profit is not what we hoped - there should be no bugs left"; "unit test everything related"; "is a price
mismatch missing data or wrong code - check it well"; "what else in running a setup has not been tested like this?"

**The indicators differed from the charts the owner reads (MT5).** Transcribed from the terminal's own sources
(MQL5/Indicators/Examples) into `foundation.py`, the single source for the research: EMA seeded with the first price;
ATR = the simple average of 14 true ranges; RSI Wilder seeded with the average of the first 14 changes; MACD = EMA12 -
EMA26 drawn as the histogram, its signal an SMA(9) (the research had an EMA signal and called MACD - signal the
histogram); Stochastic main = 100 x sum(C - LL) / sum(HH - LL) over the slowing (the research averaged the ratios); ADX
= MT5's ADX.mq5, EMA smoothing from 0 (the research had Wilder's). `test_foundation.py` checks each against a literal
Python port of the MQL5 loop on random bars (with a flat stretch) and on 720 real M1 bars of 2026-03-09, plus hand
values; six planted bugs (each one of the old research's or the bot's variants) are caught.

**The data.** Our M5 / M15 / M30 / H1 / H4 bars built from M1 equal every stored FBS bar of 2025-10 .. 2026-10 (open
time, OHLC, and the tick volume - so no M1 minute is missing against the broker), except one bar the broker saved
while it was still forming (2026-10-06 16:05 M5 / 2026-10-05 08:00 H1). Bars with fewer than all their minutes are
missing at the broker too (the daily break, holidays). The learning + exam period's M1: unique, ordered, OHLC
consistent, a spread on > 99.9 % of the bars.

**Bugs the tests found (all fixed, disclosed):**
- The snap library's levels chained into wide bands (the LV2 zone bug, in `library.sr_levels` too): now
  `foundation.merge_levels` (a level is at most the tolerance wide).
- The RSI divergence attribute read the RSI at the swings' numbers in the swing list, not at their bars
  (`fingerprint.py`); only in the 20-attribute fingerprint (round 18's first table), not in the 8 core attributes the
  library and V2 used.
- An empty run catalogue (no run of a side) crashed the labels (`snaps.labels`, `plib.catalogue`); never met on the
  real data.
- The evidence record named the pattern the trade was counted into, not the one its evidence came from (they differ
  when a like pattern first appeared earlier the same day); the numbers were right, the id (and so the example
  pictures) could be another pattern's. `evidence_patterns` now records `pid` (the evidence's) and `joined`.
- The library on disk had been built with the old indicators while a trade's codes were computed with the new ones:
  trade 1's 102 trigger matches became 16 - neither number meant anything. A test now requires a moment's codes to
  equal the stored codes of a snap at the same bar (all 20 attributes, six timeframes, and the S/R codes).
- The evidence word's thresholds compared floats exactly (0.3 - 0.2 < 0.1): now with a 1e-9 tolerance.

**What is tested now (all suites, each with planted bugs it must catch):** `test_foundation` (13), `test_parts` (30:
bars vs the broker incl. tick volume, M1 cleanliness, fractals, level merging, the library's levels and where price
sits, the run catalogue incl. a missing minute, the snap labels ran / slow / fake / flat, the ZigZag, the fingerprint by
hand, similarity and sets, snap times through DST, `raw()` feeding each column its indicator, the core attributes, the
evidence word, the New York trades, the exit time, the loser pictures = the bars the bot had), `test_lvl` (37),
`test_lvl2` (21: + R / USD / the New York stop slippage, a full stop = exactly -1 R), `test_lvl3` (7: + one signal per
setup), `test_pattern_library` (7), `test_wf` (6: + the losing streak, the Thai weeks), `test_evidence_journal` (5: the codes equal the library's, the matches
re-counted by brute force attribute by attribute, the walk-forward rule, the pattern record). Planted bugs: 6
(indicators) + 13 (building blocks) + 15 (wiring): 33 caught; the 34th (the H1 picture selected by `last` instead of
`avail`) gives the same bars whenever the data is complete - equivalent, not a gap.

**The learning period (owner, 2026-10-18): the latest 12 months first** ("to see results quickly; if it works, run the
three years as before"): `plib.LEARN_START` = 2025-10-18 (the 3-year start kept as `LEARN_START_3Y`, one switch:
`wf.py 3y`); the exam `EXAM_START` 2026-04-18 .. `EXAM_END` 2026-10-17. The library holds the snaps from 2025-10-18
(5,115), the learned stop and the cells use only signals from it; older bars are only chart history (indicator
warm-up).

**LV3 re-proven on the 12-month learning period with the foundation code (2026-10-18 evening; `check_lvl2.py verify3`,
`out_verify_lvl3_f*.txt`):** the independent re-derivation (its own bars, EMA / ATR, swings, zones, legs and trade
walk) against `lvl3.signals` + `lvl2.trades` at every decision minute:

| Slice | Signals from | Cell | Signals (independent / lvl3) | Trades checked |
|---|---|---|---|---|
| A 2025-10-18 .. 2026-02-15 | 2025-11-01 | s 1.5, adaptive, T2, p80 | 113 / 113, none missed, none extra | 11, 0 mismatches |
| B 2026-02-01 .. 06-30 | 2026-02-15 | s 2.0, n 5, T1, p90 | 38 / 38 | 0 (fewer than 30 winners: no learned stop yet) |
| C 2026-06-01 .. 10-17 | 2026-06-15 | s 1.5, n 3, T1, p80 | 193 / 193 | 34, 0 mismatches |
| B2 2026-02-01 .. 06-30 | 2026-02-15 | s 2.0, n 3, T2, p90 | 95 / 95 | 0 (the same reason) |

The s 2.0 trades are then checked with the learned stop's history lowered to 5 winners on both sides (a code test,
not a setting; the checker also asserts every trade had that many earlier winners):

| Slice | Signals from | Cell | Signals | Trades checked |
|---|---|---|---|---|
| B2 (history 5) | 2026-02-15 | s 2.0, n 3, T2, p90 | 95 / 95 | 64, 0 mismatches |
| A2 (history 5) 2025-10-18 .. 2026-02-15 | 2025-11-01 | s 2.0, adaptive, T1, p80 | 71 / 71 | 25, 0 mismatches |

In all: six runs, 605 signal checks (510 distinct signals; B2 checked twice) and 134 trades, every one the same. With the tests (126, planted bugs caught) the code is
proven; the walk-forward run on the latest 12 months is next.

## LV3 walk-forward on the latest 12 months - the first result (2026-10-18 23:00 Thai; `out_wf.txt`, `lvl3_wf_months.csv`, `lvl3_wf_weeks.csv`, `out_wf_losers.txt`, `png/lvl_losers/lvl3_wf_trades/`)

- No trade before 2026-02: the walk-forward needs 20 closed trades of a cell and the learned stop 30 earlier
  winners, both only from 2025-10-18 on.
- **Learning half (2025-10-18 .. 2026-04-17):** 66 trades (0.51 a weekday), win 18.2 %, **+0.013 R**, +11.2 USD at
  0.01 lot, max drawdown 80.9 USD, worst trade -21.30, longest losing streak 8.
- **The exam (2026-04-18 .. 10-16):** 95 trades (0.73 a weekday), win 21.1 %, **-0.139 R**, **-198.3 USD**, max
  drawdown 194.3 USD, worst trade -26.68, longest losing streak 7. Cross-checks: weekly running total -187.18 =
  +11.2 - 198.3; February's 21 trades / +42.8 USD equal in the month and week tables.
- **The library evidence at entry does not separate** (R13): exam R by the evidence word - supports -0.171 (30),
  mixed -0.180 (22), none -0.146 (24), against -0.036 (19); the learning half the same picture (supports -0.179).
- **The losers (119 of 161):** a close of the entry TF through the level 67 (+10 where the target came anyway), break-
  even after 0.6 of the target 23, the level broke and the stop followed 11, a time exit at a loss 6, shaken out 2.
  Buys lose in both halves (learning -0.131 R over 35, exam -0.260 over 22); sells +0.176 (31) then -0.103 (73).
  Windows: Thai 07:00 -0.416 R (13), London 08-12 -0.143 (60), Thai 09-12 -0.113 (30), New York 11-14 +0.053 (34).
  At entry the losers and winners measure alike (bounce 2.3 vs 2.1 A, entry 0.44 vs 0.54 A from the level).
- Gold by month (close - open): 2025-10 +140, 11 +228, 12 +93, 2026-01 +552, 02 +461, 03 -671, 04 -71, 05 -86,
  06 -533, 07 +39, 08 +374, 09 -291, 10 +10: the exam is a falling, swinging market after a five-month rally.
- Two of the worst, by eye: 2026-06-11 07:03 sell (H1 had fallen 300 USD in two days; the M5 bounce from the low
  paused under the level and then ran through it, 36 USD stop -> -26.68 at the close exit); 2026-05-18 16:41 sell
  (H1 fell 150 then based for two days; on M5 the "bounce" was a nine-hour rise of 75 USD with higher lows - a turn,
  not a pullback; it retested the breakdown level and went through, -20.70).

## Which levels hold and which break - written before it is computed (2026-10-18 23:45 Thai; `hold_break.py`)

Found in the exam's losers: the close-through exit is not the fault (holding those 50 trades: 32 to the full stop,
3 to the target; without the exit the exam is -0.173 R, not -0.139) - the level breaks in about half the trades and
price goes on. So: what could the bot see at the signal that tells a holding level from a breaking one?

- **Data:** every LV3 signal before the exam (2023-08-15 .. 2026-04-17; the 3-year signal tables of `wf.py 3y`), cell
  s 1.5 / n 3 (the most signals) and, as a check, s 2.0 / adaptive. The exam is not looked at.
- **Label** (no stop, from the entry): *held* = back to the bounce's start first; *broke* = an entry-TF close beyond
  the level first; *neither* within 12 entry-TF bars.
- **Hypotheses:**
  - H-a (the owner's 2026-09-02 reading: "the broken 4316 low"): a level price had crossed before the bounce
    (support broken, now resistance; mirrored for buys) holds more often than one price never crossed.
  - H-b: a bounce that climbs like a staircase on the entry TF (most bars with a higher low, for a sell) is a turn,
    not a pullback, and breaks the level more often.
  - H-c: a sell after the H1 has already fallen more than 3 H1 ATRs in 24 hours (mirrored) breaks more often.
  - Also shown: the session window, the side, the level's swings.
- **Decision rule:** the feature with the largest (held - broke) difference that has the same sign and at least 10
  points in both design halves (2023-08 .. 2024-12 and 2025-01 .. 2026-04-17) becomes a filter; the walk-forward is
  rerun once on the latest 12 months and reported week by week. If none qualifies, say so.

**Result (`out_hold_break.txt`, `hold_break.parquet`; 2,448 signals before the exam):** a level broke first in 62-65 %
of the signals and held in 20-21 %, in every part and cell. None of H-a / H-b / H-c moves it by 10 points in both
halves (H-a: 98 % of the levels had been crossed before - the test does not split them; H-c goes the other way: a
larger H1 move before the signal breaks a little less). **The levels do not turn price:** a driftless walk from the
entry, with the level 0.43-0.51 A away and the bounce's start 2.0-2.4 A away, reaches the start first 17.3-20.4 %
of the time; the levels hold 19.7-21.0 %. LV3 rests on its levels turning price; the swing-cluster levels it picks
(there is always one near) behave almost like lines drawn anywhere. No filter is added (none qualifies); the next
question is which kinds of level do turn price.

## Which kinds of level turn price - written before it is computed (2026-10-18 night, Thai time; `level_power.py`)

Every first touch (none in the 60 minutes before) of a level inside the owner's windows, 2023-09 .. 2026-04-17 (the
exam not looked at): afterwards, does price come back 1 M15 ATR from the level first (it turned price) or go 1 ATR
through it? A line with no effect gives 50 %. Kinds: yesterday's high / low, today's high / low so far, the Asian
session's high / low, the 72-hour high / low (ending an hour before), round 50s, H1 and M15 fractal swings of the last
120 bars, and the control: a grid of 50s shifted by 13 USD. **A kind turns price** when it is above 50 % by at least
two standard errors in both parts (2023-09 .. 2024-12, 2025-01 .. 2026-04-17); those kinds become LV3's levels, tested
by the walk-forward once.

## Each component of LV3 alone - written before it is computed (2026-10-18 night, Thai time; owner: "focus on the basic correctness of each component before assembling them into a setup or parameters"; `components.py`)

`lvl2.setup_at` was split into `bounce_at` (entry TF, the larger timeframes' trend, the bounce's start, a bounce of
>= 1 A) and the level step; the split gives the same setup at all 25,023 window minutes of 2026-02-01 .. 03-14, and
the tests pass. Found on the way: every bounce there had a level in front (3,177 of 3,177) - the level step never
says no.

The question per component: at the decision (an M1 close), does price go 1 A (the entry TF's ATR) the component's
way before 1 A the other way, within 120 minutes? From the close, a component with no effect gives 50 %. Data: the
owner's windows, 2023-09 .. 2026-04-17 (two parts, split at 2025-01-01), every 15th minute (less overlap); the LV3
signals (3-year table, s 1.5 / n 3) all.
- **A** every larger timeframe's trend agrees (LV3's own: the timeframes above the entry TF up to H4) -> its way;
- **A-H** H1 and H4 agree -> their way;
- **B** A + the bounce from the start (>= 1 A against the trend) -> the trend's way (the pullback resumes);
- **D** the LV3 signal (B + the level + the M1 legs) -> its way.
A component carries information when it is off 50 % by at least two standard errors in both parts.

**Result (`out_level_power.txt`, `level_power.parquet`; two look-ahead slips fixed before reading it - the Asian
range was visible to the 22:00-23:59 UTC bars of the next server day, and swings / ATR could include the touching
bar; and the first reading compared with 50 % although the touch bar's close often sat beyond the level: each touch
now has its own no-effect baseline):** no kind of level turns price. Turned minus no-effect, first part / second:
yesterday's high / low -0.9 / -2.3 points, the 72-hour high / low -2.1 / -1.5, round 50s -1.2 / -2.4, the Asian range
-1.3 / +0.9, today's high / low so far +0.6 / -1.5 (-3.2 SE, the other sign the first part), H1 swings -0.1 / -0.5,
M15 swings -0.8 / +0.5; the control grid +3.9 / +2.4 (1.5 SE: the noise). At 1 M15 ATR, gold touching any of these
levels turns or goes through as a line drawn anywhere would - neither fading levels (LV) nor trading their breaks
has a premise here.

**Result (`out_components.txt`): no component of LV3 carries direction.** 1 A first, the component's way vs the other
(no effect 50 %), first part / second: every larger timeframe's trend agreeing 50.3 / 50.1 % (8,555 / 8,075 grid
minutes); H1 and H4 agreeing 50.3 / 50.0 %; the trend + a bounce of >= 1 A (the pullback to resume) 49.7 / 50.8 %;
the LV3 signal 47.3 / 49.5 % (634 / 606). With the levels (no kind turns price) every part LV3 is built from measures
at chance at this scale - which is why it loses its costs whatever its parameters. The one piece measured above
chance today is the library's lean at the snap times (the setup layer called the side of the next run 57.4 % / 54.8 %
in the learning half / the exam, walk-forward; too weak to pay a bracket's costs alone).

**Learning log, round 14:** learned - the walk-forward of LV3 lost in the exam (-0.139 R, -198 USD); not the code
(proven), not the costs (0.04 R), not the close exit (holding is worse), not a stable "wrong side" (the opposite side
wins the exam, loses the learning half); every component measures at chance (trend, pullback, level, the signal);
the library's "same picture" is too coarse (pictures, `png/wf_library/`). Changed - the method: each component is
proven twice (code, and its premise against a no-effect baseline in two parts) before it is assembled (owner).
Result - LV3 stops as a setup; the components to test next are the ones with a measured or causal lead.

## F1 CONF-72's components alone - written before it is computed (2026-10-18 night, Thai time; `f1_components.py`)

F1 CONF-72 trades on DEMO; its parts are checked the same way (owner: "do it"). Data: the research's wide candidate
tables (every minute of UTC 00-02, 07-12, 12-17 x both sides, 2023-11 .. 2026-04-17; the bot's definitions - engine
= research 35 / 35). Per component (tide, at a level, price action, 2 of 3 M5 indicators, C4 the 72-hour extreme
near / behind, C5 not a fast tape) and per assembly (tide + level, + price action, B0, CONF-72): does price go 8 U
the side's way before 8 U the other way within 60 minutes of the decision close (no effect 50 %)? One row per 15
minutes per side. A component carries information when it is off 50 % by >= 2 standard errors in both parts
(2023-11 .. 2024-12, 2025-01 .. 2026-04-17).

**Result (`out_f1_components.txt`): one of F1's parts carries direction - C4.** 8 U the side's way first, first part
/ second (no effect 50 %): tide 51.4 / 50.6 % (2.1 / 1.1 SE); at a level 48.8 / 49.8; price action 49.7 / 49.9; two
of three M5 indicators 49.0 / 50.8; **C4, the 72-hour extreme near (closer than half the target) or already behind,
53.6 / 53.8 % (2.3 / 2.8 SE)**; C5 50.0 / 50.0; tide + level 50.5 / 50.1; + price action 49.7 / 50.0; B0 50.5 / 50.4;
**CONF-72 62.1 / 65.0 % (66 / 80 events, 2.0 / 2.8 SE)**. F1's measured edge comes from C4 - price at or beyond the
72-hour extreme the trade's way tends to go on - not from the tide, the level, the price action or the indicators.

## C4 taken apart - written before it is computed (2026-10-18 night, Thai time)

Same measurement (8 U, 60 minutes, one row per 15 minutes per side, two parts). C4-behind (price already beyond the
72-hour extreme the trade's way) and C4-near (not beyond, closer than 4 U); then C4 with each other component added
(tide, level, price action, indicators, C5) to see which adds to C4. A piece adds when C4 + it is above C4 alone by
>= 2 standard errors of the difference in both parts.

**Result (`out_f1_c4.txt`):** C4-near 53.7 / 55.0 % (2.2 / 3.3 SE), C4-behind 52.7 / 51.0 % (1.3 / 0.5); C4 + tide =
C4 (the tide is nearly always on with C4); C4 + level 59.2 / 57.0 % (4.0 / 3.3 SE; the difference from C4 is +5.6 /
+3.2 points, 2.0 / 1.3 SE - not proven to add by the rule); C4 + price action 52.8 / 53.4; C4 + indicators 55.4 /
55.3 (312 / 369); C4 + C5 53.7 / 54.6. Caveat: C4 was chosen by the portfolio agent on 2023-11 .. 2026-02, the same
years - not a clean test.

## C4 on the older years - written before it is computed (2026-10-18 night, Thai time; `c4_old.py`)

Gold 2020-09 .. 2023-10, never used to choose C4: every 15th minute of F1's windows, both sides; C4-near, C4-behind,
both, and the control (neither); 8 U the side's way first within 60 minutes (no effect 50 %); two parts
(2020-09 .. 2022-03, 2022-04 .. 2023-10). C4 is proven when C4-near is above 50 % by >= 2 SE in both parts.

**Result (`out_c4_old.txt`): on the years that chose nothing, C4 goes the other way.** 2020-09 .. 2022-03 /
2022-04 .. 2023-10: C4-near 39.5 / 47.3 % (-2.8 / -1.3 SE), C4-behind 42.5 / 46.7, C4 either 40.9 / 47.1 (-3.3 /
-1.8); the control (neither) 50.4 / 50.2 % - the measurement is not biased. In the trending gold of 2023-11 ..
2026-04 price near the 72-hour extreme went on (54-55 %); in the ranging gold of 2020-09 .. 2023-10 it turned back
(40-47 %). C4 is real but its sign belongs to the market phase: F1 CONF-72's edge is the trending phase's. Next: a
phase component, measured in advance, that tells C4's continuation from its reversal in both eras (owner's principle:
in a phase that does not suit a setup it trades less).

## A phase component for C4 - written before it is computed (2026-10-18 night, Thai time; `c4_phase.py`)

Candidates, from daily bars on the server day, known at the previous day's close: the 20-day efficiency ratio
(|net move| / the path; trending near 1), the daily ADX(14) (MT5's), and the distance from the 50-day average in
20-day ATRs. For every C4 event (near or behind; every 15th minute of F1's windows, both sides) in each era -
2020-09 .. 2023-10 and 2023-11 .. 2026-04-17 - its way (8 U first, 60 minutes) by the measure's terciles within the
era. **A phase measure is proven** when the top tercile minus the bottom is positive by >= 2 SE in both eras (a
trending phase: C4 goes on; a ranging one: C4 turns).

**Result (`out_c4_phase.txt`): no phase measure is proven.** Top tercile minus bottom, 2020-09 .. 2023-10 / 2023-11 ..
2026-04-17: the 20-day efficiency ratio -1.5 / +3.5 points (-0.4 / +1.2 SE); the daily ADX -8.4 / +3.8 (-2.4 / +1.3 SE;
in the old era a high ADX went with more reversal); the distance from the 50-day average -2.4 / +5.1 (-0.7 / +1.7 SE).
C4's sign is a property of the era (gold's multi-year rally vs its 2020-23 range), not of these day-level measures.

**Learning log, round 15:** learned - F1 CONF-72's only informative part is C4, and C4's sign flips with the era; no
daily phase measure tells which in advance. Changed - nothing in the bot (the owner decides on F1's DEMO run). Result -
the chart components tested so far (trend, pullback, levels, price action, indicators, the 72-hour extreme) give no
direction that holds across gold's eras; the leads left are causal (the releases), the library (with a truer
"same picture"), and the time of day (when runs happen, not their side).

## Setup OWN V2 as agreed - written before it is computed (2026-10-18 night, Thai time; `v2b.py`, tests `test_v2b.py`)

The owner (2026-10-19): "do what we agreed at first - research the patterns before price runs 5-10 USD (done), then
let the bot catch a chart whose outline matches a researched pattern and decide whether to trade"; "if it sees it
all there should be a chance: at support / resistance, with the larger timeframes' way trade the trend, near a big
support / resistance price may turn" (the library's codes hold the larger timeframes' trend and the S/R location);
"the bot read pictures that do not look alike as alike - that must have added a lot to the losses".

- **When:** the owner's snap times (20 a day), 2025-10-18 .. 2026-10-16 (the library's span).
- **Match:** per layer (H4 + H1, M30 + M15, M5 + M1) the walk-forward library (`OutlineLibrary`: earlier days only,
  a pattern counted once a day): >= 80 % of the core attributes equal, and with the outline gate every timeframe's
  120-bar close path correlating >= 0.6 or >= 0.8 with the pattern's first moment (off = codes only).
- **Decide:** each chosen layer (setup; trigger; setup + trigger; all three) needs >= N earlier days (3 / 5); the
  summed lean (up share - down share of those days) >= THETA (0.2 / 0.4) trades that way, else no trade.
- **Trade:** the next M1 open; the entry timeframe the smallest of M1 / M5 / M15 / M30 whose ATR covers 5 USD (M30 if
  none); stop one entry-TF ATR (>= 5 USD); target 10 U; out after 12 entry-TF bars; one position; the auditor's
  costs.
- **Learning:** 48 cells, the walk-forward chooses each month the best mean R of the previous six months' closed
  trades (>= 20); reported week by week; the exam 2026-04-18 .. 10-16 once.
- Bug found by the new tests (fixed in `pattern_library.py` and `v2b.py`, test added): float32 storage put an exact
  80 % at 0.79999999 - never reached in the real layers (16 / 18 attributes cannot give 80 % exactly), so no result
  changes.

**Two bugs found before reading V2 (fixed, tests added, the tests catch the old code):** (1) float32 storage put an
exact 80 % at 0.79999999 (`pattern_library.py`, `v2b.py`; never reached in the real layers); (2) **ties went to float
noise**: equal similarities (k / n) came out 2e-16 apart, so the library's argmax picked the pattern by rounding,
not the earliest - found by the independent check (`check_v2b.py`: 47 of 347 trades differed, all from the
assignment drifting over the months); similarities are now rounded before the choice (`pattern_library.py` too). The
first V2 run (learning +0.023 R, exam -0.225) is void.

**Result (`out_v2b.txt`, `out_check_v2b.txt`; proven: 8 tests, 10 planted bugs caught, the independent re-derivation
equal on all 408 trades):** learning half 221 trades (1.70 a weekday), win 37.1 %, **-0.021 R**, +14.1 USD, max DD
120.2; **the exam 187 trades (1.44 a weekday), win 31.6 %, -0.169 R, -241.2 USD**, max DD 320.2, worst -14.16 USD,
13 losses in a row. The outline gate on the learning half (cells, mean R): codes only -0.103 (16 cells, 4,051 trades),
outline >= 0.6 -0.254 (14, 723), >= 0.8 -0.534 (9, 92) - not better there (fewer earlier days per pattern in a
library six months old). The walk-forward moved to an outline cell (set + trigger, >= 0.6) from July: August +0.292
R (20), September +0.751 (7), October -1.0 (2); April - June with codes-only cells lost (June -169 USD over 98).
Pictures of eight decisions (entry / TP / SL drawn): `png/v2b_decisions/` - e.g. 2026-06-13 01:00: codes 15 of 18
equal but the outlines ran opposite (M30 -0.28, M15 -0.17): sold, stopped; pattern #319 (a steep rally faded) won
on 2026-01-29 and lost on 2026-06-15 with 15 earlier days 0 % up / 67 % down.

## "The same picture" redefined - written before it is computed (2026-10-19 night; owner: "that is the problem")

The owner on four V2 decision pictures: are they really alike? Mine, honestly: two not at all (opposite or unrelated
outlines), two only in part (the direction alike, the size not: a vertical 12 % blow-off matched a calm 3 % climb, the
normalised path removes the scale). The owner: "that is the problem". A layer's two pictures are now the same only
when, for every timeframe of the layer, all hold (thresholds set here, not tuned):
- **structure:** the core codes >= 80 % equal (as before);
- **outline:** the 120-bar close path correlates >= 0.7;
- **size:** the 120-bar range in that timeframe's ATRs within a factor 1.4;
- **the last leg:** the same way (from the last confirmed ZigZag swing to the close), its length in ATRs within a
  factor 1.6;
- **position:** the close's place in the 120-bar range within 0.2, and at a new 120-bar high (>= 0.95) or low
  (<= 0.05) on both or neither.
Order: the code with tests; pairs drawn for the owner's eye (the new rule's matches, and old matches it rejects);
only after the owner's yes, the lean's accuracy on the learning half; only then trading.
- **the trend's way (owner, the same night: "some pictures are almost alike but one goes up and one goes down - they
  must not be the same"):** on every timeframe both the net way of the 120 bars (up / down / flat within 1 ATR) and
  the swing structure (the last two ZigZag peaks and troughs: higher-higher = up, lower-lower = down, else mixed)
  must be equal.

**Built and tested (`picture.py`, `test_picture.py`: 9 tests; 12 planted bugs caught; the vectorised library equals the
one-by-one one on a mixed random sequence):** the snaps' pictures (`snap_pictures.parquet`) and the walk-forward
library under the new rule (`picture_pairs.py`, `out_picture_pairs.txt`). Snaps that find a pattern of earlier days,
the old rule (codes) -> the new rule (the same picture), of 5,115: context 2,966 -> 491, setup 3,659 -> 334, trigger
4,275 -> 211; patterns 736 -> 1,788, 1,131 -> 3,936, 820 -> 4,900. **The same picture rarely comes back within a
year**; the old rule's many "repeats" were different pictures counted together. Pairs for the owner's eye:
`png/same_picture/` (eight called the same, four the old rule matched and the new one rejects, the learning half
only). My own look: the setup and trigger pairs look alike (e.g. 2026-04-15 14:00 vs 01-13 09:00: both rising
HH/HL, a pullback from the top, sizes 17 / 19 ATR); the rejections are right (an up-trend vs a down-and-sideways
chart); but some context pairs are the same situation a few hours apart (2026-01-31 00:00 vs 01-30 17:00, H4
correlation 1.00) - one market moment counted twice, not a repeat.
- **after the owner's eye on the first pairs (2026-10-19):** picture 2 (the trigger pair 2026-02-02 16:00 / 01-14
  08:00) - on M5 one close still under its last top (the down-structure intact), the other already above its last
  top (broken): the close against the last confirmed top and bottom (above / between / below) must now be equal, and
  the swing still forming counts in the structure (a run above the last top is a higher top at once); picture 4 was
  one the new rule had already rejected - the owner's eye and the rule agree. My own look added the path's
  character: the deepest move against the window's way within a factor 1.6 (both under 1 ATR alike) and the
  smoothness (|net| / path) within 0.1 (a steady staircase is not a fall-and-recover).
- **the owner (2026-10-19): "if price runs significantly, add it to the library as a new entry"** - the picture just
  before every 10 U run (the run catalogue, inside the owner's windows) joins the library with the run's way, after
  the run is over (evidence for later days only).
- **the thirds (owner, 2026-10-19, on three more pairs: alike at the end, not at the start):** the 120 bars are cut
  in three; each third must go the same way (up / down / flat within 1 ATR) and its outline correlate >= 0.5 - a
  steady staircase is not a flat range that breaks out late, a slide is not a spike-and-crash. A repeat within 7
  days is the same episode (counted once). Tests 14, planted bugs caught 25 of 25 (one equivalent earlier).

## Does the bot read the chart right, and will it find the same picture? (2026-10-19, 00:30-01:45 Thai)

The owner: "look at the pictures - are they alike? If the bot uses this for real, will it catch patterns? Focus on
whether the bot interprets the trading screen correctly", then on the reading audit's first limit ("ZigZag 3 ATR is
sometimes too coarse"): "can't you look at a smaller timeframe to see how it shows the swings? M5 should show them".

**The reading audit (`reading_audit.py`, `png/reading_audit/`, eight learning-half snaps, every timeframe drawn with
what the bot measured):** the readings match their definitions and mostly what a trader sees; the limits - the
structure is the last two swings (the latest part of the window), and a 3-ATR ZigZag finds too few swings in a
smooth one-way move (structure unreadable on 1.5-3.9 % of the moments per timeframe, the break test on 0.0-1.1 %).

**The zoom (`moments.small_span`, `moments.zoom_all`, `picture.zoom`):** a structure or break reading of 9 (too few
swings / no top or bottom yet) is read from the next smaller timeframe's swings over the same span (H4 <- H1 <- M30
<- M15 <- M5 <- M1; M1 from its own bars with a 1.5-ATR ZigZag), against the larger bar's close. The span: from the
first smaller bar completing after the bar before the window completed to the last one completing with the window's
last bar (the same last M1 bar - the same close; asserted on every moment). Tests (`test_moments.py`, by hand): the
span with a weekend gap and a bar missing its last minute; a hand-made swing set read as HH/HL and "above the last
top" (a peak confirmed one bar after the span and a later bar's close must not count); untouched rows; only the
missing reading filled; still 9 when the smaller timeframe has too few swings too. Planted bugs caught 7 of 7 (span
start / end off by one, a span one larger bar short, the smaller timeframe's latest close, span ends swapped, a wrong
change flag, the first-bar window). The library rebuilt (29,073 moments): "too few swings" 1.5-3.9 % -> 0 % on every
timeframe, the break test's 0.0-1.1 % -> 0 %; nothing else changed (every other column and the outlines equal the
old file; only readings of 9 replaced). By eye (`zoom_audit.py`, `png/zoom_audit/`, eight cases, the stored reading
asserted equal to the panels'): the smaller timeframe shows what a trader sees there - H4 2025-09-05 a smooth climb
-> H1 HH/HL; M30 2025-02-03 a new top then below the last trough -> mixed; M5 2024-01-16 a fall and a lower
drift -> LH/LL. One scale effect to tell the owner: the smaller timeframe's last two swings are the latest part of
the window - M5 2025-12-16 23:00 is a big climb, but M1's last swings are the pullback from the top -> "down".

**Will the bot find the same picture? (`coverage_3y.py`, the walk-forward library of three years, other episodes
only - >= 7 days before):** context (H4+H1) - 17 of 12,602 learning snaps find the same picture once, none twice or
more; the exam 3 of 2,598 (before the zoom: the same 17 / 3). Setup (M30+M15) - 16 of 12,602 and 6 of 2,598, none
twice. **The same picture, every part on both timeframes of a layer, almost never comes back - the bot could not
trade on it.**

**What makes it rare (`rarity.py`, tests `test_rarity.py` - the parts together equal `picture.same_mask` on random
pictures and each part equals the scalar rule's reason; tables by hand; planted bugs 9 of 9):** 800 snaps
(2024-05 .. 2026-04-17) against every earlier moment of another episode (an upper bound: any moment, not only the
library's patterns): every part - context 0.1 %, setup 0.0 %, trigger 0.1 % of snaps have one. No single part is to
blame - without any one part at most 1.6 %. The parts added one by one (the least selective first): smoothness,
pullback, the break, size, the 120 bars' way, position leave 82-95 % of snaps with matches (median 14-25); + the
structure 55-78 % (median 2-6); + the last leg 34-57 % (median 0-1); + the outline, the codes, the thirds ~0. One
timeframe's full picture alone: 21-35 % have one, median 0.

**Which level of sameness tells the way? (`rarity_lean.py`, tests `test_rarity_lean.py` by hand, planted bugs 4 of 4;
3,000 learning snaps 2024-05 .. 2026-04-17 and all 2,598 exam snaps):** at each level, the matching earlier days
(one per day), their lean (up - down share), and with >= 5 days and |lean| >= 0.2 how often a 10 U run followed
within 30 minutes the lean's way vs the other way, minus what the half's rates give with no effect (edge):
- context: the coarse levels ~0; + the structure +0.067 (se 0.043) learning, +0.076 (0.042) exam - weak;
- setup: signs flip between the halves - nothing;
- **trigger (M5+M1): the coarse situation leans right in both halves** - smoothness + pullback + the break:
  +0.179 (0.032) learning, +0.119 (0.026) exam (the lean's way 33 % vs the other 15 % / 22 %); + the way, size,
  position: +0.105 (0.026) / +0.085 (0.026); finer levels fewer snaps and noisier;
- the full picture: too few snaps to say.
**Checked (`lean_check.py`, `out_lean_check.txt`):** an independent recount from the rule's text (plain pandas, no
picture.py / rarity.py) equals the per-snap days and lean for 300 of 300 snaps at both levels in both halves; with
each day's snaps counted as one the error barely grows (0.032 -> 0.034, 0.026 -> 0.029); placebos - the same lean
against what followed the same snap time on the trading day before / after: -0.054 .. +0.023 (nothing): the
information is the moment's own, not a trend of several days. Not yet a trade: a run following is not a stop and
target, and this is the same situation, not the same picture to the eye.

## V2 on the trigger situation - written before it is computed (2026-10-19 01:45 Thai; `v2s.py`, tests `test_v2s.py`)

At every snap: the earlier moments (>= 7 days before; snaps and the starts of 10 U runs) in the same M5 + M1
situation, one per day, their lean; trade it with >= N_MIN days and |lean| >= THETA. Fixed before the run from the
learning half: L3 = smoothness + pullback + the break; L6 = L3 + the 120 bars' way, size, position. The trade as
v2b (entry at the next M1 open within 5 minutes, entry TF by ATR, stop one entry-TF ATR >= 5 USD, target 10 U,
12 entry-TF bars, the auditor's costs, one position at a time); cells L3 / L6 x N_MIN 5 / 10 x THETA 0.2 / 0.4,
chosen walk-forward month by month from 2024-05 (lookback 6 months, >= 20 closed trades). Tests: the side by hand;
the leans from a five-moment library by hand (two timeframes, the 7-day window, L3 vs L6); planted bugs 7 of 7
(any earlier day, L6 without the way, L3 without the break, strict threshold, strict days, one timeframe only x2).
The run asserts its leans equal rarity_lean's where both measured. Then `check_v2s.py` re-derives every
walk-forward trade independently (the lean recounted from the rule's text, own ATR bars, own bar walk). The exam
(2026-04-18 .. 2026-10-16) is read week by week.

**The result (2026-10-19 ~01:50 Thai; `out_v2s.txt`, `v2s_wf_trades.parquet`, `v2s_wf_months.csv`,
`v2s_wf_exam_weeks.csv`):** every cell negative on the exam (R -0.016 .. -0.098), the learning half -0.140 ..
+0.006. Walk-forward: learning 445 trades (0.87 a weekday), win 0.380, **R -0.020**, -39 USD; **the exam 278 trades
(2.14 a weekday), win 0.331, R -0.085, -240 USD**, max DD 298, worst -13.21, longest losing streak 9 (May-June mostly
up, late August - early September the deepest: -77, -51, -42 USD weeks). **Independent check (`check_v2s.py`): 723
of 723 trades equal** (the lean recounted from the rule's text, own ATR bars, own bar walk; no trade opens before the
one before it closed). Why a right lean still lost - the trades by what followed:

| after the entry | learning | the exam |
|---|---|---|
| a 10 U run the lean's way | 149 trades, R +0.177, stopped 49 % | 104, R +0.039, stopped 56 % |
| a 10 U run the other way | 68, R -0.406 | 64, R -0.501 |
| no 10 U run | 228, R -0.033 | 110, R +0.039 |

When the lean was right the run started a median 6 (learning) / 9 (exam) minutes after the snap from a dip against
the trade of a median 5.1 / 6.2 USD (75 %: 11.1 / 11.7 USD); the stop (median 6.5 / 6.9 USD) went first in 52 % /
59 % of them. The lean tells the way of the next half hour, not the entry.

## V2's entry - waiting for the dip (2026-10-19 ~02:00 Thai; `v2e.py`, tests `test_v2e.py`) - the learning half only

Two entries that wait for the dip, with v2s's leans, cells and walk-forward, chosen on the learning half only (the
exam not run): a limit D = 3 / 5 USD beyond the snap's price the lean's way, valid 30 minutes, the stop S = 5 / 8 USD
from the fill (a fill bar's stop counts, its target not); or the turn - the first M1 close beyond the extreme bar's
other end after the dip, the stop 0.3 USD beyond the extreme, capped at 5 / 8 USD; the target 10 U, out after 15 /
30 minutes. Tests by hand (fills with the spread and on gaps, the window's end, the turn for both sides, an outside
bar is a new extreme, a wide spread moves a sell's extreme, a limit trade whose fill bar touched the target);
planted bugs 11 of 11 caught. **Every variant lost on the learning half:** limit R -0.025 .. -0.141, turn -0.160 ..
-0.210 (the snap entry: -0.020). The turn's stops (median 2.9 USD) go in M1 noise (57 % stopped); the limits fill
more often when the price keeps going against the lean; time exits are positive on average (+0.4 .. +1.9 USD) - the
price leans the right way but 10 U in half an hour is too far for most of them.

**The round's conclusion (to be concluded with the owner):** the bot reads the chart as defined (audit + zoom); the
same picture by eye does not come back (0.0-0.1 % of snaps), so a library of the same picture cannot trade; the
same situation on M5 + M1 does come back and leans the right way for the next half hour (checked four ways), but
neither the snap entry nor the dip entries turn it into a positive R - the lean's edge (run the right way 33 % vs the
other 15-22 %) is smaller than what the 10 U target, the stop and the costs need.

**The coverage, every layer (`out_coverage_3y.txt`, the zoomed library):** trigger (M5+M1) - 9 of 12,602 learning
snaps and 1 of 2,598 exam snaps find the same picture once, none twice; 27,874 of the 29,073 moments are patterns of
their own.

**The lean's drift (`out_lean_drift.txt`; an upper bound for any exit that holds a fixed time):** the mean move the
lean's way from the snap's entry, held 5 / 15 / 30 / 60 minutes - learning -0.03 .. -0.32 USD, the exam +0.18 ..
+0.74; after the costs (~0.45 USD a trade) negative everywhere but one cell (the exam, L3, 5 minutes +0.27, se by day
0.25; the learning half there -0.49). With the evidence from snaps only (no run starts - successes picked after the
fact; `out_lean_snaps_only.txt`) the run edge stays (L3 +0.125 / +0.314, L6 +0.047 / +0.076) and the drift after
costs is negative at every holding time in both halves. **The situation tells the way of the next big move, not the
average move:** when no run comes, price drifts the other way about as much.

**The stop entry (2026-10-19 ~02:10 Thai; `v2e.py` stop variants; tests: fills on the ask / bid, gaps at the open,
the slip, the window's end, a stop trade by hand, its fill bar's stop first; planted bugs 8 of 8):** a stop order D =
1 / 3 USD beyond the snap's price the lean's way (it fills only once price moves that way), the stop S = 3 / 5 USD,
the target 5 / 10 U, out after 15 / 30 minutes - **every one of the 16 negative on the learning half** (-0.037 ..
-0.358 R; the S = 3 ones the worst, M1 noise). All 28 entry variants and the snap entry lose on the learning half;
the exam was not run for any of them. **V2's levers on the entry and the exit are spent** - to be concluded with the
owner.

## The library learns the trade's result - written before it is computed (2026-10-19 02:30 Thai; owner: "the library learns the real trade result")

The owner chose (2026-10-19, about 02:30 Thai): every library moment keeps the real result of V2's trade - the R of a buy
and of a sell from it - instead of "did it run", and the bot trades only where the same situation's earlier results
were positive.
- **The labels (`trade_labels.py`):** for every snap, a buy and a sell with V2's trade (v2s: entry at the next M1 open
  within 5 minutes, the entry TF the smallest of M1 / M5 / M15 / M30 whose ATR covers 5 USD, the stop one entry-TF ATR
  >= 5 USD, the target 10 U, out after 12 entry-TF bars, the auditor's costs): R_buy, R_sell. Known when the trade
  closes (at most 6 hours), long before the evidence's 7 days.
- **Evidence from snaps only:** the starts of 10 U runs are successes picked after the fact - a buy from a run-up's
  start wins by definition, and the look-alikes that did not run are not in the library - so they would make every
  situation look better than it is; the snaps are the bot's own decision moments, all outcomes kept.
- **The evidence at a decision:** the earlier snaps (>= 7 days before) in the same situation, one per day (the day's
  first), their mean R_buy and mean R_sell; trade the better side when >= N_MIN days and its mean R >= THETA.
- **The situations (fixed now):** each layer (context H4+H1, setup M30+M15, trigger M5+M1) at L3 (smoothness, the
  deepest pullback, the close against the last top / bottom), L6 (+ the 120 bars' way, size, position) and L7 (+ the
  swing structure); N_MIN 5 / 10; THETA 0.0 / 0.1 / 0.2.
- **The premise first (`r_lean.py`), both halves (learning 2024-05 .. 2026-04-17, the exam 2026-04-18 .. 10-16),
  before any trade backtest:** at the snaps where the evidence picks a side, the realized R of that side, minus the
  no-effect baseline (the mean of R_buy and R_sell at the same snaps - a coin's side), with the error by day; and
  the placebo (the same evidence against the next trading day's same-time snap). A premise holds only when the edge
  is positive beyond its error in both halves; then the walk-forward trades (one position at a time, the cell chosen
  month by month), the exam week by week.

**The premise's result (`out_r_lean.txt`, `r_lean_premise.csv`; every layer's evidence recounted independently for
300 snaps, all equal; tests `test_r_lean.py` by hand, planted bugs 9 of 9):** the trade of every snap loses about
-0.08 R on a coin's side in both halves (learning: buy -0.037, sell -0.114; the exam: buy -0.128, sell -0.030;
`out_trade_labels.txt`). The library's pick beats the coin most at the trigger layer, L6: e.g. N_MIN 5, THETA 0.2 -
edge +0.059 (se by day 0.022) learning, +0.083 (0.046) the exam - but **the R actually earned is -0.002 / +0.014**,
and in the exam the placebo (the same pick against the next day's snap) is +0.070, as large as the edge: part of it
is a trend of several days, not the moment. No cell earns a clearly positive R in both halves; ctx and set:
nothing stable. The premise does not hold for a setup (the goal is >= +0.15 R).

## Why V2s's losers lost - the owner's three kinds (2026-10-19 ~02:50 Thai; `v2_loser_kinds.py`, test by hand)

Every walk-forward trade stopped before its target, against a coin's side (the opposite trade from the same snap,
the same stop and target; `out_v2_loser_kinds.txt`):

| the exam (278 trades) | V2s | a coin's side |
|---|---|---|
| 1 wrong way | 85 (31 %), -644 USD, median 0.16 of the target first | 103 (37 %) |
| 2 right way, fell short | 31 (11 %), -236 USD, median 0.63 of the target first | 28 (10 %) |
| 3 right way, entered too early | 49 (18 %), -336 USD; a stop of a median 11.5 USD would have survived | 37 (13 %) |
| a time exit at a loss | 12, -33 USD | 4 |
| won / a time exit in profit | 101 (36 %), +1,008 USD | 106 (38 %) |

V2s picks the wrong way less often than a coin (85 vs 103; learning 143 vs 154) but enters too early more often;
the exam -240 USD vs the coin's -142 (learning -39 vs -323).

**Each kind attacked (the learning half only; `out_v2s_*.txt`, `out_v2e_learning.txt`):**
- kind 3 (too early): a dip limit (8 variants) -0.025 .. -0.141 R; an M1 turn (4) -0.160 .. -0.210; a stop order
  the lean's way (16) -0.037 .. -0.358; **a wider stop** (owner, 2026-10-19 ~02:45 Thai: "take the profitable one,
  never mind my account's size"): at least 8 / 12 / 16 USD -0.005 / -0.026 / -0.021 R (the best cell +0.013);
- kind 2 (fell short): **break-even at half the target** -0.037 R; with the wider stops -0.050 / -0.064 / -0.063;
- kind 1 (wrong way): the side from the earlier runs' way (V2s) or from the earlier trades' results (the premise
  above) - better than a coin, not enough to earn;
- every kind: no target, out after 5-60 minutes - negative after the costs.
**No variant of the trade earns on the learning half; the exam was run for none of them.**

## Is the picture right, is the reading right? The owner: "something must still be wrong" (2026-10-19 ~02:55 Thai)

**The data under the picture and under the trade (checked):** the pictures (`plib.load`) and the trades
(`jlib.m1_frame`) read the same store (gold.bars, UTC): equal prices on all 1,128,894 common minutes, no duplicate
times; for all 723 V2s trades the trade's reference close equals the picture's last M1 close and the entry bar opens
one minute after the picture's last bar - no offset, no look-ahead; the spread column is in 0.01 USD points (median
23 = 0.23 USD).

**The readings by eye (`loser_audit.py`, `png/loser_audit/`, eight exam losers of the three kinds, the stored
readings, what followed, and two of the evidence days):** the M5 / M1 readings are right by their definitions
(e.g. 2026-07-27 19:30 TH: M5 down, mixed - the last peaks higher, the forming trough lower - the close just above
its last bottom; M1 LH/LL, the close below its last bottom).

**What was wrong - the evidence, not the chart (`out_evidence_bias.txt`):** the library mixes the snaps (fixed
times, every outcome kept) with the starts of 10 U runs - picked after the fact, and by the run catalogue's
definition each one sits at the extreme where a run began (the low before a run up). 38 % (learning) / 48 % (the
exam) of every trade's evidence days are such starts. A picture that has just fallen therefore looks like "the start
of a run up" - the library holds many run-up starts that looked like it, but not the many times the same picture
kept falling (only those that fell at a snap time). **V2s fades the move: 83 % (learning) / 96 % (the exam) of its
trades go against M1's last leg; 72 % / 86 % buy in the lower 30 % of M1's range or sell in the upper 30 %** - the
kind 1 and kind 3 losers (buying a fall that keeps falling, or falls further before it turns). In the exam (a
trending gold) the trades against M5's 120-bar way lost -0.123 R, those with it earned +0.042 R; in the learning half
the reverse (+0.020 vs -0.100) - the phase decides which way pays.

**Without the bias** (the evidence from snaps only, the result library above): the picks earn about 0 R (-0.002 /
+0.014), no edge and no big loss. The owner's own rule (2026-10-19: "with the larger timeframe's trend; near a major
support / resistance price may turn") is the opposite of what the biased library did.

**The owner (2026-10-19, ~03:15 Thai): "the library's pictures must be what the bot sees in the present - many look
as if price has already broken" (`out_library_present.txt`, `library_present.py`, `png/library_present/`):** every
run-start picture ends at the run's start bar (13,873 of 13,873) - no bar of the run is in it - but the owner is
right that they are pictures of a break that has just happened the other way: of the run-up starts 35 % have M1's
close below its last bottom (ordinary snaps 15 %), 73 % a last leg down, M1's close at a median 0.32 of the range
(snaps 0.54); the run-down starts the mirror (27 % above the last top, 68 % a last leg up). They are the end of a
sweep or a crash, kept because a rebound followed (e.g. 2026-01-21 22:25 TH: M5 and M1 had just crashed 50 USD
through every bottom; the grey bars after it rebound). The same pictures that kept falling are not in the library
(only those at a snap time), so a fresh breakdown reads as "up" to the bot.

**The fix (to build):** the library must be built the way the bot sees the market - moments taken by the clock inside
the owner's windows (every few minutes), each with what followed, never chosen because of what followed; the bot
decides at the same moments, so the library and the bot look at the same population.

## The present library - written before it is computed (2026-10-19 ~03:20 Thai; owner: "the library's pictures must be what the bot sees in the present"; "one wrong component breaks everything"; "do it correctly, with care and patience")

Every component passes three checks before it is used: the code (hand-worked tests, planted bugs, an independent
re-derivation), the data's origin (each entry chosen only by what was known at its time - tested), and only then
the premise against a no-effect baseline in two halves.
- **The moments (`present.py`):** every 5-minute clock time t (UTC :00, :05, ...) from 2023-11-01 to the exam's end
  inside the owner's windows (`plib.window_mask` of t, weekdays), where the M1 bar that closes at t exists (the market
  is trading) - nothing about what followed decides whether a moment is in. The bot decides at the same moments.
- **The picture at t:** every timeframe's bars closed by t, as the library's pictures (`picture.features`, the zoom,
  `snaps.shapes`) - one shared function for the old moments and the new ones, checked to reproduce
  moments_3y.parquet.
- **What followed (the labels, known later):** the run - the first 10 U run (the catalogue) whose start bar opens in
  [t, t + 30 min): ran_up / ran_dn, else none; the trade - V2's buy and sell from t (`trade_labels.trade`): R_buy,
  R_sell (none when no M1 bar opens within 5 minutes of t).
- **The evidence at t:** the earlier moments (>= 7 days before) in the same situation (per layer, L3 / L6 as fixed
  before), grouped by day: each day's mean R_buy / R_sell and run lean over its matching moments, then the mean over
  the days; the number of days. **The premise:** the better side when >= N_MIN days and its mean R >= THETA, its
  realized R against a coin's side at the same moments, with the error by day, in both halves (learning 2024-05 ..
  2026-04-17, the exam 2026-04-18 .. 10-16), and the placebo (the same clock time on the next trading day). Only
  then any trade backtest.

**Built and checked (2026-10-19 ~03:20-03:35 Thai):**
- `moments.pictures_at` (one picture function for every library): rebuilt all 29,073 old moments - 84 of 84
  columns and the outlines equal moments_3y.parquet. `trade_labels.trades_at` (V2's trade for any decision times):
  the snaps' labels rebuilt equal to the old file, and to V2s's 723 trades.
- `present.py`: 127,319 moments on 922 days (every 5 minutes inside the windows, the bar closing at t present);
  what followed: none 88,353, ran_dn 20,031, ran_up 18,935. Tests (`test_present.py`, by hand): the moments of a
  summer Wednesday around the New York 09:30 window (outside / inside, a missing bar), a Saturday, the end excluded;
  the run labels (a run on the decision's own bar counts, the horizon's end excluded, two runs on one bar - the up
  run, none). Two bugs found by the tests and fixed (a lone start equal to the end; no runs at all). Planted bugs 7
  of 7.
- **Me as the bot (`bot_eye.py`, the owner: "make yourself the bot"):** the chart read again from the raw M1 bars by
  code written apart from the bot's (bars, MT5's ATR, the ZigZag, every reading, the zoom): 1,000 random moments x 6
  timeframes x 13 readings = 78,000 values, **0 different**; planted bugs in my reader show at once (the forming
  swing ignored 626 differences, the window one bar short 1,767, no zoom 23; an equal high not moving the extreme 0 -
  too rare to touch a reading).
- **By eye (`eye_check.py`, six random moments, M5 and M1, clean candles read before the bot's values were shown):**
  the way, the close against the last top / bottom and the position agree; the structure 10 of 12. Every other
  difference was my imprecision (the closes at bars 40 / 80, a smaller ATR at the end, a swing I took as confirmed
  before its 3-ATR return) - the bot followed its rule. One real difference of scale: 2024-01-05 22:15 TH (NFP) on M5,
  after the spike the ATR jumped and the pullback a trader counts as a higher low is under 3 ATRs - the bot reads
  "mixed", the eye "up".

**The present library's premise (2026-10-19 ~03:45 Thai; `out_present_lean.txt`, `present_premise.csv`; the bot's
evidence and my plain recount equal on 150 moments in each of the six layer / level sets):** a coin's side earns
-0.077 R (learning) / -0.073 R (the exam). The picks beat the coin a little in the learning half at the trigger
layer (L6, N_MIN 10, THETA 0.2: +0.050, se 0.019) but earn -0.030 R, and the exam +0.022 (0.033), -0.062 R; the
only learning cell with a positive R (context L3, 10, 0.2: +0.017) earns -0.184 in the exam. No cell earns in both
halves - the premise does not hold. Without the run starts the bot no longer fades the move, but the same situation
tells the trade's side only a little better than a coin.

## Me trading by eye on the latest six months, against the bot - written before any decision (2026-10-19 ~03:50 Thai; owner: "if you backtest by yourself on the latest six months, would you profit and how many trades? Compare with the bot")

- **The moments:** one a trading day, New York 09:30 (13:30 UTC, summer time all through the exam), 2026-04-18 ..
  10-16, from the present library (the moments where a trade label exists).
- **What I see (`by_eye.py`):** H1, M5 and M1 - the 120 bars closed by the decision, candles only, no date, nothing
  after it - and the library's evidence (the trigger layer L6 and the context layer L3: matching days, mean R of
  the buy and of the sell).
- **How I decide (written now):** with the H1 trend when price has pulled back toward support / resistance on M5
  and M1 is turning the trend's way; against it only after a clear failed break at an obvious H1 level; no trade
  when H1 is flat and price sits mid-range, after a run already stretched far from where it started, or when M1 is
  a falling knife / rocket. The library's evidence is a tie-breaker, not the reason.
- **Every decision is written to `by_eye_decisions.csv` before any outcome is read;** the trade is V2's (the labels):
  entry at the next M1 open, the stop one entry-TF ATR >= 5 USD, the target 10 U, 12 entry-TF bars.
- **The bot at the same moments:** the side its evidence picks with the cell chosen walk-forward month by month; and
  the bot's full six months (every 5 minutes, one position at a time). Reported: trades, win, R, USD, week by week.

**Result (2026-10-19 ~04:00 Thai; `out_present_wf.txt`, `out_by_eye_bot.txt`, `by_eye_bot_decisions.csv`,
`by_eye_bot_scored.csv`).** The owner changed the test mid-way ("too few trades - the same conditions as the bot, the
decisions yours"): the bot on the present library (every 5 minutes, one position, the cell walk-forward) traded
**647 times in the exam (5 a weekday), win 0.338, R -0.084, -460 USD** (learning 736, -0.042 R). For a random 160 of
its exam trades I chose the side by eye (H1 / M5 / M1 and the library's evidence, no date, nothing after the
decision; every side written before any outcome was read), and flagged the ones I would not take:

| on the same 160 trades | trades | win | R a trade | USD |
|---|---|---|---|---|
| the bot's side | 160 | 0.369 | -0.054 | -69 |
| my side | 160 | 0.356 | -0.060 | -113 |
| a coin's side | 160 | | -0.034 | |
| my side, only the ones I would take (trend + pullback + M1 turning) | 21 | 0.381 | -0.024 | -12 |
| the bot on those 21 | 21 | 0.143 | -0.568 | -99 |

I took the bot's side on only 46 % of the trades, yet both lose alike (me minus the bot -0.006 R, se 0.125): at
these moments, with this trade (the 10 U target, the stop one entry-TF ATR, out after 12 entry-TF bars, the costs),
who picks the side hardly matters. The trades I would take on my own were 13 % of them and close to break-even - too
few to say more. The earlier New York 09:30 test with my own skips (the first 72 of 128 days): 12 trades, -0.229 R.

## The proposed rule as code, 2025-06-01 .. 2025-12-01 (owner, 2026-10-19 ~04:00 Thai: "backtest the method you proposed in 2025-06-01 .. 2025-12-01"; `rule_bt.py`, test `test_rule_bt.py`)

The by-eye "would take" trades as a rule: with the H1 trend (the 120 bars' way and the swing structure agree), M5
pulled back against it (its last leg against the trend; a buy's close in the lower 60 % of M5's range, a sell's in
the upper 60 %), M1 turned the trend's way (its last leg with it); every 5 minutes inside the windows, one position,
V2's trade. Tests by hand (both sides, the 60 / 40 % edges, a mixed structure, a flat H1, no pullback, no turn; the
H4 screen), planted bugs 5 of 5; my plain recount of the trades equal (324 of 324). The manual paper trade begun
before it (2026-03-23, eight charts in the 5,000 -> 4,100 crash, all skipped) was stopped by the owner's request.

| 2025-06-01 .. 2025-12-01 | trades | a weekday | win | R | USD | max DD | worst | streak |
|---|---|---|---|---|---|---|---|---|
| the rule | 324 | 2.49 | 0.321 | -0.085 | -183 | 218 | -13.92 | 13 |
| the rule + the H4 way agrees | 236 | 1.82 | 0.322 | -0.096 | -150 | 188 | -13.92 | 15 |
| the bot on the present library (walk-forward) | 206 | | 0.403 | +0.087 | +109 | | | |

A coin's side at the rule's moments -0.072 (-0.065 with H4). The buys about break-even (-0.019; with H4 +0.001), the
sells lose (-0.208; with H4 -0.388): in a rising year an H1 fall is a pullback of the larger rise. The rule from my
21 hand-picked trades does not hold as code; the bot had a good half-year here (+0.087 R) that the learning half as a
whole (-0.042) and the exam (-0.084) do not repeat.

## M and W only - written before it is computed (2026-10-19 ~04:10 Thai; owner: "the problem is not the market but your reading of the price structure - the library holds low-quality data and gives too many wrong signals; the raw material is not good enough; scope it down to M and W only and try")

- **W (a double bottom)** on a timeframe: the last three confirmed swings of the 3-ATR ZigZag (the swings the bot
  reads, checked on 78,000 readings) are a trough A, a peak B (the neckline), a trough C, the two bottoms alike -
  |C - A| <= 25 % of the height (B - min(A, C)); the signal is the first close above B after C (no newer swing
  confirmed): a buy. **M (a double top)** the mirror: peaks A, C alike, the trough B between, the first close below B:
  a sell. Only closed bars; M5, M15, M30 and H1 each on its own; decisions at the signal bar's close.
- **Checks before any result:** the detector by hand (made-up swings, both kinds, the tolerance's edge, a second
  cross that must not count, a newer swing that voids it), planted bugs, a second detector written apart (from the
  swing list instead of the bars), and the detected patterns drawn for the eye (the owner's too).
- **The premise (both halves - learning to 2026-04-17, the exam 2026-04-18 .. 10-16):** from the next M1 open, does
  price reach the measured move (the height, the signal's way) before going the height against - more than half
  the time (a driftless walk gives 50 %)? Per timeframe, every signal and inside the owner's windows.
- **Only if it holds:** the trades - the classic (the stop beyond C, the target the height) and V2's - one position
  at a time, chosen on the learning half, the exam once, week by week.
- **Stop hunts (added by the owner the same night: "and the stop hunting ones"):** on a timeframe, the first bar
  whose high goes above the latest confirmed swing peak but closes back below it (the stops above the top taken,
  price back inside): a sell at its close; the mirror below the latest trough: a buy. Only the first pierce of a
  level counts (a pierce that closes beyond it is a break, and the level is spent). The premise: from the next M1
  open, the distance to just beyond the sweep's extreme (+ 0.1 ATR) against the same distance the signal's way -
  more than half the time? The same checks first (by hand, planted bugs, a second detector, the eye).
- One planted bug in the M / W detector (marking a pattern fired before adding it) changes nothing - the freshness
  check already stops a second signal - so it is an equivalent mutant.
- **The owner, the same night: "don't read them from theory - read them from how the market's price really moves".**
  So the fixed shapes above (25 % alike, the neckline break, a pierce that closes back) are only the start. The
  events are collected wide - every pierce of the latest swing top / bottom (its depth in ATRs, whether it closed
  back inside, the level's age, the timeframe, the hour) and every pair of alike-shaped swings (the second bottom
  above or below the first and by how much, the bars between, the entry at the second bottom's turn or at the
  neckline) - and what price really did after each (the furthest the signal's way and against it within 60
  minutes, in ATRs, and the first passage at fixed distances) decides which shapes count, on the learning half; the
  exam confirms once. Every event is kept whatever followed (the run-start lesson: never pick events by their
  outcome).

**What price really did - the learning half (`explore.py`, tests `test_explore.py` by hand + a second count of the
pierces on random markets, planted bugs 8 of 8; `out_explore_learn.txt`; 8,532 pierces and 24,795 double entries
2023-11 .. 2026-10, all kept).** The first passage at 1 ATR the event's way before 1 ATR against (0.500 = no edge):
- **Stop hunts (the reversal after a pierce of the latest top / bottom):** closed back inside after a shallow pierce
  (< 0.25 ATR) 0.506 (n 1,886); **after a 0.25-1 ATR pierce 0.460 / 0.447 (n 836 / 546) - the pierce goes on more
  often than it turns**; deeper pierces few and mixed; pierces closing beyond 0.48-0.50. In gold the "stop hunt and
  turn" is not what the price does more often than chance.
- **Doubles:** every shape at the neckline entry 0.50-0.51; at the second extreme's turn 0.50-0.53 - **the best: the
  second bottom (top) a little beyond the first (0-25 % of the height), entered at its turn: 0.528 (n 2,294, se
  0.011), +0.18 ATR** - a double bottom whose second bottom sweeps just below the first, the two ideas in one.
**Written now, before the exam is read - the two shapes the data points to, each checked once on the exam:**
H1 the turn entry of a double whose second extreme goes 0-25 % beyond the first: 1-ATR first passage > 0.5;
H2 a pierce of 0.25-1 ATR that closes back inside: the continuation (the pierce's way) wins the 1-ATR first passage
> 0.5. Every timeframe together; the exam 2026-04-18 .. 10-16.
**The exam, once (`out_explore_exam.txt`):** H1 0.525 (se 0.023, n 471; learning 0.528), 2-ATR 0.539; H2 the
continuation 0.542 (se 0.029, n 306; learning 0.545), +0.55 ATR furthest-way minus against. Both keep their size in
the exam; together with the learning half H1 about 2.8 se and H2 about 3.6 se above a coin. Gold's real habit: a
pierce of 0.25-1 ATR beyond the latest top / bottom that closes back inside goes on through the level more often than
it turns; a double bottom / top pays a little when its second extreme sweeps just beyond the first and is entered at
its turn. Small edges (2.5-4.5 points over 50 %) - the costs decide: next, each as a trade with the costs, per
timeframe, the learning half first.

## Where the event happens - the larger timeframe's edge (owner, 2026-10-19 ~04:20 Thai) - written before it is computed

The owner: "everything is 50 %, like a coin - right; what gives it weight is the zone where it happens: at support /
resistance or in the middle of the price. We do not trade the middle; we trade at the edge of the timeframe larger
than the one we enter on. Don't think in one layer." Every event above gets, at its decision (closed bars only), its
place on H1 and on H4: where the price sits in the larger timeframe's 120-bar range (0 the low edge .. 1 the high
edge), and the distance to that timeframe's nearest confirmed swing bottom below and swing top above (in its ATRs).
The outcome is read by the place on the event's side: a buy (a W, a turn up after a sweep below a bottom) at the
larger range's low edge or a swing bottom; a sell the mirror; against the middle of the range. The learning half
chooses; the shapes it points to are written here before the exam is read once.

## Research outside, put together with the owner's own knowledge and our measurements (2026-10-19 ~04:25 Thai; owner: "go and research more, and put it together with my information")

What the literature and practice say (sources in the chat report):
- **Levels work, and they work two ways (Osler, NY Fed 2000 / 2002 / 2003, FX order books):** published support /
  resistance levels predicted intraday trend interruptions, for about five business days after they were given;
  take-profit orders cluster AT round numbers / levels (price stalls and turns at the first reach) while stop-loss
  orders cluster just BEYOND them (once crossed, price runs faster: a cascade).
- **Gold has round-number barriers** (Aggarwal & Lucey 2007; O'Connor & Lucey 2016, intraday 1975-2015): round
  levels (ending 0 / 00) change the mean and variance of gold's returns near them.
- **Springs / upthrusts (Wyckoff) are defined by where they happen:** a dip below the support of a mature trading
  range near its end (an upthrust the mirror) - not any pierce of any swing.
- **Double bottoms (Bulkowski, "perfect trades", bull markets):** the confirmed ones (after the breakout) are the
  measured ones; failed ("busted") patterns often run further the other way.
- **Liquidity sweeps, practitioners:** they reverse in ranges; in strong trends they more often continue; the gold
  London morning often prints a day's extreme, and New York often reverses London's first push.
Put together with the owner (OWNER_GOALS: the moments when price runs are the opens, releases, a contraction - "all
at important support or resistance"; several playbooks - break-and-hold, sweep-and-reclaim, with the higher flow;
"not in the middle - at the edge of the larger timeframe") and with our measurements (a 0.25-1 ATR pierce that closes
back inside goes on 54.5 % / 54.2 %: Osler's stop cascade; the textbook stop-hunt reversal and neckline break at
chance), the hypotheses to test, each a probability by its layers:
- **E1 the first reach of a larger-timeframe edge** (the H1 / H4 range edge or a swing level up to ~5 days old, a
  round 50 / 100 nearby), touched from inside without a pierce, M1 / M5 turning: a turn (take-profit clustering).
- **E2 the cascade:** a pierce of 0.25-1 ATR beyond such a level: the continuation (stop clustering).
- **E3 the spring / upthrust:** a sweep beyond the edge of a mature range (price inside it for a while) closing back
  inside: a turn - and in a trend: the continuation.
- **E4 the double bottom / top at the larger edge,** the second extreme sweeping just beyond the first, entered at
  its turn.
Each read by its layers - the place (edge / middle, the level's age, a round number), the larger timeframes' way,
the session (the opens) - as the probability of the 1-ATR first passage, the learning half choosing and the exam
reading it once.

## Every layer together - the first probability model (2026-10-19 04:42 Thai; owner: "combine every discipline and look at its probability"; "go on")

`touch.py` (the first reach of an H1 / H4 level from M5 without a pierce; tests by hand + a second count on random
markets, planted bugs 5 of 5), `combine.py` (42,361 candidate trades: the pierces both ways, the doubles at both
entries, the touches; the place on H1 / H4, the round 50, the H1 / H4 way and structure from `pictures_at`, the hour,
the windows, the M5 ATR against its 20-day median; the pierces' reversal outcomes asserted equal to explore.py's,
8,532 of 8,532 - the check first failed because one level pierced on several timeframes at once matched the wrong
rows; matched on the timeframe too), `model.py` (gradient-boosted trees, depth 3, learned on the learning half to
2025-10-16, the rest of it held back to stop the learning and to choose the threshold; the exam read once).
- With the side as a feature: AUC 0.523 held back, 0.511 exam; p >= 0.54 (the held-back choice: 0.546, 568 picks):
  **the exam 0.589 (377)**. The picks are 87 % buys, but they are not the drift: all exam buys win 0.491, the
  picked buys 0.595 (sells: 0.519 all, 0.551 picked); 77 of the 377 are one market moment on several timeframes.
- **Not told the side (it cannot learn a drift): AUC 0.518 / 0.519; p >= 0.52 (the held-back choice: 0.532, 1,302
  picks): the exam 0.548 (934, se 0.016).** What carries it: the hour, the distance to the H1 level the trade leans
  on, the place in the H4 range, the second extreme of a double - the place and the moment, as the owner said.
**Written before the trades are run:** the side-blind model, p >= 0.52; each pick a trade at the next M1 open (the
ask for a buy), the stop and the target 1 ATR of the event's timeframe, out after 240 minutes, the auditor's costs,
one position at a time (repeats of one moment skipped); the exam week by week, once.

### The picks as trades (04:47 Thai; `model_trades.py`, `out_model_trades.txt`)
`model_trades.trade_1atr` (lvl2.manage with the stop and the target one ATR, no break-even, out after 240 minutes) and
`take` (one position, at one moment the highest chance first): tests by hand (a buy's target, a sell's stop on the ask
with the New York slippage, the stop first when one bar reaches both, out after 240 minutes), a second count against a
plain re-statement on random markets (148 trades of all three exits), planted bugs 7 of 7 caught. The trades agree with
the mid-price 1-ATR passage on 96-97 % (the rest: the spread).
- **Side-blind, p >= 0.52 (written down first): the exam 629 trades, win 0.504, R -0.003, USD +54 (0.01 lot), max DD
  107, longest losing streak 8; held back 896 trades, R +0.031.** Week by week: -116 USD by the end of May, then up.
- With the side, p >= 0.54: the exam 267 trades, R +0.052, USD +170, September's five weeks -95; held back R +0.002 -
  the held-back part does not stand behind it.

Where the 1-ATR passage's edge went, one step at a time (owner, 04:48 Thai: "slowly, one part at a time, not one
lump that breaks so you cannot tell what to fix"):

| side-blind p >= 0.52 | picks | 1. passage win (mid) | 2. after the costs: win, R | trades | 3. one at a time: win, R | the costs in R |
|---|---|---|---|---|---|---|
| held back, all | 1,302 | 0.532 | 0.500, -0.006 | 896 | 0.519, +0.031 | 0.069 |
| the exam, all | 934 | 0.548 | 0.519, +0.028 | 629 | 0.504, -0.003 | 0.075 |
| held back M5 / M15 / M30 / H1 | 824 / 243 / 158 / 77 | 0.530 / 0.523 / 0.525 / **0.597** | R -0.026 / +0.003 / +0.008 / **+0.155** | 604 / 158 / 89 / 45 | R +0.005 / +0.029 / +0.099 / **+0.245** | 0.090 / 0.050 / 0.039 / 0.024 |
| the exam M5 / M15 / M30 / H1 | 544 / 227 / 112 / 51 | 0.566 / 0.480 / 0.518 / **0.725** | R +0.038 / -0.075 / +0.009 / **+0.411** | 397 / 143 / 60 / 29 | R +0.001 / -0.099 / +0.047 / **+0.315** | 0.096 / 0.059 / 0.044 / 0.026 |

- The costs take about 3 points of win (0.06-0.07 R) - as much as the model's whole edge on M5 (a 5-USD stop pays
  0.09 R a trade); one position at a time moves it either way (held back +0.04 R, the exam -0.03 R).
- Only the H1 events keep their edge after the costs in both parts (0.597 / 0.725 passage, R +0.155 / +0.411), on few
  trades (77 / 51 picks). M15 does not hold in the exam (0.480).
- Next, one part at a time, each checked before the next: (a) every candidate's own trade result after the costs, its
  base rate by timeframe and kind - no model; (b) the H1 events alone, why they hold (by eye too); (c) the model
  learning the after-cost result - one change from this one; (d) walk-forward month by month for more unseen trades.

### The trades by pattern (04:52 Thai; owner: "how many of each - M, W, hunting?")
Side-blind p >= 0.52, the trades one at a time (candidates: every event in the part, both entries of a double and both
readings of a pierce; totals asserted against the run's own file):

| the exam | candidates | picked | trades (turn / neck) | win | R | USD |
|---|---|---|---|---|---|---|
| W (buy) | 1,996 | 336 | 237 (163 / 74) | 0.515 | +0.018 | +159 |
| M (sell) | 2,043 | 444 | 309 (220 / 89) | 0.502 | -0.006 | -57 |
| a hunt below a low, bought back | 719 | 14 | 13 | 0.538 | +0.066 | +17 |
| a hunt above a high, sold back | 677 | 3 | 2 | 0.000 | -1.000 | -20 |
| a high broken, bought on | 677 | 58 | 24 | 0.542 | +0.067 | -2 |
| a low broken, sold on | 719 | 79 | 44 | 0.455 | -0.101 | -43 |
| the first touch of an H1 / H4 level | 63 | 0 | 0 | - | - | - |

Held back: W 460 trades R +0.023, M 317 R +0.028, the hunts bought / sold back 26 + 6, the breaks 62 + 25. M and W are
87 % of the trades; the model almost never takes a hunt's reversal (17 of 1,396 in the exam). By timeframe in the
exam: M and W on H1 23 trades, win 0.73 / 0.75, +176 USD; **M on M15 71 trades, win 0.408, -150 USD** - the largest hole.

### Part (a): every candidate after the costs, no model (04:56 Thai; `base_after_costs.py`, `out_base_after_costs.txt`)
42,361 candidates as model_trades.py's trade (its 629 exam trades re-found equal); the learning half only printed.
- **No pattern on any timeframe earns after the costs in both learning parts** (2023-11 .. 2025-10-15 and the held-back
  2025-10-16 .. 2026-04-17); part 1 R -0.18 .. -0.28 by pattern, part 2 -0.03 .. -0.13. A few part-2 cells are just
  above zero (a low hunted and bought back on M15 / M30 +0.006 / +0.024, a high hunted and sold back on M30 +0.066,
  the H1 breaks +0.02 / +0.03), none in part 1.
- Why part 1 is so much worse - checked, not a bug: the M5 events' mid-price 1-ATR passage wins 0.49-0.52 in every
  quarter, but the M5 stop (one ATR) was 1.0 USD in 2023-Q4 / 2024-Q1 against about 0.54 USD of costs (the spread
  column + 0.08 + 0.07 slippage + 0.15 stop slippage): **the costs were 55 % of the stop**, 30-35 % in 2024-Q2 .. Q4,
  9-15 % from 2025-Q4 on (stops 4-7 USD). The after-cost win follows that share exactly (0.29 -> 0.46).
- So: the events alone win 49-52 % before the costs (known), and a one-ATR stop on a small timeframe is too small for
  gold's costs - the owner's floor (a target and a stop of at least 5 USD; the entry timeframe moves up when ATR falls)
  is needed. Next part: the same table with the stop and the target at least 5 USD, then the larger timeframe's edge
  against the middle (the owner: the weight is the place).

### Part (b1): the stop and the target at least 5 / 10 USD (05:00 Thai; owner: "do it - widen the stop, grow the account, whatever it takes - say so"; `base_after_costs.py 5 | 10`, `out_base_floor5.txt`, `out_base_floor10.txt`)
One change: the stop and the target max(one ATR, FLOOR); the no-floor re-run gives the same tables line for line.

| learning half, every candidate | R a trade | buys | sells | exits stop / win / time |
|---|---|---|---|---|
| one ATR (part a) | -0.198 | -0.170 | -0.227 | 0.58 / 0.40 / 0.02 |
| at least 5 USD | -0.085 | -0.044 | -0.128 | 0.46 / 0.40 / 0.14 |
| at least 10 USD | -0.047 | -0.008 | -0.087 | 0.31 / 0.29 / 0.40 |

The floor cuts the cost loss by more than half (part 1's small stops); in part 2 (stops already 5-7 USD) it changes
little. Still no pattern earns in both parts (5 USD: one cell, the H1 breaks bought on, +0.002 / +0.023). Buys lose less
than sells throughout - gold doubled over the learning half.

### Part (b2): the floor-5 trades by the place on H1 / H4 (05:01 Thai; `place_after_costs.py`, `out_place_floor5.txt`)
Counts checked: the bins add up to each group; a hunt at its far edge is the same event as a break at its own edge.
- **Doubles at their own edge lose the most:** a W at / below the low of the H1 range, an M at / above its high:
  R -0.148 / -0.194 (H1), -0.139 / -0.146 (H4). The textbook "W at support" is buying a range that is breaking down.
- Doubles at the far edge (a W near the top of the range, an M near its bottom - with the larger timeframe's push)
  lose the least: -0.012 / -0.068 (H1), -0.011 / -0.127 (H4). The breaks at the far edge of H1 (a high broken near
  the top of the range, bought on): -0.006 / +0.013.
- Hunts bought / sold back 0.5-1 H4 ATR from the level they lean on: +0.039 / +0.142 (461 / 108 trades, se 0.042 /
  0.094) - the only bin above zero in both parts, not yet beyond chance.
- One layer of place alone gives no after-cost edge; the side with the larger timeframe's push loses least.

### Part (c): the model learns the after-cost result - written before it is computed (05:03 Thai; `model_cost.py`)
One change from model.py's side-blind model: the label is the floor-5 trade's own result after the costs (R > 0), every
candidate kept (no "none" rows to drop: every trade ends); the features, the split (fit to 2025-10-15, held back to
2026-04-17), the trees and their settings stay. The trades are the floor-5 trades, one at a time (model_trades.take).
**The threshold:** of p >= 0.40, 0.45, 0.50, 0.55, 0.60, the lowest whose held-back trades (one at a time) reach
R >= +0.05 with at least 150 trades; none -> the exam is not read. The exam: that threshold once, week by week.
**Part (c), the result (05:02 Thai; `out_model_cost_floor5.txt`):** a profitable floor-5 trade 0.457 fit / 0.465 held
back; AUC held back 0.522; held-back trades one at a time: p >= 0.40 / 0.45 / 0.50 / 0.55 / 0.60 -> 2,827 / 2,300 /
971 / 199 / 36 trades at R -0.068 / -0.061 / -0.054 / -0.001 / +0.066. **No threshold reaches +0.05 R with 150
trades: by the rule the exam is not read.**

### The two shapes that held in the exam, as trades with the costs (05:03 Thai; the learning half only)
The premise again on these rows (mid-price 1-ATR passage): the sweep double at its turn 0.529 / 0.523, the 0.25-1 ATR
pierce closed back, followed 0.544 / 0.538 (parts 1 / 2). After the costs, R a trade, parts 1 / 2:

| shape, timeframe | stop 1 ATR | stop >= 5 USD | stop >= 10 USD |
|---|---|---|---|
| sweep double, all (1,822 / 472) | -0.199 / -0.037 | -0.075 / -0.023 | -0.050 / -0.001 |
| pierce followed, all (1,102 / 280) | -0.162 / +0.008 | -0.053 / +0.017 | -0.027 / +0.000 |
| pierce followed, M15 (270 / 66) | +0.006 / -0.053 | +0.024 / -0.023 | +0.005 / +0.016 |
| pierce followed, M30 (135 / 24) | +0.093 / -0.006 | +0.056 / -0.006 | -0.012 / -0.005 |
| pierce followed, H1 (75 / 14) | +0.039 / +0.195 | +0.076 / +0.195 | +0.020 / +0.195 |

The 3-4.5-point edges are about the costs' size: break-even at best, far from +0.15 R. The costs are 1-3 % of an H1 /
H4 stop (20-40 USD) against 9-55 % of an M5 one, and the strongest lead so far is the model's H1 picks (held back
R +0.155 on 77, the exam +0.411 on 51). Next: the events on H1 and H4 only (H4 added to explore / combine), more of
them through walk-forward month by month - the stop 20-40 USD at 0.01 lot.

## The owner's cut - two or three trades a day, the heavy and wrong-way losers out (2026-10-19 05:07 Thai; owner: "keep two or three trades a day on average; take out the ones that lose a lot, the wrong-way ones, and run again")
**Step 1 (`losers.py`, `out_losers_floor5.txt`; the floor-5 trades, learning only).** Buckets below -0.10 R a trade in
both parts: against the H1 swing structure (-0.112 / -0.116; against H1 and H4 -0.109 / -0.130), the late session
17-24 UTC = 00-07 Thai (-0.118 / -0.121), the first touches of an H1 / H4 level (-0.206 / -0.128), and M (sells)
(-0.130 / -0.101). The sells are not cut by side: both learning parts are rising gold (2,000 -> 5,000), the exam
falls - a side rule would be a bet on the drift; a sell against the structure is cut with the rest.
**Steps 2-3 (`cut.py`, tests `test_cut.py`: the three buckets by hand, one position and one trade a session, a busy
position passing the session on, the exit bar still busy; planted bugs 7 of 7 after the fourth test was added - the
first three tests missed "the exit bar free").** Part 1 / part 2:
- every candidate one at a time: 13.2 / 22.1 trades a weekday, R -0.092 / -0.082;
- the cut (15,228 of 28,283 candidates kept): 9.3 / 14.3 a weekday, R -0.068 / -0.082;
- + one trade a session (the first that qualifies): 2.95 / 2.92 a weekday, **R -0.140 / -0.151** - worse: the
  first event of a session is its open (London -0.19, New York -0.17).
- Checked the worst trade (-92.83 USD): an H1 stop of one ATR in the 2026-01-29 .. 02-02 crash (H1 ATR 70-125 USD);
  every loser is exactly -1 R, none beyond 1.2 R.
- After the cut by timeframe: M5 -0.075 / -0.079 (the costs), M15 -0.054 / -0.025, M30 -0.050 / -0.022, **H1 -0.013 /
  +0.033**; the minutes since a session's open show no steady pattern.
**Step 3 again - written before it is computed:** the cut plus the timeframe floor: (A) M15 and up, (B) M30 and up,
(C) H1 only, one position at a time; (D) M15 and up with one trade a session. Chosen: the highest of min(R part 1,
R part 2) among those with at least 1.5 trades a weekday in part 2; the exam is read once if that minimum is above 0.
**Step 3 again, the result (05:12 Thai; `out_cut_learn.txt`), part 1 / part 2:**

| | trades a weekday | R a trade | USD at 0.01 lot | max DD | longest losing streak |
|---|---|---|---|---|---|
| A: M15 and up | 5.1 / 5.6 | -0.059 / -0.049 | -783 / -530 | 841 / 855 | 12 / 9 |
| **B: M30 and up** | **2.7 / 2.8** | **-0.056 / -0.028** | -488 / -99 | 637 / 379 | 9 / 6 |
| C: H1 only | 1.1 / 1.0 | -0.072 / +0.016 | -217 / -6 | 385 / 231 | 12 / 7 |
| D: M15 and up, one a session | 2.6 / 2.5 | -0.065 / -0.026 | -398 / -97 | 476 / 307 | 10 / 6 |

By the rule: B (the highest minimum, -0.056, with 2.8 trades a weekday). **Its minimum is below 0: the exam is not
read.** Inside B nothing loses in both parts any more - every pattern, session and H1 / H4 flow bucket changes sign
between the parts (W +0.021 / -0.133, M -0.088 / +0.002, the high hunted and sold back -0.187 / +0.094): a further
cut would follow noise. The loss steps so far (learning, R a trade): every candidate at one ATR -0.198 -> a 5-USD
floor -0.085 -> the owner's cut -0.068 / -0.082 -> B -0.056 / -0.028 at 2.7 a day.

### The cut's losers, by the owner's three kinds (05:18 Thai; `losers_b.py`, tests `test_losers_b.py`, `out_losers_b.txt`)
Variant B against the opposite side at the same moments (the same stop and target), parts 1 / 2: wrong way 28.7 / 23.6 %
(opposite side 29.7 / 25.8), fell short 7.2 / 11.7 % (7.9 / 10.9), entered too early 8.4 / 12.2 % (8.9 / 12.8; a stop of
1.34 / 1.35 times would have survived), won 40.3 / 45.7 % (38.9 / 44.3); R -0.056 / -0.028 against the opposite side's
-0.090 / -0.054. The losers look like the opposite side's: the side is chosen about 1.5 points better than 50 %, the costs
take the rest. No exit lever fixes an entry that picks the side this weakly: half the target is reached by 59 / 65 % of the trades, the
winners go 0.33 of the stop against them first (median; 29 / 32 % beyond half the stop). The lever is the entry.

## The patterns gold runs from, on timeframes that agree - written before it is computed (2026-10-19 05:20 Thai; owner: "find the patterns gold most likes to use to run, on the timeframes that agree with each other")
The data: the present library (`present_3y.parquet`: 127,319 moments, every 5 minutes inside the owner's windows,
never chosen by what followed; every timeframe's reading at that moment, M1 .. H4, from `moments.pictures_at`,
checked against an independent reader on 78,000 readings) and what followed: the first 10 U run (10 USD at the
reference price, within 15 minutes, its start never broken) starting within 30 minutes, up or down.
For each way (up / down) and each timeframe, the readings turned to the run's side: the swing structure (HH/HL with
the way, against, mixed), the close beyond the last swing top / bottom (with, against, between), the 120 bars' way,
the last leg's way, a new high / low at the edge, the last third's way. Measured, never picked:
- how often each reading is there before a run its way (what gold "uses") and how often it is there anyway;
- the chance of a run its way with the reading (the lift over the base) and of a run the other way (a reading that
  only raises both is activity, not a side);
- the timeframes agreeing: the number of M5 .. H4 with the structure (and the break) the run's way, and the strongest
  stacks of three.
Learning in two halves (to 2024-12-31; 2025-01-01 .. 2026-04-17). **A pattern counts when the run its way is at least
1.2 times the base and above the other way's in both halves, on at least 500 moments each; only those are read in
the exam, once.**
**The result (05:20-05:22 Thai; `runpat.py`, tests `test_runpat.py` by hand - the readings turned, the long form both
ways, the scores, the agreeing timeframes - planted bugs 7 of 7; `out_runpat.txt`, `runpat_learning.csv`).**
On the catalogue's label, six patterns counted by the rule and held in the exam: a fresh 120-bar low / high on M1, M5,
M15, M30 and a close below the last swing bottom (above the top) on M1 / M5, each followed by a run the other way
(lift 1.29-1.56 in the exam; the run its way 0.34 against 0.13-0.16 the other way at the M1 / M5 edge). The
timeframes agreeing (structure, break, the 120 bars' way on M5 .. H4) raised nothing - with all five the run the
other way was a little more likely.
**The check (`runpat_check.py`, `out_runpat_check.txt`; its vectorised first passage equal to mw.first_passage on
3,000 random trades, 0 differences): the "turn at a fresh low" is the catalogue's, not gold's.** The catalogue
starts no run of a way while the last run of that way is still going, so at a fresh low - inside a fall - a run down
is hardly ever "starting". From the next M1 open, 5 / 10 U up before down (and the mirror) within 240 minutes:
at an M1 / M5 / M15 low edge the turn comes first 0.49-0.51 (5 U) in both halves and the exam - the 50 % line. Every
label built on the run catalogue carries this (the run starts of the first library, the present library's class):
judge with a symmetric first passage, never with "a run starts".
**On the symmetric yardstick, the timeframes agreeing give a small, steady tilt their way:** the structure (HH/HL)
the way on 3 of the 5: 5 U that way first 0.499 vs 0.466 the other (L1), 0.502 vs 0.486 (L2), **0.509 vs 0.490
(exam)**; the close beyond the last swing on 3 of the 5: 0.503 / 0.464, 0.512 / 0.481, **0.522 / 0.478**; all five
in structure 0.493 / 0.488, 0.518 / 0.478, 0.542 / 0.458 (exam n 419). Two to four points the agreed way in every
part - the only multi-timeframe pattern that holds, and about the size of the costs at a 5-USD target (about 5
points needed; about 2.5 at 10 U).

## Be an observer - the coin flip is out of the system (owner, 2026-10-19 ~05:25-05:30 Thai)
"Stop using the word coin flip." "I did not ask for a replacement word - remove it from the equation of building the
system." "Learn to be an observer, not give up whenever something is 50/50 - this game is 50/50 if you look
carelessly." "Do you think the people with the money to move the market toss a coin and then press buy or sell?"
From here on: no random-side baselines, no "chance / 50-50" verdicts, no synonym for them (also written in CLAUDE.md,
BRIEF.md and the memory). A result near 50 % means the moments were not yet told apart: split them by what was there
- who was acting, when, where - and find where and why price goes one way. Each component is judged by its own
outcome (win %, R after the costs, USD, how far price got) against the goal and the other components.

## Why gold runs the way it does - the components, written before they are computed (05:30 Thai; owner: "dig deeper into why it runs that way - many components, the larger timeframes and the indicators")
Large money does not guess: it needs the other side of its orders, so it acts at certain times (the London gold
fixes 10:30 / 15:00 London, the COMEX open 08:20 New York, the US data at 08:30 New York, the session opens, the month
end) and at certain places (where the resting orders are: the previous day's high / low, today's open, the round
numbers, the swing levels), and it leaves footprints (the tick volume against the usual for that minute, the size of
the bar, the dollar moving with it). The components read at every moment of the present library (closed bars only):
1. each timeframe's indicators as MetaTrader 5 draws them (`indicators.py`: RSI, MACD, Stochastic, ADX / DI,
   Bollinger, EMA 20 / 50 / 200 and their slopes, ATR against its median) on M5, M15, H1, H4 and D1 (H4 / D1 on the
   server day), the place in the previous day's range and the distance from today's open;
2. the footprints: the tick volume of the last bars against the same minutes' median of the last 20 days; the
   minutes to / since the fixes, the COMEX open, the US data minute; the distance to the previous day's high / low,
   today's open and the nearest round 10 / 50 (in ATRs);
3. the existing pictures (structure, break, place, legs on M1 .. H4).
The outcome: from the next M1 open, 5 and 10 U up before the same down (the yardstick checked on 3,000 trades). One
part at a time: (a) the readings, their code proven (by hand, planted bugs, a second computation on the bars cut at
the moment - nothing after it can change a value); (b) each component alone, by bins, in both learning halves - where
price goes up first more often and where down; (c) the components together, learned on the first half, checked on
the second, the exam once - and what carries the weight, read as the reason.
**Part (a), the readings proven (06:00-06:15 Thai).** `indicators.py` (tests `test_indicators.py`: H4 / D1 on the
server day across the 21:00 UTC boundary, the last bar complete by a moment, a steady rise worked by hand - ATR 1.5,
RSI 100, MACD 7 / 1.5, its signal difference 0, Stochastic 96.43, +DI 66.7, ADX 100, Bollinger %B and width, the EMA
warm-up and slope - the differences' signs against foundation's own lines, and every reading recomputed from the M1
bars cut at 12 random moments: equal; planted bugs 9 of 9, the MACD-signal sign caught only after the sign test was
added). Two bugs found by the tests before any run: a read-only EMA array, a 5-bar shift on short series.
`footprints.py` (tests `test_footprints.py`: the volume against the same minutes of earlier days only - today's own
bar would move the median from 75 to 100 - the fixes / COMEX / US data minute in their zones across summer time, the
round numbers, the move before from closed M1 bars only - a forming bar planted at 500 must not count - the dollar's
sign as a whole and pair by pair; planted bugs 6 of 6 after the forming-bar test was made to bite). 127,319 moments x
82 indicator readings (D1 missing 2 %: the 200-day EMA's warm-up) and 16 footprints, no gaps.
**Part (b), each component alone (06:16 Thai; `why.py`, tests `test_why.py`; `out_why.txt`, `why_lean.csv`).** Up
first minus down first, the lowest against the highest quintile of each reading (edges from L1), L1 | L2: no single
reading moves it by more than about 0.09 (4-5 points each side); the steadiest - the daily ATR against its median
(calm -> up first: +0.080 / +0.051 at 10 U, busy -> about 0), the place in the M15 / M30 range (high -> up first),
the place against the round 50 and the previous day's range, a deep H1 pullback (10 U: +0.047 -> +0.122 / +0.009 ->
+0.046), the H4 / D1 trend strength readings. Each alone is a few points; the reason has to be read in their
combination.
**Part (c) - written before it is computed (06:17 Thai; `why_model.py`):** every reading together (the indicators,
the footprints, the pictures, the hour, the weekday), gradient-boosted trees (depth 3, min 300 a leaf) learned on L1
to predict "up first" among the moments where one side came first, for X = 10 U (and 5 U), checked on L2: the AUC,
the calibration by decile, and the picks at symmetric thresholds (p >= q a buy, p <= 1 - q a sell). **The
threshold:** the q of 0.55 / 0.58 / 0.60 / 0.62 / 0.65 whose L2 picks number 2-4 a weekday with the highest win
rate; the exam once at that q. What carries the weight: the AUC lost on L2 when each reading is shuffled, and the
direction each top reading pushes - read as the reason.
**Part (c), the result (06:30 Thai; `why_model.py`, tests `test_why_model.py` - one pick an hour, the sides and wins
by hand, planted bugs 4 of 4, one wrong expectation of mine in the test corrected; `out_why_model_10.txt`).** X = 10 U,
learned on L1 (35,713 moments with a side first, up 0.529), on L2 (48,267, up 0.504): AUC 0.503; the picks at q =
0.55 .. 0.65 are 6-13 a weekday at 0.505-0.519 - no q gives 2-4 a weekday: by the rule the exam is not read.
**What the model learned, and why it failed on L2 - the observation:** on L1 (2023-08 .. 2024-12) the larger
timeframes turned back - high in the H4 range, far above the H1 EMA 50, +DI far over -DI on H1 / H4, the H4
Stochastic high: down first (its predictions 0.40-0.45 at the top quintile). On L2 (2025-01 .. 2026-04, gold 2,600 ->
5,000) the same readings at the top went up first (0.52-0.535). The larger timeframes' place means a turn in one phase
of the market and a continuation in another: the components are read wrong unless the phase is read first.
- A first try at the phase (the D1 ADX terciles, the H4 place turned to the D1 +DI / -DI side) showed a cell that
  looked steady - a weak D1 trend, price at the low of the H4 range on the D1 side: the D1 way first +0.19 / +0.36 -
  but by days it is 20 days in L1 and one day (14 moments) in L2. The 5-minute moments cluster: every count must be
  read by distinct days as well. Not a finding.
Next: a phase reading known at the moment (trend vs range on D1 / H4: ADX, the efficiency of the last 20 days, the
EMA slopes, the range width), the components read inside each phase, every cell counted by days, in both halves.

## The phase first, then the components inside it - written before it is computed (2026-10-19 06:50 Thai; owner: "do it")
`phase.py` (tests `test_phase.py`: the efficiency of a straight rise / fall = 1, back and forth = 0, a net 2 over a
path of 4 = 0.5, no move = NaN; the way; the range width in ATRs; a hard fall on the still-forming day must not count;
planted bugs 5 of 5 after two tests were added - a straight fall and the forming day): D1 over 20 days, H4 over 30
bars - the efficiency (Kaufman), the way, the range width - at every moment from the bars complete by it.
The phase: the D1 efficiency in L1's terciles - "D1 running" (top), "between", "D1 back and forth" (bottom) - and the
D1 way. Inside each phase, every component turned to the D1 way (a place 0..1 becomes 1 - place when D1 falls; a
signed reading times the way; RSI / Stochastic as (x - 50) x way; Bollinger %B as (x - 0.5) x way), and the outcome
turned too: the D1 way's X first minus the other way's (X = 10 and 5 U). Read by the component's quintiles (L1's
edges), **counted by moments and by distinct days (each day's mean once)**. A component counts in a phase when its
move from the lowest to the highest quintile has the same sign in L1 and L2 by days, with at least 30 days in each
end bin in both halves. First the phase alone: does the D1 way come first more often when D1 runs?
**The result (06:50-06:55 Thai; `phase_tables.py`, tests `test_phase_tables.py` - the readings turned to the D1 way, the
days counted by each day's first moment; `out_phase_tables.txt`, `phase_tables.csv`).**
- **A bug of mine found before any conclusion:** the first run weighted every day by the mean of its moments in a bin
  and showed 0.3-0.5 leans everywhere (M15 RSI, M5 / M15 place ...); the moments themselves gave 0.03-0.08. How long a
  reading stays in a bin depends on what price does next, so a day's mean leaks the future (a brief spike that turns
  weighs as much as a whole day that runs on). Fixed: each day's FIRST moment in the bin (known when it happens);
  tested - a day of (-1, +1, +1) counts -1 - and planted (the day mean again, the first not by time): caught.
- The phase alone (10 U, the D1 way first minus against, moments | first moments by day): D1 running +0.010 | +0.007
  (L1), +0.043 | +0.057 (L2); D1 back and forth -0.055 | -0.056, -0.065 | -0.081 - when D1 went back and forth over 20
  days, its 20-day way is the one that does NOT come first, in both halves.
- Inside "D1 running", the larger timeframes with D1 push its way: H1 swing structure against D1 -> with it -0.241 ->
  +0.177 (L1, 54 / 79 days), -0.069 -> +0.103 (L2, 58 / 126 days); H1 MACD, H4 EMA 20, H4 Stochastic, H4 DI alike.
  Per-day first moments are single +-1 values: 40-130 days a bin is +-0.09-0.16 of noise - read the moments with them.
- One rule from it (learning only): D1 running (20-day efficiency >= 0.264) + the H1 structure with the D1 way + H4
  +DI / -DI with it -> the D1 way. 10 U: the D1 way first 0.423 vs 0.385 against (L1, 6,182 moments, 71 days), 0.479
  vs 0.408 (L2, 11,595 moments, 119 days) - as 1:1 trades of 10 U a win share of 0.524 / 0.540, against about 0.527
  needed to cover the costs and about 0.60 for +0.15 R. The rest of the running phase: 0.374 vs 0.382, 0.448 vs 0.429.
  The alignment of D1, H4 and H1 is the reason price runs the D1 way more often (two to seven points); it is not yet
  enough. Next: inside the aligned phase, the entry - where on M15 / M5 the run its way starts (the pullback's depth,
  the turn, the hour) - read the same way, by moments and first moments, both halves.

## The entry inside the aligned phase - written before it is computed (2026-10-19 07:22 Thai; owner: "do it")
The aligned phase (learning only so far): D1 running (20-day efficiency >= 0.264) + the H1 swing structure with the
D1 way + H4 +DI / -DI with it. Inside it, every M15 / M5 / M1 reading turned to the D1 way - the pullback (the place in
the M15 / M5 range, the distance to the M15 / M5 EMA 20 / 50, RSI, Stochastic), the turn (the M5 / M1 last leg's way,
the M5 / M15 structure and break), the move of the last 15 / 60 minutes, the hour, the volume - by quintile (L1's edges
inside the phase), the D1 way's X first minus the other's, by moments and by each day's first moment, L1 and L2,
X = 10 and 5 U (`entry_tables.py`). An entry condition counts when it moves the same way in both halves by moments
and by first moments, >= 30 days a bin. The best one or two are then put together with the phase as one rule, run as
trades with the costs (the stop and the target X, model_trades' trade, one position, the learning parts first), and
the exam is read once for that frozen rule, week by week.
**The entry readings (07:23 Thai; `entry_tables.py`, tests `test_entry_tables.py` - the aligned flag and the turning by
hand, planted bugs 3 of 5, the other two equivalent: an unknown structure (9) times the way never equals 1, and a
missing D1 way is already out through the H1 condition; `out_entry_tables.txt`, `entry_tables.csv`).** Inside the
aligned phase, the D1 way comes first more often after a pullback against it on M5 / M15, in both halves, by moments
and by first moments: M15 MACD under its signal (turned) +0.113 / +0.197 at the lowest quintile against -0.010 /
+0.091 at the highest (10 U); price under the M5 EMA 50 +0.061 / +0.132 against +0.015 / +0.053; M5 / M15 RSI low,
M5 EMA 20 alike. Buy the M5 / M15 dip when D1, H4 and H1 point up (the mirror down).

## Bigger runs - written before it is computed (07:24 Thai; owner: "10 USD is very little - it runs that in 15 minutes; find a way")
The D1 / H4 / H1 alignment tells the way of a run of hours to days, not of 15 minutes. The same moments, the outcome
X up before X down (and the mirror) for X = 20, 30, 50 U within one day (1,440 M1 bars) and X = 50 U within three
days (`runpat_check.passages`, checked on 3,000 trades). Read: the aligned phase, the aligned phase after a pullback
(price under the M5 EMA 50 turned, L1's lowest two quintiles inside the phase), the rest of the running phase, and all
moments - the D1 way first minus against, by moments and by first moments, L1 and L2. Then as trades with the costs
(the stop and the target X), one position, the learning parts; the exam once for the frozen rule, week by week.
**Bigger runs, the result (07:25 Thai; `big_runs.py`, its passages re-checked on 800 one-day trades: 0 differences;
`out_big_runs.txt`, `big_runs.csv`) - kept as information only:** 20 / 30 / 50 U within a day and 50 U within three
days in the aligned phase: the D1 way's share 0.42-0.52 in L1 and 0.53-0.62 in L2 - L2 is gold's 2025 rise, L1 does not
follow; not steady.
**The owner, 07:24 Thai: "No - I mean a 10-USD run is very little, M15 does it easily"; "hold short, in fast, out
fast."** The owner's way: keep the 10-USD target, enter on M15, hold briefly.

## In fast, out fast: 10 U, a short hold - written before it is computed (07:25 Thai; `big_trades.py` with the owner's sizes)
The aligned phase after an M5 pullback (`big_trades.candidates`, tested by hand), a trade the D1 way at the next M1
open, the stop and the target 10 U, out at the last close after 15 / 30 / 60 / 120 minutes, the auditor's costs, one
position at a time. The hold: the highest min(R L1, R L2) of those positive in both learning parts; none -> the exam
is not read; else the exam once for it, week by week.
**The result (07:25 Thai; `out_fast_trades_learn.txt`):** 10 U, hold 15 / 30 / 60 / 120 minutes: L1 R -0.084 / -0.084 /
-0.089 / -0.107 (1.1-3.3 trades a weekday, all buys - every running D1 phase of 2023-24 rose), L2 -0.027 / -0.004 /
+0.028 / +0.048 (2.0-4.6 a weekday). No hold is positive in both parts: the exam is not read. With 15 minutes, 90 %
(L1) / 78 % (L2) of the trades end on time, short of both the target and the stop.
**How often does 10 USD come within minutes? (07:27 Thai; every library moment, either way first, from the next M1
open):**

| part (median price) | 10 USD within 15 / 30 / 60 / 120 minutes | 10 U scaled by price |
|---|---|---|
| L1 2023-11 .. 2024-12 (2,345) | 0.01 / 0.03 / 0.08 / 0.18 | 0.05 / 0.13 / 0.26 / 0.46 |
| L2 2025-01 .. 2026-04 (3,413) | 0.15 / 0.27 / 0.42 / 0.60 | 0.16 / 0.29 / 0.47 / 0.69 |
| the exam 2026-04 .. 10 (4,335) | 0.19 / 0.37 / 0.62 / 0.85 | 0.16 / 0.33 / 0.58 / 0.82 |

From a moment taken by the clock, 10 USD in 15 minutes happens about one time in five today. Gold does run 10 USD in
15 minutes easily - from the right moments: the work is to tell those moments (the burst about to start) from the
rest. Two separate questions: WHEN a 10-USD move is about to start (the volatility, the participation, the clock of
the big orders - the kind of thing that can be read ahead) and WHICH WAY (the D1 / H4 / H1 alignment, 2-7 points).

## The owner's trade: M15, 10 USD, three or four bars - written before it is computed (2026-10-19 07:33 Thai; owner: "I mean one M15 bar running already covers 10 USD - hold three or four bars")
Decisions at the M15 closes inside the owner's windows (the library's moments at minute 0 / 15 / 30 / 45). The trade:
the D1 way at the next M1 open, the target 10 USD and the stop 10 USD (fixed - today's gold), out at the last close
after 3 or 4 M15 bars (45 / 60 minutes), the auditor's costs, one position at a time. Learning on the latest months
before the exam (the owner's rule: the latest 12 months first): 2025-10-18 .. 2026-01-15 and 2026-01-16 .. 2026-04-17,
the two parts. Entries read: (A) the aligned phase (D1 running + the H1 structure + H4 DI with the D1 way); (B) A after
an M5 pullback (price under the M5 EMA 50 turned, at or below the 40th percentile inside the phase, here on these
months). Chosen: the entry x hold with the highest min(R part 1, R part 2) of those positive in both; none -> the exam
is not read; else the exam once, week by week (`m15_trades.py`).
**The result (07:34 Thai; `m15_trades.py`, tests `test_m15_trades.py` - the parts' edges, the M15 closes only, the
pullback cut by hand; `out_m15_trades.txt`):** (A) the aligned phase: 3 bars R -0.043 / -0.065, 4 bars -0.052 / -0.061
(4.4-5.5 trades a weekday); (B) + the M5 pullback: 3 bars +0.005 / -0.089, 4 bars -0.008 / -0.085 (1.5-2.5 a weekday).
None positive in both parts: the exam is not read. P1 (2025-10 .. 2026-01): most trades end on time (184 of 350) - the
entries are not where a 10-USD move starts; P2 (2026-01 .. 04): more stops than targets (144 / 123), the late-January
crash inside it. The owner, 07:33 Thai: "keep observing the way you are doing".

## When a 10-USD move is about to start - written before it is computed (07:36 Thai; `burst.py`)
At the M15 closes inside the owner's windows, P1 / P2 as above: does price move 10 USD (either way) within 1 / 3 M15
bars (15 / 45 minutes) from the next M1 open? Read by the readings that need no side: the volume against the same
minutes, the ATR of M5 / M15 / H1 / D1 against its median, the Bollinger width on M5 / M15 / H1, the size of the last
15 / 60 minutes' move, the minutes to / since the fixes, the COMEX open, the US data and the New York open, the hour,
the weekday, the D1 / H4 phase - by quintile (P1's edges), by moments and by each day's first moment, P1 and P2.
Then, among the moments that do move 10 USD, which way - read against the D1 / H4 / H1 alignment and the pullback.
**The result (07:35 Thai; `burst.py`, `out_burst.txt`, `burst.csv`):** 10 USD either way within 15 minutes of an M15
close: P1 0.190, P2 0.460; within 45 minutes 0.475 / 0.767. The clock of the big orders and the waking of the
volatility tell WHEN, the same way in both parts: within ~60 minutes of the New York open / the London PM fix / the US
data / the COMEX open, 10 USD in 15 minutes 0.35-0.40 (P1) and 0.63-0.70 (P2) against 0.08-0.18 / 0.37-0.47 far from
them; the M5 ATR against its median in the top quintile 0.36 / 0.68 against 0.11 / 0.30 at the bottom; the volume
against the same minutes 0.25 / 0.67 against 0.11 / 0.36. WHEN a 10-USD move comes is far easier to read than which
way.
**The owner's chart (07:34 Thai, M30, 4,150-4,200 since 16 Oct): "is 10 USD inside this frame?"** At the data's end
(2026-10-16): M15 ATR 4.9, median bar 6.4, 18 % of M15 bars span 10 USD; M30 ATR 9.1, median bar 9.0, 40 %; H1 ATR
14.8, 70 %. 10 USD is about one M30 bar - five of them fit in the owner's 50-USD frame.
**The owner, 07:35 Thai: "if trading with the trend meets obstacles, try the periods when it runs inside a range."**

## Inside a range - written before it is computed (07:36 Thai; `range_trades.py`)
The range phases: D1 back and forth (the 20-day efficiency <= 0.116, L1's lower tercile) or H4 sideways (the 30-bar
efficiency <= P1's lower tercile). The edge: the place in the M30 120-bar range (2.5 days - the owner's chart) at an
M15 close - <= 0.15 a buy, >= 0.85 a sell (back into the range). The trade: 10 USD target and stop, out after 3 / 4
M15 bars, the costs, one position at a time; also the same edge outside the range phases (the contrast). P1 / P2 as
before; chosen: the phase x hold with the highest min(R P1, R P2) of those positive in both; the exam once.
**The result (07:37 Thai; `range_trades.py`, test `test_range_trades.py`; `out_range_trades.txt`):** fading the M30
edges in a range phase - P1 R -0.046 .. -0.155, P2 -0.013 .. +0.047; outside the ranges -0.033 / -0.008. Not positive
in both parts: the exam is not read. P1 (Oct 2025 - Jan 2026) rose hard: 108 of 118 D1-back-and-forth edge trades
were sells into it, half ended on time.
**Which side, inside and outside the active hours (07:38 Thai; M15 closes, 10 USD within 15 / 45 minutes, the side's
share where one came first, P1 / P2, near the NY open / PM fix / US data / COMEX and elsewhere):** the D1 way, the
aligned D1 way, with / against the last 15 / 60 minutes, the M5 leg, the H1 structure, the dollar, the M15 break all
change sides between the parts; **only the fade of the M30 range edge is above half in all eight cells: 0.524 /
0.530 / 0.540 / 0.557 (15 min), 0.510 / 0.509 / 0.533 / 0.543 (45 min)** - the owner's range idea, 51-56 %, at the
costs' line (about 0.527 for a 1:1 10-USD trade). With the D1 way or against it, H4 alike: too few days to tell.
**The owner's H1 chart (07:36 Thai): "on 1H it almost always runs 10 USD".** 70 % of H1 bars span 10 USD (median 13.1)
- but a 13-USD bar often goes 8 down before 13 up: with a 10-USD stop the first 10 USD decides.

## Let the market show the side - written before it is computed (07:38 Thai; `straddle.py`)
At the M15 closes in the active hours (within 60 minutes of the NY open / PM fix / US data / COMEX), no side picked:
a buy stop b USD above and a sell stop b below the close (b = 3 / 5), the first one hit within 60 minutes is the trade
(filled at its level, plus the spread for a buy and the slippage), then the target 10 USD and the stop s (s = 5 / 10
USD) from the fill, out 60 minutes after the fill at the last close; the other order cancelled; the costs; one position
at a time. P1 / P2; chosen: the (b, s) with the highest min(R P1, R P2) of those positive in both; the exam once.
**The straddle, the result (07:39-07:42 Thai; `straddle.py` on M1 with both bounds, tests `test_straddle.py`;
`tick_straddle.py` on the real ticks, tests `test_tick_straddle.py` tick by tick - a dip before the fill does not stop
the buy, the first trigger wins, the stop fills with its gap, ticks before the moment unused; planted bugs 5 of 5).**
On M1 the bounds were too far apart to decide (b 5 / s 5: -0.173 / -0.511 from below, +0.048 / +0.074 from above - the
fill bar's low often came before the fill); the M1 "choice" (b 5, s 5) was not used. On the ticks, P1 / P2: b 3 s 5
-0.054 / -0.090; b 3 s 10 -0.029 / -0.053; **b 5 s 5 +0.021 / -0.083**; b 5 s 10 -0.030 / -0.017 (5-9 trades a
weekday). None positive in both: the exam is not read. In the active hours the first 3-5 USD push carries on to 10
USD before 5 / 10 against only 31-48 % of the time.
The owner (07:39-07:42 Thai): "count the tops and the lows on the focus timeframe and the larger ones"; "if it makes
an A-B-C-D-E it is likely to break anyway"; "try other timeframes too, M5, M15"; "then see which kind fits us".

## How do the ones who profit do it? Does gold carry on? - written before it is computed (2026-10-19 07:43 Thai; owner: "not 'that test loses, this one loses' - how do others make a profit? You have to find it")
Every trade tested this morning had the target equal to the stop and a short clock: it can only profit by choosing the
side right well over half the time. Traders who profit mostly do not; they cut a loser short and let a winner run
where the market carries on, and take quick profits where it turns back. So, gold's own character, measured: once
price has gone X USD from a moment, does it reach 2X (the same way) before coming back to where it started? X = 5,
10, 20 USD; from every M5 close inside the owner's windows (the present library), the first X within 4 hours, then
the race within the next 4 hours; by the hour (the active hours or not), the D1 phase, the way against D1 / the
aligned phase, P1 / P2 (the latest months) and the older halves L1 / L2. Above half: let it run (a trailing or a far
target pays); below half: take the profit early / trade the turn back.
**The result (07:44 Thai; `persist.py`, tests `test_persist.py` by hand - on to twice, back to the start, the mirror,
both ways in one bar / nothing, the touch bar not raced - planted bugs 4 of 4; `out_persist.txt`, `persist.csv`):** once
price has gone X USD, the share reaching 2X before back at the start, L1 / L2 / P1 / P2: X = 5 in the active hours
0.516 / 0.523 / 0.538 / 0.534 (the steadiest - above half in all four); quiet hours 0.523 / 0.499 / 0.483 / 0.508;
X = 10 all 0.517 / 0.510 / 0.494 / 0.480; X = 20 in a D1 back-and-forth phase 0.714 / 0.633 / 0.580 / 0.501. Gold
carries on a little after the first 5 USD in the active hours; nowhere strongly.

## If it does not run, give up - written before it is computed (2026-10-19 07:45 Thai; owner: "that is why I said timing matters: once in, we do not wait for a price that does not run - if we enter it must run; if it does not run, we surrender")
On the real ticks (2025-10-18 .. 2026-04-17, P1 / P2; the exam 2026-04-18 .. 10-14): decisions at the M5 and at the M15
closes in the active hours (within 60 minutes of the NY open / PM fix / US data / COMEX); the side (S1) the D1 way in
the aligned phase, (S2) the fade of the M30 range edge, (S3) the D1 way; a market entry at the first tick after the
close (a buy at the ask + 0.07, a sell at the bid - 0.07); **the surrender: unless price has gone Y USD our way within
K minutes, out at the tick at K** (K = 3 / 5, Y = 2 / 3; and none, for the contrast); once it has run, the target 10
USD (a limit) and the stop 10 USD (the first tick at / beyond, with its gap), out after 60 minutes; one position at a
time. Chosen: the highest min(R P1, R P2) of those positive in both; the exam once, week by week.
**The surrender, the result (07:49 Thai; `surrender.py`, tests `test_surrender.py` tick by tick - it ran then the
target, no run so out at 3 minutes, the same without the surrender wins, the stop first and a sell on the ask, a late
run still surrenders; planted bugs 4 of 5, the fifth equivalent - no tick is +10 and -10 at once; `out_surrender.txt`).**
P1 / P2: the aligned D1 way at M15 closes +0.056 / -0.234 without the surrender, **+0.113 / -0.205 (3 min / 2 USD),
+0.116 / -0.202 (3 / 3)** - the surrender lifts it in P1, P2 breaks it; the M30-edge fade at M5 closes -0.099 / -0.008
without, -0.074 / +0.015 (3 / 2); the D1 way alone negative everywhere. Nothing positive in both: the exam is not read.
Each side-rule pays in its own market: the D1 way in P1 (a rising, running D1), the fade in P2 (the crash and the wide
swings after it).
**The bursts (07:49 Thai; `burst_scan.py`, tests `test_burst_scan.py` - a clean run and its first minute, against
first is not clean, one bar reaching both is not clean, consecutive starts are one burst; planted bugs 4 of 4 after
the fourth test; `out_burst_scan.txt`):** 10 USD within 5 minutes with less than 3 against first: 2.0 a weekday in
2023-08 .. 2025-10, **60.1 in the latest learning months, 19.5 in the exam** - many times a day, as the owner sees.
By the Thai hour (latest months): 20:00-22:00 4.5-6.0 an hour, 08:00 4.1, 10:00-11:00 0.8-1.4. Before a burst the
last 30 minutes were already wide (median 1.56 M15 ATRs against 1.30 for every minute) and the volume up (1.33 against
1.00): bursts come out of an already busy market, not out of a quiet squeeze.

## The side by the phase - written before it is computed (07:49 Thai; `phase_switch.py`)
One position, the active hours, on the ticks: D1 running (20-day efficiency >= 0.264) and the aligned phase -> the D1
way; D1 back and forth (<= 0.116) at the M30 edge -> the fade; otherwise no trade. The surrender 3 minutes / 2 USD,
then 10 / 10, 60 minutes. Decisions at the M15 closes, and (a second row) at the M5 closes. Chosen: the one with the
higher min(R P1, R P2) if positive in both; the exam once.
**The result (07:50 Thai; `phase_switch.py`, test `test_phase_switch.py`; `out_phase_switch.txt`):** M15: P1 121 trades
(1.89 a weekday) R +0.097, USD +117, max DD 42; P2 129 trades R -0.132, USD -171. M5: +0.010 / -0.090. Not positive
in both: the exam is not read. Where the losses sit (M15, R by month): the D1 way Nov +2.42, Dec +4.10, **Jan -3.91
(the blow-off and the crash), Mar -4.94**; the fade Nov +2.22, Feb -1.54, **Mar -4.35**, Apr +1.71. The D1-way trades
lost in P2 when H1 was busy (the H1 ATR against its median in the top tercile: 40 trades -0.432; P1 the same tercile
+0.154). Few trades a month - the next step reads the January and March losers one by one.

## The trend readings lag - every turn is a loss (2026-10-19 08:54 Thai; owner: "are you reading signals that come too late? When price turns, by the time you notice you are trading against the trend"; "this way every turn is a guaranteed loss")
Checked on the phase switch's D1-way trades (M15): in P2 all 63 were entered while the H4 swing structure, and the
H1 and M15 120-bar ways, all still read "with" (`phase_switch_d1way_trades.parquet`) - the readings confirm the
trend until long after it has turned. In P1 the best D1-way trades were the ones taken while the last H1 / M15 leg ran
against the D1 way (a pullback): H1 leg against +0.281 (28 trades) vs with +0.041 (65); M15 leg against +0.185 (52)
vs +0.023 (41). Everything aligned at once = late. The losing ones came with a busy D1 (the D1 ATR against its median
>= 1.28: P2 -0.33 .. -0.77; < 1.28: P2 -0.026, P1 +0.143).
**Written before it is computed (`phase_switch.py` variant 'pull'):** the D1-way trade only on a pullback (the last
M15 leg against the D1 way) and only while D1 is calm (the D1 ATR against its median < 1.28 - P1 and P2's own lower
tercile cut from the trades above, so this is fitted on the learning parts and the exam must judge it); the fade
trades unchanged. M15 closes, the surrender 3 min / 2 USD. If positive in both parts: the exam once.
**The result (08:54 Thai; `out_phase_switch_pull.txt`; test `test_phase_switch.py` - the pullback variant by hand):**
M15: P1 49 trades (0.77 a weekday) R +0.113, max DD 30; P2 79 trades R -0.084 (13 of them D1-way trades); M5: +0.016 /
-0.087. Not positive in both: the exam is not read. The pullback-while-calm rule keeps P1's edge with fewer trades and
removes most P2 D1-way trades; what loses in P2 is now mostly the fade.

## Trade short, turn early, keep the big trend - written before it is computed (2026-10-19 08:55 Thai; owner: "correction: use the short way - find a fast reversal signal, trade the small timeframe, but do not drop the big trend, so the trade can be held far")
Part 1 (`pullback.py`): on M1 bars, at every M1 close (decisions only from closed bars):
- the big trend: H1 swing structure up (HH / HL) and the H4 structure not down (the mirror for down) - the faster
  swing readings, not the 20-day D1 way;
- the pullback against it: the highest high of the last 30 M1 bars is at least 1.0 M5 ATR above the lowest low of the
  last 10 M1 bars, and that low came after that high (the mirror for a down trend);
- the fast turn back: this M1 bar closes above the highest high of the 3 bars before it, and the pullback's low is
  within the last 10 bars;
- the trade: in at the next M1 open (a buy at the ask + 0.07), the stop 0.3 USD beyond the pullback's low (the risk R0
  between 2 and 8 USD, else no trade), the surrender (not +1 R0 within 5 minutes -> out), the target 3 R0, out after
  4 hours; the costs; one position at a time; on M1 the stop first when a bar reaches both.
Part 2 the trailing hold (instead of 3 R0); part 3 the ticks. P1 / P2 first; the exam only for a rule positive in both.
**The result (08:58 Thai; `pullback.py`, tests `test_pullback.py` - the pullback and the turn by hand, no trend / too
shallow / the down-trend mirror, a dip before the high is not a pullback, the turn must close above the 3 bars before,
the target, the surrender, the stop with its slippage, a bar reaching both is a stop, the risk range; planted bugs 7 of
7 after three tests were added; two wrong expectations of mine corrected; `out_pullback.txt`):** P1 1,871 trades (29.2
a weekday) R -0.099; P2 1,163 (17.6) R -0.032; 78 % surrendered, 4-8 % reached 3 R0. Far too many, not positive.
**Every loser drawn (09:00 Thai; owner: "capture the price structure with the entry, TP and SL lines for every losing
trade, the entry timeframe, all of them"; `loser_charts.py`, its levels by hand; `charts/pullback_losers_2026-04-13.html`,
published as https://claude.ai/artifact/PVhxGVLW2MaMN8ucx1ZSuL):** all 45 losers of 2026-04-13 .. 04-17 (of 1,841 in the
two parts). Read by eye: #1, #2, #12 are sells while the M15 bars beside them climb in plain HH / HL (the H1 / H4
swing reading still said down - the lag the owner named); #25 a buy into an M15 that made lower highs, surrendered just
before price rose; #38 a buy at the top of a small M1 bounce under a falling M15. The direction must come from the
timeframe right above the entry (M15) as it stands now, not from H1 / H4 swings confirmed long ago.

## No stop loss - is the account wiped? (2026-10-19 09:52 Thai; owner: "take the SL out, trade without a SL - I want to know whether the account gets wiped"; `no_sl.py`, tests `test_no_sl.py` by hand - a buy 20.37 against then the target, a sell's ask and the data's end, the wipe against the balance at each trade's start; `out_no_sl.txt`)
The short trade's entries (pullback.py), one at a time, 0.01 lot, no stop / surrender / time limit, out only at +10
USD, 2023-11 .. 2026-10 (the whole history: a risk question, nothing is chosen on it): **301 trades in 2.3 years (the
holds run up to 133 days); 40 % went 10 USD or more against before +10, 22 % 22 USD, 12 % 50 USD, 4.7 % 100 USD, the
worst 1,642 USD** - a buy at 5,585 on 2026-01-29 13:36 Thai, the top before the crash, still -1,421 at the data's end
(2026-10-16). Starting at 22 or 50 USD: **wiped on the first trade** (2023-11-03, 70 USD against before +10). From 100
USD up it survived only because 300 winners (+3,000 USD) came before the deep ones; the same trades in another order
need more than 1,642 USD a 0.01 lot to live through - and the broker stops out before equity reaches 0.

## The direction from M15 as it stands, the entry on M1, only when gold runs - written before it is computed (2026-10-19 09:53 Thai; owner: "OK, go back to it" - the plan: M15's current structure, the M1 turn after a pullback, only the hours gold runs, every loser drawn)
`pullback15.py`: the trend = the M15 swing structure at the M1 close (picture.struct_brk on the 3-ATR ZigZag of the
last 120 M15 bars, the swing still forming counted: +1 HH / HL, -1 LH / LL, else none) - instead of H1 / H4. The
signal and the trade as pullback.py (the M1 pullback >= 1 M5 ATR, the turn beyond the 3 bars before, the stop 0.3
beyond the pullback's extreme, the risk 2 .. 8 USD, the surrender at 5 minutes without +1 R0, the target 3 R0, out
after 4 hours, on M1 the stop first), only when the decision is within 60 minutes of the New York open / the London PM
fix / the US data / the COMEX open. P1 / P2 (2025-10-18 .. 2026-04-17); if positive in both: the exam once. Every loser
of the run drawn (`loser_charts.py`).
**The result (09:56 Thai; `pullback15.py`, tests `test_pullback15.py` - up / down structure on M15 by hand, the active
hours in their zones summer and winter, nothing after the moment changes the structure; planted bugs 4 of 4 after the
last test was added; two wrong expectations of mine corrected; `out_pullback15.txt`):** P1 337 trades (5.27 a weekday)
R -0.101; P2 161 (2.44) R -0.268; 6 % reached 3 R0, 64 % surrendered. Worse than with H1 / H4. Every loser drawn next.
**Every loser drawn (09:57 Thai):** P1 209 (https://claude.ai/artifact/XRP7WXNDZ2XdaPxW6sb1Qp), P2 113
(https://claude.ai/artifact/Sg6cwAv62hRdhD2wae8mmf). By eye: P2 #10 a buy in a sideways M15 after a spike - no run;
P2 #60 a sell right after a V-shaped M15 rally (the 3-ATR swings had not yet turned - the lag remains even on M15);
P1 #100 a buy in a choppy M15 of large spikes both ways, stopped after 45 minutes. The losers sit in sideways / choppy
M15 and just after V turns.
**The owner, 09:55 Thai: "it looks as if it is not learning at all - or are you learning, in case I misunderstand?"**
Answered with the running table of this session's rounds (learned -> changed -> result).

## Becoming an observer of the moment before the run - written before it is computed (2026-10-19 10:01 Thai; owner: "you must research and learn until you are an expert at observing price and catching the moment before it runs; bring in momentum or any other indicator if it helps")
Part 1 (`m1_features.py`): at every M1 close of the latest learning months (P1 / P2), only from closed bars: the speed
(the close's change over 1 / 3 / 5 / 15 minutes in M5 ATRs), the acceleration (the last 3 minutes' speed against the 3
before), the bar's range against its last 20, the volume of the last 1 / 3 minutes against the same minutes of the
previous 20 days, the bars in a row one way, the close beyond the last 15 / 60 minutes' high / low, M1 RSI(14), M1
MACD(12, 26, 9) histogram (line - signal) in M5 ATRs and its last change, the spread against its median, the
minutes to / since the US data / the NY open / the PM fix / the COMEX open, the M15 structure and the M15 efficiency.
The outcome, per bar and free of any catalogue: from the next M1 open, 10 USD up (or down) within 5 minutes with less
than 3 USD against first (`burst_scan.bursts`' per-bar test, before it merges the starts). Part 2 reads each one alone
(both parts, by moments and by first moments of the day); part 3 puts them together; part 4 the ticks and the drawings.
**Part 1 done (10:05 Thai; `m1_features.py`, tests `test_m1_features.py` - speed, bars in a row, breaks from the bars
before only, the volume against earlier days only (today would move the median 15 -> 20), and every reading unchanged
when all later bars are replaced by other prices; planted bugs 6 of 6 after the volume test was fixed; `loc.location_grouped`
equal to `loc.location` on 4,000 random moments; `out_m1_features.txt`):** 350,351 M1 closes (173,030 learning); a clean
10-USD run starting at the next open: up 0.0406, down 0.0498 a minute. The owner meanwhile: "trade at support /
resistance, never mid-price except a pullback"; "ignore noise signals"; "select the good signals and the setups with an
edge" (also in the memory).
**Part 2 - written before it is computed (`m1_lean.py`):** each reading's quintiles (P1's edges): the chance of a clean
run up / down next, by moments and by each day's first moment, P1 and P2. **Kept (not noise) only when the top or the
bottom quintile lifts the run one way to >= 1.5 x its base in both parts, the same way, with >= 30 days a bin.**
**Part 2, the result (10:06 Thai; `m1_lean.py`, test `test_m1_lean.py`; `out_m1_lean.txt`, `m1_lean.csv`).** Base a
minute: P1 up 0.012 / down 0.020, P2 0.068 / 0.078. Kept (an end quintile >= 1.5 x one way in both parts): the volume of
the last 1 / 3 minutes against the same minutes (top fifth: both ways 2-3 x), the place at the M15 range's low and near /
below the previous day's low (both ways ~2 x), a close below the last 60 minutes' low (a run up next ~2 x), far from
the H1 swing top above. **Noise, dropped:** speed and acceleration, RSI, MACD and its turn, bars in a row, the bar's
expansion, the 15-minute break, the spread, the clock, the hour, the M15 structure and efficiency, the H1 place, the
round numbers. The kept ones tell WHEN (at a level, when the volume comes), not which way.
**At the levels with the volume - bounce or break? (10:07 Thai; the share of the clean runs that go each way, P1 | P2):**
at support (the M15 range's low fifth, near / below the previous day's low, or below the 60-minute low) with the top
fifth of volume, the run goes DOWN 0.58-0.61 | 0.53-0.54 whether or not the last M1 bar turned up - gold breaks the
support more than it bounces; at resistance with the volume, the turn down 0.77 (44 days) | 0.48 - not steady; mid-price
with the volume down 0.71 | 0.56. Fast 10-USD runs go down more often than up in both parts (gold climbs and drops
fast): the side with the edge for a quick run is the sell after a support gives way.

## At a level with the volume: the break - written before it is computed (2026-10-19 10:11 Thai; owner: "do it"; "trade at support / resistance, never mid-price except a pullback"; "select the good signals and the setups where we have the edge"; 10:10 Thai: "draw only the losers whose reasons differ")
`sr_break.py`, at each M1 close from `m1_features.parquet` (closed bars only), the edges from P1's quintiles:
- support = the M15 range's low fifth (`m15_pos`), or the previous day's low near / below (`to_pdl` in its low
  fifth), or a close below the last 60 minutes' low; resistance = the mirrors (`m15_pos` / `to_pdh` in the top fifth,
  a close above the 60-minute high); the volume = `vol1` or `vol3` in the top fifth;
- support + the volume (and not resistance) -> SELL the break; resistance + the volume (and not support) -> BUY.
The trade on the real ticks (`surrender.trade`): a market entry at the first tick at / after the next M1 open (+0.07
slippage, the spread in the bid / ask), the target 10 USD, the stop S of {3, 5} USD, the surrender of {none, +2 USD
within 3 minutes, +3 within 5}, out after 30 minutes; one position at a time; at most 3 trades a UTC day (the first
three that can be taken); no entry in a UTC day's last 30 minutes (the day's ticks end). The sides {sells, buys,
both} x the hours {all, the active hours (60 minutes either side of the NY open / the PM fix / the US data / the
COMEX open)}: 36 settings, R = USD / S. Chosen by the smaller R of P1 / P2; the exam read once, only for the chosen
one, only if it is positive in both.
The losers, by reason (decided now): what came in the 60 minutes after the entry - **wrong way** (10 USD against
before 10 our way), **ran later** (10 our way first, after we were out), **no run** (neither) - x the M15 structure at
the entry against the side (**against** / **with** / **none**); the count of each reason and one drawn for each (the
loser nearest its reason's median USD).
**The result (10:20 Thai; `sr_break.py`, tests `test_sr_break.py` - support / resistance with the volume by hand (each
level alone, vol1 or vol3, mid-price none, both levels none), P1's edges, what came after (wrong way / ran later / no run,
a sell judged on the ask, nothing after 60 minutes), the reason, the day's trades (the entry at the next bar's open, one
at a time, 3 a day, not in the last 30 minutes); planted bugs 11 of 11 after two tests were tightened; `loser_charts`
one loser per reason by hand, planted bugs 4 of 4 after its test was fixed; `out_sr_break.txt`):** 31,725 signal
minutes (sell 18,160 / buy 13,565 of 173,030). **No setting is positive in both parts.** The parts disagree: P1 favours
the buys at all hours (stop 5, no surrender: R +0.116, 2.6 a weekday), P2 both sides in the active hours (stop 5, no
surrender: R +0.179, 2.3 a weekday) - the same setting is -0.271 / -0.253 in P1. Selling the support break alone: P1
-0.03 .. -0.32, P2 -0.25 .. +0.125. The best by the smaller part (both / active / stop 5 / surrender 3 min +2): P1 -0.058,
P2 +0.144. The 58-61 % down share of the clean runs at support did not carry: the clean runs are a small part of the
signal minutes, and the rest decide the trades.
**The losers by reason (that setting, 195 of 303 trades; one drawn for each of the 9 reasons, `charts/sr_break_reasons.html`):**
wrong way 119 (61 %), ran later 54 (28 %), no run 22 (11 %); the M15 structure does not separate them (wrong way R
-0.83 against / -0.68 with / -0.66 none; ran later is best against it, +1.07). By eye: entries after a 15-30 USD run
(#1, #2, #4, #7), the surrender cutting a run that came after a first bar against (#3, #5, #8), signals mid-range (#6,
#9). **Checked by numbers: "late" does not separate** - the winners had run as far before the entry (median 9-14 USD in
the last 15-60 minutes, P2) as the wrong-way losers. All readings at the entry, the winners against the wrong-way
losers: the only one apart the same way in both parts was the nearest round 50 (a round 50 ahead our way within 25
USD: R -0.02 .. -0.33; behind us: +0.065 / +0.486). **On all 31,725 signal minutes (M1, 10 our way before 5 against
in 30 minutes) the round-50 effect is gone** (P1 0.21 / 0.15 / 0.10 / 0.17 / 0.19 by the distance, P2 0.31 / 0.29 /
0.29 / 0.33 / 0.32): a few hundred trades showed a pattern the minutes do not have - not a rule, the exam not read.
Learned: at these moments (a level with the volume) 5 USD against comes first 53-70 % of the time within 30 minutes; 10
our way first 15-33 %. A level made by the move itself (the 60-minute low, the M15 range's low) is not a level price
has turned at before. Drawn: https://claude.ai/artifact/QRAzAdXBdvSiTLHaH5uarK (commit 0bf0861).

## The two-way sweep at the news - written before it is computed (2026-10-19 10:23 Thai; the owner on loser #1 of `charts/sr_break_reasons`, a buy at 21:13 Thai 2026-01-09 after the US jobs report: "to really buy, wait for the fake drop in the first minute - then it sweeps up, and then it comes down"; "that is the case of the fake break upward")
The owner's sequence: the first minute fakes one way (sweeps the lows), then price sweeps the other way through the
highs (a fake break up), then it comes down. Our break rule bought the second leg's top. `news_sweep.py`, part 1 the
description, on the real ticks (the mid price, (bid + ask) / 2, so the release's wide spread does not move it), P1 / P2
only: at each weekday's 08:30 and 10:00 New York minute, p0 = the last mid before it; the first leg = the side of the
first 3-USD move from p0 within the first 60 s; then which comes first within 15 minutes of the release: p0 + 10 USD
the first leg's way (**continued**) or p0 + 10 the other way (**faked**: the sweep), or neither; for a faked one, the
sweep's extreme in those 15 minutes and how far it comes back in the 15 minutes after that extreme, and whether it
crosses p0 again (**the third leg**). Split by the release's volume (the news minute's `vol1` >= 2: a release happened;
below: a quiet minute). Part 2 (only after part 1): the trade the owner described - in after the fake first leg, out at
the sweep, then the other side.
**Part 1, the result (10:29 Thai; `news_sweep.py`, tests `test_news_sweep.py` - the owner's case by hand (the fake drop,
the sweep up, back through p0), faked without the third leg, continued / neither / quiet, the first leg only within
60 s, p0 the tick before the release, the release minutes in New York time summer and winter, and 2026-01-09's shape:
a 14-USD first minute then the sweep; planted bugs 11 of 11 after three tests were added; `out_news_sweep.txt`,
`news_sweep.parquet`).** **Corrected before the result was used:** the first definition raced p0 +- 10 USD from the
release, so a first minute of more than 10 USD was "continued" - the owner's own 2026-01-09 example came out wrong. Now
the race starts after the first minute: a new extreme beyond the first minute's (continued) against 10 USD past p0 the
other way (faked); 2026-01-09 08:30 NY is faked (the sweep 18.6 USD at minute 10.4). The release marker (`vol1` >= 2)
caught only 5 releases (the same UTC minute is busy on most days) - not used.
| minute | part | days | first leg | continued | faked | quiet | faked: the sweep / its minute / back / third leg |
|---|---|---|---|---|---|---|---|
| 08:30 NY | P1 | 62 | up 17 / down 12 | 0.37 | 0.03 | 0.53 | 15.4 USD / 7.3 / 17.7 / 0.50 |
| 08:30 NY | P2 | 65 | up 22 / down 22 | 0.49 | 0.17 | 0.32 | 16.4 / 12.3 / 19.7 / 0.64 |
| 10:00 NY | P1 | 62 | up 17 / down 30 | 0.58 | 0.08 | 0.24 | 10.5 / 9.1 / 15.4 / 0.60 |
| 10:00 NY | P2 | 65 | up 30 / down 27 | 0.69 | 0.14 | 0.12 | 15.4 / 7.2 / 31.5 / 0.89 |
The owner's sequence is there (27 days in six months, about one a week): the sweep runs 10-52 USD past p0, peaks at
minutes 1-15, and mostly comes back through p0. The first minute alone does not mark it - a new extreme after the
first minute comes 3-5 x more often. What tells the fake at the end of the first minute is the next question - handed
to the trading-system developer (owner, 10:25 Thai: "research, write the findings as a prompt, make another session the
trading-system expert"; "and your job is to measure the system and the results"): `../DEV_PROMPT.md`.

## How sure is the level-break result? (2026-10-19 10:47 Thai; owner: "how confident are you about the support / resistance break?")
- **The code / the simulation:** the real ticks, hand tests, planted bugs 11 of 11. But a design flaw: "at most 3 a
  day" took the first three of the UTC day. In the all-hours settings the day's first signal falls at 07:00 Thai on 98
  of 154 days (median 07:00), so those settings traded the Asian open, not the moments meant. The cap should pick by
  quality, not by the clock.
- **The result's margin:** the best setting has 150 / 153 trades, R SD 0.92 / 1.39, and a 95 % range of -0.20 ..
  +0.09 (P1) and -0.08 .. +0.36 (P2). The data cannot tell 0 from +0.15 R: "not passed" holds, "it fails" does not.
- **The finding "gold breaks support more than it bounces" - corrected:** the count took every minute of a run, so one
  run counted many times.
  - Each clean run counted once at support with the volume: down 56 % in P1 (223 of 395 runs, 43 days) and 50 % in P2
    (1,139 of 2,268, 56 days). A lean in P1 only; in P2 the place and the volume alone do not tell the side.
  - All fast runs, counted once: down 57 % (P1), 51.5 % (P2).
  - The earlier 58-61 % / 53-54 % overstated it. Corrected in `../DEV_PROMPT.md` too.
- **What was NOT tested:** the owner's support / resistance - levels price has turned at before (swing levels,
  touches counted), the break confirmed or the fake break back inside, the stop beyond the level. The "support" here
  (the 30-hour M15 range's low fifth, near the previous day's low, below the 60-minute low) is mostly made by the move
  itself. That is Task B of the developer's prompt.

## Support / resistance from the larger timeframe - written before it is computed (2026-10-19 10:50 Thai; owner: "so what will you do about my rule - trade at the support / resistance of a timeframe larger than the one you trade on?"; 10:51 Thai: "do not make up numbers or data; answer only from the real candles and the real chart patterns")
The plan told the owner (a plan, not a finding):
- the zones come from H1 (main) and M15, plus the previous day's high / low;
- the direction comes from M15 as it stands;
- the entry is on M1, only at a zone: the bounce (a sweep through the zone that closes back inside) or the break (a
  close beyond it that holds);
- the stop comes from the structure, the target is the next zone of the larger timeframe, and the trade surrenders if
  it does not run.

The plan was written into `../DEV_PROMPT.md` Task B.

Step 1 (`zones.py`), the zones drawn on the real candles before any count:
- H1 swings are fractals with k = 2: a bar whose high (low) is the highest (lowest) of the 2 bars each side. Each is
  known only when the second bar after it closes.
- The swings of the last 120 H1 bars known at the moment are merged into zones (`foundation.merge_levels`, tol = 0.25 x
  H1 ATR(14)). Each zone keeps its touches (how many swings it merged) and its kind (tops = resistance, lows = support,
  both = a level that flipped).
- The moments come from a fixed rule, not picked by eye: on every 12th weekday of P1 / P2, the first time after the NY
  open (09:30 NY) that an M1 bar reaches within 0.1 x H1 ATR of a zone.
- At each moment two panels are drawn: the H1 of the last 5 days with the zones and their touch counts, and the M1 of 30
  minutes before to 60 minutes after with the zone.
- The owner confirms whether these are the levels meant. Only then are the touches counted (step 2: bounce / break /
  sweep back inside, each touch once, both parts).
**Step 1, drawn (10:53 Thai; `zones.py`, tests `test_zones.py`; `charts/zones_h1.html`, published as
https://claude.ai/artifact/QXTSqxMcvzBqg47Y4tkTZu).** The tests (5 passed):
- a swing is known only when the second bar after it closes;
- the merge keeps the kinds and gives the same levels as `merge_levels` on 60 random prices;
- the zones at a moment use only the swings known by then, from the 120-bar window, and change one nanosecond later;
- the first touch is within 0.1 x ATR, and nothing before it is taken;
- the zones are unchanged when every later bar is replaced.

Planted bugs: 8 of 9 caught. The ninth, keeping swings without 2 bars after them, changes nothing: `fractals` never
returns them.

The 11 days gave 9 moments; the other 2 had no touch within 3 hours of the open. Read on the real candles:
- **#3 (2025-11-21 21:30 Thai):** the touch at 4063.8, a zone of 5 swings, both tops and lows. M1 dipped to 4063 and
  rose to 4075 - it held.
- **#6 (2026-01-28 22:08 Thai):** a 50-USD M1 drop reached 5238.8 (1 swing) and rebounded to 5287 within the hour.
- **#1 (2025-10-20 20:30 Thai):** the touch at 4308.6 (1 swing, a low). Price fell through it to 4294 and came back up
  to 4330: a sweep below and back.
- **#5 (2026-01-12 21:32 Thai):** the top zone 4600.2 (2 swings). M1 dipped under it to 4586, then broke above to 4620.
- **#8 (2026-03-03 21:30 Thai, H1 ATR 58):** price fell through 5169.6 (3 swings), 5155.1 (4), 5128.9 (2), 5093.9 and
  5074.3 down to 5000 - no zone held in that fall.

**The problem seen on the charts:** 14-23 zones in five days, e.g. #3: 14 zones within about 180 USD. Price is near a
zone almost all the time, so "at a zone" barely selects. Before counting anything, ask the owner which of these are the
levels meant.
**The owner's pick (10:54 Thai, from the drawn zones):** all four kinds:
- zones of >= 2 swings, the strongest being >= 3 or flipped (tops and lows);
- the latest swing high above the price and the latest swing low below it;
- the previous day's high / low;
- the five-day high / low.

The zones of one swing that are not the latest swing are dropped.

**Step 1b - written before it is computed:**
- `zones.levels_at`: from the zones known at the moment, keep the four kinds, each labelled: "x3+ / flip", "x2",
  "last top" / "last low" (the latest known H1 swing above / below the price), "PDH" / "PDL" (the previous server day),
  "5d high" / "5d low" (the 120 complete H1 bars).
- The same 9 moments are redrawn with only these levels. The first touch is now a touch of one of them.
**Step 1b, drawn (10:58 Thai; tests `test_zones.py`, 8 passed: the four kinds by hand - a one-swing zone that is not the
latest dropped, a two-swing flip counted strong, a weaker level inside a stronger one's tolerance dropped, the latest
top / low (not the highest), the previous day from the last complete server day, the five days from complete bars - and
the levels read with the bar's open, not its close; planted bugs 8 of 8 in the level picker after the last test, 8 of 9
in the zones as before; republished at the same link).** 9-13 levels a moment, against 14-23 before. On the real candles:
- **#1 (2025-11-05 21:47 Thai):** M1 fell through 3974.1 (x2) to about 3965, just past the next level 3966.5 (x3+ /
  flip), turned up to 3983, and never reached 3961.3 (x2) below.
- **#4 (2026-01-12 21:32 Thai):** price went under 4600.2 (x2) to 4586, then up through it, and stopped at the 5d high
  4620.2.
- A range still leaves a cluster: in #4 there are 7 flip zones between 4441 and 4481.

**The owner, 10:57 Thai: "does it usually go past the support / resistance with the wick, make the low / high, but not
reach the next level, when it reverses?"**

**Step 2 - written before it is computed (`touches.py`):**
- **The touches:** every touch of the owner's levels in the active hours (60 minutes around the four events), P1 / P2,
  each counted once. A touch is the first M1 bar within 0.1 x H1 ATR of a level, with price at least 0.5 x H1 ATR away
  from it in the 60 minutes before. The side is where price came from: from above = a support test, from below = a
  resistance test.
- **What follows, within 60 M1 bars of the touch:**
  - **reversed:** 10 USD back to the approach side first;
  - **broke:** 10 USD beyond the level first;
  - **neither**;
  - a bar reaching both: ambiguous, left out.
- **For the reversed:** the overshoot (how far the extreme went beyond the level before the reversal, in USD and in H1
  ATRs; 0 = it turned short of the level), and whether that extreme reached the next owner's level beyond.
- **The split:** by part and by the level's kind; each day's count of touches shown.
- **The drawings:** the first two touches of each outcome in each part, drawn - the real candles first, then the counts.
**Step 2, the result (11:06 Thai; `touches.py`, tests `test_touches.py` - 9 passed, each by hand:
- a support that holds without a pierce;
- a wick 4.5 past, then the reversal;
- a resistance that breaks, and a bar reaching both left out;
- the touch bar can break but not reverse;
- neither;
- the first touch after price was away, the latest bar away counting;
- the next level past the touch's own place;
- how far past counts only up to the reversal.

Planted bugs 10 of 10 after two tests were added; one wrong expectation of mine corrected (the next level's gap is the
touch distance). Outputs: `out_touches.txt`, `touches.parquet`, drawn `charts/touches.html` =
https://claude.ai/artifact/ApKRhFx5KpJxegEEFuRvS8.)** Each touch counted once, in the active hours:

| | P1 | P2 |
|---|---|---|
| touches (days) | 404 (59) | 460 (63) |
| turned 10 USD back before going 10 past | 0.50 | 0.55 |
| ... of those, pierced the level first | 0.73 | 0.58 |
| ... how far past (USD), 50 / 75 / 90 % | 1.8 / 4.3 / 7.0 | 0.6 / 3.5 / 6.9 |
| ... the extreme reached the next level | 0.09 (the next a median 9.3 USD away) | 0.04 (22.7 away) |
| went 10 past first | 0.36 | 0.44 |
| ... then came 10 back within the 60 minutes (a deep sweep) | 21 of 146 (median 13.1 USD past, 90 % 17.8) | 94 of 201 (median 18.9, 90 % 35.1) |
| neither in 60 minutes | 0.14 | 0.01 |

**The owner's question answered from these counts:** yes. When gold turns at the owner's levels it mostly goes past the
level with the wick first (73 % / 58 % of the turns): half by under 1.8 / 0.6 USD, 90 % by under 7 USD. Its low / high
almost never reaches the next level (9 % / 4 %). In P2 many turns came after a deep sweep of 10+ USD (94 touches,
median 19 USD past).

By the level's kind, nothing is steady across the parts: in P1 the x3+ / flip zones broke less (0.29) than x2 (0.44);
in P2 both broke 0.42.

**On the drawn candles, a caution:**
- P1 #5: 2025-10-21 18:56 Thai, 4244.2 x3+ / flip, from above. It bounced to about 4256 (10 back: "reversed"), then
  crashed through to 4215 at 19:11.
- P2 #11: 2026-01-16 20:23 Thai, 4592.7 x2, from below. It dipped 10 to about 4582.7, then broke up to 4608.

"Reversed" is the first 10-USD reaction, not the end of the move.

## The owner on the drawn touches: not entry points - an entry needs a chart pattern (2026-10-19 11:16 Thai)
**The owner:** "what I see in the pictures is not a place to enter at all - the price is very steep, there is no price
structure; I don't know what criterion you used to judge that this is a moment to enter."

**The answer:** the touch charts were measurements, not entries. The only rule was "price reached the level after
being away"; no entry rule had been applied. Both pages are now labelled "Not entry points", in the code too.

**The owner's entry rule, from the answers:**
- every structure offered: a sweep then the small-TF turn, a base at the level, W / M at the level;
- "chart patterns of all kinds - at least M1 must show a chart pattern, and so must every TF used to enter";
- "at least it must show an inverted H&S - something like this around the price level";
- "look at all TFs together, the smallest is M1 ... enter on a TF, exit on that same TF".

The rule is in the memory and in `../DEV_PROMPT.md` as Task P, first: a pattern detector on M1 (with M5 / M15
agreeing) at the owner's H1 levels and after the news fake. The entry is at the neckline / the base's edge, the stop
past the pattern's extreme, and the exit on the same TF. Twelve catches are drawn by a written rule for the owner's
confirmation before any count.

**The developer's A1, measured (11:16 Thai):**
- its tests re-run: 28 + 4 passed;
- its planted bugs re-run: 57 of 57 caught;
- its look-ahead check re-run: 1064 of 1064 equal, with power;
- its numbers re-derived against `news_sweep.parquet`: the same 27 faked minutes and all 254 labels under the
  researcher's rules; 2026-01-09 is faked in all 4 variants;
- my own 9 planted bugs: 5 caught, 1 that cannot happen, 3 missed (the tie side, `swept_pre` at equality on the up
  side, a partial third leg), sent back to it.

**Its two changes are accepted.** The first leg's side is the first minute's larger move: chart #9, 2026-03-03 22:00
Thai, is a 26.8-USD continuation that the first rule called a fake. "Continued" needs a new extreme 3 USD past the
first minute's.

**The A1 counts** (faked / continued / neither / quiet, every weekday's minute):

| Part | 08:30 NY | 10:00 NY |
|---|---|---|
| P1 | 3 / 13 / 13 / 33 | 7 / 29 / 11 / 15 |
| P2 | 10 / 26 / 8 / 21 | 10 / 41 / 6 / 8 |

## The developer's Task P (chart patterns at the level) - measured (2026-10-19 12:08 Thai)
**What it built:** `../dev/patterns.py`, with rules written in `DEV_LOG.md` before the first run:
- a causal ATR ZigZag (2 x the TF's ATR);
- inverse H&S / H&S, W / M (including a second low that sweeps the first), a sweep then a higher low / lower high, and
  a base then its break;
- each pattern only at the owner's H1 levels (`zones.levels_at`) or at the news first-minute extreme;
- M1 / M5 agreement attached as a label;
- a height cap of 4 x its TF's ATR.

It found 1,893 catches in P1 / P2, with no outcomes computed.

**Measured:**
- its tests re-run: 60 + 9 passed;
- my own 13 planted bugs in `patterns.py` were all caught: a flat neckline, the head without its margin, a sweep of any
  depth, a sweep without the close back, a base broken by a wick, no height cap, the farthest level winning, and
  others;
- its 71 planted bugs re-run: running, none missed so far;
- the catches' times all lie in 2025-10-20 .. 2026-04-17;
- independently on the M1 bars: the entry equals the next bar's open on 1,475 of 1,476. The other is a decision at 20:55
  UTC, the last bar before the daily break, with no next bar, so its entry is empty, which is correct;
- the decision bar's close is beyond the trigger on all of them, and the stop is past the extreme on all of them;
- none of my files was edited, and nothing was committed by it.

**The 12 catches, read on the real candles (`charts/p_patterns/`, republished for the owner as
https://claude.ai/artifact/XGjQkQxYpA7vLGgxNZL8aP):**
- **Recognisable at the level:**
  - #1, inverse H&S at 4217.43;
  - #2, W at the previous day's low;
  - #4, base break up above 4168.42;
  - #8, base break down at 5393.02;
  - #9, M5 W at 4156.94;
  - #11, the owner's NFP case: a W whose second low (the release spike 4459) swept the first.
- **Doubtful:**
  - On the crash nights the patterns are huge (#5 H&S, stop 51.66 USD; #7, stop 64.06; #12, 36.13).
  - In #5 and #7 the breakout is 43-44 USD below the level, which is not "at the level".
  - #3 and #11 have the next level only about 2.5 USD past the entry.

The owner confirms first. Then come the counts, and the developer's 8 questions (the swing size, the sweep allowance
against the measured ~7 USD, a base's tightness, M5 against as a filter, the stop when patterns overlap, close next
levels, the bars' "known" time).
**The developer's 71 planted bugs re-run (12:46 Thai): 71 of 71 caught.**

**The owner, 12:46 Thai:** "run the backtest with the pictures you got, and you will know whether it is a quality setup
- or else wait for the price structure to reveal itself and enter then; see whether that makes a better profit."

Sent to the developer as checkpoint P2, with its rules to be written before computing:
- every catch traded on the ticks, P1 / P2, one position at a time;
- **A**, entry at the breakout;
- **B**, wait for the structure to confirm: a higher low above the pattern's extreme after the breakout, then a break
  of the post-breakout high; mirrored for sells;
- the exit on the same TF: its structure turning, the next level when more than one risk away, the stop on the ticks,
  a time limit;
- the costs: ticks + 0.07, plus 0.5 / 1 / 2 USD at the news;
- the report: per part, by family / TF / level kind / M5 agreement / crash nights, with the 95 % range of R;
- the losers by reason, one drawn each.
**13:24 Thai:**
- **The pattern look-ahead check re-run:** 2343 of 2343 equal, with power, PASSED.
- **The developer stopped mid-P2 on an API rate limit**, after it had written the P2 rules in `../dev/DEV_LOG.md`.
- **The rules, read and accepted as written:**
  - every catch, one position at a time, the smallest risk first at one moment, no daily cap;
  - A at the breakout;
  - B: a pullback of at least 1 x the entry TF's ATR from the post-breakout high, then a close above that frozen high,
    within 30 bars, with no trade if the pattern's extreme is reached first; stop B1 under the pullback low, B2 the
    pattern's own;
  - the exits on the entry TF: the stop on the ticks, the next level when more than 1 risk away, a close past the last
    confirmed ZigZag swing, 60 bars, before a tick gap of more than 30 minutes;
  - the costs: ticks + 0.07, plus 0.5 / 1 / 2 at the news;
  - judged by the smaller R of P1 / P2.
- **One fix asked:** its header time was ahead of the clock.
- **The owner:** "let the subagent carry on" - it was resumed.

## The developer's P2 - the pattern catches as trades, A against B (measured 2026-10-19 14:05 Thai)
**Its result (`../dev/p2_trades.py`, `p2_trades.parquet`, `DEV_LOG.md`; ticks, P1 / P2, one at a time, no cap):**

| | A P1 | A P2 | B1 P1 | B1 P2 | B2 P1 | B2 P2 |
|---|---|---|---|---|---|---|
| trades (a weekday) | 522 (8.2) | 565 (8.6) | 382 (6.0) | 364 (5.5) | 352 (5.5) | 348 (5.3) |
| win % | 35.8 | 35.8 | 34.8 | 32.1 | 38.6 | 38.2 |
| R (95 % range) | -0.047 (-0.14..+0.05) | -0.045 (-0.14..+0.05) | -0.043 (-0.18..+0.09) | -0.082 (-0.22..+0.06) | -0.026 (-0.11..+0.06) | -0.014 (-0.10..+0.07) |
| USD | -78.9 | -301.8 | -114.8 | -500.4 | -67.9 | +48.1 |

- **The owner's question:** waiting for the structure helps a little. B2 (wait, the pattern's own stop) is best by
  0.02-0.03 R. Nothing is positive in both parts or near +0.15.
- **Leads, not results** (picked from 108 cells, checked by my own recomputation):
  - B2, the H&S family: +0.047 / +0.149 (29 / 25 trades);
  - B2, the M5 entries: +0.066 / +0.117 (62 / 71);
  - M1 negative in every variant;
  - the sweep-then-turn negative everywhere (B2 -0.142 / -0.209);
  - W / M is 70 % of the trades, at -0.034 / +0.016.
- **The losers (B2):** wrong way 0.44 / 0.46, no run 0.49 / 0.42, ran later 0.08 / 0.12.
- **Read on the 9 drawn losers:**
  - B entries came 9-13 USD past the level (#2, #3);
  - the structure exit fired on one M1 spike (#8) and gave back a 1-risk gain (#9);
  - a stop just under the W's lows was swept, then price rose (#4);
  - a sell against M5's rise at the 5-day high (#6);
  - an exit before a 50-USD fall (#7).

**Measured:**
- its tests re-run: 87 + 11 passed;
- my own 8 planted bugs in `p2_trades.py`: 7 caught. The missed one, the M5 hold as 60 minutes, is a test gap only:
  every real trade's limit is right (M1 60 minutes, M5 300);
- **my independent check (`verify_p2.py`, imports nothing of the developer's):**
  - every metric is equal in all 6 cells;
  - 0 entries before a previous exit;
  - 60 of 60 trades re-derived from the raw ticks agree;
  - the structure exits re-read with `fingerprint.zigzag` agree 1244 of 1244. The first run gave 273 of 1244 - **my
    own error**: fingerprint's ZZ_K is 3, the developer's rule is 2 x ATR. Fixed, the cause written in the code;
- the family / TF splits recomputed by me: equal;
- the tick files' time is `datetime64[ms, UTC]`: my reader converts it. The developer's own checker had first read it
  as ns, and fixed that.

Published with the 9 losers: https://claude.ai/artifact/LLCw1sB92SgZNxVWVPYjhQ.
**The developer's P2 planted bugs re-run (14:00 Thai):** the trade code 57 of 57 caught; its checker 17 of 17.

**The owner, 21:51 Thai (by `date -u`; I first wrote 14:02 without reading the clock): "start" - Task P3 sent to the developer, every change on B2, one at a time:**
1. refuse a B entry too far past the level, with the yardstick taken from the pattern itself;
2. the exit on the entry TF, but turned by the pattern's own invalidation, and break-even after +1 risk then trailed
   by the entry TF's swings - each alone and together;
3. measure the leads' paths (H&S, M5 entries; MAE / MFE and their minutes) against the rest, then one rule;
4. the sweep-then-turn with M5 turned too, or an M5 pattern at the same level;
5. the same report, the second computation, 20 trades a variant from the raw ticks, and the losers by reason.

It also adds a hand test for the M5 time limit.

## Today's market, looked at on the owner's request (2026-10-19 22:05 Thai; owner: "gold tried to test 4200, could not, and has fallen"; "open MT5 and load the data")
- **The data:** read-only from the MT5 terminal (the FBS demo login, no orders), with the same terminal checked by
  `app.cli doctor` (0 failures).
- **An open item found:** `scripts/download_history.py` (rates_range) stored nothing after Friday 2026-10-17 03:54 Thai
  even with the market open. `rates_from_pos` returned today's bars, so the last 4,000 M1 bars were read that way
  (server time - 3 h; the offset verified by doctor) into the scratchpad only. The stored history was not changed.
- **Monday 19 Oct, Thai time:**
  - the open: 05:05 at 4166.91;
  - the attempts: highs 4185.92 / 4187.63 (06:00-07:00) and 4186.18 / 4186.51 (12:00-13:00), then **4190.25 at 14:33**,
    the day's high, 10 USD short of 4200;
  - then a fall: 4167 (16:00), 4161 (18:00), 4143.37 (20:00), the low 4142.74 at 21:48; 4146.5 at 22:03.
- **The owner's H1 levels known at 14:33** (`zones.levels_at`, H1 ATR 12.2): 4199.62 x2, 4191.42 x2, 4186.98 x2;
  4178.35 / 4166.86 / 4161.82 / 4155.17 x3+ / flip; 4174.30 / 4143.99 x2; PDL 4147.21. The high sat in the 4191.42
  zone.
- **The developer's detector on today's bars** (`patterns.TF.scan` + `at_level`, not `locate`, which keeps to the
  learning parts):
  - **M1 sell at 14:40:** an M whose second high (4190.25) swept the first, at 4191.42. The neckline 4184.74 broke, and
    the next M1 open was 4183.84. It went 0.51 against at most, +10 by 14:59, +40 by 20:47, +41.10 at 21:48.
  - **M5 buy at 14:10:** a W whose second low swept the first, at 4174.30, bought at 4186.22 just under the top. At
    best +4.03, then -43.48.
  - These are bars, not ticks (no spread), and one day: a picture, not a result. Today is after the exam window and is
    not used to design anything.
- **Published:** https://claude.ai/artifact/3QrKA2bdgMYSBMUt1jXTZ4.

## The owner's own narrow windows, and P2 inside them (2026-10-19 22:14 Thai; owner: "that is almost the whole day - I said narrower before")
**The owner's words, found in the session transcripts:**
- 2026-10-17 17:01 Thai: "the Asian market, mostly 7-9 o'clock Thai, often makes a small fake move before going the
  big way; the New York market is usually volatile at the open, plus another 1-2 hours";
- `docs/OWNER_GOALS.md`: "the Asia, London and New York opens; important releases".

The 20-a-day snap table in `docs/OWN_SETUP.md` is wider than what the owner said.

**P2's trades inside them** (the developer's `p2_trades.parquet`, my split; the windows from the owner's words before
any result):

| B2 | P1 R (n, win) | P2 R (n, win) |
|---|---|---|
| Asia 07-09 Thai | +0.092 (40, 0.45) | +0.203 (35, 0.43) |
| NY open 09:30 NY + 2 h (20:30-22:30 Thai in summer) | -0.072 (41) | -0.059 (47) |
| London open, the first hour (the width is MY assumption) | -0.082 (16) | -0.233 (18) |
| the rest of the day | -0.034 (255) | -0.020 (248) |

- At the breakout (A), Asia gives -0.026 / -0.013. Waiting for the structure is what pays in Asia. That fits the
  owner's "a small fake move first, then the big way".
- Asia + B2 is positive in both parts at about 0.6 trades a weekday: a lead on few trades, not a result.
- NY open + 2 h loses in both parts.
**The owner, 22:15 Thai: "London is 13:00-14:00, plus or minus a little from there if it is running."** B2 at
13:00-14:00 Thai: +0.076 / +0.074 (21 / 17 trades); A: +0.042 / +0.219. With 30 minutes either side (my width): B2
-0.023 / +0.148. The same hour tied to London's clock (07:00-08:00 London): B2 -0.158 / -0.058. The owner's Thai-clock
hour is what pays.

**B2 in the owner's Asia 07-09 + London 13-14 Thai:**

| | P1 | P2 |
|---|---|---|
| trades (a weekday) | 61 (0.95) | 52 (0.79) |
| win | 0.410 | 0.462 |
| R (95 % range) | +0.087 (-0.14..+0.32) | +0.161 (-0.06..+0.39) |
| USD | -2.2 | +306.9 |

- R is positive in both parts. P2 is above the goal, P1 is not.
- About 1 trade a weekday, against the goal of 2-3.
- The NY open + 2 h still loses.
- The windows came from the owner's words before any result, so they are not fitted. They are tested here on trades
  the developer made with every hour allowed.
**The owner, 22:18 Thai:** "that is why I said: trade only the windows I gave; outside them, the lowest priority -
unless the setup is really clean and clear."

What follows from it (in the memory and in `../DEV_PROMPT.md` as Task P4, after P3):
- the core rule is B2 only in Asia 07-09 / London 13-14 / the NY open + 1-2 h (Thai clock);
- outside the windows there is no trade until the owner defines "really clean" on real charts;
- the NY window's loss is to be explained and its conditions changed, the window kept;
- a rule that reaches +0.15 in both parts is frozen for the one exam read.

## Today's formations, counted with the owner (2026-10-19 22:3x Thai)
**The owner, on their M1 chart** with boxes at the 07:00 top, the 12:00 top, the 14:45-17:45 slide and the 17:46-18:16
V + retest: "how many highs / lows did it make today; if we catch the timing, how many trades; believe me, every day
has chances like this, sideways or trending".

**Measured** (a fixed 10-USD ZigZag on the real M1 bars; the first counter had a bug - one wide bar's own high and low
both counted as turns, 472-974 "legs" on crash days - fixed so a turn needs a later bar, and hand-checked):
- **2026-10-19:** 15 turns, 14 legs of 10+ USD; about 4-5 of them in the owner's windows.
- **P1 + P2, 127 days:** at least 5 legs a day; the 10 % / median / 90 % are 16 / 39 / 137; the calmest months
  (Nov-Dec) have a median of 19-23.

**The rough count of formations** (by eye from the owner's chart + the swing points): about 11.
- tops: M 06:30-07:05, M 11:30-12:30, a triple top with the last top sweeping (12:57-14:33);
- bottoms: a wide W to 08:26, W / higher low 13:32, V 17:46, a base after 20:47;
- continuation: a descending channel broken at 17:20, a failed retest at 18:16, the NY-open fake leg then the drop.

About 5-6 of them are in the owner's windows. **The owner:** "that's it - and there are triple tops and channel
breaks too".

**Consequence:** the detector must work on swings of the trade's size (10+ USD legs), not on 2 x M1-ATR micro-swings,
and must cover the owner's whole set. That is Task P5 in `../DEV_PROMPT.md`, queued after P3 and P4. The day is a
shape check only: it lies after the data end and is not used for outcomes.

## The system audit by a second agent (2026-10-19 22:41 Thai; owner: "try it, nothing to lose; if it works keep it"; "have the agents look and fix together, with care, and with correct test references")
- **The scenario planning** (a picture in formation -> its completions, each with a trigger / stop / target; enter
  when the chart reveals one, in the owner's windows) is added to the developer's P5.
- **The history download bug, confirmed.** A second read-only run of `download_history.py` stored M1 through
  2026-10-19 15:40 UTC (22:40 Thai). The first run had stopped at Friday 03:54 Thai, so the bot terminal had not
  synced Monday's history until `copy_rates_from_pos` was called. The downloader does not check that it reached the
  latest bar.
- **The earlier audit already covers some of it** (`../auditor/notes.md`):
  - the M1 OHLC equals the ticks' bid OHLC in 100 % of 359k minutes;
  - the "both in one bar = stop" rule moves results within +-0.01 R and changed no verdict;
  - the costs were checked against the ticks.
- **My checks today:**
  - **both ZigZags** handle one wide bar as one turn, confirmed on the next bar;
  - **the B2 trades** were re-derived from the raw ticks (60 / 60).
- **The auditor:** a second agent was started with `../AUDIT_PROMPT.md`. It audits the nine shared building blocks
  (data, larger-TF bars against MT5's own bars, indicators, swings, simulators, costs, parts / windows / DST, metrics,
  anything untested). Each one gets hand tests, planted bugs, a second source and PASS / FAIL. Fixes come only with a
  failing-then-passing test. The developer's files are never edited; findings there are relayed. The download bug
  comes first.

## Reading the chart with the owner, live (2026-10-19 22:42-23:00 Thai; owner: "I am inviting you to look at the picture together")
**The picture** (real M1 bars, read-only from MT5):
- after the 20:35-20:47 fall to 4143.37, a 2-hour base on the Fibo 50 % (about 4142);
- the highs fell: 4155.32 (21:00), 4150.43, 4148.12, 4147.98, 4144.69;
- the floor held at 4142.7-4143.4;
- the M1 ATR shrank from 3.14 at the fall to 1.48.

What came next:
- the floor gave way slowly: M1 closes under 4142 from 22:50, a low of 4139.58 at 22:55;
- by 22:56 price was back at 4142.62, a retest from below, without the drive of 20:35.

**The H1 and M30, measured:** the highs fell since 14:00 (H1: 4190, 4180, 4173, 4172, 4177 the retest, 4170, 4167,
4155, 4150) and so did the lows (4173 ... 4162, 4159, 4143, 4142). The structure is LH / LL on every TF up to H1.

**The owner's own trade reading (22:59 Thai):** "the shape on every TF up to 1H - I would enter and wait right away, in
the consolidation zone, with the SL above 4160." What it teaches:
- **When every TF up to H1 agrees, the owner enters early** - inside the consolidation, before the break. A base
  under falling highs on all TFs is read as continuation.
- **The stop goes where the picture would be wrong:**
  - above 4160, the 61.8 % zone, over the base's highs (4155) and below the H1 lower high 4167;
  - not a fixed few USD;
  - about 17-18 USD of risk from about 4142.
- **The target:** the owner's red box toward Fibo 38.2 / 23.6. Not stated as a price; asked.

**Our tested rules do the opposite on both counts:**
- B2 waits for a confirmation after the break;
- the stops sat just past a small pattern (P2: wrong way or no run in about 90 % of the losers).

**Candidate rule to measure (the developer, after P5):** "all TFs up to H1 in LH / LL (or HH / HL) + a base under
the falling highs (or over the rising lows) at a level, in the owner's windows -> enter inside the base; the stop past
the structure that would have to break (the base's top / the last H1 lower high side); the target the next zone".

## Setup OWN V3 - the owner's playbook, handed to a second developer (2026-10-19 23:05 Thai; owner: "from now on, do whatever it takes so that everything learned makes our setup profitable, plus what we learned from reading the chart today")
**The owner on trade 4:** "the target is 23.6, the SL 4180" - the first stop about 3 USD over the failed retest's high
4177.06 (about 11 USD of risk from 4169), the target the next Fibonacci zone. The details are in
`docs/OWNER_TRADING.md`.

**Three agents work in parallel; the measurer checks each:**
- **The first developer** (`../dev/`): P3 -> P4 (B2 only in the owner's windows) -> P5 items 1-4 (the owner's pattern
  set on trade-size swings, importing the second developer's swing module).
- **The second developer** (`../dev2/`, brief `../DEV2_PROMPT.md`) builds the owner's playbook as testable rules:
  - V3-1: trade-size swings; the structure per TF up to H1; the range box, the trendline, the Fibonacci levels; a shape
    check on 2026-10-19;
  - V3-2: the four entries in the owner's windows (break and retest; the aligned consolidation; the fake break at a
    range edge; the fake first leg at an open), with the stops past the structure and the owner's trailing / next-zone
    exits;
  - V3-3: scenario planning;
  - V3-4: one frozen rule for the single exam read.
- **The auditor** (`../audit2/`, brief `../AUDIT_PROMPT.md`): the nine shared building blocks, fixes with
  failing-then-passing tests.

**The evidence the work starts from** (all measured):
- entries cause about 90 % of the losses;
- the owner's Asia / London windows +0.087 / +0.161 R under B2, the NY open + 2 h negative;
- at least 5 legs of 10+ USD on every learning day;
- the formations live on trade-size swings;
- turns at a level overshoot by under about 7 USD in 90 %.

## The team, and the first developer's P3 / P4 / P5a measured (2026-10-19 23:08 Thai; owner: "add one more agent to consult and find the way to profit"; "divide the duties and talk well")
**The team** (`../TEAM.md`):
- the measurer / coordinator;
- the first developer (`dev/`, patterns at levels);
- the second developer (`dev2/`, the owner's playbook V3 and the shared trade-size swings);
- the auditor (`audit2/`);
- the strategist (`strategist/`, `../STRATEGIST_PROMPT.md`: the review, the ranked proposals, what to stop).

Each role writes only in its own folder, every report and request goes through the measurer, and every report has one
shape.

**The first developer's P3** (B2 with one change at a time; ticks; R P1 / P2):

| Setting | R P1 / P2 |
|---|---|
| B2 | -0.025 / -0.009 |
| L (no late entry) | -0.048 / +0.007 |
| Xa (the exit on the pattern's invalidation) | -0.037 / -0.033 |
| Xb (break-even + trail) | -0.037 / -0.035 |
| Xab | -0.037 / -0.037 |
| ST (the sweep-turn with M5 turned) | -0.024 / -0.008 |
| LEAD (H&S / M5 only) | -0.047 / +0.078 |

- None is positive in both parts.
- Inside B2's own stream the late entries are worse. As a stream, refusing them frees the position for worse
  replacements: judge filters on a fixed candidate set next.
- The -271.88 trade follows the rules: the M5 M's breakout came 157 USD past the trigger.
- Risk > 100 USD: 6-7 trades a setting, -61 .. -345 USD. A risk cap in H1 ATRs is next.
- Its second program: 1,008 / 1,008 metrics, 140 / 140 trades from the raw ticks, 0 overlaps.

**P4 - B2 in the owner's windows (ticks, the 60-s fill):**

| Window | R P1 / P2 | Trades |
|---|---|---|
| all windows (W) | -0.024 / +0.036 | 115 / 109 |
| Asia | +0.074 / +0.182 | 41 / 38 |
| London | -0.052 / +0.012 | |
| NY | -0.090 / -0.066 | |
| WN (NY without 10:00-10:30, a lead from about 25 cells) | +0.004 / +0.070 | |

- NY 10:00-10:30, right after the 10:00 data minute, is -0.298 / -0.208.
- My earlier split of P2's all-day stream said London +0.076 / +0.074. With the stream kept to the windows and the
  60-s fill, London is -0.052 / +0.012. The windows-only stream is the honest figure.

**P5 (items 1-3):** the owner's pattern set coded on 0.3 x H1-ATR swings.
- 12,192 catches, 64 % of them base breaks: too loose.
- The shape check on 2026-10-19 found 4 of 11 (the 07:16 M, the wide W, the channel, the NY fake leg).
- All 7 misses come from the same cause: about 3.7-USD inner swings split the owner's 10-USD legs. That waits for dev2's
  V3-1 swings.

**Measured by me:**
- its 11 test files re-run: 136 passed;
- P4 recomputed by my own code: every number equal, every W / WN entry inside my reading of the windows.

**Next:**
- relayed to dev2: the first developer needs dev2's swing interface;
- the first developer, while waiting: filters on a fixed candidate set, a pre-registered risk cap in H1 ATRs, a tighter
  base rule (P5a).

**23:11 Thai - the first developer paused** (owner: "should we stop and wait? otherwise whatever is built will be
tested and lose anyway"). No more tests on the old micro-swing structure (B2 filters, the risk cap, the base rule).
The second developer's V3-1 (the trade-size swings and the structure on every TF up to H1) is the critical path.

The first developer resumes on it:
- P5 on the new swings;
- an independent second implementation of the structure reading, to cross-check V3-1.

The auditor (data, simulators) and the strategist (the review) go on: they do not depend on the structure.

**23:13 Thai - the owner: "focus on whether what was built from the ideas I shared gives the right result - not only
unit tests showing there are no errors."**

Tests prove the code does what it was written to do; they do not prove it reads the chart as the owner does. Every
component built from the owner's ideas now also gets acceptance checks against the owner's own cases, written into
`../DEV2_PROMPT.md` "Acceptance":
- the structure reader must reproduce the owner's reading of 2026-10-19: the 15 turns, the range, LH / LL from 14:33,
  the break at 17:20, the retest at 18:15;
- the entries must find the owner's trade 4 (a sell at about 4169, the stop about 4180, the target the Fibo 23.6), the
  triple-top sell and the NY fake-leg sell;
- found / missed / extra are listed with reasons;
- rule-picked samples are drawn for the owner to accept or reject.

"Matches the owner" and "tests pass" are reported apart; a component is done only with both. The first developer
stopped cleanly at P5a: its rules were written, `p5a_filters.py` was untested and left out.

## The strategist's review (2026-10-19 23:43 Thai; `../strategist/PROPOSALS.md`; quick checks on M1 with the team's cost model, the leads re-run on ticks)
**Why it does not pay yet:**
- **R1: the M1 / M5 pattern triggers carry no direction, and context filters cannot add it.** Five readings (the H1 /
  M15 structure, the 4-h move, the day so far, the H4 EMA-50) split B2 / W without a steady sign.
- **R2: the bar cannot see +0.15 at these counts.** A true +0.15 passes "both parts >= +0.15" only 23-25 % of the
  time. With about 300 settings, a false pass somewhere is 84-86 % likely. About 110-116 trades a part are needed to
  exclude 0 at +0.15.
- **R3: the regimes change.** ADR20 medians: about 30 USD (2023-24), 43 (2024-25), 84 (P1), 172 (P2). The leads of P1
  / P2 lose in the older years:
  - the 13:00-Thai opening-range break is positive in 18 / 18 settings (P1) and 17 / 18 (P2), but 1 / 18 and 0 / 18 in
    the two older years;
  - the reclaim in the owner's windows is +0.31 / +0.31, but -0.16 / -0.24 in the older years.
- **R4: break-and-retest on the levels everyone sees starts from -0.221 / -0.390.** The broken level is usually
  reclaimed.
- **Cleared:** the costs (1.2-4.7 % of R), R against USD, and the Asia window (both sides pay).

**The proposals, in its rank order:**
1. the 13:00-Thai opening-range break: ticks +0.206 / +0.120, 59 / 60 trades;
2. the reclaim of a level everyone sees, in the owner's windows: ticks +0.312 / +0.310, 19 / 22;
3. measure break-and-retest against its base rate;
4. a season reading in every frozen rule, plus a monthly walk-forward pick;
5. the judging: at most 5 pre-written hypotheses a round, the pooled mean with its 95 % range, neighbouring settings
   that agree, no leads under 40 trades;
6. the NY window: stand aside, except a data-minute straddle: +0.459 / +0.114, fragile at +1 USD of slippage;
7. prefer tight patterns: the smallest-risk third beats the largest in all four cells.

**What to stop:** context filters on the M1 / M5 pattern stream, leads from small cells, symmetric "which way first"
studies, NY-open pattern trades as they are, the 1-minute follow-the-news rule.

**Measured by me so far:** its tests (5 passed); its exam guard (a row filter plus asserts in `slib.py`). Its two key
scripts (`orb_ticks.py`, `retest.py`) are being re-run.

**Done with its findings:** proposals 2, 3 and the judging went into `../DEV2_PROMPT.md` V3-2.

**Its questions:**
- the older history 2023-10 .. 2025-10 as a regime check: yes, it is before the exam, for checks only, never to fit;
- the owner's real spreads and fills: ask the owner;
- whether 08:30 NY is a window: the owner listed important releases among the moments; to confirm;
- whether the 13:00-Thai first 15 minutes is the owner's London: ask the owner.
**The re-run (23:46 Thai), equal to the strategist's numbers:**

| Rule | P1 R (95 %) | P2 R (95 %) | Trades |
|---|---|---|---|
| `orb_ticks.py`, the 13:00-Thai opening-range break | +0.206 (-0.04..+0.47) | +0.120 (-0.14..+0.38) | 59 / 60 |
| the reclaim in the owner's windows | +0.312 | +0.310 | 19 / 22 |

`retest.py` P2, all hours: -0.390 (47 trades).

**The first developer resumed on Task D** (`../DEV_PROMPT.md`; it needs no swings):
- D1: the 13:00-Thai opening-range break, with one pre-written H1-level change, the older years and a season reading;
- D2: the NY data-minute straddle, with the slippage sensitivity.

`TEAM.md`: the first developer works on Task D.

## The owner's framework, measured - written before it is computed (2026-10-20 12:08 Thai)
**The owner (about 12:05 Thai):**
- "find the trend in M15-1H, then use M1-M5 to find the entry - so a big trend or a sideways market does not matter
  much, we enter and exit on the small TF";
- "in a day, if it is truly a trend, it usually runs one way; pullbacks / bounces are not far, and our SL is at the
  small-TF level anyway";
- "the daily chart tells which side has the edge";
- "an open usually runs in its first 30 minutes to 1 hour; NY tends to run up to 4 hours after its open, sometimes
  choppy for the first 1-2 hours before the real run";
- "your interpretation is wrong... be strict about the goal and the rules, flexible in the method".

(The time was first written here as 00:05 Thai without reading the clock; the clock said 12:06.)

**Study 1 (`framework.py`, P1 / P2, the server days):**
- **The D1 bias at a day's start,** from closed D1 bars only: +1 when the last D1 close is above its EMA20 and the
  EMA20 rose over 5 days, -1 when mirrored, else none.
- **Per day with a bias, measured in the bias's direction:**
  - the day's net move;
  - its furthest excursion;
  - the deepest pullback against the bias from the running extreme (bar extremes);
  - the share of days that close the bias's way.
- **The same for the days against the bias,** and the pullback depth on the days that ran 20+ USD the bias's way.

**Study 2 (the same script):** the NY open (09:30 NY, DST-aware) to +4 h, in 30-minute buckets:
- each bucket's move the bias's way;
- the |move|, the range and the efficiency (|net| / path);
- the share of days whose first 2 h are choppy (efficiency < 0.3) and whose next 2 h run 10+ USD the bias's way.

The same for the Asia (07:00 Thai) and London (13:00 Thai) first 60 minutes, in 15-minute buckets.
**The result (12:10 Thai; `framework.py`, tests `test_framework.py` 3 passed - the bias needs the close beyond a rising
/ falling EMA20, the deepest pullback from the running extreme both ways, the efficiency; planted bugs 5 of 5; one
wrong expectation of mine corrected - a flat run under the average turns the EMA down, so -1 was right;
`out_framework.txt`):**

**Study 1, the EMA20 D1 bias (my proxy for "the daily chart tells the side"):**

| | P1 | P2 |
|---|---|---|
| days with a bias | 58 (50 buy / 8 sell) | 56 (40 / 16) |
| closed the bias's way | 0.48 | 0.54 |
| the day's net the bias's way, median | -3.4 USD | +6.8 |
| the furthest the bias's way / against, median | 36.3 / 29.4 | 59.6 / 51.0 |
| the deepest pullback from the running extreme, median (75 %) | 51.3 (77.3) | 100.2 (158.4) |

**This proxy does not tell the day's side, and the whole-day pullbacks are deep.** That is not the owner's "trend day":
- the proxy may not be what the owner reads on D1;
- a whole-day pullback mixes trend days with reversal days.

Next: other D1 readings (the last D1 candle, D1 swing structure, the close within the previous day's range), and the
pullbacks measured after a window opens with the M15-H1 trend agreeing.

**Study 2, the NY open to +4 h, the move the bias's way per 30 minutes (mean):**
- P1: -0.9, -0.8, +0.0, -0.0, +1.5, -0.1, +0.2, -1.2;
- P2: -5.4, -7.2, +0.7, +0.3, +2.7, +1.1, -3.7, -1.7.

In P2 the first hour ran against the D1 bias by about 12.6 USD on average, and +1-2.5 h ran a little with it. That
fits the owner's "choppy / against first, the real run later", but it is small and noisy.

The |move| is largest in the first 30 minutes (median 8.9 / 14.2 USD) and shrinks after.

My pre-registered "choppy" test (the first 2 h's close-to-close efficiency < 0.3) marks 98-100 % of days as choppy.
**The threshold was wrong for M1 closes; that test says nothing.**

**Asia 07:00 / London 13:00, the first 60 minutes, the bias's way per 15 minutes:** small (|mean| <= 2.6). The |move|
median of the first 15 minutes is 3.3 / 6.4 (Asia) and 2.8 / 5.6 (London).

**Step 2 - written before it was computed (12:11 Thai) and run (12:13 Thai; `framework2.py`, tests in
`test_framework.py` 5 passed - the first passage with a bar reaching both counted against, the sell on the lows, the
trend sign's warm-up; planted bugs 4 of 4 after one test was added; `out_framework2.txt`, `framework2.parquet`).**

**The question:** at each window's open, with the M15-H1 trend (the proxy: the close against a rising / falling
EMA50, both agreeing) and three D1 readings (EMA20, the last candle, 3 days), does price go 10 USD the trend's way
before X against, within the window's span (Asia / London 60 min, NY 240 min)?

**What it shows** (small cells, 6-40 days):
- **Entering at the open price with a small stop fails.**
  - With 3 USD: the 10 first in 0.10-0.38, the stop first in 0.50-0.88.
  - With 5 USD: 0.14-0.60.
  - Only NY with a 10-USD stop gets the 10 first in about 0.6 (P1 agree 0.65, P2 agree 0.61).
- **The D1 readings (EMA / candle / 3-day) do not separate** steadily: against-D1 NY in P2 was 0.69 / 0.73.
- **The sizes:** NY moves big within 4 h (MFE median 22-48 USD, MAE 13-33). Asia / London 60 min: MFE 4-15, MAE
  3-18.

**Conclusion for the design:**
- The entry cannot be "at the window's open in the trend's direction". It must be the entry TF's own turn (the end of
  a pullback / the owner's pattern), with the stop at that turn's extreme.
- The side needs the structure reader (V3-1), not EMA proxies.

**The owner (12:12 Thai):**
- "the side: D1 - you can read it, 1H -> 1D already has a trend";
- "the entry is M1-M15: write down that we enter with these 3 TFs; which one per trade is chosen by the volatility and
  the opportunity - low volatility M1, higher M15 - so it fits the TP / SL we plan";
- "what I share is what I see, not guaranteed right; your job is to research the opportunities and the probabilities
  and turn them into a design for the developer".

Turned into `../DEV2_PROMPT.md` "V3 design".

## The system audit, measured and committed (2026-10-20 12:21 Thai; `../audit2/AUDIT.md`, commit f9163e0)
**Nine shared building blocks were audited; four faults were found and fixed,** each with a test that failed before
and passes after:
1. **The history download (app):** it stored nothing after Friday on 2026-10-19. It now checks that it reached the
   terminal's newest bar.
2. **The ZigZag start-up:** one wide early bar could become two turns. Fixed in `fingerprint.py`. The developer
   applied the same one-line fix (`hi_i != lo_i`) to `dev/patterns.py`; 0 of its pivots change.
3. **The midnight cut:** `surrender.run` / `tick_straddle.run` ended a trade open at midnight UTC. 0 current trades
   change. It was a trap for late-UTC work such as Asia 07:00 Thai = 00:00 UTC.
4. **The max drawdown** left out the starting balance in 20 summaries. Two drawdowns move, by +0.4 and +1.6 USD.

**No learning-part R or win % changes.**

**PASS:**
- the OLD / NEW merge;
- `plib.load`, with a note: it returns the exam rows to every caller;
- UTC through the DST weeks: 59,363 minutes equal to the ticks;
- the larger-TF bars against MT5's own H1 / H4 / D1: max difference 0;
- `avail`;
- the indicators;
- the parts / windows / events;
- the costs: the formula against the first tick, -0.005 USD.

**Measured by me:** its tests (92 passed + 1 xfail, a question); the app unit (14 passed); ruff / mypy / bandit on the
app file (clean); the precursors suite (339 passed in 5:19, without the matplotlib-only test).

**Its questions, answered:**
- "win" = pnl > 0 after costs; `wf.weekly` gets changed;
- a trade's window is judged by its entry time, with the sensitivity reported (B2 Asia P1: +0.092 by entry time,
  +0.004 by decision time - a fragility);
- the downloader stores closed bars only (a second app fix);
- a `plib.load_learning()` that stops at the exam;
- dev2's `swings.py` audited after V3-1.

## The owner's answers and the independent PLAN-1 check (2026-10-20 12:52 Thai)

**The owner answered the three open questions (12:5x Thai):**
- "London 13-14" is the 15-minute opening-range break, 13:00-13:14 Thai (as PLAN-1 has it).
- The real account's gold spread is 20-30 points (0.20-0.30 USD); the tick spread (0.20-0.27) is the cost as it is.
- NY 08:30 is one of the owner's windows.

**The agents restarted** at about 12:46 Thai (the owner opened the limit): dev1 row 38, dev2 V3-1, the strategist row 39,
the auditor items 1 / 4 then dev2's `swings.py`.

**The auditor's item 3 measured and committed** (eeca5a9): the downloader keeps closed bars only. 20 tests passed;
ruff, mypy, bandit clean; my two planted bugs (`<` for `<=`; the cut skipped) failed 3 and 10 tests.

**My independent re-derivation of PLAN-1 from the raw ticks** (`check_plan1.py`, written from the frozen text, own
loaders / ATR / fills; `out_check_plan1.txt`), against `combo_trades_slip0.parquet`:
- London ORB (0.07 slip): 119 / 119 trades in the same minute, |dR| max 0.0000. P1 +0.206, P2 +0.120.
- NY straddle (slip 0): 100 / 100 trades in the same minute; 4 differ by more than 0.01 R, all stops in P2
  (2026-02-18, 03-19, 03-20, 03-31): stored -1.000 .. -1.006, mine -1.012 .. -1.056. Re-running the strategist's own
  `run_trade` on today's ticks gives my numbers, so **`news_follow_trades.parquet` is stale** (its stops booked at the
  stop price). Mine: P1 +0.467, P2 +0.119. Told dev1: plan1.py re-simulates the straddle from the ticks.
- Asia B2: 79 trades checked on the ticks (the entry and exit against the ticks, pnl, risk, R, no tick beyond the stop
  or at the target before another exit): 0 faults.

## Three deliverables measured (2026-10-20 13:20-13:40 Thai)
- **dev2 V3-1** (commit 4a10c58): 26 tests passed; its 46 planted bugs caught; mine 10 / 12 by the unit tests. The two
  misses are test gaps (`known_at` one bar ahead, `running()` including the pivot bar); the first is caught by its
  look-ahead run (8148 of 8428 readings equal, FAILED). The auditor's independent audit: PASS. Acceptance on 2026-10-19:
  15 / 15 turns, the box, LH / LL on M5-M30, the failed retest; missed the top-test count (11 vs about 7), H1 LH / LL
  (the 18:00 H1 bar holds both the retest high and the new low) and the 17:20 acceptance (17:45). `swings.LIVE` points
  at an old session's scratchpad: switch it to `data/history` (now updated to 2026-10-20 12:59 Thai).
- **The auditor, items 1 / 4** (03dd71f): 145 passed + 2 xfailed; mine 4 / 5 (the miss is an equivalent mutant). Only
  win shares move (205 of 240 cells up, 0 down); no R changes.
- **The strategist, row 39** (36cceda): rows 42-44. My own tick loop re-derives the RT_25-opp lead 85 / 87 exactly.
- **dev1** stopped on the session limit at about 13:18 Thai (reset 17:30 Thai) with `plan1.py` + `test_plan1.py` written
  and the first runs stored; not reported, not measured. Its open question: the CHECKLIST's P1-only weight variant has
  Asia-trend + NY-sideways for slip 0 by its own rule, the text has them the other way round for +1 USD.

## dev1's PLAN-1 runner measured (2026-10-20 17:10 Thai)
- **Correction:** the 4 NY stops I called stale (12:52 Thai) are not stale. I compared my slippage-0 straddle with the
  stored 0.07-slippage file; the straddle's stop sits 8 USD from the fill, so the 0.07 moves the stop too and another
  tick stops the trade (dev1: on 03-19 the ask 4613.10 touches a stop at 4613.10, not one at 4613.17).
- **Measured:** `test_plan1.py` 19 passed; its planted bugs 40 / 40; mine 7 / 7 in memory (`plant_plan1.py`); at
  slippage 0 its trades equal my independent derivation (`check_plan1_runner.py`): London 119 / 119 and NY 100 / 100
  with |dR| 0.0000, Asia B2 79 trades with 0 faults on the ticks, the weighted R recomputed the same.
- **Spread only, slippage 0:** unweighted +0.249 / +0.137; by mechanism +0.337 / +0.188; from P1 (Asia trend, NY
  sideways - the rule's result; the CHECKLIST text had NY sideways + mixed, which is the +1 USD result) +0.288 / +0.147.
- **The exam read** (`plan1.py --exam`) failed at 17:08 Thai with a MemoryError while three agents ran (3.4 of 15.8 GB
  free) before any output: no exam number was seen. It is re-run once the agents' runs finish.

## The owner's answers on the structure reading (2026-10-20 17:2x-17:3x Thai)
- Entries outside the windows and rules that pay mainly in the present: "flexible within reason" (inside / outside the
  windows reported apart).
- The owner leaves the counting to the measurer ("you have more data; my job is ideas and confirmation"). Top test =
  a visit to the box's top quarter after price left it by at least S: 5 on 2026-10-19 (06:29, 09:10, 11:53, 12:39,
  13:58 Thai).
- "To read H1, zoom into the smaller TF when you want to measure": every TF's structure is read with its own swing
  size on the M1 path (primary); the candle-bar reading is the secondary variant. On 10-19 the H1 size on the M1 path
  gives 14:33 H 4190.25, 17:46 L 4162.21, 18:16 H 4177.06 (LH), down from 18:58 Thai. Relayed to dev2 for V3-2.

## The PLAN-1 exam read (2026-10-20 17:35 Thai; once, by the measurer)
The first attempt (17:08) died with a MemoryError before any output; the second ran with one agent working.
`dev/out_plan1_exam_s0_x0.txt`: 330 trades (2.54 a weekday), 1 dropped for overlap.

| | P1 | P2 | exam |
|---|---|---|---|
| PLAN-1 unweighted | +0.249 | +0.137 | **+0.129** (-0.007..+0.265), +344.87 USD, DD 108.12 |
| by mechanism | +0.337 | +0.188 | +0.117, +215.52 USD |
| from P1 | +0.288 | +0.147 | +0.126, +283.47 USD |
| NY straddle | +0.467 | +0.119 | +0.285 (101) |
| Asia B2 | +0.081 | +0.186 | +0.105 (108) |
| London ORB | +0.213 | +0.124 | +0.023 (122) |

- Verdict: PARTIAL (positive in all three periods, below +0.15 in P2 and the exam). Worst week 2026-09-07 (-50.38 USD);
  weeks with R > 0: 14 of 26.
- The state weights lowered the exam result: the states' meaning per piece moved (Asia B2 in a trend: P1 -0.070, exam
  +0.376; NY sideways: P1 < 0, exam -0.098 but NY mixed +0.422).
- Re-derived by the measurer (`out_check_plan1_exam.txt`): London 122 / 122 and NY 101 / 101 trades with |dR| 0.0000,
  Asia B2 108 trades with 0 faults on the ticks.
- Next: the NY straddle is the steady piece; London ORB faded in the exam; the strategist's own-result switch (row 45)
  is the next candidate for the weights, judged walk-forward with N fixed in advance.

## SW-20, the own-result switch - written before computing (2026-10-20 17:40 Thai; owner: "do it")
**The rule (fixed now, not tuned):** each piece keeps trading on paper; a trade is taken for real only when at least 20
of the piece's earlier paper trades have exited before its entry and the mean R of the last 20 of them is > 0. N = 20
was the strategist's first setting (row 45); 40 / 60 are not used.

**The judge: years no switch study has seen.** The strategist's streams ORB (13:00-Thai), RC_win (#23) and RT_opp (#43)
on M1 (spread x 0.01 + 0.08, as row 45) in Y1 2020-10-18 .. 2021-10-18, Y2 2021-10-18 .. 2022-10-18 and Y3
2022-10-18 .. 2023-10-18 (the old store), each read once, with the paper record warmed from the start of the store.
- **Pass:** the three streams together, switched, summed R >= 0 in each of Y1 / Y2 / Y3, and R per traded trade >= 0
  pooled over the three years.
- Reported beside it: always-on R per stream and year, the trades kept, and the share kept.

**PLAN-1's pieces** (Asia B2, NY straddle) have no ticks before 2025-10, so SW-20 on them is reported over P1 .. exam as
a description only: the exam was already read for PLAN-1 (row 46), so it is not a test there.

## SW-20 read on the unseen years (2026-10-20 18:04 Thai; run by the measurer from the strategist's code)
The strategist stopped on the session limit (reset 22:00 Thai) with `streams.py` / `sw20.py` written; 7 tests passed,
its planted bugs 5 / 5; `sw20.py check` reproduced O1 exactly (250 / 339 / 241 events, |dR| 0). Run once:
- the three together, switched: Y1 0 trades (the M1 store starts 2021-09-01, not 2020-09: Y1 is 1.5 months), Y2 -12.8 R
  (175 trades, -0.073), Y3 -8.8 R (215, -0.041); always-on Y2 -70.0 / Y3 -48.5 R. **FAIL** (CHECKLIST row 47).
- My own switch on its trades equals its `real` column on all 1292.
- Lesson: the switch only cuts a losing stream's loss; it does not make the leads pay in years where they do not.
  Where the edge comes from in 2025-10 .. now is still open.

## Why does the NY 08:30 straddle hold? - written before computing (2026-10-20 18:13 Thai; owner: "do it")
The piece (PLAN-1's NY straddle, `dev/plan1.py`, slippage 0) is the only one positive in all three periods
(+0.467 / +0.119 / +0.285). Its trades: `dev/plan1_every_{learn,exam}_s0_x0.parquet`. The exam was read already, so
every split below is a description of P1 / P2 / exam, not a test; a split is a lead only if it holds the same sign in
all three. Splits, fixed now:
1. **The day:** a scheduled 08:30 release in `app/news/us_releases.csv` (CPI, NFP, PPI, PCE, GDP) / a Thursday without
   one (the weekly jobless claims, every Thursday 08:30) / any other day.
2. **The side against gold's D1 direction:** the sign of the last closed D1 close minus the close 20 D1 bars before.
3. **The weekday.**
4. **When the gain is made:** each trade's R at +5 / +10 / +15 / +20 / +30 minutes from the fill (the bid for a buy,
   the ask for a sell, on the ticks), and its best (MFE) and worst (MAE) R within 30 minutes.
5. **The exit:** time vs stop.
**The result (18:15 Thai; `ny_study.py`, `out_ny_study.txt`; sums checked: P1 13.8 + 1.7 + 3.6 = 19.1 = 41 x 0.467,
exam -5.5 + 21.9 + 12.3 = 28.7):**

| Split (trades, R) | P1 | P2 | exam |
|---|---|---|---|
| release day (CPI / NFP / PPI / PCE / GDP) | 8, +0.219 | 12, +0.101 | 24, +0.913 |
| Thursday without a release (claims) | 7, +0.517 | 12, -0.452 | 15, +0.820 |
| any other day | 26, +0.530 | 35, +0.321 | 62, -0.088 |
| against gold's D1 direction | 23, +0.744 | 34, +0.012 | 51, +0.289 |
| with it | 18, +0.113 | 25, +0.264 | 50, +0.280 |
| mean R at +5 / +15 / +30 min | +0.15 / +0.34 / +0.47 | +0.10 / +0.09 / +0.12 | +0.16 / +0.24 / +0.29 |

- **Only the release days keep one sign in all three periods** (+0.219 / +0.101 / +0.913), on few trades in P1 / P2;
  the plain days paid in P1 / P2 and lost in the exam; Thursday flips. The D1 direction does not separate.
- **The gain grows with the hold:** R at +30 min is the highest in every period, so an earlier time exit would not
  help. Half the trades reach +1 R within 30 minutes (median MFE +0.90 .. +1.13 R), 24-49 % are stopped.
- **Next, a real out-of-sample test:** the straddle on release days in 2021-09 .. 2025-09 (four years no study of it
  has seen; M1 bars with the M1 spread, since there are no ticks), and a +1 R target variant, both written before the
  run.

## NS-1: the 08:30 straddle on release days, 2021-09 .. 2025-10 on M1 - written before computing (2026-10-20 18:19 Thai)
No study of the straddle has used these years. There are no ticks before 2025-10, so it runs on MT5's M1 bid bars with
the ask = bid + the bar's spread x 0.01 + 0.08 (row 45's old-year cost model).
- **Days:** the 08:30 rows of `app/news/us_releases.csv` (CPI, NFP, PPI, PCE, GDP) from 2021-09-01 to 2025-10-17;
  beside them every other weekday, for comparison.
- **The orders:** from the close of the 08:29-NY bar (bid c, ask c + s): a buy stop at the ask + 2, a sell stop at the
  bid - 2, live in the 08:30 bar only. The fill: the trigger price, or the bar's open if it gapped past it. If the
  08:30 bar reaches both, the day counts at the worse of the two sides (and the count is reported).
- **The trade:** stop 8 USD from the fill, checked from the 08:30 bar on (the trigger bar included: conservative); a
  buy's stop on the bid low, a sell's on the ask high (high + s), at the stop or the bar's open past it. Out at the open
  of the 09:00 bar (bid for a buy, ask for a sell). R = pnl / 8.
- **Variant T1:** a +1 R target as a limit; a bar reaching both the stop and the target counts as the stop.
- **Calibration first:** the same M1 simulation on P1 / P2 release days, compared with the tick trades (`dev/plan1.py`).
- **Pass (hold 30 min, release days):** R per trade >= +0.15 pooled over the four years, and > 0 in at least 3 of the
  4 years (Oct .. Sep). Read once.
**NS-1 read once (18:18 Thai; `ns1.py`, tests 10 passed, planted bugs 7 / 7; `out_ns1_run.txt`, `out_ns1_calib.txt`):**

| Release days, hold 30 min (M1) | 2021-22 | 2022-23 | 2023-24 | 2024-25 | pooled |
|---|---|---|---|---|---|
| trades, R | 40, +0.185 | 50, +0.248 | 50, +0.128 | 46, +0.095 | 186, **+0.164** |
| other days | 33, +0.007 | 50, -0.005 | 57, -0.030 | 63, -0.002 | 216, -0.026 |
| T1 (+1 R target), release days | +0.050 | +0.055 | +0.043 | +0.094 | +0.060 |

- **By the written line it passes** (+0.164 pooled, positive in 4 of 4 years), and the release / other split is clear in
  every year: the edge is the release, not the clock.
- **But the calibration says M1 flatters release days:** on the 20 P1 / P2 release days M1 gives +0.341 against the
  ticks' +0.148 (bias +0.193; the other days -0.027). The fill is the cause: on a release the price jumps several USD in
  one tick, a stop order fills past the jump, and an M1 bar cannot show it (2026-02-11: M1 +1.97 R, ticks +0.84 R).
  With that bias the old years would sit near 0. **Verdict: not trusted - OPEN until the old release days are re-run on
  ticks** (MT5 `copy_ticks_range` for 08:25-09:05 NY on about 186 days; it downloads whole months into the terminal's
  Bases, so it needs the owner's go-ahead and the free-disk guard).
- The +1 R target is worse in every year: let the release run the 30 minutes.

**NS-1 on the old ticks - written before computing (2026-10-20 18:59 Thai; owner's go-ahead 18:33 "do it"):** MT5 holds
gold ticks back to 2021 (`copy_ticks_from` / `copy_ticks_range` with datetimes; the gateway's `ticks_range` now fails
with "Call failed" on every date - an app item to fix). `fetch_release_ticks.py` saves 08:20-09:05 NY of each release
day to `data/ticks_old/XAUUSD` (checked: a fetched 2026-01-09 window equals the stored tick day, 18,869 / 18,869).
`ns1_ticks.py` runs PLAN-1's straddle rule on them with the measurer's own simulator (`check_plan1.manage`, equal to
dev1's on 219 / 219 trades). The pass line is NS-1's: pooled >= +0.15 and > 0 in at least 3 of the 4 years. Read once.
**NS-1 on the old ticks, read once (19:03 Thai; `out_ns1_ticks.txt`; parity: `ns1_ticks.straddle` equals dev1's runner
on 100 / 100 P1 / P2 trades):** 206 of 208 release days fetched (the 2 missing are Good Fridays, market shut).

| Release days, ticks | 2021-22 | 2022-23 | 2023-24 | 2024-25 | pooled |
|---|---|---|---|---|---|
| trades, R | 39, +0.031 | 50, -0.010 | 50, -0.213 | 47, -0.058 | 186, **-0.068** (-0.22..+0.08) |
| the same days on M1 | +0.185 | +0.248 | +0.128 | +0.095 | +0.164 |

- **FAIL.** On the real ticks the release-day straddle had no edge in 2021-25; the M1 result was the fill the bar
  cannot see (M1 +0.23 R over the ticks on the same 186 days, the same side on 92 %).
- So the straddle's edge (P1 +0.467 / P2 +0.119 / exam +0.285) belongs to the present (2025-10 on), like #22 / #23 / #43.
- **Lesson:** M1 cannot judge a release-minute entry; only ticks can. Every earlier M1 judgement of a release-minute
  rule is suspect.
- **App item:** `ReadOnlyMT5Gateway.ticks_range` fails with "Terminal: Call failed" on every date (2026-10-20), while
  `copy_ticks_range` with datetimes works; to fix in `app/broker/gateway.py` with a test.

## NS-2: the straddle scaled to the present volatility - written before computing (2026-10-20 19:09 Thai; owner: "start")
Owner's principle: everything relative. NS-1's fixed 2 USD trigger and 8 USD stop fit a gold that runs about 93 USD a
day; in 2021-25 it ran 22-40. **The rule:** k = the MT5 ATR(14) of the last H1 bar closed by 08:30 NY / 16.33 (P1's
median H1 ATR, dev2's V3-1 table, a number from the learning part); trigger = 2 k, stop = 8 k; everything else as
NS-1 / PLAN-1 (the reference tick before 08:30:00, live 60 s, the fill past a gap, out at +30 min, slippage 0,
R = pnl / stop). Release days only.
- **The judge:** the old release-day ticks 2021-09 .. 2025-10 (`data/ticks_old`), read once. **Pass:** pooled >= +0.15
  and > 0 in at least 3 of the 4 years.
- Beside it, as a description: the release days of P1 / P2 / exam on `data/ticks` (k near 1 there).
**NS-2 read (19:10 Thai; `out_ns2.txt`).** A first run at 19:09 was invalid: `gold.bars` keeps microsecond times and
`k_at` searched them with a nanosecond t0, so every day read the last H1 bar of the store (2026-10-16; a constant k 0.91
from the future). Kept as `out_ns2_invalid_unit_bug.txt`; a test (`test_ns2.py`) now fails on that bug and passes on the
fix. The corrected rule, read once:

| Release days | 2021-22 | 2022-23 | 2023-24 | 2024-25 | P1 | P2 | exam |
|---|---|---|---|---|---|---|---|
| trades, R | 53, +0.190 | 51, -0.170 | 51, -1.169 | 52, +0.159 | 8, -0.004 | 13, +0.060 | 26, +0.804 |
| median stop (USD), spread / stop | 1.72, 0.29 | 1.72, 0.33 | 1.77, 0.38 | 3.61, 0.11 | 6.57, 0.06 | 9.25, 0.04 | 8.08, 0.05 |

- **FAIL** (pooled -0.241 on 207). Scaled down, the stop is a few spreads wide and the release jump passes it
  (2023-24: -1.17 R a trade). The straddle does not scale with volatility; it needs the large moves of the present.
- With NS-1, the straddle is now known to pay only since 2025-10, at gold's present size.

## Why gold changed in 2025-10 - outside research (2026-10-20 19:3x Thai; owner: "research the facts, don't ask me")
Sources (web, read 2026-10-20): World Bank blog "When uncertainty rises, gold rallies"; WGC gold ETF flows 2025-11;
ING Gold Monthly; Kitco 2025-07-02 "gold will consolidate H2 2025"; BullionVault / Marex on the January 2026 record and
crash; gold.org Weekly Markets Monitor 19 Oct 2026; SSGA Monthly Gold Monitor Oct 2026; Reuters "Asia Gold" via Kitco.
- **April 2025 was one shock:** the US "reciprocal tariff" news drove gold to about 3,500 USD, then it "spent much of
  the rest of Q2 digesting gains" as ETF inflows slowed and futures positioning declined (ING, Kitco). Size without a
  lasting flow - the month our leads did not pay.
- **From 2025-10 a persistent flow:** five months in a row of ETF inflows (8.2 bn USD in 2025-10 alone), the largest
  quarterly ETF inflow in years, central-bank buying, speculators and Asian flows; record after record (4,300 in
  2025-10, above 5,000 on 2026-01-26, about 5,595 on 2026-01-31), then a crash on 2026-01-29/30 (the Fed-chair
  nomination, exchange margins). US data was delayed by the 2025-10/11 government shutdown.
- **Now (2026-10):** gold about 4,150-4,200, down about 4 % this year; managed-money net longs cut from 151,315
  (2026-08-25) to 114,820 (2026-10-06); ETF buyers still adding (reported 13 straight weeks), options leaning bearish.
  The flow regime may be fading - which the forward record must watch.
- **The hypothesis to test (strategist):** the leads pay while a persistent speculative flow drives gold (rising
  managed-money positioning / ETF inflow streaks), not merely while it is large. Data: the CFTC Commitments of Traders
  (COMEX gold, managed money, weekly, public) - known with a 3-day lag (Tuesday data, Friday release).
