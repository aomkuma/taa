# Auditor notes (2026-10-17)

Scope: the research harness (fills, labels, features), the cost model against the ticks, data quality, and the
break-even table. Scripts in this folder; outputs `*.log`, `*.csv`, `tick_minutes.parquet`, `tick_sim.parquet`.

## 1. Simulator, labels, features

| Check | Script | Result |
|---|---|---|
| `ny_lab.M1.trade` on hand-made bars (BUY at ask+slip, SELL at bid-slip, SELL stop/target on bid+spread, both-in-bar = stop, break-even, time exit at bar hz-1's close, loser kinds) | `sim_checks.py` | all as specified |
| `exits.Path.run` (scalp, both-in-bar, hold with lock + trail) | `sim_checks.py` | as specified |
| Stored labels (`own_ml_long` y4/y6/y8, `own_ml_arsenal_labels` 5/4, 8/6, 10/8, 15/10) vs `M1.trade`, 3000 random rows | `label_checks.py` | 0 mismatches |
| M15/H1 features, ret1/ret15, spread in `own_ml_long` vs recomputation on bars truncated at the decision bar (60 rows) | `label_checks.py` | identical (no look-ahead) |
| `own_ml_cr_levels` (ChartReadFrame on the full series) vs ChartReadFrame on truncated bars (25 minutes) | `cr_check.py` | identical (no look-ahead) |
| `tick_features.py`, `confluence.py`, `zz_features.py` by reading | - | ticks strictly before t; M5/M15/H1 by close time <= t; day/Asia levels as of p-15 |

Minor issues (none changes a verdict):

- **Exact touches are float-sensitive.** `(adv - stop) * side <= 0` with `stop = entry - sl` in float: a SELL whose
  ask high equals the stop to the cent (103.63 + 0.30 = 103.92999999 vs 103.93) is *not* stopped. Exact touches of
  stop or target resolve by rounding noise. Fix: round levels/prices to 0.01 or compare with a 1e-6 tolerance.
- **Gap through a stop fills at the stop.** A bar opening beyond the stop fills at `stop - slip`, not at the open.
  Only matters across the daily break / weekend or big release jumps; the tick check below measures the real gap.
- **ATR's true range omits |prev close - low|** (`ml_dataset.py` `atr14`, so `atr1` in all datasets, used by
  confluence's level test and stop). Buggy/correct median 1.000, p1 0.969, min 0.70. Negligible.
- **Loser kind ignores the stop bar's favourable side.** A stop bar that also touched half the target is counted as
  kind 1. Confluence test: 2 of 210 stops. Negligible.
- `select()`/`run()` keep one row per minute with `drop_duplicates("t")` after an unstable sort: when both sides
  pass the rule in one minute, which side trades is arbitrary. Rare.

## 2. Costs vs reality (ticks 2025-10-01 .. 2026-10-14)

**Finding: the M1 `spread` column is the minute's MINIMUM spread** (matches the ticks' min spread in 100.0 % of
359k minutes; M1 OHLC = the ticks' bid OHLC in 100 %). The spread an entry pays (first tick of the minute) is
higher: median +0.08, mean +0.076 USD. So `ask = bid + spread` understates every ask by ~0.08 USD (BUY entries,
SELL stops/targets/time exits).

Real spread (first tick / per-minute mean, USD):

| | Asia 00-02 UTC | London 08:00-09:30 | NY 08:15-11:15 | 20-24 UTC |
|---|---|---|---|---|
| 2025-10 .. 2026-03 | 0.39 | 0.37 | 0.36 | 0.37-0.45 |
| 2026-04 .. 2026-10 | 0.39 | 0.29 | 0.30 | 0.37-0.45 |
| M1 column (min) | 0.25-0.29 | 0.23 | 0.23 | 0.25-0.45 |

0.39 is a cap (38 % of minutes sit exactly on it); 0.45 at the 22-23 UTC reopen. Around US releases the spread
hardly widens (max 0.39 at minute 0); the risk there is the price: the largest single tick jump at minute 0 is
median 2.97 USD (vs 0.6 a minute before).

Entry latency: price drift from the bar's first tick to +250 ms / +1 s in the trade's direction: mean +0.00
(p90 +0.16..0.21). The fixed 0.07 entry slippage is therefore conservative.

Stop fills on ticks (first tick at/beyond the stop): median 0.07, mean 0.15 (random rows), 0.13 (confluence),
0.40 (triple screen, fat tail), p90 0.33-0.44, p99 1.0-1.8. NY stops gap more (mean 0.20) than Asia/London (0.14-0.15).
The fixed 0.07 stop slippage is the median, not the mean.

Real round trip at 0.01 lot: about 0.33-0.39 (spread) for a target exit, 0.50-0.55 for a stop exit; average about
0.43 USD. The harness charges about 0.33-0.40.

## 2b. M1 vs tick simulation (`tick_sim.py`, `tick_sim.log`)

A = harness as used; B = M1 with the real ask; C = ticks with harness conventions (only the intrabar order
differs); D = ticks realistic (250 ms latency, no fixed slip, real stop gaps); E = D with 1 s latency.

| Sample | n | A USD/trade | B | C | D | E | D - A (se) |
|---|---|---|---|---|---|---|---|
| confluence test (r9, 8/var+BE) | 425 | -0.198 | -0.239 | -0.202 | -0.173 | -0.158 | +0.025 (0.069) |
| triple screen test (r5, 10/8) | 375 | -0.507 | -0.516 | -0.516 | -0.579 | -0.582 | -0.071 (0.141) |
| random rows 5/4 | 2500 | -0.145 | -0.204 | -0.178 | -0.164 | -0.183 | -0.019 (0.023) |
| random rows 8/6 + BE 0.6 | 2500 | -0.186 | -0.263 | -0.261 | -0.251 | -0.230 | -0.065 (0.025) |
| random rows 3/3 | 2500 | -0.304 | -0.396 | -0.350 | -0.300 | -0.301 | +0.004 (0.021) |
| random rows 10/8 | 2500 | -0.178 | -0.262 | -0.262 | -0.243 | -0.205 | -0.065 (0.027) |

- Min-spread column (A -> B): -0.04 .. -0.09 USD a trade (harness optimistic).
- Both in one bar = stop (B -> C): 0.2-1.7 % of trades; on ticks about 40 % of them were wins. Harness pessimistic
  by 0 .. +0.05 USD a trade (only visible for 3/3).
- Realistic fills (C -> D): no fixed entry slip (+0.07) but real stop gaps (-0.05) and BE armed at once on ticks.
- **Net, realistic vs harness: -0.07 .. +0.03 USD a trade = within about +-0.01 R.** Test totals: confluence
  -84.1 (A) vs -73.6 (D); triple screen -190.3 vs -217.0. No earlier verdict changes.

## 3. Data quality

Gold M1 (`gold.bars`): 1,802,466 bars 2021-09-01 .. 2026-10-14 08:18 (not 2020-09 as the brief says); no duplicate
times; no OHLC inconsistencies; 0.08 % zero-range bars; 137 bars with spread <= 0; old/new stores identical over the
30,022 overlapping bars and aligned in time (return correlation 1.000 at 0 h shift, ~0 at +-1..3 h). Daily break
~17:00-18:05 New York time (20:55-22:04 UTC in summer, 21:55-23:04 in winter), tracks US DST; the session windows
use ZoneInfo and are DST-correct; the release calendar's UTC times line up with the ticks (the price jump is at
minute 0). Other gaps: 148 (65 of 1-2 min; 46 of 1-10 h = US holidays' early closes; 2 Christmas). Spike bars (wick
> 8x the 4-hour median range): 330, all at news/real moves, no reverting bad prints found.

