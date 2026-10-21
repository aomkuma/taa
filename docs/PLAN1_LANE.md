# PLAN-1 as a lane (`plan1`)

Owner (2026-10-21): "do everything in parallel - the research journal, the backtest and the bot". Until now PLAN-1
lived only in research code (`research/2026-10-18-moments/agents/dev/plan1.py`, the journal's rules in
`agents/journal/PLAN1_JOURNAL.md` / `rules_week.py`). This note says how the bot (`app/`) runs it, piece by piece, so
the bot learns with the journal: every journal rule is a parameter of the lane in `config.yaml`.

## The pieces and their order

| Piece | Where | State (checkpoint A, 2026-10-21) |
|---|---|---|
| London 13:00-Thai ORB | `app/strategy/plan1.py` `Plan1Orb` (`setup_plan1_orb`), closed M1 bars | built, PAPER-ready, disabled |
| NY 08:30 straddle, every weekday | `app/strategy/plan1.py` `Plan1Straddle` (`setup_plan1_ny`), quotes | built, PAPER-ready, disabled |
| Asia B2 (07:00-09:00 Thai) | research `dev/patterns.py`, `p2/p3/p4_trades.py`, `precursors/zones.py` | checkpoint B (below) |

The lane (`config.yaml` `lanes: - name: plan1`) trades XAUUSD on M1 with H4 as its higher timeframe, 3,000 warm-up
bars (15 complete H1 bars and yesterday's server day across a weekend), no cooldown (one position at a time comes
from `risk.max_positions_per_symbol: 1`, as the research's stream), no break-even / trailing, a spread-to-stop
ratio of 0.5 (the research has no spread rule). Both items are `enabled: false`; PAPER only once the measurer
turns them on. The XAUUSD session now opens at 06:00 UTC (was 07:00) so the 13:00-Thai ORB can be decided; the
other gold lanes have their own windows inside it (and every other gold setup is stopped). A per-lane session
window would be the cleaner fix later: the sessions are one global table today.

**The lane's spread cap** (`max_spread_points: 60`, a lane field: `AppConfig.spread_limit_for` in the decision
engine, and the lane's own view for a lane backtest). Measured on the P1 / P2 ticks (`dev/plan1_spreads.py`,
`out_plan1_spreads.txt`): at the bot's 219 fills (and the trigger tick, and the 30 s before) the spread was at most
39 points (0.39 USD; p99 / p95 / median 39); between 08:29 and 08:31 New York on every weekday at most 53 (2025-11-28,
the day of the CME outage), p99 39; whole days up to 163. The symbol cap (40) would have refused nothing in the
learning parts, but 53 shows the release minute can pass it, and the research has no spread rule: 60 sits above the
observed maximum. The spread at the decision quote is in the journal record (`spread`). Not lane-aware yet: the
SPREAD breaker (a spread above the symbol cap for 30 s) and the DEMO / LIVE pre-send check use the symbol cap;
PAPER does not send orders, and a release spike lasts seconds.

## The journal rules as parameters

| Journal rule | Parameter (default) |
|---|---|
| Week 5: ORB target 1.5 R (was 2 R) | `setup_plan1_orb.target_r: 1.5` |
| Weeks 2 / 6: the VOL-16 ceiling and the ATR floor of 12 deleted | `atr_floor: null` on both pieces (a number refuses trades under it) |
| Week 10: in a contracting H4 ATR (24 h) the ORB needs a pool break | `pool_break_when_h4_contracting: true`, `h4_change_bars: 6`, `pool_break_minutes: 15`, `h4_contracting_max_pct: 0.5` |
| The straddle: 2 / 8 USD, out at 08:30 + 30 min, no target | `setup_plan1_ny`: `trigger_u: 2`, `stop_u: 8`, `hold_seconds: 1800`, `target_cap_u: 100` (a far cap the risk checks need) |
| ORB shape | `orb_open: "13:00"` (`orb_zone: Asia/Bangkok`), `range_minutes: 15`, `entry_minutes: 60`, `late_open_minutes: 5`, `wide_atr: 1.5`, `hold_minutes: 60` |
| Week 6: Asia B2's second trade only in the first's direction | checkpoint B (`b2_second_same_side: true`) |

