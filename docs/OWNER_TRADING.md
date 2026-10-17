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
| 2 | 2026-10-15 ~15:30 | XAUUSD | SELL x2 (0.02 lot) | avg 4150.83 | 4173 (set in MT5) | target ~4100 (not set) | 2.3 | SL, 2026-10-16 03:00 | about -44.34 USD (computed; to confirm from MT5) | head-and-shoulders right shoulder; see below |
| 3 | 2026-10-16 ~10:00-10:40 | XAUUSD | SELL, 0.01 at a time (total to confirm) | avg 4173.8 | ~4180 (above the day's high 4179.72) | 4124 | 8.0 | SL, 2026-10-16 10:49 | about -6.2 USD per 0.01 lot (lots to confirm) | M30 "sideways up = leg B"; sells at the top of the M30 range; see below |

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
- Sells 0.01 at 4151.69 and 4149.97 (average 4150.83), price 4153.81: -5.96 USD. Stop 4173 set in MT5 (the owner set it, then told it).
- A stop that fits the idea is above the head (4163-4165): about 26 USD at risk (~11 % of ~231 USD) for ~101 USD
  to the target: R:R about 3.8. Between: 4143.19 (50 %), 4139, then the neckline must break for the target.
- The owner's red trend channel (drawn on the chart): a **falling channel from the head** - the upper line through
  the head 4161.7 and the right shoulder ~4154, the lower parallel through the 4131.4 low (about 4127-4128 now,
  falling). The sells sit where three resistances meet: the channel's upper line, the right shoulder and the
  horizontal 4153.8. The purple target (~4100) is steeper than the channel: it needs the neckline (4131-4136)
  and then the channel's lower line to break; inside the channel the lower line is only ~4115-4120 in 8 hours.
  The idea fails on a close above the channel's upper line and 4154-4155, and is void above the head (4161.7).
- The owner's stop: **4173** - 11.3 above the head (a false break of the head does not take it) and above the H1
  lower high 4170.29 (the larger downtrend's last high): structural. Risk 22.17 x 0.02 = 44.34 USD (about 19 % of
  ~231 USD) for ~101.66 USD to 4100: R:R about 2.3 (pays above ~30 % wins). A stop just above the head would give
  R:R 3.8 at ~11 % risk but falls to a head sweep. 19 % a trade is high: three losses in a row take ~47 %.
- The owner's plan in money (their words): **win 100, lose 40** (round numbers; computed +101.66 / -44.34):
  R:R 2.5, pays above ~28.6 % wins. The trade was planned in money before the entry - unlike trade 1, whose risk
  grew with every add. Rule for the setup: fix the money at risk and the target before the first entry.
- **Outcome (owner, 2026-10-16: "stopped, price went sideways-up"; M15 data):** 15 Oct 15:00-17:00 up to 4160.43
  and back to 4150; **19:45 down to 4130.48 - the neckline - with the trade about +40 USD**; 20:30 up through the
  head (4168.49): the pattern failed; 21:00-01:00 a 4143-4165 range; **16 Oct 03:00 through 4173: stopped** (high
  4177.30, 4179.72 by 10:00). About -44.34 USD as planned (-40). Day: +81.52 - 44.34 = +37.18 (~187 USD).
- Lessons: (1) the neckline touch with +40 USD open had no rule - a head and shoulders is confirmed only below
  the neckline, so a partial close or a break-even stop there would have turned the loss into a gain or a
  scratch; (2) the sells went against the larger up-structure (higher lows 4073 -> 4131.4, the bot's M15 read
  "now" UP, the rising channel from 4073 unbroken) - a reversal idea needs the neckline break before it is more
  than an idea; (3) the falling channel had two anchor points (head, shoulder), weaker than the rising line with
  several. Good: the stop and the loss were exactly as planned.
- Contrast with trade 1: a planned reversal at resistance with a structural invalidation and R:R near 4, against
  a range buy at R:R under 1 with averaging down. The open question is the missing stop.

### Trade 3 - sells at the top of the M30 range, "leg B" (2026-10-16 ~10:40 Thai, data to 10:39)

- **The owner's idea (their words):** sells 0.01 lot at a time, average 4173.8; stop above the day's high, about
  4180; target 4124; on M30 the move since the low looks like a sideways-up range that has made leg B (of an
  A-B-C: leg C down to come).
- **The bot's reads (data to 10:30-10:39 Thai):**
  - M30: map **RANGE**, box **4130.48 - 4179.72** (the owner's range; the bot sees it this time, unlike trade
    1); chart read FLAT, "now" UP (invalidation 4147.21).
  - M15: read UP (HL 4143.65, HH 4177.30, then 4179.72 at 09:59), "now" UP above 4147.21; map TRANSITION.
  - H1: read CONTRACTING (highs 4200.52 -> 4170.29 -> 4161.69, lows 4073.41 -> 4130.48); 4179.72 is above
    the last two lower highs, so the display read "now" is UP (invalidation 4130.48). Map TRANSITION.
  - H4: map RANGE, box 4073.41 - 4217.08; read BROADENING.
- **Leg B, as data:** from the 4073.41 low (14 Oct 23:00) to 4179.72 = 106.3. Against a leg A of 4170.29 ->
  4073.41 (96.9) B is 110 % of A (B beyond A's start: an expanded flat); against 4200.52 -> 4073.41 (127.1) B is
  84 %. Which A the owner means is to confirm. The target 4124 sits under the range bottom (4130.48 / 4131.43)
  and near the 50 % retracement of B (4126.57).
- **Risk (gold: 0.01 lot = 1 USD per 1.00):** per 0.01 lot about 6.2 USD to the stop and 49.8 USD to the
  target: R:R about 8.0 (pays above ~11 % wins). Price 4167.0 at 10:39: about +6.8 USD per 0.01 lot open.
- **The stop is 0.28 above the day's high, about one spread:** a sell's stop fills on the ask (bid + ~0.25-0.30
  spread), so a bid at about 4179.7 - a plain retest of the high - stops it. In trade 1 the range edge was swept
  (4131.4 under 4138) before the move; trade 2's stop had 11.3 of room above the head. M30 ATR 8.75, M15 ATR
  6.09: a buffer of 0.25-0.5 M30 ATR puts the stop near 4182-4184.5 (the display read has a level at 4183.71),
  about 8-11 USD per 0.01 lot, R:R about 4.7-6.
- **Against the trade:** the M15 and H1 reads "now" are UP; the sells fade the latest higher high. **For it:** M30
  and H4 are ranges and the entry is at the M30 box top (the "both sides of the range" rule from trade 1).
- **Outcome (owner, 2026-10-16 ~10:50 Thai: "stopped"; M1 data):** down to 4163.15 at 10:43 (about +10.65 USD
  per 0.01 lot open), then up 17.4 in six minutes to **4180.54 at 10:49**: the first retest of the day's high took
  the stop, 0.82 above the old high. About -6.2 USD per 0.01 lot plus any slippage; the fills to confirm from
  MT5. Whether 4180.54 was a sweep (back inside the box) or a breakout is still open at 10:49 (close 4179.21).
- **News:** Fed Chair Warsh spoke at the IMF meetings in Bangkok 10:30-11:00 Thai (scheduled a week before; read
  as neutral, the dollar fell). The run that took the stop (10:43 -> 10:49, +17.4) sat inside that window; the
  move went on to 4186.33 by 11:30 and 4189.71 at 15:00. The sells were opened just before a scheduled event.
- Lesson (to test, hypothesis 9): a stop at the range edge is taken by the first retest; a stop with a buffer
  (0.25-0.5 M30 ATR) costs more per lot but survives a sweep. Trade 1's range edge was swept too.
- Open questions: the total lots and whether more adds are planned (where); which drop is leg A; the plan at
  4147 (the M15 higher low) and at the range bottom 4130.5 (trade 2's lesson: +40 USD at the neckline with no
  rule); the account (real or demo).

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

## Setup TS - the triple screen pullback (owner, 2026-10-17)

**Where it came from.** The owner's plan for the week of 2026-10-19 (XAUUSD, H1 chart at the Friday close
4,165, OANDA): the H4 still falls (lower highs 4,225 -> 4,215 -> 4,200 under the trendline from 4,400), the H1
rallied 4,080 -> 4,200 and its MACD just crossed down, M15 "should go on down", support near 4,100.
- **Case A:** the market opens with a bounce into 4,185-4,200 (the range top and the trendline): sell once M15
  turns (a lower high, then a close below the last low); stop above 4,215 with a buffer; target 4,100, before the
  4,075-4,085 double bottom.
- **Case B:** price breaks 4,150 first: no chase; sell the retest of 4,150 from below when it holds as
  resistance (an M15 lower high under it); stop above that lower high.
- **No trade:** an H1/H4 close above 4,215, or chop between 4,150 and 4,185.

**Owner's answers (2026-10-17):** (1) the first screen both ways - H4 DOWN only, and H4 DOWN or RANGE - as two
variants; (2) the M15 trigger is the close beyond the last swing (Elder's previous-bar close as a later
variant); (3) both sides (the buy mirror at support in an up trend); (4) XAUUSD on M15 first, then the 8
symbols, and M5 as an entry timeframe too; (5) build it now as a separate setup that does not touch the others.

**The rule** (`setup_triple_screen`, `app/strategy/setups.py`; lane / research only, not offered by the scanner):

| Owner's idea | Measured rule | Parameter (default) |
|---|---|---|
| Screen 1, the tide | The H4 map with the trade; variant: also a ranging H4 | `screen_h4: with` / `with_or_range` |
| ... a range with lower highs | The H4 swings not against the trade (DOWN or a mixed phase for a sell) | `structure_tf: H4`, `structure_gate: not_against` |
| Screen 2, the wave | Read from the location below, not from the H1 state | `screen_h1: any` |
| The range top (A) / the broken level (B) | The pullback's extreme (the last swing before the break) within the read's tolerance of an H1 or H4 chart-read level, any role (resistance, flipped, or one it swept) | `pivot_level_tfs: [H1, H4]`, `pivot_tol_atr` (the read's 0.25 ATR) |
| Screen 3, M15 turns down | `structure.bos_choch` on the entry timeframe: the first close beyond the last confirmed swing (A: a change of character; B: a break of structure) | trigger |
| Stop above the lower high, with a buffer | Beyond the pullback's extreme by half an entry ATR (hypothesis 9) | `stop_mode: invalidation`, `stop_buffer_atr: 0.5`, `max_sl_atr: 20` |
| Target before the support | A quarter of an H4 ATR before the next H4 chart-read level, at least 1.5 R, at most 3 R | `target_mode: read_level`, `target_front_atr: 0.25`, `min_rr: 1.5`, `rr_target: 3` |

Not in version 1: the volume profile (POC 4,150-4,160; the system has none), the trendline as a level, the MACD
cross. Management: the system default (break-even at +1 R, trailing from +1.5 R) until a backtest says
otherwise.

**Test plan.** Variants TS-w (H4 `with`) and TS-r (`with_or_range`), each on M15 and M5 (M5: the bar-counted
settings rescaled, e.g. `cooldown_bars` 12 = 1 hour; `stop_buffer_atr` 0.85 = about half an M15 ATR). The
ladder: March 2026, then August 2026, then the year; the goal +0.15 R per trade. Backtests run in one account
with the active setups (owner, 2026-10-17; another session is building that mode), against the same account
without TS.

**Open points for the owner:** the entry window. The setups trade 07:00-20:00 UTC (14:00-03:00 Thai); the
Monday Asian bounce of case A (05:00-14:00 Thai) falls outside it.

### TS results, March 2026 (XAUUSD, TS alone; `research/2026-10-17-ts/`, outputs `data/backtests/ts/`)

One month is a screen, not proof. R per trade (net mixes lot sizes: a far stop opens the minimum lot above the
risk budget).

| Variant | M15: trades, win %, R/trade | M5: trades, win %, R/trade |
|---|---|---|
| TS-w (H4 map with the trade) | 1, 0 %, -1.000 | 1, 0 %, -1.000 |
| TS-r (with or ranging) | 3, 33 %, -0.340 | 3, 33 %, -0.312 |
| TS-rs (TS-r, the tide from the H4 swings) | 6, 33 %, -0.004 | 17, 24 %, -0.473 |
| TS-rn (H4 map not against: TRANSITION too) | 6, 33 %, -0.004 | 16, 25 %, -0.440 |
| TS-rt (TS-r, the level within 0.5 read ATR) | 3, 33 %, -0.340 | 8, 50 %, **+0.119** |

**Funnel of TS-r M15** (121 structure-break triggers in March): the pullback extreme was within 0.25 read ATR of an
H1/H4 level for 14 % (0.5: 24 %, 1.0: 46 %, 1.5: 63 %); the H4 map was TRANSITION at 79 % of the triggers (with
9 %, against 7 %, range 5 %); 39 % fell outside 07:00-20:00 UTC; the stop sat a median **3.3 entry ATR** away.

**Diagnosis (2026-10-17):** the structure-break trigger enters late, ~3 ATR after the pullback's extreme, with the
stop still beyond it: a wide stop and little room to the target. The owner sells *at* the zone once M15 turns,
with the stop just beyond it. Next: the rejection trigger (the pullback's extreme at a level, then the first
close beyond the previous bar's extreme; Elder's third screen at the zone; stop ~1.3 ATR in a 3-day sample),
both triggers recorded over the in-sample year and judged on M1 outcomes in both halves (`ts_study.py`) before
any rule goes into the setup.

### TS: the two-year study and the day-trade version (2026-10-17)

Every structure-break trigger of gold M15 over two years (in-sample 2025-10 .. 2026-09 and the out-of-sample
year 2024-10 .. 2025-09; 3,055 triggers), its outcome on M1 bars (`research/2026-10-17-ts/`). R per trade at 3 R
unless stated; "4/4" = positive in all four half-years.

| Rule | In-sample | Out-of-sample | Verdict |
|---|---|---|---|
| Every trigger | +0.090 | +0.092 | a small edge in both years |
| TS-n3: level <= 0.25 ATR, H4 map not against | +0.438 | +0.069 (2nd half -0.158) | **failed** out of sample |
| TS-n3c: + stop <= 4 ATR | +0.544 | -0.079 | **failed** |
| The rejection trigger (sell at the zone on the first close below the previous low) | +0.039 | not run | weaker than the break |
| D1 EMA tide (close beyond EMA50, EMA sloping the trade's way) | +0.180 over both years, 4/4; against it -0.003 | | the tide matters |
| D1 tide & level <= 0.5 ATR | +0.322, 4/4 | | |
| H4 EMA tide & level <= 0.5 ATR | +0.335, 4/4 | | as good as D1 |

- Gold rose ~2,650 -> 5,280 over these years: buys +0.221, sells -0.057 across all triggers. A rule that only
  buys rides that drift, so the tide must be able to turn (the EMA tide does: D1 was DOWN 68 % of Apr-Sep 2026).
- The backtest of the D1 version (TS-d1, 13 months run): +0.068 R/trade (135 trades); the losses came from the
  D1 sideways months (May-Aug 2025, -0.45) and the March 2026 top (D1 still up while gold fell: 11 buys stopped).
- **The owner's direction (2026-10-17):** day trading on small timeframes, short holds; the goal is at least one
  trade a day and >= 15 USD a day on a 100 USD account (1:2000). So the tide moves to H4 and trades close within
  the day. Study, H4 tide & level <= 0.5 ATR, every hour: held at most 12 h, 2 R: +0.195 (4/4, win 50 %); at
  most 8 h: +0.153 (4/4); closed the same day (entries to 18:00 UTC), 2 R: +0.220 (4/4). About 0.6-0.7 trades a
  day on gold. **TS-h4** (`config_ts_h4_m15.yaml`): H4 tide, level <= 0.5 ATR, stop 0.25 ATR, 2 R, at most 48 M15
  bars; being backtested month by month on gold and on the 8 symbols.
- **Against the daily goal** (gold, 0.01 lot): about +2 USD a day on average and >= 15 USD on about one day in
  eight; the worst days lose more than 100 USD. On a 100 USD account the 0.01 lot of gold risks ~20 % a trade
  (median stop ~20 USD); with the cage's 20 % ceiling and the aggressive profile's 2 x 7.5 % open-risk and daily
  limits most gold TS trades are refused (`RISK_BELOW_MIN_LOT`, March and August: 0 trades). FX stops cost
  ~1-3 USD per 0.01 lot, so the trade count for this account has to come from more markets.

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
7. **Risk per trade** on a small account: the owner's trades risked ~19 % (trade 2) and up to ~81-90 % (trade 1's
   averaging at its first stop); measure the growth and the worst drawdown at 2 %, 5 %, 10 % and 20 % a trade.
8. **Pattern confirmation:** reversal sells/buys before the neckline break against after it (and a partial or
   break-even at the neckline when entered early) - trade 2 had +40 USD at the neckline and ended -44.
9. **Stop buffer at a range edge:** a stop just past the edge (trade 3: 0.28 above the high, about one spread)
   against one 0.25 / 0.5 / 1 ATR past it - how often the edge is swept and price returns inside, and the R it
   costs.
6. **Break-even stop** once price moves: how often a tight break-even stop is taken by noise before the target
   (an M1 bar ~1.4 on gold) against a stop under the last M1 higher low.

## Status

- 2026-10-15: waiting for the real account's history report (`data/owner/`, HTML or XLSX).