Ticks: 273 files, 101 M ticks, no out-of-order ticks, 6,657 exact duplicate rows (harmless; inflates tk_n by
<0.01 %), 2026-04-03 empty (Good Friday). Sunday-evening reopen (22-24 UTC Sun) not downloaded (weekday-only
loop): 5,123 M1 bars have no ticks. Single tick jumps >= 5 USD in 486 minutes (releases, the 22/23 UTC reopen).

FX majors (`fx_quality.py`): EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD, 2023-09 .. 2026-10-14,
~1.15 M bars each; no duplicates, no bad OHLC, ~1 % zero-range, short quiet-minute gaps only, holiday gaps.
Spread column (min) in pips flat across the day: EURUSD 0.8, GBPUSD 0.9-1.0, USDJPY 0.9-1.0, AUDUSD 0.9, USDCHF 0.9,
USDCAD 1.1, NZDUSD 1.2; rollover 21-22 UTC 2-5 pips. No FX ticks: the real spread is unknown; gold's real/min ratio
(~1.3) suggests ~+0.2-0.3 pip.

Cost vs movement (spread column / median M1 range, active hours 2026-04..): gold 0.07-0.09; FX majors 0.5-1.2.
FX majors are 7-15x more expensive than gold relative to their minute-scale movement.

Cost of price-scaled tools in older half-years: gold's spread stayed ~0.20-0.24 USD while the price halved, so an
8/6 tool scaled by price/4100 costs ~0.15 R a trade in 2023 vs ~0.07 R in 2026. Older half-years are a harsher
test of the same edge (by ~0.08 R a trade); not a bug, but compare gross R across periods.