## London ORB (closed M1 bars)

Research `d1_orb.decide` + `plan1.orb_trade`, ported 1:1 in `orb_decide`:

- `t0` = 13:00 Thai = 06:00 UTC. The day counts when its first M1 bar at / after `t0` opens within 5 minutes.
- The range = high / low of the M1 bars opening in [first bar, `t0` + 15 min); skipped when wider than 1.5 x the
  H1 ATR at `t0`. The H1 ATR is MT5's ATR(14) (the simple average of 14 true ranges) of H1 bars built from the
  M1 bars on the UTC hour, the last complete by `t0` - exactly the research's `Market.H`.
- The entry: the **first** M1 close beyond the range among the bars opening in the 60 minutes after it, decided at
  that bar's close; a buy at the ask, a sell at the bid. Only that bar decides (a later bar holds with "broke
  already").
- The stop at the range's other side; the target 1.5 R of the decision price; out at the close of the M1 bar 60
  minutes after the entry minute (`manage_position`).
- Week 10: when the H4 ATR(14) (closed broker H4 bars) changed by less than +0.5 % against its value 6 H4 bars
  earlier (the journal's reading, kept by the measurer 2026-10-21: `liq_journal` rounds the change to a whole
  percent and `rules_week` skips at <= 0, so +0.4 % counts as contracting; `h4_contracting_max_pct: 0` would be
  the strict "latest <= earlier", which skips only 10 of the journal's 12 days in weeks 1-9), the trade needs
  the 15 minutes of closed M1 bars before the decision to have broken a pool in its direction (a buy: the window
  opened below the pool and traded above it; a sell mirrored). Pools as `liq_journal.pools`: yesterday's server-day
  high / low, the Asia range 00:00-07:00 Thai, today's server-day open, the last confirmed M15 3-bar fractal swing
  high / low. An unknown H4 ATR counts as contracting (fail closed).

## NY straddle (quotes, S2's machinery)

`Plan1Straddle` subclasses S2's `OwnS2`, so the live engine treats it as S2 already: the orchestrator finds it as a
quote lane, attaches the release calendar at start, polls quotes every 0.1 s while `busy` (08:29:25 .. 08:31:00
New York each weekday) and sends each quote to `on_quote`; an entry goes the bar path's way (the decision engine,
sizing, the PAPER broker). What changes against S2:

