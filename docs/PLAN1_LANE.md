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
| Asia B2 (07:00-09:00 Thai) | `app/strategy/plan1_b2.py` `Plan1B2` (`setup_plan1_b2`, M1 patterns) and `Plan1B2M5` (`setup_plan1_b2m5`, M5 patterns), closed M1 bars | built (checkpoint B), disabled |

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
| Week 6: Asia B2's second trade only in the first's direction | `setup_plan1_b2` / `setup_plan1_b2m5`: `second_same_side: true` |
| Week 16 (deleted after one week): the straddle stop max(8 USD, 0.25 H1 ATR) | not ported: the stop stays 8 USD |

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

## Asia B2 (checkpoint B)

Ported 1:1 from the research B2 that `plan1_trades_learn_s0_x0.parquet` holds (`dev/patterns.py`, `p2_trades.py`
`confirm_b` / `structure_exit_time`, `p3_trades.py` setting `B2`, `p4_trades.py` `window_of`,
`precursors/zones.py` `levels_at`) into `app/strategy/plan1_b2.py`:

1. **The causal ATR ZigZag** (a swing = 2 x MT5 ATR(14)) on M1, and on M5 bars built from M1 on the clock.
   The strategy reads a 10,000-bar M1 window, not the history since 2025-09-01: at 300 random M1 closes in P1 / P2
   the window's ZigZag structure (the last six pivots and the running extreme) equals the full-history one on
   M1 and M5 every time (`dev/plan1_b2_parity.py readings`, `out_plan1_b2_readings.txt`).
2. **The patterns** breaking out at bar d: inverse H&S / H&S, W / M (and the swept one), the sweep then the higher
   low / lower high, a base then its break; sells by the mirror; no taller than 4 x ATR; the stop 0.2 ATR beyond
   the extreme.
3. **The owner's H1 levels** known at d's close: zones of 3+ or flipped H1 fractal swings (k = 2, merged within
   0.25 H1 ATR over the last 120 H1 bars), of 2 swings, the five-day high / low, the previous server day's high
   / low, the latest swing top above / low below the price; a stronger level within the tolerance drops a
   weaker one. H1 / D1 bars are built from the M1 window (avail = the last M1 bar + 1 minute, as the research)
   and only those whose hour / server day is over by the evaluation count. The readings check found 2 of 300
   samples different, both at 21:55 UTC: the research's full-history bars know that trading stopped for the
   daily break at 21:54 (the hour and the server day "complete" at 21:55), the bot at 21:55 cannot. B2 never
   decides then: it reads the levels at its confirmation (00:00-02:00 UTC), when those bars are over in both.
4. **At a level:** 'at' (the extreme within 0.1 H1 ATR), 'swept' (past it by at most 0.5 H1 ATR, the close back),
   'base' (the box overlaps the zone); the sweep-turn needs 'swept'; the nearest level wins.
5. **Confirmation B:** a pullback of 1 ATR from the post-breakout high, then the first close above it, within 30
   bars; none if a low touches the extreme first. The entry is that bar's close, inside 07:00-09:00 Thai; the
   candidate with the smallest risk wins (the score is 100 - the risk, so the arbiter keeps the research's order
   between the M1 and the M5 strategy).
6. **The target** is the next level beyond the entry (more than one zone away, not the pattern's own) if it is
   more than one risk away, else a far cap (10 R; the risk checks need a take-profit, and a B2 stop can be 90 USD wide). **The exits:** the
   structure exit at the first entry-TF bar closing beyond the last confirmed swing low (a buy) / high (a sell),
   and out after 60 entry-TF bars (M1: 1 hour, M5: 5 hours).
7. **The agreement** with the other timeframe is recorded (its ZigZag structure), not required: the research's B2
   setting does not filter on it.
8. **Week 6:** a second B2 entry of the Thai morning only on the side of the morning's first. The engine hands
   the B2 entries of the last day to both B2 strategies before each evaluation (`BaseStrategy.entry_group` /
   `attach_entries`): live from the decision store (`DecisionStore.accepted_entries`, the ACCEPT records), in a
   backtest from the run's accepted entries - never from the strategy's memory, so a restart does not forget the
   morning.

Two strategies (M1 and M5) instead of one: a position's own timeframe must be known for its structure exit after
a restart, and the strategy name (its magic number) is what survives. The lane's warm-up is 10,000 M1 bars (125
complete H1 bars across a weekend).

**The journal record** of a B2 entry: `rule` (the pattern, its breakout, the pullback and the confirming close),
`h1_atr`, `level` (price, kind, at / swept / base, the zone, the next level), `pattern` (its points with times,
the extreme, the height), `agreement` (the other TF's structure), `pools`, `h4_atr_change`, `second_trade` (the
week-6 reading: the first of the morning, or the first's side and time), `stop_distance` (and the target or none),
`spread`.

## The regime switch (CHECKLIST row 62)

No new entry in any piece while the D1 ATR(20) is below `d1_atr20_min_usd` (60 USD; `null` = off): MT5's ATR (the
mean of 20 true ranges) of the broker's server-day D1 bars, built from the lane's H1 frame, a day counted from its
server midnight + 24 h on (`journal/regime_switch.py`). Too few closed days (under 20) = no trade (fail closed).
Every entry's journal record carries it (`regime`: the value and trade / no new entry). On P1 / P2 it changes
nothing (the lowest value there is 60.1): the lane parity below has every research trade.

