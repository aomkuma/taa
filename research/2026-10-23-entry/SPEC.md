# The entry assessment - specification (draft 1, 2026-10-23)

Owner (2026-10-23): an entry never rests on one or a few parameters - every trade combines all the evidence learned so
far, each part weighted (docs/OWNER_GOALS.md, "One trade = all the evidence, weighted"); and "convert it into code the
bot can use, complete and correct - a right understanding with wrong or incomplete code is still wrong."

This file is the contract the code is written and tested against. Every definition uses **closed bars only** (the bar
that contains the decision time is never read), times in UTC internally (Thai time only in reports), prices in USD,
distances also in D1 ATR(20) and in zone steps. Indicators use MT5's formulas (`precursors/foundation.py`).

## 1. Candidate (what is assessed)

A candidate = (time, side, entry price, stop, target) produced by a trigger on the entry timeframe (M5 by default,
M1 / M15 by the adaptive rule). Triggers are only the ways a candidate appears; the assessment decides.

- **T1 re-test of a broken zone line**: an H1 close beyond a zone line (the break), then price returns to the line's
  band (+-0.15 step) and an entry-TF bar closes back on the break side.
- **T2 rejection at a zone line** (the turn): price reaches a line's band after a move toward it, and an entry-TF bar
  closes back out with a wick through the band.
- **T3 the B2 patterns** (W / M / H&S / sweep at the owner's H1 levels) - kept as a trigger, entered at the second
  extreme (see C1), not after the neckline break.

## 2. Components (each a number with a fixed sign convention: + favours the trade)

| # | Component | Definition (inputs at the decision time) | Reading |
|---|---|---|---|
| C1 | Entry precision | `late` = distance from the move's start (the level / the pattern extreme) to the entry, in zone steps; `stop_pool` = the stop's distance beyond the nearest pool (swing high/low, round 10 USD, the previous day's high/low, a swept wick) in D1 ATR - negative = the stop sits inside the pool | late small, stop beyond the pool: + |
| C2 | Structure and clarity | the last two confirmed 3-bar fractal highs and lows on the entry TF and the one above: HH/HL = +1, LH/LL = -1, mixed = 0, times the side; clarity = the pattern's swings each >= 0.25 step and the entry-TF ATR below its 20-day median x 1.5 | agrees and clear: + |
| C3 | Trend and phase | the structure sign on D1, H4, H1, M15 times the side; phase = the last 3 closed D1 bars closed the same way (one-way run) or not | per the measured interaction (a turn against a one-way run: -) |
| C4 | Momentum at the level | the approach: the move into the level over the last 10 entry-TF bars in D1 ATR; touches of the level's band in 5 days; the bounce of each touch (shrinking = worn) | a spent approach and fresh level for a turn: + |
| C5 | Zone plan | where the entry sits in the 70-90 USD grid (share of a step to the nearest line); the room to the next line beyond the target side in R | room >= 2 R: + |
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