- `DailyStraddle` (S2's `ReleaseStraddle` planner) arms at 08:30:00 New York on **every weekday** (DST-aware);
  the calendar only names the day's release in the journal record.
- The triggers and the stop are USD (1 U = 1 USD: `unit()`), not price / 4,000: a buy stop 2 USD above the last
  ask before 08:30, a sell stop 2 USD below the last bid, live 60 s, the stop 8 USD.
- Out at the first bar close at / after 08:30 New York + 30 minutes (from the release, not from the fill).
- S2 itself is unchanged (`unit()`, `new_planner()`, `busy_between()` are hooks with S2's old behaviour).

## The journal record

Every entry (and every refusal by `atr_floor` / the pool-break rule) carries its checklist in `Signal.conditions`;
the decision log stores it, and a backtest writes it to `journal.jsonl` next to `trades.csv`:

| Condition | ORB | Straddle |
|---|---|---|
| `rule` | the first close beyond the range, the bar | the crossed trigger, the time |
| `h1_atr` | MT5 ATR(14) of the last closed H1 bar; the floor | same |
| `opening_range` | low-high, width against 1.5 x the H1 ATR at 13:00 Thai | - |
| `release` | - | the calendar's release at 08:30 or "none" |
| `pools` | yesterday high / low, Asia high / low, today's open, M15 swing high / low | same |
| `h4_atr_change` | the H4 ATR's 24-h change, contracting / expanding | - |
| `pool_break` | the pools the 15 minutes broke (or none); passed / failed | - |
| `stop_distance` | USD to the range side; the target in R | 8 USD; no target |
| `spread` | the decision quote's spread (USD, points) | the trigger tick's spread |

## The backtest

`app.cli backtest --lane plan1 --strategies setup_plan1_orb,setup_plan1_ny --ticks data/ticks ...`. With
`--ticks` the engine steps the broker on the stored ticks (`app/market_data/tick_store.py`) in every minute where a
quote strategy arms or trades, or a position / order is open; elsewhere on M1 bars. So both pieces fill and exit
as the research simulates them: a market order at the first tick after the decision, the stop at the crossing tick
(gap included), the target at its price, a close at the first tick after the request. A bar-close decision reads
the bar's last tick as its quote (as live), so the ORB's 1.5 R target is set from the price it fills near. The
straddle is decided on
the trigger tick and fills on the next tick (the live engine cannot fill on the tick it reacts to); its stop stays
8 USD from the trigger tick's price, as the research's.

Parity with the research on P1 / P2: `research/2026-10-18-moments/agents/dev/plan1_parity.py` (`out_plan1_parity.txt`).

Result (2026-10-21, rule-off run, slippage 0): 219 / 219 trades on the same days and sides (ORB 59 + 60, straddle
41 + 59); ORB entries to the tick, exits identical but for 1 target-vs-time case (the target anchored to the
decision tick, not the fill); 195 of 219 within 0.05 R. The straddle's differences are the fill: the research
fills on the trigger tick, the bot on the next tick (as live), up to 8.6 USD apart on a fast release (2026-04-10).
With the week-10 rule on, the ORB skips exactly the journal's 12 days in weeks 1-9 (`out_plan1_parity_h4.txt`).

## Asia B2 (checkpoint B): what porting needs

B2 is research code over about 1,200 lines; each part needs its own port, hand-worked tests and a parity check
against `plan1_every_learn_s0_x0.parquet`'s Asia B2 rows (79 trades on P1 + P2):

1. The causal ATR ZigZag per timeframe (`patterns.zigzag`, swing = 2 x ATR(14)) on M1 and M5 built from M1 bars.
2. The owner's H1 levels (`precursors/zones.levels_at`, about 240 lines: the H1 swing reads, the zone of
   +- 0.1 H1 ATR, the sweep allowance of 0.5 H1 ATR).
3. The pattern families at a level (`patterns.locate`): inverse H&S, W (and W whose second low swept the first),
   the sweep then the higher low, a base then its break; mirrored for sells; the breakout at the first close beyond
   the trigger; the height cap of 4 x the TF's ATR.
4. The agreement: an M1 entry needs an M5 pattern, an M5 entry an M1 pattern (`patterns.agree`).
5. B2's candidate rules and its exit (`p3_trades.candidates3`, setting `B2`: exit on the entry TF's structure).
6. The Asia window: decisions 07:00-09:00 Thai (00:00-02:00 UTC) and the week-6 rule (a second trade of the
   morning only in the first one's direction) - the only piece with memory across trades in a day, so it needs
   the lane's own trades of the day (a restart-safe reading: the day's positions from the broker / decision log).

The ZigZag and the levels are the heavy, stateful parts; they come first, with mutation tests (a change to a
later bar must not change an earlier output).

## Ticket proposal

**TAA-OWN-P1 - PLAN-1 lane `plan1` (PAPER).** Checklist:

1. [x] Design note (this file).
2. [x] London ORB on closed M1 bars (`Plan1Orb`) with the journal record; target 1.5 R; `atr_floor` (off).
3. [x] Week-10 rule: in a contracting H4 ATR the ORB needs a pool break (parameter, default on).
4. [x] NY 08:30 straddle every weekday on S2's quote machinery (`Plan1Straddle`), USD triggers, out at 08:30 + 30 min.
5. [x] Backtest quote path (`--ticks`): quote strategies and tick-level fills; `journal.jsonl`.
6. [x] Parity with the research trades on P1 / P2 (ORB at 1.5 R, straddle), every difference explained.
7. [x] Hand-worked unit tests, planted bugs, frontend strategy names (TH / EN).
8. [ ] Asia B2: ZigZag, H1 levels, patterns, M1 / M5 agreement, B2 exit, the Asia window, the week-6 rule.
9. [ ] Parity of B2 and of the whole lane (one position at a time) against `plan1_trades_learn_s0_x0.parquet`.
10. [ ] PAPER run on the real FBS demo terminal (read-only quotes), the journal read back from the decision log.
