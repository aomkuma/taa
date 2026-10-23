# The entry assessment - specification (draft 1, 2026-10-23)

Owner (2026-10-23): an entry never rests on one or a few parameters - every trade combines all the evidence learned so
far, each part weighted (docs/OWNER_GOALS.md, "One trade = all the evidence, weighted"); and "convert it into code the
bot can use, complete and correct - a right understanding with wrong or incomplete code is still wrong."

This file is the contract the code is written and tested against. Every definition uses **closed bars only** (the bar
that contains the decision time is never read), times in UTC internally (Thai time only in reports), prices in USD,
distances also in D1 ATR(20) and in zone steps. Indicators use MT5's formulas (`precursors/foundation.py`).

## 0. No fixed timeframe (owner 2026-10-23)

"Do not fix the timeframe - treat every condition as a principle that applies the same idea and system to every
TF." Every component is written for frames named by their place relative to the entry timeframe E on the ladder
M1 - M5 - M15 - M30 - H1 - H4 - D1 - W1 - MN, never by a fixed name:

- **E** the entry / exit / stop frame; **E+1** the frame that must agree with the picture (C2);
- **trend frames** E+1 .. E+4 (C3); **zone frame** Z (the grid's step = Z's ATR(20)); **near / far frames** for the
  strong levels (C5b, several hundred bars each);
- every threshold in bars of its own frame, in its ATR or in zone steps - never in minutes, hours or USD (the only
  USD numbers: the round-number spacing and the band floor, both instrument facts).