## Parity of the whole lane (checkpoint B)

`dev/plan1_b2_parity.py lane` (`out_plan1_lane_parity.txt`): the four strategies in one account, the rules in force
from the start (the ORB 1.5 R and the week-10 pool rule, B2's week-6 rule on for the check, the regime switch on),
against `plan1_trades_learn_s0_x0.parquet` with the same rules applied (`research_lane()`):

| Piece | Part | Research | Bot | Same trade | Same side | Same exit | within 0.05 R | Research R | Bot R |
|---|---|---|---|---|---|---|---|---|---|
| Asia B2 | P1 | 35 | 35 | 35 | 35 | 35 | 35 | +4.36 | +4.36 |
| Asia B2 | P2 | 35 | 35 | 35 | 35 | 35 | 35 | +6.96 | +6.96 |
| London ORB | P1 | 42 | 42 | 42 | 42 | 42 | 42 | +13.43 | +13.54 |
| London ORB | P2 | 41 | 41 | 41 | 41 | 41 | 40 | +12.75 | +13.02 |
| NY straddle | P1 | 41 | 41 | 41 | 41 | 41 | 30 | +19.14 | +18.25 |
| NY straddle | P2 | 59 | 59 | 59 | 59 | 59 | 50 | +7.01 | +5.92 |

Nothing in one only. The differences: one ORB target set from the decision tick (2026-02-26), and the straddle's
fills one tick after the trigger (as live). Two earlier differences were found and fixed on the way: an H4 frame in
the lane made every Monday-morning B2 entry DATA_STALE (its last bar is Friday's; the H4 ATR is now built from M1,
the lane's higher timeframe is H1), and a B2 take-profit cap of 150 USD cut a trade with an 88-USD stop (the cap is
now 10 R).

## The plan1 DEMO (prepared, not started)

Owner, 2026-10-21 ~20:00 Thai: plan1 is the only enabled lane on the FBS demo account (F1 / S2 off), 3 % a trade
with the 0.01 minimum lot. `config.yaml` already has: lanes `own` / `news` off, the four plan1 strategies on,
B2's same-side rule on (the frozen rules, CHECKLIST 61-63; the journal deleted it in week 29 - a switch), the regime switch on. The owner's DEMO now runs from its own worktree (C:\Users\korap\taa-demo at aa59c7a); this section is the reference for moving it to this code. Still to set **by the owner** (account / risk):

1. `config.yaml` → `risk`: `min_lot_fallback: true` and `min_lot_max_risk_percent: 20` (the cage that lets the
   0.01 lot open when 3 % buys less; the PWA profile must also switch "minimum lot" on). On a 50-100 USD account
   the 0.01 lot risks 8-16 USD on the straddle's 8-USD stop, more on a wide B2 stop: decide the cap.
2. `risk.max_account_drawdown_percent` (10) and `MAX_ACCOUNT_DRAWDOWN_PERCENT` in `.env`, `max_daily_loss_percent`
   (10), `max_consecutive_losses` (4, then a 24-hour pause): with min-lot trades of 10-20 % each, the 10 %
   drawdown latch (MAX_DRAWDOWN, manual reset) trips on the first loss. Decide them before the start.
3. PWA → Trading profile: Standard mode (the aggressive preset's `high_risk.setups` does not list the plan1
   strategies), risk 3 % per signal, the minimum lot on.

Checklist (docs/RUNBOOK_DEMO.md §1):

- [ ] the demo login with its master password in `.env`; `MT5_SERVER=FBS-Demo`; `TRADING_MODE` stays `PAPER` in
      `.env` (the start script sets DEMO and `ENABLE_DEMO_TRADING=true` for the engine process only)
- [ ] the bot terminal: Algo Trading on; "Disable automatic trading via external Python API" off
- [ ] `.venv\Scripts\python -m app.cli doctor` - 0 failures, the account is DEMO
- [ ] `$env:TAA_MT5_TESTS="1"; $env:TAA_MT5_TRADING_TESTS="1"; .venv\Scripts\python -m pytest -m mt5 tests/integration/test_mt5_terminal.py` (order_check only)
- [ ] the terminal has 10,000 M1 bars of XAUUSD (B2's warm-up) and 10,000 H1 bars (the regime switch)
- [ ] items 1-3 above decided and set
- [ ] start: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo-tasks.ps1 -Resume` (the stack was
      paused 2026-10-19; it starts web, worker and the engine with `-Mt5 -Demo`), or in windows:
      `scripts\start-demo.cmd -Mt5 -Demo`
- [ ] health `http://127.0.0.1:8766/health`; `logs\events.jsonl`; the engine log shows lane plan1 with its four
      strategies and the straddle armed at 08:29:25 New York
- [ ] after the first trades: `.venv\Scripts\python -m app.cli demo-report --days 1` (every order final, every position with
      its stop); the journal record in the decision log
- [ ] stop / pause: `scripts\demo-tasks.ps1 -Pause`; halt new entries: `.venv\Scripts\python -m app.cli kill --reason "..."`

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
