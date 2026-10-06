# LIVE runbook: real money (Phase 14)

LIVE sends orders with **real money** to a real FBS account. The path exists since TAA-1401 and is **off by
default**. Switch it on only after this whole checklist, and only with the owner's explicit decision on the
day. The strategies are unproven (PAPER and DEMO results describe the past and are no forecast); LIVE risks
the money on the account.

Read [RUNBOOK_DEMO.md](RUNBOOK_DEMO.md) first: LIVE uses the same order path (write-ahead intents,
reconciliation, protection, retcode handling) and the same commands.

## 1. Go-live checklist

Tick every line, write the date, and keep this file's copy with the ticks.

**Evidence**

- [ ] The DEMO soak (RUNBOOK_DEMO §4) ran two full weeks; `demo-report --days 14` exits 0.
- [ ] Analytics (PWA → Analytics) for PAPER and SHADOW was reviewed. No "restrict this segment" recommendation
      is still open for a strategy you leave enabled.
- [ ] The strategies you keep are enabled in `config.yaml`; the others are off.

**Account and money**

- [ ] A real FBS account funded only with money you can lose entirely.
- [ ] `config.yaml` → `risk` (the machine's cage) is set for this account. The Trading profile in the PWA sets
      the values used inside it. Start low: 0.25–0.5 % per trade.
- [ ] Probation: `risk.probation_trades` / `probation_multiplier` (default the first 20 trades at ¼ risk).
- [ ] Manual trades on the same account count toward the bot's limits (`risk.foreign_positions_policy`).
- [ ] The entry split is the one you want for real money (PWA → Trading profile → Splitting an entry; "Risk
      limits in use" shows what the bot follows). A split plan places resting limit orders for up to 4 hours
      (`execution.limit_lifetime_bars`); `execution.entry_plans: false` makes every signal one order.

**Machine** (a Windows VPS is recommended)

- [ ] A dedicated portable MT5 terminal logged in to the **real** account with its master password.
      **Algo Trading** on; "Disable automatic trading via external Python API" off.
- [ ] `MT5_PASSWORD` in Windows Credential Manager (`keyring:<service>/<name>`), not plain text
      (SECURITY_REVIEW §5).
- [ ] `.env` and `data\` readable only by the engine's Windows user; disk encrypted; the system clock synced.
- [ ] Its own engine database: `ENGINE_DB_URL=sqlite:///data/taa_engine_live.db` (DEMO intents and the
      probation count stay separate).
- [ ] `pip-audit` and `npm audit` clean (SECURITY_REVIEW §2).

**Configuration** (`.env`)

```
TRADING_MODE=LIVE
ENABLE_LIVE_TRADING=true
LIVE_TRADING_CONFIRMATION=I-ACCEPT-LIVE-RISK-<your real MT5 login>
MT5_LOGIN=<real login>
MT5_SERVER=<FBS real server>
MT5_PASSWORD=keyring:taa/mt5-live
ENABLE_DEMO_TRADING=false
KILL_SWITCH_FLATTEN_ALLOWED=true
ENGINE_DB_URL=sqlite:///data/taa_engine_live.db
```

- [ ] `python -m app.cli doctor` (real terminal) reports 0 failures and a REAL account.
- [ ] The real-terminal contract tests passed on this machine with the DEMO login (they call `order_check`
      only, never `order_send`): `$env:TAA_MT5_TESTS="1"; $env:TAA_MT5_TRADING_TESTS="1"; .venv\Scripts\python -m pytest -m mt5 tests/integration/test_mt5_terminal.py`. FakeMT5 cannot catch quirks of the
      real module: on 2026-10-06 every DEMO `order_check` failed until `MT5Client.call` was fixed.
- [ ] All drills in §2 done on this machine within the last 7 days.

## 2. Drills

Do each drill on the LIVE machine. Do them first with the DEMO login (`TRADING_MODE=DEMO`), then the kill
switch drill once more in LIVE before the first trade. Automated rehearsals:
`tests/integration/test_drills_live.py`, `tests/unit/test_backup.py`.

| Drill | Steps | Expected |
|---|---|---|
| Kill switch HALT | `python -m app.cli kill --reason "drill"`, then release with `kill --release --reason "drill done"` | PWA shows the kill-switch banner; no new orders (`order_send` count unchanged); open positions still managed; after release the gate passes |
| Kill switch FLATTEN | PWA → Risk & controls → Flatten all (step-up + engine code), or `kill --mode FLATTEN --reason "drill"` | every bot position closed at the broker; manual positions untouched |
| Breaker reset | `breaker list`; reset a tripped breaker: `breaker reset NAME --reason "..."` (`--ack` for MAX_DRAWDOWN) | the gate fails while it is latched and passes after the reset; the reset is in `audit verify` |
| Credential rotation | PWA → Engines → Rotate (step-up): put the new `ENGINE_HMAC_SECRET` in `.env` and restart the engine. `python -m app.cli engine new-totp` for `CONTROL_TOTP_SECRET` | the old secret is refused (401); the engine reconnects with the new one; a close with the new control code works |
| Restore from backup | `python -m app.cli db backup`; stop the engine; `db restore --from <file> --confirm <file name>`; `audit verify`; start | the backup passes integrity and audit-chain checks; the old database is kept as `*.before-restore-<time>`; the engine reconciles with the broker before anything else |
| Engine offline | stop the engine with Ctrl+C, and once by killing its window | a deliberate stop shows "stopped" without an alarm; a killed engine shows "offline" and a push arrives (watchdog); restarting recognises its positions and resends nothing |

Record:

| Date | Drill | Mode | Result | Notes |
|---|---|---|---|---|
| | | | | |

## 3. Start, watch, stop

| Action | Command |
|---|---|
| start | `.venv\Scripts\python -m app.main --mode live` |
| what you should see | the block **LIVE TRADING: REAL MONEY** warning in the log; `LIVE_START` in the audit log; the red LIVE banner in the PWA; Risk & controls → "Risk limits in use" (with the entry split the bot follows) |
| halt at once | `python -m app.cli kill --reason "..."` (or the PWA, step-up) |
| back to safety | stop the engine, set `TRADING_MODE=PAPER` (`ENABLE_LIVE_TRADING=false`), start with `--mode paper`. Open LIVE positions stay at the broker with their stops: close them in MT5 or flatten first. |

First days: check every order in the terminal (stop-loss present, volume as planned; with a split plan also
the resting limit orders and that they disappear after their lifetime or when the first part closes), the PWA's
decisions and the daily P/L against the limits. Halt at once on any order you do not understand.

## 4. When something is wrong

Everything in RUNBOOK_DEMO §5 applies. In addition:

| Symptom | What to do |
|---|---|
| The engine refuses to start: "LIVE trading needs …" | A gate condition is missing (flag, phrase, REAL account, Algo Trading). Fix it. Never weaken a check. |
| LIVE_GATE_FAILED on decisions | Read the failed conditions in the decision detail (kill switch, a latched breaker, account or terminal permissions). |
| A position you did not expect | Halt, compare the terminal with PWA → Positions (bot magic `7310000`+ vs manual), read `audit verify` and the logs before anything else. |
