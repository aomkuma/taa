# The trading day, end to end

The path a trading day takes through this system: preparing the data, the engine's own cycle, the gates a
signal passes before an order leaves, and what happens to each closed trade. Every name here is a real
symbol in this repository; where the text and the code disagree, the code is right and this file is wrong.

Agreed with the owner on 2026-10-28 from the drawn version of the same four stages. The six notes under
"What this means in practice" are the points the owner confirmed, including the two that are open faults.

## 1 Before the day trades

| Step | What it does | Where |
|---|---|---|
| History | closed bars per timeframe into Parquet, plus ticks for replays | `app/market_data/history_download.py`, `data/history/FBS-Demo/<symbol>/` |
| The machine | `app.cli doctor` at 0 failures; the terminal's **Algo Trading** switch pressed (it resets on a terminal restart); server clock, spread, free disk; the laptop kept awake | `app/cli/`, `app/core/clock.py` |
| Engine start | the account verified after every connect, the kill switch read, open positions restored and reconciled, each lane's warm-up bars demanded (`plan1` 10,000; `three_bots` 1,200) | `app/main.py`, `app/broker/verification.py`, `app/engine/reconciler.py` |
| The day's plan | at or after 07:00 Thai: every reading taken from the readers, never by eye, then written to `data/plans/<date>.md` and summarised to the owner before the day trades | `routine_read.py`, `rhythm_scan.py`, `picture_read.py`, `app/strategy/edge_side.py` |
| **The gate** | the plan must contain its condition, levels, side with the edge and scenarios. Missing, unreadable, empty or incomplete means no new broker order; open positions are still managed, because refusing to manage them is more dangerous | `app/risk/day_plan.py`, `app/risk/mode_gates.py` |

The trading day runs **07:00 Thai to 07:00 Thai**, so a plan written at 06:45 is filed under yesterday.

## 2 The engine's cycle, to one signal

`Orchestrator.cycle()` runs every few seconds. An exception is caught at the cycle's edge: entries stop, the
operator is told, and the engine keeps watching rather than dying.

1. `_drain_commands()` - commands from the cloud, which may only ever reduce risk.
2. `_check_kill_switch()` - a file's presence stops everything.
3. `ensure_connected()` - no link, no decision.
4. `_monitor_symbol()` - quotes, spread, and orders that wait for their price.
5. `_check_new_bar()` - the real work, and only on a closed bar.

On a new closed bar, per lane: closed candles plus `CandleWatermarks.is_new`, so a bar is evaluated **once**
even across a restart, and is marked even when the evaluation failed, so a failure cannot become a retry
storm. Then `_evaluate()` builds the lane's context, lets each strategy manage its own positions
(`on_bar` / `on_lane_bar`, `should_close`), evaluates the strategies and arbitrates down to **one** signal.
A strategy disabled from the cloud opens nothing while its closing signals still count.

Each strategy applies its own conditions before it offers a signal at all: the H4 lean on the trade's side
(`require_edge_side`), a signal at the level rather than the first touch (`app/strategy/confirm.py`), a stop
past the liquidate zone (`app/strategy/liquidity.py`), and checklist items C4, C6, C9.

The AI trader is the same path with a different author of the signal: the watcher wakes it on a closed M1
bar, it answers one step, the brakes veto or halve it, and what survives becomes a signal like any other
(`app/ai/watcher.py`, `app/ai/trader.py`, `app/engine/ai_trader.py`).

## 3 The ladder a signal climbs before an order leaves

`DecisionEngine.decide()` checks these groups in order. Any group failing means REJECT, and missing data or
an unclear state counts as failing - the system fails closed.

| Group | What it holds |
|---|---|
| `_system` | system health, data not stale, the risk values in force valid |
| `_mode` | **the mode gate**: the trading mode asked for, the enable flag, **the day's plan (P26)**, the account verified, the account's and terminal's trading permissions, the kill switch, latched breakers |
| `_preset` | the profile's preset matches what the strategy asked for |
| `_symbol` | the symbol's spec, tradable, allowed |
| `_data` | data fresh enough, price not drifted from the decided bar |
| `_session` | market open, the symbol's session, the signal not expired |
| `_costs` | spread under its ceiling, spread against the stop, slippage |
| `_geometry` | a stop on every trade - there is no "no stop" option - and the minimum reward-to-risk |
| `_size` | size from a percent of equity, floored never rounded up, the 0.01-lot minimum recorded and never a veto |
| `_portfolio` | position counts, one trade per symbol, correlation groups, and trades opened by hand counted too |
| `_budgets` | total open risk, heat, the config cage's ceilings |

ACCEPT goes to `backend.place()` → `ExecutionGateway` → `order_send`: a demo account in DEMO, a real account
in LIVE, and in PAPER no broker order is sent at all. Every decision is stored with its reasons, accepted or
rejected, so a quiet day can be explained afterwards.

## 4 After each trade closes

One set of events - `POSITION_OPENED`, `STOP_MOVED`, `POSITION_CLOSED` - feeds three paths at once.

- **Evidence:** `TradeAuditSink` appends to the hash-chained audit log, which the outbox carries to the cloud
  and the PWA shows as that trade's timeline. Append-only, stop moves included.
- **Numbers:** `broker_trades` holds each closed trade's R; `app/analytics/` reports and attributes it;
  `app/engine/forward_track.py` compares the forward mean R with the band its backtest expected;
  `demo-report` and `demo-track` summarise.
- **The journal a person reads:** the hourly observer's diary, the day's journal and ledger, the issue list,
  and the week's summary to the owner. Every trade **and** every signal the checklist turned down, with what
  it would have made. The report's four required parts are in `docs/TRADER_ROUTINE.md`.

A lesson then goes, in the same change, into the decision checklist, a permanent acceptance case, a memory
and `app/strategy/kb.yaml`. It does not become a rule that day: a shadow is recorded and measured forward
for at least four weeks before it decides anything, a failed method is kept with its lesson rather than
retried as it was, and a rule measured to cost money is deleted.

## What this means in practice

1. **The plan gate checks words, not judgement.** `DayPlan.check()` asks whether the four sections are
   present; it cannot tell whether the plan reads the market correctly. The quality of the plan is the
   writer's responsibility.
2. **The larger-timeframe edge is enforced on three strategies only** - `trend_box_down`, `trend_box_up`
   and `range_break`. The four PLAN-1 strategies can still enter without it, although the owner's rule says
   every trade. Switching it on for them requires raising the `plan1` lane's warm-up bars in the same
   change, or the registry refuses to start. **Open fault.**
3. **Nothing stops a losing run.** The loss breakers are deactivated by the owner's decision of 2026-10-27;
   what bounds a loss is each trade's stop, the risk per trade, the position limits and the kill switch. Two
   positions at 7.5 % is about 15 % of equity at risk. **Open, and the owner's call.**
4. **Signals come from code today.** The AI trader is configured off and exists as a replay path.
5. **PAPER sends nothing.** Not sent-and-ignored: `order_send` is never called. DEMO sends to the demo
   account.
6. **Trades opened by hand use the bot's quota.** They count in the portfolio group, so a large manual
   position can leave the bot opening nothing all day.