## 4. Break-even (`breakeven.py`, `breakeven_gold.csv`, `breakeven_fx.csv`)

Gold, real average costs (spread 0.345, stop gap 0.17):

| tool tp/sl USD | coin win % | break-even win % | +0.15 R win % | edge needed over the coin | cost a trade (R) |
|---|---|---|---|---|---|
| 3/3 | 44.3 | 51.4 | 58.8 | 14.6 pts | 0.143 |
| 5/4 | 40.6 | 45.5 | 52.1 | 11.5 | 0.110 |
| 5/6 | 51.4 | 55.2 | 63.4 | 12.0 | 0.070 |
| 8/6 | 40.4 | 43.5 | 50.0 | 9.6 | 0.074 |
| 10/8 | 42.5 | 45.0 | 51.6 | 9.1 | 0.055 |
| 15/10 | 38.6 | 40.4 | 46.4 | 7.8 | 0.045 |
| 20/12 | 36.4 | 37.8 | 43.5 | 7.0 | 0.038 |

Raw-type account (spread ~0.10 + 6 USD/lot round turn): saves 0.02-0.06 R a trade (8/6: 0.043 vs 0.074 R) - it does
not make a coin-like signal pass (+0.15 R still needs 8 points over the coin at 8/6). FBS's own site (fbs.com,
FBS Markets Inc.) lists one account: no commission, floating spreads "from 0.7 pips"; a raw "Ultra" account (USD 6
per lot round turn) is listed by a review only for some markets (Australia); a review gives 0.30 standard / 0.10 raw
gold spreads. Sources: https://fbs.com/trading/conditions, https://fbs.com/ ,
https://www.compareforexbrokers.com/reviews/fbs/ (2026-10-12),
https://brokeranalysis.com/broker-review/fbs/gold-spread/ (2026-10-09). Not verified with FBS directly.

Majors (pips; EURUSD real assumed 1.0 + gap 0.2): 5/5 needs 18.6 pts over the coin (cost 0.22 R a trade), 10/8 12.9
pts (0.14 R), 15/10 10.5 (0.11 R), 20/15 9.7 (0.07 R). NZDUSD/USDCAD (1.5 pips): 10/8 costs 0.20 R a trade. Never
at 21-22 UTC (0.5-1.4 R a trade).

## Cheapest ways to cut losses (cost side), largest first

1. **Bigger tools / fewer trades.** Cost is ~0.43 USD a trade whatever the signal: 3/3 pays 0.14 R, 5/4 0.11 R,
   10/8 0.055 R, 15/10 0.045 R. A coin-like signal loses exactly its cost per trade, so the loss scales with the
   count of trades and with 1/stop.
2. **Hours.** Asia and 20-24 UTC pay 0.39-0.45 vs 0.29-0.33 in London/NY (2026-04..): ~0.06-0.10 USD (0.01-0.02 R
   at 8/6) a trade. Never trade 21-23 UTC (break and reopen jumps).
3. **Release minutes.** Spread does not widen, but tick jumps of ~3 USD at minute 0 (61 USD max) gap the stops;
   NY stops gap 0.20 on average vs 0.14 elsewhere.
4. Harness choices are second order: min spread (-0.04..-0.09 USD), 0.07 entry slip (+0.07 conservative), 0.07 stop
   slip (-0.05), both-in-bar (+0..+0.05, only for tiny tools). Net within +-0.01 R.
5. Account type: a raw account would save ~0.03 R a trade at 8/6; not offered on fbs.com's international site.
