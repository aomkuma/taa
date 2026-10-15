# Breakouts with the trend: what pays and what does not (2026-10-15)

Owner's question: the M5 gold picture (a run, a box drifting with it, a break up) should have been a trade; why
does the breakout setup not take it, and "find out why others make it pay, then make ours pay". All numbers are
R per trade after the bar's spread plus slippage, judged walk-forward (choose on the first half, judge on the
second). Scripts in this folder; the harness reproduces the engine's March 2026 backtest of
`setup_breakout_box` trade for trade (`box_harness.py`).

## 1. The box breakout (`chart.box_break`, `setup_breakout_box`)

| Test | Result |
|---|---|
| First study, gold M5 (`flag_rules.py`) | +0.41 (55), but 7 trades at 21:40-22:45 UTC (rollover) made 16.1 of its 22.4 R |
| Gold, the bot's detector and limits, 07-20 UTC (`box_harness.py`) | -0.21 (26); March 2026 engine backtest -0.007 (4) |
| Gold, + Asia hours / Asia only | +0.04..+0.11 (first halves negative) / +0.46..+1.07 on 10-12 trades a year |
| Retest entries (`box_retest.py`) | +0.05 against the break entry, inside the noise; nothing passes |
| Why trades lose (`box_why.py`) | 18 of 37 hit the stop first having gone only 0.21 R our way: false breaks |
| 8 traded symbols, M5 / M15 (`box_multi.py`) | M5 bot hours -0.24 (199, CI90 -0.36..-0.11); M15 -0.07 (107) |
| Levers on 8 symbols (`box_levers.py`) | trailing exit -0.17, tested edges only -0.24, a crude fade -0.31: none pays |

H4 "not against" never binds when H1 agrees with the break (0 of 77 cases).

## 2. Trend following, the breakout that pays in the literature (`trend_follow.py`)

29 symbols (28 FX pairs + gold), Donchian break, 2 ATR stop, trailing (chandelier 3 ATR) or channel exit:

| Timeframe | Result |
|---|---|
| H4, 2024-04 .. 2026-10, 8 sets | -0.06 .. -0.17 (900-1,900 trades); win rate 22-35 %; costs about 0.05 R a trade |
| D1 (Turtle 20 / 55 days) | second half -0.10 .. -0.51 in every set; first halves of 10-33 trades |

## 3. Reading

- In these markets and years, a break in the trend's direction is more often false than not, intraday and on
  H4/D1, before and after costs. The documented profits of breakout trend following come from diversified
  futures (commodities, bonds, indices, currencies) over decades, paid by rare strong-trend years; FX and gold
  over 2024-2026 did not have them.
- The edges measured here sit on the other side of the break: fading false breaks inside a trend (S1 M1 gold
  +0.28, F1 M15 +0.16) and reversals at a harmonic PRZ (V1 + room +0.23).
- Nothing in this note changes the bot: `setup_breakout_box` stays out of `config.yaml`.
