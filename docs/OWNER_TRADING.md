# The owner's own trading: a custom setup in the making

The owner trades by hand on the real account and asked (2026-10-15) for their trading to be analysed and turned
into a setup of their own: what they do, what works, where it is weak, what to improve. This file is the running
note. The bot never reads or touches the real account: the trade history comes from a report the owner exports
from MT5 (History, Report), and everything else from the history store.

## How this works (owner, 2026-10-15: "this is what a custom setup means")

1. The owner tells each trade: what they saw, the entry price(s), why; the stop and target and why; when they
   moved the stop or closed by hand and why.
2. Claude maps it onto what the bot measures (H4/H1/M15 map states, chart-read structure HH/HL, levels,
   trendlines, EMAs, MACD) and writes the rule it implies.
3. Claude restates the rule for the owner to confirm before any code.
4. The confirmed rules become the owner's setup (entries, scale-in, stop, target, management), judged by
   backtest on the ladder (March, August, the year).
5. Strengths, weaknesses and improvements go in this file. The real-account report is a supplement.

### Draft rule from trade 1 (corrected by the owner: "close; I meant to trade the range 4138-4160")

**Range trading after a run.** After a strong run (4073 -> 4161.7) price ranges (about 4138-4160): buy in the lower
part of the range, stop below the range with room for a false break (4128), target near the top but under the
high (4154); stop to break-even once it runs; close by hand when it stalls.

- Data: since 10:00 Thai the M15 high was 4161.69 and the low 4131.43; 81 % of the M15 closes stayed inside
  4138-4160 (4 of 21 below). **The bot's market map found no range box** on M15 or H1 (box None at 12:00, 13:00
  and 15:00): the owner sees a range the bot does not.
- The adds at 4135.83-4136 were below the range bottom: price swept to 4131.4 and closed back inside - a false
  break, the side our measurements say pays (F1, S1 fade false breaks). The owner's idea sits on the paying side;
  the weak part is the entry method (reactive averaging down while price falls through the bottom).
- Improvement to test: wait for the reclaim (a close back inside the range, above 4138) and enter there, the
  stop under the sweep low (4131.4): smaller risk, a planned entry. The chart read already records the event
  (SWEEP_RECLAIM).

Owner's answers: **both sides of the range** - sells start above 4151, 0.01 lot at a time; the account is
**150 USD at 1:2000**.

### Risk on a 150 USD account (gold: 0.01 lot = 1 USD per 1.00 of price)

| | Value | Of the account |
|---|---|---|
| The buy set, 0.09 lot, average ~4142.97 | 9 USD per 1.00 | |
| At the first stop 4128 | about **135 USD** | **about 90 %** |
| At the break-even stop | about 0 | |
| Margin at 1:2000 | about 2.1 USD per 0.01 lot, ~19 USD | about 13 % |

The leverage keeps the margin light, so the size is limited only by the stop distance times the lots - and the
averaging down put about 90 % of the account at risk on one range. **The main weakness.** Rule to test: a fixed
risk per set (e.g. 10 % = 15 USD; with a 15.00 stop that is 0.01 lot), the number of 0.01 steps derived from it.

Open questions: the sells' stop (how far above the 4161.7 high), the step between adds and the most adds; whether
sells may open while the buys are still open (both sides at once between 4151 and 4154).

