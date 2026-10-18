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