Gold intraday (the owner's framework: M1-M5 entry, M15-H1 trend, D1 side) maps to E = M5, Z = D1, near / far =
H4 / D1; the offsets for other E are measured, not assumed. The code takes the frames as inputs
(`zone_grid.grid_rows(..., bar_ns)`, `strong_levels.strong_levels(near, far, ...)`).

## 1. Candidate (what is assessed)

A candidate = (time, side, entry price, stop, target) produced by a trigger on the entry timeframe (M5 by default,
M1 / M15 by the adaptive rule). Triggers are only the ways a candidate appears; the assessment decides.

- **T1 re-test of a broken zone line**: an H1 close beyond a zone line (the break), then price returns to the line's
  band (+-0.15 step) and an entry-TF bar closes back on the break side.
- **T2 rejection at a zone line** (the turn): price reaches a line's band after a move toward it, and an entry-TF bar
  closes back out with a wick through the band.
- **T4 consolidation at a zone line, then the break** (owner 2026-10-23: wait for price to consolidate at the zone,
  then trade): an arrival at a line (main or half), 8+ bars in a box at most 0.3 step tall overlapping the band,
  the first close out of the box -> that way. Measured (zone_wait.py, M15 2023-09 .. 2026-10): THROUGH the line
  +0.087 R, positive in all four years; back the way price came (bounce) -0.089, negative in all four; the bounce at
  the arrival -0.028. So a bounce at a line needs strong evidence from the other components; a straight break then
  the return (+0.046, mixed by year) stays a candidate. Code: `app/strategy/zone_break.py`.
- **T3 the B2 patterns** (W / M / H&S / sweep at the owner's H1 levels) - kept as a trigger, entered at the second
  extreme (see C1), not after the neckline break.

## 2. Components (each a number with a fixed sign convention: + favours the trade)

| # | Component | Definition (inputs at the decision time) | Reading |
|---|---|---|---|
| C1 | Entry precision | `late` = distance from the move's start (the level / the pattern extreme) to the entry, in zone steps; `stop_pool` = the stop's distance beyond the nearest pool (swing high/low, round 10 USD, the previous day's high/low, a swept wick) in D1 ATR - negative = the stop sits inside the pool | late small, stop beyond the pool: + |
| C2 | Structure and clarity | the last two confirmed 3-bar fractal highs and lows on the entry TF and the one above: HH/HL = +1, LH/LL = -1, mixed = 0, times the side; clarity = the last four swings alternate high / low and every leg >= 2 x the frame's ATR(14) (code: `structure_read.py`) | agrees and clear: + |
| C3 | Trend and phase | the structure sign on D1, H4, H1, M15 times the side; phase = the last 3 closed D1 bars closed the same way (one-way run) or not | per the measured interaction (a turn against a one-way run: -) |
| C4 | Momentum at the level | the approach: the move into the level over the last 10 entry-TF bars in D1 ATR; touches of the level's band in 5 days; the bounce of each touch (shrinking = worn) | a spent approach and fresh level for a turn: + |
| C5 | Zone plan | where the entry sits in the 70-90 USD grid (share of a step to the nearest line); the room to the next line beyond the target side in R | room >= 2 R: + |
| C5b | Strong levels ahead (owner 2026-10-23: "look at several hundred bars to see the farther overall picture - the next strong levels price may reach") | from the last ~500 H4 bars (about 4 months) and ~250 D1 bars: the levels price turned at more than once (fractal swing highs / lows merged within 0.15 step, counted by touches and by the size of the move they turned), the anchors of past zone shifts, the multi-month high / low; the strong levels beyond the entry on the target side (the room before the first one, in R) and on the stop side (the stop must sit beyond one, not inside it) | room to the first strong level >= 2 R and the stop beyond a strong level: + |
| C6 | Volatility | H1 ATR(14) / its 20-day median | above 1.1: stand aside (the one rule that held twice) |
| C7 | Timing | the session (Asia 07-09, London 13-14, NY open + 1-2 h, Thai time); minutes from the scheduled data (08:30 / 10:00 New York) | inside a window, not in the first 30 min after data: + |
| C8 | Volume | the trigger bar's tick volume / the same bar-of-day's 20-day mean | a break with volume, a rejection with volume: + |
| C9 | D1 context | yesterday's body in D1 ATR and its close position; today's run so far | with yesterday's strong day: + |

## 3. The decision

`score = sum(w_i * f_i(C_i))`, each `f_i` a fixed step / clip map written before fitting; trade when `score >= s*`
and C6 is not "stand aside". Weights start from the owner's order (C1 > C2 > C3 > C4 > C5 > C6 > C7 > C8 > C9), set on
the old years (2023-09 .. 2025-03), judged on 2025-04 .. 2025-10 (unseen for this design), then the solo exam. At most
one weight per component; the number of fitted values stays small next to the number of candidates.

## 4. Correctness (before any result is read)

1. **Each component a pure function** (bars in, number out), in one module the bot imports - the research and the
   bot run the same code, never two copies.
2. **Hand-worked unit tests** per component: small bar series built by hand with the answer computed on paper
   (including the closed-bar edge: the forming bar must not change the result).
3. **Planted bugs**: for each component a mutated copy (look-ahead by one bar, side sign flipped, off-by-one in the
   swing, wrong time zone, summer / winter D1 open) - the tests must fail on every one.
4. **Independent re-derivation**: a second, separate implementation of each component (plain loops, no shared
   helpers) agrees with the module on every candidate of a month of data.
5. **Acceptance cases from the owner's charts** (results must match the owner): 2026-10-20 .. 22 H4 (the owner's
   chart): T1 must produce the sell re-test of 4,141 (entry ~4,130-4,140, the stop above the swept 4,155.5, the
   target 4,066) and C1-C9 must read it as the chart does; plus a losing B2 case read as late (C1).
6. **Parity**: the bot's backtest on ticks and the research run produce the same candidates and readings on the same
   days.

## Progress (code that passed sections 4.2-4.4)

| Module | Components | Hand-worked tests | Planted bugs | Independent check |
|---|---|---|---|---|
| `app/strategy/zone_grid.py` | C5 grid | 18 | 13 / 13 | parity with the research grid, 1,327 D1 bars |
| `app/strategy/strong_levels.py` | C1 pools, C5b strong levels, zone lines + halves | 23 | 22 / 22 | plain-loop re-derivation 120 / 120; 2025 snapshots drawn for the owner (accepted 2026-10-23: "OK, overlap is normal") |
| `app/strategy/structure_read.py` | C2 structure + clarity, C3 trend + phase | 19 | 12 / 12 | parity with the research structure / run3 at 300 times on D1 / H4 / H1 / M15 |
| `app/strategy/zone_break.py` | T4 consolidation at a line, then the break | 15 | 13 / 13 | parity with zone_wait.py: 942 / 942 events (arrival, entry bar, side, stop) |
| `app/strategy/level_momentum.py` | C4 touches, bounces, worn, approach, bars at the line | 14 | 12 / 12 | parity with the journal's context: 98 / 98 trades |
| `app/strategy/zone_retest.py` | T1 the re-test of a broken zone line | 10 | 12 / 12 | a separate state-machine version equal on all 1,223 M15 events of 2025 (it found an off-by-one in the first version); acceptance: the owner's 4,141 sell re-tests on H4 / H1 with the stop 4,159.3 above the swept 4,155.5 |
| `app/strategy/zone_reject.py` | T2 the rejection at a zone line (arrivals shared with T4) | 8 | 10 / 10 | a plain re-derivation equal on all 656 M15 events 2023-08 .. 2026-10; raw: -0.024 R a trade (won 37 %), swept -0.089 on 139 (negative in 3 of 4 years), not swept -0.007 on 517 |
| `app/strategy/context_read.py` | C6 vol ratio, C7 minutes from / windows, C8 relative volume, C9 the last D1 bar + the day so far | 14 | 14 / 14 | vol and day-so-far equal on 98 / 98 trades; strong days 166 / 166 against retest_week.py's rule (2021-2026) |