Earlier open questions: (1) do they also sell near the top of the range? (2) how are the range edges
picked (the run's high and the first bounce?) (3) how long must price range before it counts as a range?

## How the owner trades (their own words, 2026-10-15)

- Manual trades on the real account, gold mostly; reads M1, M5 and H1 charts (EMAs, a trendline, MACD).
- Stop beyond the structure (below the higher low that keeps the trend), target below the next swing high.
- **Closes by hand** when the trade does not run and looks like turning the other way.

## Trade log

| # | Opened (Thai time) | Symbol | Side | Entry | SL | TP | R:R | Exit | R | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-15 11:55-15:15 | XAUUSD | BUY x7 (0.09 lot) | avg 4142.98 | 4128, then 4143.00 (break-even) | 4153.72-4154.36 | 0.76 at first | 4 TP, 3 by hand | +81.52 USD (+54 % of 150) | range trade; see below |
| 2 | 2026-10-15 ~15:30 | XAUUSD | SELL x2 (0.02 lot) | avg 4150.83 | none set | target ~4097-4102 (not set) | ~3.8 with a stop above 4161.7 | open | | head-and-shoulders right shoulder; see below |

### Trade 1 - context at the entry (bot's reads, data to 14:51)

- M5: the run from 4073 (14 Oct) to 4161.7, a pullback to 4131.4 on the rising trendline and the long EMA (a
  higher low), MACD turning up: a with-trend entry after a pullback.
- M1: higher lows 4132.69 -> 4138.89 -> 4140.89, but equal highs 4145.25 / 4145.49 and MACD fading.
- M15: broadening confirmed, up "now" (higher low 4131.43). H1: map TRANSITION (efficiency 0.04), chart read
  down (invalidation 4161.69). No trending higher timeframe.
- Stop 4128 sits below the M15 higher low (structure) - good. Target 4155 sits above four resistances
  (4145.3-4145.5, 4147.4, 4150.98, 4152.46) but below the swing high 4159.7-4161.7. R:R 0.76: it needs to win
  more than 57 % of the time to pay.

### Trade 1 - the fills (the owner's MT5 history; server time + 4 h = Thai time)

| Opened (Thai) | Lot | Entry | Exit | How | Profit |
|---|---|---|---|---|---|
| 11:55 | 0.02 | 4146.47 | 4148.45 | by hand | +3.96 |
| 12:10 | 0.02 | 4145.87 | 4154.01 | TP | +16.28 |
| 12:20 | 0.01 | 4144.31 | 4148.54 | by hand | +4.23 |
| 12:28 | 0.01 | 4141.69 | 4153.84 | TP | +12.15 |
| 12:54 | 0.01 | 4139.44 | 4153.52 | by hand, under its TP | +14.08 |
| 13:33 | 0.01 | 4135.83 | 4153.84 | TP | +18.01 |
| 14:19 | 0.01 | 4140.91 | 4153.72 | TP | +12.81 |
| **0.09** | | **4142.98** | | | **+81.52** |

Every profit checks against (exit - entry) x lot x 100. **Correction:** the two 0.02 lots were the *first*
entries (11:55, 12:10), not adds at a later high as written before; the owner started with the largest size at
the highest prices and averaged down with 0.01 lots.

- Exits: the high was about 4154.0; every TP at 4153.72-4154.01 filled, the ones at 4154.19/4154.36 did not -
  the falling-trendline confluence held. The two dearest lots were closed by hand at 4148.5 (the stall under
  4149.5), the cheaper ones held to the target; the 4139.44 lot closed by hand at 4153.52 when price stalled.
- Drawdown: at the 4131.43 low (13:15) the 0.07 lot then open was down about 90 USD (about 60 % of the account);
  at the first stop 4128 the set would have lost about 122 USD (about 81 %).
- A planned reclaim entry (about 4138-4140 after the close back inside the range, stop under 4131.4) risks about
  8 USD per 0.01 lot: about 14-30 USD at the 4154 target for 0.01-0.02 lot, against 81.52 USD made here with 6-10
  times the risk. The setup must compare return against risk, not profit alone.

### Trade 2 - the right shoulder (M15 chart at ~15:30 Thai)

- The owner's idea (read from the chart, to confirm): a head and shoulders on M15 - left shoulder ~4154 (14 Oct
  afternoon), head 4161.7 (this morning), right shoulder now ~4154 under the horizontal 4153.8 and the falling
  trendline from the head; neckline ~4131-4136 (today's 4131.4 low). The purple target ~4097-4102 is the
  head-to-neckline height (~30) below the neckline, at the 78.1 % retracement.
- The bot's H1 read agrees: H1 structure down, ending above 4161.69 (the head).
- Sells 0.01 at 4151.69 and 4149.97 (average 4150.83), price 4153.81: -5.96 USD. **No stop set.**
- A stop that fits the idea is above the head (4163-4165): about 26 USD at risk (~11 % of ~231 USD) for ~101 USD
  to the target: R:R about 3.8. Between: 4143.19 (50 %), 4139, then the neckline must break for the target.
- The owner's red trend channel (drawn on the chart): a **falling channel from the head** - the upper line through
  the head 4161.7 and the right shoulder ~4154, the lower parallel through the 4131.4 low (about 4127-4128 now,
  falling). The sells sit where three resistances meet: the channel's upper line, the right shoulder and the
  horizontal 4153.8. The purple target (~4100) is steeper than the channel: it needs the neckline (4131-4136)
  and then the channel's lower line to break; inside the channel the lower line is only ~4115-4120 in 8 hours.
  The idea fails on a close above the channel's upper line and 4154-4155, and is void above the head (4161.7).
- Contrast with trade 1: a planned reversal at resistance with a structural invalidation and R:R near 4, against
  a range buy at R:R under 1 with averaging down. The open question is the missing stop.

### Trade 1 - management (chart at ~15:55 Thai, before the fills were known)

- Seven buys, average about 4142.97 for 0.09 lot.
- When price started to move, the stop went to about 4143.19 (the average: break-even); the target to ~4153.8.
- Price 4145.83, just above the M1 double top 4145.3-4145.5 (broken: high 4146.49). Next resistances 4147.4-4147.9,
  4149.85, 4151.8.
- Notes: the break-even stop is about 2.6 below the price while an M1 bar ranges about 1.4: an ordinary two-bar
  pullback can take it before the target. The two 0.02 adds (40 % of the size) came at the latest high and lifted
  the average. The buys at 4135.83-4141.59 were added **because price fell** (owner, 2026-10-15): averaging
  down, not a plan. It worked here because the M5 higher low (4131.4, on the rising trendline) held.
- The target ~4153.8-4154.2 sits where the falling trendline from the 4161.7 high crosses: a higher-timeframe
  resistance confluence just above the target (a strength).

## Findings so far

| | Finding | Why it matters |
|---|---|---|
| Strength | Stop beyond the structure (the M15 higher low), not at a round number | The trade survives an M1 trend break |
| Strength | Moves the stop to break-even once price runs | Protects the capital |
| Strength | Target just below a higher-timeframe resistance | Takes the move before the likely stall |
| **Weakness** | **Averages down when price falls (unplanned adds)** | The risk grows exactly when the trade is going wrong; one deeper move (below the higher low) turns small losses into a large one |
| Weakness | The largest lots (0.02 x2) first, at the highest prices, then averaging down in 0.01 | An inverted pyramid: the most size at the worst prices; 60 % of the account under water at the low |
| Strength | Closed the dearest lots by hand at the stall (4148.5), held the cheap ones to the target | Cut the risk where the trade was weakest |
| Strength | Targets at the confluence (4153.7-4154.0) filled; the high was ~4154.0 | Precise target reading |
| To check | Break-even stop ~2.6 under the price with M1 bars of ~1.4 | Noise may take it before the target |

Improvement to test: a **planned scale-in** in place of averaging down - the levels decided before the first
entry (e.g. at the structure: the last higher low / the rising trendline), one shared stop below the structure, the
total risk of all parts fixed in advance. The PWA's Trading profile already has this ("Splitting an entry: Scale
in": the first order at the signal, the others as limits toward the stop, one shared stop, the total within the
risk per signal).

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
