# The owner's own trading: a custom setup in the making

The owner trades by hand on the real account and asked (2026-10-15) for their trading to be analysed and turned
into a setup of their own: what they do, what works, where it is weak, what to improve. This file is the running
note. The bot never reads or touches the real account: the trade history comes from a report the owner exports
from MT5 (History, Report), and everything else from the history store.

## How the owner trades (their own words, 2026-10-15)

- Manual trades on the real account, gold mostly; reads M1, M5 and H1 charts (EMAs, a trendline, MACD).
- Stop beyond the structure (below the higher low that keeps the trend), target below the next swing high.
- **Closes by hand** when the trade does not run and looks like turning the other way.

## Trade log

| # | Opened (Thai time) | Symbol | Side | Entry | SL | TP | R:R | Exit | R | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-15 13:00-15:55 | XAUUSD | BUY x7 (0.09 lot) | avg ~4142.97 | 4128, then ~4143.19 (break-even) | 4155, then ~4153.8 | 0.76 at first | open | | scaled in; see below |

### Trade 1 - context at the entry (bot's reads, data to 14:51)

- M5: the run from 4073 (14 Oct) to 4161.7, a pullback to 4131.4 on the rising trendline and the long EMA (a
  higher low), MACD turning up: a with-trend entry after a pullback.
- M1: higher lows 4132.69 -> 4138.89 -> 4140.89, but equal highs 4145.25 / 4145.49 and MACD fading.
- M15: broadening confirmed, up "now" (higher low 4131.43). H1: map TRANSITION (efficiency 0.04), chart read
  down (invalidation 4161.69). No trending higher timeframe.
- Stop 4128 sits below the M15 higher low (structure) - good. Target 4155 sits above four resistances
  (4145.3-4145.5, 4147.4, 4150.98, 4152.46) but below the swing high 4159.7-4161.7. R:R 0.76: it needs to win
  more than 57 % of the time to pay.

### Trade 1 - management (chart at ~15:55 Thai)

- Seven buys (read from the chart labels, some hidden; to confirm): 0.01 at 4135.83, ~4139.44, ~4140.91,
  ~4141.59, 4144.31; 0.02 at 4145.87 and 4146.47. Average about 4142.97 for 0.09 lot.
- When price started to move, the stop went to about 4143.19 (the average: break-even); the target to ~4153.8.
- Price 4145.83, just above the M1 double top 4145.3-4145.5 (broken: high 4146.49). Next resistances 4147.4-4147.9,
  4149.85, 4151.8.
- Notes: the break-even stop is about 2.6 below the price while an M1 bar ranges about 1.4: an ordinary two-bar
  pullback can take it before the target. The two 0.02 adds (40 % of the size) came at the latest high and lifted
  the average. Open question: were the buys at 4135.83-4141.59 planned (buying the pullback) or added because
  price fell?

## Hypotheses to test (with the report and backtests)

1. **Early manual exit** ("it does not run and looks like turning"): turn it into a measurable rule (not +X R
   within N bars and the last bar against the trade: close) and backtest it against holding to the SL/TP.
2. **Target placement**: below the swing high (the owner's habit) against the R:R it leaves; how often price stalls at
   the resistances in between.
3. **Entries into nearby resistance**: entries a few points under a double top; does waiting for the break above
   it (or a retest) do better?
4. Which higher-timeframe states the winners and losers came from (trending vs TRANSITION).
5. **Scaling in** (several entries, larger adds after the break) against a single entry: the average, the risk
   it adds, and whether the adds at the high pay.
6. **Break-even stop** once price moves: how often a tight break-even stop is taken by noise before the target
   (an M1 bar ~1.4 on gold) against a stop under the last M1 higher low.

## Status

- 2026-10-15: waiting for the real account's history report (`data/owner/`, HTML or XLSX).
