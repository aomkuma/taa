# Journal agent - notes (2026-10-17)

Learning like a trader: chart the confluence rule's trades on design data, keep a journal (journal.md), turn the
lessons into a revised rule, check it by half-year against a coin, freeze, one test on 2026-03-01 .. 10-14.

## Files

- `jlib.py` - M1 arrays per instrument, the one-trade simulation (ny_lab.M1.trade with the instrument's slippage),
  the confluence selection loop (one position, at most 2 trades per day and session), the coin (10-20 seeds).
- `build.py` - candidate table (every minute of the three windows x both sides), the confluence parts re-implemented
  from M1 (so they exist before 2025-12 and for FX), plus chart context. Runs under `.venv` (ChartReadFrame).
  `design` = 2023-11-01 .. 2026-02-28; `test` built only after the rule is frozen.
- `verify.py` - build.py vs own_ml_long + own_ml_cr_levels on 2025-12 .. 2026-02.
- `rules.py` - every rule (written here first), `lab.py` - half-year table vs coin, `charts.py` - trade charts.

## Conventions

- Gold sizes in U = price / 4100 USD (ny_lab's scaling; in 2026 U is 0.98-1.29 USD). Target 8 U, stop beyond the
  level by one M1 ATR, 3-10 U, break-even at 0.6 of the target, 60-minute horizon (confluence.py). R = P&L / (stop +
  slippage). Costs as ny_lab (ask/bid + 0.07 slippage).
- Design half-years: 2023-11..04, 2024-05..10, 2024-11..2025-04, 2025-05..08 (4 months), 2025-09..2026-02.
  Charts and journal only on 2025-09 .. 2026-02.

## Rule B0 (baseline, written before running)

confluence.py exactly: H1 tide (H1 EMA20 slope with the side and close beyond EMA50), the nearest level behind the
price (today's / yesterday's / Asian extreme as of 15 min before, round 50, M15 / H1 chart-read level) within 3 M1
ATR and the last 5 minutes' extreme within 1 ATR of it, price action (M1 or M5 hammer, M1 engulfing, sweep and
reclaim), two of three M5 indicators (RSI turning from its side of 50, MACD histogram rising, Stochastic cross);
stop = level - 1 ATR, 3-10 U; target 8 U; break-even at 0.6; 60 min; all three windows.

### B0 result (design, real costs; out_B0.txt)

1150 trades 2023-11 .. 2026-02, win 24%, **-0.140 R/trade**, 0/5 half-years positive; the coin on the same minutes
-0.151 R (10 seeds). Last half-year 2025-09 .. 2026-02: 267 trades, -0.125 R (coin -0.104). Kinds ours 53/4/43 vs
coin 52/4/44 - the rule picks the side like a coin (as on the test window in round 9).

## Round 1 lessons (journal.md, 60 charts of 2025-09 .. 2026-02) -> rules J1..J6, written before running

All on top of B0; the earlier half-years (2023-11 .. 2025-08) were not charted, so they are the check.

- J1 M5 with the trade: the last closed M5 bar's close beyond its EMA20 on the trade's side and the EMA20's last
  change not against the side ((e20 - e20[-1]) * side >= 0).
- J2 H1 structure not against: chart-read H1 structure and "now" structure, signed by side, both >= 0.
- J3 no knife / spike: |ret15| <= 4 M1 ATR and M1 ATR <= 2x its trailing day median (atr_ratio).
- J4 no US release from 15 min before to 15 min after (since_rel > 15 and until_rel > 15).
- J5 stop beyond the sweep: stop price = the farther of (level - 1 ATR) and (the last 15 minutes' extreme - 0.5
  ATR) for the side; 3-10 U as before.
- J6 = J1 + J2 + J3 + J4 + J5 (the trader's revised rule, version 1).

### Round 1 results (design, real costs; out_J1-6.txt) - R/trade, ours vs the coin (10 seeds) on the same minutes

| rule | trades | win % | R/trade | coin R | halves + | note |
|---|---|---|---|---|---|---|
| B0 | 1150 | 24 | -0.140 | -0.151 | 0/5 | baseline |
| J1 M5 with | 472 | 28 | -0.071 | -0.165 | 1/5 | the only lesson clearly above the coin: 3 of 5 halves (2023-11, 2024-11, 2025-09) |
| J2 H1 structure | 823 | 24 | -0.137 | -0.148 | 0/5 | nothing |
| J3 no knife | 830 | 21 | -0.137 | -0.187 | 1/5 | small, mixed |
| J4 no news | 1132 | 23 | -0.141 | -0.150 | 0/5 | nothing (few trades touched) |
| J5 sweep stop | 1111 | 24 | -0.100 | -0.118 | 1/5 | cuts the loss (kind 3 43% -> 34% in 2025-09..02) but the coin gains as much: a cost/stop effect, not side |
| J6 all | 201 | 28 | -0.012 | -0.060 | 3/5 | 0.34 trades/day; halves -0.30 -0.19 +0.32 +0.15 +0.05 |

Ablation next (written before running): J7 = J1 + J5; J8 = J1 + J3 + J5; J9 = J1 + J2 + J5; J10 = J1 + J4 + J5.

### Ablation (out_J7-10.txt)

| rule | trades | win % | R/trade | coin R | halves + | 2025-09..02 ours / coin |
|---|---|---|---|---|---|---|
| J7 = J1 + J5 | 387 | 29 | -0.021 | -0.052 | 3/5 | +0.087 / +0.083 |
| J8 = J1 + J3 + J5 | 300 | 29 | -0.015 | -0.085 | 3/5 | +0.085 / +0.028 |
| J9 = J1 + J2 + J5 | 263 | 30 | +0.001 | -0.104 | 3/5 | +0.069 / -0.008 |
| J10 = J1 + J4 + J5 | 383 | 29 | -0.026 | -0.050 | 3/5 | +0.082 / +0.082 |

The edge over the coin is 0.03-0.10 R and comes mostly from 2024-11..2025-04; on the charted half-year J7 equals
the coin. Most of the loss cut (B0 -0.140 -> J7 -0.021) is the wider stop (cheaper in R) plus M5-with.

## Round 2 - journal of J7's 48 trades of 2025-09 .. 2026-02 (charts/J7), and the numbers (out_analyze_B0.txt)

New losers (journal.md round 2): buying under the 72-hour H1 high / the day high (room < 0.5 tp) after a vertical
run; flat H1 (EMAs tangled, close within ~1 H1 ATR of the EMA50) -> chop; a release 5 min ahead. Winners again:
compression on the level then a break, or a higher low after a sweep, then a break.
Bins of B0's 1150 trades vs the coin (SE ~0.08 R a bin): nothing beyond noise; consistent in both the charted and
the earlier halves only weakly: flat H1 (h1_c_e50 < 0.85) the worst bin (ours -0.249 vs coin -0.188); the trades
*with* 60-min momentum (ret60 > +3 ATR) and at the 4-hour extreme on their side the best (ours -0.003 vs coin
-0.080).

### Rule K (written before running): the trader's trigger - test, higher low, break

Context: H1 tide (B0) and M5 with (J1). Setup (for a buy; mirror for a sell): L = the lowest low of the last 30
M1 bars (the test); the level = B0's nearest level behind the close; the test reached the level zone:
L <= level + 1 ATR and L >= level - 2 ATR (a sweep allowed, not a collapse); a higher low: the lowest low of the
last 5 bars >= L + 0.3 ATR; the trigger: the decision bar closes above the highest high of the 10 bars before it;
the close above the level. Stop = L - 0.5 ATR, 3-10 U. Target 8 U, break-even 0.6, 60 min (as B0). No B0
price-action / indicator conditions (the trigger is the price action).
K2 = K + no release +-15 min + not a flat H1 (h1_c_e50 >= 0.85).
