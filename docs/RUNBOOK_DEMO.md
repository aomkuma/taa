# DEMO runbook: broker orders on the demo account (Phase 12)

The engine sends real orders to the **FBS demo account** in DEMO mode. Real money (LIVE) has its own path behind
the live gate, off by default: see [RUNBOOK_LIVE.md](RUNBOOK_LIVE.md) before ever switching it on. The strategies are demonstrations; a demo soak tests the *machinery*
(orders, stops, reconciliation, breakers), not whether a strategy makes money.

## 1. Before the first start

1. Backtest on real history first (`scripts/download_history.py`, then `python -m app.cli backtest`). If
   the result is unusable, there is no point watching it fail live.
2. `.env`:
   - `TRADING_MODE=DEMO`
   - `ENABLE_DEMO_TRADING=true`
   - the demo login with its **master** password (the investor password cannot trade)
   - `KILL_SWITCH_FLATTEN_ALLOWED=true` only if you want the FLATTEN drill (step 5)
3. In the bot terminal (`C:\MT5\taa-bot`): press **Algo Trading** (it must be on) and check Tools → Options
   → Expert Advisors → "Disable automatic trading via external Python API" is **off**.
4. `python -m app.cli doctor` must report 0 failures. It confirms the account is DEMO; DEMO mode refuses any
   other account.
5. Start small: keep one or two symbols in `config.yaml` → `symbols.allowed`, and set the risk in the PWA →
   Trading profile (risk per signal 0.25–0.5 % to begin). `config.yaml` → `risk` is only the machine's hard
   ceiling (PLAN §A33, 2026-10-06).

## 2. Start, watch, stop

| Action | Command |
|---|---|
| start | `.venv\Scripts\python -m app.main --mode demo` |
| health | `http://127.0.0.1:8765/health` (200 = running and connected) |
| events | `logs\events.jsonl` (one JSON line per event; CRITICAL ones first) |
| halt new entries | `.venv\Scripts\python -m app.cli kill --reason "..."` (positions stay managed) |
| release | `.venv\Scripts\python -m app.cli kill --release --reason "..."` (local only) |
| stop | Ctrl+C (the heartbeat records a deliberate stop; the watchdog leaves it alone) |
| report | `.venv\Scripts\python -m app.cli demo-report --days 14` |
| breakers | `.venv\Scripts\python -m app.cli breaker list` |
| reset one | `.venv\Scripts\python -m app.cli breaker reset DUPLICATE_EXECUTION --reason "..."` (`--ack` for MAX_DRAWDOWN, `--symbol` for symbol breakers) |

## 3. What happens to an order

1. A closed bar produces a signal; the decision engine checks every A8 rule and the DEMO gate.
2. The intent is written to `order_intents` **before** anything is sent (write-ahead), then `order_check`.
3. Right before `order_send` the engine re-checks the kill switch, breakers, connection, quote, spread and
   signal expiry.
4. The result follows the retcode matrix (PLAN §A12). An answer that is missing or unclear makes the order
   UNKNOWN: nothing is resent, DUPLICATE_EXECUTION trips, and the reconciler searches the account.
5. After a fill: slippage is checked; risk above plan is reduced; a position without its stop gets it back
   or is closed (UNPROTECTED_POSITION trips).
6. Break-even, trailing, the time stop and strategy close signals are sent as SL/TP changes or closes.

## 4. Two-week soak: what to check

Run it for two full trading weeks, including at least one news day and one weekend restart. Each day:

- [ ] `demo-report` shows **every order in a final state** (no NEW/SENDING/UNKNOWN/UNPROTECTED left).
- [ ] No UNPROTECTED_POSITION or DUPLICATE_EXECUTION trip (if one happened: read §5 before resetting).
- [ ] Every bot position in the terminal has a stop-loss.
- [ ] Positions in the terminal match the report (magic `7310000`+, comment `taa:...`).
- [ ] Slippage stays within `risk.max_slippage_points` on average.
- [ ] A restart (stop and start) sends nothing twice.

Drills, once each:

- [ ] kill switch HALT: no new orders, open positions still managed
- [ ] kill switch FLATTEN (with `KILL_SWITCH_FLATTEN_ALLOWED=true`): every bot position closed
- [ ] pull the network for > 15 s: CONNECTION trips, then recovers after reconnecting
- [ ] stop the engine with a position open, start it again: the position is recognised, nothing is resent

`demo-report` exits with code 0 when its acceptance checks pass and 3 when one fails.

## 5. When something is wrong

| Symptom | What it means | What to do |
|---|---|---|
| ORDER_UNKNOWN event | `order_send` gave no usable answer | Wait 30 s: the reconciler marks it RECONCILED or NOT_EXECUTED. Check the terminal, then reset DUPLICATE_EXECUTION with an operator and a reason. |
| POSITION_UNPROTECTED | a position had no stop and could not get one | Check the terminal at once; close by hand if the engine could not. Reset only after understanding why. |
| kill switch activated by the engine | the server answered NO_MONEY, autotrading disabled, or an account-mode conflict | Fix the terminal or account, then release the kill switch locally. |
| SYMBOL_RESTRICTED | the server said trade disabled / market closed / long-only for a symbol | It resets after `execution.symbol_pause_minutes`. Frequent trips: check the symbol's schedule. |
| ORDER_FAILURES | 3 failed sends in 15 minutes, or the server asked to back off | Read `order_intents.retcode_desc` and the logs; usually a config or symbol problem. |
| ACCOUNT_CHANGE | another account, or a bot-magic position with no intent | Do not reset until you know where the position came from. |

Manual breaker resets are local and audited (actor and reason); MAX_DRAWDOWN also needs an acknowledgement.
